# DeepSix — Roadmap canônico até `READY FOR 6+ AUTONOMOUS SIMULATOR`

Última atualização estrutural: **26/08/2026**.

Este documento mede **capacidade validada**, não quantidade de código. `PASS` exige gate reproduzível. Implementações novas permanecem `PARTIAL/PENDING CI` até o workflow correspondente fechar.

## Objetivo final congelado

> **Construir a IA de Cash Game 6+ / Short Deck mais forte que conseguirmos dentro de um orçamento computacional realista, capaz de jogar sessões completas 2..6 jogadores no nosso próprio simulador, com economia GGPoker-reference versionada e treinamento principal dimensionado para um Ryzen 9.**

A cadeia crítica é:

```text
rules/economy/settlement/utility versionados
 -> Core matemático exato
 -> Simulator 2..6 reproduzível
 -> state/reach/chance reference oracles
 -> action/state abstraction escolhida por benchmark
 -> solver family escolhida por evidência Ryzen
 -> HU multi-street blueprint
 -> multiway 3..6
 -> treino longo/adaptive refinement
 -> policy compiler/runtime
 -> strategic closed loop
 -> certificação
 -> READY FOR 6+ AUTONOMOUS SIMULATOR
```

## Princípios arquiteturais congelados

- **GGPoker é referência econômica, não ambiente de execução.**
- **O ambiente primário é o DeepSixSimulator.**
- Estado exato continua autoritativo. Buckets/embeddings/compressão pertencem ao boundary de policy/training.
- Invariâncias exatas são eliminadas por construção; equivalências aproximadas precisam de benchmark.
- `SolverExperimentProfile` identifica toda experiência estratégica relevante: rules/economy/settlement/utility, player count, stake/BBJ, stack/training distribution, state representation, action abstraction, solver family e objective.
- `GROSS_POKER_DELTA` e `NET_CASH_DELTA` são objetos matematicamente diferentes. Rake nunca é escondido por renormalização.
- Long run só começa depois de state/action/utility suficientemente congelados.
- Worker count não pode mudar a identidade semântica de uma linhagem estocástica. Streams independentes podem paralelizar; a mesma linhagem permanece serial até prova em contrário.
- SpinCore é referência de engenharia e metodologia. Nenhuma semântica, arquitetura neural ou conclusão estratégica é importada automaticamente.
- Deep CFR não é vencedor presumido. Sampling precisa justificar sua complexidade antes de neuralização.
- Ganho é julgado por força/erro/cobertura **por CPU-hora e memória**, não por sofisticação aparente.

---

# Fase 0 — Contrato do jogo e alvo econômico

**Status: PASS — Simulator Profile v1**

Congelado:

- deck 36 cartas, ranks 6..A;
- duas hole cards + cinco community cards; best-five Hold'em;
- 2..6 jogadores;
- Flush > Full House;
- A6789 como menor straight;
- Straight > Trips no profile atual;
- No-Limit;
- 1 ante por dealt player e Dealer/Button total 2 antes;
- ação começa no primeiro dealt seat à esquerda do Dealer e termina no Dealer em todas as streets;
- unidade publicada da stake mapeada para 1 ante no simulator v1;
- preflop initial full-raise increment = 2 antes;
- postflop minimum bet / initial full-raise increment = 2 antes;
- short all-in exato permitido abaixo do minimum full raise;
- reopen v1 `CUMULATIVE_FULL_RAISE`;
- odd chip v1 ao primeiro tied winner à esquerda do Dealer, seguindo clockwise;
- EV Cashout/RIMT fora da árvore-base v1;
- BBJ como camada econômica versionada separável.

Economia `ggpoker_shortdeck_cash_2026-08-16_v1`:

- 5% rake;
- 9 stakes de $0.02 a $10;
- default buy-ins;
- caps 2/3/4/5+ jogadores;
- high-stakes caps convertidos exatamente por stake;
- BBJ Short Deck = 1 ante a partir do threshold de 100 antes;
- simulator settlement v1 usa floor para converter rake fracionário à unidade monetária inteira;
- nenhum exemption/rounding adicional foi inventado.

Mudança semântica futura cria **novo profile**, preservando reprodução de runs antigas.

---

# Fase 1 — Core matemático Short Deck

**Status: PASS — fundação; manutenção contínua**

Gated:

