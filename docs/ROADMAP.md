# DeepSix — Roadmap canônico até uma IA completa de 6+ / Short Deck

Última atualização estrutural: 16/08/2026.

O roadmap mede **capacidade validada**, não quantidade de código. Um item só muda para `PASS` quando existe gate reproduzível. Implementação sem evidência suficiente permanece `PARTIAL`.

## Definição do objetivo final

O objetivo técnico do DeepSix é chegar a uma cadeia completa:

```text
regras/economia corretas
 -> observação confiável da mesa
 -> reconstrução temporal completa
 -> estado canônico
 -> estratégia multi-street/multiway forte
 -> policy compilada
 -> consulta determinística de baixa latência
 -> decisão auditável
 -> execução fechada em ambiente permitido
 -> replay exato e certificação longa
```

O **alvo estratégico primário passa a ser GGPoker Short Deck cash**, preservando KKPoker como referência/fallback. O Core não será reescrito: deck, evaluator, canonicalização, pot/accounting e infraestrutura de solver continuam compartilhados.

GGPoker e KKPoker **não são tratados como economicamente idênticos**. A regra matemática básica é muito próxima, mas a publicação atual da GGPoker usa 5% de rake e caps por stake/número de jogadores, enquanto KKPoker publica 3% e caps/isenções diferentes. Isso pode alterar estratégia ótima e precisa entrar no utility model correto.

A ativação de um bot/RTA em GGPoker está atualmente proibida pelos Termos e pela Security & Ecology Policy da plataforma. Portanto, o endpoint técnico de autonomia será certificado primeiro em simulador/test environment/permitted environment. A linha GGPoker permanece observação/replay/offline enquanto essa política continuar vigente.

---

# Fase 0 — Plataforma-alvo, regras e economia real

**Status: PARTIAL — pivot para GGPoker iniciado**

## Já feito

- alvo original KKPoker formalizado em `GAME_SPEC_KKPOKER_V0.md`;
- novo alvo **GGPoker-first** formalizado em `TARGET_PLATFORM_GGPOKER_V0.md`;
- deck Short Deck de 36 cartas, ranks 6..A;
- mesas Short Deck com até 6 jogadores;
- Flush > Full House confirmado na documentação específica de GGPoker e KKPoker;
- A6789 como menor straight confirmado;
- best-five Hold'em com zero/uma/duas hole cards;
- modelo de forced bets parameterizado;
- modelo estrutural atual compatível com ante em todos os jogadores e 2A total no Button, mas ainda não congelado para GGPoker por evidência real do cliente;
- No-Limit e full-raise/min-raise representáveis pelo Core;
- rake percentual/cap possui motor exato configurável sem arredondamento inventado;
- diferença econômica GGPoker x KKPoker já identificada e documentada;
- jackpot/promotional deductions separados do evaluator.

## Ainda falta

- provar com cliente/replay real da **GGPoker** o forced-bet baseline exato;
- provar ordem de ação preflop e pós-flop no cliente real;
- congelar min-bet/min-raise/reopen após short all-ins;
- congelar a tabela de stakes/buy-ins/unidades usada pelo cliente;
- confirmar ranking completo específico de produção, inclusive Straight x Trips;
- confirmar rake 5% e caps por quantidade de jogadores contra mãos reais;
- verificar se existe ou não isenção preflop/small-pot na GGPoker Short Deck de produção;
- congelar rounding e timing do rake;
- congelar jackpot deduction de 1 ante e seu threshold/timing exato;
- odd-chip em split pots;
- run-it-multiple-times/cashout/insurance-like features, se disponíveis;
- side-pot settlement;
- sit-out/waiting-seat semantics;
- selecionar oficialmente os primeiros stakes de treino/validação.

**Gate de saída:** uma especificação GGPoker versionada capaz de reproduzir mãos reais sem hipótese oculta.

---

# Fase 1 — Core matemático Short Deck

**Status: PASS para a fundação; OPEN para extensões de plataforma/utility**

## Concluído

