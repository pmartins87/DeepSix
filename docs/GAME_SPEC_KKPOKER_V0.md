# DeepSix target game specification — KKPoker 6+ v0

Status: **partially frozen**  
Verification date: 2026-08-16  
Target: KKPoker cash-game 6+ / Short Deck

This document separates rules that are already explicit in the current
official KKPoker documentation from rules that still need client evidence.

## Frozen rules

### Deck and table

- 36-card deck.
- Ranks 2, 3, 4 and 5 are removed.
- Valid ranks are 6, 7, 8, 9, T, J, Q, K, A.
- Cash-game tables are 6-handed.

### Forced bets and action order

- There are no Small Blind or Big Blind positions.
- Every player posts one ante.
- The Dealer/Button posts **two antes total**: the official worked example says
  all players post the mandatory ante and the Dealer then posts a second ante.
- Action starts with the player immediately left of the Dealer.
- The same positional rule applies on every betting round, including preflop.
- The game is No-Limit.

### Hand ranking differences

- Flush outranks Full House.
- Ace may act below 6 in the lowest straight: A-6-7-8-9.
- Other Hold'em best-five semantics remain: the best five cards may use zero,
  one or two private cards.

### Current rake publication

Current official rake information lists:

- 3% rake for 6+.
- cap expressed in antes: 3 antes for lower/mid listed ante levels and 2 antes
  for the listed 5 and 10 ante levels.
- no rake when the hand ends preflop.
- no rake when the pot is at or below the site's published threshold.

The exact economic configuration used for training remains parameterized until
the target stake is selected.

### Jackpot

The cash-game jackpot is a separate economic layer. Current official rules
list 6+ Cooler eligibility beginning at quad sixes and High Hand eligibility
beginning at a 6789T straight flush, with both hole cards required for a
qualifying jackpot hand. Jackpot EV must not be baked into the base evaluator.

## Still unresolved / requires real-client evidence

1. Exact min-bet/min-raise mechanics and UI behavior after unusual all-in sizes.
2. Exact stack/buy-in bounds at the target stake.
3. Exact unit meant by the rake page's `pot <= 5BB` wording in a blindless game.
4. Rounding of rake to chip/currency units.
5. Side-pot display/collection details and timing.
6. Sit-out / waiting-player states and how the client exposes them.
7. Run-it-multiple-times behavior if available in the target 6+ cash game.
8. Exact button/ante values exposed to the OpenHoldem scraper/tablemap.

No unresolved item above may be guessed inside a long training run.

## Official sources

- KKPoker, “Short Deck (6+)”: https://kkpoker.net/how-to-play/short-deck-6/
- KKPoker, “Games & Rake Info”: https://kkpoker.net/how-to-play/rake-information/
- KKPoker, “Cash Game Jackpot”: https://kkpoker.net/how-to-play/cash-game-jackpot/
