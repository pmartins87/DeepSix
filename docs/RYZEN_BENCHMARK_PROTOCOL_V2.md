# DeepSix — Ryzen Benchmark Protocol v2

## Objetivo

Os números de performance do GitHub Actions servem para regressão informativa. Eles não representam o Ryzen 9 que será usado como orçamento computacional real do projeto.

`tools/run_ryzen_benchmark_suite.py` transforma uma execução local em evidência reproduzível, comparável entre commits e auditável meses depois.

A **v2** mantém os quatro outputs da v1 e acrescenta uma quinta linha: `state_abstraction_convergence`. O manifest passa a usar:

```text
deepsix_ryzen_benchmark_suite_v2
```

`tools/analyze_ryzen_benchmark_suite.py` continua aceitando manifests v1. Runs históricos não são invalidados pela mudança de contrato.

O runner não promove algoritmo, sizing ou bucket automaticamente. Ele apenas executa benchmarks versionados e registra exatamente o que foi medido.

## Pré-condições

Para uma medição destinada a decisão de engenharia:

1. usar um commit conhecido da `main`;
2. trabalhar com repositório limpo — o runner recusa mudanças não commitadas por padrão;
3. evitar outras cargas pesadas concorrentes na máquina;
4. registrar o profile usado;
5. conservar a pasta de output inteira, não apenas valores copiados à mão.

`--allow-dirty` existe somente para experimentação local e o manifest registra explicitamente que o estado estava sujo.

## Perfis

### smoke

Valida wiring. Usa budgets minúsculos e limita as baterias caras à primeira fixture.

- action abstraction: 10 iterações;
- scalable multi-size + raise: 10;
- state-abstraction battery: 1, primeira fixture;
- state-abstraction convergence: checkpoints 1/2, primeira fixture;
- solver algorithms: checkpoint 2, primeira fixture.

Não serve para escolher arquitetura.

### engineering

Primeira execução comparativa útil:

- action abstraction: 5.000 iterações por caso;
- scalable multi-size + raise: 3.000;
- state-abstraction battery v3: 1.000 por caso, todas as fixtures;
- state-abstraction convergence: checkpoints 100/300/1.000, todas as fixtures, largura principal 4 buckets;
- solver algorithms: checkpoints 100/300/1.000/3.000, todas as fixtures.

Esse profile é a referência inicial para decidir onde gastar mais CPU.

### long

Aumenta os budgets para observar melhor convergência:

- action abstraction: 30.000;
- scalable multi-size + raise: 15.000;
- state-abstraction battery: 5.000 por caso;
- state-abstraction convergence: checkpoints 300/1.000/3.000/5.000;
- solver algorithms: checkpoints 300/1.000/3.000/10.000.

Não existe obrigação de executar `long` inteiro antes de analisar `engineering`. Se uma opção estiver claramente dominada em custo/erro, o experimento deve ser redesenhado antes de queimar CPU.

## Comando

Na raiz do repositório:

```text
python tools/run_ryzen_benchmark_suite.py --profile engineering
```

Por padrão os resultados vão para:

```text
benchmark_runs/YYYYMMDDTHHMMSSZ_<profile>_<commit12>/
```

## Manifest v2

Cada pasta contém `manifest.json` com:

- `suite=deepsix_ryzen_benchmark_suite_v2`;
- commit Git exato;
- flag/status de working tree suja;
- plataforma, Python, executable e logical CPU count;
- parâmetros do profile;
- linha de comando exata de cada benchmark;
- horário e wall time;
- return code;
- nome e SHA-256 de cada JSON;
- nome e SHA-256 do log stdout/stderr.

O manifest é regravado depois de cada benchmark. Se uma etapa falhar, o estado parcial permanece registrado com `success=false`.

## Cinco benchmarks incluídos

### action_abstraction

Compara largura de initial bet sizings na fixture controlada. Mede custo estrutural de action width em isolamento.

### scalable_multisize_raise

