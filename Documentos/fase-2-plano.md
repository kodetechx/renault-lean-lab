# Fase 2 — Detecção da Peça Completa e Contagem de Parafusos via YOLO
## Projeto: Digitalização do Lab de Lean Manufacturing — Renault x UniSenai

**Status:** 🟡 Escopo fechado (Passo 0 respondido, decisão de encaixe tomada) — falta a sessão de captura dedicada de parafuso + peças de encaixe
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

### O que ainda falta capturar (próxima sessão de terça)

| Necessidade | Por quê | Prioridade |
|---|---|---|
| Fotos de parafusos isolados e já encaixados na peça | Ainda não existem em quantidade suficiente (18 fotos de "imãs/parafusos" coletadas na Fase 0, insuficiente) | Alta — bloqueia a parte de contagem |
| Fotos das 4 peças de encaixe (circular, retangular, hexágono, cápsula/estádio), isoladas e já encaixadas nas camadas amarela/vermelha | Decidido em 20/09/2026 (seção 4.1): serão detectadas como classes próprias do modelo | Alta — bloqueia a verificação de completude das camadas amarela/vermelha |
| Fotos com **mais de uma peça no quadro simultaneamente** | Confirmado funcionando ao vivo em 20/09/2026 (ver seção 3.2) — item mantido como reforço, não mais bloqueante | Baixa (já validado; captura extra apenas fortalece o modelo) |

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

**Ressalva importante sobre `parafuso`:** o script imprimiu `parafuso: 0,965` na lista "mAP50-95 por classe", mas esse número **deve ser desconsiderado**. A classe `parafuso` nem aparece na tabela nativa de validação do Ultralytics (que lista só as 5 classes de camada), o que indica fortemente que o split de validação (200 imagens sorteadas do lote 1) não continha nenhuma instância real de parafuso — consistente com o relatório do `build_yolo_dataset.py`, que registrou apenas 2 instâncias de `parafuso` em todo o lote 1. Quando uma classe não tem nenhum exemplo de verdade no conjunto de validação, o mAP calculado para ela cai num caso degenerado (pode sair artificialmente alto ou zero, dependendo da implementação) e não reflete qualidade real de detecção. Com só 2 instâncias de treino, é matematicamente impossível que o modelo já reconheça parafuso de forma confiável. **A contagem de parafusos no `infer_webcam_yolo.py` continua não-funcional até a sessão de captura dedicada de parafusos (e agora também de encaixe) ser feita e um novo treino/validação com instâncias reais dessas classes for rodado.**

### 3.2 Teste de inferência ao vivo (webcam, 20/09/2026)

Rodado `infer_webcam_yolo.py` com o `best.pt` do lote 1. Resultado: **detecção de peça por cor funcionando corretamente ao vivo**, via webcam, confirmando que o modelo generaliza além do conjunto de validação (câmera/condições de luz diferentes das fotos de treino). Este é o primeiro teste end-to-end do pipeline completo da Fase 2 (captura → anotação → treino → inferência ao vivo → log de evento).

**Confirmado no mesmo dia:** o modelo já detecta corretamente **mais de uma peça simultaneamente em câmera** ao vivo, mesmo o dataset de treino tendo apenas 1 peça por imagem (ver seção 3.3) — resolvendo informalmente a dúvida que motivou tecnicamente a escolha do YOLO sobre o MobileNetV2 (seção 2, revisão 3).

### 3.3 Risco identificado (mitigado): generalização para múltiplas peças no quadro

Todas as 1.783 imagens de camada anotadas no CVAT contêm apenas 1 peça por frame. O receio era que isso limitasse a detecção com múltiplas peças ao vivo. **Testado em 20/09/2026 e funcionando** (ver seção 3.2) — o modelo generalizou bem mesmo sem exemplos multi-objeto no treino. Os riscos abaixo continuam válidos como pontos de atenção para cenários mais adversos (peças encostadas/sobrepostas, ângulos extremos), mas deixam de ser bloqueio:

1. **Peças encostadas ou parcialmente sobrepostas:** risco de supressão indevida via NMS.
2. **Composição/enquadramento não vistos no treino:** cenas com peças afastadas ou nas bordas do frame.
3. **Troca de identidade no tracking:** `model.track()` pode trocar `track_id` em cruzamentos rápidos entre peças parecidas.

Mitigação, se necessário no futuro: captura multi-peça real + fine-tuning a partir do `best.pt` atual (em vez de retreinar do zero), ou ajuste de `CONFIDENCE_THRESHOLD`/IoU do NMS como paliativo.

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

1. Criar um projeto no CVAT (ex.: "Lean Lab — Peça, Parafusos e Encaixes").
2. Definir as classes finais: `camada_base`, `camada_verde`, `camada_amarela`, `camada_azul`, `camada_vermelha`, `parafuso`, `encaixe_circular`, `encaixe_retangular`, `encaixe_hexagono`, `encaixe_capsula`.
3. **Importar as 1.783 imagens já existentes** (reaproveitadas da Fase 0) e desenhar uma bounding box ao redor da peça inteira em cada uma, atribuindo a classe de cor correspondente.
4. Importar as fotos novas de parafuso e das 4 peças de encaixe (quando capturadas) e anotar cada uma individualmente com a classe correspondente.
5. Exportar as anotações em formato **YOLO** (exportação nativa do CVAT).

