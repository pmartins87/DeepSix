# DeepSix — Roadmap de viabilidade e desenvolvimento

## Objetivo

Construir a melhor estratégia de Poker Cash Game 6+ / Short Deck possível dentro de um orçamento de computação doméstica forte, tendo como referência um Ryzen 9 operando continuamente por semanas ou meses.

A meta não é resolver o jogo completo de forma exata. A meta é converter o orçamento disponível no máximo de força estratégica prática, com validação suficiente para sabermos onde a aproximação é boa, onde ainda é fraca e onde vale gastar o próximo ciclo de CPU.

## Decisão arquitetural permanente

DeepSix possui dois trilhos que avançam em paralelo desde o início:

- **Trilho A — DeepSix Core/Trainer:** regras, evaluator, estado canônico, abstração, solver e política;
- **Trilho B — OpenHoldem6Plus:** fork exclusivo do OpenHoldem para scraping, estado de mesa, replay e execução.

A política só será integrada quando estiver pronta, mas o fork de runtime começa cedo. Isso evita descobrir no fim problemas de forced bets, posições, scraping, bet sizing ou hand reset.

O OpenHoldem6Plus **não precisa preservar compatibilidade estratégica com Hold'em 52-card, AoF, Spin ou OFC**. O que for semanticamente errado para 6+ deve ser substituído ou desabilitado, não mascarado.

---

## Fase 0 — Regras e especificação do jogo

### Objetivo
Congelar exatamente o jogo alvo antes de qualquer treino pesado.

### Entregáveis
- deck e ranks válidos;
- ranking completo das mãos;
- regra da sequência baixa;
- número máximo de jogadores;
- ante e button blind;
- ordem de ação pré-flop e pós-flop;
- stacks mínimos/máximos e unidade de normalização;
- min-bet, min-raise e regras de all-in;
- rake, caps e exceções;
- regras de jackpot/promoções, separadas da estratégia-base quando possível;
- definição de side pots;
- exemplos reais do cliente para validação.

### Gate
Nenhuma ambiguidade que altere payoff, ação legal ou ranking de mão.

---

## Fase 1A — Núcleo matemático Short Deck

### Objetivo
Construir um ambiente de referência independente do OpenHoldem.

### Entregáveis
- deck compacto de 36 cartas;
- parser/encoder de cartas;
- conversão explícita entre card IDs compactos do DeepSix e card IDs legados do OpenHoldem;
- evaluator 5/6/7 cartas correto;
- A6789;
- ranking Short Deck configurável;
- distribuição de mãos conhecida por testes;
- equity heads-up exata ou enumerável;
- testes contra motores independentes;
- pot accounting, rake e side pots;
- ação legal e transições de street.

### Gate
100% dos testes estruturais e de referência passando.

---

## Fase 1B — Fundação do OpenHoldem6Plus

### Objetivo
Criar o fork exclusivo do OpenHoldem e separar o que pode ser reaproveitado do que é perigoso no 6+.

### Política de compatibilidade
- preservar scraping, reconhecimento de cartas, cadeiras, pot, balances, botões, mouse/teclado e infraestrutura de logs quando semanticamente corretos;
- manter o card ID legado de 52 cartas na fronteira do scraper, se isso reduzir risco, mas **aceitar como cartas válidas apenas 6..A**;
- converter para o card ID compacto 0..35 do DeepSix Core antes de qualquer cálculo estratégico;
- nunca usar `Hand_EVAL_N`, `prwin`, `handrank1326`, versus tables ou range engines de 52 cartas como fonte estratégica em 6+;
- não fingir que ante/button blind são small blind/big blind;
- manter símbolos legados incompatíveis explicitamente desabilitados ou marcados como inválidos.

### Entregáveis
- nome/binário próprio do runtime;
- namespace/log prefix próprio;
- feature flag/build que só aceita 6+;
- filtro de cartas 2–5 como erro de estado;
- skeleton de `ShortDeckRules`/`GameRules`;
- skeleton de forced bets nativos: ante e button blind;
- posições relativas ao button sem depender de SB/BB;
- captura de um `TableObservation` neutro;
- replay offline de observações sem clicar na mesa;
- testes que provem que engines 52-card proibidos não entram no caminho de decisão.

