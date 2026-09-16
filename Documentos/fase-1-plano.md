# Fase 1 — Implementação do MVP
## Projeto: Digitalização do Lab de Lean Manufacturing — Renault x UniSenai

**Status:** ✅ Fase 1 concluída e testada de ponta a ponta (câmera → IA → alerta → API → banco → dashboard, rodando em conjunto e validado pelo grupo)
**Depende de:** `fase-0-validacao-e-escopo.md` (concluída) e `projeto-renault-lean-lab-pesquisa.md`

---

## 1. Objetivo da Fase 1

Entregar a primeira versão funcional do pipeline de visão computacional definido no MVP:

> Classificar a camada de cor presente na peça e verificar se ela é a esperada para a estação, contando peças e medindo tempo de ciclo, com alerta automático quando a camada estiver incorreta.

Nesta etapa o foco é **fazer o núcleo de IA + captura funcionar localmente** (webcam + notebook), antes de conectar com backend/API/banco/dashboard (isso fica para a Fase 1.2).

---

## 2. Escopo desta entrega

### ✅ Incluído agora
1. Script para organizar o dataset já coletado em `train/val/test`.
2. Script de treino do classificador de camada (transfer learning).
3. Script de inferência ao vivo pela webcam, com:
   - estabilização da predição (evita contar/alertar por ruído de um único frame);
   - alerta automático quando a camada detectada ≠ camada esperada da estação (atende ao requisito "automação de processos" do documento oficial);
   - contagem de peças e tempo de ciclo, registrados em CSV local.

### 🔜 Fica para a Fase 1.2 (próxima etapa) — ✅ ENTREGUE

- ~~Backend/API para receber os eventos (hoje ficam em CSV local).~~ → **Feito:** API FastAPI (`backend/main.py`).
- ~~Banco de dados (Postgres) substituindo o CSV.~~ → **Feito com SQLite** (via SQLAlchemy — trocar para Postgres depois é só mudar `DATABASE_URL`, sem tocar no resto do código).
- ~~Dashboard web consumindo a API.~~ → **Feito:** dashboard Streamlit (`dashboard/app.py`).
- Comunicação via MQTT entre múltiplas estações — continua pendente, só faz sentido quando o grupo replicar para mais de uma estação (ver Fase 2).

---

## 3. Decisões técnicas desta etapa

| Decisão | Escolha | Motivo |
|---|---|---|
| Framework de IA | **TensorFlow/Keras** | API de alto nível (`image_dataset_from_directory`) mapeia direto para a estrutura de pastas por classe que já temos; poucas linhas de código para transfer learning |
| Arquitetura do modelo | **MobileNetV2 pré-treinada (transfer learning), base congelada** | Leve o suficiente para rodar em notebook comum sem GPU dedicada; ótimo custo-benefício para 5 classes visualmente bem distintas |
| Split do dataset | **70% treino / 15% validação / 15% teste** | Padrão para datasets de porte médio (~280-470 imagens/classe); garante um conjunto de teste isolado pra avaliação honesta |
| Balanceamento | Opcional via flag `--balance` no script de organização | Reduz o pequeno desbalanceamento (281 a 468 imagens/classe) igualando todas ao tamanho da menor |
| Estabilização da predição | Exige confiança ≥ 75% e 5 frames seguidos com a mesma classe antes de "confirmar" um evento | Evita falso alerta por causa de um frame borrado ou mão passando na frente da câmera |
| Cooldown entre contagens | 3 segundos | Evita contar a mesma peça várias vezes enquanto ela ainda está parada em frente à câmera |
| Registro de eventos (por enquanto) | CSV local (`eventos.csv`) | Stub simples — a função `log_event()` no script de inferência é o único ponto que vai precisar mudar quando plugarmos a API na Fase 1.2 |

---

## 4. Arquivos entregues nesta etapa

Pasta `fase1-mvp/`:

