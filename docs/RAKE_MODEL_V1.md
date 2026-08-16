# DeepSix — Rake Model v1

> **Historical model.** This document records the original KKPoker-oriented rake work. It is no longer the primary DeepSix economy. The current simulator target is `docs/SIMULATOR_TARGET_GGPOKER_ECONOMY_V1.md` and `deepsix_core/ggpoker_economy.py`. KKPoker parameters must never be selected implicitly by the current trainer/simulator.

## Objetivo histórico

Rake altera diretamente a utilidade do cash game e, portanto, não pode entrar no trainer como uma aproximação implícita. A v1 implementou apenas a parte que conseguíamos representar **exatamente** com parâmetros explícitos e manteve arredondamento/timing do cliente fora do Core.

## Fatos publicados usados na referência original KKPoker

Na página oficial de rake da KKPoker consultada durante a construção desta versão, a seção de 6+ publicava:

- rake percentual de 3%;
- ausência de rake se a mão termina preflop;
- ausência de rake para potes no limite publicado como `5BB` ou abaixo;
- caps expressos em antes: 3 antes nas stakes de ante 0.02 até 2 e 2 antes nas stakes 5 e 10.

A mesma página descrevia a variante 6+ como ante-based e sem blinds, com o Button colocando dois antes. Por isso a expressão `5BB` no limiar de small pot não foi convertida automaticamente pelo Core. A hipótese `1 BB = button blind = 2 antes`, que produziria threshold de 10 antes, permaneceu como hipótese de integração.

Esse conjunto de parâmetros é preservado somente para reproduzir experimentos históricos ou realizar comparações explicitamente solicitadas.

## Representação exata reutilizável

`deepsix_core.rake` continua sendo infraestrutura genérica e válida para o target atual:

- pot e caps em unidades inteiras exatas;
- percentuais como `fractions.Fraction`;
- cap aplicado sobre o valor percentual exato;
- resultado de rake e net pot mantidos como `Fraction`;
- nenhuma política de rounding é inventada no caminho matemático.

## Separação de responsabilidades

`compute_exact_rake()` resolve genericamente:

1. isenção preflop configurável;
2. limiar de small pot configurável;
3. percentual exato;
4. multiplicador explícito de table size;
5. cap exato.

A função não decide qual operador/plataforma está sendo simulado. O profile atual deve ser escolhido explicitamente.

## Helper Short Deck histórico

`shortdeck_percentage_cap_config()` continua disponível como helper genérico em múltiplos explicitamente fornecidos de ante. Ele não representa automaticamente GGPoker nem KKPoker.

## Target atual

Para o simulador GGPoker, usar:

```text
from deepsix_core.ggpoker_economy import ggpoker_shortdeck_rake_config
```

O profile atual usa a tabela pública de 5% e caps por stake/player count congelada em 2026-08-16. Jackpot Short Deck é tratado separadamente por `ggpoker_shortdeck_bbj_contribution()`.

## Regra de compatibilidade

Runs históricas que usaram este modelo KKPoker permanecem válidas como evidência do experimento original. Elas não devem ser renomeadas, reinterpretadas ou comparadas como se usassem a economia GGPoker atual.
