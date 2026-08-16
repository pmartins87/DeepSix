# OpenHoldem6Plus

Esta árvore receberá o fork exclusivo do OpenHoldem usado pelo DeepSix.

## Regras

- preservar avisos/licença GPL do código de origem;
- registrar o commit/snapshot upstream usado como base;
- binário, logs e configurações devem ser identificáveis como OpenHoldem6Plus/DeepSix;
- nenhuma dependência estratégica de evaluator, prwin, handrank ou versus 52-card pode permanecer ativa sem reimplementação Short Deck;
- ante e button blind são conceitos nativos, não aliases silenciosos de SB/BB;
- antes de qualquer autoplayer, o fork deve funcionar em modo replay/observe-only.

Consulte `docs/OH6PLUS_SOURCE_AUDIT.md` e `docs/ARCHITECTURE.md` antes de portar módulos.
