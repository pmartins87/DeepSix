# DeepSix — Roadmap canônico até uma IA autônoma de 6+ / Short Deck no simulador

Última atualização estrutural: 16/08/2026.

O roadmap mede **capacidade validada**, não volume de código. Um item só recebe `PASS` quando existe gate reproduzível. Implementação sem evidência suficiente permanece `PARTIAL`.

## Objetivo final congelado

O produto primário do DeepSix passa a ser:

> **uma IA autônoma de Cash Game 6+ / Short Deck capaz de jogar sessões completas dentro do nosso próprio simulador, usando uma economia modelada a partir do GGPoker Short Deck e treinada dentro do orçamento real de um Ryzen 9.**

A cadeia final é:

```text
regras 6+ versionadas
 -> economia GGPoker versionada
 -> simulador determinístico 2..6 jogadores
 -> estado canônico
 -> abstração de ações/estados escolhida por benchmark
 -> solver multi-street/multiway
 -> blueprint amplo
 -> camada exploratória opcional
 -> policy compilada
 -> agente autônomo
 -> self-play/avaliação
 -> certificação longa
 -> READY FOR 6+ AUTONOMOUS SIMULATOR
```

### O que mudou nesta revisão

- **GGPoker substitui KKPoker como referência econômica.**
- **KKPoker passa a ser apenas material histórico/comparativo.** Nenhum rake/cap/threshold de KKPoker pode entrar silenciosamente no target atual.
- **O simulador é o ambiente primário de execução.** Tablemap, scraping e automação de cliente real não são requisitos para terminar a IA.
- O trabalho já feito em OpenHoldem6Plus/reconstrução temporal é preservado em uma trilha auxiliar, pois contém engenharia útil, mas saiu do caminho crítico.
- O perfil econômico GGPoker é date-versioned. Mudança futura na tabela cria novo profile; não reescreve semanticamente runs antigas.

---

# Fase 0 — Contrato do jogo e alvo econômico

**Status: PARTIAL AVANÇADO**

## Já feito

- target primário redefinido para **simulador próprio**;
- GGPoker definido como referência econômica do 6+;
- KKPoker retirado da condição de fallback/target;
- `SIMULATOR_TARGET_GGPOKER_ECONOMY_V1.md` criado;
- `TARGET_PLATFORM_GGPOKER_V0.md` preservado como documento histórico/superseded;
- deck com 36 cartas, apenas 6..A;
- duas hole cards;
- cinco community cards;
- best-five Hold'em;
- máximo de seis assentos;
- Flush > Full House;
- A6789 como menor straight;
- estrutura de jogo capaz de representar ante-based Short Deck;
- forced bets desacoplados da economia;
- No-Limit representável;
- full raise/min-raise estrutural representável;
- side pots representáveis;
- rake separado de hand strength;
- jackpot/promotional deductions separados do rake base.

## Economia GGPoker já congelada em profile v1

A tabela pública observada em 16/08/2026 foi codificada em `deepsix_core.ggpoker_economy`:

- rake: **5%**;
- stakes publicadas: $0.02 / $0.05 / $0.10 / $0.25 / $0.50 / $1 / $2 / $5 / $10;
- default buy-in publicado por stake;
- caps distintos para 2 / 3 / 4 / 5+ jogadores;
- high-stakes caps publicados em BB convertidos exatamente para cents em cada stake;
- BBJ Short Deck: contribuição separada de **1 ante** a partir do threshold publicado de **100 antes**;
- profile versionado como `ggpoker_shortdeck_cash_2026-08-16_v1`;
- nenhum no-flop/preflop ou small-pot exemption foi inventado no profile, pois a tabela pública usada não o publica;
- rounding do cliente continua deliberadamente não inventado.

## Ainda falta congelar na especificação do simulador