### Gate
O runtime consegue observar e serializar corretamente uma mão 6+ sem tomar decisão estratégica e sem consultar nenhum cálculo 52-card incompatível.

---

## Fase 2 — Canonicalização e representação de estado

### Objetivo
Evitar desperdiçar CPU aprendendo equivalências triviais.

### Invariâncias mínimas
- ordem das duas hole cards;
- ordem das cartas recebidas simultaneamente no flop;
- permutação global de naipes;
- representação relativa ao button/posição;
- normalização de valores monetários por unidade escolhida;
- histories semanticamente equivalentes quando a ordem interna não altera o estado observável.

### Entregáveis
- canonicalizer determinístico;
- encoder versionado;
- round-trip tests;
- testes adversariais de colisão;
- medida de redução efetiva do espaço de estados;
- representação compartilhável entre Trainer e OpenHoldem6Plus.

### Gate
Nenhuma equivalência óbvia deixada para a rede aprender sem necessidade e nenhuma colisão entre estados estrategicamente distintos.

---

## Fase 3 — Máquina de estados e contrato runtime

### Objetivo
Garantir que engine de treino e runtime descrevam exatamente o mesmo estado do jogo.

### Estado mínimo
- hand/street;
- button e posições relativas;
- jogadores dealt/active/folded/all-in;
- hole cards do Hero;
- board;
- stack inicial e stack atual por jogador;
- contribuição total e da street;
- pot principal/side pots quando aplicável;
- valor para call;
- min-raise-to/max-raise-to;
- histórico completo de ações relevantes;
- ante e button blind;
- rake model version.

### Entregáveis
- contrato versionado `TableObservation -> CanonicalState`;
- serialização estável para replay;
- hash determinístico de estado;
- detector de transições e ações observadas;
- invalid-state reasons explícitos;
- comparação byte/semantic-equivalent entre Trainer e runtime.

### Gate
Replay da mesma mão produz a mesma sequência de estados canônicos independentemente de ter vindo do simulador ou do OpenHoldem6Plus.

---

## Fase 4 — Abstração de ações

### Objetivo
Transformar No-Limit contínuo em uma árvore tratável sem eliminar decisões essenciais.

### Estratégia inicial
Começar pequeno e permitir refinamento posterior.

Conjunto inicial candidato:
- fold;
- check/call;
- bet/raise pequeno;
- bet/raise médio;
- bet/raise grande;
- all-in.

Os tamanhos exatos serão definidos por street, SPR e estrutura real do jogo, não fixados prematuramente.

### Refinamento
- detectar regiões onde a ação ótima cai frequentemente entre buckets;
- adicionar sizings somente onde o ganho marginal justificar o aumento da árvore;
- permitir abstração diferente por street e SPR;
- mapear ação abstrata para sizing legal real no OpenHoldem6Plus e registrar qualquer clipping.

### Gate
Árvore pequena o suficiente para treinar profundamente e rica o suficiente para não produzir erros grosseiros de sizing.

---

## Fase 5 — Baseline estratégico simples

### Objetivo
Criar algo pequeno, reproduzível e difícil de quebrar.

### Primeiros escopos
1. heads-up postflop isolado em estados artificiais;
2. heads-up desde preflop com stacks fixos;
3. 3-handed simplificado;
4. 6-max progressivamente.

### Uso
Esse baseline servirá como:
- oráculo de regressão;
- comparação para arquiteturas maiores;
- detector de bugs no treino;
- referência de ganho marginal por custo.

---

## Fase 6 — Solver/treino principal

### Objetivo
Extrair o máximo do Ryzen 9.

### Princípios
- treinamento interruptível e retomável;
- checkpoints frequentes;
- sampling adaptativo;
- prioridade para estados de maior reach e maior erro;
- evitar sample caps arbitrários quando houver capacidade útil;
- medir throughput real por configuração de workers;
- nunca assumir que mais workers = mais velocidade;
- separar custo de geração, inferência, atualização e validação.

### Candidatos técnicos
A arquitetura final poderá usar combinação de:
- MCCFR/variants;
- regret matching aproximado;
- redes para value/policy/regret;
- replay/reservoir;
- subgame refinement;
- distillation de políticas.

