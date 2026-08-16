# DeepSix

DeepSix é o projeto de estratégia para **Poker Cash Game 6+ / Short Deck**, desenvolvido para obter a melhor força de jogo possível dentro de um orçamento computacional realista.

## Princípio central

O objetivo **não é resolver o 6+ perfeitamente** nem provar equilíbrio exato do jogo completo.

O objetivo é:

> **construir a melhor estratégia que conseguirmos obter, validar e executar com segurança dentro das nossas possibilidades reais de hardware e tempo.**

O orçamento de referência é **um Ryzen 9 trabalhando continuamente por semanas ou meses**, com armazenamento e pré-computação extensivos quando úteis, mas sem assumir clusters ou hardware de datacenter.

DeepSix é julgado por força prática, robustez e ganho por CPU-hora. Uma abstração menor e profundamente treinada pode superar uma árvore enorme e superficial. Invariâncias matemáticas devem ser garantidas por construção para que capacidade de treino não seja desperdiçada reaprendendo equivalências triviais.

## Arquitetura

1. **DeepSix Core** — regras, deck, evaluator, pot accounting, ação legal, canonicalização, reconstrução e utilidade.
2. **Trainer/Solver** — CFR/regret/value/policy e demais técnicas que vencerem benchmarks reproduzíveis no orçamento real.
3. **OpenHoldem6Plus** — fork exclusivo do OpenHoldem para observar a mesa e formar estado confiável. Não precisa preservar compatibilidade estratégica com Hold'em 52-card, AoF, Spin ou OFC.
4. **Validation/Replay** — oracles independentes, fuzzing, replays, fingerprints, contratos cross-repo e auditorias de invariância.

Quando um conceito legado do OpenHoldem não possui a mesma semântica em 6+, ele deve ser substituído, desabilitado ou marcado como incompatível — nunca reaproveitado apenas para aparentar compatibilidade.

O roadmap canônico fica em `docs/ROADMAP.md`.

## Estado atual — 16/08/2026

A fundação matemática já é fortemente gated; o OpenHoldem6Plus possui boundary real C++ ↔ Python; a reconstrução temporal conserva incerteza em vez de inventar ações; a economia possui rake exato configurável sem arredondamento implícito; e o laboratório de solver já permite comparar **largura de ação, primeira camada de raise, abstração privada e algoritmo de regrets sob um oracle exato comum**.

### Regras atualmente congeladas

- deck com **36 cartas**, apenas 6..A;
- mesas até 6-handed;
- estrutura ante-based, sem modelar SB/BB como forced bets estratégicos;
- modelo atual de forced bets: A nos demais dealt players e **2A totais no Dealer/Button**;
- primeiro jogador à esquerda do Dealer age primeiro em todas as streets;
- No-Limit;
- Flush > Full House;
- A6789 é a menor sequência;
- full raise usa incremento pelo menos igual ao bet/raise anterior da street no modelo estrutural.

A documentação pública de rake do 6+ usa terminologia que ainda exige confirmação contra Hand Review/client. O Core não converte silenciosamente unidades ambíguas nem inventa rounding/timing. Essas pendências permanecem explicitamente abertas em `docs/GAME_SPEC_KKPOKER_V0.md` e `docs/RAKE_MODEL_V1.md`.

## Core matemático

Já existem e são testados:

- codec compacto 0..35 e rejeição obrigatória de ranks 2..5 na fronteira legada;
- **81 starting-hand classes cobrindo exatamente 630 combos**;
- evaluator de 5 cartas e best-of-5 para 5/6/7 cartas;
- A6789 e ranking Short Deck;
- enumeração de **todas as 376.992 mãos de cinco cartas** contra distribuição analítica;
- oracle externo PokerKit pinado;
- equity HU exata para validação;
- pot e side-pot accounting;
- legal-action boundary `FOLD/CHECK/CALL/RAISE_TO`;
- betting-round state machine No-Limit com full raises e short all-ins;
- full-hand state machine `forced bets -> preflop -> flop -> turn -> river -> showdown/fold`;
- runout automático quando não há mais decisão de betting;
- showdown bruto exato, mantendo splits como `Fraction` até odd-chip ser observado;
- canonicalização de hole-card order, flop order, 24 permutações globais de naipes e chairs relativos ao Dealer;
- `ReplayFrame`, `DecisionToken`, fingerprints e detecção de corrupção;
- fuzzing determinístico de mãos completas.

## Evaluator nativo