- codec 36-card;
- rejeição de ranks 2..5 na fronteira legada;
- 81 starting classes cobrindo exatamente 630 combos;
- evaluator 5/6/7 cartas;
- A6789;
- ranking Short Deck configurado;
- exhaustive audit das 376.992 mãos de cinco cartas;
- oracle independente PokerKit;
- evaluator C++ baseline;
- evaluator C++ lookup exato/rápido;
- paridade Python ↔ C++;
- equity HU exata para validação;
- legal actions `FOLD/CHECK/CALL/RAISE_TO`;
- betting-round state machine;
- full-hand state machine;
- pot e side-pot accounting;
- showdown bruto exato;
- `Fraction` onde odd-chip ainda não foi observado;
- canonicalização de hole-card order;
- canonicalização da ordem das três cartas do flop;
- canonicalização de 24 permutações globais de naipes;
- chairs relativos ao Dealer;
- `ReplayFrame`;
- fingerprints;
- `DecisionToken`;
- detecção de corrupção;
- fuzzing determinístico de mãos completas.

## Ainda falta nesta fase

- profile explícito de regras/economia GGPoker depois que a Fase 0 for congelada;
- fixtures de mãos reais GGPoker convertidas em regression tests;
- testes completos das edge cases que só o cliente revelar.

**Gate de manutenção:** toda evolução posterior deve continuar passando os invariants/oracles do Core.

---

# Fase 2 — OpenHoldem6Plus / Adapter de plataforma

**Status: PARTIAL — boundary funcional; adapter GGPoker ainda não iniciado em mesa real**

## Concluído

- branch operacional dedicada `myoh_private:deepsix_6plus`;
- origem/pin do OpenHoldem operacional registrados;
- migration map para premissas 52-card/SB-BB/1326/2652/prwin/dealposition;
- `ShortDeckRules` C++ independente;
- `TableObservation` C++;
- validator;
- JSON canônico;
- `RawTableSnapshot` read-only sobre `CTableState`/`CPlayer`/`Card`;
- schema raw v2;
- `hero_myturnbits` e `hero_sitting_in` preservados como evidência, não decisão;
- parser/espelho Python;
- workflow CI próprio;
- contratos cross-repo C++ -> JSON -> Python/Core;
- observe/replay-first como princípio do runtime.

## Ainda falta

- abandonar a hipótese de tablemap KKPoker como alvo principal e construir **tablemap GGPoker Short Deck**;
- mapear 2..6 seats e Dealer/Button;
- reconhecer hole cards e board 6..A de forma robusta;
- pot;
- contribuições por jogador;
- balances/stacks;
- status seated/sitting-out/waiting;
- fold/all-in states;
- action buttons;
- amount field/slider semantics para test harness controlado;
- banners/animations/card squeeze/jackpot overlays que possam contaminar scraping;
- detectar mudanças de tema/resolução/DPI;
- importar/usar replay/hand-history quando permitido e disponível;
- eliminar/desabilitar no build final todos os símbolos legados perigosos de 52 cards;
- integrar evaluator/equity Short Deck no caminho nativo que realmente necessitar deles;
- build dedicado Windows reproduzível;
- soak test do observation boundary.

**Gate de saída:** replays/capturas GGPoker produzem o mesmo estado estratégico offline e no runtime, sem divergência silenciosa.

---

# Fase 3 — Reconstrução temporal completa da mão

**Status: PARTIAL avançado**

## Concluído

- projeção raw-chair -> strategic-seat explícita;
- dinheiro decimal -> unidade inteira exata;
- stable-frame gate;
- classificação conservadora de transições;
- `RawEvidenceTimeline`;
- inferência local de `CALL` quando há interpretação monetária única;
- inferência de short all-in CALL;
- inferência de `RAISE_TO` exato quando único;
- recusa deliberada de inventar CHECK/FOLD;
- forced-bet baseline detector;
- hand epochs;
- novo hand index somente quando reset + mudança de Dealer + baseline exato concordam;
- ambiguity contamina `complete_from_hand_start` até novo início provado;
- `RawObservationPipeline`: raw JSON -> validação -> projection -> stable gate -> timeline;
- gate end-to-end sintético.

## Ainda falta com dados GGPoker reais

