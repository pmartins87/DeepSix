# DeepSix target platform — GGPoker 6+ / Short Deck v0

Status: **SUPERSEDED AS PRIMARY TARGET**  
Verification date: 2026-08-16

This document records the first pivot from KKPoker toward GGPoker as a concrete platform reference. It is preserved as historical engineering evidence, but it is no longer the primary DeepSix target contract.

The current target is defined in:

`docs/SIMULATOR_TARGET_GGPOKER_ECONOMY_V1.md`

## Current decision

DeepSix is being built as an autonomous **6+ / Short Deck simulator AI**. GGPoker is the reference for the cash-game economy we want the simulator to reproduce; KKPoker is historical reference material only.

Therefore:

- live GGPoker scraping/tablemaps are not on the critical path;
- live-client automated play is not an objective of the primary roadmap;
- OpenHoldem6Plus work is preserved as a useful observation/replay side track;
- deck/evaluator/canonicalization/solver work remains platform-independent;
- GGPoker rake/caps/jackpot deductions are represented by date-versioned simulator profiles rather than by client-specific runtime assumptions.

## Research preserved from v0

The public GGPoker Short Deck material checked on 2026-08-16 supports:

- 36-card deck, ranks 6..A;
- maximum six seats;
- Flush above Full House;
- A-6-7-8-9 as the lowest straight;
- a 5% cash-game rake schedule with caps by stake/player count;
- published default buy-ins;
- a Short Deck Bad Beat Jackpot contribution of one ante when the pot reaches the published 100-ante threshold.

Educational GGPoker material describes Short Deck as ante-based with an additional Button/Dealer contribution. Because generic educational pages are not a precise production-client protocol, the simulator keeps forced-bet semantics versioned and explicit rather than silently treating website prose as a client oracle.

## Historical KKPoker relationship

DeepSix originally used KKPoker 6+ to bootstrap rules/economy work. That work remains useful for comparison and regression, but **KKPoker is no longer a fallback economy or training target**.

No new strategy should inherit KKPoker rake, thresholds, caps or runtime assumptions unless a test explicitly selects a historical KKPoker profile.

## Successor contract

The successor document freezes the simulator-first direction and the current GGPoker economy schedule:

- `docs/SIMULATOR_TARGET_GGPOKER_ECONOMY_V1.md`
- `deepsix_core/ggpoker_economy.py`
- `tests/test_ggpoker_economy.py`

This v0 file should not be edited to represent future economy changes. Create a new date/versioned profile instead.
