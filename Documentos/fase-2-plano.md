# Fase 2 — Detecção da Peça Completa e Contagem de Parafusos via YOLO
## Projeto: Digitalização do Lab de Lean Manufacturing — Renault x UniSenai

**Status:** 🟡 Retreino `lean_lab_v2` concluído em 11/10/2026 (60 épocas, GPU, ~85min) com as 10 classes — mAP50-95 geral 0,858 na validação (seção 3.4); no teste ao vivo, porém, parafuso/encaixe não apareciam demarcados — causa encontrada (webcam capturando em 640×480, muito abaixo da resolução das fotos de treino) e corrigida (seção 3.6); falta confirmar ao vivo se a correção foi suficiente
**Depende de:** `fase-1-plano.md` (MVP de classificação de camada, concluído) e `fase-0-validacao-e-escopo.md`
**Prioridade escolhida pelo grupo (set/2026):** detecção de objeto (YOLO) como substituto do MobileNetV2 para a verificação da camada + contagem de parafusos, entre as 4 frentes possíveis da Fase 2 (as outras — QR/RFID, replicação multi-estação — ficam para depois, ver seção 7; detecção de avaria foi removida do escopo do projeto, ver seção 7).

---

## 1. Objetivo da Fase 2 (esta frente)

Substituir a classificação de imagem inteira (MobileNetV2, Fase 1) por **detecção de objetos (YOLO)** para dois fins:

1. **Detectar a peça montada como um objeto** (uma caixa por peça, classificada pela cor da camada) — resolve uma limitação estrutural do MobileNetV2: ele só dá um rótulo por frame inteiro, então não lida bem com **mais de uma peça na bancada ao mesmo tempo** (cenário realista no dia a dia do operador).
2. **Detectar e contar parafusos e peças de encaixe** individualmente — permite comparar a quantidade encontrada com a esperada por estação.

A verificação de "montagem completa/correta" passa a ser uma **regra de negócio** (contagem de parafusos e peças de encaixe detectados vs. esperados por estação, ver seção 4), não uma classe visual única de "completo/incompleto" — evitando a necessidade de fotografar todos os estados possíveis de montagem incompleta.

---

## 2. Histórico da decisão (registrado em 18-20/09/2026, para a documentação acadêmica do projeto)

Este escopo passou por várias revisões na mesma conversa, vale documentar o raciocínio:

1. **Proposta inicial:** detectar cada componente individual (peças A/B/C/D de cada cor + parafusos) via YOLO, para verificação fina de montagem.
2. **Primeira revisão — descartar A/B/C/D:** o grupo observou que as peças A/B/C/D de uma mesma cor são visualmente muito parecidas, e que o encaixe mecânico entre elas é específico (uma peça errada fisicamente não encaixa no lugar de outra — um design do tipo *poka-yoke*). Duas consequências: (a) verificar componente por componente é redundante, já que o encaixe físico já impede montagem errada; (b) anotar caixas para peças visualmente quase idênticas é propenso a erro de rotulagem humana, o que geraria um dataset ruim independente do volume de fotos. **Esta decisão foi mantida e confirmada em 20/09/2026** — as peças A/B/C/D continuam fora de escopo.
3. **Segunda revisão — manter YOLO para a peça inteira (não voltar ao MobileNetV2):** o grupo identificou que, mesmo com a simplificação acima, a classificação de imagem inteira (MobileNetV2) tem uma fragilidade de longo prazo: se mais de uma peça estiver na bancada ao mesmo tempo, o modelo não consegue contar/localizar cada uma individualmente, porque só produz um rótulo por frame. Decisão: usar YOLO para detectar a **peça inteira montada** (uma caixa por peça, classificada pela cor), não para os componentes internos. Isso também resolve de forma nativa a checagem de presença (a classe `vazio` criada como solução de contorno na Fase 1 deixa de ser necessária). **Confirmado ao vivo em 20/09/2026** — o modelo já detecta corretamente múltiplas peças simultâneas em câmera (ver seção 3.2).
4. **Terceira revisão — peças de encaixe (amarela/vermelha) tratadas como classes próprias, distintas das A/B/C/D:** o alinhamento com a Renault (Passo 0, seção 4) revelou que as camadas amarela e vermelha usam 4 peças de encaixe de formatos diferentes entre si (circular, retangular, hexágono, cápsula/estádio) — ao contrário das A/B/C/D, que eram quase idênticas entre si. Como o argumento que descartou A/B/C/D (dificuldade de anotação por semelhança visual) não se aplica aqui, o grupo decidiu **detectar as 4 peças de encaixe como classes próprias do modelo YOLO** (ver seção 4.1).

**Resultado final do escopo:** um único modelo YOLO com classes de peça por cor + `parafuso` + as 4 classes de peça de encaixe, e a verificação de completude por estação feita em lógica de negócio (contagem esperada vs. detectada, tabela da seção 4).

---

## 3. Boa notícia: parte do dataset já existe e pode ser reaproveitada

As **1.783 imagens de camada coletadas na Fase 0** (306 base + 281 verde + 468 amarela + 384 azul + 344 vermelha) não precisam ser recapturadas. Elas foram tiradas para classificação (uma classe por pasta), mas servem perfeitamente como matéria-prima para detecção — só precisam ser **reanotadas no CVAT com uma bounding box ao redor da peça inteira**, atribuindo a classe de cor correspondente. Isso é uma anotação rápida (tipicamente 1 caixa por imagem), bem mais simples do que o cenário de componente-a-componente descartado na seção 2.

