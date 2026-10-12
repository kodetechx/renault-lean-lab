# Fase 2 — Detecção de objetos com YOLO

Evolução da Fase 1 (classificação com MobileNetV2, um rótulo por frame) para **detecção de objetos** com YOLO (Ultralytics): o modelo localiza várias peças no mesmo frame, conta parafusos e peças de encaixe dentro de cada peça, e o tracking nativo identifica quando uma peça nova entra na cena. Isso elimina a classe artificial "vazio" da Fase 1 — cena sem detecção já significa vazio.

Contexto, decisões técnicas e pendências: [`Documentos/fase-2-plano.md`](../../Documentos/fase-2-plano.md).

## Classes

Ordem fixa (vira o ID usado no treino), definida em `MASTER_CLASSES` no `build_yolo_dataset.py`. As 6 primeiras vieram do primeiro treino (lote 1); as 4 últimas (peças de encaixe) foram acrescentadas no lote 2 — a ordem das 6 primeiras não deve mudar, só é permitido acrescentar classes no final.

| ID | Classe |
|----|--------|
| 0 | `camada_base` |
| 1 | `camada_verde` |
| 2 | `camada_amarela` |
| 3 | `camada_azul` |
| 4 | `camada_vermelha` |
| 5 | `parafuso` |
| 6 | `encaixe_circular` |
| 7 | `encaixe_retangular` |
| 8 | `encaixe_hexagono` |
| 9 | `encaixe_capsula` |

## Estrutura

```
fase2-mvp/
├── iniciar.ps1                # sobe backend + dashboard + câmera de uma vez (seção 4)
├── parar.ps1                  # encerra backend + dashboard
├── build_yolo_dataset.py     # junta os exports do CVAT (lote 1 + lote 2 + futuros) em um dataset único
├── train_yolo.py             # treina e avalia o modelo
├── infer_webcam_yolo.py      # inferência ao vivo pela webcam
├── requirements.txt
├── backend/                  # API FastAPI + banco SQLite (recebe os eventos)
├── dashboard/                # dashboard Streamlit (consome a API)
├── dataset_yolo_v2/          # dataset atual (lote 1 + lote 2, 10 classes)
│   ├── data.yaml             # versionado
│   ├── labels/{train,val}/   # versionado (anotações)
│   └── images/{train,val}/   # NÃO versionado (~6 GB, gerado pelo script)
├── runs_yolo/
│   ├── lean_lab_v1/            # 1º treino (lote 1, 6 classes)
│   └── lean_lab_v2/            # retreino (lote 1+2, 10 classes) — toda a pasta é versionada, exceto o last.pt
├── cvat_exports/             # NÃO versionado (~6 GB, zips do CVAT, lote 1 + lote 2)
└── raw_images/               # NÃO versionado (~3,9 GB, fotos originais)
```

O que não é versionado (`.gitignore`) precisa existir localmente para refazer o dataset — veja "Dados que não estão no repositório". Datasets futuros (`dataset_yolo_v3`, etc.) já caem automaticamente na mesma regra do `.gitignore` (`images/` ignorado, `labels/`+`data.yaml` versionados).

## 0. GPU (se tiver uma disponível)

O pacote `torch` do PyPI vem **CPU-only por padrão** no Windows — `pip install -r requirements.txt` sozinho não habilita a GPU, mesmo com uma NVIDIA disponível. Confira:

```bash
python -c "import torch; print(torch.cuda.is_available())"
```

Se vier `False` e você tem uma GPU NVIDIA, veja a versão de CUDA que o driver suporta (`nvidia-smi`, campo "CUDA Version") e reinstale o `torch` a partir do índice da PyTorch com a tag `cuXXX` correspondente, por exemplo (CUDA 12.9):

```bash
pip install --index-url https://download.pytorch.org/whl/cu129 torch torchvision
```

