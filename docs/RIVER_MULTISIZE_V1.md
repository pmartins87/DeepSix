# DeepSix — River Multi-Size Microgame v1

## Objetivo

Esta etapa testa a primeira pergunta real de **abstração de ações** do DeepSix: quanto de complexidade acrescentamos quando um spot deixa de ter um único sizing abstrato e passa a oferecer vários tamanhos de aposta?

Ainda não estamos escolhendo sizings “bons para a KKPoker”. Os valores usados nos testes são unidades artificiais de laboratório. O objetivo é validar a infraestrutura necessária para comparar árvores mais ricas de forma mensurável e auditável.

## Árvore

Quando não enfrenta aposta, cada jogador possui:

```text
CHECK / BET(size_1) / BET(size_2) / ...
```

Quando enfrenta qualquer bet:

```text
FOLD / CALL
```

Não existem raises nesta versão. Isso isola a dimensão “quantos sizings iniciais oferecer” sem misturar ainda a explosão combinatória causada por re-raises.

O número de sizings é parametrizado de 1 a 4 no v1. O limite de quatro não é uma afirmação estratégica; é um guard de auditabilidade para manter a exact best response barata durante esta fase.

## Chance e evaluator

Assim como no River Microgame v1:

- board é um river Short Deck real;
- ranges contêm combos exatos de duas cartas e pesos positivos;
- blockers são respeitados;
- chance é normalizada sobre todos os pares compatíveis;
- showdown usa o evaluator validado do DeepSix;
- strength de cada chance deal é calculada uma vez e cacheada.

## CFR

O trainer usa full-chance CFR **síncrono**. Todos os chance deals da iteração usam a mesma estratégia de início de iteração; regrets e average-strategy deltas são aplicados somente depois da travessia completa.

Os nós possuem aridade variável:

- sem bet: `1 + número_de_sizings` ações;
- enfrentando bet: duas ações.

Determinismo e continuidade são gates: duas runs com as mesmas condições devem produzir exatamente a mesma average policy, e `750 + 750` iterações deve coincidir com `1500` em uma run única.

## Exact best response

A best response continua exata e é decomposta por mão privada própria. Para `S` sizings, uma mão possui:

- uma decisão inicial com `1 + S` alternativas;
- `S` possíveis nós futuros de fold/call.

Portanto o número de planos puros por **mão privada** é:

```text
(1 + S) × 2^S
```

Com o limite atual de quatro sizings, isso permanece pequeno e independente do número total de combos no range. O range pode crescer sem voltar à enumeração exponencial de uma política pura global.

## Gates implementados

A suíte exige:

1. **equivalência exata com o River Microgame v1 quando existe apenas um sizing** — EV da política uniforme e exploitability devem coincidir;
2. com dois sizings, a best response decomposta deve coincidir com uma **enumeração brute-force independente da política pura global** em ranges pequenos;
3. CFR com dois sizings deve reduzir fortemente a exact exploitability da política uniforme;
4. treino deve ser determinístico e retomável;
5. a exact best response deve continuar funcionando com quatro sizings;
6. conjuntos vazios, duplicados, não ordenados, não positivos ou com mais de quatro sizings são rejeitados.

No gate CI #75, a suíte completa chegou a **120 testes Python e todos passaram**, incluindo os seis testes multi-sizing. Todos os gates C++/Python de evaluator e OpenHoldem6Plus também permaneceram verdes no mesmo run.

## O que este resultado permite

Agora já conseguimos comparar abstrações com diferentes números de ações sem mudar o evaluator, a chance model ou o auditor de exploitability. Isso é a fundação para um benchmark de custo marginal:

```text
mais sizing
    -> árvore maior
    -> mais custo por iteração / mais iterações para convergir
    -> potencial redução do erro de abstração
```

A próxima versão deverá medir essa troca explicitamente em uma bateria de boards/ranges/SPR artificiais antes de aumentar para raises ou streets anteriores.

## O que ainda não devemos concluir

Este gate **não** prova que dois, três ou quatro sizings serão ideais no cash 6+ real. Também não prova quais percentuais de pot devem existir na abstração final. Essas decisões dependerão de benchmarks muito mais amplos e das regras/valores reais observados no cliente KKPoker.