- confirmar/decidir formalmente o forced-bet profile principal: ante de todos + contribuição total do Button;
- congelar ordem exata de ação preflop e pós-flop;
- congelar minimum bet / minimum raise / reopen após short all-ins;
- confirmar Straight > Trips no profile final de ranking, embora o Core já seja capaz de usar essa ordem;
- congelar odd-chip rule;
- decidir se RIMT fará parte do simulador-base ou será módulo opcional;
- decidir se EV Cashout será modelado como feature opcional;
- definir quais stakes entram no primeiro blueprint principal;
- escolher política de rounding do **simulador** para valores fracionários de rake, mantendo a versão registrada;
- definir se o BBJ será default-on no ambiente principal ou um segundo profile econômico.

**Gate de saída:** `GGPokerShortDeckRulesProfile v1` + `GGPokerShortDeckEconomyProfile v1` totalmente versionados, sem parâmetros ocultos.

---

# Fase 1 — Core matemático Short Deck

**Status: PASS para a fundação; OPEN para extensões**

## Concluído

- codec compacto de 36 cartas;
- rejeição obrigatória de ranks 2..5 na fronteira legada;
- 81 starting-hand classes cobrindo exatamente 630 combos;
- evaluator de 5 cartas;
- best-of-5 para 6/7 cartas;
- A6789;
- ranking Short Deck configurado;
- auditoria exaustiva das 376.992 mãos de cinco cartas;
- oracle independente PokerKit;
- evaluator C++ baseline;
- evaluator C++ lookup exato/rápido;
- paridade Python ↔ C++;
- equity HU exata para validação;
- legal actions `FOLD/CHECK/CALL/RAISE_TO`;
- betting-round state machine;
- short all-ins;
- reopen/full-raise architecture;
- full-hand state machine;
- forced-bet posting;
- preflop/flop/turn/river;
- runout automático quando ninguém pode mais apostar;
- pot accounting;
- side-pot accounting;
- showdown bruto exato;
- splits mantidos como `Fraction` quando odd-chip não está congelado;
- canonicalização de hole-card order;
- canonicalização da ordem do flop;
- 24 permutações globais de naipes;
- chairs relativos ao Dealer;
- `ReplayFrame`;
- `DecisionToken`;
- fingerprints;
- corrupção detectável;
- fuzzing determinístico de mãos completas;
- CI mantendo todos esses gates.

## Ainda falta nesta fase

- `GGPokerShortDeckRulesProfile` explícito;
- regression fixtures do simulador usando o profile GGPoker;
- odd-chip após a regra ser escolhida;
- optional-feature fixtures para RIMT/EV Cashout caso entrem no target.

**Gate de manutenção:** qualquer evolução do solver/simulador deve continuar passando todos os invariants/oracles desta fase.

---

# Fase 2 — Simulador de mesa 6+ completo

**Status: PARTIAL — existe state machine de mão, mas ainda não existe o ambiente multiagente final**

## Componentes já disponíveis para reutilizar

- deck/evaluator;
- betting state machine;
- full-hand state machine;
- legal-action engine;
- stacks/contribuições;
- all-ins;
- pot/side-pot accounting;
- board runout;
- showdown;
- canonicalização;
- deterministic replay primitives;
- economia exata configurável.

## Falta construir

- `DeepSixSimulator` como boundary estável;
- `reset(seed, config)`;
- `observe(player)` com information-set correto;
- `legal_actions(player)`;
- `step(action)`;
- chance/deal transitions explícitas;
- multi-agent turn ownership;
- 2..6 dealt players;
- arbitrary asymmetric stacks;
- Button rotation;
- player join/leave entre mãos para suites de teste;
- sit-out apenas se fizer parte do target simulado;
- persistent bankroll/session accounting;
- rake/cap por player count;
- BBJ contribution toggle/profile;
- hand history canônica do simulador;
- event log completo;
- deterministic replay a partir de seed + actions;
- invalid-action fail-fast;
- no hidden information leakage no observation API;
- batch simulation API;
- vectorized/batched deal generation quando medir ganho real;
- fault-free long self-play loop;
- property/fuzz tests de milhares/milhões de mãos.

**Gate de saída:** duas a seis políticas simples conseguem jogar sessões completas e reproduzíveis, sem estado ilegal, dinheiro criado/perdido fora das deductions configuradas ou vazamento de informação.

