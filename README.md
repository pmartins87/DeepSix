# DeepSix

DeepSix é o projeto de estratégia para **Poker Cash Game 6+ / Short Deck**, desenvolvido para obter a melhor força de jogo possível dentro de um orçamento computacional realista.

## Princípio central

O objetivo **não é resolver o 6+ perfeitamente** nem provar equilíbrio exato do jogo completo.

O objetivo é:

> **construir a melhor estratégia que conseguirmos obter, validar e executar com segurança dentro das nossas possibilidades reais de hardware e tempo.**

O orçamento de referência é **um processador Ryzen 9 trabalhando continuamente por semanas ou meses**, com possibilidade de usar armazenamento e pré-computação extensivos, mas sem assumir clusters, GPUs de datacenter ou recursos computacionais irreais para o projeto.

Essa filosofia é diferente da adotada em jogos muito menores, como All-in or Fold, onde uma aproximação extremamente próxima do ótimo pode ser atingível dentro do orçamento disponível. Em DeepSix, por causa da árvore multi-street, sizings, stacks e jogo multiway, aceitaremos abstração e aproximação quando elas produzirem uma estratégia melhor dentro do mesmo orçamento.

## Critério de sucesso

DeepSix será julgado por **força prática e robustez**, não por perfeição teórica.

Isso implica:

- nunca gastar enorme capacidade computacional perseguindo precisão irrelevante enquanto regiões importantes do jogo continuam mal treinadas;
- preferir uma abstração bem escolhida e profundamente treinada a uma árvore quase completa e superficial;
- usar invariâncias matemáticas e canonicalização para que capacidade de treino não seja desperdiçada aprendendo equivalências triviais;
- concentrar amostras e refinamento onde o erro estratégico ou o impacto em EV é maior;
- validar regras, evaluator, pot accounting e transições de estado antes de aumentar a complexidade da rede/solver;
- manter versões simples como baselines e só aceitar arquiteturas mais pesadas quando houver ganho medido;
- usar dados, testes adversariais e benchmarks para decidir entre alternativas, sem assumir que a arquitetura mais sofisticada necessariamente será melhor.

## Arquitetura do projeto

DeepSix terá quatro blocos deliberadamente separados:

1. **DeepSix Core** — regras, deck, evaluator, pot accounting, ação legal, canonicalização e estado estratégico. É a fonte matemática de verdade.
2. **Trainer/Solver** — geração de experiência, CFR/regret/value/policy e demais técnicas que forem vencendo os benchmarks no Ryzen 9.
3. **OpenHoldem6Plus** — fork exclusivo do OpenHoldem para 6+. Não precisa preservar compatibilidade estratégica com Hold'em 52-card, AoF ou OFC. Sua função principal será observar a mesa, formar um estado confiável, consultar o DeepSix e executar a ação correta.
4. **Validation/Replay** — testes, replays, fuzzing, auditoria de invariâncias e comparação runtime ↔ engine.

### Decisão estrutural: OpenHoldem exclusivo para 6+

Não vamos acrescentar o 6+ como mais um conjunto de exceções dentro do OpenHoldem usado pelos outros projetos. O DeepSix terá uma **versão própria do OpenHoldem**, com nome/build/runtime próprios.

Isso permite:

- remover ou desabilitar premissas de Hold'em 52-card que seriam perigosas no Short Deck;
- substituir evaluator/equity/handrank sem medo de quebrar DeepKK, SpinCore ou outros runtimes;
- tratar ante e button blind como conceitos nativos, em vez de fingir que são SB/BB;
- criar símbolos e logs específicos de Short Deck;
- evoluir a máquina de estados e o autoplayer de acordo com as necessidades reais do DeepSix;
- manter testes de regressão independentes.

O fork do OpenHoldem começa **em paralelo** ao núcleo matemático. A integração da política treinada ocorre mais tarde, mas não deixaremos para descobrir problemas de scraping, posições, forced bets ou bet sizing somente no fim do projeto.

## Escopo inicial

1. Formalizar exatamente as regras do 6+ alvo.
2. Implementar e testar um motor Short Deck de 36 cartas.
3. Implementar evaluator correto, incluindo a ordenação de mãos da variante e a sequência A-6-7-8-9 quando aplicável.
4. Criar representação canônica de cartas, boards, suits, posições, stacks, potes e histórico de ações.
5. Iniciar o fork **OpenHoldem6Plus**, preservando o que é útil do scraper/autoplayer e isolando tudo que assume 52 cartas, SB/BB ou rankings tradicionais.
6. Construir um ambiente de jogo determinístico e auditável.
7. Definir uma abstração de ações compatível com o orçamento computacional.
8. Produzir uma estratégia-base treinável em um Ryzen 9.
9. Medir estabilidade, qualidade e ganho marginal por custo de treino.
10. Refinar adaptativamente regiões de maior impacto e integrar somente políticas validadas ao runtime.

