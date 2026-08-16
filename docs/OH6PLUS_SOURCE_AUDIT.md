# OpenHoldem6Plus — Auditoria inicial do código legado

## Objetivo

Registrar, antes de copiar ou modificar o OpenHoldem, quais partes do código legado podem ser reaproveitadas e quais carregam premissas de Hold'em tradicional que seriam perigosas em 6+.

Esta auditoria foi feita sobre o snapshot de código-fonte do OpenHoldem disponível no projeto.

## Conclusão executiva

Não é seguro tratar 6+ como uma simples fórmula nova sobre o OpenHoldem atual.

Há dependências explícitas de:

- deck 52-card;
- ranks 2..A;
- evaluator tradicional;
- 1.326 combinações / 2.652 hole-card permutations;
- small blind / big blind;
- identificação de chairs baseada em SB/BB;
- funções de equity e versus pré-computadas para Hold'em tradicional.

Por outro lado, uma parte grande da infraestrutura é valiosa e pode ser preservada:

- tablemaps e scraper;
- representação visual das cartas;
- dealerchair;
- dealt/playing bits;
- pot, current bets e balances;
- detecção de flop/turn/river por community cards;
- mouse/teclado, betsize input e confirmação de botões;
- logs, replay frames e infraestrutura de heartbeat.

A decisão correta é um fork exclusivo **OpenHoldem6Plus**, não uma coleção de exceções dentro do runtime usado pelos outros projetos.

---

## 1. Representação de cartas: preservar a fronteira, não a matemática

### Código legado relevante

`Card.cpp` documenta explicitamente:

- StdDeck usa ranks `0..12` para `2..A`;
- OpenHoldem expõe ranks `2..14`;
- `Card::GetOpenHoldemRank()` é `GetStdDeckRank() + 2`.

`CardFunctions.cpp` aceita diretamente `2,3,4,5,6,...,A` e converte para `StdDeck_MAKE_CARD(rank-2, suit)`.

### Decisão DeepSix

**Não precisamos remapear o scraper inteiro para um deck físico 0..35.**

O runtime pode continuar usando o card ID legado do StdDeck **somente na fronteira de captura/UI**, porque isso reduz radicalmente a quantidade de código que precisa ser mexida e mantém compatibilidade com tablemaps existentes.

Mas qualquer cálculo DeepSix deve obedecer a esta fronteira:

`OH legacy card id -> validate rank >= 6 -> DeepSix compact card id 0..35 -> DeepSix Core`

Qualquer carta 2, 3, 4 ou 5 reconhecida em uma mesa 6+ deve produzir `INVALID_SHORTDECK_CARD`, nunca ser silenciosamente aceita.

### Regra

Nenhuma função estratégica pode enumerar `0..51` ou assumir que todo `StdDeck` card é válido.

---

## 2. Evaluator tradicional: proibido no caminho DeepSix

### Código legado relevante

`CSymbolEnginePokerval.cpp`:

- constrói máscaras iterando `Rank_2 .. Rank_ACE`;
- usa `Hand_EVAL_N`;
- possui lógica de straight/flush/pokerval baseada no ranking tradicional.

`versus_table.cpp`, `CSymbolEngineVersus.cpp`, `CSymbolEngineVersusmod.cpp`, `CIteratorThread.cpp`, `CSymbolEnginePrwin.cpp` e outros também chamam `Hand_EVAL_N`.

### Problema

No 6+ alvo, a semântica de mão não é a mesma do Hold'em tradicional. Além do deck reduzido, há regras específicas de sequência e de ordenação de categorias.

### Decisão DeepSix

- `Hand_EVAL_N` não será usado como oráculo de estratégia no OpenHoldem6Plus;
- o evaluator autoritativo virá do **DeepSix Core**;
- símbolos de `pokerval`, `prwin`, `versus`, `handrank` e derivados só poderão existir se forem reimplementados sobre o evaluator DeepSix;
- na primeira versão do runtime, é preferível **desabilitar** símbolos incompatíveis a produzir valores plausíveis porém errados.

