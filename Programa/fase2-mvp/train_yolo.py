"""
train_yolo.py

Treina um modelo de deteccao YOLO (Ultralytics) usando o dataset gerado por
build_yolo_dataset.py.

Antes de rodar, instale a biblioteca (uma unica vez):
    pip install ultralytics

Uso -- primeiro treino (a partir do checkpoint generico):
    python train_yolo.py --data ./dataset_yolo/data.yaml --epochs 50

Uso -- retreino a partir do modelo anterior (fine-tuning), com as 10 classes,
em notebook com GPU de pouca VRAM (ex.: RTX 2050, 4GB) e pouca RAM (ex.: 8GB):
    python train_yolo.py --data ./dataset_yolo_v2/data.yaml \
        --model "<caminho do best.pt do treino anterior>" \
        --name lean_lab_v2 --epochs 60 --imgsz 960 --batch -1 --workers 4

Sobre --model apontando para um best.pt com MENOS classes: o Ultralytics
aproveita o que o modelo ja aprendeu (as camadas internas) e recria sozinho
a camada de saida para o novo numero de classes. Isso e esperado -- aparece
no log como "Transferred N/M items from pretrained weights".

Sobre --imgsz: parafuso e pecas de encaixe sao objetos pequenos dentro da
cena. Com o padrao (640) eles encolhem bastante. Se a deteccao deles vier
fraca, 960 costuma ajudar (mais lento, e pode exigir --batch menor).

Sobre --batch -1 (AutoBatch): deixa o Ultralytics escolher o maior batch que
cabe em ~60% da VRAM da GPU, em vez de arriscar um numero fixo. Em uma GPU de
4GB (ex.: RTX 2050) com --imgsz 960, o AutoBatch mede na pratica batch=2 --
testado e confirmado neste projeto. So use um numero fixo se already souber
que ele cabe.

Sobre --device e --workers: por padrao o Ultralytics usa a GPU
automaticamente se o torch instalado tiver suporte a CUDA (confira com
`python -c "import torch; print(torch.cuda.is_available())"` -- se vier
False, o pacote `torch` instalado e a build CPU-only, e o treino roda muito
mais lento). --workers controla quantos processos carregam imagens em
paralelo; em notebooks com pouca RAM (ex.: 8GB), o padrao do Ultralytics (8)
pode esgotar a memoria antes mesmo da primeira epoca -- foi o que aconteceu
num treino anterior deste projeto (processo morto sem gerar results.csv).
"""
import argparse
from pathlib import Path


def count_val_instances(data_yaml: Path):
    """
    Conta quantas instancias de cada classe existem nos labels de VALIDACAO,
    lendo os .txt direto (independe de detalhes internos do Ultralytics).
    Devolve (nomes_das_classes_por_indice, Counter indice->contagem).
    """
    import yaml
    from collections import Counter

    cfg = yaml.safe_load(data_yaml.read_text(encoding="utf-8"))
    names = cfg["names"]
    if isinstance(names, list):
        names = dict(enumerate(names))
    names = {int(k): v for k, v in names.items()}

    root = Path(cfg.get("path", data_yaml.parent))
    val_images = Path(cfg["val"])
    # images/val -> labels/val (convencao do Ultralytics)
    labels_dir = root / str(val_images).replace("images", "labels", 1)

    counts = Counter()
    if labels_dir.exists():
        for txt in labels_dir.glob("*.txt"):
            for line in txt.read_text(encoding="utf-8").splitlines():
                parts = line.split()
                if parts:
                    counts[int(parts[0])] += 1
    return names, counts