Compara prefixes de 1..4 sizes com uma camada de raise e Dynamic Exact BR. Mede interação entre largura inicial e resposta agressiva.

### state_abstraction_battery

Usa a bateria v3 de seis texturas e compara:

- identity;
- conditional-equity quantiles;
- equity + nutness + blocker Borda quantiles;
- uniform-reference CFV k-medoids;
- showdown category;
- single bucket.

A política abstrata é sempre expandida e julgada no jogo exato não abstraído. A v3 mede também `mapping_build_seconds`.

### state_abstraction_convergence

Mantém uma largura principal fixa e treina cada mapping cumulativamente em múltiplos checkpoints.

Registra por checkpoint:

- mean/median/worst exploitability/pot;
- cumulative training seconds;
- iterations/s;
- nós/action slots;
- mapping build cost.

O mesmo número de iterações **não é tratado como custo igual**. Wall-clock real é preservado e usado pelo analyzer como eixo de custo.

### solver_algorithms

Compara vanilla synchronous CFR e synchronous RM+ nos mesmos jogos e no mesmo exact oracle, em checkpoints cumulativos.

## Analyzer v2

`tools/analyze_ryzen_benchmark_suite.py` primeiro verifica todos os SHA-256. Só depois calcula métricas derivadas.

Para solver, compara métodos no mesmo jogo/checkpoint.

Para state abstraction final-budget, a fronteira usa:

```text
mean exploitability/pot ↓
max exploitability/pot  ↓
mean nodes               ↓
iterations/s             ↑
```

Para state convergence, a fronteira de cada checkpoint usa:

```text
mean exploitability/pot              ↓
max exploitability/pot               ↓
mean cumulative training seconds     ↓
mean nodes                            ↓
```

O mapping-build cost é reportado separadamente porque é custo one-shot/precompute e pode amortizar de modo diferente do treino.

Para action spaces diferentes, o analyzer não cria ranking por exploitability. A métrica pertence a jogos diferentes e é usada apenas como diagnóstico de convergência/estrutura.

## Compatibilidade com v1

Um manifest `deepsix_ryzen_benchmark_suite_v1` continua sendo:

1. verificado integralmente por SHA-256;
2. analisado nos quatro outputs originais;
3. marcado com `state_abstraction_convergence = null`;
4. preservado como evidência histórica válida.

Não converter ou editar manifests antigos para fingir que são v2.

## Repetições

Antes de promover diferença pequena de performance, repetir o mesmo commit/profile é preferível a confiar em uma única medição de wall-clock.

Resultados estratégicos idênticos com wall times diferentes são evidência de ruído de máquina, não de mudança do solver.

Uma família de abstração não deve ser promovida por aparecer na fronteira de um único checkpoint. O sinal relevante é permanecer perto da fronteira em múltiplos checkpoints e fixtures.

## O que v2 ainda não mede

- uso máximo de RAM por processo;
- energia/temperatura/throttling;
- paralelismo multi-process/multi-core do trainer futuro;
- GPU;
- equal-wall-clock training budgets controlados diretamente;
- multi-street blueprint;
- ranges do cliente real;
- rake/utility não-zero-sum.

O wall-clock da convergence v1 é medido a posteriori em checkpoints de iteração iguais. Um runner de equal-wall-clock só deve ser adicionado se as primeiras curvas reais do Ryzen mostrarem que isso muda a decisão.

## Gate para usar resultados em decisões

Uma decisão relevante de arquitetura deve registrar:

1. commit + manifest da execução;
2. profile;
3. quais casos/fixtures/checkpoints sustentam a conclusão;
4. se a vantagem é de erro, wall-clock, tamanho de árvore ou combinação deles;
5. se existe pior caso que contradiz a média;
6. se custo de mapping é material ou amortizável;
7. qual próximo experimento poderia refutar a conclusão.

Isso impede que uma única taxa de iterações/s, uma fixture favorável ou um checkpoint isolado vire “verdade” do projeto sem contexto.
