# DeepSix — Simulator target with GGPoker Short Deck economy v1

Status: **PRIMARY TARGET**  
Frozen on: 2026-08-16  
Execution environment: **DeepSix simulator / self-play / permitted test environment**  
Economic reference: **current public GGPoker 6+ Short Deck cash-game schedule**

## Decision

DeepSix is no longer being designed around KKPoker as the target economy or around a live poker client as the primary execution environment.

The primary product target is now:

> **an autonomous 6+ / Short Deck AI that plays complete cash-game sessions inside our own simulator, with rules and economic deductions modeled after GGPoker Short Deck.**

KKPoker work remains historical engineering/reference material only. It is not a fallback economy and must not silently influence training targets.

OpenHoldem6Plus and real-client reconstruction work are preserved because they contain useful observation/replay engineering, but they are no longer on the critical path to the first complete DeepSix AI.

## What is currently supported by public GGPoker material

The current GGPoker Short Deck page explicitly supports the following simulator facts:

- 36-card deck;
- ranks 2 through 5 removed;
- up to six seats;
- Flush above Full House;
- A-6-7-8-9 as the lowest straight;
- 5% rake;
- rake caps that depend on the published stake and number of players;
- a published default buy-in per stake.

The current GGPoker Bad Beat Jackpot page states that Short Deck contributes one ante to the jackpot fund when the pot reaches at least 100 antes. This is modeled as a separate economic deduction because the promotion can change independently of poker rules.

## Published cash-game schedule frozen into the simulator profile

All monetary values below are copied into `deepsix_core.ggpoker_economy` as integer cents.

| Published stake | Default buy-in | Rake | 2 players cap | 3 players cap | 4 players cap | 5+ players cap |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| $0.02 | $0.80 | 5% | $0.02 | $0.03 | $0.05 | $0.06 |
| $0.05 | $2.00 | 5% | $0.04 | $0.08 | $0.11 | $0.15 |
| $0.10 | $4.00 | 5% | $0.08 | $0.15 | $0.23 | $0.30 |
| $0.25 | $10.00 | 5% | $0.13 | $0.25 | $0.38 | $0.50 |
| $0.50 | $20.00 | 5% | $0.25 | $0.50 | $0.75 | $1.00 |
| $1 | $40.00 | 5% | $0.50 | $1.00 | $1.50 | $2.00 |
| $2 | $80.00 | 5% | 0.38BB | 0.75BB | 1.13BB | 1.50BB |
| $5 | $200.00 | 5% | 0.38BB | 0.75BB | 1.13BB | 1.50BB |
| $10 | $500.00 | 5% | 0.38BB | 0.75BB | 1.13BB | 1.50BB |

For the high-stakes rows, the code stores the exact cent equivalents of the published BB caps for each listed stake.

## Important simulator boundary

The public Short Deck table does **not** state a preflop/no-flop exemption or a small-pot exemption. The v1 simulator economy therefore applies the published 5% rate subject to cap without inventing either exemption.

That is a deliberate simulator convention based on published information, not a claim that an undocumented production-client exception cannot exist.

Likewise, client rake rounding is not guessed. The mathematical layer retains exact `Fraction` values until we deliberately choose or validate a rounding policy.

## Forced bets

Public GGPoker educational material describes Short Deck as ante-based, with every player contributing an ante and the Button/Dealer contributing an additional button amount. Some wording is generic rather than a precise production-client specification.

For the simulator, forced bets remain a versioned game-rule parameter instead of being entangled with rake. The current structural default may use one ante per dealt player and two antes total on the Button, but that choice must remain explicit in the simulator rules profile.

This separation lets us improve or correct the forced-bet model without retraining the evaluator or rewriting the economy table.

## Bad Beat Jackpot contribution

The v1 economic profile exposes:

```text
if gross pot >= 100 antes:
    deduct 1 ante for the jackpot fund
else:
    deduct 0
```

The contribution is kept separate from rake so we can train/evaluate with:

- base GGPoker rake only;
- base rake + current BBJ contribution;
- historical/future economy profiles.

Leaderboard, cashback/rewards and optional account-level promotions are not mixed into the base poker utility unless a dedicated experiment explicitly models them.

## Optional features

GGPoker currently publishes an EV Cashout feature with a 1% fee for Short Deck. This is not part of the baseline game tree because it is an optional player choice layered on top of an all-in state. If we later want the simulator to model it, it should be implemented as an explicit optional action/economic branch, not silently included in showdown EV.

Run-it-multiple-times and other optional client features follow the same rule: they enter only if we decide they are part of the target simulator environment.

## What must exist before the final simulator AI is considered complete

1. a frozen `GGPokerShortDeckRulesProfile` for forced bets, action order and min-raise/reopen semantics;
2. exact simulator rake/cap profile for the selected stake set;
3. explicit jackpot toggle/profile;
4. side-pot and all-in settlement under the same economy;
5. a complete 2..6-player simulator environment;
6. multi-street and multiway strategy training;
7. policy compiler/runtime;
8. autonomous self-play closed loop;
9. long-run certification against baselines and held-out states.

Real-client scraping, tablemaps, UI automation and live-client execution are **not requirements** for this target.

## Code contract

`deepsix_core.ggpoker_economy` now contains:

- `GGPOKER_SHORTDECK_ECONOMY_VERSION`;
- the nine published cash stakes;
- default buy-ins;
- player-count rake caps;
- `ggpoker_shortdeck_rake_config()` using 5%;
- `ggpoker_shortdeck_bbj_contribution()` with the 100-ante threshold.

The module is date-versioned so a future GGPoker schedule change creates a new profile rather than silently changing historical training semantics.

## Current official sources used

- GGPoker Short Deck cash-game page, checked 2026-08-16.
- GGPoker Bad Beat Jackpot page, checked 2026-08-16.
- GGPoker Short Deck educational material for the ante/button structure, checked 2026-08-16.
- GGPoker EV Cashout page, checked 2026-08-16.
