# DeepSix — Ryzen Benchmark Analyzer v2

## Objetivo

A suíte `run_ryzen_benchmark_suite.py` produz evidência bruta e um manifest com hashes. O analyzer mantém uma segunda etapa separada:

```text
benchmark run
  -> verificar SHA-256 de todos os outputs/logs
  -> carregar somente evidência íntegra
  -> resumir comparações que vivem no mesmo espaço
  -> identificar candidatos não dominados
```

A v2 acrescenta análise das curvas de `state_abstraction_convergence` e mantém compatibilidade explícita com manifests v1.

## Uso

```text
python tools/analyze_ryzen_benchmark_suite.py benchmark_runs/<run_dir> --output analysis.json
```

Se qualquer JSON/log tiver sido alterado depois da execução, a análise é recusada antes de calcular métricas.

## Contratos aceitos

### Suite v2

Espera cinco outputs:

- action abstraction;
- scalable multi-size + one-raise;
- state-abstraction battery;
- state-abstraction convergence;
- solver algorithms.

### Suite v1

Os quatro outputs históricos continuam válidos e são verificados/analisados. Nesse caso:

```text
state_abstraction_convergence = null
```

Não há migração ou edição silenciosa de manifest antigo.

## Solver Pareto

CFR e RM+ usam a mesma chance, árvore e Dynamic Exact Best Response. No checkpoint final, o analyzer minimiza:

```text
mean exploitability / pot
worst exploitability / pot
mean training wall time
```

Pertencer à fronteira não promove automaticamente o algoritmo.

## State-abstraction final-budget Pareto

Como todas as abstrações usam a mesma action tree e são julgadas no jogo exato não abstraído, a fronteira usa:

```text
mean exploitability / pot ↓
worst exploitability / pot ↓
mean nodes ↓
mean iterations / second ↑
```

`mapping_build_seconds` é preservado fora da fronteira porque é custo one-shot/precompute e possui amortização diferente do treino.

## State-abstraction convergence Pareto

A v2 acrescenta uma fronteira independente em cada checkpoint cumulativo.

Critérios:

```text
mean exploitability / pot ↓
worst exploitability / pot ↓
mean cumulative training seconds ↓
mean nodes ↓
```

Todos os métodos de um checkpoint receberam o mesmo número de iterações, mas o analyzer **não presume custo igual**: o wall-clock realmente medido entra como eixo de Pareto.

O sinal de promoção deve persistir em múltiplos checkpoints e fixtures. Um método que aparece na fronteira apenas em um ponto não é considerado vencedor.

## Action abstraction

O analyzer continua sem criar ranking estratégico entre action spaces diferentes.

Adicionar sizings/raises muda o próprio jogo no qual exploitability é definida. Portanto action-abstraction e scalable-multisize-raise permanecem evidência estrutural/throughput, não um ranking de força baseado em exploitability bruta.

## Gates v2

A suíte de testes exige:

- SHA-256 válido antes de qualquer análise;
- tampering rejeitado;
- manifest `success=false` rejeitado;
- v2 exige exatamente os cinco outputs;
- v1 exige exatamente os quatro outputs históricos;
- legacy v1 continua analisável;
- Pareto solver remove alternativa dominada;
- Pareto state-abstraction final preserva tradeoffs;
- Pareto de convergence remove alternativa dominada em checkpoint sintético.

## Resultado

A cadeia atual é:

```text
commit
 -> suite manifest v2 hashado
 -> cinco baterias versionadas
 -> analyzer v2
 -> Pareto final-budget + Pareto por checkpoint
 -> repetição/refutação
 -> decisão de engenharia
```

O objetivo não é automatizar uma escolha cedo demais. É tornar explícito **quanto de erro estratégico compramos por tempo, estado e memória**, sem misturar objetos matematicamente incomparáveis.