- timing real de `Pot()`;
- timing de `_bet`;
- timing de `_balance`;
- card backs;
- flags de player state;
- prova confiável de CHECK;
- prova confiável de FOLD;
- clipped forced bets quando um jogador começa short;
- múltiplas ações/animations no mesmo intervalo visual;
- all-ins e folds durante animações;
- side-pot formation;
- board runout automático;
- hand-end/payout confirmation;
- split pot e odd-chip;
- sit-out/join/leave transitions;
- timeout/disconnect;
- recuperar ou marcar corretamente frames perdidos;
- métrica de cobertura dos estados `AMBIGUOUS`.

**Gate de saída:** action history completa de replays reais, sem ação inventada e com incerteza explicitamente mensurada.

---

# Fase 4 — Economia GGPoker exata / Utility model

**Status: PARTIAL**

## Concluído

- `RakeConfig`;
- `compute_exact_rake` com `Fraction`;
- isenção preflop configurável;
- threshold inclusivo configurável;
- percentual/cap explícitos;
- table-size multiplier explícito;
- `requires_rounding`;
- helper em múltiplos de ante sem conversão silenciosa de `BB`;
- separação entre poker utility e promoções/jackpot/rakeback externos.

## Ainda falta

- criar profile específico da GGPoker 5%;
- caps por stake e quantidade de jogadores;
- unit normalization para low/mid/high stakes publicados;
- `ClientRakeRounding` validado;
- timing da retirada do rake;
- confirmar existência/ausência de no-flop/small-pot exemption;
- jackpot 1A >~100 antes com threshold exato;
- rake/main/side pots se necessário para reproduzir payout;
- cashback/rewards/leaderboard apenas como camada econômica secundária;
- decidir formalmente como utility non-constant-sum entra no método de solução;
- definir quais métricas serão usadas em multi-player com rake.

**Gate de saída:** gross pot -> deductions -> net payouts reproduzidos em bateria de mãos GGPoker.

---

# Fase 5 — Laboratório de ação, estado e solver

**Status: IN PROGRESS — infraestrutura madura; primeira bateria Ryzen real ainda pendente**

## Concluído

- Kuhn CFR baseline com valor/exploitability conhecidos;
- river microgame Short Deck com ranges/evaluator reais;
- exact best response por mão privada;
- river 1..4 initial bet sizings sem raise;
- benchmark de custo marginal de action width;
- river one-raise com bet fixo + raise-to;
- exact BR one-raise auditada contra brute force global;
- benchmark `no_raise -> one_raise`;
- multi-size + one-raise S=1/S=2;
- custo enumerativo `(1+S)6^S` explicitado;
- Dynamic Exact Best Response por programação dinâmica;
- DP BR gated contra enumerador em políticas uniformes/treinadas/ranges ponderados;
- linha escalável 1..4 sizings + um raise;
- private-state abstraction lab;
- policy abstrata expandida e julgada no jogo original não abstraído;
- identity bucket reproduz CFR não abstraído;
- `single`;
- `showdown_category`;
- `conditional-equity quantiles` blocker-aware;
- features exatas de range equity;
- universal equity;
- nutness;
- blocked range weight;
- blocked stronger range weight;
- `feature_borda_quantile` equity+nutness+blocker;
- uniform-reference CFVs por mão/infoset;
- `cfv_kmedoids_bucket_map` determinístico;
- gate analítico de incentivos opostos FOLD/CALL;
- River Benchmark Battery v3 em seis texturas;
- `mapping_build_seconds` separado do treino;
- State-Abstraction Convergence v1;
- checkpoints cumulativos;
- cumulative wall-clock;
- exact exploitability/pot por checkpoint;
- Pareto por checkpoint;
- synchronous Regret-Matching+;
- regrets RM+ truncados em zero;
- average strategy delay/peso configurável;
- determinismo/resumibilidade;
- benchmark CFR vs RM+ no mesmo exact oracle;
- Ryzen Benchmark Protocol v2;
- cinco baterias consolidadas;
- manifest com commit/máquina/comandos/hashes;
- analyzer com verificação SHA-256;
- compatibilidade com manifests v1;
- Pareto somente entre objetos comparáveis;
- CI dos gates acima.