Sem isso, o treino roda inteiro na CPU — em `--imgsz 960` isso pode ser lento ao ponto de nunca terminar uma época numa máquina com pouca RAM (ver seção 3 e `fase-2-plano.md`, seção 3.5, para um caso real disso).

## 1. Instalar dependências

```bash
python -m venv venv
venv\Scripts\activate          # Linux/macOS: source venv/bin/activate
pip install -r requirements.txt
```

## 2. Montar o dataset

Anote as imagens no CVAT e exporte cada tarefa/lote como `.zip`, salvando todos em `cvat_exports/` (pode juntar lotes de datas diferentes na mesma pasta). Dois formatos de export são aceitos, inclusive misturados:

- **"YOLO 1.1"** — só retângulos (usado no lote 1, as fotos de camada por cor).
- **"CVAT for images 1.1"** (marcando **Save images**) — guarda retângulo, polígono e elipse; cada forma vira a caixa que a envolve (usado no lote 2, parafuso/encaixe/múltiplas peças).

```bash
python build_yolo_dataset.py --zips_dir ./cvat_exports \
    --images_dir ./raw_images --out_dir ./dataset_yolo_v2 --val_ratio 0.2
```

`--out_dir` precisa ser uma pasta nova (o script recusa gravar dentro de `--zips_dir`/`--images_dir` ou numa pasta não vazia) — use um nome novo (`_v3`, `_v4`...) a cada dataset ampliado, para não perder a versão anterior nem confundir qual `best.pt` foi treinado com qual dataset.

O script **não** simplesmente descompacta tudo junto: em cada zip, o número da classe é a posição dela no `obj.names` (ou `data.yaml`) *daquele* zip, e ele pode diferir entre exports. O script remapeia pelo **nome** da classe para os IDs globais de `MASTER_CLASSES`.

Outros cuidados que ele já resolve sozinho:
- **Imagem repetida entre lotes** (ex.: a mesma foto de camada do lote 1 foi reanotada no lote 2 com parafuso): mantém só a versão com mais anotações, comparando pelo conteúdo do arquivo — evita a mesma foto cair em treino e validação ao mesmo tempo.
- **Split estratificado:** garante exemplos de toda classe na validação (no primeiro treino, `parafuso` ficou com zero exemplos na validação e o mAP dessa classe não significava nada — ver `fase-2-plano.md`, seção 3.1).
- **Polígono/elipse → caixa:** convertido automaticamente; formas que não têm como virar caixa (`points`, máscara, tag) são ignoradas e contadas no relatório.

No final ele imprime um relatório por classe (treino/validação, com aviso de "sem exemplos" ou "poucos exemplos") e por zip. Vale ler os avisos antes de treinar:
- nomes de classe nos zips que não batem com `MASTER_CLASSES` (geralmente erro de digitação no CVAT);
- anotações sem imagem correspondente em `--images_dir`;
- imagens sem nenhuma anotação válida.

> `data.yaml` grava o caminho **absoluto** do dataset na máquina onde foi gerado. Ao clonar o repositório em outro computador, edite a linha `path:` ou rode o script de novo.

## 3. Treinar

```bash
python train_yolo.py --data ./dataset_yolo_v2/data.yaml --epochs 50
```

