"""
rename_images.py

Renomeia em lote as imagens dentro de cada subpasta de classe, no padrao:
    <nome_da_pasta>_001.jpg, <nome_da_pasta>_002.jpg, ...

Exemplo de estrutura esperada (--raw_dir):
    raw_images/
        base/
        camada_verde/
        camada_amarela/
        camada_azul/
        camada_vermelha/

Depois de rodar:
    raw_images/base/base_001.jpg, base_002.jpg, ...
    raw_images/camada_verde/camada_verde_001.jpg, camada_verde_002.jpg, ...

Uso:
    python rename_images.py --raw_dir ./raw_images
    python rename_images.py --raw_dir ./raw_images --dry_run   (só mostra o que faria, sem alterar nada)
"""
import argparse
from pathlib import Path

VALID_EXT = {".jpg", ".jpeg", ".png"}


def rename_class_folder(folder: Path, dry_run: bool):
    files = sorted(f for f in folder.iterdir() if f.suffix.lower() in VALID_EXT)
    if not files:
        print(f"  (nenhuma imagem encontrada em {folder.name}, pulando)")
        return

    # Passo 1: renomeia tudo para um nome temporário, para evitar conflito
    # caso algum arquivo já tenha um nome final no meio do caminho (ex.: já
    # existe "camada_verde_003.jpg" antes de chegarmos nele na ordenação).
    temp_names = []
    for i, f in enumerate(files):
        temp_path = folder / f"__tmp_{i}{f.suffix.lower()}"
        if not dry_run:
            f.rename(temp_path)
        temp_names.append(temp_path if not dry_run else f)

    # Passo 2: renomeia do temporário para o nome final sequencial
    for i, temp_path in enumerate(temp_names, start=1):
        final_name = f"{folder.name}_{i:03d}{temp_path.suffix.lower()}"
        final_path = folder / final_name
        if dry_run:
            print(f"  {temp_path.name}  ->  {final_name}")
        else:
            temp_path.rename(final_path)

    print(f"  {len(files)} imagens renomeadas em '{folder.name}'")


def main():
    parser = argparse.ArgumentParser(description="Renomeia imagens em lote por pasta de classe")
    parser.add_argument("--raw_dir", required=True, help="Pasta com subpastas por classe")
    parser.add_argument("--dry_run", action="store_true", help="Só mostra o que seria feito, sem renomear de fato")
    args = parser.parse_args()

    raw_dir = Path(args.raw_dir)
    class_dirs = sorted(d for d in raw_dir.iterdir() if d.is_dir())
    if not class_dirs:
        raise SystemExit(f"Nenhuma subpasta de classe encontrada em {raw_dir}")

    for class_dir in class_dirs:
        print(f"Pasta '{class_dir.name}':")
        rename_class_folder(class_dir, args.dry_run)

    if args.dry_run:
        print("\n(dry-run: nada foi alterado de fato — rode sem --dry_run para aplicar)")
    else:
        print("\nRenomeação concluída.")


if __name__ == "__main__":
    main()