### O que faltava capturar (próxima sessão de terça) — situação em 11/10/2026

| Necessidade | Por quê | Situação |
|---|---|---|
| Fotos de parafusos isolados e já encaixados na peça | Só havia 2 parafusos anotados no lote 1 | Coberto pelo lote 2 (anotado e exportado em 11/10/2026): **642 instâncias** de parafuso no dataset unificado (512 treino + 130 validação) |
| Fotos das 4 peças de encaixe, isoladas e já encaixadas nas camadas amarela/vermelha | Decidido em 20/09/2026 (seção 4.1) | Coberto pelo lote 2 (fotos dentro e fora das peças de camada, em vários cenários): 81–90 instâncias de treino por classe de encaixe |
| Fotos com **mais de uma peça no quadro simultaneamente** | Reforço do cenário multi-objeto | Coberto pelo lote 2 (`lote2-multiplas-pecas-1/2/3.zip`, 121 fotos) |

**Fora de escopo, permanentemente:** fotos individuais das peças A/B/C/D por cor (ver seção 2, decisão 2). Não é mais necessário capturar nem anotar essas variações — o foco de captura passa a ser exclusivamente **parafuso** e **peças de encaixe**.

### 3.1 Resultado do primeiro treino de teste (lote 1, 20/09/2026)

Rodado com ~1.001 imagens já reanotadas (801 treino / 200 validação), modelo `yolo11n.pt`, via `train_yolo.py`:

| Classe | mAP50-95 |
|---|---|
| Geral (todas as classes) | **0,965** (mAP50 geral: 0,995) |
| camada_base | 0,984 |
| camada_verde | 0,93–0,98 (faixa observada entre as camadas) |
| camada_amarela | 0,93–0,98 |
| camada_azul | 0,931 |
| camada_vermelha | 0,93–0,98 |

**Leitura:** a detecção da peça inteira por cor já está excelente logo no primeiro treino — confirma que a decisão de migrar para YOLO (seção 2) foi acertada, e que o pipeline ponta a ponta (CVAT → `build_yolo_dataset.py` → `train_yolo.py` → avaliação) está validado e funcionando.

**Ressalva importante sobre `parafuso`:** o script imprimiu `parafuso: 0,965` na lista "mAP50-95 por classe", mas esse número **não mede nada**. Verificado em 11/10/2026 no código-fonte do Ultralytics: a propriedade `metrics.box.maps` começa com o **mAP50-95 geral repetido em todas as classes** e só sobrescreve as classes que têm pelo menos um exemplo na validação. Como `parafuso` não tinha nenhum exemplo no split de validação (apenas 2 instâncias existiam em todo o lote 1), ela ficou com o valor geral (0,965 — exatamente o mAP50-95 geral). Isso corrige a explicação anterior deste documento, que descrevia o fenômeno apenas como um "caso degenerado". A contagem de parafusos no `infer_webcam_yolo.py` só passa a ter validação real depois do retreino com o lote 2, e **a nova versão do `train_yolo.py` já imprime, ao lado do mAP de cada classe, quantos exemplos ela tem na validação, marcando "IGNORE" quando for zero.**

### 3.2 Teste de inferência ao vivo (webcam, 20/09/2026)

Rodado `infer_webcam_yolo.py` com o `best.pt` do lote 1. Resultado: **detecção de peça por cor funcionando corretamente ao vivo**, via webcam, confirmando que o modelo generaliza além do conjunto de validação (câmera/condições de luz diferentes das fotos de treino). Este é o primeiro teste end-to-end do pipeline completo da Fase 2 (captura → anotação → treino → inferência ao vivo → log de evento).

**Confirmado no mesmo dia:** o modelo já detecta corretamente **mais de uma peça simultaneamente em câmera** ao vivo, mesmo o dataset de treino tendo apenas 1 peça por imagem (ver seção 3.3) — resolvendo informalmente a dúvida que motivou tecnicamente a escolha do YOLO sobre o MobileNetV2 (seção 2, revisão 3).

### 3.3 Risco identificado (mitigado): generalização para múltiplas peças no quadro

Todas as 1.783 imagens de camada anotadas no CVAT no lote 1 contêm apenas 1 peça por frame. O receio era que isso limitasse a detecção com múltiplas peças ao vivo. **Testado em 20/09/2026 e funcionando** (ver seção 3.2) — o modelo generalizou bem mesmo sem exemplos multi-objeto no treino. Os riscos abaixo continuam válidos como pontos de atenção para cenários mais adversos (peças encostadas/sobrepostas, ângulos extremos), mas deixam de ser bloqueio — e o lote 2 (fotos com várias peças) passa a cobrir esse cenário também no treino:

1. **Peças encostadas ou parcialmente sobrepostas:** risco de supressão indevida via NMS.
2. **Composição/enquadramento não vistos no treino:** cenas com peças afastadas ou nas bordas do frame.
3. **Troca de identidade no tracking:** `model.track()` pode trocar `track_id` em cruzamentos rápidos entre peças parecidas.

Mitigação, se necessário no futuro: ajuste de `CONFIDENCE_THRESHOLD`/IoU do NMS como paliativo.

### 3.4 Retreino v2 com lote 1 + lote 2 (11/10/2026) — concluído, após correção de ambiente (seção 3.5)

**Dataset unificado** gerado por `build_yolo_dataset.py` (pasta `dataset_yolo_v2`), a partir de 8 zips:

