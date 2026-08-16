# DeepSix — River Hand Features v1

## Objetivo

Os primeiros buckets privados do DeepSix usam apenas uma informação escalar simples — equity condicional — ou a categoria final da mão. Isso é útil como baseline, mas não representa duas propriedades importantes de um river:

- **nutness absoluta** contra todo o espaço de combos compatíveis;
- **efeito de blockers** sobre o range configurado do adversário.

A v1 adiciona features exatas e transparentes antes de qualquer embedding aprendido. O objetivo é criar um baseline mais rico que continue totalmente auditável por enumeração.

## Features exatas

Para cada combo privado configurado calculamos:

### `conditional_range_equity`

Equity river blocker-aware contra o range configurado do adversário:

```text
win = 1
tie = 0.5
loss = 0
```

Somente chance deals compatíveis participam.

### `universal_equity`

Depois de remover board + duas hole cards, restam 29 cartas desconhecidas. Enumeramos os `C(29,2) = 406` holdings exatos possíveis do adversário e calculamos equity uniforme contra esse universo completo.

Essa feature não depende de como o range sintético/adversário foi escolhido.

### `nutness`

No mesmo universo de 406 holdings compatíveis:

```text
nutness = 1 - fraction(strictly stronger opponent hands)
```

Uma mão que não pode ser estritamente batida recebe `1.0`, mesmo que possa empatar com outros holdings.

Por isso `nutness >= universal_equity`: ties contam integralmente para nutness e pela metade para equity.

### `blocked_range_weight_fraction`

Antes de aplicar as hole cards do jogador como blockers, somamos o peso total do range exato adversário. Depois calculamos qual fração desse peso contém uma das duas cartas do jogador e, portanto, é impossível.

Isso mede pressão bruta de blocker sobre a distribuição configurada.

### `blocked_stronger_weight_fraction`

Entre os holdings adversários que teriam `HandValue` estritamente superior ao do jogador, medimos qual fração do peso é eliminada pelas hole cards do jogador.

Essa feature procura capturar uma informação estrategicamente mais direcionada: não apenas “bloqueio quantos combos?”, mas “bloqueio quanto da parte do range que me derrotaria?”.

Se não existe holding configurado mais forte, a feature é zero; a ausência de mãos superiores já está representada pela nutness/equity.

## Cache

As features são determinísticas para `(config, player, exact_cards)` e são cacheadas. Isso é importante porque a bateria compara múltiplas quantidades de buckets sobre a mesma fixture; não precisamos repetir milhares de avaliações exatas para cada largura.

## Baseline Borda por ranks

`feature_borda_quantile_bucket_map` transforma quatro features em um baseline de bucketing:

```text
conditional_range_equity
universal_equity
nutness
blocked_stronger_weight_fraction
```

Para cada jogador:

1. cada feature é ordenada separadamente;
2. ties recebem o rank médio;
3. o rank é normalizado para percentile `[0,1]`;
4. os quatro percentiles recebem **peso igual**;
5. a média forma um score composto;
6. as mãos são divididas em quantis determinísticos de tamanho aproximadamente igual.

O nome “Borda” descreve exatamente essa agregação por ranks. Não existe tuning oculto de pesos para uma fixture.

## Por que não usamos pesos otimizados agora

Se ajustássemos pesos de equity/nutness/blockers diretamente na mesma bateria que mede o resultado, poderíamos apenas overfitar seis boards sintéticos.

Peso igual cria um ponto de partida refutável. Mais tarde podemos separar treino/validação de fixtures e otimizar features ou clustering somente se o ganho sobreviver fora da amostra.

## Gates

A suíte exige:

- todas as features dentro de `[0,1]`;
- `nutness >= universal_equity`;
- blocker weight reproduzido exatamente em um range ponderado construído para auditoria;
- uma Broadway nut sem holding estritamente superior recebe `nutness=1`;
- blocker de stronger range desaparece quando não existe mão superior;
- bucket map determinístico;
- quantidade de buckets solicitada respeitada;
- mãos fora do range configurado e parâmetros inválidos rejeitados.

## Integração à Battery v2

A `river_state_abstraction_battery` passa a comparar, na mesma largura de buckets:

```text
conditional-equity quantiles
versus
equity + universal equity + nutness + blocker pressure
```

ambos continuam sendo julgados pela política expandida contra a **Dynamic Exact Best Response do jogo não abstraído**.

A feature nova não é promovida por existir. Ela precisa mostrar uma fronteira melhor de compressão/erro em várias texturas e, idealmente, no Ryzen 9 antes de virar base para o blueprint.