def main():
    parser = argparse.ArgumentParser(description="Treina um modelo YOLO com o dataset gerado")
    parser.add_argument("--data", required=True, help="Caminho para o data.yaml gerado por build_yolo_dataset.py")
    parser.add_argument(
        "--model",
        default="yolo11n.pt",
        help=(
            "Checkpoint base. 'yolo11n.pt' (nano) para comecar do zero; ou o best.pt de um treino anterior "
            "para continuar a partir dele (fine-tuning)."
        ),
    )
    parser.add_argument("--epochs", type=int, default=50)
    parser.add_argument("--imgsz", type=int, default=640, help="Tamanho da imagem no treino. Tente 960 para objetos pequenos.")
    parser.add_argument(
        "--batch", type=int, default=8, help="Numero fixo, ou -1 para o Ultralytics escolher (AutoBatch, so com GPU)"
    )
    parser.add_argument(
        "--device",
        default="",
        help="'' deixa o Ultralytics escolher (GPU se o torch tiver CUDA, senao CPU); '0' forca a 1a GPU; 'cpu' forca CPU",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=4,
        help="Processos paralelos para carregar imagens. Reduza (ex.: 2) se faltar RAM; o padrao do Ultralytics e 8",
    )
    parser.add_argument("--project", default="runs_yolo", help="Pasta onde os resultados de treino sao salvos")
    parser.add_argument("--name", default="lean_lab_v2", help="Nome deste experimento de treino")
    args = parser.parse_args()

    from ultralytics import YOLO

    data_yaml = Path(args.data).resolve()
    # Caminho ABSOLUTO: sem isso o Ultralytics pode gravar dentro da pasta
    # 'runs/detect' configurada nas settings dele (foi o que escondeu o
    # best.pt do primeiro treino em runs/detect/runs_yolo/...).
    project_dir = Path(args.project).resolve()

    model = YOLO(args.model)

    model.train(
        data=str(data_yaml),
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=args.batch,
        device=args.device,
        workers=args.workers,
        project=str(project_dir),
        name=args.name,
    )

    # Pasta REAL onde o Ultralytics salvou (pode ter ganho sufixo numerico).
    save_dir = Path(getattr(model.trainer, "save_dir", project_dir / args.name))
    best_weights = save_dir / "weights" / "best.pt"

    print("\n=== Avaliando no conjunto de validacao ===")
    metrics = model.val()

    print(f"\nmAP50 geral (todas as classes):     {metrics.box.map50:.3f}")
    print(f"mAP50-95 geral (todas as classes):  {metrics.box.map:.3f}")

    # IMPORTANTE: para uma classe SEM nenhum exemplo na validacao, o Ultralytics
    # nao deixa zero em metrics.box.maps -- ele preenche com o mAP50-95 GERAL.
    # Foi isso que fez 'parafuso' aparecer com 0.965 no primeiro treino. Por
    # isso a tabela abaixo mostra quantos exemplos de validacao cada classe tem
    # e marca os numeros que nao significam nada.
    names, val_counts = count_val_instances(data_yaml)
    print(f"\n{'classe':<22}{'mAP50-95':>10}{'ex. na validacao':>20}")
    sem_validacao, poucos = [], []
    for idx, class_map in enumerate(metrics.box.maps):
        name = names.get(idx, f"classe_{idx}")
        n = val_counts.get(idx, 0)
        if n == 0:
            nota = "  <-- IGNORE (sem exemplos na validacao)"
            sem_validacao.append(name)
        elif n < 10:
            nota = "  <-- poucos exemplos, numero instavel"
            poucos.append(name)
        else:
            nota = ""
        print(f"{name:<22}{class_map:>10.3f}{n:>20}{nota}")

    if sem_validacao:
        print(
            f"\nAtencao: {sem_validacao} nao tem exemplos na validacao -- o mAP dessas classes e o valor geral "
            "repetido, nao uma medida real. Refaca o build_yolo_dataset.py (ele tenta garantir exemplos de "
            "toda classe na validacao) ou anote mais imagens dessas classes."
        )
    if poucos:
        print(f"\nAtencao: {poucos} tem menos de 10 exemplos na validacao; trate esses numeros com cautela.")

    print(f"\nMelhor modelo salvo em: {best_weights.resolve()}")
    print("Use esse arquivo .pt no proximo passo (inferencia ao vivo pela webcam).")


if __name__ == "__main__":
    main()