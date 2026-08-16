# DeepSix — Roadmap canônico

Última atualização estrutural: 16/08/2026.

O roadmap mede **capacidade validada**, não quantidade de código. Um item só muda para `PASS` quando existe gate reproduzível; implementação sem evidência suficiente permanece `PARTIAL`.

## Fase 0 — Regras, economia e alvo real

**Status: PARTIAL**

Já congelado/testado:

- deck Short Deck 36 cartas, 6..A;
- Flush > Full House;
- A6789 como menor straight;
- estrutura ante-based e Dealer com dois antes totais no modelo atual;
- ação clockwise a partir da esquerda do Dealer;
- No-Limit e regra estrutural de full raise parametrizada;
- rake percentual/cap possui motor exato configurável, sem arredondamento inventado.

Ainda depende de evidência do cliente/Hand Review:

- interpretação real do threshold de rake publicado como `5BB` em uma variante sem blinds;
- rounding/timing do rake;
- aplicação exata da redução de rake short-handed ao 6+;
- min-raise/reopen após sequência de short all-ins;
- odd-chip em split pots;
- buy-in/stack conventions por stake alvo;
- side-pot rendering/timing;
- sit-out/waiting-seat semantics.

**Gate de saída:** uma especificação versionada capaz de reproduzir hand reviews reais sem hipótese oculta.

## Fase 1 — Core matemático Short Deck

**Status: PASS para a fundação; OPEN para extensões**

Concluído:

- codec 36-card;
- 81 starting classes / 630 combos;
- evaluator 5/6/7 cartas;
- exhaustive 376.992 five-card audit;
- oracle independente PokerKit;
- evaluator C++ baseline e lookup exato;
- equity HU exata para validação;
- legal actions;
- betting-round state machine;
- full-hand state machine;
- pot/side-pot accounting;
- showdown bruto exato;
- canonicalização de naipes, hole order, flop order e chairs relativos;
- replay/fingerprint/DecisionToken;
- fuzzing de mãos completas.

**Gate de manutenção:** qualquer mudança estratégica posterior deve continuar passando todos os invariants e oracles desta fase.

## Fase 2 — OpenHoldem6Plus dedicado

**Status: PARTIAL, boundary funcional**

Concluído:

- branch operacional dedicada `myoh_private:deepsix_6plus`;
- origem/pin do OH operacional registrados;
- migration map para premissas 52-card/SB-BB/1326/prwin;
- `ShortDeckRules` C++ independente;
- `TableObservation` C++ + validator + JSON canônico;
- `RawTableSnapshot` read-only sobre `CTableState`/`CPlayer`/`Card`;
- schema raw v2 preservando `hero_myturnbits` e `hero_sitting_in` como evidência;
- boundary CI próprio;
- contratos cross-repo C++ -> JSON -> Python/Core.

Ainda falta:

- tablemap real KKPoker 6+;
- captura/replay contínua de mãos reais;
- eliminar/desabilitar todos os símbolos legados perigosos no build final;
- integração do evaluator/equity Short Deck no caminho nativo que realmente precisar deles;
- build/runtime dedicado certificado em Windows com mesa real.

**Gate de saída:** replay de sessões reais produzindo o mesmo estado estratégico offline e no runtime, sem divergência silenciosa.

## Fase 3 — Reconstrução temporal da mão

**Status: PARTIAL avançado**

Concluído:

- projeção raw-chair -> strategic-seat explícita;
- dinheiro decimal -> unidade inteira exata;
- stable-frame gate;
- classificação conservadora de transições;
- `RawEvidenceTimeline`;
- inferência local somente de `CALL` e `RAISE_TO` quando existe exatamente uma interpretação contábil;
- recusa deliberada de inferir CHECK/FOLD por sinais insuficientes;
- detector exato de forced-bet baseline;
- hand epochs: um novo hand index só nasce quando reset + mudança do Dealer + baseline exato concordam;
- ambiguity taints `complete_from_hand_start` até um novo início de mão ser novamente provado;
- `RawObservationPipeline` compõe **raw JSON -> validação -> projection -> stable gate -> timeline** sem acrescentar semântica e já possui gate end-to-end sintético.

Ainda falta:

- validar timing real de `Pot()`, `_bet`, `_balance`, card backs e flags;
- prova real de CHECK;
- prova real de FOLD;
- clipped forced bets / short stack no início da mão;
- folds/all-ins simultâneos a animações do cliente;
- confirmação robusta de hand end/payout.

**Gate de saída:** action history completa de replays reais com zero ação inventada e cobertura mensurada de estados `AMBIGUOUS`.

## Fase 4 — Economia exata

**Status: PARTIAL**

Concluído:

- `RakeConfig` e `compute_exact_rake` com `Fraction`;
- isenção preflop configurável;
- threshold inclusivo configurável;
- percentual, cap e short-table multiplier explícitos;
- `requires_rounding` preserva casos ainda não inteiros;
- helper por múltiplos de ante sem converter `BB` implicitamente.

Ainda falta:

- `ClientRakeRounding` validado por mãos reais;
- distribuição de rake entre main/side pots se necessária para reproduzir payouts;
- PVI/rakeback como camada econômica separada;
- jackpot/fees apenas se fizerem parte do stake/ambiente alvo;
- decidir formalmente como economia non-constant-sum entra no método de solução.

**Gate de saída:** gross pot -> rake -> net payout reproduzido contra Hand Review/client em uma bateria representativa.

## Fase 5 — Laboratório de abstração e solver

**Status: IN PROGRESS — ação, estado privado e algoritmo river já possuem comparação sob oracle exato comum**

Concluído:

