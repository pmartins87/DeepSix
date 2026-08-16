# DeepSix

DeepSix é o projeto de IA para **Poker Cash Game 6+ / Short Deck**, desenvolvido para obter a maior força possível dentro de um orçamento computacional realista.

## Objetivo primário

O alvo atual é:

> **uma IA autônoma capaz de jogar sessões completas de 6+ dentro do nosso próprio simulador, com economia modelada a partir do GGPoker Short Deck e treinamento principal em um Ryzen 9.**

O projeto não depende de automatizar um cliente real para ser considerado concluído. GGPoker é a referência econômica; KKPoker permanece apenas como material histórico/comparativo de fases anteriores.

O contrato atual está em:

- `docs/ROADMAP.md` — roadmap canônico completo até `READY FOR 6+ AUTONOMOUS SIMULATOR`;
- `docs/SIMULATOR_TARGET_GGPOKER_ECONOMY_V1.md` — target/economia atual;
- `deepsix_core/ggpoker_economy.py` — profile econômico versionado.

## Princípio central

O objetivo não é resolver o jogo completo de forma exata. Queremos maximizar **força prática por CPU-hora**, sem desperdiçar capacidade de treino reaprendendo invariâncias que podem ser garantidas por construção.

O orçamento de referência é um **Ryzen 9 trabalhando continuamente por semanas ou meses**, com RAM/disco e pré-computação usados de maneira explícita e mensurada.

Cada aumento de complexidade precisa mostrar o que comprou em força, cobertura ou eficiência. Uma árvore maior não é promovida apenas por ser mais sofisticada.

## Arquitetura atual

1. **DeepSix Core** — deck, evaluator, regras, legal actions, betting/full-hand state machines, pot/side-pot accounting, canonicalização e replay.
2. **DeepSix Simulator** — ambiente multiagente 2..6 jogadores, chance, sessões, economia e self-play. Esta é a principal peça de ambiente ainda a concluir.
3. **Trainer/Solver** — CFR/RM+/abstrações e qualquer método posterior que vença benchmarks reproduzíveis.
4. **Economy** — profiles GGPoker versionados, rake/caps/BBJ e settlement.
5. **Policy Runtime** — compilação/lookup determinístico da estratégia treinada.
6. **Validation** — oracles exatos, fuzzing, invariance tests, held-out states, replay e certificação.
7. **OpenHoldem6Plus** — trilha auxiliar já bastante desenvolvida para observação/replay; não está no caminho crítico do simulador.

## Estado atual

### Core matemático

A fundação está fortemente gated:

- 36 cartas, ranks 6..A;
- 81 starting-hand classes / 630 combos;
- evaluator 5/6/7 cartas;
- A6789;
- Flush > Full House;
- exhaustive audit das 376.992 mãos de cinco cartas;
- oracle externo PokerKit;
- evaluator C++ baseline + lookup exato;
- equity HU exata;
- legal actions `FOLD/CHECK/CALL/RAISE_TO`;
- betting-round e full-hand state machines;
- all-ins, side pots e showdown;
- suit/hole/flop/chair canonicalization;
- deterministic replay/fingerprints;
- hand fuzzing.

### Economia GGPoker

`ggpoker_shortdeck_cash_2026-08-16_v1` codifica a tabela pública atual usada como referência do simulador:

- **5% rake**;
- nove stakes publicadas de $0.02 a $10;
- default buy-ins;
- caps distintos para 2 / 3 / 4 / 5+ jogadores;
- high-stakes caps publicados em BB convertidos exatamente por stake;
- Short Deck BBJ separado: **1 ante quando o pot alcança 100 antes**.

O profile não inventa no-flop/small-pot exemptions não publicadas na tabela usada e não inventa client rounding. Esses detalhes permanecem explicitamente versionados no simulator contract.

### Laboratório de solver

Já existem:

- Kuhn CFR baseline;
- Short Deck river microgames;
- exact brute-force BR para árvores pequenas;
- Dynamic Exact Best Response;
- 1..4 bet sizes;
- one-raise e multi-size + one-raise;
- private-state bucketed CFR;
- identity/equity/category/single abstractions;
- nutness/blocker features;
- CFV k-medoids;
- River Benchmark Battery v3;
- State-Abstraction Convergence v1;
- synchronous Regret-Matching+;
- CFR vs RM+ benchmarks;
- Ryzen Benchmark Protocol v2 + SHA-256 analyzer/Pareto.

O próximo benchmark estratégico relevante continua sendo:

```text
python tools/run_ryzen_benchmark_suite.py --profile engineering
```

## O que ainda separa o projeto da IA final

O trabalho pesado restante é transformar o core/laboratório em uma política ampla:

```text
DeepSixSimulator 2..6
 -> escolher abstraction/solver no Ryzen
 -> blueprint HU multi-street
 -> expansão 3-way até 6-way
 -> treino longo/refinement
 -> population/exploit overlay opcional
 -> policy compiler/runtime
 -> autonomous simulator closed loop
 -> certificação
```

O roadmap detalha todos os gates e subtarefas.

## OpenHoldem6Plus

O trabalho realizado não foi descartado. Já existem boundary C++/Python, raw snapshots, validators, conservative temporal reconstruction e contratos cross-repo. Essa trilha pode voltar a ser útil para estudo/replay/validação externa, mas **não é requisito para finalizar a IA de simulador**.

## Filosofia de engenharia

- correção antes de escala;
- evidência acima de intuição;
- invariâncias garantidas por construção;
- benchmark por custo real, não por aparência;
- estratégia-base separada da exploração;
- nenhuma run de meses antes de congelar state/action/utility suficientemente bem;
- nenhuma tecnologia é promovida apenas porque é mais nova ou mais complexa.
