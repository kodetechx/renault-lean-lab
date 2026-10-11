"""
build_yolo_dataset.py

Une os varios .zip exportados do CVAT, de qualquer numero de lotes, em
formato "YOLO 1.1" (so retangulos) e/ou "CVAT for images 1.1" (annotations.xml,
guarda poligono, elipse etc. -- cada forma vira a caixa que a envolve). Os dois
formatos podem ser misturados na mesma pasta de zips. em um unico dataset pronto para treinar com Ultralytics YOLO.

POR QUE ISSO E NECESSARIO (e nao um simples "descompacta tudo junto"):
No formato YOLO 1.1 do CVAT, cada arquivo de anotacao .txt referencia a
classe por um NUMERO (ex.: "0 0.5 0.5 0.2 0.3"), e esse numero e a posicao
da classe dentro do arquivo obj.names DAQUELE zip especifico. Como cada zip
foi exportado separadamente, nao ha garantia de que "classe 0" signifique a
mesma coisa em todos os zips. Este script le o obj.names de CADA zip e
remapeia os IDs para a lista global MASTER_CLASSES, usando o NOME da classe
como chave -- nunca o numero.

O QUE ELE FAZ:
1. Descompacta cada .zip informado (lote 1, lote 2, ... todos juntos).
2. Mapeia "id local -> nome -> id global" por zip.
3. Le cada anotacao .txt e reescreve o ID de classe. Linhas em formato de
   poligono (segmentacao) sao convertidas para a caixa que envolve o
   poligono; linhas invalidas sao descartadas e contadas no relatorio.
4. Acha a imagem original de cada anotacao (indexando --images_dir uma vez).
5. Se a MESMA imagem aparece em mais de um zip (ex.: reanotada no lote 2 com
   parafuso/encaixe), mantem so uma versao -- a que tem mais anotacoes --
   para a mesma foto nao cair em treino E validacao ao mesmo tempo.
6. Divide treino/validacao de forma estratificada: garante exemplos de TODA
   classe na validacao (o treino anterior teve 'parafuso' com zero exemplos
   na validacao, o que tornava o resultado dessa classe sem sentido).
7. Escreve images/train|val, labels/train|val e data.yaml, e imprime um
   relatorio com instancias por classe em treino e validacao.

SEGURANCA: este script so LE os zips e as imagens originais; nunca altera,
move ou apaga nada deles. Tudo e gravado (copiado) em --out_dir, que precisa
ser uma pasta nova e fora de --zips_dir/--images_dir.

Uso:
    python build_yolo_dataset.py --zips_dir ./cvat_exports \
        --images_dir ./raw_images --out_dir ./dataset_yolo_v2 --val_ratio 0.2

--zips_dir deve conter TODOS os zips que entram no treino (lote 1 + lote 2).
--images_dir deve conter TODAS as imagens originais (pode ter subpastas).
"""
import argparse
import hashlib
import random
import shutil
import tempfile
import math
import xml.etree.ElementTree as ET
import zipfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List, Optional

# Lista global e definitiva de classes, na ordem que vira o ID usado no
# treino. A ordem das 6 primeiras NAO deve mudar em relacao ao primeiro
# treino (so foram acrescentadas classes no final).
MASTER_CLASSES = [
    "camada_base",
    "camada_verde",
    "camada_amarela",
    "camada_azul",
    "camada_vermelha",
    "parafuso",
    "encaixe_circular",
    "encaixe_retangular",
    "encaixe_hexagono",
    "encaixe_capsula",
]

RESERVED_FILENAMES = {"obj.data", "obj.names", "train.txt", "valid.txt", "val.txt", "test.txt"}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}
MIN_TRAIN_INSTANCES_WARN = 30  # abaixo disso, avisa que a classe tem pouco exemplo


# ---------------------------------------------------------------- utilidades
def build_image_index(images_dir: Path) -> Dict[str, List[Path]]:
    """Varre --images_dir uma unica vez: nome-sem-extensao -> lista de caminhos."""
    index = defaultdict(list)
    for p in images_dir.rglob("*"):
        if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS:
            index[p.stem].append(p)
    return index


