# DeepSix — River Benchmark Battery v1

## Objetivo

Os primeiros laboratórios de abstração usaram fixtures pequenas e controladas. Isso é necessário para criar oracles independentes, mas uma única combinação de board/range pode favorecer acidentalmente uma abstração e levar a uma conclusão errada.

A Battery v1 cria uma primeira defesa contra esse tipo de overfitting **antes** de termos ranges reais do ambiente alvo.

Ela continua sendo sintética: não representa a população da KKPoker e não deve ser usada para estimar win rate. Sua função é comparar algoritmos e abstrações sobre vários regimes matemáticos do Short Deck de forma reproduzível.

## Geração mecânica dos ranges

Para cada river board fixo:

1. removemos as cinco cartas do board do deck Short Deck de 36 cartas;
2. enumeramos todos os `C(31,2) = 465` combos exatos possíveis de hole cards;
3. avaliamos cada combo com o evaluator validado do DeepSix;
4. ordenamos toda a população por `HandValue`, com desempate determinístico pelo ID das cartas;
5. selecionamos ranges de P0 e P1 em posições de quantil regularmente espaçadas, com offsets diferentes (`1/4` e `3/4` do passo);
6. os dois ranges exatos precisam ser distintos; a compatibilidade entre holdings adversários continua sendo filtrada posteriormente pela chance model blocker-aware.

Esse processo evita escolher manualmente apenas mãos que “ficam bonitas” para uma hipótese de bucket.

## Texturas iniciais

A Battery v1 possui seis fixtures nomeadas:

- `broadway_dry`;
- `paired_ace`;
- `four_flush`;
- `low_connected`;
- `double_paired`;
- `four_straight_broadway`.

Elas variam pairing, conectividade, possibilidade de flush e estrutura de nuts. Pot, sizings iniciais e raise-to também variam dentro do laboratório para impedir que toda comparação dependa de uma única razão bet/pot.

Cada range inicial possui dez combos exatos mecanicamente amostrados e os testes exigem que cada lado cubra múltiplas categorias terminais de mão.

## O que a bateria mede

`tools/benchmark_river_state_abstraction_battery.py` mantém o action game de cada fixture fixo e compara uma família de abstrações privadas:

```text
identity
equity_quantile_N ...
showdown_category
single_bucket
```

Depois de treinar cada caso, a política de bucket é expandida para os combos exatos e avaliada pela **Dynamic Exact Best Response do jogo não abstraído**.

São reportados, por fixture e agregados:

- número de buckets;
- nós e action slots;
- iterações/s;
- exact unabstracted exploitability;
- exploitability normalizada pelo pot;
- média, mediana e pior caso por método.

## Por que a agregação inclui pior caso

Escolher abstração apenas pela média pode esconder uma textura em que o agrupamento destrói informação crítica. Por isso a Battery v1 publica também o `max_exploitability_over_pot`.

Uma abstração candidata para expansão futura deverá ser julgada em uma fronteira de Pareto, não por uma única pontuação:

```text
menos estados / menos memória / mais throughput
                    versus
média + pior caso de erro estratégico
```

## Limitações deliberadas

A Battery v1 ainda é:

- somente river;
- HU;
- zero-sum e sem rake;
- ranges sintéticos construídos por força terminal, não por ranges de ação reais;
- action tree limitada a múltiplos bets iniciais + uma camada de raise;
- pequena o bastante para manter avaliação exata barata.

Essas limitações são uma vantagem nesta fase: sabemos exatamente o que cada resultado mede.

## Próximo uso

Existem duas escalas de execução:

### CI smoke

Pouquíssimas iterações e, quando necessário, apenas a primeira fixture. Serve exclusivamente para detectar script quebrado, regressões de schema e incompatibilidades.

### Benchmark de engenharia

Todas as seis fixtures, várias contagens de buckets, iterações suficientes para reduzir o erro de treino da identidade e repetição no Ryzen 9.

Somente essa segunda escala pode informar decisões de abstração. Mesmo ela ainda não substitui ranges e estados derivados do jogo real quando eles estiverem disponíveis.

## Critério de evolução

Uma nova feature de estado — blockers, nutness, counterfactual values ou embedding aprendido — deve entrar como mais um método na mesma bateria e competir contra:

- identity como teto de informação;
- quantis de equity como baseline simples;
- category e single como baselines de compressão grosseira.

Assim, sofisticação só é promovida quando compra redução mensurável de erro por unidade de custo.
