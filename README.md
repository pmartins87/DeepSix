# DeepSix

DeepSix é o projeto de estratégia para **Poker Cash Game 6+ / Short Deck**, desenvolvido para obter a melhor força de jogo possível dentro de um orçamento computacional realista.

## Princípio central

O objetivo **não é resolver o 6+ perfeitamente** nem provar equilíbrio exato do jogo completo.

O objetivo é:

> **construir a melhor estratégia que conseguirmos obter, validar e executar com segurança dentro das nossas possibilidades reais de hardware e tempo.**

O orçamento de referência é **um Ryzen 9 trabalhando continuamente por semanas ou meses**, com armazenamento e pré-computação extensivos quando úteis, mas sem assumir clusters ou hardware de datacenter.

DeepSix será julgado por força prática, robustez e ganho por CPU-hora. Uma abstração menor e profundamente treinada pode ser melhor do que uma árvore muito maior e superficial. Invariâncias matemáticas devem ser garantidas por construção para que capacidade de treino não seja desperdiçada reaprendendo equivalências triviais.

## Arquitetura

1. **DeepSix Core** — regras, deck, evaluator, pot accounting, ação legal, canonicalização, reconstrução e utilidade.
2. **Trainer/Solver** — CFR/regret/value/policy e demais técnicas que vencerem benchmarks reproduzíveis no orçamento do projeto.
3. **OpenHoldem6Plus** — fork exclusivo do OpenHoldem para observar a mesa e formar estado confiável. Não precisa preservar compatibilidade estratégica com Hold'em 52-card, AoF, Spin ou OFC.
4. **Validation/Replay** — oracles independentes, fuzzing, replays, fingerprints, contratos cross-repo e auditorias de invariância.

### OpenHoldem exclusivo para 6+

Não acrescentaremos o 6+ como uma coleção de exceções no runtime dos outros projetos. O fork dedicado permite remover ou bloquear premissas perigosas de 52 cartas, substituir evaluator/equity/handrank, tratar ante e Button como conceitos nativos e evoluir scraping/state machine sem risco para as outras linhas.

Quando um conceito legado não possui a mesma semântica no 6+, ele deve ser substituído, desabilitado ou marcado como incompatível — nunca reutilizado apenas para aparentar compatibilidade.

## Estado atual — 16/08/2026

A fundação matemática já está validada; o boundary OpenHoldem6Plus existe e possui contrato C++ ↔ Python; a reconstrução temporal conservadora já consegue provar alguns eventos sem inventar ações; a economia possui um motor de rake exato configurável; e o laboratório de solver já avançou de um sizing sem raise para múltiplos sizings e para a primeira árvore com um raise.

O roadmap canônico e seus gates ficam em `docs/ROADMAP.md`.

### Regras atualmente congeladas

- deck com **36 cartas**, apenas 6..A;
- mesas até 6-handed;
- estrutura ante-based, sem modelar SB/BB como forced bets estratégicos;
- modelo atual de forced bets: A nos demais dealt players e **2A totais no Dealer/Button**;
- primeiro jogador à esquerda do Dealer age primeiro em todas as streets;
- No-Limit;
- Flush > Full House;
- A6789 é a menor sequência;
- full raise usa incremento pelo menos igual ao bet/raise anterior da street no modelo estrutural.

A documentação pública de rake do 6+ usa a expressão `5BB` para o limiar de small pot apesar da variante ser ante-based. **DeepSix não converte isso silenciosamente para 10 antes.** A interpretação real permanece aberta até Hand Review/captura do cliente comprovar a cobrança. O mesmo princípio vale para rounding/timing e para eventual redução short-handed.

A especificação completa e ambiguidades estão em `docs/GAME_SPEC_KKPOKER_V0.md`.

## Core matemático validado

Já existem:

- codec compacto 0..35 e rejeição obrigatória de ranks 2..5 na fronteira legada;
- **81 starting-hand classes cobrindo exatamente 630 combos**;
- evaluator de 5 cartas e best-of-5 para 5/6/7 cartas;
- A6789 e ranking Short Deck testados;
- enumeração de **todas as 376.992 mãos de cinco cartas** contra distribuição analítica;
- oracle externo PokerKit pinado;
- equity HU exata para validação;
- pot e side-pot accounting;
- legal-action boundary `FOLD/CHECK/CALL/RAISE_TO`;
- betting-round state machine No-Limit com full raises e short all-ins;
- full-hand state machine `forced bets -> preflop -> flop -> turn -> river -> showdown/fold`;
- runout automático quando não há mais decisão de betting;
- showdown bruto exato, mantendo splits como `Fraction` até odd-chip ser observado;
- canonicalização de hole-card order, flop order, 24 permutações globais de naipes e chairs relativos ao Dealer;
- `ReplayFrame`, `DecisionToken`, fingerprints e detecção de corrupção;
- fuzzing determinístico de mãos completas.

## Evaluator nativo

Há dois caminhos C++ gated:

- `ShortDeckEvaluator`, baseline claro/auditável;
- `FastShortDeckEvaluator`, lookup exato de todas as combinações de cinco cartas.

Os gates exigem paridade do baseline C++ contra Python em todas as 376.992 mãos de cinco cartas e amostras determinísticas de seis/sete cartas; o lookup é comparado contra o baseline em todas as cinco-cartas + 10.000 seis-cartas + 20.000 sete-cartas.

O benchmark de CI é apenas informativo. No run #102 o lookup ficou em ~1,39 milhão de avaliações de sete cartas/s contra ~484 mil do baseline (~2,88x). Esse número **não é extrapolado para o Ryzen 9**; o benchmark versionado deverá ser executado nele antes de investir em estruturas ainda maiores.

## OpenHoldem6Plus

O repositório operacional `pmartins87/myoh_private` possui a branch dedicada `deepsix_6plus`, derivada do baseline operacional registrado no projeto.

Já estão implementados/gated:

- migration map de dependências 52-card/1326/2652/prwin/SB-BB/dealposition;
- `ShortDeckRules` C++ independente;
- `TableObservation` + validator + JSON canônico;
- contrato C++ -> Python/Core com igualdade byte-a-byte/fingerprints;
- `RawTableSnapshot` read-only sobre `CTableState`/`CPlayer`/`Card`;
- **schema raw v2**, preservando `hero_myturnbits` (F/C/K/R/A visíveis) e `hero_sitting_in` como evidência bruta, não como decisão;
- parser/espelho Python do snapshot bruto;
- workflow `DeepSix 6+ boundary CI` restrito à branch dedicada;
- contrato cross-repo que compila o boundary C++ pinado e exige compatibilidade exata no Core.

**Nenhuma ação automática está habilitada no OpenHoldem6Plus.** A linha permanece deliberadamente `observe/replay-first` durante a construção e validação.

## Reconstrução temporal conservadora

A cadeia atual é:

```text
RawTableSnapshot
  -> ProjectedSnapshot
  -> StableSnapshotGate
  -> RawEvidenceTimeline
```

A timeline só infere uma ação quando o delta observado possui interpretação monetária única sob guards estritos.

Atualmente ela consegue inferir:

- `CALL` exato;
- `CALL` all-in curto exato;
- `RAISE_TO` exato, incluindo opening bet postflop sob a semântica do Core.

Ela **não** inventa `CHECK` pelo desaparecimento de botões nem `FOLD` por mera mudança de flags. Estados insuficientes permanecem `AMBIGUOUS`.

Também existe prova estrita de início de mão: um hand epoch só é estabelecido quando o snapshot mostra o baseline exato de forced bets; entre mãos, a confirmação exige regressão para preflop + mudança de Dealer + novo baseline exato. Uma ambiguidade invalida `complete_from_hand_start` até um novo início confiável ser provado.

Detalhes: `docs/RAW_EVIDENCE_TIMELINE_V1.md` e `docs/RAW_HAND_START_EVIDENCE_V1.md`.

## Economia / rake