## Falta imediatamente

1. executar `python tools/run_ryzen_benchmark_suite.py --profile engineering` no Ryzen 9;
2. analisar a primeira fronteira real erro x wall-clock x nós;
3. repetir candidatos próximos da fronteira;
4. escolher ou rejeitar CFV vs equity/blocker baselines;
5. escolher CFR vs RM+ por custo real, não aparência;
6. decidir se é necessário equal-wall-clock benchmark;
7. decidir próxima riqueza de ação: múltiplos raises, re-raise ou mais states;
8. substituir progressivamente ranges sintéticos por distribuições de estados reais/permitted replays.

## Experimentos antes de encerrar a fase

- múltiplos raise sizes;
- pelo menos uma camada de re-raise se o custo justificar;
- abstraction sensitivity por board texture;
- stack-to-pot sensitivity;
- generalização fora das fixtures de treino;
- stress de ranges skewed/weighted;
- memória por milhão de infosets;
- throughput multi-core real no Ryzen;
- serialization/resume de runs longas;
- detecção de regressão matemática entre commits.

**Gate de saída:** família action/state/solver escolhida por evidência reproduzível no Ryzen 9.

---

# Fase 6 — Primeiro solver multi-street / Blueprint HU

**Status: NOT STARTED**

## Objetivo

Sair do laboratório de river e resolver decisões ligadas entre preflop, flop, turn e river.

## Falta fazer

- public-state representation multi-street;
- chance transitions flop/turn/river;
- canonicalização entre streets;
- stack/pot/to-call/min-raise features;
- action abstraction dependente de SPR;
- preflop limp/raise/jam tree;
- postflop bet/check/raise/re-raise abstractions;
- private abstraction por street;
- transição entre bucket granularities;
- terminal utility com economia configurada;
- CFR/MCCFR/RM+/outro algoritmo escolhido pela Fase 5;
- external/chance sampling se necessário;
- checkpoint/resume;
- deterministic seeds;
- compression/serialization;
- held-out subgame tests;
- local exact/oracle subgames pequenos para auditar aproximações;
- benchmark por CPU-hora;
- blueprint HU inicial;
- política baseline simples para comparação.

**Gate de saída:** blueprint HU multi-street supera baselines simples fora do treino e possui erro/custo mensurado.

---

# Fase 7 — 3-way, 4-way, 5-way e 6-way

**Status: NOT STARTED**

## Objetivo

Modelar o que realmente torna 6+ cash difícil: multiway com stacks, rake e action branching.

## Falta fazer

- state/action representation para 3+ jogadores;
- player elimination/fold order;
- side pots no solver;
- all-in runouts;
- asymmetric stacks;
- 2..6-player starting configurations;
- position/chair symmetries válidas e somente as válidas;
- multiplayer regret method adequado;
- métrica de qualidade para jogo não puramente two-player zero-sum;
- exploitability surrogate/NashConv apropriada;
- rake/deductions no utility;
- sparse/adaptive traversal;
- foco de CPU em states de maior reach/EV/error;
- progressive expansion HU -> 3-way -> 4-way -> 5/6-way;
- curriculum de stacks e pot sizes;
- benchmark de memory pressure;
- shard/checkpoint layout para meses de treino;
- avaliação cross-seat/cross-player-count.

**Gate de saída:** política multiway robusta que cobre realisticamente 2..6 jogadores sem depender de equivalência falsa com HU.

---

# Fase 8 — Estratégia-base completa e treinamento longo no Ryzen

**Status: NOT STARTED**

## Objetivo

Transformar a arquitetura vencedora em um blueprint de cobertura ampla usando semanas/meses do Ryzen de forma eficiente.

## Falta fazer

- selecionar coverage target de stacks/stakes/player counts;
- definir budget de CPU/RAM/disk;
- scheduler de jobs;
- treinamento resumível após reboot/falha;
- filas/shards;
- deterministic/reproducible job manifests;
- prioritized state refinement;
- error heatmaps;
- coverage heatmaps;
- targeted resampling de regiões raras mas caras em EV;
- validation holdout states;
- periodic frozen checkpoints;
- rollback de regressões;
- compaction dos artefatos;
- policy distillation somente se comprar latência/memória sem perda relevante;
- final blueprint selection por out-of-sample suites.

