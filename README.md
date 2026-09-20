# Renault Lean Lab — Digitalização do Laboratório de Lean Manufacturing

Projeto acadêmico do **UniSenai** em parceria com a **Renault**, integrando as disciplinas de **Arquitetura de Software**, **IA Aplicada** e **Arquitetura de Sistemas IoT**.

A sala de treinamento da Renault no UniSenai tem 5 estações de montagem e 5 de reciclagem/desmontagem de uma mesma peça, hoje operadas de forma manual e registradas em papel. O projeto digitaliza esse processo com **visão computacional**: uma câmera em cada estação verifica se a peça montada tem a camada correta para aquela estação, conta as peças, mede o tempo de ciclo, dispara alerta em caso de erro e envia tudo para um dashboard.

> ⚠️ **Confidencialidade:** a sala, o processo e as imagens são de uso restrito a fins acadêmicos e à Renault. Veja [`Documentos/fase-0-validacao-e-escopo.md`](Documentos/fase-0-validacao-e-escopo.md) (seções 2.4 e 4.3) antes de compartilhar qualquer imagem, vídeo ou dado deste projeto.

**Atualizado em:** 20/09/2026

## Índice

1. [Onde o projeto está hoje](#1-onde-o-projeto-está-hoje)
2. [O que já foi feito](#2-o-que-já-foi-feito)
3. [Arquitetura](#3-arquitetura)
4. [Próximas etapas e fases futuras](#4-próximas-etapas-e-fases-futuras)
5. [Estrutura do repositório](#5-estrutura-do-repositório)
6. [Como rodar](#6-como-rodar)
7. [Mapa da documentação](#7-mapa-da-documentação)

---

## 1. Onde o projeto está hoje

| Fase | O que é | Status | Documento |
|------|---------|--------|-----------|
| **0** | Validação com o laboratório, escopo do MVP e coleta do dataset | ✅ Concluída | [`fase-0-validacao-e-escopo.md`](Documentos/fase-0-validacao-e-escopo.md) |
| **1** | MVP: classificação da camada (MobileNetV2) + API + banco + dashboard | ✅ Concluída e testada de ponta a ponta | [`fase-1-plano.md`](Documentos/fase-1-plano.md) |
| **2** | Detecção de objetos (YOLO) para peça inteira + contagem de parafusos | 🟢 Em andamento — pipeline validado; falta dado de parafuso | [`fase-2-plano.md`](Documentos/fase-2-plano.md) |
| Futuras | Avaria/anomalia, QR/RFID, várias estações + MQTT, hardware dedicado | ⏳ Planejadas | [seção 4](#4-próximas-etapas-e-fases-futuras) |

## 2. O que já foi feito

### Fase 0 — Validação e escopo
Detalhes em [`fase-0-validacao-e-escopo.md`](Documentos/fase-0-validacao-e-escopo.md).

- Premissas confirmadas com o laboratório: rede (Wi-Fi compartilhado → **hotspot de celular** como rede isolada do protótipo), fixação de câmera permitida, acesso à peça, e captura de imagens **só presencial, às terças das 19h às 22h**.
- Escopo do MVP fechado em torno do pedido do laboratório: verificar se a **camada de cor** da peça é a esperada para a estação (estação 1 verde, 2 amarela, 3 azul, 4 vermelha) — não detecção de avaria.
- Hardware inicial decidido: **webcam + notebook** (custo zero de hardware novo).
- Primeira coleta: **1.783 imagens** de peça montada (base, verde, amarela, azul, vermelha), muito acima da meta inicial.

### Fase 1 — MVP de classificação
Detalhes em [`fase-1-plano.md`](Documentos/fase-1-plano.md) · código e passo a passo em [`Programa/fase1-mvp/`](Programa/fase1-mvp/README.md).

- **Modelo:** classificador de camada com MobileNetV2 (transfer learning). A v1 (5 classes) atingiu 100% no teste; a v2, com a classe `vazio` (6 classes), 98% — uma queda esperada, pois a v2 tem mais variedade de fundo e ângulo (comparação na seção 8.2 do plano).
- **Inferência ao vivo pela webcam** com estabilização (confiança mínima e frames consecutivos), alerta em tela quando a camada é a errada, contagem de peças e tempo de ciclo. A contagem usa uma máquina de estados de presença (`AGUARDANDO_PECA` / `PECA_PRESENTE`) em vez de cooldown por tempo.
- **Backend** FastAPI + SQLite (via SQLAlchemy, então trocar para PostgreSQL é só mudar `DATABASE_URL`) e **dashboard** Streamlit, com backup em CSV local quando a API está inacessível.
- **Bug corrigido:** o pré-processamento do MobileNetV2 estava aplicado duas vezes na inferência, o que fazia o modelo classificar tudo como `base`.
- **Decisão registrada:** manter o MobileNetV2 na Fase 1 e migrar para YOLO na Fase 2 (seção 9 do plano).

### Fase 2 — Detecção com YOLO (em andamento)
Detalhes e histórico de decisão em [`fase-2-plano.md`](Documentos/fase-2-plano.md) · código e passo a passo em [`Programa/fase2-mvp/`](Programa/fase2-mvp/README.md).

- **Por que YOLO:** o classificador dá um rótulo por frame, então não lida com mais de uma peça na bancada nem conta componentes pequenos. Com detecção, a ausência de caixas já significa "vazio" e a classe `vazio` deixa de ser necessária.
- **Pipeline ponta a ponta validado:** anotação no CVAT → `build_yolo_dataset.py` → `train_yolo.py` → inferência ao vivo. Primeiro treino com ~1.001 imagens (`yolo11n`): mAP50 geral ≈ 0,995 para as camadas, e a detecção da peça por cor funciona ao vivo na webcam.
- **Contagem de parafusos ainda não é confiável:** há apenas 2 instâncias anotadas. O número de `parafuso` no relatório do treino deve ser desconsiderado.
- **Backend e dashboard da Fase 2**, com contagem de parafusos detectados × esperados e alertas separados por tipo (camada incorreta × parafusos insuficientes).

## 3. Arquitetura

Fluxo implementado hoje (tudo no notebook do grupo, em rede local):

```
Webcam ──► Script Python (OpenCV + modelo) ──► API FastAPI ──► SQLite ──► Dashboard Streamlit
            │ detecta/classifica a camada      │ valida e grava
            │ conta peças e mede o ciclo       │ /eventos  /estatisticas
            └─ se a API cair: backup em CSV
```

- **Imagem e vídeo nunca saem da estação** — só o evento (JSON) trafega, atendendo à exigência de proteção de dados da Renault.
- A separação em camadas isolou as migrações: trocar MobileNetV2 por YOLO mudou o script de inferência e o conteúdo do evento, mas não a estrutura da API/banco/dashboard.
- A proposta original de arquitetura (com broker **MQTT**, dashboard em React e roadmap de 6 meses) está em [`Arquitetura proposta para o MVP.md`](Documentos/Arquitetura%20proposta%20para%20o%20MVP.md); a viabilidade técnica e a escolha de tecnologias, em [`projeto-renault-lean-lab-pesquisa.md`](Documentos/projeto-renault-lean-lab-pesquisa.md). O protótipo atual usa HTTP/REST direto; o MQTT entra quando houver mais de uma estação.

## 4. Próximas etapas e fases futuras

### Pendências da Fase 2 (em ordem de impacto)
Checklist completo na seção 8 de [`fase-2-plano.md`](Documentos/fase-2-plano.md).

1. **Confirmar com a Renault a quantidade de parafusos esperada por estação** (a "receita" que vira a regra de completude) e se os parafusos são visualmente uniformes.
2. **Sessão de captura dedicada de parafusos** (isolados e encaixados na peça) — bloqueia a contagem.
3. **Retreinar** com o dataset de parafuso e validar de novo.
4. **Testar com várias peças de cores diferentes no quadro** — o cenário que motivou o YOLO ainda não foi formalmente testado (risco descrito na seção 3.3 do plano).
5. **Anotar o lote 2** (restante das 1.783 imagens) e, se preciso, capturar imagens com múltiplas peças.

### Fases futuras
Itens deliberadamente fora do MVP atual (seção 7 de [`fase-2-plano.md`](Documentos/fase-2-plano.md) e seção 3 de [`fase-0-validacao-e-escopo.md`](Documentos/fase-0-validacao-e-escopo.md)):

- **Detecção de avaria/anomalia** — exige dataset de peças defeituosas, ainda não coletado (abordagens em [`projeto-renault-lean-lab-pesquisa.md`](Documentos/projeto-renault-lean-lab-pesquisa.md), seção 3.5).
- **Identificação por QR Code ou RFID** — saber *qual* peça foi produzida, não só em qual estação.
- **Replicação para as demais estações** (incluindo as de reciclagem/desmontagem) e **MQTT** entre elas.
- **Hardware dedicado** (ex.: Raspberry Pi por estação) e, opcionalmente, sensor físico de presença — comparativo de opções na seção 5 da pesquisa.
- **IA sobre os dados já gravados** — tendências por estação/turno e resumos automáticos de turno (seção 9 da pesquisa).
- **Entrega final:** integração na estação real, validação com o laboratório, demonstração e documentação — etapas 4 a 7 do roadmap em [`Arquitetura proposta para o MVP.md`](Documentos/Arquitetura%20proposta%20para%20o%20MVP.md). Atenção: esse roadmap numera as fases de outra forma (Fase 0 a 7 em 6 meses) que a usada nos documentos `fase-N-*.md`.

Itens de entrega da Fase 1 ainda em aberto: vídeo/demo ao vivo e prints do dashboard com dados reais (seção 7 de [`fase-1-plano.md`](Documentos/fase-1-plano.md)).

## 5. Estrutura do repositório

```
renault-lean-lab/
├── README.md                         # este arquivo
├── Documentos/
│   ├── projeto-renault-lean-lab-pesquisa.md
│   ├── fase-0-validacao-e-escopo.md
│   ├── fase-1-plano.md
│   ├── fase-2-plano.md
│   └── Arquitetura proposta para o MVP.md
└── Programa/
    ├── fase1-mvp/                    # classificação (MobileNetV2) + backend + dashboard
    └── fase2-mvp/                    # detecção (YOLO) + backend + dashboard
```

Não são versionados (`.gitignore`): ambientes virtuais, fotos brutas (`raw_images/`, `Imagens/`), datasets gerados, exports do CVAT, bancos `*.db` e pesos base do YOLO. Eles precisam existir localmente para refazer o treino.

## 6. Como rodar

Cada fase tem seu próprio passo a passo — comece por eles:

| Fase | README | Componentes |
|------|--------|-------------|
| 1 | [`Programa/fase1-mvp/README.md`](Programa/fase1-mvp/README.md) | organizar dataset → treinar → backend → dashboard → inferência pela webcam |
| 2 | [`Programa/fase2-mvp/README.md`](Programa/fase2-mvp/README.md) | montar dataset YOLO → treinar → backend → dashboard → inferência pela webcam |

Requisitos gerais: Python 3 e uma webcam. Os backends das duas fases usam a porta 8000 por padrão — rode um de cada vez. Os modelos já treinados versionados são `Programa/fase1-mvp/modelo_camada.keras` e o `best.pt` em `Programa/fase2-mvp/runs_yolo/lean_lab_v1/weights/`.

## 7. Mapa da documentação

| Documento | Para que serve | Leia quando... |
|-----------|----------------|----------------|
| [`projeto-renault-lean-lab-pesquisa.md`](Documentos/projeto-renault-lean-lab-pesquisa.md) | Viabilidade técnica, tecnologias, hardware e visão geral da arquitetura | quiser entender *por que* as tecnologias foram escolhidas |
| [`Arquitetura proposta para o MVP.md`](Documentos/Arquitetura%20proposta%20para%20o%20MVP.md) | Componentes da arquitetura e roadmap de 6 meses | quiser ver a visão de longo prazo (MQTT, React, cronograma) |
| [`fase-0-validacao-e-escopo.md`](Documentos/fase-0-validacao-e-escopo.md) | Respostas do laboratório, escopo do MVP, coleta do dataset, confidencialidade | precisar do contexto e das restrições do laboratório |
| [`fase-1-plano.md`](Documentos/fase-1-plano.md) | Decisões, arquivos, métricas v1/v2 e checklist de entrega do MVP | precisar do detalhe do que foi entregue na Fase 1 |
| [`fase-2-plano.md`](Documentos/fase-2-plano.md) | Decisão pelo YOLO, resultados do primeiro treino, riscos e checklist | for trabalhar na Fase 2 ou planejar os próximos passos |
| [`Programa/fase1-mvp/README.md`](Programa/fase1-mvp/README.md) | Como rodar o código da Fase 1 | for executar a Fase 1 |
| [`Programa/fase2-mvp/README.md`](Programa/fase2-mvp/README.md) | Como rodar o código da Fase 2 | for executar a Fase 2 |

Ordem sugerida para quem chega agora: pesquisa → Fase 0 → Fase 1 → Fase 2.
