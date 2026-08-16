# DeepSix — Native Short Deck Evaluator v1

## Status

O evaluator nativo C++ deixou de ser apenas uma intenção de roadmap. Existem agora duas implementações deliberadamente separadas:

1. `native/ShortDeckEvaluator.*` — baseline simples, legível e independente, usado como referência nativa;
2. `native/FastShortDeckEvaluator.*` — versão exata por lookup de todas as combinações de cinco cartas, destinada a reduzir o custo do hot path sem mudar semântica.

Nenhuma delas substitui o oracle Python como fonte final de correção. O C++ só é promovido porque existe paridade automática contra o Core de referência.

## Semântica congelada

- card IDs compactos `0..35` iguais aos do DeepSix Core;
- ranks `6..A`;
- `A6789` como menor straight;
- `Flush > Full House`;
- ordenação restante idêntica ao Core;
- best-of-five para 5/6/7 cartas.

## Gate baseline C++ ↔ Python

O CI enumera **todas as 376.992 mãos de cinco cartas** em C++ e em Python e compara um digest determinístico que inclui categoria e todos os tiebreaks. Além disso, compara **4.000 amostras de seis cartas + 6.000 amostras de sete cartas** produzidas por PRNG determinístico idêntico nos dois lados.

Gate atual: **PASS**.

Isso é mais forte do que comparar apenas distribuição por categoria: qualquer divergência de kicker/tiebreak também altera o digest.

## Lookup exato de cinco cartas

`FastShortDeckEvaluator` mantém uma tabela de **376.992 valores exatos**, indexada por combinadic sobre os cinco card IDs ordenados. O índice é denso no intervalo `0..376991`; o construtor verifica colisões e cobertura completa.

Para 6/7 cartas, o evaluator:

1. valida e ordena as cartas uma única vez;
2. enumera as combinações de cinco cartas;
3. faz lookup do valor empacotado;
4. escolhe o maior valor.

O CI exige:

- paridade para **todas as 376.992 mãos de cinco cartas** contra o baseline C++ já validado pelo Python;
- paridade em **10.000 amostras de seis cartas**;
- paridade em **20.000 amostras de sete cartas**.

Gate atual: **PASS**.

## Benchmark informativo

O benchmark não possui threshold de PASS/FAIL, porque runners compartilhados do GitHub não são um ambiente de performance estável. Ele serve para impedir que uma otimização seja promovida apenas por parecer mais rápida.

Primeira medição comparável no runner Linux do CI, 200.000 avaliações de sete cartas sobre exatamente as mesmas mãos pré-geradas:

- baseline: **475.651,58 eval/s**;
- lookup: **1.412.406,71 eval/s**;
- ganho observado: **2,97×**.

Esse número não deve ser extrapolado diretamente para o Ryzen 9. O benchmark é versionado para podermos medir a mesma carga no hardware real antes de decidir se vale desenvolver uma tabela direta de 6/7 cartas, perfect hash ou outra otimização mais pesada.

## Decisão atual

A versão lookup passa a ser o **candidato nativo preferencial** para benchmarks do Trainer, mas ainda não deve apagar o baseline. O baseline permanece como oráculo C++ simples de regressão; o Python permanece como referência semântica independente.

O próximo passo de performance só será justificado se profiling do primeiro Trainer mostrar que evaluator continua representando parcela relevante do custo por iteração. Isso evita gastar memória/complexidade em uma otimização que não compre força estratégica real.
