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
- rake percentual/cap agora possui motor exato configurável, sem arredondamento inventado.

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
- ambiguity taints `complete_from_hand_start` até um novo início de mão ser novamente provado.

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
- decidir formalmente como economia não-constant-sum entra no método de solução.

**Gate de saída:** gross pot -> rake -> net payout reproduzido contra Hand Review/client em uma bateria representativa.

## Fase 5 — Laboratório de abstração e solver

**Status: IN PROGRESS**

Concluído:

- Kuhn CFR baseline com valor/exploitability conhecidos;
- river microgame Short Deck com ranges/evaluator reais;
- exact best response escalável por mão privada;
- river multi-size 1..4 sizings, ainda sem raise;
- benchmark de custo marginal de número de sizings;
- river one-raise: uma aposta fixa + um raise-to fixo, sem re-raise;
- exact BR do one-raise auditada contra brute force global independente;
- benchmark `no_raise -> one_raise` preparado e CI-smokeado.

Próximos experimentos:

1. medir `no_raise -> one_raise` em bateria maior de boards/ranges/pot/SPR;
2. introduzir múltiplos sizings + um raise sem misturar outras dimensões;
3. testar abstração de cartas/estados mantendo os mesmos action games;
4. comparar CFR/CFR+/MCCFR/alternativas somente em jogos com oracle barato;
5. medir ganho estratégico por CPU-hora e memória, não somente exploitability final.

**Gate de saída:** família de abstração/algoritmo escolhida por benchmark reproduzível, adequada ao Ryzen 9.

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
   agora -> river abstraction labs -> multi-street prototypes -> blueprint

C) economia
   agora -> exact rake algebra -> capturas/rounding -> utility model
```

O caminho crítico imediato não é “treinar por meses”. Antes de uma run longa, precisamos provar que o estado, as ações, o evaluator e a economia que alimentam o treino correspondem ao jogo real.
