# DeepSix — Roadmap canônico até uma IA autônoma de 6+ / Short Deck no simulador

Última atualização estrutural: **26/08/2026**.

O roadmap mede **capacidade validada**, não volume de código. Um item só recebe `PASS` quando existe gate reproduzível. Código novo cujo CI/soak ainda não fechou permanece `PARTIAL`, mesmo quando a implementação já existe.

## Objetivo final congelado

O produto primário do DeepSix é:

> **uma IA autônoma de Cash Game 6+ / Short Deck capaz de jogar sessões completas dentro do nosso próprio simulador, usando uma economia versionada modelada a partir do GGPoker Short Deck e treinada dentro do orçamento real de um Ryzen 9.**

A cadeia final é:

```text
rules profile 6+ versionado
 -> economy profile GGPoker versionado
 -> simulador determinístico 2..6
 -> estado canônico
 -> action/state abstraction escolhida por benchmark
 -> solver multi-street HU
 -> solver/policy multiway 3..6
 -> blueprint amplo
 -> exploração opcional
 -> policy compiler/runtime
 -> agente autônomo
 -> self-play/avaliação
 -> certificação longa
 -> READY FOR 6+ AUTONOMOUS SIMULATOR
```

### Decisões arquiteturais congeladas

- **GGPoker é a referência econômica**, não a plataforma de execução.
- **O simulador próprio é o ambiente primário da IA.**
- KKPoker permanece apenas como material histórico/comparativo; nenhum rake/cap/threshold antigo pode contaminar o target atual.
- OpenHoldem6Plus e reconstrução de cliente são preservados como trilha auxiliar, fora do caminho crítico.
- Todo profile de regras/economia/settlement/utility é versionado. Mudança futura cria nova versão sem reescrever o significado de runs antigas.
- Correção e reprodutibilidade precedem escala. Uma run longa não começa sobre semântica, abstração ou utility ainda não gated.
- Paralelismo não pode alterar a identidade semântica de uma mão. O schedule global de seeds é independente da topologia de shards/workers.

---

# Fase 0 — Contrato do jogo e alvo econômico

**Status: PASS para o Simulator Profile v1; OPEN somente para futuras versões/opcionais**

## Concluído

- target primário redefinido para simulador próprio;
- GGPoker definido como referência econômica;
- KKPoker retirado da condição de target/fallback econômico;
- `SIMULATOR_TARGET_GGPOKER_ECONOMY_V1.md` criado e atualizado;
- rules profile versionado `deepsix_shortdeck_sim_rules_2026-08-25_v1`;
- economy profile versionado `ggpoker_shortdeck_cash_2026-08-16_v1`;
- settlement profile versionado `deepsix_sim_settlement_2026-08-25_v1`;
- utility profile versionado `deepsix_sim_utility_2026-08-25_v1`;
- 36 cartas, ranks 6..A;
- duas hole cards + cinco community cards;
- best-five Hold'em;
- até seis jogadores;
- Flush > Full House;
- A6789 como menor straight;
- Straight > Trips no evaluator/profile atual;
- No-Limit;
- todos os dealt players postam 1 ante;
- Button/Dealer posta 2 antes totais;
- action order: primeiro dealt seat à esquerda do Dealer até o Dealer, em todas as streets;
- simulator v1 mapeia a unidade publicada da stake para 1 ante;
- preflop initial full-raise increment = 2 antes;
- postflop minimum bet / initial full-raise increment = 2 antes;
- short all-in permitido quando é o all-in exato abaixo do minimum full raise;
- reopen v1 por `CUMULATIVE_FULL_RAISE`;
- odd chip v1 vai ao primeiro tied winner à esquerda do Dealer e segue clockwise;
- EV Cashout/RIMT excluídos explicitamente da árvore-base v1;
- BBJ pode ser ligado/desligado como camada econômica versionada.

## Economia GGPoker v1 congelada

- rake de **5%**;
- stakes publicadas $0.02 / $0.05 / $0.10 / $0.25 / $0.50 / $1 / $2 / $5 / $10;
- default buy-in por stake;
- caps separados para 2 / 3 / 4 / 5+ jogadores;
- high-stakes caps publicados em BB convertidos exatamente para cents;
- nenhum no-flop/preflop ou small-pot exemption inventado;
- BBJ Short Deck separado: 1 ante no threshold de 100 antes;
- simulator settlement v1 usa floor para converter rake fracionário ao integer money unit.