| Origem | Zips | Imagens com anotação |
|---|---|---|
| Lote 1 (camadas, formato YOLO 1.1) | `lote1-camada-amarela/azul/base/verde/vermelha.zip` | 206 + 209 + 180 + 202 + 204 = **1.001** |
| Lote 2 (várias peças, formato "CVAT for images 1.1") | `lote2-multiplas-pecas-1/2/3.zip` | 37 + 42 + 42 = **121** |
| **Total** | | **1.122** (888 treino / 234 validação) |

Instâncias por classe (split estratificado: toda classe tem exemplos nos dois conjuntos):

| Classe | Treino | Validação |
|---|---|---|
| camada_base | 163 | 43 |
| camada_verde | 181 | 46 |
| camada_amarela | 184 | 49 |
| camada_azul | 217 | 57 |
| camada_vermelha | 193 | 53 |
| parafuso | 512 | 130 |
| encaixe_circular | 84 | 30 |
| encaixe_retangular | 90 | 38 |
| encaixe_hexagono | 81 | 28 |
| encaixe_capsula | 82 | 30 |

Formas no lote 2: **911 elipses e 192 polígonos** (1.103 formas) convertidas em caixas; nenhuma forma ignorada.

**Configuração do treino:** fine-tuning a partir do `best.pt` do lote 1 (que fica preservado; o novo treino grava em `lean_lab_v2`), 10 classes (a camada de saída é reinicializada automaticamente; o restante dos pesos é aproveitado). O comando inicial (`--epochs 60 --imgsz 960 --batch 4`) **falhou** — ver diagnóstico e comando corrigido na seção 3.5.

**Ressalvas a acompanhar:**
1. **Parafusos/encaixes sem anotação nas fotos do lote 1.** 1.001 das 1.122 imagens só têm a peça de camada anotada. Se parafusos ou peças de encaixe aparecem nessas fotos sem caixa, o modelo as vê como "fundo" e pode aprender a ignorá-las justamente sobre a camada. As 121 fotos do lote 2 compensam em parte. Verificar no teste ao vivo; se a detecção de parafuso/encaixe sobre a peça vier fraca, o caminho é anotar parafusos/encaixes em mais fotos de camada (seção 5.1, fonte 1).
2. **Caixa envolvente de polígono/elipse.** Como o YOLO de detecção só usa caixas, cada forma virou a caixa que a envolve (seção 5.2). Em objetos inclinados ou alongados (ex.: cápsula girada) a caixa inclui folga nos cantos. A regra de contagem usa o centro da caixa, então o impacto é pequeno, mas peças muito próximas podem ter caixas sobrepostas. Conferir visualmente uma amostra e as previsões de validação do treino.
3. **Métricas só valem com exemplos de validação.** Todas as 10 classes têm 28 ou mais instâncias na validação, então o mAP por classe agora é interpretável (ao contrário de `parafuso` no primeiro treino, seção 3.1).

**Resultado do treino (concluído em 11/10/2026):** fine-tuning a partir do `best.pt` do lote 1, GPU (RTX 2050, ver seção 3.5), `--imgsz 960 --batch -1 (AutoBatch escolheu 2) --workers 4`, 60 épocas, **~85 minutos** (5077s).

| Classe | mAP50-95 | Exemplos na validação |
|---|---|---|
| **Geral (todas as classes)** | **0,858** (mAP50 geral: 0,962; precisão 0,946; recall 0,907) | 504 instâncias / 234 imagens |
| camada_base | 0,975 | 43 |
| camada_verde | 0,980 | 46 |
| camada_amarela | 0,967 | 49 |
| camada_azul | 0,940 | 57 |
| camada_vermelha | 0,954 | 53 |
| parafuso | 0,689 | 130 |
| encaixe_circular | 0,856 | 30 |
| encaixe_retangular | 0,812 | 38 |
| encaixe_hexagono | 0,717 | 28 |
| encaixe_capsula | 0,690 | 30 |

**Leitura:** diferente do primeiro treino (seção 3.1), agora **todas as 10 classes têm exemplos reais de validação** — o mAP de `parafuso` deixou de ser o valor geral repetido (era o caso degenerado da seção 3.1) e passou a ser uma medida de verdade: 0,689, mais baixo que as camadas, mas nada perto de zero — já é detecção real, não ruído. As camadas continuam excelentes (0,94-0,98). Os encaixes ficaram entre 0,69 e 0,86; `encaixe_hexagono` e `encaixe_capsula` são os mais fracos, consistentes com terem o menor número de instâncias de treino (seção 3.4, tabela de instâncias). Isso é esperado para um dataset ainda pequeno dessas classes (81-90 no treino) e não invalida o resultado — é o próximo ponto a reforçar se, no teste ao vivo (seção 8), a detecção desses dois encaixes vier fraca.

### 3.5 Diagnóstico: a primeira tentativa de retreino morreu na CPU, sem erro visível (11/10/2026)

O comando original (`--epochs 60 --imgsz 960 --batch 4`) foi iniciado e, depois de um tempo, não deixou nenhum resultado: a pasta `runs_yolo/lean_lab_v2/` tinha só os artefatos de setup (`args.yaml`, `labels.jpg`, 3 `train_batch*.jpg`) e uma pasta `weights/` vazia — nenhum `results.csv`, nenhum peso salvo. Nenhum processo Python ficou rodando. Essa pasta parcial foi apagada depois do diagnóstico abaixo, para o próximo treino gravar limpo em `lean_lab_v2`.

**Hardware do notebook usado para treinar:**

| Componente | Especificação |
|---|---|
| CPU | Intel i5-12500H (12 núcleos / 16 threads) |
| RAM | 7,67 GB total — pouca para treino de visão computacional |
| GPU | NVIDIA GeForce RTX 2050, 4 GB de VRAM (driver com suporte a CUDA 12.9) |