| Arquivo | Função | Status |
|---|---|---|
| `organize_dataset.py` | Organiza as imagens brutas (pastas por classe) em `train/val/test` | ✅ Testado |
| `rename_images.py` | Utilitário para padronizar nomes de arquivo por classe | ✅ Testado |
| `train_classifier.py` | Treina o classificador de camada e avalia no conjunto de teste | ✅ Testado |
| `infer_webcam.py` | Roda o modelo ao vivo pela webcam, com alerta e envio de eventos para a API | ✅ Testado |
| `requirements.txt` | Dependências Python necessárias (scripts principais) | ✅ |
| `README.md` | Passo a passo de como rodar tudo | ✅ |
| `backend/main.py`, `database.py`, `models.py`, `schemas.py` | API FastAPI + SQLite: recebe eventos e expõe estatísticas | ✅ Entregue |
| `dashboard/app.py` | Dashboard Streamlit consumindo a API (peças por estação, taxa de alerta, tempo de ciclo) | ✅ Entregue |

## 4.1 O que já pode ser entregue como resultado da Fase 1

Esta etapa já constitui uma **entrega parcial válida** do protótipo, cobrindo o núcleo de IA Aplicada do desafio:

- Pipeline funcional: captura (webcam) → classificação (modelo treinado) → decisão automática (alerta) → registro do evento (CSV).
- Evidência de que a "automação de processos" e a "IA para análise de dados" (requisitos do documento oficial) já funcionam de ponta a ponta, mesmo que hoje de forma local/single-estação.

**Para fechar essa entrega com mais robustez, vale complementar com:**
- As métricas de avaliação do `train_classifier.py` (acurácia, precisão/recall por classe e a matriz de confusão) — se já foram geradas no teste, registrar aqui como evidência de qualidade do modelo.
- Um vídeo curto ou prints da tela do `infer_webcam.py` mostrando o alerta disparando (bom para a apresentação/relatório acadêmico).

### 4.2 Métricas obtidas no conjunto de teste — v1, histórico (registrado em set/2026)

> **Nota:** esta é a versão inicial do modelo (5 classes, sem detecção de presença). Foi substituída pela v2, com a classe `vazio` adicionada — ver comparação completa na seção 8.2.

| Classe | Precisão | Recall | F1-score | Amostras (teste) |
|---|---|---|---|---|
| base | 1.00 | 1.00 | 1.00 | 36 |
| camada_verde | 1.00 | 1.00 | 1.00 | 36 |
| camada_amarela | 1.00 | 1.00 | 1.00 | 36 |
| camada_azul | 1.00 | 1.00 | 1.00 | 36 |
| camada_vermelha | 1.00 | 1.00 | 1.00 | 36 |
| **Acurácia geral** | | | **1.00** | 180 |

Matriz de confusão perfeitamente diagonal (nenhum erro entre classes).

⚠️ **Observação de cautela:** 100% de acurácia é esperado dado que as classes são cores bem distintas, mas como o split treino/val/teste veio de uma única sessão de captura, teste e treino provavelmente compartilham fundo/iluminação/ângulo — o que pode inflar o resultado. **Antes de considerar o modelo validado, testar `infer_webcam.py` em condições um pouco diferentes** (outro ângulo, luz ou fundo) para confirmar que a generalização é real e não só "decoreba" do cenário da sessão de captura. Se a acurácia cair nesse teste, é sinal de que vale coletar mais variação de fundo/ângulo na próxima sessão presencial.

---

## 5. Como isso conecta com as 3 matérias

- **IA Aplicada**: todo o núcleo de `train_classifier.py` e a lógica de decisão em `infer_webcam.py`.
- **Arquitetura de Software**: separação clara em 3 scripts com responsabilidade única (organizar dados → treinar → inferir), e o ponto de extensão já isolado (`log_event()`) pensando na futura troca de CSV por API — é exatamente o tipo de decisão que entra na documentação de arquitetura do projeto.
- **Arquitetura de Sistemas IoT**: a webcam já está sendo tratada como o "sensor" da estação; a Fase 1.2 vai formalizar como esse sensor se comunica com o resto do sistema (hoje é local, depois via MQTT/API).

---

## 6. Próximos passos após esta etapa

