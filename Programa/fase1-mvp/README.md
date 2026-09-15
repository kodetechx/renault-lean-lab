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

## 4. Rodar o backend (API + banco de dados)

Em um terminal separado:

```bash
cd backend
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Isso cria automaticamente o arquivo `eventos.db` (SQLite) na primeira execução. Para conferir se está no ar, abra `http://localhost:8000/docs` — a documentação interativa da API (Swagger).

## 5. Rodar o dashboard

Em outro terminal (com o backend já rodando):

```bash
cd dashboard
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

Isso abre o dashboard no navegador (geralmente `http://localhost:8501`), já configurado para consultar `http://localhost:8000` por padrão. Se o backend estiver em outro endereço (ex.: outro computador na mesma rede do hotspot), é só trocar a "URL da API" na barra lateral.

## 6. Rodar a inferência ao vivo (webcam), agora conectada à API

```bash
python infer_webcam.py --model modelo_camada.keras --class_names class_names.json \
    --estacao camada_verde --api_url http://localhost:8000
```

- Troque `--estacao` pela classe esperada da estação que está simulando (`base`, `camada_verde`, `camada_amarela`, `camada_azul` ou `camada_vermelha`).
- Cada evento confirmado (OK ou alerta) é enviado automaticamente para a API e aparece no dashboard.
- Se a API estiver temporariamente fora do ar (ex.: instabilidade do hotspot), o evento não se perde: cai em `eventos_backup.csv`, que pode ser conferido/reenviado depois.
- Pressione `q` para encerrar.

## 7. Rodando tudo junto (resumo)

1. Terminal 1: `uvicorn main:app --reload` (dentro de `backend/`)
2. Terminal 2: `streamlit run app.py` (dentro de `dashboard/`)
3. Terminal 3: `python infer_webcam.py ...` (na raiz do projeto)
4. Acompanhar os números aparecendo ao vivo no dashboard conforme a webcam detecta as peças.