Opções:
- `--model` — `yolo11n.pt` (padrão, nano) para começar do zero, ou o `best.pt` de um treino anterior para continuar dele (fine-tuning). Ao mudar de dataset com mais classes (ex.: lote 1 → lote 1+2), o Ultralytics reaproveita o que já foi aprendido e só reinicializa a camada de saída — aparece no log como `Transferred N/M items from pretrained weights`.
- `--imgsz` (padrão 640) — parafuso e peças de encaixe são pequenos na cena; 960 ajuda a detectá-los melhor, mas é mais lento e pesa mais na memória.
- `--batch` (padrão 8) — um número fixo, ou **`-1` (AutoBatch)** para o Ultralytics medir a VRAM livre e escolher o maior batch que cabe em ~60% dela. Recomendado em GPU com pouca VRAM: medido na prática, uma RTX 2050 (4GB) só cabe `batch=2` em `--imgsz 960`.
- `--device` (padrão `''`, auto) — usa GPU automaticamente se o `torch` tiver CUDA (seção 0); force com `0` (1ª GPU) ou `cpu`.
- `--workers` (padrão 4) — processos paralelos carregando imagens. O padrão do Ultralytics é 8; reduzido aqui porque notebooks com pouca RAM (ex.: 8GB) podem ficar sem memória antes da 1ª época com 8 workers em `--imgsz 960` — foi exatamente o que aconteceu num treino real deste projeto (processo morto sem gerar `results.csv`; diagnóstico completo em `fase-2-plano.md`, seção 3.5).
- `--name` — nome do experimento (pasta em `--project`, padrão `runs_yolo`).

Exemplo de retreino (fine-tuning) em notebook com GPU de 4GB e 8GB de RAM:

```bash
python train_yolo.py --data ./dataset_yolo_v2/data.yaml \
    --model ./runs_yolo/lean_lab_v1/weights/best.pt \
    --name lean_lab_v2 --epochs 60 --imgsz 960 --batch -1 --workers 4
```

Ao final o script avalia no conjunto de validação e imprime o mAP50/mAP50-95 geral e **por classe, junto com quantos exemplos de validação cada classe tem** — uma classe com 0 exemplos de validação não tem mAP que signifique nada (o Ultralytics preenche com o valor geral), e o script marca isso como "IGNORE".

### Resultado do treino `lean_lab_v1` (lote 1, 6 classes)

50 épocas, `yolo11n.pt`, `imgsz=640`, `batch=8`, 1001 imagens (801 treino / 200 validação). Última época:

| Métrica | Valor |
|---------|-------|
| Precisão | 0,998 |
| Recall | 1,000 |
| mAP50 | 0,995 |
| mAP50-95 | 0,962 |

Curvas, matriz de confusão e amostras de validação estão em `runs_yolo/lean_lab_v1/`.

**Leia estes números com cautela:**
- Instâncias anotadas por classe: `camada_base` 180, `camada_verde` 202, `camada_amarela` 206, `camada_azul` 209, `camada_vermelha` 202 e **`parafuso` apenas 2**. A detecção de parafuso **não tinha base estatística** nesse treino — resolvido no lote 2 (642 instâncias de parafuso no dataset atual).
- Métricas quase perfeitas em validação podem estar otimistas: o split do lote 1 era aleatório por imagem, então frames muito parecidos (mesma peça, mesma sessão) podiam cair em treino e validação ao mesmo tempo. O teste real é a webcam, em condições de uso.

### Retreino `lean_lab_v2` (lote 1 + lote 2, 10 classes)

Dataset `dataset_yolo_v2`: 1.122 imagens (888 treino / 234 validação), todas as 10 classes com exemplos de validação. 60 épocas, GPU, `--imgsz 960 --batch -1 --workers 4`, ~85 minutos.

| Métrica geral | Valor |
|---|---|
| Precisão | 0,946 |
| Recall | 0,907 |
| mAP50 | 0,962 |
| mAP50-95 | 0,858 |

mAP50-95 por classe: camadas entre 0,94-0,98 (consistente com o treino anterior); `parafuso` 0,689 (642 instâncias no dataset, primeira medida real — no treino anterior não tinha nenhum exemplo de validação); encaixes entre 0,69-0,86, com `encaixe_hexagono` e `encaixe_capsula` mais fracos (classes com menos exemplos de treino). Detalhe completo, por classe com contagem de validação, e leitura dos resultados em `fase-2-plano.md`, seção 3.4. Diagnóstico de por que a primeira tentativa de treino morreu sem gerar resultado, e a correção aplicada, na seção 3.5.