---

# Fase 3 — Economia GGPoker e settlement final

**Status: PARTIAL AVANÇADO**

## Concluído

- `RakeConfig`;
- `compute_exact_rake()` com `Fraction`;
- rate/cap exatos;
- threshold opcional;
- preflop exemption opcional;
- table-size multiplier opcional;
- `requires_rounding`;
- helper genérico Short Deck;
- módulo `deepsix_core.ggpoker_economy`;
- nove stakes GGPoker publicadas codificadas;
- default buy-ins codificados;
- caps 2/3/4/5+ codificados;
- high-stakes BB caps convertidos exatamente para cents;
- rake GGPoker 5% profile;
- BBJ contribution `>=100 antes -> 1 ante` separada;
- testes de schedule/caps/threshold/erros.

## Ainda falta

- policy de rounding do simulador;
- settlement `gross pot -> rake -> BBJ -> net pot` em uma API única;
- side-pot deductions policy se rake/BBJ precisarem ser alocados por pote;
- odd-chip policy;
- tests de conservation sob splits/side pots;
- utility interface usada pelo solver;
- decidir se economia será tratada por hand payoff líquido ou por session bankroll delta;
- definir métrica para multiplayer non-zero-sum com house deductions;
- optional EV Cashout 1% somente se escolhido;
- rewards/cashback/leaderboard somente como camada secundária, nunca misturados silenciosamente ao base game.

**Gate de saída:** toda mão do simulador fecha com accounting exato e versionado sob a economia GGPoker escolhida.

---

# Fase 4 — Laboratório de abstração, ações e solver

**Status: IN PROGRESS — infraestrutura madura; benchmark Ryzen real ainda pendente**

## Concluído

### Baselines/oracles

- Kuhn CFR com valor/exploitability conhecidos;
- river microgame Short Deck usando ranges/evaluator reais;
- exact best response por private hand;
- brute-force oracle para jogos pequenos;
- Dynamic Exact Best Response por programação dinâmica;
- DP BR gated contra o enumerador em S=1/S=2, políticas uniformes/treinadas e ranges ponderados.

### Action abstraction

- river 1..4 initial bet sizings sem raise;
- custo marginal de action width;
- one-raise com bet fixo + raise-to;
- benchmark `no_raise -> one_raise`;
- multi-size + one-raise;
- custo enumerativo `(1+S)6^S` explicitado;
- linha escalável 1..4 sizings + um raise usando exact DP BR.

### Private-state abstraction

- `BucketedRiverCFR`;
- política abstrata expandida novamente para combos exatos antes da avaliação;
- avaliação sempre no jogo original não abstraído;
- identity bucket reproduz CFR não abstraído;
- `single`;
- `showdown_category`;
- conditional-equity quantiles blocker-aware;
- range equity;
- universal equity;
- nutness;
- blocked range weight;
- blocked stronger range weight;
- `feature_borda_quantile`;
- uniform-reference counterfactual values;
- deterministic CFV k-medoids;
- gate analítico com incentivos opostos FOLD/CALL.

### Benchmarking

- River Benchmark Battery v3;
- seis board textures;
- ranges sintéticos gerados mecanicamente;
- mean/median/worst exact exploitability/pot;
- nodes/action slots;
- throughput;
- `mapping_build_seconds` separado do training cost;
- State-Abstraction Convergence v1;
- checkpoints cumulativos;
- cumulative wall-clock;
- Pareto por checkpoint;
- synchronous Regret-Matching+;
- regrets RM+ truncados em zero;
- average-strategy delay/peso configurável;
- determinismo/resumibilidade;
- benchmark CFR vs RM+ no mesmo oracle;
- Ryzen Benchmark Protocol v2;
- manifest com commit/máquina/comandos/logs/hashes;
- analyzer com SHA-256 verification;
- compatibilidade com manifests v1;
- Pareto apenas entre objetos matematicamente comparáveis;
- CI cobrindo os gates.

## Falta imediatamente

1. executar no Ryzen 9:

