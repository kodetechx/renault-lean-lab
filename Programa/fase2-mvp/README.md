# Fase 2 — Detecção de objetos com YOLO

Evolução da Fase 1 (classificação com MobileNetV2, um rótulo por frame) para **detecção de objetos** com YOLO (Ultralytics): o modelo localiza várias peças no mesmo frame, e o tracking nativo identifica quando uma peça nova entra na cena. Isso elimina a classe artificial "vazio" da Fase 1 — cena sem detecção já significa vazio.

Contexto, decisões técnicas e pendências: [`Documentos/fase-2-plano.md`](../../Documentos/fase-2-plano.md).

## Classes

Ordem fixa (vira o ID usado no treino), definida em `MASTER_CLASSES` no `build_yolo_dataset.py`:

| ID | Classe |
|----|--------|
| 0 | `camada_base` |
| 1 | `camada_verde` |
| 2 | `camada_amarela` |
| 3 | `camada_azul` |
| 4 | `camada_vermelha` |
| 5 | `parafuso` |

## Estrutura

```
fase2-mvp/
├── build_yolo_dataset.py     # junta os exports do CVAT em um dataset único
├── train_yolo.py             # treina e avalia o modelo
├── infer_webcam_yolo.py      # inferência ao vivo pela webcam
├── requirements.txt
├── backend/                  # API FastAPI + banco SQLite (recebe os eventos)
├── dashboard/                # dashboard Streamlit (consome a API)
├── dataset_yolo/
│   ├── data.yaml             # versionado
│   ├── labels/{train,val}/   # versionado (anotações)
│   └── images/{train,val}/   # NÃO versionado (~6 GB, gerado pelo script)
├── runs_yolo/lean_lab_v1/    # resultados do treino (só o best.pt fica versionado)
├── cvat_exports/             # NÃO versionado (~6 GB, zips do CVAT)
└── raw_images/               # NÃO versionado (~3,9 GB, fotos originais)
```

O que não é versionado (`.gitignore`) precisa existir localmente para refazer o dataset — veja "Dados que não estão no repositório".

## 1. Instalar dependências

```bash
python -m venv venv
venv\Scripts\activate          # Linux/macOS: source venv/bin/activate
pip install -r requirements.txt
```

## 2. Montar o dataset

Anote as imagens no CVAT (uma tarefa por camada) e exporte cada uma no formato **YOLO 1.1**, salvando os `.zip` em `cvat_exports/`. Depois:

```bash
python build_yolo_dataset.py --zips_dir ./cvat_exports \
    --images_dir ./raw_images --out_dir ./dataset_yolo --val_ratio 0.2
```

O script **não** simplesmente descompacta tudo junto: em cada zip, o número da classe é a posição dela no `obj.names` *daquele* zip, e ele pode diferir entre exports. O script remapeia pelo **nome** da classe para os IDs globais de `MASTER_CLASSES`, evitando rótulos trocados sem erro aparente.

No final ele imprime um relatório. Vale ler os avisos antes de treinar:
- nomes de classe nos zips que não batem com `MASTER_CLASSES` (geralmente erro de digitação no CVAT);
- anotações sem imagem correspondente em `--images_dir`;
- imagens que ficaram sem anotação válida.

A divisão treino/validação é aleatória por imagem (`--seed 42` por padrão).

> `data.yaml` grava o caminho **absoluto** do dataset na máquina onde foi gerado. Ao clonar o repositório em outro computador, edite a linha `path:` ou rode o script de novo.

## 3. Treinar

```bash
python train_yolo.py --data ./dataset_yolo/data.yaml --epochs 50
```

Opções úteis: `--model` (padrão `yolo11n.pt`, a variante nano, leve o bastante para CPU), `--imgsz 640`, `--batch 8` (reduza para 4 se faltar memória), `--name` (nome do experimento). Na primeira execução o Ultralytics baixa o `yolo11n.pt`, então é preciso ter internet.

Ao final o script avalia no conjunto de validação (mAP50, mAP50-95 geral e por classe) e indica o caminho do `best.pt`.

### Resultado do treino `lean_lab_v1`

50 épocas, `yolo11n.pt`, `imgsz=640`, `batch=8`, 1001 imagens (801 treino / 200 validação). Última época:

| Métrica | Valor |
|---------|-------|
| Precisão | 0,998 |
| Recall | 1,000 |
| mAP50 | 0,995 |
| mAP50-95 | 0,962 |

Curvas, matriz de confusão e amostras de validação estão em `runs_yolo/lean_lab_v1/`.

