# DeepSix — River Microgame v1

## Objetivo

O `River Microgame` é o primeiro solver do projeto que já usa **cartas e evaluator Short Deck reais**, mas mantém uma árvore pequena o suficiente para termos métricas exatas de correção e exploitability.

Ele **não é a estratégia final de cash game** e o único sizing presente na versão v1 não deve ser interpretado como sizing recomendado para a KKPoker. O objetivo desta etapa é validar a arquitetura de treino antes de aumentar árvore, stacks, streets ou número de jogadores.

## Jogo v1

Estado inicial: river completo, pot conhecido, ranges exatos de dois jogadores e um tamanho de bet parametrizado.

Árvore:

```text
P0: CHECK / BET
  CHECK -> P1: CHECK / BET
    CHECK -> showdown
    BET -> P0: FOLD / CALL
  BET -> P1: FOLD / CALL
```

Não há raise na v1.

As utilities são zero-sum a partir do instante imediatamente anterior à ação de P0. O pot já existente é sunk:

- showdown sem bet: `±pot/2`;
- bet seguido de fold: bettor recebe `+pot/2` em utility líquida;
- bet/call: `±(pot/2 + bet)`;
- tie: `0`.

## Chance e informação privada

Cada range é uma coleção de **combos exatos de duas cartas**, com peso positivo opcional. O conjunto de chance é formado apenas por pares de combos compatíveis com:

- board;
- cartas privadas do adversário;
- deck Short Deck de 36 cartas.

A probabilidade de um deal é proporcional ao produto dos pesos dos dois combos e depois normalizada sobre todos os deals compatíveis.

O showdown de cada deal compatível é pré-computado uma única vez usando o evaluator real do DeepSix. Isso evita gastar a maior parte de cada iteração reavaliando as mesmas sete cartas.

## CFR síncrono

Uma iteração percorre **todos os chance deals sob a estratégia existente no início da iteração**. Regrets e reach-weighted average strategy são acumulados em buffers e só então aplicados.

Essa decisão é deliberada. Uma implementação anterior atualizava os nós entre chance branches e, embora pudesse convergir, isso transformava silenciosamente os deals em micro-iterações sequenciais. O baseline foi corrigido antes de ser usado como referência para arquiteturas maiores.

O microgame possui:

- treino determinístico;
- continuação exata (`train(1000)` + `train(1000)` = `train(2000)`);
- average policy explícita;
- expected value exato sobre todos os chance deals;
- best response exata;
- exploitability como half-NashConv.

## Best response exata e escalável

A primeira versão do auditor de best response enumerava uma política pura completa sobre todos os infosets privados, custo exponencial em `2^(2N)` para `N` combos por jogador.

Isso foi substituído por uma decomposição exata específica desta árvore. Com a política do oponente fixa, chance é aditiva por mão privada própria. Portanto, cada combo do jogador que responde pode ser otimizado independentemente sobre suas quatro combinações de decisões puras nos dois nós em que pode atuar; os valores ponderados são então somados.

Consequência:

- custo deixa de explodir com o número de combos do range;
- a best response continua exata para esta árvore;
- um teste independente compara o método escalável com enumeração brute-force da política inteira em ranges pequenos;
- outro teste usa ranges com nove combos por jogador, acima do antigo limite de oito mãos.

## Um bug de fixture que virou teste de regra

A primeira fixture de range usava uma mão aparentemente fraca contendo `9+7` sobre board com `A,8,6`. No Short Deck isso completa **A6789**, a straight baixa especial. O evaluator corretamente derrubou a hipótese de que a mão era high-card e o teste falhou.

A fixture foi corrigida para evitar o straight, e o comentário ficou preservado no teste. Esse episódio é útil: mostra que o solver está de fato consumindo a semântica Short Deck validada, não uma ordenação mental de Hold'em 52-card.

## Gate de promoção

A v1 só é aceita se:

1. os testes de ranges/blockers usam o evaluator Short Deck real;
2. best responses limitam corretamente o valor da política;
3. o algoritmo escalável de BR coincide com brute force independente em um jogo pequeno;
4. CFR reduz fortemente a exploitability da política uniforme;
5. treino é determinístico e retomável;
6. todos os gates anteriores de Core/evaluator/OH continuam verdes.

## Próximo experimento

A próxima etapa não é simplesmente adicionar complexidade. Será construída uma variante de river com **mais de um sizing abstrato**, ainda sem raises, para medir:

- quanto a árvore cresce;
- quanto custa em iterações/segundo;
- quanto muda exploitability e política;
- se a ação adicional realmente compra qualidade estratégica suficiente para justificar o custo.

Os sizings desse experimento serão parâmetros artificiais de laboratório. Os sizings reais de produção não serão congelados antes das capturas do cliente KKPoker e dos benchmarks de abstração.