**Causa raiz:** o pacote `torch` instalado na venv da Fase 2 era a build **CPU-only** (`2.14.0+cpu`) — `torch.cuda.is_available()` retornava `False`. Isso não é um erro do comando em si: o pacote `torch` do PyPI, no Windows, vem CPU-only por padrão desde que os builds com CUDA passaram a ser distribuídos só pelo índice próprio da PyTorch (`download.pytorch.org`); é fácil instalar `ultralytics` sem perceber que a GPU nunca vai ser usada. Com isso, o treino rodava inteiro na CPU, numa imagem de 960px com `batch=4` e os 8 processos de carregamento de imagem que são o padrão do Ultralytics (`workers`) — carga de memória alta o bastante, numa máquina com só 7,67 GB de RAM, para o processo ser encerrado antes de completar a primeira época (sem gerar log de erro próprio, por isso o problema só apareceu como "não sobrou nada na pasta do treino").

**Correção aplicada:**

1. **Reinstalado `torch`/`torchvision` com CUDA**, casando a versão com o CUDA 12.9 do driver: `torch==2.8.0+cu129` / `torchvision==0.23.0+cu129` (via `pip install --index-url https://download.pytorch.org/whl/cu129 ...`). Confirmado com um treino real de 1 época: `Ultralytics ... CUDA:0 (NVIDIA GeForce RTX 2050, 4096MiB)`, inferência a 12,7ms/imagem — a GPU está sendo usada de ponta a ponta.
2. **Medido o batch real que cabe em 960px nessa GPU**, usando o AutoBatch do Ultralytics (`batch=-1`, mede a VRAM livre antes de decidir): escolheu **batch = 2** (1,77GB de 4GB, 44% de uso) — confirma que `--batch 4` em 960px estava arriscando ficar no limite dos 4GB, ou passar dele. Nesse batch, uma época levou ~2min50s (444 lotes, 3-4,5 iterações/s).
3. **`train_yolo.py` passou a expor `--device` e `--workers`** (antes fixos no padrão do Ultralytics). O padrão de `--workers` foi reduzido de 8 para 4 — 8 processos paralelos carregando imagens em 960px é pesado para 7,67GB de RAM, mesmo com o treino agora na GPU.

**Comando corrigido para o retreino:**

```bash
python train_yolo.py --data ./dataset_yolo_v2/data.yaml \
    --model "<caminho do best.pt do lote 1>" \
    --name lean_lab_v2 --epochs 60 --imgsz 960 --batch -1 --workers 4
```

Não é necessário passar `--device`: com o `torch` corrigido, o padrão (`''`) já escolhe a GPU automaticamente. Estimativa: ~2,5-3h para as 60 épocas na GPU — a mesma configuração na CPU provavelmente nunca completaria uma época, dado o que já aconteceu.

**Ação se isso se repetir em outra máquina:** antes de treinar, confirmar com `python -c "import torch; print(torch.cuda.is_available())"`. Se vier `False` com uma GPU NVIDIA disponível, o pacote `torch` precisa ser reinstalado a partir do índice da PyTorch com a tag `cuXXX` compatível com a versão de CUDA do driver (visível em `nvidia-smi`), não do PyPI direto.

### 3.6 Diagnóstico: ao vivo, a webcam escondia parafuso e encaixe por falta de resolução (11/10/2026)

Primeiro teste ao vivo do `lean_lab_v2`: a camada é detectada normalmente, mas as peças de encaixe dentro dela **não aparecem demarcadas**, mesmo com a peça completa e visível.

**Causa:** as fotos de treino são de celular, em alta resolução (~4096×3072, 12 megapixels). A webcam usada no `infer_webcam_yolo.py` nunca teve a resolução de captura configurada — o script só fazia `cv2.VideoCapture(args.camera)` e lia os frames na resolução padrão que o driver da câmera entrega, que **por padrão, na prática, saiu em 640×480 (0,3 megapixel)**. Confirmado com um teste direto no notebook usado: pedindo explicitamente 1280×720 ao OpenCV, a mesma câmera entrega — ou seja, o padrão estava usando menos de um terço da resolução que a câmera já suporta.

Isso explica o padrão observado: a camada (objeto grande, cor uniforme) continua visível mesmo em baixa resolução, mas parafuso e as peças de encaixe (pequenos, precisam de detalhe de forma para distinguir círculo/retângulo/hexágono/cápsula) ficam com poucos pixels reais — nenhum valor de `--imgsz` no treino ou na inferência recupera detalhe que a câmera nunca capturou; aumentar `imgsz` só amplia os pixels que já existem (upscaling), não cria detalhe novo. Isso também explica por que os números da seção 3.4 (validação) parecem bons mesmo para `encaixe_circular`/`encaixe_retangular`: aquela validação usa as fotos de treino (alta resolução), não a webcam.

**Correção aplicada:** `infer_webcam_yolo.py` passou a configurar explicitamente a resolução da webcam ao abrir a câmera (`--cam_width`/`--cam_height`, padrão 1280×720 — o máximo que a câmera testada suportou; o OpenCV usa o mais próximo disponível se a câmera não suportar exatamente esse valor). O script agora imprime a resolução pedida e a obtida ao iniciar, para conferir rapidamente se a mudança teve efeito.

