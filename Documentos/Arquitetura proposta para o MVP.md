
---
![](arquitetura_mvp_renault.png)

#### Componentes e responsabilidades

**1. Estação piloto (borda/edge)** — notebook do integrante + webcam apontada para a bancada. Roda um script Python (OpenCV + Ultralytics YOLO) que:

- Detecta a peça base e as 4 peças da camada daquela estação dentro de uma ROI
- Conta quantas das 4 peças esperadas foram encaixadas, e se os parafusos foram colocados
- Lê o QR code (se usado) para identificar a peça
- Marca timestamp de início/fim → calcula tempo de ciclo
- Empacota tudo num JSON simples: `{station_id, layer_color, pieces_detected, pieces_expected, screws_ok, status, part_id, cycle_time_s, timestamp}`

Essa lógica é **reaproveitável entre estações** — só troca o conjunto de classes (cor da camada). Isso já demonstra escalabilidade sem redesenho, sem precisar rodar em 10 estações ao vivo.

**2. Broker MQTT (Mosquitto)** — recebe o JSON de cada estação publicado por tópico (ex.: `lab/estacao/1/evento`) e roteia para quem está inscrito. Sem autenticação/TLS no MVP — isso seria complexidade sem retorno agora.

**3. Backend (FastAPI)** — se inscreve no broker, valida o payload e grava no banco. Expõe endpoints REST (`GET /eventos`, `GET /estacoes/{id}/resumo`) para o dashboard consumir. Estrutura em camadas: rotas (apresentação) → regras de negócio (cálculo de métricas) → persistência (SQLAlchemy).

**4. Banco de dados** — recomendo SQLite nos primeiros meses, migrando para PostgreSQL só quando houver múltiplas estações escrevendo simultaneamente (conforme a ressalva que fiz acima). Tabelas essenciais: `estacoes`, `eventos`, `pecas` (se usar QR).

**5. Dashboard (React + Recharts)** — consome a API REST e mostra: peças produzidas por estação, tempo médio de ciclo, status recente (OK/NG), lista de últimos eventos.

**6. Nuvem** — papel deliberadamente pequeno: hospedar só backend + dashboard (dados já estruturados) num free tier, para demonstrar acesso remoto. **Vídeo e imagem bruta nunca saem da estação** — isso atende diretamente à exigência de proteção de dados da Renault, e evita montar uma infraestrutura de nuvem elaborada só para "usar a disciplina".

**7. IA** — aparece em dois pontos: (a) na borda, o YOLO fazendo detecção/contagem (núcleo do MVP); (b) opcionalmente, sobre os dados já estruturados no banco, uma análise simples de tendência (ex.: taxa de defeito por turno) — isso é "could have", não bloqueia a demonstração de viabilidade.

**Fluxo de dados**, de ponta a ponta: câmera capta vídeo → script local detecta/conta/mede tempo → publica JSON via MQTT → broker roteia → backend valida e grava → dashboard consulta via REST e exibe.

---
### Item 5 — Divisão do desenvolvimento em etapas (6 meses)

#### Visão geral por mês

|Mês|Foco principal|
|---|---|
|1|Descoberta, requisitos e coleta de dataset|
|2|Arquitetura, setup técnico e baseline do modelo|
|3|Desenvolvimento do núcleo do MVP|
|4|Integração na estação real do laboratório|
|5|Validação, refinamento e (se sobrar tempo) 2ª estação|
|6|Preparação da demonstração, documentação e apresentação|

#### Fase 0 — Descoberta e definição (semanas 1-2)

- **Objetivo:** transformar a pesquisa já feita em um plano validado e começar a coletar matéria-prima do dataset.
- **Tarefas principais:** agendar sessão de fotos/vídeos no laboratório (todas as camadas da peça); confirmar nome/identificação formal da peça e componentes com a Renault; validar o MVP e a arquitetura com o professor orientador; criar repositório Git e board de tarefas (Trello/GitHub Projects).
- **Resultado esperado:** dataset bruto inicial (fotos/vídeos) coletado; repositório e ferramentas de gestão criados.
- **Dependências:** acesso ao laboratório (já confirmado).
- **Responsável sugerido:** todo o grupo participa da sessão de fotos; 1-2 pessoas cuidam da organização do repositório.

#### Fase 1 — Requisitos e dataset anotado (semanas 3-4)

- **Objetivo:** ter um dataset utilizável e requisitos técnicos escritos.
- **Tarefas principais:** anotar imagens no Roboflow ou CVAT (classes: peça base, as 4 peças de cada camada, parafusos); escrever requisitos funcionais/não funcionais; desenhar o schema inicial dos dados de evento (o JSON que cada estação vai gerar).
- **Resultado esperado:** dataset anotado v1; documento de requisitos; schema de dados definido.
- **Dependências:** fotos da Fase 0.
- **Responsável sugerido:** dupla focada em IA cuida da anotação; 1 pessoa modela o schema de dados (ponte com Arquitetura de Software).

#### Fase 2 — Arquitetura e setup técnico (semanas 5-6)