## Futuras extensões, sem bloquear v1

- novo economy profile quando a tabela pública mudar;
- novo rules profile se quisermos espelhar outra convenção de min-raise/reopen;
- optional profile para RIMT;
- optional profile para EV Cashout;
- rewards/leaderboard/cashback apenas como camada econômica separada, se algum experimento justificar.

**Gate de manutenção:** qualquer mudança semântica exige nova versão e testes de compatibilidade histórica.

---

# Fase 1 — Core matemático Short Deck

**Status: PASS para a fundação; manutenção contínua**

## Concluído e gated

- codec compacto 0..35;
- rejeição obrigatória de ranks 2..5 na fronteira legada;
- 81 starting-hand classes cobrindo exatamente 630 combos;
- evaluator 5-card e best-of-5 para 6/7 cards;
- A6789;
- ranking Short Deck;
- auditoria exaustiva das **376.992** mãos de cinco cartas;
- contagens analíticas por categoria;
- oracle independente PokerKit pinado;
- evaluator C++ baseline;
- evaluator C++ lookup exato/rápido;
- paridade Python ↔ C++;
- equity HU exata para validação;
- `FOLD/CHECK/CALL/RAISE_TO`;
- legal-action boundary;
- betting-round state machine;
- full raises;
- short all-ins;
- reopen policies explícitas;
- full-hand state machine `preflop -> flop -> turn -> river -> terminal`;
- auto-runout quando não existe mais decisão de betting;
- chip conservation;
- pot layers/main pot/side pots;
- folded chips preservados e folded players inelegíveis;
- showdown exato por pot layer;
- splits mantidos como `Fraction` no Core;
- canonicalização de hole order;
- canonicalização da ordem interna do flop;
- 24 permutações globais de naipes;
- chairs relativos ao Dealer;
- action sizing/history preservados quando estrategicamente distintos;
- `ReplayFrame`;
- `DecisionToken`;
- semantic/observation fingerprints;
- detecção de corrupção/tampering;
- fuzzing determinístico de mãos completas;
- randomized pot-layer conservation para 2..6 jogadores.

## Gate de manutenção

Toda evolução posterior precisa continuar passando evaluator/oracle/invariance/chip-conservation/pot-layer e replay gates. O Python permanece correctness oracle; hot paths futuros podem ser nativos, mas precisam provar paridade.

---

# Fase 2 — DeepSixSimulator multiagente

**Status: PARTIAL AVANÇADO — ambiente funcional e crash-safe; long-soak/target-performance ainda abertos**

## Concluído ou já implementado

### Rules + environment

- pacote `deepsix_simulator` criado;
- `SimulatorRulesProfile` versionado;
- `SimulatedHand` com deck real de 36 cartas;
- shuffle determinístico por seed;
- deal round-robin de duas hole cards;
- 2..6 dealt players;
- physical seats 0..5 e sparse seats suportados pelo Core;
- asymmetric starting stacks;
- seat-local private observation: cada policy vê apenas suas duas hole cards;
- board, pot, stacks, commitments, folds, all-ins, history e actor como informação pública;
- opponent hole cards deliberadamente ausentes do observation contract;
- legal actions expostas somente ao seat que realmente age;
- out-of-turn action fail-closed;
- illegal actions rejeitadas pelo Core;
- automatic flop/turn/river chance transitions;
- automatic board runout em all-in/dry betting;
- full closed-loop hand via `play_to_terminal()`;
- deterministic passive/aggressive policies apenas para validação.

### Session/table shell

- `DeepSixTable`;
- published default buy-in como default de sessão;
- persistent stacks entre mãos;
- Dealer rotation clockwise;
- funded-seat filtering;
- commit de settlement ao bankroll da sessão;
- encerramento natural quando restar menos de dois funded seats;
- `SimulatorTableSnapshot` schema v1;
- snapshot/restauração entre mãos;
- busted seats com stack zero preservados;
- continuação após restore comparada contra execução ininterrupta por transcript fingerprint/stacks/Dealer/hand index.