- codec compacto 0..35 e rejeição de ranks 2..5;
- 81 starting-hand classes / 630 combos;
- evaluator 5/6/7 cartas;
- auditoria exaustiva de 376.992 mãos de cinco cartas;
- contagens analíticas por categoria;
- PokerKit independente pinado;
- evaluator C++ baseline e lookup exato/rápido;
- paridade Python ↔ C++;
- equity HU exata de referência;
- `FOLD/CHECK/CALL/RAISE_TO`;
- betting-round state machine;
- full raise, short all-in e reopen policies;
- full-hand state machine preflop→river;
- all-in auto-runout/dry side-pot handling;
- chip conservation;
- main/side pots e showdown exato por layer;
- exact `Fraction` gross splits no Core;
- canonicalização de hole order, flop order, 24 suit permutations e chairs relativos ao Dealer;
- action history/sizing preservados quando estrategicamente distintos;
- ReplayFrame/DecisionToken/fingerprints;
- fuzzing determinístico;
- randomized pot-layer conservation.

Python permanece correctness oracle. Hot paths nativos só são promovidos após paridade.

---

# Fase 2 — DeepSixSimulator multiagente

**Status: PARTIAL AVANÇADO — funcional/crash-safe; long-soak e target-machine evidence abertos**

Implementado/gated:

- `SimulatorRulesProfile` versionado;
- `SimulatedHand` com deck físico real de 36 cartas e seed explícita;
- deal round-robin, 2..6 players, sparse physical seats e stacks assimétricos;
- seat-local private observation; opponent holes ausentes do contract;
- legal actions apenas ao actor correto e out-of-turn fail-closed;
- flop/turn/river automáticos e all-in runout;
- `play_to_terminal()`;
- `DeepSixTable` com stacks persistentes e Dealer rotation;
- table snapshot/restore e continuação idêntica ao uninterrupted path;
- `DeepSixEnv.reset/observe/legal_actions/step`;
- observation canonical JSON + SHA-256;
- terminal transcript com seed/private-deal/settlement digests;
- exact transcript replay;
- session results/fingerprint/conservation;
- `SimulatorSoakPlan` com global seed/index schedule independente da topologia de shards;
- atomic checkpoint + resume + `failure.json`;
- periodic exact replay sampling;
- throughput/peak-memory instrumentation;
- 5.000 randomized pot-layer accounting cases;
- 17.688 generated cumulative-short-all-in/reopen sequences;
- 400 deterministic six-way asymmetric-stack stress hands com ações aleatórias legais e replay periódico;
- shard-topology invariance.

Falta para F2 PASS:

- long soak de escala relevante sem divergence;
- hands/s, decisions/s e peak memory na máquina-alvo;
- expandir 6-way stress se o long soak indicar;
- transcript-retention policy para milhões de mãos;
- multiprocess/batch somente se profiling mostrar ROI;
- join/leave/sit-out/rebuy/top-up apenas se o modelo de sessão final exigir.

**Gate:** runs longas 2..6 reproduzíveis, zero accounting/state/replay divergence e custo medido.

---

# Fase 3 — Economia, settlement e utility

**Status: PARTIAL AVANÇADO — camada v1 gated; strategy/long-run evidence aberta**

Implementado/gated:

- rational `RakeConfig`/`Fraction` calculations;
- GGPoker 5% + player-count cap;
- nove stakes/default buy-ins/caps;
- BBJ separável;
- integer odd-chip settlement v1;
- deterministic pro-rata/largest-remainder house-charge allocation;
- exact fractional rake + floor integer settlement v1;
- post-hand bankroll conservation;
- `SimulatorUtilityVector` por seat;
- gross poker delta e net cash delta;
- exact ante normalization;
- `sum(gross)=0`;
- `sum(net)=-(rake+BBJ)`;
- 9-stake/player-count golden matrix;
- cap-transition e BBJ-threshold regressions.

Falta:

- rake-aware strategic baselines;
- long-run utility/accounting statistics;
- escolher quais economy profiles entram no blueprint principal;
- declarar em cada treino se o objetivo é gross zero-sum ou net cash, sem misturar garantias.

---

# Fase 4 — Laboratório de ação, estado e solver

**Status: IN PROGRESS / READY FOR PRIMEIRA EVIDÊNCIA RYZEN**

## Já construído