`deepsix_core.rake` representa percentual e rake como `Fraction` e separa explicitamente:

1. elegibilidade/isenções;
2. percentual/cap exatos;
3. **rounding do cliente, ainda não inventado**.

O engine suporta threshold configurável, cap em unidades exatas e multiplicador short-handed somente quando explicitamente habilitado. O helper Short Deck aceita múltiplos de ante fornecidos pelo chamador e permite deixar o threshold sem resolução (`None`).

Detalhes: `docs/RAKE_MODEL_V1.md`.

Rake variável não será simplesmente inserido no microgame HU e chamado de exploitability zero-sum: quando a retirada depende da trajetória/pot, a soma das utilidades varia. A metodologia econômica será tratada explicitamente antes do blueprint principal.

## Laboratório de solver e abstração

A progressão atual foi deliberadamente incremental:

- Kuhn CFR com valor/exploitability conhecidos;
- river microgame Short Deck com ranges e evaluator reais;
- exact best response escalável por mão privada;
- river multi-size com 1..4 sizings iniciais, sem raises;
- benchmark de custo marginal de número de sizings;
- **river one-raise**, com um bet fixo + um raise-to fixo e sem re-raise;
- exact best response do one-raise auditada contra brute force global independente em ranges pequenos;
- benchmark `no_raise -> one_raise` para medir aumento estrutural e convergência.

No smoke do run #102, adicionar um raise elevou a fixture de 12 para 18 nós (1,5x) e de 24 para 42 action slots (1,75x). O throughput observado em apenas 10 iterações não é usado como conclusão de performance; uma bateria longa e representativa é necessária.

Detalhes: `docs/RIVER_MULTISIZE_V1.md` e `docs/RIVER_ONE_RAISE_V1.md`.

## Validação atual

O último gate de código consolidado, **DeepSix CI #102**, passou com:

- **167 testes Python/Core: PASS**;
- exhaustive 376.992 five-card audit: PASS;
- baseline C++ ↔ Python evaluator: PASS;
- fast lookup C++ ↔ baseline: PASS;
- ShortDeckRules C++: PASS;
- TableObservation validator/JSON C++: PASS;
- C++ -> Python canonical observation/fingerprints: PASS;
- raw reconstruction/timeline/hand-start/rake: PASS;
- river microgame/multi-size/one-raise e exact BR gates: PASS;
- os dois benchmarks de abstração em smoke CI: PASS.

O CI não é usado para transformar números de runner compartilhado em estimativa de Ryzen 9; ele prova corretude/regressão e apenas reporta performance informativa.

## Próximos gates

1. **Capturas reais KKPoker 6+** para congelar chair layout, timing de `Pot/_bet/_balance`, CHECK/FOLD, hand boundary, short-stack forced bets, min-raise/reopen, side pots, sit-out, rake rounding e payouts.
2. Executar os benchmarks versionados em **Ryzen 9** e medir custo marginal com iterações suficientemente longas.
3. Evoluir o laboratório para **múltiplos sizings + um raise**, aumentando apenas uma dimensão de cada vez.
4. Definir formalmente a metodologia de utility/solução quando houver rake e, depois, jogo multiway.
5. Só então escalar para protótipos multi-street/blueprint, evitando gastar meses de CPU sobre estado, economia ou abstração errados.

## Filosofia de engenharia

### Correção antes de escala

Uma run de meses sobre uma representação errada é pior que uma run curta sobre um modelo correto.

### Eficiência representa força

Capacidade economizada deve ser convertida, quando útil, em mais conhecimento estratégico: mais estados, melhores abstrações, mais iterações, maior capacidade ou refinamento dirigido.

### Evidência acima de intuição

Arquiteturas e abstrações só são promovidas por testes reproduzíveis. Uma V2 mais elegante não vence por parecer superior; um resultado surpreendente também não é aceito sem auditoria de viés, bug ou desperdício.

### Melhor possível, não perfeito

Não existe gate artificial de “GTO completo”. O roadmap continua enquanto houver forma mensurável de converter orçamento disponível em estratégia melhor.