def file_md5(path: Path) -> str:
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def resolve_image(stem: str, index: Dict[str, List[Path]], stats: dict) -> Optional[Path]:
    candidates = index.get(stem, [])
    if not candidates:
        return None
    if len(candidates) > 1:
        # Varios arquivos com o mesmo nome em pastas diferentes. Se forem
        # identicos byte a byte, tanto faz; se forem diferentes, a anotacao
        # pode estar sendo ligada a foto errada -- registra para revisao.
        hashes = {file_md5(c) for c in candidates}
        if len(hashes) > 1:
            stats["imagens_ambiguas"].append((stem, [str(c) for c in candidates]))
    return candidates[0]


def read_class_names(tmp_path: Path) -> Optional[List[str]]:
    """Le a lista de classes do zip: obj.names (YOLO 1.1) ou data.yaml (Ultralytics)."""
    matches = list(tmp_path.rglob("obj.names"))
    if matches:
        return [l.strip() for l in matches[0].read_text(encoding="utf-8").splitlines() if l.strip()]

    yaml_matches = list(tmp_path.rglob("data.yaml"))
    if yaml_matches:
        try:
            import yaml  # PyYAML ja vem instalado junto com o ultralytics
        except ImportError:
            return None
        data = yaml.safe_load(yaml_matches[0].read_text(encoding="utf-8"))
        names = data.get("names")
        if isinstance(names, dict):
            return [names[k] for k in sorted(names, key=int)]
        if isinstance(names, list):
            return names
    return None


def parse_label_line(parts: List[str]):
    """
    Converte uma linha de anotacao em (local_id, x_c, y_c, w, h) normalizados.
      - 5 campos: caixa normal (formato de deteccao).
      - >5 campos com numero par de coordenadas: poligono (formato de
        segmentacao) -> usa a caixa que envolve todos os pontos.
    Devolve (tupla, tipo) onde tipo e 'caixa', 'poligono' ou None se invalida.
    """
    try:
        local_id = int(parts[0])
        values = [float(v) for v in parts[1:]]
    except ValueError:
        return None, None

    if len(values) == 4:
        return (local_id, *values), "caixa"

    if len(values) >= 6 and len(values) % 2 == 0:
        xs, ys = values[0::2], values[1::2]
        x_min, x_max, y_min, y_max = min(xs), max(xs), min(ys), max(ys)
        w, h = x_max - x_min, y_max - y_min
        if w <= 0 or h <= 0:
            return None, None
        return (local_id, (x_min + x_max) / 2, (y_min + y_max) / 2, w, h), "poligono"

    return None, None


# ------------------------------------------------------------- processamento
def _bbox_from_points(points):
    xs, ys = [p[0] for p in points], [p[1] for p in points]
    return min(xs), min(ys), max(xs), max(ys)


def _parse_points(text: str):
    return [tuple(float(v) for v in pair.split(",")) for pair in text.split(";") if pair.strip()]


def _rotated_rect_bbox(xtl, ytl, xbr, ybr, deg):
    cx, cy = (xtl + xbr) / 2, (ytl + ybr) / 2
    a = math.radians(deg)
    pts = []
    for x, y in ((xtl, ytl), (xbr, ytl), (xbr, ybr), (xtl, ybr)):
        dx, dy = x - cx, y - cy
        pts.append((cx + dx * math.cos(a) - dy * math.sin(a), cy + dx * math.sin(a) + dy * math.cos(a)))
    return _bbox_from_points(pts)


