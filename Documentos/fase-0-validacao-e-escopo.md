# Fase 0 — Validação e Preparação
## Projeto: Digitalização do Lab de Lean Manufacturing — Renault x UniSenai

**Status:** ✅ Concluída — todos os itens de saída atendidos
**Depende de:** `projeto-renault-lean-lab-pesquisa.md` (documento de viabilidade técnica)

---

## 1. Objetivo da Fase 0

Antes de programar qualquer coisa, precisamos **confirmar premissas** que hoje são suposições no documento de pesquisa. A Fase 0 termina quando tivermos:

1. Respostas do laboratório sobre infraestrutura e acesso.
2. O escopo do MVP fechado (o que entra, o que fica pra depois).
3. Um plano concreto de como vamos coletar as primeiras fotos/vídeos da peça para treinar o modelo.

Sem isso, qualquer código escrito agora tem alto risco de retrabalho.

---

## 2. Checklist de validação com o laboratório / Renault — RESPONDIDO

### 2.1 Infraestrutura física
- [x] **Rede:** existe Wi-Fi compartilhado com toda a faculdade. Se precisarmos de uma rede própria/isolada para o projeto, a alternativa é rotear pelo celular (hotspot).
- [x] **Energia:** existem tomadas na sala; se precisarmos de tomada bem próxima à bancada, será necessário extensão.
- [x] **Fixação de câmera:** permitido.
- [x] **Iluminação:** artificial, LED, da própria sala. Se precisarmos de mais variedade para o dataset, podemos tirar fotos em diferentes ambientes/luzes.

### 2.2 Acesso à peça e ao processo
- [x] **Fotografar/filmar a peça em diferentes estágios:** sim, acesso total às peças.
- [x] **Fotografar peça com defeito/avaria:** permitido, mas **o foco inicial do laboratório não é defeito/avaria** — é verificar **se a peça está montada corretamente de acordo com a respectiva estação**. Isso muda a prioridade do MVP (ver seção 7).
- [x] **Peça emprestada fora do horário:** não é possível — **toda captura de imagem só pode ser feita presencialmente na sala de treinamento**.
- [x] **Variações da peça:** existe uma peça-base (sem nada montado) e depois camadas por estação — **estação 1: camada verde, estação 2: camada amarela, estação 3: camada azul, estação 4: camada vermelha**. Também há acesso às peças individuais/componentes usados em cada estação.

### 2.3 Acesso e horários
- [x] **Horário de acesso ao laboratório:** somente **terças-feiras, das 19h às 22h**.
- [x] **Contato técnico da Renault:** existe e está disponível para dúvidas sobre o processo real.

### 2.4 Dados e propriedade
- [x] **Confidencialidade:** sim — a sala de treinamento e o processo são de uso **restrito a fins acadêmicos e à Renault** (proprietária da sala). Nada pode ser publicado/divulgado fora desse escopo.
- [x] **Armazenamento:** os dados/imagens podem ficar em equipamentos próprios do grupo (não precisa ser só em equipamento do laboratório).

---

## 3. Escopo do MVP — REVISADO com base nas respostas do laboratório

A resposta do item 2.2 muda a prioridade original: o laboratório deixou claro que o interesse principal, num primeiro momento, é **verificar se a peça está com a montagem/camada correta para aquela estação** — não detecção de avaria/quebra. Isso é, na prática, o item **3.1 do documento de pesquisa** (montagem correta), e ele fica **mais fácil do que o previsto**, porque agora sabemos que o critério de "correto" é bem objetivo: **cada estação espera uma cor de camada específica** (verde/amarela/azul/vermelha). Ou seja, o modelo não precisa entender "está bem parafusado" no detalhe fino — precisa, no mínimo, **reconhecer qual camada/cor está presente na peça e comparar com a camada esperada daquela estação**. Isso é uma tarefa de classificação de imagem bem mais simples e rápida de treinar do que detecção fina de parafusos/encaixes.

### ✅ Entra no MVP (Fase 1) — revisado
- 1 estação piloto de montagem (sugestão: a estação da camada verde, por ser a primeira).
- **Verificação de montagem correta por estação**: o modelo classifica a peça observada e confirma se a camada/cor presente é a esperada para aquela estação (ex.: estação 1 espera "verde"; se aparecer "amarela" ali, sinaliza inconsistência).
- Contagem de peças processadas naquela estação (reaproveita a mesma detecção — toda vez que uma peça "correta" é identificada, conta +1).
- Tempo de ciclo por peça (início → conclusão).
- Envio dos eventos para um backend simples.
- Dashboard básico mostrando: total de peças, taxa de acerto/inconsistência, tempo médio de ciclo.

### 🔜 Fica para uma Fase 2 (se o tempo permitir)
- Verificação mais fina de montagem (contagem de parafusos/encaixes específicos, não só a cor da camada).
- Detecção de avarias/quebras (dataset de defeito, se o laboratório disponibilizar exemplos reais).
- Identificação por QR Code/RFID (qual peça específica, não só qual estação).
- Replicação para as demais estações (incluindo as de reciclagem/desmontagem).