- Kuhn CFR com valor/exploitability conhecidos;
- Short Deck river microgames com ranges/evaluator reais;
- brute-force exact BR e Dynamic Exact BR;
- 1..4 bet sizings;
- one-raise e multi-size + one-raise;
- private-state abstraction lab;
- identity/single/showdown-category/equity baselines;
- blocker/nutness/range features;
- CFV k-medoids;
- six-texture River Benchmark Battery;
- State-Abstraction Convergence;
- synchronous Regret-Matching+;
- CFR × RM+ sob mesmo exact oracle;
- **external-sampling MCCFR** como terceira família candidata;
- same-seed determinism;
- exact stochastic checkpoint contendo RNG + regrets + strategy sums;
- checkpoint/resume == uninterrupted run;
- fresh-process / diferente `PYTHONHASHSEED` semantic reproduction;
- `TrainingStreamScheduler` com uma active iteration por lineage, durable receipt, parent SHA-256 e atomic checkpoint;
- `SolverExperimentProfile` hashável;
- exact `PrivateReachVector` / `PublicReachState`;
- public-action likelihood multiplica somente o reach privado do actor;
- explicit blocker/card-compatible joint mass para pequenos supports;
- direct-public-history vs factorized-reach parity;
- Ryzen Benchmark Suite v3 + SHA verification + analyzer/Pareto;
- simulator throughput no mesmo manifest, separado de strategy quality;
- `SPINCORE_SOLVER_TRANSFER_AUDIT.md`;
- `SOLVER_ARCHITECTURE_PRECOMMIT_V1.md`.

## Transferência SpinCore congelada

Aproveitado:

- exact-state vs lossy-boundary separation;
- exact symmetry governance;
- external sampling como candidato;
- stochastic stream determinism;
- atomic checkpoint/hash lineage;
- equal-compute causal controls;
- Phase2C0/C1 como evidência de viabilidade estrutural de range/reach;
- Phase2C2 como evidência negativa: correção estrutural de reach **não** prova melhora de target neural.

Não copiado:

- deck 52-card / 169 classes;
- ICM/tournament utility;
- 3-seat assumptions;
- action-head width do SpinCore;
- incumbent neural representation;
- Phase2C2 neural target candidate;
- qualquer suposto architecture winner.

## Gate Ryzen imediato

```text
python tools/run_ryzen_benchmark_suite.py --profile engineering
python tools/analyze_ryzen_benchmark_suite.py benchmark_runs/<RUN> --output analysis.json
```

Depois:

- repetir Pareto-close candidates;
- multiple independent seeds para sampling candidato;
- equal-wall-clock se ainda houver empate material;
- congelar primeira action abstraction;
- congelar primeira state abstraction;
- escolher solver family por erro/força por CPU-hora e memória.

Deep CFR só entra se sampling sem rede mostrar benefício que possa justificar a complexidade neural.

---

# Fase 5 — Blueprint HU multi-street

**Status: FOUNDATION IN PROGRESS — referência exata já atravessou a fronteira river-only; produção depende do gate Ryzen**

Esta fase deixou de ser `NOT STARTED`. O solver de produção ainda não foi escolhido, mas o **reference stack solver-independent** já está sendo construído para que a família vencedora entre sobre uma semântica auditada.

## Reference foundation implementada

### 1. Exact public/private strategic identity

`multistreet_state.py`:

- `PublicDecisionState` separado de `PrivateDecisionState`;
- public board canonicalizado antes das hole cards;
- 24 suit permutations globais;
- somente o residual stabilizer do board pode canonicalizar a mão privada;
- chairs relativos ao Dealer;
- exact stack/commitment/current-bet/raise geometry/action history;
- public fingerprint não depende de opponent private cards;
- `decision_state_from_components()` desacopla identidade estratégica do container `SimulatedHand`;
- simulator wrapper e explicit branch precisam produzir fingerprints idênticos.

### 2. Deterministic replay/fork oracle

`multistreet_reference.py`:

- reconstrói seed + starting stacks + public action history;
- verifica raw state/private deal/canonical fingerprints;
- permite fork de ações sem modificar parent;
- serve de oracle lento contra traversal otimizado futuro.

### 3. Exact fixed-private board chance

`multistreet_chance.py`:

- `C(32,3)=4.960` flops HU com quatro hole cards fixas;
- 29 turns e 28 rivers HU;
- 2.024/21/20 para 6-way com 12 hole cards fixas;
- `Fraction` probability sum exatamente 1;
- flop como reveal simultâneo não ordenado; turn/river preservam ordem temporal.

### 4. Exact private reach

`reach.py`:

- per-seat reach vectors;
- exact public-action likelihood update;
- explicit blocker compatibility;
- exact joint mass/assignment count para supports tratáveis;
- incremental factorization == direct full-history weight.

### 5. Range-weighted chance

`multistreet_range_chance.py`:

```text
P(reveal | public history, fixed private)
 = compatible reach mass after reveal
   / compatible reach mass before reveal
   / physical reveals per private assignment
```