## 4. Rodar tudo de uma vez (`iniciar.ps1`)

Depois de instalado (seção 1) e com um modelo treinado (seção 3), o dia a dia — subir backend, dashboard e a câmera juntos — pode ser feito com um comando:

```powershell
.\iniciar.ps1 -Estacao camada_verde
```

Abre o backend e o dashboard cada um na sua própria janela, espera a API responder antes de continuar, e roda a câmera nesta janela (pressione `q` para sair dela). Sem `-Model`, usa automaticamente o `best.pt` mais recente em `runs_yolo\*\weights\`.

```powershell
.\iniciar.ps1 -Estacao camada_amarela -IgnorarClasses "encaixe_hexagono,encaixe_capsula"   # repassa --ignorar_classes
.\iniciar.ps1 -PularCamera                                                                  # só backend + dashboard
.\iniciar.ps1 -Estacao camada_azul -PularBackend                                             # backend já estava rodando em outra janela
```

Backend e dashboard continuam rodando nas janelas deles mesmo depois que a câmera for fechada. Para derrubar os dois:

```powershell
.\parar.ps1
```

`parar.ps1` encontra e encerra o que estiver nas portas 8000 (backend) e 8501 (dashboard) — incluindo os processos filhos do `uvicorn --reload` (no Windows ele sobe um supervisor + um worker; matar só um dos dois faz o backend "voltar sozinho"). A janela da câmera não é tocada por ele; feche-a com `q`.

**Isto é só um atalho** — empacota exatamente os comandos das seções 5, 6 e 7 abaixo, nada mais. Para depurar uma parte isolada (ex.: testar só o backend com `curl`, sem dashboard nem câmera), continue usando os comandos manuais dessas seções.

Os dois scripts usam o venv único desta pasta (`venv\Scripts\python.exe`, o mesmo das seções 1-3). Se você optou por venvs separados em `backend\` e `dashboard\` (como as seções 5 e 6 também documentam), use `-PythonBackend`/`-PythonDashboard` para apontar para eles — veja `Get-Help .\iniciar.ps1 -Full` para todos os parâmetros.

## 5. Rodar o backend (API + banco de dados)

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
| `GET /eventos` | lista eventos; filtros `estacao`, `status`, `modelo_versao` e `limit` (padrão 200, máx. 5000) |
| `GET /estatisticas` | agregado por estação: peças, OK, alertas por tipo (camada incorreta, parafusos insuficientes, encaixe incompleto), taxa de alerta, tempo médio de ciclo, média de parafusos detectados e horário do último evento; filtro opcional `modelo_versao` |
| `GET /versoes-modelo` | lista os valores distintos de `modelo_versao` já recebidos (usado para popular o filtro do dashboard) |

Corpo do `POST /eventos`:

```json
{
  "estacao": "camada_amarela",
  "classe_detectada": "camada_amarela",
  "status": "ALERTA_ENCAIXE_INCOMPLETO",
  "tempo_ciclo_s": 6.0,
  "parafusos_detectados": 4,
  "parafusos_esperados": 4,
  "encaixes_detectados": "encaixe_circular,encaixe_retangular",
  "encaixes_esperados": "encaixe_circular,encaixe_retangular,encaixe_hexagono,encaixe_capsula",
  "modelo_versao": "lean_lab_v2"
}
```

Todos os campos a partir de `parafusos_detectados` são opcionais (os dois `parafusos_*` não podem ser negativos): o `infer_webcam.py` da Fase 1 continua enviando eventos sem eles e a API aceita. `encaixes_detectados`/`encaixes_esperados` são uma string com os nomes separados por vírgula (`""` se a estação não exige nenhum). Qualquer `status` diferente de `OK` conta como alerta nas estatísticas, incluindo `ALERTA_ENCAIXE_INCOMPLETO`.

`modelo_versao` identifica qual treino gerou o modelo usado (ex.: `lean_lab_v2`) — o `infer_webcam_yolo.py` deduz isso automaticamente do caminho de `--model`. Serve para o dashboard não misturar nas mesmas estatísticas eventos de versões de modelo diferentes (ex.: comparar v1 e v2 lado a lado em vez de uma média sem sentido entre os dois).

> Se o `backend/eventos.db` já existir de uma versão anterior deste `models.py` (sem essas colunas), o backend adiciona as colunas que faltarem sozinho ao iniciar (`ensure_sqlite_columns` em `database.py`), sem apagar os eventos já gravados. Isso só vale para SQLite; um banco real (Postgres) precisaria de uma ferramenta de migração própria (ex.: Alembic).

Este backend é independente do da Fase 1 (banco próprio) e usa a mesma porta 8000 por padrão — rode um de cada vez, ou troque a porta com `--port` e ajuste a URL nos demais componentes. Para usar outro banco (ex.: PostgreSQL), defina a variável de ambiente `DATABASE_URL`.

## 6. Rodar o dashboard

Em outro terminal, com o backend já no ar:

```bash
cd dashboard
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

