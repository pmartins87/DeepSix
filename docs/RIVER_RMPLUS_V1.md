# DeepSix — Synchronous Regret-Matching+ River Lab v1

## Objetivo

Depois de estabilizar action abstraction, exact best response e private-state abstraction, podemos testar algoritmos de treino sem mudar o jogo sendo resolvido.

A v1 adiciona um segundo trainer para a mesma árvore river: **Regret-Matching+ síncrono (RM+)**.

O nome é deliberadamente específico. A implementação usa a ideia central de regret-matching+ — regrets cumulativos truncados em zero — mas preserva a semântica full-chance síncrona já usada pelos laboratórios DeepSix. Ela não é apresentada como uma reprodução bit-a-bit de toda variante publicada sob o nome CFR+.

## Diferença para o CFR baseline

O CFR baseline acumula regrets positivos e negativos normalmente.

RM+ v1 aplica, ao final de cada iteração completa:

```text
R_plus[a] <- max(0, R_plus[a] + delta_regret[a])
```

A estratégia corrente usa regret matching diretamente sobre esses regrets não negativos.

Todos os chance deals da iteração continuam vendo a mesma estratégia de início de iteração. Os deltas são aplicados somente após a travessia full-chance inteira, preservando determinismo e a possibilidade de auditar `train(A)+train(B) == train(A+B)`.

## Average strategy

A política média possui duas opções explícitas:

- peso uniforme depois de um delay;
- peso linear depois de um delay.

Com `averaging_delay = D` e linear averaging, a iteração `t` recebe peso:

```text
max(0, t - D)
```

O contador absoluto de iterações é preservado quando o treino é retomado. Portanto uma run dividida não reinicia os pesos e deve reproduzir exatamente a run contínua.

## O que é gate e o que é hipótese

São gates de corretude:

- regrets permanecem não negativos depois de cada atualização;
- treino é determinístico;
- treino dividido reproduz treino único;
- delay maior que a run mantém a average policy uniforme, embora regrets continuem sendo atualizados;
- a política treinada reduz substancialmente exploitability exata em relação à política uniforme.

**Não é gate** que RM+ seja sempre melhor que o CFR baseline no mesmo número de iterações. Isso seria transformar uma hipótese empírica na condição de aprovação do código e poderia enviesar o experimento.

A comparação deve ser feita em benchmark separado, medindo principalmente:

```text
exact exploitability
por
wall-clock / CPU-hora
```

não apenas por número de iterações.

## Oracle

Tanto CFR quanto RM+ são avaliados pela mesma `Dynamic Exact Best Response` no jogo exato não abstraído.

Isso impede que o algoritmo novo seja beneficiado por uma métrica diferente.

## Benchmark de algoritmos

`tools/benchmark_river_solver_algorithms.py` executa, sobre a mesma River Benchmark Battery:

- vanilla synchronous CFR;
- synchronous RM+ com linear average.

Ele coleta checkpoints cumulativos e publica por algoritmo:

- exploitability exata;
- exploitability/pot;
- tempo acumulado de treino;
- iterações/s;
- média, mediana e pior caso entre fixtures.

O CI não usa essa bateria longa para selecionar vencedor. A comparação real deve ser executada no Ryzen 9 com vários checkpoints e orçamento suficiente para observar a forma de convergência, não apenas o comportamento inicial.

## Critério de promoção

RM+ só deve substituir o baseline em etapas maiores se demonstrar uma fronteira melhor de custo/erro em várias texturas, sem perder resumibilidade/auditabilidade e sem depender de um tuning de delay específico para uma única fixture.

Se outro algoritmo vencer depois — CFR+, DCFR, MCCFR ou uma abordagem learned/value-based — o mesmo protocolo permanece: jogo fixo, oracle fixo, orçamento medido e comparação reproduzível.