**Ainda assim, 1280×720 é ~16x menos pixels que as fotos de treino.** Se a detecção de parafuso/encaixe continuar fraca mesmo depois dessa correção, o próximo passo é testar com a peça mais perto da câmera (o objeto pequeno ocupando mais pixels do frame, independente da resolução total) e, se o notebook tiver uma webcam melhor ou for possível usar a câmera do celular como webcam, usar essa em vez da webcam embutida.

---

## 4. Passo 0: alinhamento com a Renault — respondido em 20/09/2026

### Regra de completude por estação (confirmada com a Renault)

| Camada | Parafusos esperados | Peças de encaixe necessárias |
|---|---|---|
| base | 0 | Nenhuma |
| camada_verde | 4 | Nenhuma |
| camada_amarela | 4 | 4 (1 circular + 1 retangular + 1 hexágono + 1 cápsula/estádio) |
| camada_azul | 4 | Nenhuma |
| camada_vermelha | 4 | 4 (mesmas 4 peças de encaixe da camada amarela) |

Os parafusos são **visualmente uniformes** entre todas as estações (mesmo tipo/tamanho) — não há necessidade de distinguir "tipos" de parafuso, só contar quantidade.

As 4 peças de encaixe (circular, retangular, hexágono, cápsula/estádio) são **diferentes entre si em formato**, e todas as 4 são necessárias para fechar corretamente as camadas amarela e vermelha.

### 4.1 Decisão de escopo: como tratar as peças de encaixe — DECIDIDO em 20/09/2026

Diferente das peças A/B/C/D descartadas na revisão 2 (seção 2) — que eram visualmente quase idênticas entre si dentro de uma mesma cor, o que tornava a anotação propensa a erro humano e redundante frente ao encaixe mecânico —, as 4 peças de encaixe (circular, retangular, hexágono, cápsula/estádio) têm **formatos claramente distintos** entre si, o que torna a anotação individual viável e pouco propensa a erro de rotulagem.

**Decisão do grupo: Opção A — detectar as 4 peças de encaixe como classes próprias do modelo YOLO** (`encaixe_circular`, `encaixe_retangular`, `encaixe_hexagono`, `encaixe_capsula`), no mesmo modelo unificado que já detecta camada + parafuso. A verificação de completude das camadas amarela/vermelha passa a checar, via regra de negócio, se as 4 classes de encaixe foram detectadas na cena além do número certo de parafusos (tabela da seção 4).

Alternativas consideradas e não escolhidas, mantidas aqui como registro de decisão:
- *Opção B (descartada):* não detectar visualmente as peças de encaixe, confiando apenas no encaixe mecânico (mesmo raciocínio do A/B/C/D) — descartada porque deixaria de verificar uma parte real do processo específica dessas duas camadas.
- *Opção C (descartada):* uma única classe genérica `peca_encaixe`, contando quantidade sem distinguir o formato — descartada por ser menos informativa que a Opção A sem ser significativamente mais simples de anotar, já que os formatos são fáceis de distinguir visualmente.

---

## 5. Anotação no CVAT (revisado — classes finais)

Com o CVAT já instalado e configurado:

1. Criar um projeto no CVAT (ex.: "Lean Lab — Peça, Parafusos e Encaixes"). Se o projeto atual já existir, basta adicionar as classes novas a ele (ver seção 5.1) em vez de criar um projeto separado.
2. Definir as classes finais: `camada_base`, `camada_verde`, `camada_amarela`, `camada_azul`, `camada_vermelha`, `parafuso`, `encaixe_circular`, `encaixe_retangular`, `encaixe_hexagono`, `encaixe_capsula`.
3. **Importar as 1.783 imagens já existentes** (reaproveitadas da Fase 0) e desenhar uma bounding box ao redor da peça inteira em cada uma, atribuindo a classe de cor correspondente.
4. Importar as fotos novas de parafuso e das 4 peças de encaixe (quando capturadas) e anotar cada uma individualmente com a classe correspondente.
5. Exportar as anotações. **Formato:** "YOLO 1.1" só serve para retângulos (usado no lote 1). Para anotações com polígono/elipse, exportar como **"CVAT for images 1.1"** (XML, guarda todas as formas), marcando **Save images** para levar as fotos dentro do zip (usado no lote 2, ver seção 5.2).

> Dica prática, já validada na Fase 1: comecem anotando um lote pequeno (ex.: 100-150 imagens de peça, já reaproveitadas) e treinem uma primeira versão rápida do modelo cedo, só para validar o pipeline completo (anotação → export → treino → inferência) antes de anotar o restante. **Feito com sucesso em 20/09/2026 com o lote 1 (~1.001 imagens) — ver resultado nas seções 3.1 e 3.2.**

> Lembrete técnico: `MASTER_CLASSES` no `build_yolo_dataset.py` já contém as 10 classes finais (feito em 22/09/2026), com remapeamento por nome (não por índice) — essencial porque cada zip do CVAT pode listar as classes em ordem diferente (confirmado na prática: a ordem das classes de encaixe no lote 2 difere da ordem do script).

### 5.1 Duas fontes de anotação de parafuso/encaixe (registrado em 22/09/2026)

Uma mesma imagem no CVAT pode ter várias caixas de classes diferentes ao mesmo tempo — a caixa da peça inteira (`camada_amarela`, por exemplo) e, dentro dela, uma caixa separada para cada parafuso/peça de encaixe visível naquela mesma foto. O grupo decidiu combinar duas fontes de anotação, não usar só uma:

