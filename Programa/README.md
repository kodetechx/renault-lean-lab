# Fase 1 — Scripts do MVP (classificação de camada)

## 1. Instalar dependências

Recomendado usar um ambiente virtual:

```bash
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## 2. Organizar as imagens coletadas

Antes de rodar, organize as fotos coletadas em uma pasta com uma subpasta por classe, por exemplo:

```
raw_images/
    base/
    camada_verde/
    camada_amarela/
    camada_azul/
    camada_vermelha/
```

Depois rode:

```bash
python organize_dataset.py --raw_dir ./raw_images --out_dir ./dataset --balance
```

- `--balance` é opcional: iguala todas as classes ao tamanho da menor (recomendado, já que as classes coletadas variaram de 281 a 468 imagens).
- Isso vai gerar `dataset/train`, `dataset/val` e `dataset/test`, prontos para o próximo passo.

## 3. Treinar o classificador

```bash
python train_classifier.py --dataset_dir ./dataset --epochs 15
```

Ao final, você terá:
- `modelo_camada.keras` — o modelo treinado.
- `class_names.json` — o mapeamento de índice → nome da classe.
- No console, um relatório de precisão/recall por classe e a matriz de confusão no conjunto de teste (esse relatório mostra se alguma classe está sendo confundida com outra).

Se o treino estiver rodando muito devagar em CPU, você pode reduzir `--img_size` para 160 ou diminuir `--epochs`.

## 4. Rodar a inferência ao vivo (webcam)

```bash
python infer_webcam.py --model modelo_camada.keras --class_names class_names.json --estacao camada_verde
```

- Troque `--estacao` pela classe esperada da estação que está simulando (`base`, `camada_verde`, `camada_amarela`, `camada_azul` ou `camada_vermelha`).
- Uma janela vai abrir mostrando a webcam com a predição em tempo real.
- Quando a camada detectada bater com a esperada, o evento é gravado como `OK` em `eventos.csv`.
- Quando não bater, aparece um alerta em vermelho na tela **e** o evento é gravado como `ALERTA_CAMADA_INCORRETA`.
- Pressione `q` para encerrar.

## 5. Onde ficam os dados por enquanto

Tudo é local: o modelo treinado, o `class_names.json` e o `eventos.csv` ficam na mesma pasta onde os scripts rodaram. Na Fase 1.2, a função `log_event()` dentro de `infer_webcam.py` será o único ponto a trocar para passar a enviar os eventos para a API do backend em vez do CSV.
