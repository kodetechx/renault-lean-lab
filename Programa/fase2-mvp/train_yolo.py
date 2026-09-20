"""
train_yolo.py

Treina um modelo de deteccao YOLO (Ultralytics) usando o dataset gerado por
build_yolo_dataset.py.

Antes de rodar, instale a biblioteca (uma unica vez):
    pip install ultralytics

Uso:
    python train_yolo.py --data ./dataset_yolo/data.yaml --epochs 50

Na primeira execucao, o Ultralytics baixa automaticamente o checkpoint
pre-treinado (ex.: yolo11n.pt) da internet — precisa de conexao.
"""
import argparse
from pathlib import Path

from ultralytics import YOLO


def main():
    parser = argparse.ArgumentParser(description="Treina um modelo YOLO com o dataset gerado")
    parser.add_argument("--data", required=True, help="Caminho para o data.yaml gerado por build_yolo_dataset.py")
    parser.add_argument(
        "--model",
        default="yolo11n.pt",
        help="Checkpoint base pre-treinado. 'n' (nano) e a variante mais leve, recomendada para CPU/notebook",
    )
    parser.add_argument("--epochs", type=int, default=50)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--batch", type=int, default=8, help="Reduza se faltar memoria (ex.: 4)")
    parser.add_argument("--project", default="runs_yolo", help="Pasta onde os resultados de treino sao salvos")
    parser.add_argument("--name", default="lean_lab_v1", help="Nome deste experimento de treino")
    args = parser.parse_args()

    model = YOLO(args.model)

    model.train(
        data=args.data,
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=args.batch,
        project=args.project,
        name=args.name,
    )

    print("\n=== Avaliando no conjunto de validacao ===")
    metrics = model.val()

    print(f"\nmAP50 geral (todas as classes):     {metrics.box.map50:.3f}")
    print(f"mAP50-95 geral (todas as classes):  {metrics.box.map:.3f}")

    # metrics.box.maps traz o mAP50-95 individual de cada classe, na mesma
    # ordem em que as classes aparecem no data.yaml (0, 1, 2, ...).
    class_names = model.names  # dict {indice: nome}
    print("\nmAP50-95 por classe:")
    for class_idx, class_map in enumerate(metrics.box.maps):
        name = class_names.get(class_idx, f"classe_{class_idx}")
        print(f"  {name}: {class_map:.3f}")

    print(
        "\nAtencao: a classe 'parafuso' tinha pouquissimos exemplos anotados neste lote "
        "(esperado, ainda falta a sessao de captura dedicada) — nao se surpreenda se o "
        "resultado dela vier proximo de zero. As classes de camada (cor) sao o indicador "
        "real de qualidade deste primeiro teste."
    )

    best_weights = Path(args.project) / args.name / "weights" / "best.pt"
    print(f"\nMelhor modelo salvo em: {best_weights.resolve()}")
    print("Use esse arquivo .pt no proximo passo (inferencia ao vivo pela webcam).")


if __name__ == "__main__":
    main()