Abre em `http://localhost:8501`, já apontando para `http://localhost:8000` (dá para trocar a "URL da API" na barra lateral). Atualiza sozinho a cada 10 s (desmarque na barra lateral para congelar a tela).

**Filtros (barra lateral):** versão do modelo (afeta o dashboard inteiro — cartões, tabela por estação e gráficos), e estação/status/nº de eventos a carregar (afetam a tabela de eventos e o gráfico de tendência).

**O que mostra:**
- Cartões gerais: peças processadas, alertas, taxa de alerta e tempo médio de ciclo.
- **Aviso de estação parada:** compara o horário do último evento de cada estação conhecida (`camada_base/verde/amarela/azul/vermelha`) com "agora"; sinaliza quem está sem evento há mais que o limite configurado na barra lateral (padrão 15 min) e quem nunca recebeu nenhum evento — útil para notar câmera travada ou estação ociosa sem precisar ficar olhando a tabela.
- Tabela por estação: peças, OK, alertas por tipo (camada incorreta, parafusos insuficientes, encaixe incompleto), taxa de alerta, tempo médio de ciclo, média de parafusos detectados e horário do último evento (convertido para horário de Brasília).
- Dois gráficos de barra: peças por estação, e alertas por tipo e estação (as três categorias).
- **Tendência de eventos ao longo do tempo:** gráfico de barras empilhadas por status, agrupado no intervalo escolhido (1min/5min/15min/1h) — mostra se a taxa de alerta piora ao longo de uma sessão/turno, não só o total acumulado.
- Tabela dos últimos eventos (respeitando os filtros), com parafusos e encaixes detectados × esperados, e botão para baixar essa tabela em CSV.

Um aviso fixo lembra que a contagem de parafuso/encaixe depende do retreino e das condições de captura (ver seção 7).

## 7. Inferência ao vivo

```bash
python infer_webcam_yolo.py --model ./runs_yolo/lean_lab_v2/weights/best.pt --estacao camada_amarela --api_url http://localhost:8000
```

Pressione `q` para sair. Argumentos: `--camera` (índice da webcam, padrão 0), `--cam_width`/`--cam_height` (resolução pedida à webcam, padrão 1280×720 — ver aviso abaixo), `--backup_file` (padrão `eventos_backup_yolo.csv`), `--modelo_versao` (ver seção 5 — por padrão, deduzido do caminho de `--model`), `--ignorar_classes` (ver abaixo).