def parse_cvat_xml(xml_path: Path):
    """
    Le o export "CVAT for images 1.1" (annotations.xml), que guarda TODAS as formas.
    Devolve lista de (stem_da_imagem, [(nome_da_classe, x_c, y_c, w, h, tipo)], formas_ignoradas)
    com coordenadas normalizadas. Qualquer forma vira a caixa que a envolve:
      box -> ela mesma (considera rotacao), polygon/polyline -> caixa dos pontos,
      ellipse -> caixa da elipse (considera rotacao). 'points', 'mask' e 'tag' nao
      tem como virar caixa e sao ignorados (e contados).
    """
    result = []
    for img in ET.parse(xml_path).getroot().iter("image"):
        W, H = float(img.get("width")), float(img.get("height"))
        stem = Path(img.get("name").replace("\\", "/")).stem
        boxes, ignoradas = [], Counter()
        for shape in img:
            kind, label = shape.tag, shape.get("label")
            if kind == "box":
                x0, y0, x1, y1 = (float(shape.get(k)) for k in ("xtl", "ytl", "xbr", "ybr"))
                bb = _rotated_rect_bbox(x0, y0, x1, y1, float(shape.get("rotation", 0)))
            elif kind in ("polygon", "polyline"):
                bb = _bbox_from_points(_parse_points(shape.get("points")))
            elif kind == "ellipse":
                cx, cy, rx, ry = (float(shape.get(k)) for k in ("cx", "cy", "rx", "ry"))
                a = math.radians(float(shape.get("rotation", 0)))
                hw = math.hypot(rx * math.cos(a), ry * math.sin(a))
                hh = math.hypot(rx * math.sin(a), ry * math.cos(a))
                bb = (cx - hw, cy - hh, cx + hw, cy + hh)
            else:
                ignoradas[kind] += 1
                continue
            x0, y0, x1, y1 = max(0.0, bb[0]), max(0.0, bb[1]), min(W, bb[2]), min(H, bb[3])
            if x1 - x0 <= 0 or y1 - y0 <= 0:
                ignoradas["vazia"] += 1
                continue
            boxes.append((label, (x0 + x1) / 2 / W, (y0 + y1) / 2 / H, (x1 - x0) / W, (y1 - y0) / H, kind))
        result.append((stem, boxes, ignoradas))
    return result


def _register(stem, boxes, zip_path, image_index, collected, stats, zip_stats):
    """Parte comum aos dois formatos: acha a foto, trata vazio e duplicata."""
    image_path = resolve_image(stem, image_index, stats)
    if image_path is None:
        stats["imagens_nao_encontradas"].append(f"{zip_path.name}::{stem}")
        return
    if not boxes:
        zip_stats["imagens_sem_anotacao"] += 1
        stats["labels_vazios"].append(f"{zip_path.name}::{stem}")
        return
    key = file_md5(image_path)  # mesma foto em zips diferentes tem caminhos diferentes, mas o mesmo conteudo
    previous = collected.get(key)
    if previous is not None:
        stats["duplicatas"].append((stem, previous["zip"], zip_path.name))
        if len(boxes) <= len(previous["boxes"]):
            return
    collected[key] = {"image_src": image_path, "boxes": boxes, "zip": zip_path.name, "stem": stem}


def process_zip(zip_path: Path, image_index: dict, global_index: dict, collected: dict, stats: dict, work_dir: Path):
    zip_stats = Counter()
    # Extrai numa pasta de trabalho que sobrevive ate o fim do build (as fotos de
    # dentro do zip precisam existir quando forem copiadas para o dataset).
    tmp_path = work_dir / zip_path.stem
    tmp_path.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(tmp_path)

    # Fotos que vieram DENTRO do zip (export com "Save images") tem prioridade;
    # as de --images_dir sao o plano B. Assim cada anotacao fica com a foto do seu proprio zip.
    local_index = build_image_index(tmp_path)
    if local_index:
        print(f"  {sum(len(v) for v in local_index.values())} imagens dentro do zip.")
        image_index = {**image_index, **local_index}

    if True:
        xml_files = list(tmp_path.rglob("annotations.xml"))
        if xml_files:
            # ---- formato "CVAT for images 1.1": classes pelo NOME, todas as formas ----
            for stem, shapes, ignoradas in parse_cvat_xml(xml_files[0]):
                for kind, n in ignoradas.items():
                    zip_stats[f"formas_ignoradas_{kind}"] += n
                boxes = []
                for label, x, y, w, h, kind in shapes:
                    if label not in global_index:
                        stats["classes_desconhecidas"].add(label)
                        continue
                    if kind != "box":
                        zip_stats[f"{kind}_convertidos_em_caixa"] += 1
                    boxes.append((global_index[label], x, y, w, h))
                _register(stem, boxes, zip_path, image_index, collected, stats, zip_stats)
        else:
            # ---- formato "YOLO 1.1": remapeia o ID local pelo NOME da classe ----
            local_classes = read_class_names(tmp_path)
            if local_classes is None:
                print(f"  [AVISO] '{zip_path.name}' nao contem annotations.xml, obj.names nem data.yaml -- pulando este zip.")
                return

            local_to_global = {}
            for local_id, class_name in enumerate(local_classes):
                if class_name not in global_index:
                    stats["classes_desconhecidas"].add(class_name)
                    continue
                local_to_global[local_id] = global_index[class_name]

            label_files = [p for p in tmp_path.rglob("*.txt") if p.name not in RESERVED_FILENAMES]
            if not label_files:
                print(f"  [AVISO] '{zip_path.name}' nao contem arquivos de anotacao .txt de imagem.")
                return

            for label_path in label_files:
                boxes = []
                for line in label_path.read_text(encoding="utf-8").splitlines():
                    parts = line.strip().split()
                    if not parts:
                        continue
                    parsed, kind = parse_label_line(parts)
                    if parsed is None:
                        zip_stats["linhas_invalidas"] += 1
                        continue
                    local_id, x, y, w, h = parsed
                    if local_id not in local_to_global:
                        continue  # classe desconhecida, ja registrada acima
                    if kind == "poligono":
                        zip_stats["poligonos_convertidos_em_caixa"] += 1
                    boxes.append((local_to_global[local_id], x, y, w, h))
                _register(label_path.stem, boxes, zip_path, image_index, collected, stats, zip_stats)

    for k, v in zip_stats.items():
        stats["por_zip"][zip_path.name][k] += v
    stats["por_zip"][zip_path.name]["imagens_com_anotacao"] = sum(
        1 for item in collected.values() if item["zip"] == zip_path.name
    )