---

## 3. 1.326 / 2.652: forte dependência estrutural

A busca no snapshot encontrou referências a `1326` em pelo menos 17 arquivos e a `2652` em pelo menos 5 arquivos.

Os principais pontos incluem:

- `CSymbolEnginePrwin.cpp`;
- `CSymbolEngineRange.cpp`;
- `CIteratorThread.cpp`;
- `CEngineContainer.cpp`;
- `CSymbolEngineHandrank.cpp`;
- `CSymbolEngineHandrank.h`;
- `CSymbolEnginePrwin.h`;
- `CSymbolengineUserDLL.cpp`.

`CSymbolEngineHandrank.cpp` contém inclusive tabelas estáticas `handrank_table_2652`.

### Decisão DeepSix

O Short Deck possui:

- `C(36,2) = 630` hole-card combinations exatos;
- 81 hand classes pré-flop quando se usa a classificação pair/suited/offsuit por ranks.

Não vamos tentar adaptar tabelas 1326/2652 in-place. Elas serão consideradas **legado 52-card** e removidas do caminho de decisão.

---

## 4. Forced bets: o OH é profundamente SB/BB-centric

### Arquivos críticos

- `CBlindGuesser.cpp`;
- `CSymbolEngineBlinds.cpp`;
- `CSymbolEngineTableLimits.cpp`;
- `CSymbolEngineChairs.cpp`;
- `CHandresetDetector.cpp`;
- `CBlindLevels.cpp`;
- `SwagAdjustment.cpp`;
- `CSymbolEngineRaisers.cpp`;
- diversas funções de history/action.

### Exemplos concretos

`CBlindGuesser.cpp` tenta inferir small blind e big blind comparando as primeiras apostas depois do dealer e possui regras como:

- primeira/segunda aposta representando SB/BB;
- big blind aproximadamente duas vezes o small blind;
- ante estimado como fração do BB em certos contextos.

`CSymbolEngineChairs.cpp` define `SmallBlindChair()` e `BigBlindChair()` por deal positions, testa `currentbet == sblind/bblind` e possui lógica específica de missing small blind.

`CHandresetDetector.cpp` guarda `_bblind`, detecta mudança de blind level e usa apostas menores que o BB como evidência potencial de SB/ante.

### Decisão DeepSix

O OpenHoldem6Plus terá forced bets nativos:

- `ante`;
- `button_blind`;
- demais contribuições forçadas somente se a regra alvo realmente exigir.

Não vamos definir um SB/BB fictício para enganar o código estratégico.

Uma camada de compatibilidade poderá fornecer um valor legado apenas para rotinas de UI que exijam número não-zero, mas:

- DeepSix Core não verá esse valor;
- posições não serão derivadas de SB/BB;
- ação legal não dependerá dele;
- logs devem distinguir claramente `compat_bblind` de forced bets reais, se essa ponte for necessária.

---

## 5. Posições: parte reutilizável, parte deve ser substituída

`CSymbolEnginePositions.cpp` já possui uma qualidade importante: grande parte de `dealposition` e contagem à esquerda/direita é calculada caminhando a partir do `dealerchair` e usando dealt/playing bits.

Isso é reutilizável.

O que não é reutilizável são posições derivadas de `SmallBlindChair()` / `BigBlindChair()` e heurísticas de missing blind.

### Plano

Criar posição Short Deck explicitamente relativa ao button, por exemplo:

- BTN;
- UTG;
- HJ;
- CO;
- demais nomes conforme número de jogadores e convenção final.

A representação estratégica deve usar **índice relativo canônico**, não chair absoluto.

---

## 6. Betround: altamente reutilizável

`CBetroundCalculator.cpp` identifica a street pela presença de:

- três community cards -> flop;
- turn card -> turn;
- river card -> river.

Essa lógica não depende da composição 52-card do deck e é conceitualmente válida em 6+.

Ela deve ser preservada, adicionando testes específicos de animação/frame parcial.

---

## 7. Autoplayer e bet sizing: reutilizar transporte, substituir semântica

