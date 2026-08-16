# DeepSix — River State-Abstraction Convergence v1

## Problema

Uma comparação de abstrações privadas em um único número de iterações responde apenas parte da pergunta.

Duas famílias de buckets podem ter:

- número de nós diferente;
- custo de construção diferente;
- throughput de CFR diferente;
- curvas de convergência diferentes;
- pisos de erro estratégico diferentes.

Portanto, escolher uma abstração apenas pela exploitability após `N` iterações pode favorecer um método que converge rápido no começo e estagna depois, ou penalizar outro que custa mais por iteração mas compra mais qualidade por CPU-hora.

## Benchmark

`tools/benchmark_river_state_abstraction_convergence.py` mantém a mesma árvore river `multi-size + one-raise`, as mesmas fixtures e o mesmo oracle exato não abstraído usados no laboratório de state abstraction.

A largura principal fica fixa em um `bucket_count` comum e são comparadas:

- `identity`;
- conditional-equity quantile;
- equity + nutness + blocker Borda quantile;
- uniform-reference CFV k-medoids;
- showdown category;
- single bucket.

Cada mapping é construído uma única vez. O mesmo `BucketedRiverCFR` é então treinado cumulativamente até checkpoints crescentes.

Exemplo:

```text
100 -> +200 -> +700
```

produz observações em 100, 300 e 1000 iterações sem reiniciar o trainer entre os checkpoints.

## Métricas por checkpoint

Para cada fixture/mapping são registrados:

- exploitability exata no jogo não abstraído;
- exploitability / pot;
- cumulative training seconds;
- iterations / second calculado sobre o tempo cumulativo;
- nós;
- action slots;
- bucket count por jogador;
- mapping build seconds.

A agregação por checkpoint preserva média, mediana e pior exploitability/pot, além de custo de treino, throughput, nós e custo de construção do mapping.

## Boundary de comparação

Todos os métodos dentro de um checkpoint recebem o mesmo número cumulativo de iterações e são julgados pelo mesmo Dynamic Exact Best Response.

**Isso não significa wall-clock igual.**

Por esse motivo o benchmark registra explicitamente `cumulative_training_seconds`. O analyzer usa esse tempo como eixo de custo ao construir a fronteira de Pareto de cada checkpoint.

O custo de construção do mapping continua separado. Ele é one-shot/precompute e pode ser amortizado de maneira muito diferente do custo recorrente de treinamento.

## Analyzer

`tools/analyze_ryzen_benchmark_suite.py` v2 inclui `state_abstraction_convergence`.

Em cada checkpoint, um método só permanece candidato à fronteira se não for dominado simultaneamente em:

- mean exploitability/pot — menor é melhor;
- max exploitability/pot — menor é melhor;
- mean cumulative training seconds — menor é melhor;
- mean nodes — menor é melhor.

Pertencer à fronteira não promove automaticamente o método. A regra é procurar famílias que permaneçam próximas da fronteira em **múltiplos checkpoints e múltiplas fixtures**.

## Integração Ryzen

`run_ryzen_benchmark_suite.py` agora executa cinco baterias:

1. action abstraction;
2. scalable multi-size + one-raise;
3. state-abstraction final-budget battery;
4. state-abstraction convergence;
5. CFR vs RM+.

Perfis da convergência:

```text
smoke:       1,2                  / 1 fixture
engineering: 100,300,1000         / todas as fixtures
long:        300,1000,3000,5000   / todas as fixtures
```

A largura de comparação v1 é `bucket_count=4`.

## O que v1 ainda não resolve

O benchmark ainda observa checkpoints de **iterações iguais**, com wall-clock medido a posteriori. Isso é melhor do que ignorar o custo, mas não equivale a treinar todos os métodos sob budgets exatos de segundos/minutos.

Uma próxima evolução, caso os resultados justifiquem, é um runner de **equal-wall-clock budgets**, por exemplo 10 s / 30 s / 120 s por fixture/método, com checkpoint final medido pelo tempo e não pelo número de iterações.

Isso só vale a pena depois de termos a primeira curva real no Ryzen 9. Até lá, a v1 já impede a conclusão incorreta de que `1000 iterações` representam o mesmo custo para abstrações diferentes.