def count_by_class(items: List[dict]) -> Counter:
    c = Counter()
    for item in items:
        for gid, *_ in item["boxes"]:
            c[MASTER_CLASSES[gid]] += 1
    return c


def stratified_split(keys: List[str], collected: dict, val_ratio: float, seed: int) -> set:
    """
    Escolhe as imagens de validacao garantindo que cada classe (com 2+ exemplos
    no total) tenha ~val_ratio das suas instancias na validacao E ao menos uma
    instancia sobrando no treino. Classes mais raras sao tratadas primeiro.
    """
    rng = random.Random(seed)
    keys = sorted(keys)
    rng.shuffle(keys)

    per_image = {k: Counter(MASTER_CLASSES[g] for g, *_ in collected[k]["boxes"]) for k in keys}
    total = Counter()
    for c in per_image.values():
        total.update(c)

    target = {cls: max(1, round(n * val_ratio)) for cls, n in total.items() if n >= 2}
    val, val_count = set(), Counter()

    def leaves_train_ok(k):
        # nao deixa nenhuma classe sem exemplo no treino
        return all(total[c] - val_count[c] - n >= 1 for c, n in per_image[k].items())

    for cls in sorted(target, key=lambda c: total[c]):  # mais rara primeiro
        for k in keys:
            if val_count[cls] >= target[cls]:
                break
            if k in val or cls not in per_image[k] or not leaves_train_ok(k):
                continue
            val.add(k)
            val_count.update(per_image[k])

    n_val = max(len(val), max(1, int(len(keys) * val_ratio)))
    for k in keys:
        if len(val) >= n_val:
            break
        if k not in val and leaves_train_ok(k):
            val.add(k)
            val_count.update(per_image[k])
    return val