Arquivos como:

- `CBetsizeInputBox.cpp`;
- `CBetSlider.cpp`;
- `CAutoplayer.cpp`;
- `CAutoplayerButton.cpp`;

fornecem infraestrutura útil para clicar fold/check/call/raise e inserir um valor.

Entretanto, funções legadas como `BetpotCalculations.cpp` e partes do autoplayer podem calcular tamanho a partir de `bblind`/pot usando convenções do OH.

### Decisão

DeepSix deve preferir o seguinte contrato:

`policy -> ACTION + absolute_raise_to`

O runtime:

1. valida que a ação ainda é legal;
2. calcula/observa `to_call`, `min_raise_to`, `max_raise_to`;
3. verifica/clippa somente conforme regra explicitamente definida;
4. digita o `raise_to` absoluto;
5. confirma no log o valor pedido e o efetivamente executado.

Não dependeremos de `BetPot`/`BetMax` como representação estratégica autoritativa.

---

## 8. Hand reset: precisa de implementação Short Deck

Parte dos detectores atuais é reaproveitável:

- mudança do dealerchair;
- mudança do hand number quando disponível;
- desaparecimento/aparecimento coerente de cards;
- mudanças de street/board.

Mas sinais baseados em `_bblind`, small blind e ante tradicional precisam ser auditados ou removidos.

### Requisito

O reset Short Deck deve ser um state machine auditável com reason codes, e não apenas uma votação opaca de heurísticas legadas.

---

## 9. Engines legados: classificação inicial

### Reaproveitar com pouca ou moderada alteração

- scraper/tablemap;
- `Card` como transporte de card ID;
- `dealerchair`;
- dealt/seated/playing bits;
- `CBetroundCalculator`;
- chip amounts/pot/balances após validação;
- casino interface;
- betsize input/slider;
- replay/logging/heartbeat.

### Reescrever ou criar versão Short Deck

- rules/deck validation;
- evaluator;
- equity;
- positions estratégicas;
- forced bets;
- hand reset;
- action reconstruction;
- legal action/min-raise model;
- policy interface;
- state hashing/replay contract.

### Desabilitar inicialmente

- `prwin` 52-card;
- `handrank1326` / 2652 tables;
- `versus` tables tradicionais;
- range engines construídos sobre 1326;
- símbolos de pokerval cuja semântica não tenha sido reimplementada;
- ICM/tournament logic que não faça parte do cash 6+ alvo;
- qualquer módulo que só exista para manter compatibilidade com variantes fora do DeepSix.

---

## 10. Arquitetura alvo do OpenHoldem6Plus

Fluxo desejado:

```text
KKPoker 6+
  -> TableMap / Scraper
  -> RawTableState (legacy card ids allowed only here)
  -> ShortDeckStateValidator
  -> TableObservation
  -> convert cards 52-boundary -> 36-core
  -> DeepSix canonicalizer
  -> Policy Runtime
  -> legal-action validator
  -> absolute action / raise-to
  -> CasinoInterface / Autoplayer transport
  -> post-action confirmation/log/replay
```

### Regra de ouro

Se um estado não puder ser demonstrado como válido e semanticamente igual ao estado que o Trainer conhece, **não há decisão automática**.

---

## 11. Próximos passos técnicos

1. importar o snapshot escolhido do OpenHoldem para uma árvore `OpenHoldem6Plus/`, preservando licença e histórico de origem quando possível;
2. renomear projeto/binário/log prefix para evitar confusão com outros OH;
3. criar `ShortDeckRules` e `ShortDeckCardCodec`;
4. adicionar teste de rejeição de ranks 2–5;
5. criar `TableObservation` serializável;
6. substituir forced-bet discovery por ante/button blind;
7. neutralizar prwin/handrank/versus 52-card no build DeepSix;
8. criar replay-only mode antes de habilitar qualquer ação;
9. validar tudo com frames reais de 6+.

Esta lista é o primeiro corte da auditoria. Ela deve ser atualizada sempre que um novo acoplamento 52-card/SB-BB for encontrado.