**Leia estes números com cautela:**
- Instâncias anotadas por classe: `camada_base` 180, `camada_verde` 202, `camada_amarela` 206, `camada_azul` 209, `camada_vermelha` 202 e **`parafuso` apenas 2**. Portanto a detecção de parafuso **não tem base estatística** ainda; o resultado geral só reflete as camadas.
- Métricas quase perfeitas em validação podem estar otimistas: o split é aleatório por imagem, então frames muito parecidos (mesma peça, mesma sessão) podem cair em treino e validação ao mesmo tempo. O teste real é a webcam, em condições de uso.

## 4. Rodar o backend (API + banco de dados)

Em um terminal separado, a partir da pasta `backend/` (o `eventos.db` é criado ali, na primeira execução):

```bash
cd backend
python -m venv venv
venv\Scripts\activate          # Linux/macOS: source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Documentação interativa (Swagger): `http://localhost:8000/docs`.

| Endpoint | O que faz |
|----------|-----------|
| `GET /health` | verifica se a API está no ar |
| `POST /eventos` | registra um evento (uma peça nova detectada) |
| `GET /eventos` | lista eventos; filtros `estacao`, `status` e `limit` (padrão 200, máx. 5000) |
| `GET /estatisticas` | agregado por estação: peças, OK, alertas por tipo, taxa de alerta, tempo médio de ciclo e média de parafusos detectados |

Corpo do `POST /eventos`:

```json
{
  "estacao": "camada_verde",
  "classe_detectada": "camada_verde",
  "status": "ALERTA_PARAFUSOS_INSUFICIENTES",
  "tempo_ciclo_s": 6.0,
  "parafusos_detectados": 1,
  "parafusos_esperados": 4
}
```

`parafusos_detectados` e `parafusos_esperados` são opcionais (não podem ser negativos): o `infer_webcam.py` da Fase 1 continua enviando eventos sem eles e a API aceita. Qualquer `status` diferente de `OK` conta como alerta nas estatísticas.

Este backend é independente do da Fase 1 (banco próprio) e usa a mesma porta 8000 por padrão — rode um de cada vez, ou troque a porta com `--port` e ajuste a URL nos demais componentes. Para usar outro banco (ex.: PostgreSQL), defina a variável de ambiente `DATABASE_URL`.

## 5. Rodar o dashboard

Em outro terminal, com o backend já no ar:

```bash
cd dashboard
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

Abre em `http://localhost:8501`, já apontando para `http://localhost:8000` (dá para trocar a "URL da API" na barra lateral). Mostra: peças processadas, alertas, taxa de alerta e tempo médio de ciclo (gerais e por estação), gráfico de alertas por tipo (camada incorreta × parafusos insuficientes) e a lista dos últimos eventos com parafusos detectados × esperados. Atualiza sozinho a cada 10 s (desmarque na barra lateral para congelar a tela). Um aviso fixo lembra que a contagem de parafusos ainda é preliminar.

## 6. Inferência ao vivo

```bash
python infer_webcam_yolo.py --model ./runs_yolo/lean_lab_v1/weights/best.pt --estacao camada_verde --parafusos_esperados 4 --api_url http://localhost:8000
```

Pressione `q` para sair. Argumentos: `--camera` (índice da webcam, padrão 0), `--backup_file` (padrão `eventos_backup_yolo.csv`).

Como funciona:
- `model.track` mantém um ID por peça entre frames; cada ID é contabilizado **uma vez** por sessão.
- Para cada peça nova, conta os parafusos cujo centro está dentro da caixa da peça.
- Status do evento:
  - `OK` — camada correta e parafusos ≥ `--parafusos_esperados`;
  - `ALERTA_CAMADA_INCORRETA` — camada detectada diferente da estação;
  - `ALERTA_PARAFUSOS_INSUFICIENTES` — camada correta, mas faltam parafusos.
- Confiança mínima: `CONFIDENCE_THRESHOLD = 0.5` (no topo do script).

O evento é enviado para `POST /eventos` do backend desta pasta (seção 4), incluindo `parafusos_detectados` e `parafusos_esperados`. Se a API estiver inacessível, cai no CSV de backup local (`eventos_backup_yolo.csv`, que guarda só `parafusos_detectados`); esse CSV não é reenviado automaticamente.

Pendências que afetam o uso:
- A contagem de parafusos é **preliminar** (2 exemplos de treino). É preciso uma sessão de captura dedicada e retreino antes de confiar nela.
- `--parafusos_esperados` tem padrão 4, mas a quantidade real por estação ainda precisa ser confirmada com a Renault (`fase-2-plano.md`, seção 4).

## Dados que não estão no repositório

Por serem pesados e regeneráveis, ficam só na máquina local (ignorados no `.gitignore`): `cvat_exports/`, `raw_images/`, `dataset_yolo/images/`, `venv/`, `yolo11n.pt` e `last.pt`. Se precisar compartilhá-los ou fazer backup, considere Git LFS ou um drive — o repositório já passou de vários GB no histórico.
