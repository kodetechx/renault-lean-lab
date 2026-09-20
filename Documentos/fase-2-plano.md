# Fase 2 — Detecção da Peça Completa e Contagem de Parafusos via YOLO
## Projeto: Digitalização do Lab de Lean Manufacturing — Renault x UniSenai

**Status:** 🟢 Primeiro treino de teste (lote 1) concluído com sucesso — pipeline ponta a ponta validado
**Depende de:** `fase-1-plano.md` (MVP de classificação de camada, concluído) e `fase-0-validacao-e-escopo.md`
**Prioridade escolhida pelo grupo (set/2026):** detecção de objeto (YOLO) como substituto do MobileNetV2 para a verificação da camada + contagem de parafusos, entre as 4 frentes possíveis da Fase 2 (as outras — detecção de avaria, QR/RFID, replicação multi-estação — ficam para depois, ver seção 7).

---

## 1. Objetivo da Fase 2 (esta frente)

Substituir a classificação de imagem inteira (MobileNetV2, Fase 1) por **detecção de objetos (YOLO)** para dois fins:

1. **Detectar a peça montada como um objeto** (uma caixa por peça, classificada pela cor da camada) — resolve uma limitação estrutural do MobileNetV2: ele só dá um rótulo por frame inteiro, então não lida bem com **mais de uma peça na bancada ao mesmo tempo** (cenário realista no dia a dia do operador).
2. **Detectar e contar parafusos** individualmente — permite comparar a quantidade encontrada com a esperada por estação.

A verificação de "montagem completa/correta" passa a ser uma **regra de negócio** (contagem de parafusos detectados vs. esperados), não uma classe visual — evitando a necessidade de fotografar todos os estados possíveis de montagem incompleta.

---

## 2. Histórico da decisão (registrado em 18/09/2026, para a documentação acadêmica do projeto)

Este escopo passou por três revisões na mesma conversa, vale documentar o raciocínio:

1. **Proposta inicial:** detectar cada componente individual (peças A/B/C/D de cada cor + parafusos) via YOLO, para verificação fina de montagem.
2. **Primeira revisão — descartar A/B/C/D:** o grupo observou que as peças A/B/C/D de uma mesma cor são visualmente muito parecidas, e que o encaixe mecânico entre elas é específico (uma peça errada fisicamente não encaixa no lugar de outra — um design do tipo *poka-yoke*). Duas consequências: (a) verificar componente por componente é redundante, já que o encaixe físico já impede montagem errada; (b) anotar caixas para peças visualmente quase idênticas é propenso a erro de rotulagem humana, o que geraria um dataset ruim independente do volume de fotos.
3. **Segunda revisão — manter YOLO para a peça inteira (não voltar ao MobileNetV2):** o grupo identificou que, mesmo com a simplificação acima, a classificação de imagem inteira (MobileNetV2) tem uma fragilidade de longo prazo: se mais de uma peça estiver na bancada ao mesmo tempo, o modelo não consegue contar/localizar cada uma individualmente, porque só produz um rótulo por frame. Decisão: usar YOLO para detectar a **peça inteira montada** (uma caixa por peça, classificada pela cor), não para os componentes internos. Isso também resolve de forma nativa a checagem de presença (a classe `vazio` criada como solução de contorno na Fase 1 deixa de ser necessária).

**Resultado:** um único modelo YOLO com classes de peça (por cor) + classe de parafuso, e a verificação de completude feita em lógica de negócio (contagem) em vez de em classes visuais dedicadas.

---

## 3. Boa notícia: parte do dataset já existe e pode ser reaproveitada

As **1.783 imagens de camada coletadas na Fase 0** (306 base + 281 verde + 468 amarela + 384 azul + 344 vermelha) não precisam ser recapturadas. Elas foram tiradas para classificação (uma classe por pasta), mas servem perfeitamente como matéria-prima para detecção — só precisam ser **reanotadas no CVAT com uma bounding box ao redor da peça inteira**, atribuindo a classe de cor correspondente. Isso é uma anotação rápida (tipicamente 1 caixa por imagem), bem mais simples do que o cenário de componente-a-componente descartado na seção 2.