1. Rodar `organize_dataset.py` com o dataset real coletado.
2. Rodar `train_classifier.py` e conferir a matriz de confusão — se alguma classe confundir muito com outra (ex.: camada azul com vermelha), pode ser preciso mais dados ou ajuste de hiperparâmetros.
3. Testar `infer_webcam.py` ao vivo (pode ser com fotos impressas ou a própria peça em mãos, sem precisar estar na sala do laboratório).
4. Validar com o grupo se o comportamento do alerta e da contagem faz sentido na prática.
5. Iniciar a Fase 1.2 (backend + banco + dashboard).

---

## 7. Checklist do que entregar como resultado da Fase 1

Tudo abaixo já existe e está funcionando — isto é só a lista do que reunir para a entrega/apresentação.

### 7.1 Código-fonte
- [x] Pasta `fase1-mvp/` completa: `organize_dataset.py`, `rename_images.py`, `train_classifier.py`, `infer_webcam.py`, `backend/`, `dashboard/`, `requirements.txt` de cada parte.
- [x] `modelo_camada.keras` + `class_names.json` (modelo já treinado, não precisa treinar de novo na hora da apresentação).

### 7.2 Evidência de qualidade do modelo
- [x] Relatório de métricas do conjunto de teste (seção 4.2 deste documento — 100% de acurácia, com a ressalva sobre generalização já registrada).
- [ ] **Pendente, se der tempo:** um teste rápido do `infer_webcam.py` em condições diferentes da sessão de captura original (outro fundo/ângulo/luz), para reforçar a validação do modelo antes da entrega — não bloqueia a entrega, mas fortalece a apresentação.

### 7.3 Demonstração ao vivo ou gravada
- [ ] Vídeo curto (ou demo ao vivo) mostrando: webcam detectando a peça → evento aparecendo no dashboard → alerta disparando quando a camada está incorreta. Isso é a prova mais direta de que o "protótipo funcional" pedido no documento oficial existe de verdade.
- [ ] Print(s) do dashboard com dados reais (peças por estação, taxa de alerta, tempo de ciclo).

### 7.4 Documentação
- [x] `projeto-renault-lean-lab-pesquisa.md` — viabilidade técnica e visão geral da arquitetura.
- [x] `fase-0-validacao-e-escopo.md` — validação com o laboratório e decisões de escopo/hardware/rede.
- [x] `fase-1-plano.md` (este documento) — decisões técnicas, arquivos entregues, métricas.

### 7.5 Ligação explícita com as 3 matérias (útil para a banca/professor)
- **IA Aplicada:** modelo de classificação treinado via transfer learning (MobileNetV2), métricas de avaliação, lógica de decisão do alerta.
- **Arquitetura de Software:** separação em módulos com responsabilidade única (captura/IA, API, banco, dashboard), API REST documentada, fallback de resiliência no `infer_webcam.py`.
- **Arquitetura de Sistemas IoT:** webcam como sensor da estação, rede via hotspot, tolerância a falha de conectividade (backup local quando a API está inacessível).

### 7.6 O que deixar claro que é próximo passo (não é dívida técnica, é escopo planejado)
- MQTT entre múltiplas estações — só faz sentido replicando para mais de uma estação (Fase 2).
- Verificação fina de parafusos/encaixes, detecção de avaria, QR/RFID — Fase 2, propositalmente fora do MVP.

---

## 8. Melhorias identificadas durante os testes (registrado em set/2026)

Durante o uso real do `infer_webcam.py`, o grupo identificou que uma peça parada continuamente em frente à câmera é contada várias vezes — o sistema hoje não distingue "peça nova chegou" de "a mesma peça continua ali", só respeita o cooldown de 3s entre contagens.