**Gate de saída:** blueprint amplo com força e coverage mensurados, pronto para servir decisões.

---

# Fase 9 — Population model e exploração separada

**Status: NOT STARTED**

## Objetivo

Adicionar adaptação exploratória sem contaminar a estratégia-base.

## Falta fazer

- definir fonte de dados permitida e auditável;
- schema de hand samples;
- opponent identities/aliases apenas onde permitido;
- frequência por action/state abstraído;
- confidence intervals;
- shrinkage para população quando amostra individual é pequena;
- archetypes/clusters;
- sizing tendencies;
- fold/call/raise deviations;
- preflop population frequencies;
- postflop deviations;
- exploit policy bounded por confiança;
- fallback para blueprint quando confiança cai;
- out-of-sample evaluation;
- adversarial robustness;
- limite de exploração para evitar overfit;
- separation `base_policy` x `exploit_overlay`.

**Gate de saída:** ganho out-of-sample demonstrado sem regressão grave contra adversários não modelados.

---

# Fase 10 — Policy compiler, armazenamento e runtime de decisão

**Status: NOT STARTED**

## Objetivo

Transformar artefatos de treino em uma política consultável em tempo real de forma determinística.

## Falta fazer

- policy file format versionado;
- metadata de rules/economy/model version;
- state key canonical;
- lookup exato/nearest abstraction;
- action probability retrieval;
- deterministic RNG por hand/decision token quando sampling for usado;
- fallback para estado não coberto;
- interpolation/refinement se necessário;
- memory mapping/cache;
- startup validation/hash;
- corruption detection;
- policy hot/cold loading design;
- latência p50/p95/p99;
- timeout behavior;
- explain log por decisão;
- replay byte-for-byte da mesma query;
- policy compatibility gate com runtime version.

**Gate de saída:** `canonical state -> audited action distribution` dentro do orçamento de latência, reproduzível offline.

---

# Fase 11 — Integração end-to-end e Shadow Mode

**Status: NOT STARTED**

## Objetivo

Unir observação, reconstrução, policy e auditoria sem executar ações automaticamente na plataforma-alvo.

## Falta fazer

- `raw snapshot -> timeline -> state -> policy query -> decision`;
- validação de seat/position/stacks/pot/action history;
- decisão apenas quando estado completo/confiável;
- fail-closed em `AMBIGUOUS`;
- latência end-to-end;
- replay da decisão contra gravações;
- divergence detector online/offline;
- hand-level decision trace;
- shadow sessions extensas;
- comparar decisão shadow com posterior solver/offline audit;
- detectar stale policy;
- detectar missed frames;
- crash/restart recovery;
- watchdog;
- observability dashboard/logs.

**Gate de saída:** milhares de decisões shadow/replay sem divergência estrutural e com todas as decisões explicáveis.

---

# Fase 12 — Executor autônomo em ambiente permitido

**Status: NOT STARTED**

## Objetivo técnico

Provar que a IA consegue realmente jogar uma mão inteira em closed loop **em simulador, test client ou outra plataforma/ambiente que permita automação**.

## Falta fazer

- action executor abstrato;
- fold/check/call;
- bet/raise-to;
- amount entry;
- action confirmation;
- retry policy limitada;
- detect action accepted/rejected;
- timeout/fail-closed;
- zero double-click/double-action;
- stack cap/all-in handling;
- UI coordinate independence quando possível;
- state-before-action fingerprint;
- state-after-action confirmation;
- autonomous simulator table;
- self-play closed loop;
- fault injection;
- delayed frames;
- dropped observations;
- corrupted policy file;
- unknown UI state;
- long soak test;
- exact replay of autonomous sessions.

**Gate de saída:** IA joga autonomamente sessões longas de 6+ em ambiente permitido sem erro de estado/ação e com replay determinístico.

---

# Fase 13 — Certificação de força e prontidão operacional

**Status: NOT STARTED**

## Falta fazer

