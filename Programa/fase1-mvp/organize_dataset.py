"""
organize_dataset.py

Organiza as imagens brutas (separadas em pastas por classe) em uma estrutura
de treino/validacao/teste, pronta para ser usada pelo train_classifier.py.

Estrutura esperada na pasta de entrada (--raw_dir):
    raw_dir/
        base/
        camada_verde/
        camada_amarela/
        camada_azul/
        camada_vermelha/

Gera a pasta de saida (--out_dir):
    out_dir/
        train/<classe>/...
        val/<classe>/...
        test/<classe>/...

Exemplo de uso:
    python organize_dataset.py --raw_dir ./raw_images --out_dir ./dataset \
        --train 0.7 --val 0.15 --test 0.15 --balance
"""
import argparse
import random
import shutil
from pathlib import Path


def split_class_files(files, train_ratio, val_ratio, seed):
    random.Random(seed).shuffle(files)
    n = len(files)
    n_train = int(n * train_ratio)
    n_val = int(n * val_ratio)
    train_files = files[:n_train]
    val_files = files[n_train:n_train + n_val]
    test_files = files[n_train + n_val:]
    return train_files, val_files, test_files


def main():
    parser = argparse.ArgumentParser(description="Organiza dataset em train/val/test")
    parser.add_argument("--raw_dir", required=True, help="Pasta com subpastas por classe")
    parser.add_argument("--out_dir", required=True, help="Pasta de saida")
    parser.add_argument("--train", type=float, default=0.7)
    parser.add_argument("--val", type=float, default=0.15)
    parser.add_argument("--test", type=float, default=0.15)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--balance",
        action="store_true",
        help="Limita todas as classes ao tamanho da menor classe (evita desbalanceamento)",
    )
    args = parser.parse_args()

    assert abs(args.train + args.val + args.test - 1.0) < 1e-6, "As proporcoes devem somar 1.0"

    raw_dir = Path(args.raw_dir)
    out_dir = Path(args.out_dir)

    class_dirs = sorted(d for d in raw_dir.iterdir() if d.is_dir())
    if not class_dirs:
        raise SystemExit(f"Nenhuma subpasta de classe encontrada em {raw_dir}")

    valid_ext = {".jpg", ".jpeg", ".png"}
    class_files = {}
    for class_dir in class_dirs:
        files = [f for f in class_dir.iterdir() if f.suffix.lower() in valid_ext]
        class_files[class_dir.name] = files
        print(f"Classe '{class_dir.name}': {len(files)} imagens encontradas")

    if args.balance:
        min_count = min(len(f) for f in class_files.values())
        print(f"\nBalanceando todas as classes para {min_count} imagens (tamanho da menor classe)")
        for cls in class_files:
            random.Random(args.seed).shuffle(class_files[cls])
            class_files[cls] = class_files[cls][:min_count]

    print()
    for cls, files in class_files.items():
        train_files, val_files, test_files = split_class_files(files, args.train, args.val, args.seed)
        for split_name, split_files in [("train", train_files), ("val", val_files), ("test", test_files)]:
            split_dir = out_dir / split_name / cls
            split_dir.mkdir(parents=True, exist_ok=True)
            for f in split_files:
                shutil.copy2(f, split_dir / f.name)
        print(f"Classe '{cls}': {len(train_files)} treino / {len(val_files)} val / {len(test_files)} teste")

    print(f"\nDataset organizado em: {out_dir.resolve()}")


if __name__ == "__main__":
    main()