1. **Anotação retroativa nas fotos de camada já existentes** (inclusive as do lote 1, já usadas no primeiro treino): reabrir essas imagens no CVAT e adicionar caixas de `parafuso`/encaixe onde aparecerem, além da caixa da peça inteira já existente. Vantagem: ensina o modelo a reconhecer esses objetos no contexto real (mesmo ângulo/distância da captura na estação), sem depender de nova sessão presencial. Risco: os objetos ficam pequenos na imagem (foto pensada para mostrar a peça inteira), o que pode ser mais difícil de aprender sem reforço.
2. **Fotos dedicadas, mais de perto** (sessão de captura nova, ver tabela da seção 3): dá exemplos "limpos" e variados do objeto isolado (ângulos, iluminação), complementando o ponto fraco da opção 1.

**Nota técnica:** como parafuso/encaixe são pequenos, se a detecção deles vier fraca depois do retreino, considerar aumentar `--imgsz` no `train_yolo.py` (ex.: 960 ou 1280, em vez do padrão 640) para preservar mais detalhe desses objetos pequenos no treino — mais lento, mas ajuda especificamente com objetos pequenos numa cena maior. O retreino v2 já usa 960.

### 5.2 Lote 2 (anotado e exportado em 11/10/2026)

Três zips exportados do CVAT (`lote2-multiplas-pecas-1.zip`, `-2.zip`, `-3.zip`), com as 10 classes finais, anotados com **retângulos, polígonos e elipses** para delimitar melhor as classes novas. Pontos de atenção e o que foi feito:

- **Formato de exportação.** A primeira tentativa de ler o lote 2 foi pelo formato "YOLO 1.1", pensado para retângulos; a documentação do CVAT não diz o que acontece com outras formas nele. Para não depender disso, o lote 2 foi exportado como **"CVAT for images 1.1"** (XML com todas as formas) com **Save images** (as fotos vêm numa pasta `images` dentro de cada zip). O `build_yolo_dataset.py` detecta o formato de cada zip pelo conteúdo (`annotations.xml` → XML; senão → YOLO 1.1), então o lote 1 em YOLO 1.1 e o lote 2 em XML são lidos juntos na mesma execução.
- **Conversão de forma em caixa.** O modelo é de detecção (só caixas). Retângulo vira ele mesmo (com rotação, a caixa que o envolve); polígono vira a caixa dos pontos; elipse vira a caixa da elipse (considerando rotação). Resultado real: 911 elipses e 192 polígonos convertidos, nenhuma forma ignorada. Formas `points`, máscaras e tags não têm como virar caixa e são ignoradas e contadas no relatório. **Limitação:** a caixa envolvente de um objeto inclinado/alongado tem folga nos cantos (ver ressalva 2 da seção 3.4).
- **Fotos dentro dos zips.** O script usa primeiro as fotos da pasta `images` do próprio zip e só depois procura em `--images_dir`. Isso resolveu o problema inicial em que as 121 anotações do lote 2 eram descartadas por "foto não encontrada".
- **Imagens repetidas entre lotes.** Se a mesma foto aparece em mais de um zip (comparada pelo conteúdo, não pelo nome), o script mantém só a versão com mais caixas, para a mesma foto não cair ao mesmo tempo em treino e validação (vazamento que inflaria as métricas).
- **Validação estratificada.** O split garante exemplos de toda classe na validação — o primeiro treino teve `parafuso` com zero exemplos na validação, o que tornou o resultado dessa classe sem sentido (seção 3.1).
- **Segurança dos dados.** O script só lê os zips e as fotos originais; grava tudo numa pasta de saída nova (recusa pasta com conteúdo ou dentro das pastas de entrada). Os lotes 1 e 2 e o `best.pt` do v1 permanecem intactos.

---

## 6. Decisões técnicas (revisado)