### Trainer/worker API

- `DeepSixEnv` dependency-free;
- `reset(seed)`;
- `observe(seat)`;
- `current_observation()`;
- `legal_actions(seat)`;
- `step(action)` exatamente uma decisão por chamada;
- `SimulatorObservation` schema version 1;
- canonical observation JSON;
- SHA-256 observation fingerprint;
- use-before-reset e out-of-turn requests rejeitados.

### Replay/auditoria

- `SimulatorHandTranscript` schema v1;
- canonical JSON;
- seed + starting stacks + Dealer + action sequence;
- private-deal SHA-256;
- settlement SHA-256;
- transcript fingerprint;
- exact replay a partir da seed;
- actor sequence verificada;
- board, hidden deal e settlement comparados por digest;
- tampering de seed/actor rejeitado;
- fold terminal suportado preflop/flop/turn/river.

### Session evidence

- `run_seeded_session()` single-process;
- explicit seed schedule;
- per-hand transcript fingerprint;
- accumulated decisions/gross pot/rake/BBJ;
- final stacks;
- session canonical JSON/fingerprint;
- session-level bankroll conservation.

### Crash-safe soak/sharding

- `SimulatorSoakPlan` schema v1;
- deterministic global hand indexes/seeds;
- disjoint shard allocation `s, s+N, s+2N...`;
- global schedule coberto exatamente uma vez pelos shards;
- hand id derivado somente do global index;
- mesma global hand permanece byte/semanticamente equivalente sob outra topologia de shards;
- `SimulatorSoakCheckpoint` canonical JSON + SHA-256;
- atomic checkpoint write com `flush/fsync/os.replace`;
- `failure.json` com exact seed/global index/error;
- `--resume` rejeita plan incompatível;
- independent-hand long-soak design para não terminar artificialmente por bankroll/rake;
- periodic exact transcript replay sampling;
- terminal board/card uniqueness/accounting invariants em toda mão;
- hands/s, decisions/s e peak `tracemalloc` reportados por segmento.

### Gates de robustness já adicionados

- deterministic equal-seed deal;
- hidden-information boundary;
- passive checkdown;
- all-in auto-runout;
- 2..6-player randomized trajectories;
- asymmetric stacks;
- randomized legal fold/call/check/min-raise/max-raise choices;
- main/side-pot adversarial fixture;
- tied-pot odd-chip fixture;
- deterministic replay subset;
- aggregate chip/money conservation;
- 5.000 randomized pot-layer accounting cases 2..6;
- soak smoke no CI;
- shard-topology invariance gate.

Durante esses gates apareceram duas fixtures erradas, e os testes foram corrigidos em vez de relaxar o motor:

1. um fold pós-flop é terminal legítimo com board de 3/4 cards; exigir somente board 0/5 era um invariant artificial;
2. `67` em board `AKQ98` forma **A6789**, portanto a mão corretamente ganhava de trips no teste de side pot. A fixture foi substituída por uma mão que realmente perde.

## Falta para F2 PASS

- long soak de escala relevante com zero divergência de accounting/state/replay;
- real hands/s, decisions/s e peak-memory measurement na máquina-alvo;
- stress específico de 6-way com stacks muito desiguais em escala maior;
- adversarial short-all-in/reopen sequences geradas automaticamente;
- definir transcript-retention policy para runs longas sem explodir I/O;
- batch/multiprocess runner somente se profiling mostrar ganho útil;
- join/leave/sit-out/rebuy/top-up semantics somente se forem necessárias ao tipo de sessão longa escolhido.

**Gate de saída:** simulador executa/reproduz runs longas 2..6 sem state/accounting divergence e com throughput/memória medidos.

---

# Fase 3 — Economia, settlement e utility GGPoker-reference

**Status: PARTIAL AVANÇADO — settlement/utility v1 gated; long-run/rake-aware strategy gates abertos**

## Concluído ou implementado

- `RakeConfig` genérico;
- rational `Fraction` calculations;
- `ggpoker_shortdeck_rake_config()`;
- 5% + player-count cap;
- nine frozen stakes;
- published default buy-ins;
- no undocumented exemptions;
- `ggpoker_shortdeck_bbj_contribution()`;
- BBJ separável on/off;
- gross showdown por pot layer;
- integer odd-chip settlement v1;
- floor rake rounding v1;
- aggregate house deductions;
- deterministic pro-rata/largest-remainder allocation aos gross winners;
- post-hand stack accounting;
- conservation identity:

```text
sum(final player stacks)
= sum(initial player stacks)
- rounded rake
- BBJ
```

- side-pot test com main winner diferente do side winner;
- odd-chip tie test;
- `SimulatorUtilityVector` por seat;
- `gross_poker_delta = gross_award - contribution`;
- `net_cash_delta = net_award - contribution`;
- exact ante normalization por `Fraction`;
- prova de `sum(gross utility)=0`;
- prova de `sum(net utility)=-(rake+BBJ)`;
- stake/ante compatibility gate;
- golden regression da matriz completa das 9 stakes/default buy-ins/caps;
- cap-transition regression em 9 stakes × 2..6 players;
- BBJ threshold regression em todas as nove unidades de ante.

## Falta para fechar a camada estratégica

- rake-aware benchmark baselines usando a utility final;
- long-run accounting soak com utility statistics;
- definir quais economy profiles entram no blueprint principal e quais ficam para cross-stake evaluation;
- decidir se F5 treina primariamente gross zero-sum subgames, net cash objective, ou combinação controlada por estágio — sem confundir as garantias matemáticas de cada objeto.

**Gate de saída:** todo terminal gera utility por seat reproduzível e o método de treino/avaliação declara explicitamente qual utility otimiza.

---

# Fase 4 — Laboratório de ação, estado e solver

**Status: IN PROGRESS — infraestrutura madura; primeira bateria Ryzen real ainda pendente**

## Concluído

- Kuhn CFR com valor/exploitability conhecidos;
- river microgame Short Deck com ranges/evaluator reais;
- exact best response por private hand;
- 1..4 initial bet sizings sem raise;
- benchmark de custo marginal da largura de ação;
- one-raise com bet fixo + raise-to;
- exact BR one-raise auditada contra brute force;
- multi-size + one-raise;
- custo enumerativo explicitado;
- Dynamic Exact Best Response por programação dinâmica;
- DP BR gated contra enumerador;
- scalable 1..4 sizings + one raise;
- private-state abstraction lab;
- policy abstrata expandida e julgada no jogo original não abstraído;
- identity bucket equivalence;
- single bucket;
- showdown-category;
- conditional equity quantiles blocker-aware;
- exact range equity;
- universal equity;
- nutness;
- blocked range weight;
- blocked stronger range weight;
- equity+nutness+blocker Borda features;
- uniform-reference counterfactual value vectors;
- deterministic CFV k-medoids;
- six-texture River Benchmark Battery;
- separate mapping-build cost;
- State-Abstraction Convergence;
- cumulative checkpoints;
- cumulative wall-clock;
- exact exploitability/pot at checkpoints;
- synchronous Regret-Matching+;
- nonnegative regret clipping;
- average strategy delay/weighting;
- deterministic/resumable solver runs;
- CFR vs RM+ benchmark under same oracle;
- Ryzen Benchmark Suite **v3**;
- action abstraction + scalable multi-size raise + state battery + state convergence + solver algorithms + simulator throughput em um manifest;
- SHA-256 verification de todo JSON/log antes da análise;
- Pareto somente entre objetos matematicamente comparáveis;
- v1/v2 manifest backward compatibility;
- end-to-end suite/analyzer smoke no CI.

## Próximo gate imediato desta fase

Na máquina Ryzen:

```text
python tools/run_ryzen_benchmark_suite.py --profile engineering
```

Depois:

```text
python tools/analyze_ryzen_benchmark_suite.py benchmark_runs/<RUN> --output analysis.json
```

A suite v3 também mede 2/4/6-player simulator hands/s e decisions/s no mesmo manifest; esses números são capacity evidence e permanecem separados de exploitability/strategy quality.

## Falta para F4 PASS