# ------------------------------------------------------------------- principal
def main():
    parser = argparse.ArgumentParser(description="Une exports YOLO 1.1 do CVAT em um dataset unico para treino")
    parser.add_argument("--zips_dir", required=True, help="Pasta contendo TODOS os .zip exportados do CVAT (todos os lotes)")
    parser.add_argument("--images_dir", required=True, help="Pasta com as imagens originais (pode ter subpastas)")
    parser.add_argument("--out_dir", required=True, help="Pasta de saida do dataset unificado (use uma pasta NOVA)")
    parser.add_argument("--val_ratio", type=float, default=0.2, help="Fracao dos dados para validacao (default 0.2)")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    zips_dir, images_dir, out_dir = Path(args.zips_dir), Path(args.images_dir), Path(args.out_dir)

    zip_files = sorted(zips_dir.glob("*.zip"))
    if not zip_files:
        raise SystemExit(f"Nenhum .zip encontrado em {zips_dir}")
    out_abs = out_dir.resolve()
    for entrada in (zips_dir.resolve(), images_dir.resolve()):
        if out_abs == entrada or entrada in out_abs.parents:
            raise SystemExit(
                f"--out_dir ('{out_dir}') nao pode ficar dentro de '{entrada}': o script reindexaria a "
                "propria saida. Use uma pasta separada (ex.: ./dataset_yolo_v2 ao lado, nao dentro)."
            )
    if out_dir.exists() and any(out_dir.iterdir()):
        raise SystemExit(
            f"A pasta de saida '{out_dir}' ja existe e nao esta vazia. Use uma pasta nova "
            f"(ex.: ./dataset_yolo_v2) para nao misturar com o dataset anterior."
        )

    print(f"Indexando imagens em {images_dir} ...")
    image_index = build_image_index(images_dir)
    print(f"  {sum(len(v) for v in image_index.values())} imagens encontradas.\n")

    global_index = {name: i for i, name in enumerate(MASTER_CLASSES)}
    collected: Dict[str, dict] = {}
    stats = {
        "classes_desconhecidas": set(),
        "imagens_nao_encontradas": [],
        "imagens_ambiguas": [],
        "labels_vazios": [],
        "duplicatas": [],
        "por_zip": defaultdict(Counter),
    }

    print(f"Classes globais (nesta ordem viram os IDs de treino): {MASTER_CLASSES}\n")
    work_dir = Path(tempfile.mkdtemp(prefix="build_yolo_"))
    try:
        for zip_path in zip_files:
            print(f"Processando '{zip_path.name}'...")
            process_zip(zip_path, image_index, global_index, collected, stats, work_dir)
        _write_dataset(collected, out_dir, args, stats)
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