| Decisão | Escolha | Motivo |
|---|---|---|
| Framework | **Ultralytics (`ultralytics`)** | API de alto nível, treino via poucos comandos |
| Variante do modelo | **YOLO11n ou YOLO26n ("nano")** | Leve o suficiente para CPU/webcam+notebook em tempo real |
| Modelo único vs. múltiplos | **Um único modelo** detectando peça (por cor) + `parafuso` + as 4 classes de encaixe simultaneamente | Simplifica o pipeline de inferência — uma só passada por frame, um só ponto de manutenção |
| Verificação de completude | **Regra de negócio por estação** (contagem de parafusos e peças de encaixe detectados vs. o esperado — tabela da seção 4) | Evita precisar fotografar todos os estados possíveis de montagem incompleta |
| Detecção de presença (vazio vs. peça) | Natural — nenhuma detecção de classe de peça na ROI = vazio | A classe `vazio` da Fase 1 deixa de ser necessária |
| Contagem sem recontagem da mesma peça parada | Tracking nativo do Ultralytics (`model.track()`, baseado em ByteTrack), já testado ao vivo com sucesso, inclusive com múltiplas peças | Mais robusto que a máquina de estados da Fase 1 |
| Retreino com classes novas | **Fine-tuning a partir do `best.pt` do lote 1** (passado em `--model`), não treino do zero — o Ultralytics reinicializa automaticamente a camada de saída para as 10 classes, mantendo o aprendizado já obtido sobre cor de camada | Aproveita o treino já validado (seção 3.1) em vez de descartá-lo |
| Versões de modelo | O `best.pt` do lote 1 (v1) é mantido; o retreino grava em `lean_lab_v2` | Permite comparar v1 x v2 na webcam e voltar ao v1 se necessário |
| Entrada do `build_yolo_dataset.py` | Aceita zips "YOLO 1.1" e "CVAT for images 1.1" (XML) na mesma pasta; usa as fotos de dentro do zip primeiro; remapeia classes por nome; deduplica por conteúdo | Lote 1 (YOLO) e lote 2 (XML, polígono/elipse) lidos juntos sem reexportar o lote 1 |
| Parafuso/encaixe só contam dentro da peça | Contenção geométrica: o centro da caixa do parafuso/encaixe precisa cair dentro da caixa da peça (`box_center_inside`) | Evita contar um parafuso solto na mesa como parte da montagem |
| Desligar uma classe sem retreinar | `--ignorar_classes` no `infer_webcam_yolo.py`, que usa o filtro `classes=` do Ultralytics (os pesos não mudam, só a saída é filtrada) | Permite esconder uma classe pouco confiável sem voltar a uma versão anterior do modelo |
| `infer_webcam_yolo.py` | **Atualizado em 04/10/2026**: receita de completude por estação (tabela da seção 4), checagem das 4 formas de encaixe pelo nome (não só contagem), contenção geométrica para parafuso e encaixe | Implementa a regra de negócio da seção 4 |
| Backend/dashboard | Schema do evento ampliado (`encaixes_detectados`/`encaixes_esperados`/`modelo_versao`), sem quebrar eventos antigos (campos novos opcionais; banco SQLite já existente ganha as colunas sozinho ao iniciar o backend — ver `ensure_sqlite_columns` em `backend/database.py`) (12/10/2026) | Reforça que a separação em camadas da Fase 1.2 já isola essa migração — nenhuma mudança na estrutura da API, só no conteúdo do evento |
| Dashboard (Fase 2) | Filtros (versão do modelo, estação, status), aviso de estação sem evento recente, gráfico de tendência ao longo do tempo, exportação em CSV, horário convertido para fuso local (12/10/2026) | Indicadores por estação já existiam; essas melhorias respondem a limitações observadas no uso: não dava pra comparar v1×v2, nem ver tendência ao longo de um turno, nem notar uma estação parada sem abrir a tabela |
| Saída do treino | `train_yolo.py` grava em caminho **absoluto** e imprime o caminho real do `best.pt` | No primeiro treino o Ultralytics gravou em `runs/detect/runs_yolo/...` (pasta das settings dele) e o caminho impresso estava errado |
| Ambiente de treino (GPU) | `torch`/`torchvision` reinstalados com build CUDA (`cu129`, compatível com o driver da RTX 2050) na venv da Fase 2; `train_yolo.py` passou a expor `--device` e `--workers` (padrão de `--workers` reduzido de 8 para 4) | O pacote `torch` do PyPI vem CPU-only por padrão — sem reinstalar com o índice certo, o treino nunca usa a GPU, mesmo com uma disponível (ver seção 3.5) |
| Tamanho de batch em GPU com pouca VRAM | `--batch -1` (AutoBatch do Ultralytics), em vez de um número fixo | Medido na prática: só 2 cabe em 960px nos 4GB da RTX 2050 a 60% de uso; um número fixo maior arriscava ultrapassar a VRAM (seção 3.5) |

**Limitação conhecida do `infer_webcam_yolo.py` (a tratar se aparecer nos testes):** a completude é avaliada no primeiro frame de um novo `track_id`. Se a peça ainda estiver sendo montada nesse instante (parafusos sendo colocados), pode sair um alerta de incompleto falso. Correção possível: uma pequena espera de estabilização antes de avaliar.

---

## 7. O que fica para depois (dentro da Fase 2, mas não agora)

- Identificação por QR Code/RFID (qual peça específica passou por cada estação, não só a contagem/estação).
- Replicação para as demais estações + MQTT entre múltiplas estações.
- Sensor de presença físico (hardware novo) — com detecção de objeto, a necessidade dele cai bastante, já que o próprio YOLO resolve presença de forma nativa.
- Verificação fina por componente individual (A/B/C/D) — descartada por redundância mecânica e dificuldade de anotação confiável (ver seção 2).
- Enviar ao backend/dashboard as contagens de parafuso e encaixe detectados (hoje só vão para o CSV de backup).

> **Nota (20/09/2026):** a detecção de avarias/defeitos, cogitada na pesquisa inicial (`projeto-renault-lean-lab-pesquisa.md`, seção 3.5) e listada anteriormente aqui como possível frente futura, **foi removida do escopo do projeto**. Motivo: o laboratório não disponibiliza peças com defeito real para treinar esse tipo de modelo (treinar detecção de anomalia exige exemplos reais de defeito, que não existem no ambiente de treinamento).

### 7.1 Como funcionaria a identificação por QR Code/RFID (explicação conceitual, não implementada)

Essa frente resolveria uma pergunta diferente da que a Fase 1/2 já respondem: hoje o sistema sabe "que tipo de peça passou por aqui e se está completa", mas não sabe "**qual** peça específica, dentre todas as produzidas, é essa". QR Code/RFID serviriam para dar uma identidade única a cada peça:

- **QR Code:** um código impresso e colado (ou uma etiqueta) na peça-base, gerado no início da montagem (ex.: `PECA-2026-000123`). A mesma câmera que já roda o YOLO pode ler o QR Code (bibliotecas como `pyzbar` ou o próprio OpenCV), sem precisar de hardware extra — é só mais um passo de processamento na mesma imagem. Vantagem: custo zero de hardware. Desvantagem: o código pode ficar sujo, amassado ou fora de ângulo de leitura durante o manuseio na linha.
- **RFID:** uma tag pequena (passiva, sem bateria) colada na peça-base, lida por um leitor físico (módulo tipo RC522) posicionado em cada estação. Vantagem: não depende de estar visível/limpo, leitura mais confiável em ambiente industrial. Desvantagem: exige comprar e instalar um leitor por estação (baixo custo, mas é hardware novo, ao contrário do QR Code que reaproveita a câmera já instalada).

