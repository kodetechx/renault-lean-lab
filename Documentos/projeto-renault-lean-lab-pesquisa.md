# Digitalização do Laboratório de Lean Manufacturing — Renault x UniSenai
## Documento de Pesquisa e Organização de Ideias

**Disciplinas integradas:** Arquitetura de Software · IA Aplicada · Arquitetura de Sistemas IoT
**Status:** Rascunho de pesquisa — v0.1
**Última atualização:** 26/08/2026

---

## 1. Objetivo deste documento

Organizar, antes de qualquer decisão de implementação, o que é **tecnicamente viável**, **o que cada matéria contribui** e **quais tecnologias/hardwares** permitem construir um protótipo funcional com o máximo de trabalho feito pelos próprios alunos (código, integração, dashboards) e o mínimo de dependência de compras (idealmente só o hardware físico de captura/identificação).

Este documento **não é a arquitetura final** — é a base de pesquisa para decidirmos, em seguida, o escopo do MVP.

---

## 2. Contexto resumido

- Sala de treinamento da Renault no UniSenai.
- **5 estações de montagem** (montam a peça).
- **5 estações de reciclagem/desmontagem** (desmontam a mesma peça).
- Processos hoje são manuais, em papel, sem dados centralizados.
- Objetivo: digitalizar, rastrear, centralizar e permitir análise dos dados de produção.

---

## 3. Viabilidade de Visão Computacional — ponto a ponto

A ideia central é usar **uma câmera por estação** (ou uma câmera compartilhada/móvel no protótipo, dependendo do orçamento) apontada para a bancada, processando o vídeo com um modelo de **detecção de objetos** treinado especificamente nas peças da Renault.

### 3.1 Montagem correta da peça (peças corretas, nº de parafusos, encaixes)
**Viável.** É um problema clássico de **detecção de objetos + contagem de classes** dentro de uma região de interesse (ROI):
- Treina-se um modelo para reconhecer cada componente da peça (base, encaixes, parafusos, etc.) como classes distintas.
- Para cada classe "obrigatória" (ex.: parafuso), o sistema conta quantas instâncias foram detectadas na peça finalizada e compara com o número esperado (regra de negócio simples, não precisa de IA para essa parte — é lógica determinística em cima da saída do modelo).
- Encaixes podem ser validados por **posição relativa** (o modelo detecta a peça B dentro da bounding box esperada da peça A) ou por um segundo modelo de classificação "montagem OK / montagem NG" treinado com fotos de montagens corretas e incorretas.
- **Nível de dificuldade:** médio. Depende principalmente da qualidade e volume do dataset de treino (fotos da peça em várias etapas de montagem, ângulos e condições de luz).

### 3.2 Contar peças montadas por estação
**Viável e é o caso de uso mais simples.**
- Basta detectar o evento "peça completa apareceu na área de entrega/saída da bancada" e contar.
- Técnicas possíveis: detecção de objeto + lógica de "linha de contagem" (a peça cruza uma linha virtual = +1), ou um sensor complementar (ver seção IoT) confirmando o evento para reduzir falso positivo.
- Pode ser combinado com QR Code/RFID (seção 5) para também saber **qual peça específica** foi produzida, não só a contagem.

### 3.3 Enviar todos os dados para um dashboard
**Viável** — é puramente engenharia de software/arquitetura, não depende de pesquisa de viabilidade:
- Cada estação (script de visão computacional) publica eventos (JSON) via API REST ou mensageria (MQTT) para um backend central.
- Backend grava em banco de dados e expõe os dados para um front-end de dashboard.
- Esse é exatamente o ponto onde **Arquitetura de Software** e **Arquitetura de Sistemas IoT** se conectam (ver seção 6).

### 3.4 Tempo de montagem por estação
**Viável.**
- Marca-se o timestamp do primeiro evento relevante (ex.: primeira peça-base detectada na bancada) e o timestamp de conclusão (peça completa detectada/contada).
- A diferença é o tempo de ciclo daquela unidade naquela estação.
- Pode ser enriquecido futuramente com detecção de "parada"/"peça parada sem atividade" para métricas de eficiência (ex.: um proto-OEE).