> **Importante:** as fotos de treino são de celular (~12 megapixels). A maioria das webcams usa 640×480 (0,3 megapixel) por padrão se a resolução não for pedida explicitamente — nessa resolução, a camada ainda é detectada (objeto grande), mas parafuso e peças de encaixe (pequenos) ficam com poucos pixels reais e deixam de ser detectados, mesmo com a peça completa e visível. `--cam_width`/`--cam_height` já pedem 1280×720 por padrão (o script imprime a resolução obtida ao iniciar, para confirmar); mesmo assim é bem menos que as fotos de treino — se a detecção de parafuso/encaixe continuar fraca, aproxime a peça da câmera. Diagnóstico completo em `fase-2-plano.md`, seção 3.6.

Como funciona:
- `model.track` mantém um ID por peça entre frames; cada ID é contabilizado **uma vez** por sessão.
- Para cada peça nova, conta parafusos e peças de encaixe cujo **centro** cai dentro da caixa da peça — um parafuso solto na mesa, fora da peça, não entra na contagem.
- A receita de completude (quantos parafusos, quais peças de encaixe) é **por estação**, confirmada com a Renault (`fase-2-plano.md`, seção 4) e definida em `ESTACAO_RECEITA` no topo do script — não é mais um número fixo via flag:

  | Estação (`--estacao`) | Parafusos | Peças de encaixe |
  |---|---|---|
  | `camada_base` | 0 | nenhuma |
  | `camada_verde` | 4 | nenhuma |
  | `camada_amarela` | 4 | as 4 (circular, retangular, hexágono, cápsula) |
  | `camada_azul` | 4 | nenhuma |
  | `camada_vermelha` | 4 | as 4 (mesmas da amarela) |

- Status do evento:
  - `OK` — camada correta, parafusos suficientes e (se a estação exigir) as 4 peças de encaixe presentes;
  - `ALERTA_CAMADA_INCORRETA` — camada detectada diferente da estação;
  - `ALERTA_PARAFUSOS_INSUFICIENTES` — camada correta, mas faltam parafusos;
  - `ALERTA_ENCAIXE_INCOMPLETO` — camada e parafusos OK, mas falta alguma peça de encaixe exigida.
- `--ignorar_classes` desliga a detecção de uma ou mais classes em tempo de inferência (ex.: `--ignorar_classes encaixe_hexagono` se ela ainda não estiver confiável), sem precisar retreinar — usa o filtro `classes=` do Ultralytics, os pesos não mudam. Cuidado: se a classe ignorada for exigida pela receita da estação atual, o status fica sempre em alerta de incompleto para essa estação (o script avisa isso ao iniciar).
- Confiança mínima: `CONFIDENCE_THRESHOLD = 0.5` (no topo do script).

O evento é enviado para `POST /eventos` do backend desta pasta (seção 5), incluindo parafusos **e** encaixes (detectados e esperados) e a versão do modelo. Se a API estiver inacessível, cai no CSV de backup local (`eventos_backup_yolo.csv`, mesmas colunas do evento); esse CSV não é reenviado automaticamente. Se o arquivo já existir com um cabeçalho de uma versão anterior do script, ele é renomeado para `.bak` e um novo é criado — evita linhas com número de colunas diferente do cabeçalho.

Pendências que afetam o uso:
- Trate a contagem de parafuso/encaixe como **preliminar** até confirmar que o `--model` usado já é o retreinado com o lote 2 (ver seção 3) e validar ao vivo.
- A completude é avaliada no primeiro frame em que o `track_id` aparece — se a peça ainda estiver sendo montada nesse instante, pode sair um alerta de incompleto falso (limitação conhecida, registrada em `fase-2-plano.md`, seção 6).

## Dados que não estão no repositório

Por serem pesados e regeneráveis, ficam só na máquina local (ignorados no `.gitignore`): `cvat_exports/`, `raw_images/`, `dataset_yolo*/images/`, `venv/`, pesos `*.pt` exceto o `best.pt` de cada treino em `runs_yolo/`, e `runs/` (saída de validação duplicada). Se precisar compartilhá-los ou fazer backup, considere Git LFS ou um drive — o repositório já passou de vários GB no histórico.