```text
python tools/run_ryzen_benchmark_suite.py --profile engineering
```

2. analisar erro x wall-clock x nós x mapping cost;
3. repetir candidatos próximos da fronteira;
4. decidir CFV vs equity/blocker families;
5. decidir CFR vs RM+ por custo real;
6. decidir se equal-wall-clock benchmark é necessário;
7. testar multiple raise sizes;
8. testar re-raise se comprar força suficiente;
9. medir stack-to-pot sensitivity;
10. medir RAM por infoset e throughput multi-core;
11. serialization/resume de runs longas;
12. substituir gradualmente ranges artificiais por distribuições geradas pelo próprio simulador multi-street.

**Gate de saída:** action/state/solver family escolhida por evidência reproduzível no Ryzen 9.

---

# Fase 5 — Solver multi-street HU / primeiro blueprint

**Status: NOT STARTED**

## Falta fazer

- public-state representation preflop/flop/turn/river;
- chance transitions;
- canonicalização consistente entre streets;
- stack/pot/to-call/min-raise/SPR features;
- preflop limp/open/raise/jam abstraction;
- flop/turn/river bet/check/raise abstractions;
- multiple raise sizes onde aprovados na Fase 4;
- private abstraction por street;
- bucket transitions;
- range propagation;
- reach probabilities;
- economy-aware terminal utility;
- solver escolhido na Fase 4;
- sampling scheme se necessário;
- checkpoint/resume;
- deterministic seeds;
- compression/serialization;
- local exact subgame oracles;
- held-out subgame evaluation;
- baseline policies simples;
- blueprint HU inicial;
- comparação fora do treino.

**Gate de saída:** blueprint HU multi-street supera baselines simples e possui custo/erro medidos.

---

# Fase 6 — Multiway 3, 4, 5 e 6 jogadores

**Status: NOT STARTED**

## Falta fazer

- state representation 3+ players;
- action ordering multiway;
- folds/elimination;
- arbitrary stack asymmetry;
- side pots dentro do solver;
- all-in runouts;
- 2..6 player starting configurations;
- only-valid position/chair symmetries;
- chance reach multiway;
- range representation multi-player;
- solver/regret method apropriado para multiplayer;
- métrica de qualidade que não finja two-player zero-sum;
- NashConv/exploitability surrogate onde aplicável;
- GGPoker rake/cap/deductions dentro da utility;
- sparse/adaptive traversal;
- CPU prioritization por reach/error/EV;
- curriculum HU -> 3-way -> 4-way -> 5/6-way;
- stack-depth curriculum;
- memory-pressure benchmark;
- shard layout;
- checkpoint layout para meses de treino;
- cross-seat/cross-player-count evaluation.

**Gate de saída:** política 2..6 jogadores robusta, sem reduzir falsamente multiway a HU.

---

# Fase 7 — Blueprint amplo e treinamento longo no Ryzen 9

**Status: NOT STARTED**

## Falta fazer

- definir coverage target de stacks/player counts/stakes;
- definir CPU/RAM/disk budget;
- job scheduler;
- multi-core scaling;
- resumibilidade após reboot/falha;
- queues/shards;
- deterministic job manifests;
- prioritized state refinement;
- error heatmaps;
- coverage heatmaps;
- targeted resampling de rare/high-EV states;
- held-out validation states;
- periodic frozen checkpoints;
- regression rollback;
- artifact compaction;
- policy distillation apenas se reduzir custo sem perda importante;
- selecionar blueprint final por suites out-of-sample;
- long-run reproducibility.

**Gate de saída:** blueprint amplo e estável, com cobertura e força mensuradas.

---

# Fase 8 — Population model e exploração

**Status: NOT STARTED**

## Princípio

A estratégia-base continua separada da exploração. A camada exploit nunca deve ser necessária para que a IA seja considerada funcional.

## Fontes válidas para o target atual

- populações sintéticas do simulador;
- pools de agentes congelados;
- hand datasets offline/permitted quando existirem;
- self-play checkpoints históricos.

## Falta fazer

