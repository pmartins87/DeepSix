# DeepSix — Roadmap de viabilidade e desenvolvimento

## Objetivo

Construir a melhor estratégia de Poker Cash Game 6+ / Short Deck possível dentro de um orçamento de computação doméstica forte, tendo como referência um Ryzen 9 operando continuamente por semanas ou meses.

A meta não é resolver o jogo completo de forma exata. A meta é converter o orçamento disponível no máximo de força estratégica prática, com validação suficiente para sabermos onde a aproximação é boa, onde ainda é fraca e onde vale gastar o próximo ciclo de CPU.

---

## Fase 0 — Regras e especificação do jogo

### Objetivo
Congelar exatamente o jogo alvo antes de qualquer treino.

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

## Fase 1 — Núcleo matemático Short Deck

### Objetivo
Construir um ambiente de referência independente do OpenHoldem.

### Entregáveis
- deck de 36 cartas;
- parser/encoder de cartas;
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
- medida de redução efetiva do espaço de estados.

### Gate
Nenhuma equivalência óbvia deixada para a rede aprender sem necessidade e nenhuma colisão entre estados estrategicamente distintos.

---

## Fase 3 — Abstração de ações

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
- permitir abstração diferente por street e SPR.

### Gate
Árvore pequena o suficiente para treinar profundamente e rica o suficiente para não produzir erros grosseiros de sizing.

---

## Fase 4 — Baseline estratégico simples

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

## Fase 5 — Solver/treino principal

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

## Fase 6 — Escalonamento progressivo

### Ordem preferencial
- mais profundidade no mesmo jogo antes de aumentar dimensionalidade quando isso trouxer mais EV;
- depois ampliar stacks/SPR;
- depois ampliar sizings;
- depois ampliar multiway;
- depois enriquecer o encoder/modelo.

O critério será sempre ganho medido por custo computacional, não elegância arquitetural.

---

## Fase 7 — Auditoria adversarial

### Caminho auditado
estado real → canonicalização → infoset → encoder → rede/solver → ações legais → treino → política exportada → runtime

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
- métricas que melhorem sem ganho real de estratégia.

---

## Fase 8 — Tracker e exploração

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

## Fase 9 — Integração com OpenHoldem

### Separação de responsabilidades
O OpenHoldem será tratado como camada de observação/ação. O conhecimento estratégico deve permanecer no motor DeepSix e não depender de símbolos tradicionais de Hold'em 52-card que sejam semanticamente incorretos para Short Deck.

### Necessidades
- game mode Short Deck;
- deck/rank mapping correto;
- evaluator/equity Short Deck;
- posições e button blind;
- pot e stacks;
- ações e sizings;
- validação de estado antes de agir;
- replay offline de mãos coletadas.

---

## Fase 10 — Certificação prática

### Testes
- self-play massivo;
- replay de mãos reais;
- fuzzing de estados;
- invariance tests;
- determinism tests;
- regression suite;
- stress de longas sessões;
- medição de latência de inferência;
- divergência entre engine e runtime.

### Critério final
Não haverá um rótulo de “jogo resolvido”.

O sistema será considerado pronto quando:
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