Nenhuma técnica é mandatória antes dos benchmarks.

### Gate
Superar consistentemente o baseline em testes fora da amostra sem regressões estruturais.

---

## Fase 7 — Escalonamento progressivo

### Ordem preferencial
- mais profundidade no mesmo jogo antes de aumentar dimensionalidade quando isso trouxer mais EV;
- depois ampliar stacks/SPR;
- depois ampliar sizings;
- depois ampliar multiway;
- depois enriquecer o encoder/modelo.

O critério será sempre ganho medido por custo computacional, não elegância arquitetural.

---

## Fase 8 — Auditoria adversarial

### Caminho auditado
estado real → observação OH6+ → canonicalização → infoset → encoder → rede/solver → ações legais → treino → política exportada → runtime → clique

### Procurar explicitamente
- vazamento de informação privada;
- dependência indevida da ordem das cartas;
- dependência indevida do nome absoluto dos naipes;
- states distintos colidindo no mesmo encoding;
- states equivalentes sendo duplicados;
- ação ilegal sendo treinada ou inferida;
- payoff/rake incorreto;
- terminalidade incorreta;
- viés de sampling;
- testes que favoreçam uma arquitetura;
- métricas que melhorem sem ganho real de estratégia;
- uso acidental de evaluator/prwin/handrank 52-card;
- conversão incorreta de card IDs 52-boundary ↔ 36-core;
- confusão entre ante/button blind e SB/BB;
- discrepância entre raise-to do solver e valor efetivamente digitado/clicado.

---

## Fase 9 — Tracker e exploração

Somente depois da estratégia-base estar estável.

### Dados possíveis
- VPIP;
- open/limp/raise por posição;
- 3-bet e respostas;
- frequência por sizing;
- c-bet por textura;
- turn/river barrels;
- fold/call/raise por street e sizing;
- showdown tendencies.

### Política estatística
- shrinkage;
- amostra mínima;
- intervalos de confiança;
- fallback para a base;
- exploração somente quando o ganho esperado superar a incerteza e o risco de modelo.

---

## Fase 10 — Integração da política no OpenHoldem6Plus

### Separação de responsabilidades
O OpenHoldem6Plus é camada de observação e execução. O conhecimento estratégico permanece no DeepSix Core/Policy Runtime.

### Requisitos
- inferência somente sobre estado validado;
- action mask legal antes e depois da inferência;
- raise-to absoluto validado contra call/min/max;
- timeout/failure = nenhuma ação perigosa;
- policy version e state hash em todo log de decisão;
- replay reproduzindo exatamente a decisão;
- nenhum símbolo tradicional 52-card participando da escolha.

### Gate
Para toda decisão de uma suíte de replay, Trainer/Policy Runtime e OpenHoldem6Plus concordam sobre estado, ações legais, ação escolhida e sizing final.

---

## Fase 11 — Certificação prática

### Testes
- self-play massivo;
- replay de mãos reais;
- fuzzing de estados;
- invariance tests;
- determinism tests;
- regression suite;
- stress de longas sessões;
- medição de latência de inferência;
- divergência entre engine e runtime;
- falhas de scraping e frames incompletos;
- betsize input/click confirmation;
- entradas/saídas de jogadores e mesas incompletas.

### Critério final
Não haverá um rótulo de “jogo resolvido”.

O sistema será considerado tecnicamente pronto quando:
- regras e engine estiverem corretos;
- runtime reproduzir a política treinada;
- estratégia superar os baselines disponíveis;
- novas horas de CPU apresentarem retorno marginal suficientemente baixo ou houver gargalo mais valioso para atacar;
- riscos conhecidos estiverem documentados.

---

## Filosofia permanente

**A capacidade computacional é um orçamento de inteligência.**

Toda otimização que economizar CPU, memória ou amostras deve ser avaliada não apenas pelo tempo economizado, mas pelo que podemos comprar com esse orçamento liberado: melhor representação, mais treino, mais estados, melhor abstração ou maior robustez.

DeepSix busca o melhor possível dentro das possibilidades reais — não uma perfeição teórica inalcançável.
