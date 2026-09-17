"""
find_misclassified.py

Roda o modelo ja treinado sobre o conjunto de teste e lista exatamente quais
arquivos foram classificados incorretamente (classe real vs. classe
prevista), para inspecao manual.

Uso:
    python find_misclassified.py --dataset_dir ./dataset --model modelo_camada.keras \
        --class_names class_names.json

Para copiar as imagens erradas para uma pasta separada (facilita abrir todas
de uma vez):
    python find_misclassified.py --dataset_dir ./dataset --model modelo_camada.keras \
        --class_names class_names.json --copy_to ./erros_revisao
"""
import argparse
import json
import shutil
from pathlib import Path

import numpy as np
import tensorflow as tf


def main():
    parser = argparse.ArgumentParser(description="Lista as imagens de teste classificadas incorretamente")
    parser.add_argument("--dataset_dir", required=True, help="Pasta com train/val/test")
    parser.add_argument("--model", required=True)
    parser.add_argument("--class_names", required=True)
    parser.add_argument("--img_size", type=int, default=224)
    parser.add_argument("--batch_size", type=int, default=16)
    parser.add_argument("--copy_to", default=None, help="Se informado, copia as imagens erradas para esta pasta")
    args = parser.parse_args()

    dataset_dir = Path(args.dataset_dir)

    # shuffle=False garante que a ordem das imagens bate com a ordem de file_paths
    test_ds = tf.keras.utils.image_dataset_from_directory(
        dataset_dir / "test",
        image_size=(args.img_size, args.img_size),
        batch_size=args.batch_size,
        shuffle=False,
    )
    file_paths = test_ds.file_paths  # caminho de cada imagem, na mesma ordem dos batches

    model = tf.keras.models.load_model(args.model)
    with open(args.class_names, "r", encoding="utf-8") as f:
        class_names = json.load(f)

    y_true = np.concatenate([y.numpy() for _, y in test_ds])
    y_pred_probs = model.predict(test_ds)
    y_pred = np.argmax(y_pred_probs, axis=1)

    if args.copy_to:
        copy_dir = Path(args.copy_to)
        copy_dir.mkdir(parents=True, exist_ok=True)

    print("=== Imagens classificadas incorretamente ===\n")
    count = 0
    for path, true_idx, pred_idx, probs in zip(file_paths, y_true, y_pred, y_pred_probs):
        if true_idx == pred_idx:
            continue
        count += 1
        conf = probs[pred_idx]
        print(f"{count}. {path}")
        print(f"   Real: {class_names[true_idx]}  |  Previsto: {class_names[pred_idx]} (confianca {conf:.1%})\n")

        if args.copy_to:
            origem = Path(path)
            destino = copy_dir / f"real_{class_names[true_idx]}__previsto_{class_names[pred_idx]}__{origem.name}"
            shutil.copy2(origem, destino)

    if count == 0:
        print("Nenhum erro encontrado no conjunto de teste.")
    else:
        print(f"Total: {count} imagem(ns) incorreta(s) de {len(file_paths)} no conjunto de teste.")
        if args.copy_to:
            print(f"Imagens copiadas para: {Path(args.copy_to).resolve()}")


if __name__ == "__main__":
    main()
