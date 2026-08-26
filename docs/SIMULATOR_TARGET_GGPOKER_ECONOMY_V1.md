# DeepSix — Simulator target with GGPoker Short Deck economy v1

Status: **PRIMARY TARGET / SIMULATOR RULES v1 FROZEN**  
Economic schedule frozen on: 2026-08-16  
Simulator-rule freeze: 2026-08-25  
Execution environment: **DeepSix simulator / self-play / permitted test environment**  
Economic reference: **public GGPoker 6+ Short Deck cash-game schedule**

## Decision

DeepSix is designed around neither KKPoker economics nor a live poker client.

The primary product target is:

> **an autonomous 6+ / Short Deck AI that plays complete cash-game sessions inside our own simulator, with economic deductions modeled after GGPoker Short Deck.**

KKPoker work remains historical engineering/reference material only. It is not a fallback economy and must not silently influence training targets.

OpenHoldem6Plus and real-client reconstruction work are preserved as auxiliary engineering, but they are not on the critical path to the first complete DeepSix AI.

## Public GGPoker facts frozen into the economic reference

The GGPoker material checked for the v1 reference supports:

- 36-card Short Deck with ranks 2 through 5 removed;
- up to six seats;
- Flush above Full House;
- A-6-7-8-9 as the lowest straight;
- 5% rake;
- rake caps dependent on published stake and number of players;
- a published default buy-in per stake;
- a Short Deck Bad Beat Jackpot contribution of one ante at the published 100-ante pot threshold.

The BBJ contribution is modeled separately from rake because promotions can change independently of the poker rules.

## Published cash-game schedule frozen into the simulator economy

All monetary values below are stored by `deepsix_core.ggpoker_economy` as integer cents.

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

The public Short Deck table used for this freeze does not state a preflop/no-flop exemption or small-pot exemption. The v1 simulator economy therefore applies the published 5% rate subject to cap without inventing either exemption. This is a simulator convention based on the published table, not a claim about undocumented production behavior.

## Simulator rules profile v1

The economic schedule alone is not enough to run a complete game. We therefore freeze the remaining game semantics explicitly in:

```text
deepsix_shortdeck_sim_rules_2026-08-25_v1
```

These are **simulation conventions**. They make the target complete and reproducible; they are not presented as proof of undocumented live-client edge cases.

### Monetary/game unit

The published stake denomination maps to **one ante unit** in simulator v1.

Thus, for a published $0.25 stake:

```text
ante = 25 integer cents
```

All stacks, bets, pots, rake caps and payouts use the same integer-cent unit.

### Forced contributions

- every dealt player posts one ante;
- the Dealer/Button posts two antes total.

### Action order

The action order is clockwise from the first dealt seat immediately left of the Dealer through the Dealer. The same positional ordering is used on every betting street.

### Minimum bet / full raise

- initial preflop full-raise increment: **2 antes**;
- postflop minimum bet / initial full-raise increment: **2 antes**.

The existing generic betting engine then applies normal no-limit raise geometry from that starting increment.

### Short all-ins and reopen

- a sub-minimum raise is allowed only when it is the player's exact all-in;
- prior raise rights reopen once cumulative price increases faced since the player's last action reach one full-raise increment.

This maps to `ShortAllInReopenPolicy.CUMULATIVE_FULL_RAISE`.

### Odd chips

When a gross pot layer ties and cannot be divided evenly in the integer monetary unit, odd units are awarded to tied winners clockwise beginning with the first winner left of the Dealer.

## Simulator settlement v1

The settlement profile is:

```text
deepsix_sim_settlement_2026-08-25_v1
```

### Rake rounding

The generic Core retains exact `Fraction` rake. Simulator v1 rounds rake **down to the integer monetary unit**.

That rule belongs to the simulator profile and is not a claim about GGPoker client rounding.

### BBJ toggle

The base environment supports two explicit modes:

```text
bbj_enabled = true
bbj_enabled = false
```

When enabled:

```text
if gross pot >= 100 antes:
    BBJ deduction = 1 ante
else:
    BBJ deduction = 0
```

### Aggregate house deductions and side pots

Rake and BBJ are computed from the aggregate gross pot. Because operator-specific side-pot rake attribution is not part of the simulator target, v1 allocates the final integer house deduction pro-rata across gross winners using a deterministic largest-remainder method.

This guarantees:

```text
sum(post_hand_player_stacks)
= sum(pre_hand_player_stacks)
  - rounded_rake
  - BBJ
```

without inventing hidden side-pot client behavior.

## Optional features

EV Cashout, run-it-multiple-times and similar features are not part of the baseline v1 game tree. If later selected, each becomes an explicit versioned branch/profile rather than silently changing showdown EV.

Leaderboard, cashback/rewards and account-level promotions are also excluded from the base game utility unless a dedicated experiment explicitly models them.

## Code contracts

`deepsix_core.ggpoker_economy` contains:

- `GGPOKER_SHORTDECK_ECONOMY_VERSION`;
- nine published cash stakes;
- default buy-ins;
- player-count rake caps;
- `ggpoker_shortdeck_rake_config()` using 5%;
- `ggpoker_shortdeck_bbj_contribution()`.

`deepsix_simulator.rules` contains the frozen simulator game semantics.

`deepsix_simulator.settlement` contains integer odd-chip/rake/BBJ settlement.

`deepsix_simulator.environment` contains seeded dealing, seat-local observations, legal-action stepping, automatic runouts and session stack/Dealer state.

The profiles are versioned independently so economic schedule changes, game-rule changes and settlement changes never rewrite historical run semantics.

## What is still required before the final simulator AI is complete

1. finish and soak-test the 2..6-player simulator boundary;
2. canonical simulator event history and exact action replay;
3. multi-street HU solver/blueprint;
4. multiway 3..6 solver path;
5. long Ryzen training and held-out validation;
6. policy compiler/runtime;
7. autonomous self-play closed loop;
8. long-run certification against baselines and held-out states.

Real-client scraping, tablemaps, UI automation and live-client execution are **not requirements** for this target.

## Public source snapshot used by the economic reference

- GGPoker Short Deck cash-game page, checked 2026-08-16.
- GGPoker Bad Beat Jackpot page, checked 2026-08-16.
- GGPoker Short Deck educational material for ante/button structure, checked 2026-08-16.
- GGPoker EV Cashout page, checked 2026-08-16.

A later source change creates a new dated economic/profile version; it does not mutate this v1 freeze.
