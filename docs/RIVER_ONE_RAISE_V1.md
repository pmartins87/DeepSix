# DeepSix — River One-Raise Microgame v1

## Objetivo

Depois de validar múltiplos sizings sem raises, esta etapa adiciona **exatamente uma dimensão nova** à árvore: um raise fixo, sem re-raise posterior.

O objetivo não é afirmar que os valores usados são bons sizings para KKPoker. O objetivo é medir e auditar o custo estrutural de admitir a primeira resposta agressiva depois de uma aposta.

## Árvore

Com `x=check`, `b=bet`, `r=raise-to`, `f=fold`, `c=call`:

```text
P0: x / b
  x -> P1: x / b
    b -> P0: f / c / r
      r -> P1: f / c
  b -> P1: f / c / r
    r -> P0: f / c
```

Não existe re-raise depois de `r`.

A configuração possui:

- `pot`;
- `bet_size`;
- `raise_to`, obrigatoriamente maior que `bet_size`;
- ranges exatos de P0/P1;
- board river Short Deck real.

## Contabilidade terminal

A utilidade continua expressa em fichas líquidas para P0 relativamente à metade do pot inicial.

Exemplos para pot `P`, bet `B` e raise-to `R`:

```text
P0 bet, P1 fold                +P/2
P0 bet, P1 call                ±(P/2 + B)
P0 bet, P1 raise, P0 fold      -(P/2 + B)
P0 bet, P1 raise, P0 call      ±(P/2 + R)
P0 check, P1 bet, P0 fold      -P/2
P0 check, P1 bet, P0 raise,
  P1 fold                      +(P/2 + B)
P0 check, P1 bet, P0 raise,
  P1 call                      ±(P/2 + R)
```

O sinal nos showdowns vem exclusivamente do evaluator Short Deck validado.

## CFR e auditoria

O trainer usa o mesmo padrão do laboratório anterior:

- full-chance CFR;
- atualização síncrona de regrets/average strategy após atravessar todos os chance deals da iteração;
- chance blocker-aware;
- determinismo obrigatório;
- `train(a); train(b)` deve ser idêntico a `train(a+b)`.

## Exact best response

Cada jogador possui três infosets possíveis por mão privada:

- uma decisão de 2 ações;
- uma decisão de 3 ações;
- uma decisão de 2 ações.

Logo cada mão privada possui somente:

```text
2 × 3 × 2 = 12 planos puros
```

A best response é decomposta por mão privada e enumera esses 12 planos. Como gate independente, em ranges pequenos ela é comparada com brute force global de todas as combinações de planos por mão.

Isso evita declarar uma BR “exata” apenas porque duas implementações reutilizam o mesmo algoritmo.

## Gates

A suíte exige:

1. árvore legal e utilidades terminais auditadas diretamente;
2. exatamente 12 planos puros por mão para cada jogador;
3. best response decomposta = brute force global independente em ranges pequenos;
4. CFR reduz fortemente exact exploitability da política uniforme;
5. treino determinístico e retomável;
6. chance usa o evaluator Short Deck real e normaliza para probabilidade 1;
7. parâmetros e histories inválidos são rejeitados.

## Limite conceitual importante

Este microgame continua sendo **HU e zero-sum, sem rake**. Isso é intencional para termos exploitability e best responses matematicamente auditáveis.

Não devemos simplesmente inserir rake variável na mesma função de utilidade e continuar chamando a métrica de exploitability zero-sum: se o rake depende da trajetória/pot, a soma das utilidades dos dois jogadores varia com a ação. A economia real será introduzida em uma camada separada com métricas apropriadas, depois que rounding/timing estiverem congelados.

Também não devemos extrapolar resultados HU diretamente para a árvore 6-handed. O laboratório serve para escolher algoritmos e abstrações sob controle antes de enfrentar o componente multiway.

## Próxima etapa estratégica

Depois deste gate, as duas comparações mais úteis serão:

- custo marginal de `sem raise -> 1 raise` sob os mesmos boards/ranges;
- depois, `1 sizing + raise -> múltiplos sizings + raise`, aumentando apenas uma dimensão por vez.

Essa progressão evita explodir a árvore antes de sabermos qual complexidade realmente compra força por CPU-hora.