Há dois caminhos C++ gated:

- `ShortDeckEvaluator`, baseline auditável;
- `FastShortDeckEvaluator`, lookup exato de todas as combinações de cinco cartas.

O CI exige paridade do baseline C++ contra Python em todas as 376.992 mãos de cinco cartas e amostras determinísticas de seis/sete cartas. O lookup é comparado contra o baseline em todas as cinco-cartas + 10.000 seis-cartas + 20.000 sete-cartas.

Benchmarks do runner CI são apenas informativos e **não são extrapolados para o Ryzen 9**.

## OpenHoldem6Plus

O repositório operacional `pmartins87/myoh_private` possui a branch dedicada `deepsix_6plus`.

Já estão implementados/gated:

- migration map de premissas 52-card/1326/2652/prwin/SB-BB/dealposition;
- `ShortDeckRules` C++ independente;
- `TableObservation` + validator + JSON canônico;
- contrato C++ -> Python/Core com igualdade byte-a-byte/fingerprints;
- `RawTableSnapshot` read-only sobre `CTableState`/`CPlayer`/`Card`;
- schema raw v2 preservando `hero_myturnbits` e `hero_sitting_in` como **evidência**, não decisão;
- parser/espelho Python do snapshot bruto;
- workflow próprio da branch 6+;
- contrato cross-repo que compila o boundary C++ pinado e exige compatibilidade exata no Core.

**Nenhuma ação automática está habilitada no OpenHoldem6Plus.** A linha permanece deliberadamente `observe/replay-first` durante construção e validação.

## Reconstrução temporal conservadora

A cadeia atual é:

```text
RawTableSnapshot JSON
  -> validation
  -> ProjectedSnapshot
  -> StableSnapshotGate
  -> RawEvidenceTimeline
```

`RawObservationPipeline` compõe esse caminho end-to-end.

A timeline só infere uma ação quando o delta observado possui interpretação monetária única. Atualmente consegue inferir `CALL`, short all-in `CALL` e `RAISE_TO` exatos. Ela **não** inventa `CHECK` pelo desaparecimento de botões nem `FOLD` por mera mudança de flags; estados insuficientes permanecem `AMBIGUOUS`.

Um hand epoch só é estabelecido quando existe baseline exato de forced bets. Entre mãos, a confirmação exige regressão para preflop + mudança do Dealer + novo baseline exato. Uma ambiguidade invalida `complete_from_hand_start` até um novo início confiável ser provado.

Detalhes: `docs/RAW_EVIDENCE_TIMELINE_V1.md` e `docs/RAW_HAND_START_EVIDENCE_V1.md`.

## Economia / rake

`deepsix_core.rake` usa `Fraction` e separa explicitamente:

1. elegibilidade/isenções;
2. percentual/cap exatos;
3. **rounding do cliente ainda não comprovado**.

Rake variável não é simplesmente inserido em um microgame HU e chamado de exploitability zero-sum. Quando a retirada depende da trajetória/pot, a soma das utilidades varia; a metodologia econômica será tratada explicitamente antes do blueprint principal.

## Action abstraction

A progressão do laboratório é incremental:

- river microgame Short Deck com ranges/evaluator reais;
- 1..4 sizings iniciais sem raise;
- one-raise com bet fixo + raise-to fixo;
- multi-size + one-raise;
- exact BR enumerativa em árvores pequenas;
- **Dynamic Exact Best Response** por programação dinâmica, gated contra o enumerador;
- linha escalável de **1..4 sizings + um raise** usando exact DP exploitability.

Isso permite enriquecer a árvore sem deixar o custo do oracle crescer exponencialmente com `(1+S)6^S` planos puros por mão.

## Private-state abstraction

`BucketedRiverCFR` permite que combos exatos compartilhem um infoset, mas a política resultante é expandida novamente para cada combo e avaliada pela **best response exata do jogo não abstraído**.

Baselines atuais:

- `identity` — uma estratégia por combo exato;
- `conditional-equity quantiles` — equity river blocker-aware;
- `showdown_category`;
- `single` — compressão extrema deliberada.

O identity bucket é gated para reproduzir exatamente o CFR não abstraído sob as mesmas iterações. Abstrações grosseiras têm sua perda exposta pelo oracle exato original, não por uma BR presa aos mesmos buckets.

Detalhes: `docs/RIVER_STATE_ABSTRACTION_V1.md`.

## River Benchmark Battery