> Dica prática, já validada na Fase 1: comecem anotando um lote pequeno (ex.: 100-150 imagens de peça, já reaproveitadas) e treinem uma primeira versão rápida do modelo cedo, só para validar o pipeline completo (anotação → export → treino → inferência) antes de anotar o restante. **Feito com sucesso em 20/09/2026 com o lote 1 (~1.001 imagens) — ver resultado nas seções 3.1 e 3.2.**

> Lembrete técnico (já coberto por `build_yolo_dataset.py`, seção 6): ao adicionar as novas classes de encaixe, atualizar a lista `MASTER_CLASSES` no script para incluir `encaixe_circular`, `encaixe_retangular`, `encaixe_hexagono`, `encaixe_capsula`, mantendo o remapeamento por nome (não por índice) para evitar o mesmo risco de inconsistência já documentado.

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
| O que muda no `infer_webcam.py` | De "1 rótulo por frame" para "lista de detecções (caixa + classe + confiança) por frame"; lógica de contagem de parafusos e peças de encaixe comparada à receita esperada por estação (tabela da seção 4) — **pendente: hoje o script usa um único `--parafusos_esperados` fixo por execução e não checa encaixe; falta ajustar para a receita variar por estação (0 na base, 4 nas demais) e somar a checagem das 4 classes de encaixe quando a estação for amarela/vermelha** | — |
| Backend/dashboard | Sem mudança estrutural — a API já recebe eventos genéricos; muda o conteúdo do evento (incluir contagem de parafusos e de peças de encaixe detectadas) | Reforça que a separação em camadas da Fase 1.2 já isola essa migração |

---

## 7. O que fica para depois (dentro da Fase 2, mas não agora)

- Identificação por QR Code/RFID (qual peça específica passou por cada estação, não só a contagem/estação).
- Replicação para as demais estações + MQTT entre múltiplas estações.
- Sensor de presença físico (hardware novo) — com detecção de objeto, a necessidade dele cai bastante, já que o próprio YOLO resolve presença de forma nativa.
- Verificação fina por componente individual (A/B/C/D) — descartada por redundância mecânica e dificuldade de anotação confiável (ver seção 2).

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
- [x] Projeto criado no CVAT com as classes de camada definidas (seção 5).
- [ ] Adicionar as 4 classes de encaixe ao projeto CVAT (seção 5).
- [x] Reanotação de um primeiro lote das 1.783 imagens já existentes (peça inteira, por cor) — lote 1, ~1.001 imagens.
- [ ] Nova sessão de captura de fotos de parafuso (isolado + em contexto).
- [ ] Nova sessão de captura das 4 peças de encaixe (isoladas + em contexto, nas camadas amarela e vermelha).
- [x] Export das anotações em formato YOLO.
- [x] Ambiente Python com `ultralytics` instalado.
- [x] Primeiro treino de teste rodado (lote 1) — pipeline ponta a ponta validado (ver seção 3.1). Resultado: detecção de camada excelente (mAP50 geral 0,995); contagem de parafuso ainda não confiável (poucas instâncias anotadas).
- [x] Testar `infer_webcam_yolo.py` ao vivo com o modelo do lote 1 — detecção de peça por cor confirmada funcionando ao vivo, inclusive com múltiplas peças simultâneas (ver seções 3.2 e 3.3).
- [ ] Atualizar `MASTER_CLASSES` em `build_yolo_dataset.py` com as 4 novas classes de encaixe.
- [ ] Ajustar `infer_webcam_yolo.py` para a receita de completude variar por estação (parafuso + encaixe, tabela da seção 4), em vez do `--parafusos_esperados` fixo atual.
- [ ] Retreinar com dataset de parafuso e encaixe real, uma vez capturado.
- [ ] (Opcional, reforça robustez) Nova sessão de captura formal com múltiplas peças no mesmo quadro, com anotação.
- [ ] Anotar lote 2 (restante das 1.783 imagens) para ampliar o dataset de camada.

---

## 9. Como isso conecta com as 3 matérias

- **IA Aplicada:** detecção de objetos (YOLO), reaproveitamento de dataset entre abordagens (classificação → detecção), decisão de regra de negócio vs. classe visual para completude, decisão de granularidade de detecção (peças de encaixe como classes próprias vs. A/B/C/D descartadas) documentada como processo de refinamento de escopo.
- **Arquitetura de Software:** evolução do contrato de evento (JSON com contagem de parafusos e peças de encaixe), mantendo a separação em camadas já estabelecida na Fase 1.2; histórico de decisões documentado (seções 2 e 4.1) como registro de arquitetura evolutiva.
- **Arquitetura de Sistemas IoT:** robustez da captura na borda a cenários reais (múltiplos objetos simultâneos na bancada, já validada), simplificação da lógica de presença sem sensor físico dedicado, avaliação conceitual de QR Code/RFID para identificação individual de peças (seção 7.1).