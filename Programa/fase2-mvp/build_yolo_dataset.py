"""
build_yolo_dataset.py

Une os varios .zip exportados do CVAT (formato "YOLO 1.1"), um por camada,
em um unico dataset pronto para treinar com Ultralytics YOLO.

POR QUE ISSO E NECESSARIO (e nao um simples "descompacta tudo junto"):
No formato YOLO 1.1 do CVAT, cada arquivo de anotacao .txt referencia a
classe por um NUMERO (ex.: "0 0.5 0.5 0.2 0.3"), e esse numero e a posicao
da classe dentro do arquivo obj.names DAQUELE zip especifico. Como cada zip
foi exportado separadamente (um por camada), nao ha garantia de que
"classe 0" signifique a mesma coisa em todos os zips — por exemplo,
"camada_verde" pode ser a classe 0 num zip e "camada_amarela" ser a classe 0
em outro. Se os arquivos forem simplesmente copiados juntos, o dataset final
fica com rotulos errados sem nenhum erro aparente.

Este script resolve isso lendo o obj.names de CADA zip e remapeando os
IDs para uma lista global fixa de classes (definida abaixo em
MASTER_CLASSES), usando o NOME da classe como chave — nunca o numero.

O QUE ELE FAZ:
1. Descompacta cada .zip informado.
2. Le obj.names de cada um e monta o mapa "id local -> nome -> id global".
3. Localiza os arquivos de anotacao .txt (um por imagem) e reescreve o ID
   de classe de cada linha para o ID global correspondente.
4. Encontra a imagem original correspondente a cada anotacao (buscando por
   nome de arquivo dentro de --images_dir, que pode ser a pasta
   raw_images/ ja usada nas fases anteriores).
5. Divide o conjunto em treino/validacao e organiza tudo na estrutura que
   o Ultralytics espera (images/train, images/val, labels/train,
   labels/val, data.yaml).
6. Imprime um relatorio: quantas instancias de cada classe, quantas
   imagens ficaram sem anotacao valida, e principalmente, quaisquer nomes
   de classe encontrados nos zips que NAO batem com MASTER_CLASSES (sinal
   de erro de digitacao ao criar os labels no CVAT — merece atencao antes
   de treinar).

Uso:
    python build_yolo_dataset.py --zips_dir ./cvat_exports \
        --images_dir ./raw_images --out_dir ./dataset_yolo --val_ratio 0.2
"""
import argparse
import random
import shutil
import tempfile
import zipfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, Optional

# Lista global e definitiva de classes, na ordem que vira o ID usado no
# treino (0 = camada_base, 1 = camada_verde, etc). Ajuste aqui se os nomes
# usados no CVAT forem diferentes destes.
MASTER_CLASSES = [
    "camada_base",
    "camada_verde",
    "camada_amarela",
    "camada_azul",
    "camada_vermelha",
    "parafuso",
]

RESERVED_FILENAMES = {"obj.data", "obj.names", "train.txt", "valid.txt"}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}


def find_file(root: Path, name: str) -> Optional[Path]:
    matches = list(root.rglob(name))
    return matches[0] if matches else None


def find_image(images_dir: Path, stem: str) -> Optional[Path]:
    for ext in IMAGE_EXTENSIONS:
        matches = list(images_dir.rglob(f"{stem}{ext}"))
        if matches:
            return matches[0]
    return None


def process_zip(zip_path: Path, images_dir: Path, global_index: dict, collected: dict, stats: dict):
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        with zipfile.ZipFile(zip_path) as zf:
            zf.extractall(tmp_path)

        names_file = find_file(tmp_path, "obj.names")
        if names_file is None:
            print(f"  [AVISO] '{zip_path.name}' nao contem obj.names — pulando este zip.")
            return

        local_classes = [line.strip() for line in names_file.read_text(encoding="utf-8").splitlines() if line.strip()]

        # Mapa: id local (posicao neste zip) -> id global (posicao em MASTER_CLASSES)
        local_to_global = {}
        for local_id, class_name in enumerate(local_classes):
            if class_name not in global_index:
                stats["classes_desconhecidas"].add(class_name)
                continue
            local_to_global[local_id] = global_index[class_name]

        label_files = [
            p for p in tmp_path.rglob("*.txt")
            if p.name not in RESERVED_FILENAMES
        ]

        if not label_files:
            print(f"  [AVISO] '{zip_path.name}' nao contem arquivos de anotacao .txt de imagem.")
            return

        for label_path in label_files:
            stem = label_path.stem
            image_path = find_image(images_dir, stem)
            if image_path is None:
                stats["imagens_nao_encontradas"].append(stem)
                continue

            remapped_lines = []
            for line in label_path.read_text(encoding="utf-8").splitlines():
                parts = line.strip().split()
                if not parts:
                    continue
                local_id = int(parts[0])
                if local_id not in local_to_global:
                    continue  # classe desconhecida, ja registrada em stats acima
                global_id = local_to_global[local_id]
                remapped_lines.append(" ".join([str(global_id)] + parts[1:]))
                stats["instancias_por_classe"][MASTER_CLASSES[global_id]] += 1

            if not remapped_lines:
                stats["labels_vazios_apos_remapeamento"].append(stem)
                continue

            # Usa o nome do zip como prefixo para evitar colisao de nomes
            # entre imagens de zips diferentes.
            unique_stem = f"{zip_path.stem}__{stem}"
            collected[unique_stem] = {
                "image_src": image_path,
                "label_lines": remapped_lines,
            }