### 3.5 Detecção de anomalias na peça (avarias, quebras, etc.)
**Viável, com duas abordagens possíveis (do mais simples ao mais robusto):**

1. **Classificação binária "OK / defeito"** com um modelo treinado em cima de fotos de peças boas e peças com defeito (abordagem supervisionada clássica, exige dataset com exemplos de defeito).
2. **Detecção de anomalias não supervisionada** (ex.: *anomaly detection* / autoencoders, ou modelos "one-class" que aprendem apenas o padrão "normal" e sinalizam qualquer desvio). É a abordagem usada em inspeção industrial quando **exemplos de defeito são raros**, o que provavelmente será o caso aqui (é difícil ter muitas fotos de peça quebrada de propósito).
- Literatura recente confirma esse tipo de aplicação: pesquisas de 2025/2026 aplicam justamente modelos YOLO em detecção de defeitos de superfície em peças industriais, incluindo em dispositivos de borda (edge), com resultados de acurácia acima de 85-90% em datasets de referência.
- **Nível de dificuldade:** o mais alto dos cinco pontos. Recomenda-se deixar como "fase 2" do projeto, começando pelo item 3.1/3.2/3.4 no MVP.

### Conclusão da seção 3
Todos os 5 pontos são **tecnicamente viáveis** com ferramentas gratuitas e open-source. O fator limitante não é a tecnologia, e sim **volume e qualidade do dataset de imagens** que conseguirmos capturar das peças da Renault (por isso vale já perguntar ao laboratório se podemos fotografar/filmar as peças em diferentes estágios).

---

## 4. Modelos e frameworks de IA/Visão Computacional recomendados

| Necessidade | Ferramenta recomendada | Por quê |
|---|---|---|
| Detecção de objetos (peças, parafusos, encaixes) | **YOLO (Ultralytics)** — hoje a geração mais recente é a **YOLO26** (lançada em jan/2026), otimizada para inferência em CPU/edge e sem NMS; **YOLOv11** também é uma opção madura e muito documentada | Framework open-source, treina com poucas centenas de imagens por classe, roda em tempo real até em Raspberry Pi |
| Contagem por linha/zona | Lógica de *tracking* simples (ex.: **ByteTrack**, incluído no Ultralytics) sobre a saída do YOLO | Evita contar a mesma peça duas vezes |
| Classificação OK/NG | Modelo de classificação leve (ex.: **MobileNetV3**, ou até um classificador simples via *transfer learning*) | Rápido de treinar, roda em hardware barato |
| Detecção de anomalia sem muitos exemplos de defeito | Bibliotecas de *anomaly detection* visual, como **Anomalib** (Intel/OpenVINO) | Pensada exatamente para "poucos exemplos de defeito, muitos exemplos normais" |
| Treino/anotação de dataset | **Roboflow** (gratuito para uso educacional/pequena escala) ou **CVAT** (open-source, self-hosted) | Facilita anotar as fotos das peças e já exporta no formato certo para treinar YOLO |

> **Observação importante sobre licença:** as versões mais recentes do YOLO (YOLOv12/YOLO26 via Ultralytics) usam licença **AGPL-3.0**, que é gratuita para uso acadêmico/protótipo, mas exige atenção se depois quisermos algo "fechado" comercialmente. Para um projeto de faculdade isso não é um problema.

---

## 5. IoT: hardware necessário

### 5.1 O que a solução de IoT precisa capturar, no mínimo
- Imagem de vídeo contínua de cada bancada (para a visão computacional).
- Identificação de qual peça está sendo montada/desmontada (QR Code ou RFID).
- Opcionalmente: sensores complementares (ex.: sensor de presença/fim de curso para confirmar "peça chegou/saiu" sem depender 100% da câmera).

### 5.2 Opções de hardware "cérebro" da estação (onde a IA roda)

