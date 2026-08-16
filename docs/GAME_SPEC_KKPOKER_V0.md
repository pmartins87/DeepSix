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
- The Dealer/Button posts **two antes total**: the 6+-specific official worked
  example says all players post the mandatory ante and the Dealer then posts a
  second ante. In that example, a non-Dealer with a $1 ante calls by adding $1
  and the Dealer can then check, which confirms the Dealer's total forced
  contribution is $2 rather than $3.
- Action starts with the player immediately left of the Dealer.
- The same positional rule applies on every betting round, including preflop.
- The game is No-Limit.

The generic KKPoker Game Rules page describes this structure as every player
posting an ante and the Dealer posting the single `button blind`, whose stated
size is twice the ante. We interpret that wording consistently with the more
specific worked example above: the Dealer's **total forced level is 2A**. We
will still confirm what the client exposes numerically before wiring preflop
raise reconstruction to live data.

### Betting rules

The current official KKPoker Game Rules explicitly state for NLH 6+:

- the minimum bet is the size of the button blind;
- a raise increment must be at least as large as the previous bet or raise in
  the same betting round;
- the maximum raise is the player's stack;
- there is no cap on the number of raises;
- available actions are fold/check/bet/call/raise according to prior action.

For the DeepSix engine this is modeled as standard semantic `RAISE_TO` actions
with a current legal interval. Postflop, the minimum opening bet is therefore
2A under the published button-blind definition.

**Still to verify in the live client:** the exact preflop `raise-to` values
shown/enforced by the UI when antes and the Dealer's 2A forced contribution are
already present, plus handling of incomplete all-in raises. We do not infer
those edge cases from wording alone.

### Hand ranking differences

- Flush outranks Full House.
- Ace may act below 6 in the lowest straight: A-6-7-8-9.
- Other Hold'em best-five semantics remain: the best five cards may use zero,
  one or two private cards.

### Current rake publication

Current official rake information lists:

- 3% rake for 6+.
- cap expressed in antes: 3 antes for ante levels $0.02 through $2 and 2 antes
  for the listed $5 and $10 ante levels.
- no rake when the hand ends preflop.
- the rake page expresses the small-pot exception as `pot <= 5BB`, despite 6+
  being blindless. A separate current KKPoker Cash Game Leaderboard rules page
  states the 6+-specific equivalent explicitly as **pot <= 10 antes**. These are
  consistent if the site's `BB` shorthand means the 2A button-blind unit.

DeepSix therefore records the published no-rake threshold as **10A for 6+**,
while keeping rake arithmetic parameterized and subject to client/hand-history
validation for rounding.

The exact economic configuration used for training remains parameterized until
the target ante level is selected.

### Jackpot

The cash-game jackpot is a separate economic layer. Current official rules
list 6+ Cooler eligibility beginning at quad sixes and High Hand eligibility
beginning at a 6789T straight flush, with both hole cards required for a
qualifying jackpot hand. Jackpot EV must not be baked into the base evaluator.

## Still unresolved / requires real-client evidence

1. Exact **preflop** min-raise UI values with the ante + Dealer 2A forced level,
   including incomplete all-in raises/reopens.
2. Exact stack/buy-in bounds at the target ante level.
3. Rake rounding to chip/currency units and exact deduction timing.
4. Side-pot display/collection details, settlement timing and odd-chip rules.
5. Sit-out / waiting-player states and how the client exposes them.
6. Run-it-multiple-times behavior if available in the target 6+ cash game.
7. Exact button/ante/current-bet fields exposed to the OpenHoldem scraper/tablemap.

No unresolved item above may be guessed inside a long training run.

## Official sources

- KKPoker, “Short Deck (6+)”: https://kkpoker.net/how-to-play/short-deck-6/
- KKPoker, “Poker Game Rules”: https://kkpoker.net/gamerules/
- KKPoker, “Games & Rake Info”: https://kkpoker.net/how-to-play/rake-information/
- KKPoker, “Cash Game Leaderboard”: https://kkpoker.net/promotions/cash-game-leaderboards/
- KKPoker, “Cash Game Jackpot”: https://kkpoker.net/how-to-play/cash-game-jackpot/
