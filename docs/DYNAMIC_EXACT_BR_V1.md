# DeepSix — Dynamic Exact Best Response v1

## Problema resolvido

O primeiro auditor de `River Multi-Size + One-Raise` enumerava todos os planos puros de resposta de cada mão privada.

Para `S` sizings iniciais, isso custa:

```text
(1 + S) × 6^S planos por mão
```

Logo:

```text
S=1 -> 12
S=2 -> 108
S=3 -> 864
S=4 -> 6480
```

A enumeração é excelente como oracle independente em árvores pequenas, porém transforma a própria validação em gargalo quando a abstração cresce.

## Solução

`river_multisize_one_raise_dpbr.py` implementa uma exact best response por programação dinâmica sobre infosets.

Para uma mão privada fixa do jogador BR, cada estado recursivo carrega todos os deals compatíveis e seus pesos de realização.

### Nó do jogador BR

A decisão deve ser a mesma para todos os opponent holdings que pertencem ao mesmo infoset. Portanto cada ação legal é avaliada usando o **mesmo conjunto ponderado de deals** e escolhemos:

- máximo de utilidade P0 quando P0 é BR;
- mínimo de utilidade P0 quando P1 é BR.

### Nó do oponente

Cada deal pode possuir estratégia diferente porque a mão privada do oponente muda. O peso do deal é multiplicado pela probabilidade daquela ação na política fixa do oponente, e os valores ponderados dos branches são somados.

### Terminal

Somamos:

```text
peso_de_realização × utilidade_terminal
```

sobre todos os deals restantes.

Os pesos carregam apenas chance e reach do oponente. O próprio jogador BR é determinístico na resposta ótima.

## Gate independente

A implementação dinâmica **não foi promovida por plausibilidade matemática**.

Ela é confrontada com o auditor enumerativo anterior em:

- S=1, política uniforme;
- S=2, política uniforme;
- S=2, política produzida após CFR;
- ranges com pesos não uniformes;
- ambos os jogadores (`BR0` e `BR1`);
- exploitability completa.

Todos esses valores devem coincidir numericamente com precisão apertada.

Assim mantemos dois caminhos de validação independentes:

```text
árvore pequena
  enumerative pure-plan BR
          ==
  dynamic infoset BR
```

Depois desse gate, a implementação dinâmica pode ser usada em árvores maiores onde a enumeração seria desperdício.

## Scalable Multi-Size + One-Raise

`river_multisize_one_raise_scalable.py` reutiliza exatamente a mesma chance, CFR, árvore e utilidades do game já gated, mas permite **1..4 sizings iniciais**.

A única mudança semântica é o boundary de validação do número de sizes. Exact exploitability dessa linha usa sempre o DP BR; o enumerador exponencial não participa.

O limite atual de quatro sizes não é uma afirmação estratégica. Ele existe para manter a árvore de laboratório suficientemente pequena enquanto comparamos custo/benefício e antes de adicionar novas dimensões como múltiplos raise sizes ou re-raises.

## Resultado arquitetural

Esta etapa é um exemplo direto da filosofia do DeepSix:

> quando removemos uma ineficiência estrutural, a capacidade liberada não deve ser desperdiçada; ela deve ser convertida em maior riqueza estratégica que continue auditável.

Antes, S=4 implicava 6480 planos por mão no oracle. Agora o exato é resolvido diretamente na árvore de infosets, permitindo testar quatro sizings + raise sem transformar o auditor em protagonista do custo.

## Benchmark

`tools/benchmark_river_multisize_raise_scalable.py` executa os prefixes de 1 até 4 sizes sob:

- mesmo board;
- mesmos ranges;
- mesmo pot;
- mesmo raise-to;
- mesmo número de iterações.

Ele reporta nós, action slots, iterações/s, exploitability exata via DP e também a contagem teórica de planos que o método antigo teria enumerado.

O benchmark de CI é somente smoke. Decisões de abstração devem usar uma bateria maior e, para orçamento real, medições no Ryzen 9.