def main():
    parser = argparse.ArgumentParser(description="Une exports YOLO 1.1 do CVAT em um dataset unico para treino")
    parser.add_argument("--zips_dir", required=True, help="Pasta contendo os .zip exportados do CVAT")
    parser.add_argument("--images_dir", required=True, help="Pasta com as imagens originais (ex.: raw_images/)")
    parser.add_argument("--out_dir", required=True, help="Pasta de saida do dataset unificado")
    parser.add_argument("--val_ratio", type=float, default=0.2, help="Fracao dos dados para validacao (default 0.2)")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    zips_dir = Path(args.zips_dir)
    images_dir = Path(args.images_dir)
    out_dir = Path(args.out_dir)

    zip_files = sorted(zips_dir.glob("*.zip"))
    if not zip_files:
        raise SystemExit(f"Nenhum .zip encontrado em {zips_dir}")

    global_index = {name: i for i, name in enumerate(MASTER_CLASSES)}
    collected: Dict[str, dict] = {}
    stats = {
        "classes_desconhecidas": set(),
        "imagens_nao_encontradas": [],
        "labels_vazios_apos_remapeamento": [],
        "instancias_por_classe": Counter(),
    }

    print(f"Classes globais (nesta ordem viram os IDs de treino): {MASTER_CLASSES}\n")

    for zip_path in zip_files:
        print(f"Processando '{zip_path.name}'...")
        process_zip(zip_path, images_dir, global_index, collected, stats)

    if not collected:
        raise SystemExit("Nenhuma imagem/anotacao valida foi encontrada. Verifique os avisos acima.")

    # --- Split treino/validacao ---
    stems = list(collected.keys())
    random.Random(args.seed).shuffle(stems)
    n_val = max(1, int(len(stems) * args.val_ratio))
    val_stems = set(stems[:n_val])

    for split in ("train", "val"):
        (out_dir / "images" / split).mkdir(parents=True, exist_ok=True)
        (out_dir / "labels" / split).mkdir(parents=True, exist_ok=True)

    for stem in stems:
        split = "val" if stem in val_stems else "train"
        item = collected[stem]
        ext = item["image_src"].suffix.lower()
        shutil.copy2(item["image_src"], out_dir / "images" / split / f"{stem}{ext}")
        (out_dir / "labels" / split / f"{stem}.txt").write_text("\n".join(item["label_lines"]) + "\n", encoding="utf-8")

    # --- data.yaml para o Ultralytics ---
    data_yaml = out_dir / "data.yaml"
    names_yaml = "\n".join(f"  {i}: {name}" for i, name in enumerate(MASTER_CLASSES))
    data_yaml.write_text(
        f"path: {out_dir.resolve()}\n"
        f"train: images/train\n"
        f"val: images/val\n"
        f"names:\n{names_yaml}\n",
        encoding="utf-8",
    )

    # --- Relatorio final ---
    n_train = len(stems) - len(val_stems)
    print("\n=== Resumo ===")
    print(f"Imagens em treino: {n_train}")
    print(f"Imagens em validacao: {len(val_stems)}")
    print("\nInstancias anotadas por classe:")
    for name in MASTER_CLASSES:
        print(f"  {name}: {stats['instancias_por_classe'].get(name, 0)}")

    if stats["classes_desconhecidas"]:
        print("\n⚠️  CLASSES ENCONTRADAS NOS ZIPS QUE NAO BATEM COM MASTER_CLASSES:")
        for name in sorted(stats["classes_desconhecidas"]):
            print(f"  '{name}' — verifique se e erro de digitacao no CVAT ou se falta adicionar em MASTER_CLASSES")

    if stats["imagens_nao_encontradas"]:
        print(f"\n⚠️  {len(stats['imagens_nao_encontradas'])} anotacao(oes) sem imagem correspondente encontrada em --images_dir:")
        for stem in stats["imagens_nao_encontradas"][:10]:
            print(f"  {stem}")
        if len(stats["imagens_nao_encontradas"]) > 10:
            print(f"  ... e mais {len(stats['imagens_nao_encontradas']) - 10}")

    if stats["labels_vazios_apos_remapeamento"]:
        print(f"\n⚠️  {len(stats['labels_vazios_apos_remapeamento'])} imagem(ns) ficaram sem nenhuma anotacao valida apos o remapeamento (todas as classes daquela imagem eram desconhecidas):")
        for stem in stats["labels_vazios_apos_remapeamento"][:10]:
            print(f"  {stem}")

    print(f"\nDataset pronto em: {out_dir.resolve()}")
    print(f"Arquivo de configuracao: {data_yaml.resolve()}")


if __name__ == "__main__":
    main()