- opponent/population schema;
- action frequencies por state abstraction;
- confidence intervals;
- Bayesian/shrinkage fallback;
- archetypes/clusters;
- sizing tendencies;
- fold/call/raise deviations;
- preflop frequencies;
- postflop deviations;
- exploit policy bounded por confiança;
- fallback automático para base policy;
- out-of-sample evaluation;
- robustness contra adversário não modelado;
- anti-overfit limits;
- `base_policy` e `exploit_overlay` artefatos separados.

**Gate de saída:** ganho out-of-sample demonstrado sem regressão grave de robustez.

---

# Fase 9 — Policy compiler e runtime do agente

**Status: NOT STARTED**

## Falta fazer

- policy file format versionado;
- metadata de rules/economy/model version;
- canonical state key;
- exact/abstract lookup;
- action distribution retrieval;
- deterministic RNG por seed/decision token quando sampling for usado;
- fallback para estado fora de coverage;
- cache/memory mapping;
- startup hash validation;
- corruption detection;
- load-time compatibility gates;
- p50/p95/p99 query latency;
- timeout behavior;
- explain log;
- byte-for-byte replay da mesma decisão;
- runtime ↔ simulator version compatibility.

**Gate de saída:** `simulator observation -> canonical state -> audited action distribution` determinístico dentro do budget de latência.

---

# Fase 10 — Agente autônomo em closed loop no simulador

**Status: NOT STARTED**

## Falta fazer

- agent interface;
- self-play seat assignment;
- fold/check/call/raise-to submission;
- action legality enforcement;
- state-before-action fingerprint;
- state-after-action confirmation;
- full session loop;
- multiple simultaneous agent policies;
- policy-vs-baseline tables;
- policy-vs-policy tables;
- bankroll/session accounting;
- reconnect/restart of simulation workers;
- bad/unknown state fail-closed;
- corrupted policy rejection;
- delayed worker result handling;
- deterministic session replay;
- long soak tests;
- millions-of-hands stability tests.

**Gate de saída:** a IA joga autonomamente sessões longas completas de 6+ no simulador sem erro de estado/ação/accounting.

---

# Fase 11 — Certificação de força e release

**Status: NOT STARTED**

## Falta fazer

- baseline tournaments;
- frozen-policy A/B;
- cross-check contra exact/local solvers em subgames;
- strategy invariance audit;
- NashConv/exploitability proxies onde matematicamente válidos;
- head-to-head confidence intervals;
- multiway evaluation protocol;
- GGPoker-rake-aware win-rate simulation;
- bankroll/variance simulation;
- stress por 2..6 players;
- stress por stack depth;
- stress por stake/economy profile;
- rare-state audit;
- adversarial action sequences;
- memory/disk stress;
- restart/resume certification;
- version rollback;
- independent deterministic replay audit;
- reproducibility package;
- final release manifest;
- freeze de rules/economy/policy hashes.

**Gate de saída:** somente aqui o projeto recebe:

```text
READY FOR 6+ AUTONOMOUS SIMULATOR
```

---

# Trilha auxiliar A — OpenHoldem6Plus e observação de cliente

**Status: PARTIAL AVANÇADO — PRESERVADA, FORA DO CAMINHO CRÍTICO**

Este trabalho já foi feito e não será apagado, porém não bloqueia a IA de simulador.

## Concluído

- branch dedicada `myoh_private:deepsix_6plus`;
- auditoria de premissas 52-card/SB-BB/1326/2652/prwin;
- `ShortDeckRules` C++;
- `TableObservation` C++;
- validator;
- JSON canônico;
- `RawTableSnapshot` read-only;
- raw schema v2;
- `hero_myturnbits`/`hero_sitting_in` tratados como evidência;
- parser Python;
- cross-repo C++ -> JSON -> Python contracts;
- workflow CI;
- observe/replay-first architecture.

## Reconstrução temporal concluída/parcial

- raw-chair -> strategic-seat;
- decimal money -> integer units;
- stable-frame gate;
- conservative transition classification;
- `RawEvidenceTimeline`;
- inferência segura de CALL;
- short all-in CALL;
- exact RAISE_TO quando único;
- recusa de inventar CHECK/FOLD;
- forced-bet baseline detector;
- hand epochs;
- ambiguity taint;
- `RawObservationPipeline` end-to-end sintético.