- Kuhn CFR baseline com valor/exploitability conhecidos;
- river microgame Short Deck com ranges/evaluator reais;
- exact best response escalável por mão privada;
- river multi-size 1..4 sizings, ainda sem raise;
- benchmark de custo marginal de número de sizings;
- river one-raise: uma aposta fixa + um raise-to fixo, sem re-raise;
- exact BR do one-raise auditada contra brute force global independente;
- benchmark `no_raise -> one_raise`;
- **river multi-size + one-raise** com S=1/S=2 auditado contra o one-raise anterior e brute force global;
- exact BR por enumeração torna explícito o custo `(1+S)6^S` planos/mão;
- **Dynamic Exact Best Response** por programação dinâmica de infosets, gated contra a BR enumerativa em S=1/S=2, política uniforme, política treinada e ranges ponderados;
- `ScalableRiverMultiSizeOneRaiseConfig` libera **1..4 sizings + um raise** sem usar o enumerador exponencial na exploitability;
- benchmark escalável de prefixes 1..4 sizes + raise;
- **private-state abstraction lab**: o CFR pode agrupar combos exatos em buckets, mas a política é expandida novamente e julgada pela Dynamic Exact BR do jogo não abstraído;
- identity bucket reproduz exatamente o CFR sem abstração sob as mesmas iterações;
- baselines de compressão `single`, `showdown_category` e `conditional-equity quantiles`, com equity blocker-aware;
- abstração propositalmente grosseira produz perda visível na exploitability exata não abstraída;
- **River Benchmark Battery v1** com seis texturas Short Deck e ranges sintéticos gerados mecanicamente a partir dos 465 combos possíveis por board, evitando seleção manual favorável a uma hipótese;
- benchmark agregado de state abstraction mede média, mediana e pior caso de exploitability/pot, além de nós, slots e throughput;
- **synchronous Regret-Matching+** implementado como segundo algoritmo mantendo a mesma árvore/chance/utility, regrets truncados em zero e average strategy com delay/peso linear ou uniforme;
- RM+ possui gates de regrets não negativos, convergência, determinismo e resumibilidade; não existe gate artificial exigindo que ele vença o CFR baseline;
- benchmark `CFR vs RM+` usa a mesma River Benchmark Battery e a mesma Dynamic Exact BR, registrando exploitability/pot por wall-clock em checkpoints cumulativos;
- **Ryzen Benchmark Protocol v1** e `run_ryzen_benchmark_suite.py` consolidam action abstraction, multi-size+raise, state-abstraction battery e solver-algorithm battery em uma execução auditável com commit, máquina, parâmetros, logs e SHA-256 dos resultados.

Próximos experimentos:

1. executar `--profile engineering` no Ryzen 9 e registrar a primeira fronteira real `CPU/memória/wall-clock -> erro estratégico` do projeto;
2. repetir os casos próximos da fronteira para separar ganho estratégico de ruído de wall-clock antes de promover CFR ou RM+;
3. adicionar features privadas mais informativas — blockers, nutness e counterfactual values — sempre contra identity e Dynamic Exact BR;
4. decidir, a partir dos dados, se a próxima expansão de ação deve ser múltiplos raise sizes, re-raise ou maior cobertura de estados;
5. preparar o primeiro protótipo multi-street somente quando a abstração river mostrar uma região de custo/qualidade defensável;
6. substituir gradualmente ranges sintéticos por distribuições derivadas de estados/replays reais quando as capturas do cliente existirem.

**Gate de saída:** família de abstração/algoritmo escolhida por benchmark reproduzível no Ryzen 9, sem depender de uma única fixture favorável ou de iterações/s isoladas.

## Fase 6 — Blueprint escalável

**Status: NOT STARTED**

Objetivo:

- sair dos microgames para uma política multi-street;
- primeiro HU/subgames controlados, depois 3-way e 6-way conforme custo;
- treino resumível e determinístico onde aplicável;
- priorização adaptativa de estados de maior erro/EV;
- armazenamento/lookup compatível com runtime.

**Gate de saída:** blueprint offline que supera baselines simples em suites de avaliação fora do treino e possui custo medido no Ryzen 9.

## Fase 7 — Multiway e exploração

**Status: NOT STARTED**

Objetivo:

- modelar o componente 3+ players sem fingir equivalência com HU;
- definir métricas apropriadas para jogo multi-player e economia com rake;
- adicionar população/opponent model somente depois do baseline robusto;
- separar estratégia-base de adaptações exploratórias para preservar auditabilidade.

**Gate de saída:** ganhos out-of-sample demonstrados sem regressão grave de robustez.

## Fase 8 — Integração e certificação

**Status: NOT STARTED**

Objetivo técnico:

- `real table -> raw snapshots -> timeline -> canonical state -> policy query -> audited decision`;
- replay determinístico da mesma decisão;
- latência e timeout definidos;
- fail-closed em estado desconhecido/ambíguo;
- logging suficiente para explicar toda decisão.

A linha OpenHoldem6Plus permanece **observe/replay-first** durante a construção. Nenhum gate técnico autoriza automaticamente uso em ambiente que proíba bots ou assistência em tempo real; conformidade com as regras da plataforma é uma decisão operacional separada.

## Dependências críticas atuais

Existem três caminhos que avançam em paralelo:

```text
A) OH6Plus / reconstrução
   agora -> capturas reais -> congelar semantics -> replay completo

B) estratégia
   agora -> Ryzen benchmark suite -> escolha action/state/solver -> multi-street prototype

C) economia
   agora -> exact rake algebra -> capturas/rounding -> utility model
```

O caminho crítico imediato não é “treinar por meses”. Antes de uma run longa, precisamos provar que o estado, as ações, o evaluator e a economia que alimentam o treino correspondem ao jogo real e que a complexidade escolhida compra força suficiente por CPU-hora.