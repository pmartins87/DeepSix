# DeepSix — Raw Hand-Start Evidence v1

## Problema

Um simples `river -> preflop` não prova sozinho que o runtime observou corretamente uma nova mão. Em interfaces reais, board, Dealer, stacks, cards e bets podem ser atualizados em frames diferentes. Se o reconstrutor reiniciar a mão cedo demais, toda a action history posterior pode ficar deslocada.

Por isso o DeepSix separa duas coisas:

- `HAND_BOUNDARY_CANDIDATE`: regressão observada para preflop;
- **prova de baseline inicial**: padrão exato de contribuições forçadas antes de qualquer ação voluntária.

## Detector v1

`deepsix_core.raw_hand_start.exact_forced_bet_baseline()` recebe um `ProjectedSnapshot` e um `ante` explícito em unidades inteiras exatas.

No modelo de regras atualmente congelado, o Dealer possui **dois antes totais** e cada outro jogador dealt possui um ante.

Para aceitar o snapshot como baseline pré-ação, v1 exige simultaneamente:

1. street `PREFLOP` e board vazio;
2. entre 2 e 6 seats dealt, identificados por `seated && has_any_cards`;
3. Dealer entre os seats dealt;
4. exatamente um flag de Dealer, coincidente com `dealer_seat`;
5. todo seat dealt ainda `active`;
6. nenhum seat dealt já marcado all-in nesta versão;
7. `current_bet == ante` para não-Dealer;
8. `current_bet == 2 * ante` para o Dealer;
9. `stack_including_current_bet == balance + current_bet` para cada dealt seat;
10. todo seat mapeado mas não dealt possui `current_bet == 0` e não expõe cartas conhecidas.

O pot visível não participa da prova v1 porque ainda não congelamos empiricamente se o campo `Pot()` do scraper inclui ou não contribuições correntes e em qual instante ele é atualizado.

## Por que o detector é tão rígido

Se um jogador já tiver dado o primeiro call, o padrão deixa de ser aceito. Se um short stack tiver sido clipado pelo ante e já estiver all-in, o padrão também não é aceito na v1.

Isso reduz cobertura, mas aumenta a força da afirmação: quando o detector retorna `matched=True`, estamos olhando um estado que corresponde exatamente ao baseline de forced bets do modelo, e não apenas um preflop plausível.

## Confirmação de nova mão

`confirm_new_hand_from_exact_baseline(previous, current, ...)` exige três fatos conjuntamente:

1. o classificador bruto produziu `HAND_BOUNDARY_CANDIDATE`;
2. o Dealer mudou entre as duas mãos;
3. o snapshot atual satisfaz o baseline exato de forced bets.

Somente essa combinação pode ser usada futuramente para reiniciar uma action sequence com `complete_from_hand_start=True`.

## Limites conhecidos

Este detector ainda é uma **hipótese operacional testável**, não uma afirmação sobre a ordem real de atualização da UI da KKPoker.

As capturas reais podem mostrar que:

- `current_bet` não contém ante no frame inicial;
- card backs aparecem depois dos forced bets;
- Dealer muda antes/depois do board reset;
- short stacks exigem uma prova separada;
- o primeiro jogador age antes de conseguirmos obter dois frames idênticos do baseline.

Nesses casos, não vamos enfraquecer silenciosamente a v1. Criaremos uma nova versão baseada na sequência real observada.

## Gates

A suíte atual exige:

- padrão 3-handed exato aceito;
- estado após primeiro call rejeitado;
- seat sentado mas fora da mão aceito somente com bet zero;
- forced all-in clipado rejeitado pela v1;
- postflop rejeitado;
- configuração inválida rejeitada;
- river -> preflop + Dealer move + baseline exato confirmado;
- mesmo Dealer rejeitado;
- reset para preflop já após uma ação voluntária rejeitado.