def _write_dataset(collected, out_dir, args, stats):

    if not collected:
        raise SystemExit("Nenhuma imagem/anotacao valida foi encontrada. Verifique os avisos acima.")

    # --- Split treino/validacao estratificado por classe ---
    keys = list(collected.keys())
    val_keys = stratified_split(keys, collected, args.val_ratio, args.seed)

    for split in ("train", "val"):
        (out_dir / "images" / split).mkdir(parents=True, exist_ok=True)
        (out_dir / "labels" / split).mkdir(parents=True, exist_ok=True)

    used_names = set()
    for key in keys:
        item = collected[key]
        split = "val" if key in val_keys else "train"
        # Prefixo do zip evita colisao de nomes; o sufixo numerico cobre o caso
        # raro de dois zips com o mesmo nome-base.
        base = f"{Path(item['zip']).stem}__{item['stem']}"
        name, n = base, 1
        while name in used_names:
            n += 1
            name = f"{base}_{n}"
        used_names.add(name)

        ext = item["image_src"].suffix.lower()
        shutil.copy2(item["image_src"], out_dir / "images" / split / f"{name}{ext}")
        lines = [f"{g} {x:.6f} {y:.6f} {w:.6f} {h:.6f}" for g, x, y, w, h in item["boxes"]]
        (out_dir / "labels" / split / f"{name}.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")

    # --- data.yaml para o Ultralytics ---
    names_yaml = "\n".join(f"  {i}: {name}" for i, name in enumerate(MASTER_CLASSES))
    data_yaml = out_dir / "data.yaml"
    data_yaml.write_text(
        f"path: {out_dir.resolve()}\ntrain: images/train\nval: images/val\nnames:\n{names_yaml}\n",
        encoding="utf-8",
    )

    # --- Relatorio ---
    train_items = [collected[k] for k in keys if k not in val_keys]
    val_items = [collected[k] for k in keys if k in val_keys]
    train_c, val_c = count_by_class(train_items), count_by_class(val_items)

    print("\n=== Resumo ===")
    print(f"Imagens em treino:    {len(train_items)}")
    print(f"Imagens em validacao: {len(val_items)}")

    print("\nPor zip:")
    for zname, c in stats["por_zip"].items():
        extra = ", ".join(f"{k}={v}" for k, v in sorted(c.items()))
        print(f"  {zname}: {extra}")

    print(f"\n{'classe':<22}{'treino':>8}{'validacao':>11}")
    problemas = []
    for name in MASTER_CLASSES:
        t, v = train_c.get(name, 0), val_c.get(name, 0)
        flag = ""
        if t + v == 0:
            flag = "  <-- SEM EXEMPLOS"
            problemas.append(f"'{name}' nao tem nenhuma anotacao")
        elif v == 0:
            flag = "  <-- sem exemplo na validacao"
            problemas.append(f"'{name}' sem exemplo na validacao (so 1 instancia no total)")
        elif t < MIN_TRAIN_INSTANCES_WARN:
            flag = "  <-- poucos exemplos"
            problemas.append(f"'{name}' com apenas {t} no treino")
        print(f"{name:<22}{t:>8}{v:>11}{flag}")

    if problemas:
        print("\n⚠️  Classes que merecem atencao antes de confiar no resultado do treino:")
        for p in problemas:
            print(f"  - {p}")

    if stats["classes_desconhecidas"]:
        print("\n⚠️  CLASSES ENCONTRADAS NOS ZIPS QUE NAO BATEM COM MASTER_CLASSES:")
        for name in sorted(stats["classes_desconhecidas"]):
            print(f"  '{name}' -- erro de digitacao no CVAT? ou falta adicionar em MASTER_CLASSES")

    formas = Counter()
    for c in stats["por_zip"].values():
        for k, v in c.items():
            if k.endswith("_convertidos_em_caixa"):
                formas[k.replace("_convertidos_em_caixa", "")] += v
            elif k.startswith("formas_ignoradas_"):
                formas["IGNORADA:" + k.replace("formas_ignoradas_", "")] += v
    for k, v in sorted(formas.items()):
        if k.startswith("IGNORADA:"):
            print(f"\n⚠️  {v} forma(s) do tipo '{k[9:]}' foram IGNORADAS (nao tem como virar caixa).")
        else:
            print(f"\nℹ️  {v} {k}(s) convertido(s) para a caixa que o envolve.")
    poligonos = sum(c.get("poligonos_convertidos_em_caixa", 0) for c in stats["por_zip"].values())
    invalidas = sum(c.get("linhas_invalidas", 0) for c in stats["por_zip"].values())
    if poligonos:
        print(f"\nℹ️  {poligonos} anotacao(oes) em formato de poligono foram convertidas para a caixa que as envolve.")
    if invalidas:
        print(f"\n⚠️  {invalidas} linha(s) de anotacao com formato invalido foram descartadas.")

    if stats["labels_vazios"]:
        print(
            f"\n⚠️  {len(stats['labels_vazios'])} imagem(ns) sem nenhuma anotacao utilizavel (ficaram FORA do dataset). "
            "Se voce anotou essas imagens com poligono/elipse, o exportador 'YOLO 1.1' pode ter ignorado "
            "essas formas em silencio -- confira no CVAT e, se for o caso, refaca como retangulo:"
        )
        for s in stats["labels_vazios"][:10]:
            print(f"  {s}")
        if len(stats["labels_vazios"]) > 10:
            print(f"  ... e mais {len(stats['labels_vazios']) - 10}")

    if stats["duplicatas"]:
        print(
            f"\nℹ️  {len(stats['duplicatas'])} imagem(ns) apareciam em mais de um zip; "
            "ficou so a versao com mais anotacoes (evita a mesma foto em treino e validacao):"
        )
        for stem, z1, z2 in stats["duplicatas"][:5]:
            print(f"  {stem}  ({z1} x {z2})")

    if stats["imagens_ambiguas"]:
        print(
            f"\n⚠️  {len(stats['imagens_ambiguas'])} nome(s) de imagem existem em mais de uma pasta com "
            "CONTEUDO DIFERENTE -- a anotacao pode ter sido ligada a foto errada. Renomeie para ficarem unicos:"
        )
        for stem, paths in stats["imagens_ambiguas"][:5]:
            print(f"  {stem}: {paths}")

    if stats["imagens_nao_encontradas"]:
        print(f"\n⚠️  {len(stats['imagens_nao_encontradas'])} anotacao(oes) sem imagem correspondente em --images_dir:")
        for stem in stats["imagens_nao_encontradas"][:10]:
            print(f"  {stem}")
        if len(stats["imagens_nao_encontradas"]) > 10:
            print(f"  ... e mais {len(stats['imagens_nao_encontradas']) - 10}")

    print(f"\nDataset pronto em: {out_dir.resolve()}")
    print(f"Arquivo de configuracao: {data_yaml.resolve()}")


if __name__ == "__main__":
    main()