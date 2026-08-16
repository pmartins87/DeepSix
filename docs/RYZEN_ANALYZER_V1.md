# DeepSix — Ryzen Benchmark Analyzer v1

## Objetivo

A suíte `run_ryzen_benchmark_suite.py` produz evidência bruta e um manifest com hashes. O analyzer adiciona uma segunda etapa separada:

```text
benchmark run
  -> verificar SHA-256 de todos os outputs/logs
  -> carregar somente evidência íntegra
  -> resumir comparações que realmente vivem no mesmo espaço
  -> identificar candidatos não dominados
```

A separação é deliberada: o runner mede; o analyzer interpreta estrutura comparável. Nenhum dos dois altera estratégia ou promove uma arquitetura automaticamente.

## Uso

Depois de concluir uma pasta de benchmark:

```text
python tools/analyze_ryzen_benchmark_suite.py benchmark_runs/<run_dir> --output analysis.json
```

Se qualquer JSON/log tiver sido alterado depois da execução, o SHA-256 deixa de coincidir e a análise é recusada.

## Solver Pareto

CFR e RM+ usam a mesma chance, árvore e Dynamic Exact Best Response. No checkpoint final do run, o analyzer calcula por algoritmo:

- mean exploitability/pot;
- worst-case exploitability/pot;
- mean training wall time;
- mean iterations/s.

Para Pareto, os três primeiros critérios comparáveis são minimizados:

```text
mean error
worst error
wall time
```

Um algoritmo é marcado dominado somente se outro for pelo menos tão bom em todos e estritamente melhor em pelo menos um.

Pertencer à fronteira de Pareto **não promove automaticamente** o algoritmo. Resultados próximos devem ser repetidos e checkpoints anteriores/piores fixtures precisam ser examinados.

## State-abstraction Pareto

Todas as abstrações privadas usam a mesma action tree e são julgadas no jogo exato não abstraído. O analyzer usa:

- mean exploitability/pot — menor é melhor;
- worst exploitability/pot — menor é melhor;
- mean nodes — menor é melhor;
- mean iterations/s — maior é melhor.

Isso produz um conjunto de métodos não dominados em qualidade/compressão/throughput.

A regra permanece conservadora: uma abstração que ganha muito em média mas possui um pior caso grave não é escondida por uma pontuação única.

## Action abstraction

O analyzer **não cria um ranking Pareto estratégico** entre action spaces diferentes.

Adicionar sizings ou raises muda o jogo no qual exploitability é definida; comparar diretamente os números pode punir uma árvore rica simplesmente porque o adversário também ganhou novas ações.

Por isso action-abstraction e scalable-multisize-raise são reportados como evidência estrutural/throughput. Uma comparação de força entre action abstractions exigirá um protocolo de tradução/evaluation em um action space de referência comum.

## Gates

A suíte do analyzer exige:

- manifest v1 bem formado e `success=true`;
- presença de todos os quatro outputs esperados;
- SHA-256 válido de cada output e stdout/stderr log;
- tampering rejeitado antes de qualquer métrica;
- Pareto solver correto em fixture sintética;
- Pareto state-abstraction conserva tradeoffs e remove método realmente dominado;
- manifest incompleto/fracassado rejeitado.

## Papel no roadmap

Com runner + analyzer, o primeiro benchmark real no Ryzen passa a produzir não apenas quatro arquivos soltos, mas uma cadeia auditável:

```text
commit
 -> manifest hashado
 -> resultados versionados
 -> análise verificada
 -> candidatos Pareto
 -> repetição/refutação
 -> decisão de engenharia documentada
```

Isso reduz o risco de escolher uma arquitetura por uma leitura informal de console ou por um único número favorável.