| Opção | Custo aproximado | Poder de processamento | Quando usar |
|---|---|---|---|
| **ESP32-CAM** | Muito baixo (~US$ 10) | Baixíssimo — não roda YOLO localmente, só captura imagem e envia para processamento em outro lugar | Só como câmera "burra" + envio de frames via Wi-Fi, se o processamento for centralizado em um PC/servidor |
| **Raspberry Pi 5 (4-8GB) + Câmera oficial** | Moderado — a placa 8GB gira em torno de US$ 80, mais a câmera (~US$ 25-35) | Roda modelos YOLO leves (ex.: YOLO-Nano) em tempo real com desempenho aceitável, principalmente com o **Raspberry Pi AI HAT+** (acelerador de IA opcional que pode ser acoplado) | **Melhor custo-benefício para o protótipo** — 1 unidade por estação já cobre visão + lógica local |
| **NVIDIA Jetson Orin Nano Super** | Alto — atualmente em torno de US$ 399 no site oficial (o preço subiu bastante em 2026; chegou a ser vendido por US$ 249 no lançamento) | Muito superior (até 67 TOPS), roda modelos maiores e múltiplos modelos ao mesmo tempo | Only se quisermos **uma estação "referência" mais robusta** para provar o conceito de detecção de anomalia mais pesada; não é necessário nas 10 estações |
| **PC/notebook + webcam USB comum** | Custo zero se já houver equipamento disponível no laboratório | Alto (depende do PC) | **Opção mais barata de todas para o protótipo inicial**: uma única estação de teste, processando localmente em um notebook, antes de investir em hardware dedicado |

**Recomendação para o MVP (restrição de baixo custo):** começar com **1-2 estações piloto** usando **webcam comum + notebook/Raspberry Pi 5**, provar o conceito de detecção/contagem/dashboard, e só depois avaliar replicar para as 10 estações com Raspberry Pi 5 (que é hoje a opção mais equilibrada entre custo e capacidade de rodar IA localmente).

### 5.3 Identificação de peças/estações

| Tecnologia | Custo | Prós | Contras |
|---|---|---|---|
| **QR Code impresso** | Praticamente zero (só impressão) | Fácil de gerar e alterar, leitura pela própria câmera já usada para visão computacional (sem hardware extra) | Pode ser danificado/sujo na linha; precisa estar sempre visível |
| **RFID (módulo RC522 ou similar)** | Baixo (~US$ 3-5 por leitor + tags) | Não depende de estar visível/limpo, leitura mais robusta em ambiente industrial | Precisa de hardware extra (leitor + antena) por estação, mais um pouco de eletrônica/fiação |
| **Sensor infravermelho / chave fim-de-curso** | Muito baixo | Ótimo para confirmar "peça entrou/saiu" sem processamento de imagem | Não identifica *qual* peça, só detecta presença |

**Recomendação:** usar **QR Code** no MVP (zero custo extra, aproveita a câmera já instalada) e deixar **RFID como evolução futura** para ambientes onde o código pode ficar sujo/oculto — atende à restrição de "priorizar soluções de baixo custo".

---

## 6. Arquitetura da solução — como as 3 matérias se conectam

```
[Estação de montagem/reciclagem]
   Câmera + (QR/RFID opcional)
        |
        v
[Módulo de Visão Computacional / Edge]   <-- IA Aplicada
   - Detecção de peças/parafusos (YOLO)
   - Contagem por evento
   - Classificação OK/NG ou anomalia
   - Empacota o resultado em JSON
        |
        v  (MQTT ou HTTP/REST)
[Gateway / Broker de mensagens]          <-- Arquitetura de Sistemas IoT
   - Recebe eventos de todas as estações
   - Roteia para o backend
        |
        v
[Backend / API]                          <-- Arquitetura de Software
   - Valida, processa, grava no banco
   - Expõe endpoints REST para o dashboard
   - Camadas: apresentação / regras de negócio / persistência
        |
        v
[Banco de Dados]                         <-- Arquitetura de Software
   - Histórico de eventos, contagens, tempos, status
        |
        v
[Dashboard Web]                          <-- Arquitetura de Software + IA Aplicada (insights)
   - Peças produzidas por estação/turno
   - Tempo médio de ciclo
   - Taxa de defeito/anomalia
   - Alertas em tempo real
```