### O que ainda falta capturar (novo, em sessão de terça)

| Necessidade | Por quê | Prioridade |
|---|---|---|
| Fotos de parafusos isolados e já encaixados na peça | Ainda não existem em quantidade suficiente (18 fotos de "imãs/parafusos" coletadas na Fase 0, insuficiente) | Alta — bloqueia a parte de contagem |
| Fotos com **mais de uma peça no quadro simultaneamente** | O dataset atual provavelmente tem uma peça por foto; para validar de verdade a robustez multi-objeto que motivou essa decisão, vale ter exemplos reais desse cenário | Média — não bloqueia o início, mas fortalece o modelo para o caso de uso que motivou a escolha do YOLO |

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

**Ressalva importante sobre `parafuso`:** o script imprimiu `parafuso: 0,965` na lista "mAP50-95 por classe", mas esse número **deve ser desconsiderado**. A classe `parafuso` nem aparece na tabela nativa de validação do Ultralytics (que lista só as 5 classes de camada), o que indica fortemente que o split de validação (200 imagens sorteadas do lote 1) não continha nenhuma instância real de parafuso — consistente com o relatório do `build_yolo_dataset.py`, que registrou apenas 2 instâncias de `parafuso` em todo o lote 1. Quando uma classe não tem nenhum exemplo de verdade no conjunto de validação, o mAP calculado para ela cai num caso degenerado (pode sair artificialmente alto ou zero, dependendo da implementação) e não reflete qualidade real de detecção. Com só 2 instâncias de treino, é matematicamente impossível que o modelo já reconheça parafuso de forma confiável. **A contagem de parafusos no `infer_webcam_yolo.py` continua não-funcional até a sessão de captura dedicada de parafusos (linha "Alta prioridade" da tabela acima) ser feita e um novo treino/validação com instâncias reais de parafuso for rodado.**

---

## 4. Passo 0: alinhar com a Renault (revisado)

- [ ] Confirmar a **quantidade exata de parafusos esperada por estação** (a "receita" que vira a regra de negócio de completude).
- [ ] Confirmar se os parafusos são visualmente uniformes (mesmo tipo/tamanho em todas as estações) ou se há variação relevante para a contagem.
- [ ] (Descartado da versão anterior: não é mais necessário alinhar nomenclatura A/B/C/D, já que essas classes saíram de escopo.)

---

## 5. Anotação no CVAT (revisado)

Com o CVAT já instalado e configurado:

1. Criar um projeto no CVAT (ex.: "Lean Lab — Peça e Parafusos").
2. Definir as classes: `camada_base`, `camada_verde`, `camada_amarela`, `camada_azul`, `camada_vermelha`, `parafuso`.
3. **Importar as 1.783 imagens já existentes** (reaproveitadas da Fase 0) e desenhar uma bounding box ao redor da peça inteira em cada uma, atribuindo a classe de cor correspondente.
4. Importar as fotos novas de parafuso (quando capturadas) e anotar cada parafuso individualmente com a classe `parafuso`.
5. Exportar as anotações em formato **YOLO** (exportação nativa do CVAT).

> Dica prática, já validada na Fase 1: comecem anotando um lote pequeno (ex.: 100-150 imagens de peça, já reaproveitadas) e treinem uma primeira versão rápida do modelo cedo, só para validar o pipeline completo (anotação → export → treino → inferência) antes de anotar o restante. **Feito com sucesso em 20/09/2026 com o lote 1 (~1.001 imagens) — ver resultado na seção 3.1.**

---

## 6. Decisões técnicas (revisado)