Para evitar escolher uma abstração porque funcionou numa única fixture, existe uma bateria determinística com seis texturas Short Deck. Em cada board são enumerados todos os **465 combos exatos possíveis** das 31 cartas restantes e ranges sintéticos são amostrados mecanicamente em quantis de `HandValue`, com offsets distintos para P0/P1.

A bateria mede por método e por textura nós, action slots, throughput e exact exploitability/pot, além de média, mediana e pior caso.

Esses ranges são deliberadamente sintéticos: servem para engenharia comparativa antes de existirem distribuições reais, não para estimar população ou win rate.

Detalhes: `docs/RIVER_BENCHMARK_BATTERY_V1.md`.

## Solver algorithms

Além do vanilla synchronous CFR, existe agora um **synchronous Regret-Matching+ (RM+)**:

- regrets cumulativos truncados em zero;
- full-chance síncrono;
- average strategy com delay e peso uniforme ou linear;
- determinismo e resumibilidade obrigatórios;
- exploitability medida pelo mesmo Dynamic Exact BR.

Não existe gate artificial dizendo que RM+ precisa derrotar CFR. O código passa se estiver correto e convergir; qual algoritmo compra mais redução de erro por CPU-hora é decidido pela bateria `benchmark_river_solver_algorithms.py`.

Detalhes: `docs/RIVER_RMPLUS_V1.md`.

## Protocolo Ryzen 9

`tools/run_ryzen_benchmark_suite.py` transforma uma execução local em evidência reproduzível. Ele registra:

- commit Git;
- working tree clean/dirty;
- plataforma/Python/CPU lógico;
- profile e parâmetros;
- comandos exatos;
- wall time;
- outputs/logs e seus SHA-256.

Perfis: `smoke`, `engineering` e `long`. O primeiro benchmark útil para decisão é `engineering`; `smoke` prova somente wiring.

A suíte consolida action abstraction, scalable multi-size+raise, state-abstraction battery e CFR-vs-RM+ sob uma pasta/manifeste único.

Detalhes: `docs/RYZEN_BENCHMARK_PROTOCOL_V1.md`.

## Validação

O CI principal exige simultaneamente:

- toda a suíte Python/Core;
- exhaustive five-card audit;
- baseline/fast evaluator C++ parity;
- ShortDeckRules C++;
- TableObservation validator/JSON C++;
- C++ -> Python canonical observation/fingerprints;
- raw reconstruction/timeline/hand-start/rake;
- action/state/solver exact-oracle gates;
- smokes dos benchmarks versionados.

Falhas de teste são tratadas como informação. Nesta fase, por exemplo, o evaluator corretamente expôs uma fixture que havia sido classificada intuitivamente como high-card mas formava **A6789**, e a bateria também mostrou que exigir três HandCategories em todo range era um invariant errado para boards double-paired; o gate foi corrigido para refletir diversidade de `HandValue`, não relaxado para fabricar PASS.

## Próximos gates

1. Executar `python tools/run_ryzen_benchmark_suite.py --profile engineering` no **Ryzen 9** e comparar erro por wall-clock, não apenas iterações/s.
2. Capturar evidência real do cliente 6+ para congelar chair layout, timing de `Pot/_bet/_balance`, CHECK/FOLD, hand boundaries, min-raise/reopen, side pots, sit-out, rake rounding e payouts.
3. Testar features privadas mais informativas — blockers, nutness e counterfactual values — contra identity e Dynamic Exact BR.
4. Usar os resultados para decidir se a próxima complexidade deve ir para multiple raise sizes/re-raises, mais estados ou o primeiro protótipo multi-street.
5. Só depois iniciar treino longo de blueprint, evitando gastar meses de CPU sobre uma representação ou abstração ainda não comprovada.

## Filosofia de engenharia

### Correção antes de escala

Uma run de meses sobre uma representação errada é pior que uma run curta sobre um modelo correto.

### Eficiência representa força

Capacidade economizada deve ser convertida, quando útil, em mais conhecimento estratégico: mais estados, melhores abstrações, mais iterações, maior capacidade ou refinamento dirigido.

### Evidência acima de intuição

Arquiteturas e abstrações só são promovidas por testes reproduzíveis. Uma V2 mais elegante não vence por parecer superior; um resultado surpreendente também não é aceito sem auditoria de viés, bug ou desperdício.

### Melhor possível, não perfeito

Não existe gate artificial de “GTO completo”. O roadmap continua enquanto houver forma mensurável de converter orçamento disponível em estratégia melhor.