Isso torna a chance pública corretamente condicionada ao card removal dos ranges desconhecidos. Um public action que repondera o range pode mudar exatamente a distribuição marginal de turn/river.

### 6. Explicit action/chance branch state

`multistreet_branch.py`:

- immutable `ExactBranchState`;
- `DECISION / CHANCE / TERMINAL` explícitos;
- action transition reutiliza `apply_hand_action`;
- chance transition reutiliza `deal_next_board`;
- terminal reutiliza `settle_terminal_hand`;
- private-card-as-board collision fail-closed;
- múltiplos children podem nascer do mesmo chance parent;
- seeded simulator path e explicit branch path são comparados raw-state por raw-state e settlement por settlement.

### 7. Primeiro HU multi-street reference game

`hu_multistreet_reference.py`:

- tiny exact HU imperfect-information evaluator;
- passive deterministic preflop line apenas para fixar um root pequeno;
- flop configurável;
- estratégia real em flop→turn→river;
- private ranges condicionados ao flop e joint-deal probabilities exatas;
- action abstraction solver-neutral v1:
  - checked-to: `CHECK` ou `BET_MIN`;
  - facing-bet: `FOLD` ou `CALL`;
  - sem re-raise;
- exact future chance;
- policy vê somente `PrivateDecisionState` do actor;
- explicit gross ou net objective;
- expected gross utility deve somar 0;
- expected net utility deve somar `-E[house deduction]`;
- deterministic check/call, min-bet/call e uniform policies como instrumentos de gate, não estratégia final.

## Estado de validação desta fundação

- exact fixed-private board chance: **CI #230 PASS**;
- range-weighted chance, explicit branch, component strategic-state parity e HU reference game: **implementados no `main`; workflows subsequentes ainda aguardando execução no momento desta atualização**.

Nenhum item pendente de CI é promovido a PASS antes do workflow fechar.

## Próximos gates F5

1. fechar os workflows atuais e corrigir qualquer divergência sem relaxar invariants;
2. adicionar solver tabular adapter ao HU reference game **somente com gross zero-sum objective para as garantias CFR**;
3. comparar CFR/RM+ e, se útil, sampling nesse mesmo jogo sob oracles idênticos;
4. tornar preflop estratégico em um tiny-support game depois do loop postflop estar gated;
5. introduzir sizing/re-raise progressivamente, medindo custo marginal;
6. usar F4 Ryzen evidence para escolher o production solver/action/state family;
7. montar primeiro blueprint HU amplo preflop→river;
8. held-out boards/ranges/stacks + CPU-hour benchmark + checkpoint/resume.

**Gate F5:** blueprint HU supera baselines fora do treino, com custo, erro, coverage e reprodução medidos.

---

# Fase 6 — Multiway 3, 4, 5 e 6 jogadores

**Status: NOT STARTED — small-support reach/chance oracles já preparados**

Falta:

- multi-player public/private solver state;
- progressive HU→3w→4w→5w→6w;
- asymmetric stacks/training distribution;
- folds/all-ins/side pots na traversal;
- scalable joint-private sampling/factorization;
- toda aproximação de joint reach provada contra exact small-support oracle;
- non-constant-sum rake utility;
- multiplayer regret/learning method apropriado;
- NashConv/unilateral-BR/exploitability surrogate apenas onde matematicamente válido;
- adaptive reach/EV/error prioritization;
- memory/sharding/cross-seat invariance.

HU exploitability não será apresentado como certificado falso de multiway cash.

---

# Fase 7 — Treinamento longo / blueprint amplo

**Status: NOT STARTED — lineage/checkpoint primitives já existem**

Falta:

- coverage target de stacks/player counts/stakes;
- CPU/RAM/disk budget;
- production scheduler da família vencedora;
- deterministic shard manifests;
- reboot/failure resume;
- artifact SHA/parent lineage;
- prioritized refinement;
- error/coverage heatmaps;
- rare/high-EV resampling;
- held-out validation;
- periodic frozen checkpoints/rollback;
- artifact compaction;
- policy distillation somente se comprar memória/latência sem perda material;
- stop rules por ganho marginal/CPU-hour.

---

# Fase 8 — Population model / exploração

**Status: OPTIONAL / NOT STARTED**

A base policy precisa ser robusta sem exploit overlay.

Fontes válidas: synthetic populations, frozen-agent pools, historical self-play checkpoints e datasets offline/permitted quando existirem.

Falta opponent schema, confidence/shrinkage, archetypes, bounded exploitation, automatic fallback, out-of-sample gain e anti-overfit gates.

---

# Fase 9 — Policy compiler/runtime

