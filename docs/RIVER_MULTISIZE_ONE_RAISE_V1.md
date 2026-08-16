# DeepSix — River Multi-Size + One-Raise Microgame v1

## Objetivo

Esta etapa combina, pela primeira vez, as duas dimensões de ação que já tinham sido validadas isoladamente:

- múltiplos sizings iniciais;
- uma camada de raise.

Nada além disso é acrescentado. Não existem re-raises, streets anteriores, rake ou jogo multiway. O laboratório continua HU/river/zero-sum para manter exact best response e exploitability auditáveis.

## Árvore

Para cada sizing configurado `B_i`:

```text
sem aposta:
  CHECK / BET(B_1) / ... / BET(B_S)

contra BET(B_i):
  FOLD / CALL / RAISE_TO(R)

contra RAISE_TO(R):
  FOLD / CALL
```

`R` é um raise-to absoluto único e deve ser maior que todos os bets iniciais.

Os valores são unidades inteiras artificiais de laboratório. Eles não representam ainda sizings recomendados para a KKPoker.

## Por que v1 limita S <= 2

Com `S` sizings, cada mão privada possui:

```text
(1 + S) × 3^S × 2^S
= (1 + S) × 6^S
```

planos puros possíveis para uma exact best response por mão.

Logo:

```text
S=1 -> 12 planos/mão
S=2 -> 108 planos/mão
S=3 -> 864 planos/mão
S=4 -> 6480 planos/mão
```

A explosão aqui ocorre no **auditor exato**, não apenas no CFR. Em vez de deixar o CI crescer exponencialmente e depois fingir que a validação continua barata, v1 congela duas sizes. Para passar de S=2, primeiro devemos substituir a enumeração de planos por um exact-BR mais eficiente ou aceitar explicitamente outra forma de oracle.

## Equivalência de baseline

Com apenas um sizing, a árvore é matematicamente a mesma do `River One-Raise v1`.

O gate exige que, sob a mesma fixture:

- EV da política uniforme seja idêntico;
- exploitability exata da política uniforme seja idêntica.

Assim, a generalização multi-size não pode alterar silenciosamente a semântica do jogo de uma size.

## Exact best response

A BR continua decomposta pela mão privada própria. Para S=2, cada mão testa 108 planos.

Existe também um gate independente de brute force **global** em ranges pequenos com duas mãos privadas para o jogador que responde. Ele combina todos os planos por mão e exige o mesmo valor da BR decomposta.

Esse gate é importante porque uma implementação de CFR pode convergir e ainda assim um bug no auditor produzir uma exploitability aparentemente boa. O oracle não reutiliza a decomposição que está sendo testada.

## CFR

O trainer mantém:

- chance exata blocker-aware;
- board/ranges/evaluator Short Deck reais;
- full-chance CFR;
- atualizações síncronas por iteração;
- determinismo;
- continuidade exata entre treino dividido e treino único.

## Gates implementados

1. S=1 exatamente equivalente ao `River One-Raise v1` na política uniforme;
2. contagem de planos `12` para S=1 e `108` para S=2;
3. legal actions e payouts terminais auditados para cada sizing;
4. exact BR S=2 = brute force global independente em ranges pequenos;
5. CFR S=2 reduz fortemente exploitability exata;
6. treino é determinístico e resumível;
7. sizes vazias, repetidas, fora de ordem, mais de duas ou `raise_to <= max(size)` são rejeitadas.

## Benchmark

`tools/benchmark_river_multisize_raise.py` compara, na mesma fixture:

```text
1 sizing + 1 raise
vs
2 sizings + 1 raise
```

Ele mede:

- chance deals;
- nós;
- action slots;
- planos puros por mão exigidos pelo oracle atual;
- iterações/s;
- exploitability inicial/final como diagnóstico de convergência.

Exploitability dos dois casos vive em espaços de ações diferentes e **não deve ser tratada diretamente como uma pontuação de qualidade entre abstrações**. O benchmark é, primeiro, um medidor de custo estrutural e de dificuldade de convergência.

## Próxima decisão

O resultado já mostra conceitualmente onde está um gargalo futuro importante: aumentar o número de sizings faz crescer não só o trainer, mas também o custo de provar que ele está certo.

Antes de expandir para 3+ sizes com raise, devemos avaliar duas linhas:

1. melhorar o algoritmo de exact best response para não enumerar `(1+S)6^S` planos por mão;
2. começar a testar abstração de estado/cartas usando S=1/S=2, onde ainda possuímos oracle exato barato.

A filosofia permanece: complexidade só entra quando sua contribuição pode ser medida e auditada.