- primeira engineering run real;
- repetir candidatos próximos da fronteira;
- escolher/rejeitar CFV vs equity/blocker baselines;
- escolher CFR vs RM+ por erro por wall-clock;
- equal-wall-clock battery somente se os dados mostrarem necessidade;
- multiple raise sizes;
- re-raise layer se comprar qualidade suficiente;
- board-texture sensitivity;
- stack-to-pot sensitivity;
- skewed/weighted ranges;
- out-of-fixture generalization;
- memory per million infosets;
- multi-core throughput no Ryzen;
- long-run serialization/resume;
- regressão matemática entre commits;
- substituir ranges sintéticos por distribuições provenientes do próprio simulador conforme F2 amadurecer.

**Gate de saída:** família de action/state abstraction + solver escolhida por evidência reproduzível no Ryzen.

---

# Fase 5 — Primeiro solver multi-street / Blueprint HU

**Status: NOT STARTED**

## Objetivo

Resolver decisões conectadas entre preflop, flop, turn e river, usando os contracts reais do simulator em vez de um river lab isolado.

## Falta fazer

- public-state representation multi-street;
- chance transitions compatíveis com simulator;
- canonicalização entre streets;
- stack/pot/to-call/min-raise/SPR features;
- preflop limp/raise/jam tree;
- postflop bet/check/raise/re-raise action abstraction;
- sizing sets dependentes de SPR/public state;
- private abstraction por street;
- bucket transition/refinement;
- terminal utility adapter da F3;
- solver escolhido na F4;
- chance/external/outcome sampling se justificado;
- deterministic seeds;
- checkpoint/resume;
- compression/serialization;
- exact local subgames como auditoria;
- held-out boards/ranges/stacks;
- benchmark por CPU-hour;
- blueprint HU inicial;
- simple-policy baseline para medir ganho.

**Gate de saída:** blueprint HU preflop→river supera baselines fora do treino, com erro, custo, coverage e reprodução medidos.

---

# Fase 6 — Multiway 3, 4, 5 e 6 jogadores

**Status: NOT STARTED**

## Objetivo

Cobrir a parte estruturalmente mais difícil do target: cash 6+ multiway, com folds, all-ins, side pots, stacks e rake.

## Falta fazer

- multi-player public/private state representation;
- fold/elimination order;
- asymmetric stacks;
- 2..6-player starting configurations;
- side pots no solver/utility;
- all-in chance runouts;
- valid positional/chair symmetries only;
- multiplayer regret/learning method apropriado;
- NashConv/exploitability surrogate apropriada ao setting;
- non-constant-sum rake utility;
- sparse/adaptive traversal;
- reach/EV/error-based state prioritization;
- progressive HU -> 3w -> 4w -> 5w -> 6w expansion;
- stack/pot curriculum;
- player-count cross-validation;
- memory-pressure benchmark;
- shard layout para months-long runs;
- cross-seat fairness/invariance tests;
- policies robustas a player count variável no meio de sessões.

**Gate de saída:** política multiway robusta e avaliada para 2..6 jogadores sem usar equivalências falsas com HU.

---

# Fase 7 — Estratégia-base completa e treinamento longo no Ryzen

**Status: NOT STARTED**

## Objetivo

Transformar a arquitetura vencedora em um blueprint amplo usando semanas/meses de CPU de forma recuperável e mensurável.

## Falta fazer

- coverage target de stacks/player counts/stakes;
- CPU/RAM/disk budget;
- scheduler de jobs;
- deterministic shard manifests;
- resumability após reboot/falha;
- checkpoint integrity hashes;
- prioritized state refinement;
- error/coverage heatmaps;
- rare-but-high-EV resampling;
- held-out validation states;
- periodic frozen checkpoints;
- rollback de regressões;
- artifact compaction;
- policy distillation somente se comprar memória/latência sem perda relevante;
- final blueprint selection por out-of-sample suites;
- monitorar ganho marginal por CPU-hour e interromper regiões saturadas.

**Gate de saída:** blueprint amplo com coverage/força mensurados e artifacts reproduzíveis prontos para runtime.

---

# Fase 8 — Population model e exploração separada

**Status: NOT STARTED / OPTIONAL PARA PRIMEIRO AGENTE FORTE**

A estratégia-base precisa funcionar sem exploração. Exploit overlay nunca pode ser requisito para segurança funcional.

## Fontes válidas para o target

- populações sintéticas no simulador;
- pools de agents frozen;
- historical self-play checkpoints;
- datasets offline/permitted quando existirem.

