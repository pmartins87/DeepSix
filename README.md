# DeepSix

DeepSix é o projeto de IA para **Poker Cash Game 6+ / Short Deck**, desenvolvido para maximizar força prática dentro de um orçamento computacional realista.

## Objetivo primário

> **Uma IA autônoma capaz de jogar sessões completas 2..6 de 6+ dentro do nosso próprio simulador, com economia modelada a partir do GGPoker Short Deck e treinamento principal dimensionado para um Ryzen 9.**

GGPoker é referência econômica, não ambiente de execução. OpenHoldem6Plus/client observation permanece como trilha auxiliar de estudo/replay e não bloqueia o produto final.

Documentos principais:

- `docs/ROADMAP.md` — caminho canônico até `READY FOR 6+ AUTONOMOUS SIMULATOR`;
- `docs/SIMULATOR_TARGET_GGPOKER_ECONOMY_V1.md` — contrato econômico atual;
- `docs/SOLVER_ARCHITECTURE_PRECOMMIT_V1.md` — regras de promoção de arquitetura;
- `docs/SPINCORE_SOLVER_TRANSFER_AUDIT.md` — transferência source-first de engenharia do SpinCore.

## Princípio central

Não tentamos resolver o jogo completo de forma exata. O objetivo é maximizar **força/erro/cobertura por CPU-hora e memória**, usando exatidão onde ela compra correção e abstração/sampling onde a árvore explode.

Invariâncias verdadeiras são removidas por construção. Abstrações aproximadas precisam provar valor. Runs longas só começam depois de state/action/utility e solver family passarem pelos gates reproduzíveis.

## Estado atual

### F0/F1 — contrato + Core: PASS

Já estão gated:

- 36 cartas 6..A;
- 81 starting-hand classes / 630 combos;
- evaluator 5/6/7, A6789 e Flush > Full House;
- exhaustive audit das 376.992 mãos de cinco cartas + PokerKit oracle;
- C++ evaluator/lookup parity;
- legal actions e betting/full-hand state machines;
- full raises, short all-ins e reopen policies;
- main/side pots, showdown, chip conservation;
- exact suit/hole/flop/chair invariances;
- replay/fingerprints/fuzzing.

### F2 — Simulator: PARTIAL AVANÇADO

O simulador já executa mãos e sessões 2..6 com hidden-information boundary, exact legal actions, board chance, all-ins, settlement, transcript/replay, snapshot/restore, deterministic shards e crash-safe soak. Robustness gates incluem 5.000 randomized pot-layer cases, 17.688 short-all-in/reopen sequences e 400 deterministic six-way asymmetric-stack stress hands.

Falta principalmente long soak e throughput/memória reais na máquina-alvo.

### F3 — Economy/utility: PARTIAL AVANÇADO

O profile GGPoker-reference v1 contém 5% rake, nove stakes, caps por player count, default buy-ins e BBJ separado. Settlement inteiro e utility por seat preservam explicitamente:

```text
sum(gross poker delta) = 0
sum(net cash delta)    = -(rake + BBJ)
```

### F4 — Solver lab: pronto para a primeira decisão Ryzen

O torneio de arquitetura já contém:

- CFR;
- Regret-Matching+;
- external-sampling MCCFR;
- exact BR / Dynamic Exact BR;
- action-width experiments;
- state abstraction/bucket experiments;
- blocker/nutness/CFV features;
- exact stochastic checkpoint/restart;
- fresh-process reproduction;
- deterministic training-stream scheduler;
- exact per-seat private reach + blocker-compatible joint mass;
- Ryzen Benchmark Suite v3 + SHA/Pareto analyzer.

O próximo comando de evidência continua:

```text
python tools/run_ryzen_benchmark_suite.py --profile engineering
python tools/analyze_ryzen_benchmark_suite.py benchmark_runs/<RUN> --output analysis.json
```

Nenhum solver family é vencedor presumido. Deep CFR continua condicional à evidência.

### F5 — HU multi-street: FUNDAÇÃO EM CONSTRUÇÃO

O projeto já saiu do river-only. O `main` contém um stack de referência solver-independent:

- `multistreet_state.py` — exact public/private strategic identity;
- `multistreet_reference.py` — seeded replay/fork oracle;
- `multistreet_chance.py` — exact fixed-private board chance;
- `reach.py` — exact private reach / blocker-compatible joint mass;
- `multistreet_range_chance.py` — range-weighted marginal board chance;
- `multistreet_branch.py` — immutable explicit action/chance branching;
- `hu_multistreet_reference.py` — primeiro exact HU imperfect-information reference game cobrindo flop→turn→river, ranges privados, chance, canonical infosets e gross/net terminal utility.

O microgame v1 usa uma linha preflop passiva congelada e uma action abstraction deliberadamente pequena (`CHECK/BET_MIN` ou `FOLD/CALL`). Ele é um oracle para integrar/validar solvers, não a estratégia final.

`docs/ROADMAP.md` registra quais desses gates já têm CI verde e quais continuam aguardando workflow.

## Caminho até a IA final

```text
fechar F5 reference CI
 -> Ryzen F4 architecture evidence
 -> long F2 soak/performance
 -> freeze state/action/solver family
 -> solver tabular no exact HU reference game
 -> strategic preflop + HU blueprint amplo
 -> 3-way ... 6-way
 -> long adaptive training
 -> policy compiler/runtime
 -> strategic autonomous self-play
 -> certification
```

## Filosofia de engenharia

- correção antes de escala;
- source-first/evidence-first;
- exact state autoritativo;
- abstração somente com benchmark;
- custo real por CPU-hora;
- gross e net utility nunca confundidos;
- strategy-base separada de exploit overlay;
- checkpoint/restart e semantic identity desde antes das runs longas;
- nenhuma tecnologia é promovida apenas por ser mais nova ou mais complexa.