**Status: NOT STARTED**

Falta:

- versioned policy format + embedded experiment identity;
- canonical/abstract lookup;
- deterministic action RNG quando sampling;
- uncovered-state fallback;
- cache/mmap;
- startup hash/version validation;
- corruption detection;
- p50/p95/p99 latency;
- fail-closed timeout;
- explain/decision trace;
- byte-for-byte replay da query.

---

# Fase 10 — Agente estratégico closed-loop no simulator

**Status: NOT STARTED — F2 já prova closed loop apenas com policies mecânicas de validação**

Falta conectar a policy treinada, self-play tables, policy-vs-baseline, sessões cash, deterministic worker seeds, restart recovery, stale/corrupt policy rejection, long soak e millions-of-hands stability.

---

# Fase 11 — Certificação/release

**Status: NOT STARTED**

Falta:

- frozen-policy tournaments/A-B;
- exact local-solver audits;
- invariance audit;
- valid exploitability/NashConv/unilateral-BR metrics;
- confidence intervals;
- multiway protocol;
- rake-aware win-rate/variance simulation;
- stress player-count/stack/economy/rare states;
- latency/memory/disk/restart certification;
- independent deterministic replay;
- reproducibility package + release manifest;
- freeze de hashes rules/economy/settlement/utility/experiment/policy/runtime.

Somente depois:

```text
READY FOR 6+ AUTONOMOUS SIMULATOR
```

---

# Trilha auxiliar A — OpenHoldem6Plus / client observation

**Status: SIDE / PARTIAL AVANÇADO — fora do caminho crítico**

Preservado:

- `myoh_private` branch dedicada;
- provenance/upstream pin;
- 52-card/SB-BB/1326/2652/prwin/dealposition migration map;
- C++ `ShortDeckRules`;
- TableObservation/validator/JSON;
- read-only raw snapshot v2;
- C++→JSON→Python contract;
- stable-frame gate;
- conservative temporal reconstruction;
- exact CALL/short-call/RAISE_TO inference quando unambiguous;
- hand-start epochs;
- observe/replay-first architecture.

Isso pode apoiar estudo/replay/validação externa; não bloqueia o produto de simulator.

---

# Trilha auxiliar B — Evidência externa GGPoker

**Status: OPTIONAL**

Usada para futuras mudanças de rake/caps/BBJ/rules/rounding. Toda alteração semântica gera profile novo; v1 permanece reproduzível.

---

# Trilha de referência C — SpinCore solver engineering

**Status: ACTIVE RESEARCH INPUT / NÃO DEPENDÊNCIA**

Continua servindo para transferir disciplina de solver, exact range/reach, stochastic lineage, checkpointing e metodologia causal. DeepSix não depende de SpinCore em runtime e não herda seus assumptions de jogo.

---

# Estado resumido

```text
F0  Rules/economy contract v1          PASS        ██████████
F1  Core matemático                    PASS        ██████████
F2  Simulator 2..6                     PARTIAL+    █████████░
F3  Economy/settlement/utility         PARTIAL+    ████████░░
F4  Action/state/solver lab            RYZEN NEXT  █████████░
F5  HU multi-street reference          IN PROG     ████░░░░░░
F6  Multiway 3-6                       NOT START   ░░░░░░░░░░
F7  Long blueprint training            NOT START   ░░░░░░░░░░
F8  Population/exploit                 OPTIONAL    ░░░░░░░░░░
F9  Policy compiler/runtime            NOT START   ░░░░░░░░░░
F10 Strategic autonomous simulator     NOT START   ░░░░░░░░░░
F11 Certification/release              NOT START   ░░░░░░░░░░
A   OH6Plus observation/replay         SIDE        ███████░░░
B   External GGPoker evidence          OPTIONAL    ███░░░░░░░
C   SpinCore solver reference          ACTIVE      ████████░░
```

As barras são maturidade aproximada, não percentual matemático do projeto.

## Caminho crítico imediato

```text
1. CI dos novos F5 reference gates
      ↓
2. Ryzen F4 engineering run + analysis
      ↓
3. long simulator soak / target-machine throughput
      ↓
4. freeze first action/state/solver family
      ↓
5. tabular solver on exact HU reference game
      ↓
6. strategic preflop + wider HU blueprint
      ↓
7. 3w→6w expansion
      ↓
8. long blueprint training
      ↓
9. policy runtime / strategic self-play
      ↓
10. certification
```

Não iniciaremos uma run de semanas/meses enquanto a arquitetura ainda puder mudar por evidência básica de F2/F4/F5.