**Por quê essa mudança:** classificar "qual camada de cor está presente" é uma tarefa de visão computacional mais simples e com menos ambiguidade do que detectar parafuso a parafuso — e é literalmente o que o laboratório pediu como prioridade. Isso também reduz o tamanho do dataset necessário para o MVP: como as classes são bem distintas visualmente (cores diferentes), o modelo deve aprender com relativamente poucas imagens por classe.

*(Este escopo é uma sugestão — ajustem livremente conforme o que o professor/orientador considerar adequado para a avaliação.)*

---

## 4. Plano de coleta do dataset inicial — revisado (janela única semanal)

**Restrição chave:** só é possível fotografar presencialmente, às terças-feiras das 19h às 22h. Isso significa que **cada visita precisa ser planejada como uma sessão de captura eficiente**, e não dá pra "voltar amanhã" se faltar alguma foto.

### 4.1 Quantidade alvo por classe
Como o MVP agora é **classificação por cor de camada** (verde/amarelo/azul/vermelho + peça-base sem camada), as classes são visualmente bem distintas — isso reduz a quantidade de imagens necessárias comparado a detecção fina de parafusos:
- Meta por sessão: **~40-60 fotos por classe/cor** (peça-base, verde, amarela, azul, vermelha), variando ângulo, distância e leve variação de posição na bancada.
- Isso já é suficiente para um primeiro modelo de classificação de teste; pode ser complementado em sessões seguintes.

### 4.2 Roteiro da sessão de fotos (para não perder tempo na sala)
1. Definir de antemão, antes de ir à sala, **em qual estação/câmera o piloto vai ficar fixado** (evita perder tempo testando posição de tripé na hora).
2. Levar notebook/celular já com o app/script de captura pronto (idealmente já testado em casa com um objeto qualquer, só para validar que o script de captura funciona).
3. Fotografar nesta ordem, para não esquecer nenhuma classe: peça-base → camada verde → amarela → azul → vermelha, variando ângulo/distância a cada 5-10 fotos.
4. Se sobrar tempo, gravar também um pequeno vídeo contínuo do processo de montagem completo (útil para depois extrair frames e para testar a detecção "ao vivo").
5. Ao final da sessão, copiar os arquivos para pelo menos dois lugares (ex.: notebook + pendrive/nuvem privada) — não há uma segunda chance até a próxima terça.

### 4.3 Anotação e ferramenta — atenção à confidencialidade
O laboratório deixou claro que as imagens são de uso **restrito a fins acadêmicos e à Renault** — isso significa que **não podemos usar um projeto público** em ferramentas de anotação:
- **Roboflow:** usar apenas em **projeto privado** (o plano gratuito permite projetos privados; evitar qualquer opção de "publicar"/tornar o dataset público).
- **Alternativa mais segura:** **CVAT** rodando localmente (self-hosted, open-source) ou em um Docker no próprio notebook do grupo — garante que nenhuma imagem saia para servidor de terceiros.
- Independentemente da ferramenta, as imagens ficam armazenadas apenas em equipamentos do grupo (conforme autorizado), nunca em repositório público (ex.: não subir para um GitHub público).

### 4.5 Resultado real da primeira coleta (registrado em 08/09/2026)

**Imagens de peça montada por camada (uso principal do MVP):**

| Camada | Nº de imagens |
|---|---|
| base | 306 |
| camada_verde | 281 |
| camada_amarela | 468 |
| camada_azul | 384 |
| camada_vermelha | 344 |
| **Total** | **1.783** |

**Imagens de peças individuais/componentes (uso futuro — Fase 2):**

| Peça | Nº de imagens |
|---|---|
| Peça Amarela | 8 |
| Peça Azul | 19 |
| Peça Vermelha | 12 |
| Peça Verde | 0 |
| Imãs/Parafusos | 18 |

> Nota do grupo: as peças individuais foram fotografadas apenas separadas por cor, sem a classificação alfabética (A/B/C/D) de cada peça dentro da cor.

**Análise:**