## Se retomarmos essa trilha no futuro

Faltariam tablemap/layout real, CHECK/FOLD evidence, animation timing, side-pot/payout timing, build Windows/soak e outros detalhes de integração. **Nada disso é requisito para `READY FOR 6+ AUTONOMOUS SIMULATOR`.**

---

# Trilha auxiliar B — Evidência externa de regras GGPoker

**Status: OPTIONAL/PARTIAL**

O simulador pode avançar com um profile explícito e versionado. Ainda assim, material oficial/replays permitidos podem ser usados para melhorar fidelidade.

Útil para:

- forced-bet/button semantics;
- min-raise/reopen edge cases;
- Straight x Trips confirmation;
- rounding real;
- optional features;
- mudanças futuras de rake/caps/jackpot.

Qualquer descoberta cria uma nova versão da spec/economy quando alterar semântica. Runs antigas permanecem reproduzíveis.

---

# Onde estamos agora

```text
F0  Contrato/regras/economia target     PARTIAL+  ███████░░░
F1  Core matemático                     PASS      ██████████
F2  Simulador multiagente               PARTIAL   ████░░░░░░
F3  Economia/settlement GGPoker         PARTIAL+  ███████░░░
F4  Lab abstração/solver                IN PROG   ████████░░
F5  Blueprint HU multi-street           NOT START ░░░░░░░░░░
F6  Multiway 3-6 jogadores              NOT START ░░░░░░░░░░
F7  Treino longo blueprint              NOT START ░░░░░░░░░░
F8  Population/exploit                  NOT START ░░░░░░░░░░
F9  Policy compiler/runtime             NOT START ░░░░░░░░░░
F10 Closed-loop autonomous simulator    NOT START ░░░░░░░░░░
F11 Certificação/release                NOT START ░░░░░░░░░░
A   OH6Plus/real-client observation     SIDE      ███████░░░
B   External GGPoker rule validation    OPTIONAL  ███░░░░░░░
```

As barras representam maturidade aproximada dentro de cada fase, não percentual matemático do projeto.

## Leitura correta do progresso

O projeto já tem uma fundação matemática e de validação muito acima de um protótipo inicial. O river lab também já possui oracles, abstrações e benchmarking sofisticados. O que **ainda não existe** é justamente a parte que transforma isso em uma IA completa de cash game: simulador multiagente final, solver multi-street, multiway 3..6, blueprint amplo e closed-loop autonomous agent.

Portanto não estamos “quase prontos”, mas também não estamos começando: boa parte do risco de regra/evaluator/abstraction auditing já foi atacada antes de gastar meses de CPU.

---

# Caminho crítico atual

```text
1. congelar RulesProfile + EconomyProfile do simulador
           |
           +-> finalizar DeepSixSimulator 2..6
           |
2. Ryzen engineering benchmark
           |
3. escolher action/state/solver family
           |
4. construir blueprint HU multi-street
           |
5. expandir 3-way -> 4-way -> 5/6-way
           |
6. treino longo + refinement
           |
7. policy compiler/runtime
           |
8. autonomous self-play closed loop
           |
9. certification
           |
READY FOR 6+ AUTONOMOUS SIMULATOR
```

## Próximos dois gates com maior valor

### Gate estratégico

```text
python tools/run_ryzen_benchmark_suite.py --profile engineering
```

Isso fornece a primeira fronteira real de custo/erro no hardware-alvo antes de escolhermos a arquitetura que receberá meses de treino.

### Gate de ambiente

Construir a primeira versão do `DeepSixSimulator` sobre o Core já existente e usar o novo `ggpoker_shortdeck_cash_2026-08-16_v1` como economia configurável.

Esses dois caminhos podem avançar em paralelo. Não precisamos mais esperar tablemap, captura KKPoker ou integração com cliente real para chegar à IA completa de 6+ no simulador.
