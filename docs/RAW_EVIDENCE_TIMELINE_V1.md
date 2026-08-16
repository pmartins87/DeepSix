# DeepSix — Raw Evidence Timeline v1

## Objetivo

Esta camada é o primeiro passo entre o `RawTableSnapshot` capturado pelo OpenHoldem6Plus e uma linha de ações estrategicamente utilizável pelo DeepSix.

O princípio é deliberadamente conservador:

> **um delta de tela só vira ação de poker quando a evidência observada possui uma única interpretação compatível com a contabilidade visível.**

O objetivo não é maximizar cobertura nesta fase. O objetivo é impedir que o reconstrutor produza uma história plausível, porém falsa.

## Entrada

A timeline recebe apenas `ProjectedSnapshot` já validados e estabilizados pelo `StableSnapshotGate`.

Cada snapshot contém, entre outros campos:

- street e board conhecidos;
- Dealer e Hero mapeados para seats estratégicos;
- estados `seated`, `active`, `all_in` e presença de cartas por seat;
- `balance`, `current_bet` e `stack_including_current_bet` em unidades inteiras exatas;
- pot slots;
- `hero_myturnbits` e `hero_sitting_in` como evidência bruta do runtime.

`hero_myturnbits` continua sendo evidência de botões visíveis, não prova de ação executada.

## Ações que v1 pode inferir

A versão v1 infere somente `CALL` e `RAISE_TO`.

O Core usa `RAISE_TO` também para uma primeira aposta postflop quando o preço anterior da street é zero. Isso evita criar uma semântica paralela `BET_TO` que não existe no contrato estratégico atual.

### Condições obrigatórias para qualquer inferência monetária

Uma ação só é aceita quando todas as condições abaixo são verdadeiras:

1. a transição ocorre dentro da mesma street e sem mudança de board ou Dealer;
2. exatamente um seat altera valores monetários;
3. `current_bet` desse seat aumenta estritamente;
4. a queda de `balance` é exatamente igual ao aumento de `current_bet`;
5. `stack_including_current_bet` permanece idêntico;
6. pot slots permanecem idênticos;
7. nenhum outro seat altera dinheiro, presença, identidade física, cartas conhecidas ou estado estrutural;
8. o ator permanece `seated` e `active`;
9. uma mudança para `all_in=true` só é aceita quando acompanhada pelo movimento monetário exato.

Esses guards são intencionalmente mais rígidos do que provavelmente será necessário no cliente real. Eles serão relaxados somente quando capturas reais mostrarem uma semântica diferente de atualização dos campos.

## Classificação exata

Se o novo `current_bet` do único ator fica **acima** do maior `current_bet` anterior da mesa, a única interpretação monetária local é `RAISE_TO(new_bet)`.

Se o ator estava abaixo do preço anterior e passa a igualá-lo exatamente, a ação é `CALL`.

Se o ator estava abaixo do preço, paga todo o saldo disponível, termina `all_in` e ainda fica abaixo do preço anterior, a ação é `CALL` all-in curto.

Qualquer outro padrão permanece `AMBIGUOUS`.

## O que v1 se recusa a inferir

### CHECK

Ausência de alteração de fichas, desaparecimento de botões ou mudança de `hero_myturnbits` não é suficiente para provar um check. O jogador também poderia ter perdido a vez, a interface poderia estar em transição, ou outro evento poderia ter mudado o estado visual.

Portanto v1 nunca cria `CHECK` apenas por delta visual sem fichas.

### FOLD

Uma mudança em `active`, `has_any_cards` ou outro flag legado do OpenHoldem não prova sozinha que ocorreu fold. Sit-out, mudança transitória do scraper ou semântica específica da tablemap podem produzir alterações semelhantes.

Portanto v1 nunca cria `FOLD` somente a partir desses flags.

### HAND RESET

River → preflop é tratado apenas como `HAND_BOUNDARY_CANDIDATE`.

A timeline não reinicia a sequência de ações nem declara uma nova mão enquanto não houver um confirmer independente de nova mão baseado em evidência real do cliente.

## Cobertura versus confiança

A timeline mantém a distinção entre duas propriedades diferentes:

- **inferência local**: um delta específico pode ser classificado com segurança como `CALL` ou `RAISE_TO`;
- **história completa desde o início da mão**: ainda não é afirmada pela v1.

Assim, mesmo que várias ações locais sejam inferidas corretamente, `complete_from_hand_start` permanece `false` até existir prova do verdadeiro início da mão.

Isso evita transformar uma captura iniciada no meio de uma mão em uma falsa hand history completa.

## Gates da v1

Os testes cobrem:

- call exato;
- call all-in curto;
- raise-to exato;
- primeiro bet postflop representado como `RAISE_TO`;
- dois seats mudando dinheiro simultaneamente → `AMBIGUOUS`;
- pot mudando junto com a ação candidata → `AMBIGUOUS`;
- quebra da conservação `balance + current_bet` → `AMBIGUOUS`;
- mudança de flags equivalente a possível fold → não inferir fold;
- mudança apenas de botões visíveis → não inferir check;
- progressão de street;
- mutação de board dentro da mesma street → `AMBIGUOUS`;
- reset para preflop → apenas `HAND_BOUNDARY_CANDIDATE`;
- sequência interna de ações inferidas numerada deterministicamente.

## Próxima evolução

A v2 depende principalmente das capturas reais do KKPoker 6+.

Precisamos descobrir empiricamente:

1. se `Pot()` muda imediatamente após cada ação ou somente no fechamento da street;
2. a ordem temporal de atualização de `balance`, `bet`, `active`, card backs e botões;
3. como fold e check aparecem em frames sucessivos;
4. como o Dealer e o board mudam na fronteira entre duas mãos;
5. como all-ins, side pots e sit-out afetam os mesmos campos;
6. se existe evidência adicional no scraper que permita identificar o ator atual sem inferência indireta.

Depois disso poderemos construir o confirmer de hand boundary e transformar a timeline local em uma hand history completa e auditável.
