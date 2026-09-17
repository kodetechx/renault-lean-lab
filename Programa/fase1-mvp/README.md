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
    vazio/
```

- A pasta `vazio/` contém fotos da bancada **sem nenhuma peça** — é o que permite ao sistema distinguir "peça nova chegou" de "a mesma peça continua ali" na inferência ao vivo (ver seção 7). Se você ainda não tiver essas fotos, pode organizar/treinar só com as 5 classes de cor por enquanto, mas a contagem em `infer_webcam.py` funciona melhor com a classe `vazio` incluída.

Depois rode:

```bash
python organize_dataset.py --raw_dir ./raw_images --out_dir ./dataset --balance
```

- `--balance` é opcional: iguala todas as classes ao tamanho da menor (recomendado, já que as classes coletadas variaram bastante em quantidade).
- Isso vai gerar `dataset/train`, `dataset/val` e `dataset/test`, prontos para o próximo passo.
- Se você já tem um `dataset/` de uma organização anterior e adicionou fotos novas (incluindo a classe `vazio`), apague a pasta antiga antes de rodar de novo (`rm -rf dataset` / `Remove-Item -Recurse -Force dataset` no Windows), para o split ser refeito do zero com todas as classes.

## 3. Treinar o classificador

```bash
python train_classifier.py --dataset_dir ./dataset --epochs 15
```

Ao final, você terá:
- `modelo_camada.keras` — o modelo treinado.
- `class_names.json` — o mapeamento de índice → nome da classe.
- No console, um relatório de precisão/recall por classe e a matriz de confusão no conjunto de teste (esse relatório mostra se alguma classe está sendo confundida com outra).

Se o treino estiver rodando muito devagar em CPU, você pode reduzir `--img_size` para 160 ou diminuir `--epochs`.

> Dica: antes de treinar por cima de um modelo que já está funcionando, renomeie os arquivos atuais (ex.: `modelo_camada.keras` → `modelo_camada_v1.keras`, `class_names.json` → `class_names_v1.json`) para guardar a versão anterior e poder comparar os resultados depois.

## 4. Revisar imagens classificadas incorretamente

Depois do treino, é possível inspecionar exatamente **quais imagens do conjunto de teste** o modelo errou, sem precisar retreinar nada:

```bash
python find_misclassified.py --dataset_dir ./dataset --model modelo_camada.keras \
    --class_names class_names.json --copy_to ./erros_revisao
```

- O script imprime no console cada imagem errada, com a classe real, a classe prevista e o nível de confiança do erro.
- Com `--copy_to`, ele também copia as imagens erradas para a pasta informada (ex.: `erros_revisao/`), já renomeadas no padrão `real_<classe_real>__previsto_<classe_prevista>__<nome_original>.jpg` — assim dá para abrir a pasta e ver de cara o que era e o que o modelo achou que era, sem caçar arquivo por arquivo dentro de `dataset/test/`.
- Use isso para decidir se um erro é um caso genuinamente ambíguo (peça de lado, mão cobrindo parte dela) — não é motivo de preocupação — ou um sinal de que vale coletar mais exemplos parecidos, ou até corrigir uma foto que ficou na pasta de classe errada.

## 5. Rodar o backend (API + banco de dados)

Em um terminal separado:

```bash
cd backend
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Isso cria automaticamente o arquivo `eventos.db` (SQLite) na primeira execução. Para conferir se está no ar, abra `http://localhost:8000/docs` — a documentação interativa da API (Swagger).

## 6. Rodar o dashboard

Em outro terminal (com o backend já rodando):

```bash
cd dashboard
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

Isso abre o dashboard no navegador (geralmente `http://localhost:8501`), já configurado para consultar `http://localhost:8000` por padrão. Se o backend estiver em outro endereço (ex.: outro computador na mesma rede do hotspot), é só trocar a "URL da API" na barra lateral.

## 7. Rodar a inferência ao vivo (webcam), agora conectada à API

```bash
python infer_webcam.py --model modelo_camada.keras --class_names class_names.json \
    --estacao camada_verde --api_url http://localhost:8000
```

- Troque `--estacao` pela classe esperada da estação que está simulando (`base`, `camada_verde`, `camada_amarela`, `camada_azul` ou `camada_vermelha`).
- Cada evento confirmado (OK ou alerta) é enviado automaticamente para a API e aparece no dashboard.
- Se a API estiver temporariamente fora do ar (ex.: instabilidade do hotspot), o evento não se perde: cai em `eventos_backup.csv`, que pode ser conferido/reenviado depois.
- Se o modelo foi treinado com a classe `vazio`, a contagem usa uma máquina de estados (bancada vazia → peça chegou → peça presente) para não contar a mesma peça várias vezes enquanto ela continua parada em frente à câmera. Sem essa classe, o script ainda funciona, mas exibe um aviso no console e não tem essa proteção.
- Pressione `q` para encerrar.

## 8. Rodando tudo junto (resumo)

1. Terminal 1: `uvicorn main:app --reload` (dentro de `backend/`)
2. Terminal 2: `streamlit run app.py` (dentro de `dashboard/`)
3. Terminal 3: `python infer_webcam.py ...` (na raiz do projeto)
4. Acompanhar os números aparecendo ao vivo no dashboard conforme a webcam detecta as peças.