Na prática, isso permitiria, por exemplo, rastrear o histórico completo de uma peça específica (por quais estações passou, quanto tempo ficou em cada uma, se algum alerta foi disparado) em vez de só estatísticas agregadas por estação — útil para rastreabilidade e auditoria, mas não é necessário para o objetivo atual do MVP (verificar se a montagem está correta). Por isso permanece como evolução futura, não como bloqueio da Fase 2.

---

## 8. Checklist para concluir a Fase 2

- [x] Quantidade de parafusos esperada por estação confirmada com a Renault (seção 4).
- [x] Uniformidade dos parafusos confirmada (seção 4).
- [x] Decisão de escopo das peças de encaixe tomada — Opção A, 4 classes próprias (seção 4.1).
- [x] Projeto criado no CVAT com as classes finais (camada + parafuso + 4 encaixes).
- [x] Reanotação de um primeiro lote das 1.783 imagens já existentes (peça inteira, por cor) — lote 1, 1.001 imagens.
- [x] Captura e anotação de parafuso e das 4 peças de encaixe, dentro e fora das peças de camada, incluindo cenas com várias peças — lote 2 (3 zips, 121 fotos, 11/10/2026).
- [x] Export das anotações: lote 1 em YOLO 1.1; lote 2 em "CVAT for images 1.1" (XML com polígono/elipse + fotos).
- [x] Ambiente Python com `ultralytics` instalado.
- [x] Primeiro treino de teste rodado (lote 1) — pipeline ponta a ponta validado (ver seção 3.1).
- [x] Testar `infer_webcam_yolo.py` ao vivo com o modelo do lote 1 — detecção de peça por cor, inclusive com múltiplas peças simultâneas (seções 3.2 e 3.3).
- [x] Atualizar `MASTER_CLASSES` em `build_yolo_dataset.py` com as 4 classes de encaixe (22/09/2026).
- [x] Ajustar `infer_webcam_yolo.py` para a receita por estação, contenção geométrica e `--ignorar_classes` (04/10/2026).
- [x] Ajustar `build_yolo_dataset.py` e `train_yolo.py` para o lote 2 (11/10/2026): leitura de XML (polígono/elipse → caixa), fotos de dentro dos zips, duplicatas entre lotes por conteúdo, split estratificado, relatório por classe, caminho de saída absoluto.
- [x] **Rodar `build_yolo_dataset.py` com lote 1 + lote 2** — 1.122 imagens (888/234), 10 classes com exemplos nos dois conjuntos (seção 3.4).
- [x] Diagnosticar por que a primeira tentativa de retreino morreu sem erro (treino caiu na CPU por `torch` CPU-only) e corrigir o ambiente: `torch`/`torchvision` com CUDA instalados, `train_yolo.py` com `--device`/`--workers`, batch real medido via AutoBatch (seção 3.5).
- [x] **Retreinar de fato** (fine-tuning a partir do `best.pt` do lote 1, `--imgsz 960 --batch -1 --workers 4 --epochs 60`, na GPU, ~85min) e conferir o mAP **por classe com a contagem de exemplos de validação ao lado**; resultado registrado na seção 3.4 — mAP50-95 geral 0,858, todas as classes com validação real.
- [ ] (Recomendado) Conferir visualmente uma amostra das caixas geradas a partir de polígono/elipse e as previsões de validação do treino.
- [x] Testar o novo `best.pt` ao vivo no `infer_webcam_yolo.py` — camada detectada normalmente, mas parafuso/encaixe não apareciam demarcados. Diagnosticado: webcam capturando em 640×480 por padrão (seção 3.6). Corrigido (`--cam_width`/`--cam_height`, padrão 1280×720).
- [ ] Repetir o teste ao vivo com a correção de resolução, nas camadas verde (4 parafusos) e amarela/vermelha (4 parafusos + 4 encaixes), com parafuso solto na mesa fora da peça; comparar v1 x v2.
- [ ] Anotar parafusos/encaixes nas fotos de camada do lote 1 e/ou o restante das 1.783 imagens de camada, se a detecção de parafuso/encaixe sobre a peça vier fraca (opcional).

---

## 9. Como isso conecta com as 3 matérias

- **IA Aplicada:** detecção de objetos (YOLO), reaproveitamento de dataset entre abordagens (classificação → detecção), decisão de regra de negócio vs. classe visual para completude, decisão de granularidade de detecção (peças de encaixe como classes próprias vs. A/B/C/D descartadas) documentada como processo de refinamento de escopo, anotação multi-classe por imagem (peça + componentes) como técnica de contexto real, conversão de formas de anotação (polígono/elipse) para caixas de detecção, e cuidado com a validade das métricas (classe sem exemplos na validação, vazamento entre treino e validação).
- **Arquitetura de Software:** evolução do contrato de evento (JSON com contagem de parafusos e peças de encaixe), mantendo a separação em camadas já estabelecida na Fase 1.2; histórico de decisões documentado (seções 2 e 4.1) como registro de arquitetura evolutiva; pipeline de dados que lê formatos de anotação diferentes sem alterar os dados de origem.
- **Arquitetura de Sistemas IoT:** robustez da captura na borda a cenários reais (múltiplos objetos simultâneos na bancada, já validada), simplificação da lógica de presença sem sensor físico dedicado, avaliação conceitual de QR Code/RFID para identificação individual de peças (seção 7.1).