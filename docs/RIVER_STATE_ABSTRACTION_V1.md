# DeepSix — River Private-State Abstraction Lab v1

## Objetivo

Depois de aumentar a riqueza da **árvore de ações**, a próxima dimensão é reduzir a quantidade de estados privados que precisam de estratégia própria.

Esta etapa foi construída para evitar uma confusão comum: uma abstração pode parecer excelente quando avaliada dentro do próprio jogo abstrato, mas ser facilmente explorável no jogo original.

O gate do DeepSix segue outro caminho:

```text
mãos exatas
   -> buckets usados somente pelo CFR
   -> política média por bucket
   -> expansão da política para cada combo exato
   -> best response exata no jogo NÃO abstraído
```

Assim, perda de informação causada pelos buckets aparece diretamente na exploitability exata do jogo original.

## Árvore de ação mantida fixa

O laboratório usa a mesma árvore já validada de `River Multi-Size + One-Raise`:

- CHECK ou um dos sizings iniciais;
- contra bet: FOLD/CALL/RAISE_TO;
- contra o primeiro raise: FOLD/CALL;
- sem re-raise.

Board, ranges, blockers, chance probabilities, evaluator e terminal utilities continuam exatos. A única variável desta etapa é **quais mãos privadas compartilham o mesmo infoset CFR**.

## Baselines de bucket

### Identity

Cada combo exato recebe seu próprio bucket.

Esse caso deve reproduzir exatamente o CFR não abstraído. Ele existe como gate estrutural: se `identity_bucket` mudar a política, o problema está na implementação da abstração, não na ideia de bucketing.

### Single bucket

Todas as mãos de cada jogador compartilham uma única estratégia.

É um baseline propositalmente extremo para provar que o auditor exato enxerga informação estratégica perdida. Também dá um limite de compressão de nós/slots.

### Showdown category

As mãos são agrupadas somente pela categoria final (`HIGH_CARD`, `PAIR`, `STRAIGHT`, etc.) produzida pelo evaluator Short Deck.

Esse baseline é simples, determinístico e deliberadamente grosseiro: duas mãos da mesma categoria podem ter força, blockers e incentivos muito diferentes.

### Conditional-equity quantiles

Para cada combo exato calculamos a equity river contra o range configurado do adversário:

```text
win = 1
tie = 0.5
loss = 0
```

A distribuição é **blocker-aware**, porque usa apenas os chance deals compatíveis e seus pesos reais do microgame.

As mãos são ordenadas deterministicamente por essa equity e divididas em quantis de tamanho aproximadamente igual. O builder atual permite pedir qualquer número positivo de buckets, limitado naturalmente pelo número de combos do range.

Isso ainda é uma abstração muito simples: usa só showdown equity e não modela nut advantage, blockers de bluff/call, action-conditioned ranges ou counterfactual values. A utilidade dela é servir como baseline transparente.

## CFR abstrato

`BucketedRiverCFR` troca apenas a chave do infoset:

```text
antes: (player, exact_cards, history)
agora: (player, bucket, history)
```

Se várias mãos pertencem ao mesmo bucket, regrets e average-strategy reach são acumulados no mesmo nó. Todas compartilham a estratégia correspondente.

O treino continua full-chance e síncrono.

## Avaliação sem esconder erro

`concrete_average_policy()` expande a estratégia de cada bucket para todos os combos concretos que pertencem a ele.

Depois usamos a `Dynamic Exact Best Response` do jogo exato, que continua enxergando cada mão privada separadamente.

Portanto a métrica:

```text
exact_unabstracted_exploitability
```

contém:

- erro residual de convergência do CFR;
- **mais** erro introduzido pela abstração privada.

Não existe best response “presa” aos mesmos buckets.

## Gates v1

A suíte exige:

1. Identity bucket -> política exatamente igual ao CFR não abstraído sob as mesmas iterações;
2. single bucket reduz de fato o número de nós e força mãos diferentes a compartilhar estratégia;
3. showdown-category agrupa mãos distintas da mesma categoria;
4. equity condicional permanece entre 0 e 1 e respeita blockers;
5. quantile buckets são determinísticos e respeitam a quantidade solicitada;
6. uma abstração propositalmente extrema produz perda visível quando avaliada pela BR exata não abstraída;
7. bucket maps incompletos ou configurações inválidas são rejeitados.

## Benchmark

`tools/benchmark_river_state_abstraction.py` mantém a árvore de ação fixa e compara:

- identity;
- equity quantile 3;
- equity quantile 2;
- showdown category;
- single bucket.

Para cada caso mede:

- buckets por jogador;
- compressão de private states;
- nós e action slots;
- iterações/s;
- exploitability exata no jogo não abstraído.

O smoke de CI só prova que a infraestrutura funciona. Escolher número/tipo de buckets exigirá uma bateria ampla de boards, ranges, pot/SPR e budgets de treino — idealmente com medições reais no Ryzen 9.

## Próxima evolução

A comparação mais importante não é simplesmente `mais buckets = melhor`.

Queremos medir uma fronteira de eficiência:

```text
memória / CPU-hora / número de estados
             versus
exploitability exata / erro estratégico
```

Depois dos baselines simples, podemos introduzir features mais informativas — blocker features, counterfactual values, clustering aprendido — sempre mantendo identity e a BR exata como referências enquanto o jogo de laboratório continuar pequeno o suficiente.
