# DeepSix — Plano de evidência do cliente real KKPoker 6+

## Objetivo

Fechar somente as lacunas que o código e a documentação pública não conseguem provar com segurança. As capturas do cliente serão usadas como evidência de regras, geometria/scraping e transições de estado — não como substituto de testes matemáticos já congelados no Core.

O princípio é **não deduzir uma regra importante a partir de um único frame ambíguo**. Sempre que possível, uma situação deve vir como sequência de frames da mesma mão e, se disponível, acompanhada do Hand Review/histórico do cliente.

## Pacote mínimo de captura

Para cada cenário, preservar a janela inteira da mesa, sem recortar somente a área de interesse. Isso permite validar simultaneamente Dealer, seats, stacks, bets, pot, board, botões de ação e mensagens auxiliares.

1. **Início normal de mão** — frame imediatamente antes das cartas, primeiro frame com as hole cards e primeiro frame em que o jogador à esquerda do Dealer pode agir. Objetivo: confirmar seats usados pelo layout, ante de cada cadeira, contribuição total do Dealer e ação inicial.
2. **Preflop sem raise** — limp/call até o Dealer e check do Dealer, seguido do flop. Objetivo: confirmar `to_call`, fechamento da rodada e transição preflop→flop.
3. **Primeiro raise preflop** — preferencialmente uma situação em que seja possível registrar o menor `raise-to` aceito pelo cliente. Objetivo: congelar a semântica exata do min-raise inicial.
4. **Full raise após raise** — dois raises consecutivos com valores claramente visíveis. Objetivo: confirmar se o incremento mínimo seguinte é exatamente o incremento do último full raise.
5. **Short all-in abaixo do full raise mínimo** — sequência completa antes/depois do all-in e, sobretudo, frame quando a ação retorna a um jogador que já havia agido. Objetivo: determinar a política real de reopen sem assumir `NEVER`, `ANY_INCREASE` ou `CUMULATIVE_FULL_RAISE`.
6. **Flop/turn/river com apostas** — ao menos uma mão com bet, call e raise pós-flop. Objetivo: validar reset de `committed_street`, tamanho mínimo de bet, `raise-to`, pot e ordem de ação.
7. **All-in e side pot** — idealmente três jogadores com stacks diferentes. Capturar antes dos all-ins, após cada contribuição, board/runout e payout. Objetivo: validar stack/bet/pot scraping, fechamento de dry side pot e distribuição final.
8. **Empate com possibilidade de odd chip** — se surgir naturalmente, preservar payout completo. Objetivo: congelar a regra de ficha indivisível. Até existir essa evidência, o Core continuará usando divisão racional exata e não inventará destinatário para odd chip.
9. **Rake** — mãos imediatamente abaixo/acima do small-pot threshold e ao menos uma mão grande/cap, com pot antes e payout depois. Objetivo: determinar momento e arredondamento real do rake e confirmar como a unidade publicada é refletida no cliente.
10. **Sit-out / entrada / saída / observer** — frames com cadeira vazia, jogador sentado sem cartas, sit-out, Hero ainda não sentado e troca de ocupante. Objetivo: separar corretamente `seated`, `active`, `dealt`, fold e observer-mode.

## Dados que devem permanecer visíveis

- janela completa e tamanho/resolução usados normalmente;
- Dealer/Button e todas as cadeiras;
- hole cards do Hero quando disponíveis;
- board completo disponível no momento;
- stacks/balances de todos os jogadores;
- bets/contribuições visíveis por cadeira;
- pot principal e side pots, quando aparecerem;
- botões `Fold/Check/Call/Raise/All-in` e campo/slider de sizing quando for a vez do Hero;
- mensagens de resultado/payout e, se possível, Hand Review correspondente.

## O que já não depende dessas capturas

As capturas não serão usadas para revalidar do zero o deck de 36 cartas, o evaluator Short Deck, `A6789`, `Flush > Full House`, canonicalização de naipes ou o pot-layer matemático. Esses componentes possuem gates independentes. A evidência real é necessária principalmente para **contrato cliente↔runtime** e para regras operacionais ainda ambíguas.

## Política de uso

Nenhum frame isolado autoriza mudança de regra se houver explicação alternativa plausível por scraping incompleto, animação ou hand reset. Frames inconsistentes serão marcados como evidência ambígua e mantidos fora do caminho de decisão até que outra captura ou Hand Review resolva a ambiguidade.