- ✅ **Dataset de camadas está mais do que suficiente para o MVP.** A meta original era ~40-60 imagens/classe; o grupo trouxe entre 281 e 468 por classe — dá para treinar com uma divisão tradicional de **treino/validação/teste (ex.: 70/15/15)** e ainda sobra margem para validar bem o modelo antes de testar ao vivo na bancada.
- ⚠️ **Leve desbalanceamento entre classes** (281 a 468) — não é grave, mas ao treinar vale ou (a) usar *class weights*/balanceamento no treino, ou (b) simplesmente limitar todas as classes ao tamanho da menor (~281) para manter o treino balanceado. Qualquer uma resolve.
- 🔴 **Imagens de peças individuais são insuficientes para qualquer uso no momento** (0 a 19 por peça — precisaria de dezenas por classe, no mínimo). Isso **não bloqueia o MVP** (que usa só as imagens de camada montada), mas é um item pendente para quando o grupo avançar à Fase 2 (verificação fina de parafusos/encaixes).
- 🔴 **Falta a classificação alfabética (A/B/C/D)** dentro de cada cor de peça individual — como o próprio grupo já notou, se a Fase 2 exigir diferenciar as variações de uma mesma cor, será necessária uma sessão de captura dedicada, fotografando cada peça separadamente (não em conjunto) e já organizando os arquivos por essa subclasse (ex.: `peca_azul_A_001.jpg`, `peca_azul_B_001.jpg`). **Recomendação: não fazer isso agora** — só vale a pena investir tempo de captura nisso quando o MVP de camada já estiver validado e o grupo decidir avançar para inspeção fina de componentes.

---

## 5. Implicações técnicas das respostas (para a arquitetura)

| Resposta do laboratório | Implicação |
|---|---|
| Wi-Fi é compartilhado com toda a faculdade (não dedicado ao projeto) | Testar logo na primeira visita se o Wi-Fi da faculdade permite comunicação **dispositivo-a-dispositivo** (muitas redes corporativas/educacionais têm "client isolation", que bloqueia MQTT entre dispositivos na mesma rede). Se bloquear, a alternativa combinada na resposta é usar **hotspot do celular** como rede isolada só para o protótipo — simples e já validado como opção pelo laboratório. |
| Pode precisar de extensão para energia na bancada | Item de logística simples — levar uma extensão/régua na sessão de testes. |
| Captura só presencial, 1x por semana (terça 19h-22h) | Já refletido no plano de coleta (seção 4) — sessões precisam ser roteirizadas. Também significa que **o cronograma do projeto depende diretamente do número de terças disponíveis até a entrega** — vale mapear isso num cronograma à parte. |
| Foco inicial é "camada correta por estação", não avaria | Escopo do MVP revisado (seção 3) — tarefa de classificação por cor, mais simples que detecção fina de defeito. |
| Confidencialidade restrita a uso acadêmico + Renault | Nenhum dado/imagem pode ser publicado ou usado em repositório/projeto público (seção 4.3). Vale também evitar prints/vídeos do processo em apresentações fora do contexto acadêmico sem autorização. |
| Dados podem ficar em equipamento próprio do grupo | Não é obrigatório usar servidor do laboratório — o backend/banco de dados pode rodar no notebook de algum integrante do grupo durante o desenvolvimento. |
| **Decisão: hotspot de celular** como rede do protótipo | Rede isolada e sob controle do grupo — evita o risco de *client isolation* do Wi-Fi da faculdade. Broker MQTT e backend podem rodar no próprio notebook, todos os dispositivos (notebook, e futuramente placas) conectam no mesmo hotspot. Ponto de atenção: **consumo de dados/bateria do celular** durante as sessões de 3h — vale levar carregador. |
| **Decisão: webcam + notebook** como hardware inicial | MVP com **custo zero de hardware novo** — usa equipamento que o grupo já possui. Toda a captura, inferência do modelo e backend rodam no mesmo notebook durante o protótipo, o que simplifica a Fase 1 (não precisa lidar com deploy em placa separada ainda). Isso é aderente à restrição de "baixo custo" do desafio. |

## 6. Entregáveis da Fase 0

| Entregável | Responsável | Status |
|---|---|---|
| Checklist da seção 2 respondido pelo laboratório | Grupo + laboratório | ✅ Concluído |
| Escopo do MVP validado com o professor/orientador | Grupo | ✅ Validado — escopo conferido ponto a ponto contra o "Registro de Demanda" oficial (Focal: Sidnei Santos), sem divergências. Recomendação: incluir alerta automático em tela quando a camada errada for detectada, para reforçar explicitamente o requisito de "automação de processos". |
| Teste de conectividade Wi-Fi dispositivo-a-dispositivo na sala | Grupo | ✅ Decidido — usar **hotspot de celular** como rede isolada do protótipo, sem depender do Wi-Fi da faculdade |
| Primeiras ~40-60 fotos por classe de cor capturadas | Grupo | ✅ Concluído — 1.783 imagens de camadas coletadas (muito acima da meta) |
| Decisão de hardware inicial (webcam+notebook vs. Raspberry Pi) | Grupo | ✅ Decidido — **webcam + notebook** para o MVP |

## 7. Critério de saída da Fase 0

A Fase 0 é considerada concluída quando o grupo tiver: checklist respondido, escopo do MVP validado formalmente, teste/decisão de rede feita, e pelo menos uma sessão de captura de imagens realizada.

**Todos os itens foram atendidos — Fase 0 encerrada.** Próximo passo: Fase 1 (implementação do MVP), começando pela organização do dataset e treino do primeiro modelo de classificação de camada.
