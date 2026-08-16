# DeepSix — Ryzen Benchmark Protocol v1

## Objetivo

Os números de performance do GitHub Actions servem apenas para regressão informativa. Eles não representam o Ryzen 9 que será usado como orçamento computacional real do projeto.

`tools/run_ryzen_benchmark_suite.py` cria um protocolo único para transformar uma execução local em evidência reproduzível, comparável entre commits e auditável meses depois.

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

Valida wiring. Usa budgets minúsculos e limita as baterias caras à primeira fixture. Não serve para escolher arquitetura.

### engineering

Primeira execução comparativa útil:

- action abstraction: 5.000 iterações por caso;
- scalable multi-size + raise: 3.000;
- state-abstraction battery: 1.000 por caso, todas as fixtures;
- solver algorithms: checkpoints 100/300/1.000/3.000, todas as fixtures.

Esse profile é a referência inicial para escolher onde gastar mais CPU.

### long

Aumenta os budgets para observar melhor convergência:

- action abstraction: 30.000;
- scalable multi-size + raise: 15.000;
- state-abstraction battery: 5.000 por caso;
- solver algorithms: checkpoints 300/1.000/3.000/10.000.

Não existe obrigação de executar `long` inteiro antes de analisar `engineering`. Se uma opção já estiver claramente dominada em custo/erro, podemos redesenhar o experimento antes de queimar CPU.

## Comando

Na raiz do repositório:

```text
python tools/run_ryzen_benchmark_suite.py --profile engineering
```

Por padrão os resultados vão para:

```text
benchmark_runs/YYYYMMDDTHHMMSSZ_<profile>_<commit12>/
```

## Manifest

Cada pasta contém `manifest.json` com:

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

## Benchmarks incluídos

### action_abstraction

Compara 1..4 initial bet sizings sem raise na fixture controlada original. Mede custo de action width em isolamento.

### scalable_multisize_raise

Compara prefixes de 1..4 sizes com uma camada de raise e Dynamic Exact BR. Mede a interação entre largura inicial e resposta agressiva.

### state_abstraction_battery

Executa a bateria de seis texturas e compara identity, quantis de equity, category e single bucket. A política abstrata é sempre julgada no jogo exato não abstraído.

### solver_algorithms

Compara vanilla synchronous CFR e synchronous RM+ nos mesmos jogos e no mesmo exact oracle, em checkpoints cumulativos.

## Como interpretar

A unidade de decisão não é “quem fez mais iterações/s”. Queremos uma fronteira de eficiência.

Para solver:

```text
wall-clock / CPU-hora
    -> exact exploitability / pot
```

Para state abstraction:

```text
nós / slots / memória / throughput
    -> mean + worst-case exact exploitability / pot
```

Para action abstraction, valores de exploitability pertencem a espaços de ações diferentes; eles são úteis como diagnóstico de convergência, mas não constituem sozinhos uma comparação de qualidade entre árvores. A pergunta relevante é quanto custa enriquecer a árvore e, depois, se essa riqueza melhora decisões quando comparada por um protocolo apropriado.

## Repetições

Antes de promover uma diferença pequena de performance, repetir o mesmo commit/profile pelo menos algumas vezes é preferível a confiar em uma única medição de wall-clock. A estratégia matemática deve ser determinística; throughput do sistema operacional não é.

Resultados estratégicos idênticos com wall times diferentes são evidência de ruído de máquina, não de mudança do solver.

## O que este protocolo ainda não mede

- uso máximo de RAM por processo;
- energia/temperatura/throttling;
- paralelismo multi-process/multi-core do trainer futuro;
- GPU;
- multi-street blueprint;
- ranges do cliente real;
- rake/utility não-zero-sum.

Essas métricas serão adicionadas quando passarem a influenciar a escolha de arquitetura. A v1 evita instrumentação complexa antes de existir carga que justifique isso.

## Gate para usar resultados em decisões

Uma decisão relevante de arquitetura deve registrar:

1. commit + manifest da execução;
2. profile;
3. quais casos/fixtures sustentam a conclusão;
4. se a vantagem é de erro, wall-clock, tamanho de árvore ou combinação deles;
5. se existe pior caso que contradiz a média;
6. qual próximo experimento poderia refutar a conclusão.

Isso impede que uma única taxa de iterações/s ou uma fixture favorável vire “verdade” do projeto sem contexto.