| Decisão | Escolha | Motivo |
|---|---|---|
| Framework | **Ultralytics (`ultralytics`)** | API de alto nível, treino via poucos comandos |
| Variante do modelo | **YOLO11n ou YOLO26n ("nano")** | Leve o suficiente para CPU/webcam+notebook em tempo real |
| Modelo único vs. múltiplos | **Um único modelo** detectando peça (por cor) + parafuso simultaneamente | Simplifica o pipeline de inferência — uma só passada por frame, um só ponto de manutenção |
| Verificação de completude | **Regra de negócio** (contagem de parafusos detectados vs. esperado por estação), não uma classe visual | Evita precisar fotografar todos os estados possíveis de montagem incompleta |
| Detecção de presença (vazio vs. peça) | Natural — nenhuma detecção de classe de peça na ROI = vazio | A classe `vazio` da Fase 1 deixa de ser necessária |
| Contagem sem recontagem da mesma peça parada | Avaliar o tracking nativo do Ultralytics (`model.track()`, baseado em ByteTrack) para acompanhar a mesma peça entre frames | Mais robusto que a máquina de estados da Fase 1, e já lida melhor com múltiplas peças na cena |
| O que muda no `infer_webcam.py` | De "1 rótulo por frame" para "lista de detecções (caixa + classe + confiança) por frame"; lógica de contagem de parafusos comparada à receita esperada por estação | — |
| Backend/dashboard | Sem mudança estrutural — a API já recebe eventos genéricos; muda o conteúdo do evento (incluir contagem de parafusos detectados) | Reforça que a separação em camadas da Fase 1.2 já isola essa migração |

---

## 7. O que fica para depois (dentro da Fase 2, mas não agora)

- Detecção de avarias/defeitos (precisa de dataset de peças defeituosas, ainda não coletado).
- Identificação por QR Code/RFID.
- Replicação para as demais estações + MQTT entre múltiplas estações.
- Sensor de presença físico (hardware novo) — com detecção de objeto, a necessidade dele cai bastante, já que o próprio YOLO resolve presença de forma nativa.
- Verificação fina por componente individual (A/B/C/D) — descartada por redundância mecânica e dificuldade de anotação confiável (ver seção 2).

---

## 8. Checklist para iniciar de fato o treino

- [ ] Quantidade de parafusos esperada por estação confirmada com a Renault (seção 4).
- [x] Projeto criado no CVAT com as classes definidas (seção 5).
- [x] Reanotação de um primeiro lote das 1.783 imagens já existentes (peça inteira, por cor) — lote 1, ~1.001 imagens.
- [ ] Nova sessão de captura de fotos de parafuso (isolado + em contexto).
- [x] Export das anotações em formato YOLO.
- [x] Ambiente Python com `ultralytics` instalado.
- [x] Primeiro treino de teste rodado (lote 1) — pipeline ponta a ponta validado (ver seção 3.1). Resultado: detecção de camada excelente (mAP50 geral 0,995); contagem de parafuso ainda não confiável (poucas instâncias anotadas).
- [ ] (Opcional, reforça robustez) Nova sessão de captura com múltiplas peças no mesmo quadro.
- [ ] Anotar lote 2 (restante das 1.783 imagens) para ampliar o dataset de camada.
- [ ] Testar `infer_webcam_yolo.py` ao vivo com o modelo do lote 1.
- [ ] Retreinar com dataset de parafuso adequado, uma vez capturado.

---

## 9. Como isso conecta com as 3 matérias

- **IA Aplicada:** detecção de objetos (YOLO), reaproveitamento de dataset entre abordagens (classificação → detecção), decisão de regra de negócio vs. classe visual para completude.
- **Arquitetura de Software:** evolução do contrato de evento (JSON com contagem de parafusos), mantendo a separação em camadas já estabelecida na Fase 1.2; histórico de decisão documentado (seção 2) como registro de arquitetura evolutiva.
- **Arquitetura de Sistemas IoT:** robustez da captura na borda a cenários reais (múltiplos objetos simultâneos na bancada), simplificação da lógica de presença sem sensor físico dedicado.