- **Arquitetura de Sistemas IoT**: define como os dispositivos de borda (câmeras/Raspberry Pi/sensores) se comunicam com o restante do sistema — protocolo (MQTT é o padrão de fato em IoT industrial, leve e baseado em publish/subscribe), topologia de rede, tolerância a falhas (o que acontece se a estação perder conexão), segurança da comunicação.
- **IA Aplicada**: cobre o modelo de visão computacional em si (treinamento, inferência, anomaly detection) e pode também aparecer no backend, aplicando IA sobre os dados já estruturados (ex.: prever quando uma estação tende a gerar mais peças com defeito, ou normalizar/limpar dados usando um modelo de linguagem para gerar resumos automáticos de turno).
- **Arquitetura de Software**: define como o sistema é dividido em módulos/serviços (monólito simples vs. microsserviços — para um protótipo de faculdade, um monólito modular bem organizado é mais que suficiente), o design da API, o modelo de dados e o próprio dashboard.

---

## 7. Linguagens e frameworks sugeridos (o que os alunos programam)

| Camada | Linguagem/Stack sugerida | Justificativa |
|---|---|---|
| Visão computacional / IA | **Python** + Ultralytics YOLO + OpenCV | Linguagem padrão do ecossistema de IA/visão, maior quantidade de tutoriais e bibliotecas prontas |
| Comunicação IoT | **MQTT** (broker **Mosquitto**, open-source) + biblioteca `paho-mqtt` (Python) | Protocolo leve, ideal para muitos dispositivos pequenos enviando eventos curtos |
| Backend / API | **Python (FastAPI)** ou **Node.js (Express)** | Ambas gratuitas, produtivas, e times de eng. de software costumam já ter familiaridade; FastAPI tem vantagem de ficar na mesma linguagem da parte de IA |
| Banco de dados | **PostgreSQL** (relacional, robusto, gratuito) — ou **SQLite** só para protótipo inicial sem infraestrutura de servidor | Gratuito, roda local, escala bem se o projeto crescer |
| Dashboard | **React** (front-end) consumindo a API, com biblioteca de gráficos como **Recharts** ou **Chart.js**; alternativa mais rápida de prototipar: **Streamlit** (Python) para uma primeira versão | React dá um resultado mais profissional; Streamlit é mais rápido para provar o conceito com poucas linhas de código |
| Identificação (QR) | Biblioteca `pyzbar` ou `opencv` (leitura) + `qrcode` (geração), ambas em Python | Reaproveita a mesma stack de visão computacional |

Com essa stack, **100% do software é escrito pelos alunos** — Python, MQTT, FastAPI/Node, PostgreSQL e React/Streamlit são todos gratuitos e open-source. O único investimento necessário é o **hardware físico** (câmera, Raspberry Pi, e opcionalmente RFID), conforme pedido no desafio.

---

## 8. Como a Visão Computacional/IA automatiza a captura de dados na linha

Hoje, a captura é manual (papel). A proposta substitui isso por:

1. **Captura automática de eventos**: a câmera, rodando o modelo continuamente, detecta sozinha quando uma peça é iniciada, concluída, ou apresenta um problema — sem que o operador precise anotar nada.
2. **Geração automática de metadados**: cada evento já sai com timestamp, estação de origem, status (OK/NG), e (se usado QR/RFID) identificador único da peça — dados que hoje, em papel, dependeriam de preenchimento manual e seriam propensos a erro/atraso.
3. **Padronização dos dados**: como tudo passa pelo mesmo pipeline de IA, os dados chegam ao backend já em um formato estruturado (JSON), eliminando inconsistências de registro manual (letra ilegível, campo esquecido, etc.).

## 9. Como usar IA para formatação/processamento dos dados já capturados

Depois que os dados brutos (contagens, tempos, status) estão no banco, a IA pode atuar numa segunda camada, sobre dados já estruturados:

- **Detecção de padrões/tendências**: identificar, por exemplo, se uma estação específica tem taxa de defeito crescente ao longo do turno (poderia indicar fadiga do operador, desgaste de ferramenta, etc.) — isso pode ser feito com análise estatística simples ou modelos de série temporal.
- **Geração automática de relatórios/resumos**: usar um modelo de linguagem (LLM) para transformar os números brutos do turno em um resumo em texto simples ("Estação 3 produziu 42 peças, 2 com anomalia detectada, tempo médio de ciclo 3min12s"), facilitando a leitura por supervisores que não querem abrir o dashboard.
- **Classificação de causas prováveis de anomalia**: se o dataset de defeitos crescer, um modelo pode começar a agrupar/categorizar os tipos de defeito mais comuns automaticamente (clustering), ajudando a apontar causas raiz.

Essas duas frentes (IA na borda para gerar dados vs. IA sobre os dados já estruturados) deixam claro o uso da matéria de **IA Aplicada** em dois pontos diferentes do pipeline, o que é interessante para a avaliação acadêmica.

---

## 10. O que pode ser feito 100% pelos alunos vs. o que exige compra

| Componente | Quem faz | Custo para o grupo |
|---|---|---|
| Modelo de visão computacional (treino, anotação, inferência) | Alunos (código) | Zero (ferramentas open-source) |
| Backend, API, banco de dados | Alunos (código) | Zero (self-hosted / free tier) |
| Dashboard web | Alunos (código) | Zero |
| Comunicação IoT (MQTT) | Alunos (código) | Zero |
| Geração/leitura de QR Code | Alunos (código) | Zero |
| **Câmera(s)** | Compra | Baixo (webcam comum ou módulo de câmera) |
| **Placa de borda (Raspberry Pi, se usado)** | Compra | Moderado, só se formos além de 1 estação piloto |
| **Leitor RFID (se optarmos por essa via no futuro)** | Compra | Baixo |

Ou seja: a única fronteira real de "precisa comprar" é a **câmera + eventualmente a placa de borda** — exatamente como pedido no desafio.

---

## 11. Restrições e cuidados a levar em conta

- **Proteção de dados da Renault**: imagens das peças/processos capturadas pelas câmeras não devem sair do ambiente controlado (evitar subir para serviços de nuvem públicos sem autorização); preferir processamento local (edge) e, se precisar de nuvem, usar apenas para o dashboard com dados já anonimizados/agregados.
- **Infraestrutura do laboratório**: validar com o laboratório se há Wi-Fi/rede disponível nas 10 estações, tomadas de energia, e se é permitido instalar câmeras fixas.
- **Escalabilidade**: a arquitetura baseada em MQTT + API + banco relacional já é pensada para crescer de 1 estação piloto até as 10, e depois para novos processos, sem redesenho.
- **Prova de conceito mínima esperada**: 1 estação real (ou simulada em bancada de teste) rodando o pipeline completo — captura → IA → mensageria → backend → dashboard — já atende ao requisito mínimo do desafio.

---

## 12. Próximos passos sugeridos

1. Validar com o laboratório: podemos fotografar/filmar as peças? Existe rede disponível nas bancadas?
2. Definir o escopo do MVP (sugestão: 1 estação, contagem + tempo de ciclo + dashboard básico — deixar anomalia/OK-NG para uma segunda fase).
3. Montar um pequeno dataset inicial de fotos da peça para treinar o primeiro modelo de detecção.
4. Prototipar o pipeline ponta a ponta com hardware simples (webcam + notebook) antes de comprar qualquer placa dedicada.
5. Desenhar o modelo de dados (o que exatamente vamos gravar por evento) — ponto de encontro entre Arquitetura de Software e IA Aplicada.

---

## 13. Referências de apoio

- Documentação oficial Ultralytics (YOLO): https://docs.ultralytics.com
- NVIDIA Jetson Orin Nano Super — página oficial: https://www.nvidia.com/en-us/autonomous-machines/embedded-systems/jetson-orin/nano-super-developer-kit/
- Raspberry Pi 5 — especificações oficiais: https://www.raspberrypi.com
- Anomalib (biblioteca de detecção de anomalias visuais): https://github.com/openvinotoolkit/anomalib
- Mosquitto (broker MQTT open-source): https://mosquitto.org