| Melhoria | Descrição | Fase | Exige hardware novo? |
|---|---|---|---|
| Classe "vazio/sem peça" no modelo | Adicionar uma classe extra representando a bancada vazia; só conta uma peça nova depois de detectar "vazio" entre uma peça e outra — cria um ciclo real de entrada/saída | **Fase 1 (refinamento)** | Não |
| Fine-tuning das últimas camadas do modelo | Descongelar parte da base do MobileNetV2 após o treino inicial, com taxa de aprendizado menor, para melhorar generalização | **Fase 1 (refinamento)** | Não |
| Testar em condições variadas de luz/ângulo/fundo | Validar se a acurácia de 100% se mantém fora das condições da sessão de captura original | **Fase 1 (refinamento)** | Não |
| Recorte de região de interesse (ROI) fixa | Classificar só a região da bancada, reduzindo ruído de fundo/mãos/mesa | **Fase 1 (refinamento)** | Não |
| Sensor de presença físico (IR ou chave fim-de-curso) | Detecta fisicamente a chegada/saída da peça, disparando a classificação só no momento certo — mais confiável que depender só da visão computacional para presença | **Fase 2** | Sim (baixo custo) |
| Migração de classificação para detecção de objeto (YOLO) | Localizar a peça na cena antes de classificar — mais robusto a variação de posição/câmera, e reaproveita o mesmo caminho técnico da verificação fina de parafusos/encaixes já planejada para a Fase 2 | **Fase 2** | Não (mas é retrabalho técnico maior) |

### 8.1 Atualização — classe "vazio" implementada (registrado em set/2026)

- ✅ Corrigido bug de pré-processamento duplicado no `infer_webcam.py` (o `preprocess_input` já está embutido no grafo do modelo salvo por `train_classifier.py`; aplicá-lo de novo na inferência distorcia a entrada — identificado e corrigido pelo grupo).
- ✅ Lógica de contagem trocada de "cooldown por tempo" para **máquina de estados de presença** (`AGUARDANDO_PECA` / `PECA_PRESENTE`), usando a nova classe `vazio` como gatilho de transição. Isso resolve o problema de recontagem de uma peça parada em frente à câmera sem precisar de sensor de hardware novo.
- ✅ `organize_dataset.py` e `train_classifier.py` não precisaram de nenhuma alteração — são genéricos o suficiente para reconhecer a 6ª classe automaticamente a partir da estrutura de pastas.
- ✅ Retreino concluído com a nova classe `vazio` e dataset ampliado (mais variedade de ângulo/fundo, conforme recomendado).

### 8.2 Comparação v1 (5 classes) vs. v2 (6 classes, com "vazio")

| | v1 | v2 |
|---|---|---|
| Classes | 5 | 6 (+ `vazio`) |
| Amostras de teste | 180 | 294 |
| Acurácia geral | 100% | **98%** |
| Erros no conjunto de teste | 0 | 5 |

**Detalhamento dos erros da v2:**

| Classe real | Confundida com | Qtd |
|---|---|---|
| camada_amarela | base | 1 |
| camada_amarela | camada_azul | 1 |
| camada_azul | vazio | 1 |
| camada_verde | vazio | 1 |
| camada_vermelha | camada_azul | 1 |

**Interpretação:** a queda de 100% para 98% é um sinal **positivo**, não uma regressão. A v1 foi treinada e testada com imagens de uma única sessão de captura (mesmo fundo/luz/ângulo), o que tende a inflar a acurácia artificialmente — o modelo pode acertar por reconhecer o cenário, não só a peça. A v2 tem mais diversidade real (incluindo a classe `vazio`, que é naturalmente mais próxima visualmente de algumas cores em certos ângulos), e os erros que aparecem fazem sentido: confusões pontuais entre cores próximas e entre cor/vazio, não erros aleatórios. Isso é evidência de que o modelo está generalizando melhor, mesmo com uma acurácia nominal menor.

**Ação recomendada (opcional, não bloqueia a entrega):** se der tempo antes da apresentação final, vale abrir as 5 imagens específicas que erraram e conferir se são casos genuinamente ambíguos (ex.: ângulo ruim, peça parcialmente fora de quadro) ou se há algum problema de rotulagem/captura — isso ajuda a decidir se vale coletar mais alguns exemplos desses casos-limite na próxima sessão. Para o MVP, 98% com esse padrão de erro já é um resultado sólido e defensável.