## Filosofia de engenharia

### Correção antes de escala

Uma run de meses sobre uma representação errada é pior que uma run curta sobre um modelo correto. Deck, ranking, payouts, rake, stacks, ação legal, terminalidade e canonicalização devem possuir testes independentes antes de treino pesado.

### Eficiência representa força

Eliminar redundâncias não serve apenas para acelerar o mesmo treino. Toda capacidade liberada deve, quando útil, ser convertida em **mais conhecimento estratégico real**: mais estados, melhores abstrações, maior capacidade do modelo, mais iterações ou refinamento dirigido.

### Melhor possível, não perfeito

O projeto não terá um gate artificial de “GTO completo”. O roadmap deverá evoluir enquanto houver uma forma mensurável de converter o orçamento disponível em uma estratégia melhor.

### Evidência acima de intuição

Toda mudança relevante de encoder, arquitetura, loss, sampling, abstraction ou política deverá ser comparada contra baselines em testes reproduzíveis. Uma V2 conceitualmente mais elegante não será promovida apenas por parecer superior; ao mesmo tempo, resultados surpreendentes serão auditados para descartar viés de teste, bug ou desperdício de capacidade.

### Sem compatibilidade falsa

Quando um conceito legado do OpenHoldem não possuir a mesma semântica em 6+, ele não será reaproveitado apenas para evitar mudanças. Compatibilidade aparente é mais perigosa do que uma quebra explícita. Símbolos inválidos devem ser substituídos, desabilitados ou marcados como incompatíveis.

## Estado atual — 16/08/2026

**Fase 0 parcialmente congelada; Fases 1A (Core), 1B (OpenHoldem6Plus) e a fundação do contrato da Fase 3 estão em execução, com os principais gates estruturais iniciais verdes.**

### Regras já congeladas a partir da documentação oficial atual do KKPoker

- 36 cartas, apenas 6..A;
- mesas 6-handed;
- sem SB/BB;
- um ante por jogador e **dois antes totais no Dealer/Button**;
- primeiro jogador à esquerda do Dealer age primeiro em todas as streets;
- No-Limit;
- Flush > Full House;
- A6789 é a menor sequência;
- minimum bet publicado = tamanho do button blind;
- full raise deve ter incremento pelo menos igual ao bet/raise anterior da street;
- no-rake small-pot threshold publicado para 6+ = **10 antes** (equivalente ao `5BB` usado em outra página do site).

A especificação, a reconciliação das páginas oficiais e as ambiguidades ainda abertas estão em `docs/GAME_SPEC_KKPOKER_V0.md`.

### DeepSix Core já implementado

- codec compacto de cartas `0..35`, com rejeição obrigatória de 2..5 na fronteira com o OH;
- **81 hand classes** Short Deck cobrindo exatamente **630 combos**;
- evaluator de 5 cartas e best-of-5 para 5/6/7 cartas;
- A6789 e ranking KKPoker testados;
- oracle de equity HU por enumeração exata para validação offline;
- regras estruturais nativas de ante/Dealer e ordem de ação;
- `TableObservation` v1 com validação e fingerprints semântico/transport;
- canonicalização exata de ordem das hole cards, ordem interna do flop, 24 permutações globais de naipes e labels físicos de chairs relativos ao Dealer;
- pot/side-pot layer accounting com conservação exata de contribuições;
- legal-action boundary com `FOLD/CHECK/CALL/RAISE_TO` e intervalo de raise-to explícito;
- `ReplayFrame` + `DecisionToken` para detectar corrupção e invalidar decisões quando o estado muda;
- **betting-round state machine No-Limit determinística**, com full raises, short all-ins, ordem de ação, fechamento de dry side pots, terminalidade por fold e conservação de fichas;
- comportamento de reopen após short all-ins mantido explicitamente parametrizado (`NEVER`, `ANY_INCREASE`, `CUMULATIVE_FULL_RAISE`) até evidência real do cliente.

A semântica e os gates dessa máquina estão registrados em `docs/BETTING_STATE_MACHINE_V1.md`.

### Validação matemática atual

O evaluator de referência já passou por múltiplas camadas independentes:

- testes unitários de regras especiais;
- enumeração de **todas as 376.992 mãos de cinco cartas** do deck de 36 cartas, com distribuição analítica exata por categoria;
- vetores documentados do PokerKit;
- oracle externo pinado em `uoftcprg/pokerkit@5841c0afe4d6eb71ae5db0f8a6a376ee3e329afb`;
- comparação determinística contra o PokerKit em **10.000 pares de mãos de cinco cartas + 2.000 showdowns de sete cartas**, sem divergência de ordering.

O evaluator Python é agora um forte **oráculo de correção**. Ainda falta criar/benchmarkar o evaluator nativo de alta performance e exigir paridade bit-a-bit/regressiva antes de usá-lo no hot path do trainer.

### OpenHoldem6Plus já iniciado

- fork exclusivo formalizado;
- proveniência do upstream limpa registrada em `OpenHoldem6Plus/PROVENANCE.md`;
- baseline upstream pinado em `OpenHoldem/openholdembot@5d2bb3afec7922aab1b72aef1b23265ff6ea1b13`;
- repositório operacional **build-complete** confirmado em `pmartins87/myoh_private`, branch `oh_pre_release_v15`, pinado em `3aa8a28944e3759fecc9323fb9f7361d54d4c9af`;
- branch dedicada **`deepsix_6plus`** criada nesse repositório exatamente a partir do pin operacional, isolando o desenvolvimento 6+ da linha usada pelos outros projetos;
- o antigo snapshot textual de 393 `.cpp/.h` permanece preservado apenas como evidência histórica/auditável complementar;
- `OpenHoldem6Plus/MIGRATION_MAP.md` quantifica e localiza dependências 1326/2652/prwin/Hand_EVAL/SB/BB/dealposition;
- `ShortDeckRules.h/.cpp` funciona como fronteira 36-card independente dos evaluators tradicionais;
- C++ nativo já implementa ordem clockwise por dealt-mask, Dealer last e contribuição forçada 2A no Dealer/A nos demais;
- `TableObservation.h` + `TableObservationValidator` formam o primeiro contrato C++ OH6Plus → DeepSix;
- `TableObservationJson` produz bytes JSON determinísticos compatíveis com a canonicalização Python;
- o CI do DeepSix gera uma fixture em C++, reconstrói a mesma observação em Python e exige igualdade byte-a-byte e dos fingerprints semântico/transport;
- o branch real `myoh_private:deepsix_6plus` já contém a primeira captura **somente leitura** `RawTableSnapshot` sobre `CTableState`/`CPlayer`/`Card`, sem decisão e sem clique;
- validação estrutural do snapshot bruto foi isolada do código MFC para ser testável fora do executável;
- `RawTableSnapshotJson` produz uma representação determinística de auditoria; dinheiro bruto permanece string de round-trip do `double` até ser convertido para unidade inteira exata sob configuração de stake;
- existe um workflow dedicado **DeepSix 6+ boundary CI** no próprio repositório operacional, restrito ao branch `deepsix_6plus`.

### Validação atual

- DeepSix CI até **#26: PASS**;
- independent evaluator oracle **#2: PASS**;
- exhaustive five-card audit: PASS;
- C++ ShortDeckRules boundary: PASS;
- C++ TableObservation validator: PASS;
- **C++ → JSON canônico → Python/Core → fingerprints: PASS**;
- betting/replay/legal/canonical/pot/rules Core tests: PASS;
- `myoh_private:deepsix_6plus` raw-boundary CI **#2: PASS** — validação e serialização puras compiladas/testadas independentemente do MFC.

**Nenhuma ação automática está habilitada no OpenHoldem6Plus.** O runtime continua deliberadamente observe/replay-first.

### Próximos gates

1. criar o parser/fixture Python do `RawTableSnapshot` e provar paridade da serialização bruta antes de ligá-la ao heartbeat do OH;
2. construir a state machine **de mão completa** que usa a betting-round machine para preflop/flop/turn/river, terminalidade e showdown, ainda sem rake cliente-específico embutido;
3. capturar evidência/prints do cliente real para preflop min-raise/reopen após all-ins, stack/buy-in do stake alvo, rake rounding/timing, side-pot/odd-chip, sit-out e campos exatos do scraper/tablemap;
4. depois dos gates anteriores, ligar logging somente leitura no build dedicado e provar em replays reais `OH6Plus snapshot → TableObservation → CanonicalState` com sequência/fingerprints idênticos offline;
5. só então iniciar os primeiros benchmarks pequenos de abstração/solver para descobrir qual arquitetura compra mais força por CPU-hora no Ryzen 9.