## Falta fazer

- opponent/population schema;
- frequencies por abstract state/action;
- confidence intervals;
- shrinkage/Bayesian fallback;
- archetypes/clusters;
- sizing tendencies;
- preflop/postflop deviations;
- bounded exploit policy;
- automatic fallback to base policy;
- out-of-sample evaluation;
- adversarial robustness;
- anti-overfit limits;
- separated `base_policy` and `exploit_overlay` artifacts.

**Gate de saída:** ganho out-of-sample demonstrado sem regressão grave de robustez.

---

# Fase 9 — Policy compiler e runtime do agente

**Status: NOT STARTED**

## Falta fazer

- versioned policy file format;
- rules/economy/solver metadata;
- canonical state key;
- exact/abstract lookup;
- action distribution retrieval;
- deterministic RNG por decision token quando sampling for usado;
- uncovered-state fallback;
- cache/memory mapping;
- startup hash validation;
- corruption detection;
- load-time compatibility gate;
- p50/p95/p99 query latency;
- timeout/fail-closed behavior;
- explain/decision trace;
- byte-for-byte replay da query;
- runtime↔simulator version contract;
- policy hot/cold loading apenas se necessário.

**Gate de saída:** `SimulatorObservation -> canonical state -> audited action distribution` dentro do latency budget e reproduzível.

---

# Fase 10 — Agente autônomo em closed loop no simulador

**Status: NOT STARTED, embora F2 já prove closed-loop com policies de teste**

Aqui o agente passa a usar a **policy estratégica treinada**, não baselines mecânicos de validação.

## Falta fazer

- agent interface ligada ao policy runtime;
- self-play seat assignment;
- policy-vs-policy tables;
- policy-vs-baseline tables;
- full cash sessions;
- bankroll/session accounting;
- rebuy/top-up/session policy escolhida;
- simultaneous workers;
- deterministic worker seed schedule;
- crash/restart recovery;
- bad state fail-closed;
- corrupted/stale policy rejection;
- deterministic session replay;
- long soak;
- millions-of-hands stability;
- decision-latency monitoring;
- transcript sampling on errors/outliers.

**Gate de saída:** a IA estratégica joga autonomamente sessões longas completas 2..6 no simulador sem erro de estado/ação/accounting.

---

# Fase 11 — Certificação de força e release

**Status: NOT STARTED**

## Falta fazer

- baseline tournaments;
- frozen-policy A/B;
- exact/local solver cross-check in tractable subgames;
- strategy invariance audit;
- exploitability/NashConv proxies onde válidos;
- head-to-head confidence intervals;
- multiway evaluation protocol;
- GGPoker-rake-aware win-rate simulation;
- bankroll/variance simulation;
- stress 2..6 players;
- stress por stack depth;
- stress por economy profile/stake;
- rare-state audit;
- adversarial action sequence audit;
- latency/memory/disk stress;
- restart/resume certification;
- version rollback;
- independent deterministic replay audit;
- reproducibility package;
- final release manifest;
- freeze dos hashes de rules/economy/settlement/policy/runtime.

**Gate de saída final:** somente aqui o projeto recebe:

```text
READY FOR 6+ AUTONOMOUS SIMULATOR
```

---

# Trilha auxiliar A — OpenHoldem6Plus / observação de cliente

**Status: PARTIAL AVANÇADO — preservada, fora do caminho crítico**

## Já feito

- repo operacional `pmartins87/myoh_private`;
- branch dedicada `deepsix_6plus`;
- provenance/upstream pin;
- migration map 52-card/SB-BB/1326/2652/prwin/dealposition;
- `ShortDeckRules` C++;
- `TableObservation`/validator/JSON;
- `RawTableSnapshot` read-only;
- raw schema v2;
- myturnbits/sitting-in como evidência;
- Python mirror;
- cross-repo C++ -> JSON -> Python contract;
- stable-frame gate;
- conservative raw timeline;
- exact CALL/short-call/RAISE_TO inference quando unambiguous;
- refusal to invent CHECK/FOLD;
- hand-start baseline/epochs;
- observe/replay-first architecture;
- dedicated CI.

## Se retomarmos no futuro