- **Objetivo:** montar o esqueleto do sistema, mesmo que com dados fictícios.
- **Tarefas principais:** estruturar o repositório (monólito modular); subir o broker MQTT localmente via Docker; criar esqueleto do backend FastAPI (rotas + conexão SQLite); criar esqueleto do projeto React; treinar uma primeira versão baseline do YOLO (mesmo que fraca).
- **Resultado esperado:** um evento fictício conseguindo percorrer o caminho inteiro — script → MQTT → backend → banco → algo aparecendo no dashboard. Isso é o "hello world" da arquitetura.
- **Dependências:** dataset anotado da Fase 1 (só para começar o treino).
- **Responsável sugerido:** cada componente (borda, MQTT, backend, dashboard) tem um "dono temporário" nesta fase — a rotação real de responsabilidades entra no item 6.

> **⚠️ Marco de decisão:** ao final da Fase 2 (~6 semanas), se o "hello world" ponta a ponta não estiver funcionando, é sinal de alerta cedo — melhor simplificar agora (por exemplo, trocar MQTT por REST puro temporariamente) do que descobrir isso no mês 4.

#### Fase 3 — Desenvolvimento do núcleo do MVP (semanas 7-12 / meses 2-3)

- **Objetivo:** sair do "hello world" para a lógica real do produto.
- **Tarefas principais:** treinar e validar o modelo YOLO com o dataset completo (medir acerto de contagem); implementar a lógica de contagem de peças/parafusos na ROI; implementar cálculo de tempo de ciclo; implementar leitura de QR Code (se ainda estiver no escopo do MVP); finalizar endpoints reais do backend; dashboard exibindo métricas reais (não mais mockadas).
- **Resultado esperado:** pipeline funcional em ambiente controlado (mesa de testes fora da estação real), com dados de verdade, não fictícios.
- **Dependências:** esqueleto da Fase 2.
- **Responsável sugerido:** sub-times por componente, com encontros semanais de sincronização para todos entenderem o todo (evitar silos).

> **⚠️ Marco de decisão:** este é o bloco mais longo (6 semanas) porque é o mais arriscado tecnicamente. Se em meados da Fase 3 perceberem que alguma parte (ex.: detecção de parafuso, ou leitura de QR) está consumindo tempo desproporcional, cortem — isso é exatamente o tipo de funcionalidade que pode virar "Won't Have" sem comprometer a prova de viabilidade.

#### Fase 4 — Integração na estação real (semanas 13-16 / mês 4)

- **Objetivo:** sair do ambiente de testes e rodar no laboratório de verdade.
- **Tarefas principais:** instalar câmera/notebook na estação real; ajustar ROI, iluminação e ângulo com a peça de verdade; testar ciclos repetidos; corrigir bugs de integração (rede, timeouts, falsos positivos/negativos).
- **Resultado esperado:** pipeline completo rodando na estação real, com dados aparecendo no dashboard a partir do ambiente do laboratório.
- **Dependências:** MVP funcional da Fase 3.
- **Responsável sugerido:** todo o grupo presente fisicamente pelo menos uma vez — essa é a fase mais importante para todos entenderem o sistema como um todo, não só quem programou a IA.

#### Fase 5 — Validação e refinamento (semanas 17-19 / início do mês 5)

- **Objetivo:** confirmar que o sistema resolve o problema, com feedback de quem importa.
- **Tarefas principais:** apresentar o protótipo funcionando ao padrinho do desafio (Sidnei Santos) e ao professor orientador; refinar usabilidade do dashboard; corrigir falsos positivos/negativos do modelo se necessário; **se e somente se houver tempo sobrando**, tentar replicar em uma 2ª estação para reforçar a narrativa de escalabilidade.
- **Resultado esperado:** versão "candidata à demonstração final", com feedback já incorporado.
- **Dependências:** Fase 4 concluída.
- **Responsável sugerido:** todo o grupo.

#### Fase 6 — Preparação da demonstração (semanas 20-22 / fim do mês 5 - início do mês 6)

- **Objetivo:** garantir uma demonstração confiável, mesmo que algo falhe ao vivo.
- **Tarefas principais:** gravar um vídeo de backup da demo funcionando; escrever roteiro de apresentação; ensaiar a demo repetidas vezes em condições reais; preparar slides/material de apoio.
- **Resultado esperado:** demo testada e resiliente, material de apresentação pronto.
- **Dependências:** Fase 5.
- **Responsável sugerido:** todo o grupo, com 1-2 pessoas liderando a condução da apresentação.

#### Fase 7 — Documentação final e apresentação (semanas 23-26 / mês 6)

- **Objetivo:** consolidar e entregar.
- **Tarefas principais:** documentação técnica (arquitetura, decisões tomadas e por quê, como rodar o projeto); documentação de limitações conhecidas e evoluções futuras; ensaio final; apresentação para a Renault/banca.
- **Resultado esperado:** projeto entregue, documentado e apresentado.
- **Dependências:** Fase 6.
- **Responsável sugerido:** todo o grupo.