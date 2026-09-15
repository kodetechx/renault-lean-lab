# Fase 1 — Implementação do MVP
## Projeto: Digitalização do Lab de Lean Manufacturing — Renault x UniSenai

**Status:** ✅ Fase 1 completa — pipeline ponta-a-ponta funcionando (câmera → IA → alerta → API → banco → dashboard)
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

### 4.2 Métricas obtidas no conjunto de teste (registrado em set/2026)

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