Faltariam target-specific tablemap/layout, animation timing, exact CHECK/FOLD evidence, UI/session details, build/soak e outros itens. Nada disso bloqueia `READY FOR 6+ AUTONOMOUS SIMULATOR`.

---

# Trilha auxiliar B — Evidência externa de GGPoker

**Status: OPTIONAL**

Pode melhorar a fidelidade de futuras versões de rules/economy, mas não bloqueia o profile v1 porque as convenções do simulador são explícitas e versionadas.

Útil para:

- mudanças futuras de rake/caps/BBJ;
- live-client min-raise/reopen comparison;
- optional features;
- production rounding comparison;
- ranking/rule documentation changes.

Qualquer alteração semântica gera profile novo; runs v1 continuam reproduzíveis.

---

# Onde estamos agora

```text
F0  Rules/economy contract v1          PASS       ██████████
F1  Core matemático                    PASS       ██████████
F2  Simulador multiagente              PARTIAL+   ████████░░
F3  Economia/settlement/utility        PARTIAL+   ████████░░
F4  Lab abstração/solver               IN PROG    ████████░░
F5  Blueprint HU multi-street          NOT START  ░░░░░░░░░░
F6  Multiway 3-6                       NOT START  ░░░░░░░░░░
F7  Treino longo blueprint             NOT START  ░░░░░░░░░░
F8  Population/exploit                 OPTIONAL   ░░░░░░░░░░
F9  Policy compiler/runtime            NOT START  ░░░░░░░░░░
F10 Agente estratégico closed-loop     NOT START  ░░░░░░░░░░
F11 Certificação/release               NOT START  ░░░░░░░░░░
A   OH6Plus/real-client observation    SIDE       ███████░░░
B   External GGPoker validation        OPTIONAL   ███░░░░░░░
```

As barras representam maturidade aproximada da fase, não percentual matemático do projeto.

## Leitura correta

Já existe um ambiente que distribui cartas, recebe decisões de múltiplos agents, percorre preflop/flop/turn/river, resolve all-ins/side pots, aplica a economia GGPoker-reference, produz gross/net utility, atualiza stacks, reproduz a mão por transcript/seed e consegue persistir/reiniciar sessões. Existe também um harness de soak determinístico, crash-safe e shardable cuja identidade global não depende do número de workers.

Ainda não temos a IA estratégica final. O principal artefato faltante continua sendo o blueprint multi-street/multiway. F2 precisa produzir evidência de long-soak/throughput real; F4 precisa produzir a primeira evidência real da máquina Ryzen; então F5 pode começar sobre uma base empiricamente escolhida.

---

# Caminho crítico atual

```text
A. F2 simulator certification
   crash-safe deterministic soak infra      DONE
    -> randomized pot-layer matrix          DONE
    -> larger/long soak                     NEXT
    -> target-machine throughput/memory     NEXT
    -> adversarial short-all-in/reopen

B. F4 architecture decision
   benchmark suite v3 + analyzer            DONE
    -> Ryzen engineering run                NEXT
    -> repeat close Pareto candidates
    -> freeze solver/action/state family

C. F3 utility/economy
   gross + net per-seat utility              DONE
    -> 9-stake/player-count golden matrix   DONE
    -> rake-aware strategy baseline
    -> long-run utility accounting

D. F5/F6 strategy
   HU multi-street
    -> 3-way
    -> 4-way
    -> 5/6-way

E. F7/F9/F10
   long blueprint training
    -> policy compiler
    -> strategic closed-loop self-play
    -> certification
```

## Próximos gates imediatos

1. executar o Ryzen `--profile engineering` e preservar a pasta completa de evidência;
2. executar um soak de escala relevante (começando por 100k/1M, conforme throughput medido) e preservar `checkpoint.json/result.json`;
3. gerar stress adversarial de short-all-in/reopen e 6-way asymmetric stacks;
4. analisar Pareto e repetir candidatos próximos antes de congelar F4;
5. iniciar F5 HU multi-street somente sobre a família de solver/abstração escolhida pelos dados.

Uma run de semanas/meses só começa quando F4 escolher a arquitetura por evidência e F2/F3 estiverem suficientemente estáveis para que o trainer não aprenda sobre um ambiente contabilmente errado.