- baseline tournaments contra políticas simples;
- frozen-policy A/B;
- cross-check contra solver local em subgames;
- strategy invariance audits;
- exploitability/NashConv proxies onde válidos;
- bankroll/variance simulation;
- rake-aware win-rate simulation;
- stress por player count;
- stress por stack depth;
- rare-state audit;
- latency stress;
- memory/disk stress;
- restart/resume certification;
- version rollback;
- independent replay audit;
- reproducibility package;
- final release manifest;
- `READY FOR 6+ AUTONOMOUS TEST ENVIRONMENT` somente quando todos os gates anteriores passarem.

**Gate de saída:** pacote técnico reproduzível que demonstra força, robustez e autonomia no ambiente permitido.

---

# Fase 14 — Plataforma real / Compliance gate

**Status: BLOCKED para automação live na GGPoker pelas regras atuais da plataforma**

GGPoker atualmente proíbe bots, AI playing, RTA, automated execution, HUD/data-mining e assistência externa em tempo real. Portanto nenhum PASS técnico das fases anteriores muda sozinho essa condição.

Possíveis caminhos legítimos para liberar esta fase no futuro:

- mudança oficial da política da plataforma;
- ambiente oficial de API/bot/teste autorizado;
- autorização expressa aplicável ao uso pretendido;
- outra plataforma/ambiente onde automação seja permitida.

Até lá, GGPoker é alvo de **regras/economia, estudo offline, replay e shadow analysis**, não de execução autônoma live.

---

# Onde estamos agora

```text
F0  Plataforma/regras/economia        PARTIAL   ██████░░░░
F1  Core matemático                   PASS      ██████████
F2  Adapter/OpenHoldem6Plus           PARTIAL   ██████░░░░
F3  Reconstrução temporal             PARTIAL+  ███████░░░
F4  Economia/utility                   PARTIAL   █████░░░░░
F5  Lab abstração/solver              IN PROG   ███████░░░
F6  Blueprint HU multi-street         NOT START ░░░░░░░░░░
F7  Multiway 3-6 jogadores            NOT START ░░░░░░░░░░
F8  Treino longo blueprint            NOT START ░░░░░░░░░░
F9  Population/exploit                NOT START ░░░░░░░░░░
F10 Policy compiler/runtime           NOT START ░░░░░░░░░░
F11 End-to-end shadow                 NOT START ░░░░░░░░░░
F12 Executor ambiente permitido       NOT START ░░░░░░░░░░
F13 Certificação final                NOT START ░░░░░░░░░░
F14 Live platform compliance          BLOCKED   ----------
```

As barras são apenas uma **visualização aproximada de maturidade dentro de cada fase**, não um percentual matemático do projeto.

## Leitura correta do progresso

Temos uma fundação matemática forte, uma boa parte da observação/reconstrução e um laboratório de solver já bastante sofisticado. Porém ainda **não temos o principal artefato estratégico final**: um blueprint multi-street/multiway amplo. Portanto o projeto está avançado em infraestrutura e validação, mas ainda no início da parte mais pesada de força de jogo.

---

# Caminhos críticos a partir de agora

```text
A) Plataforma GGPoker
   spec v0
    -> capturas/replays permitidos
    -> tablemap
    -> forced bets/min-raise/rake/payout congelados
    -> reconstrução completa

B) Estratégia
   Ryzen engineering run
    -> selecionar abstraction/solver
    -> multi-street HU
    -> 3-way
    -> 4-6-way
    -> treino longo

C) Economia
   GGPoker 5% + caps
    -> client rounding
    -> jackpot deductions
    -> net utility

D) Runtime
   policy compiler
    -> shadow mode
    -> autonomous simulator/permitted environment
    -> certification
```

## Próximo gate imediato

O próximo passo com maior informação por hora continua sendo:

```text
python tools/run_ryzen_benchmark_suite.py --profile engineering
```

Em paralelo, precisamos obter **evidência real da GGPoker Short Deck** para não continuar congelando detalhes de KKPoker que talvez não pertençam ao alvo final.

Não iniciaremos uma run de semanas/meses antes de escolher a abstração/solver por evidência e antes de o utility/state semantics do alvo GGPoker estarem suficientemente congelados.
