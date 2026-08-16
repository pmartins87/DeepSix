# DeepSix target platform — GGPoker 6+ / Short Deck v0

Status: **GGPoker-first, partially frozen**  
Verification date: 2026-08-16  
Primary target for strategy/economy: **GGPoker Short Deck cash games**  
Secondary reference/fallback: KKPoker 6+

## Why this document exists

DeepSix began by using KKPoker 6+ as the concrete reference environment. The mathematical Short Deck core is largely platform-independent, but **the complete game is not**: forced-bet semantics, rake, caps, jackpot deductions, buy-in conventions, UI timing and hand-history fields can change the optimal strategy and the runtime implementation.

Therefore GGPoker and KKPoker must not be treated as interchangeable merely because both call the game 6+ / Short Deck.

## Rules already supported by current official GGPoker material

### Deck and hand construction

- 36-card deck.
- Ranks 2, 3, 4 and 5 are removed.
- Valid ranks are 6, 7, 8, 9, T, J, Q, K, A.
- Two private cards and five community cards.
- Best-five Hold'em semantics: zero, one or two hole cards may be used.
- Maximum of six seats at the Short Deck table.

### Hand ranking differences

Current GGPoker Short Deck material explicitly confirms:

- **Flush outranks Full House**.
- **A-6-7-8-9** is the lowest straight.

Current GGPoker educational material also describes Straight above Three-of-a-kind for the common Short Deck ranking, but because some educational pages discuss house-rule variants generically, the exact GGPoker production ordering must still be confirmed against the client/official game-specific ranking before being called platform-frozen. The DeepSix evaluator already supports the ranking model used in the original KKPoker target and will not be changed without a platform-specific gate.

## Forced bets — likely compatible, not yet client-frozen

GGPoker educational material says Short Deck uses antes rather than the normal Small Blind / Big Blind structure: every player pays an ante and the Button/Dealer pays an additional button contribution. One current GGPoker article describes the button ante as commonly double the ante; another GGPoker article describes all players paying an ante plus an additional blind equal to the ante paid by the Button. Both descriptions are consistent with a **2A total Button contribution** when interpreted literally.

However, a generic GGPoker poker-rules page contains a Short Deck section templated around Small Blind / Big Blind language. Because that conflicts with the game-specific educational description, DeepSix will not freeze GGPoker preflop action/min-raise semantics from website prose alone.

**Required evidence before freezing GGPoker forced bets:**

1. screenshots/video or permitted hand-history/replay evidence from an actual Short Deck cash table;
2. exact starting contributions for every seat;
3. exact amount required to limp/call preflop;
4. exact minimum raise-to and reopen behavior after short all-ins;
5. action order on every street.

Until then the engine keeps forced bets parameterized.

## Economy — GGPoker is materially different from KKPoker

The current official GGPoker Short Deck table page lists **5% rake**, with caps depending on stake and number of players.

Examples from the published table:

| Stake | Default buy-in | 2p cap | 3p cap | 4p cap | 5+p cap |
| --- | ---: | ---: | ---: | ---: | ---: |
| $0.02 | $0.80 | $0.02 | $0.03 | $0.05 | $0.06 |
| $0.05 | $2.00 | $0.04 | $0.08 | $0.11 | $0.15 |
| $0.10 | $4.00 | $0.08 | $0.15 | $0.23 | $0.30 |
| $0.25 | $10.00 | $0.13 | $0.25 | $0.38 | $0.50 |
| $0.50 | $20.00 | $0.25 | $0.50 | $0.75 | $1.00 |
| $1 | $40.00 | $0.50 | $1.00 | $1.50 | $2.00 |

For the listed $2 / $5 / $10 levels, the page publishes high-stakes caps as 0.38 / 0.75 / 1.13 / 1.5 BB for 2 / 3 / 4 / 5+ players. The page labels the stake column as `Blinds` in some localizations even though Short Deck elsewhere uses ante terminology; DeepSix will preserve the published values but will not silently reinterpret the unit until the client confirms it.

This differs materially from the KKPoker model previously frozen for experimentation, which publishes 3% rake with caps in antes and a small-pot/preflop exemption. Therefore **a strategy trained under KKPoker economics cannot simply be relabeled GGPoker**.

## GGPoker jackpot/promotion deductions

Current GGPoker Bad Beat Jackpot material states that Short Deck contributes **1 ante** to the jackpot fund for sufficiently large pots described as above 100 antes. This must be represented as a separate economic layer rather than baked into hand strength.

GGPoker also currently runs Short Deck leaderboard/promotional programs. These can affect total account EV but should remain outside the zero-sum poker utility unless a future experiment explicitly models them.

## Platform-security constraint

Current GGPoker Terms & Conditions and Security & Ecology Policy prohibit bots, artificial intelligence used to play, real-time assistance, automated execution, HUDs/data-mining tools and other external assistance during gameplay.

Therefore:

- DeepSix may continue as an **offline research/training/replay** system;
- the GGPoker adapter should remain **observe/replay-first** and must not be interpreted as authorization for live automated play;
- autonomous closed-loop execution must be certified in a simulator/test environment or another environment where such automation is permitted;
- live GGPoker activation is an operational/compliance gate separate from technical readiness and is currently **blocked by platform policy**.

## What carries over unchanged from the KKPoker work

The following are platform-independent and remain valid unless the GGPoker client proves a different house rule:

- 36-card codec;
- starting-hand class/combo enumeration;
- canonicalization of suit, hole order and flop order;
- evaluator architecture and exhaustive audit framework;
- exact equity tools;
- legal-action/state-machine architecture;
- pot/side-pot accounting architecture;
- replay/fingerprint/DecisionToken contracts;
- solver laboratory, exact best-response oracles and Ryzen benchmark infrastructure.

## What must be revalidated/replaced for GGPoker

1. exact forced-bet/button semantics;
2. exact min-bet/min-raise/reopen rules;
3. exact stake and buy-in units;
4. 5% rake table and player-count caps;
5. rake rounding/timing and whether any small-pot/preflop exemption exists in production;
6. jackpot deduction threshold/timing;
7. odd chips and side-pot settlement;
8. run-it-multiple-times / cashout / insurance-like options if present;
9. sit-out/waiting-seat semantics;
10. table layout, graphics, card/button/pot/bet/balance fields and animations;
11. hand-history/replay availability and exact schema;
12. action-button and amount-entry behavior for a controlled test harness.

## Current platform conclusion

**GGPoker and KKPoker are close at the mathematical Short Deck layer but not identical at the economic/platform layer.**

The DeepSix Core remains reusable. The immediate pivot is therefore not a rewrite: it is a new GGPoker platform specification, GGPoker economy profile and GGPoker observation/replay adapter, while preserving KKPoker as a secondary reference implementation.

## Official sources checked on 2026-08-16

- GGPoker — Short Deck: https://ggpoker.com/pt-br/poker-games/short-deck/
- GGPoker — Introduction to Short Deck: https://ggpoker.com/blog/the-beginners-guide-series-introduction-to-short-deck/
- GGPoker — Security & Ecology Policy: https://legal.ggpoker.com/network/security-ecology-policy/
- GGPoker — Terms & Conditions: https://ggpoker.com/terms-conditions/
- GGPoker — Bad Beat Jackpot: https://ggpoker.com/pt-br/jackpots/bad-beat-jackpot-rebirth/
- GGPoker — Short Deck Daily Leaderboard: https://legal.ggpoker.com/promotions/short-deck-daily-leaderboard/
- KKPoker — Short Deck (6+): https://kkpoker.net/how-to-play/short-deck-6/
- KKPoker — Games & Rake Info: https://kkpoker.net/how-to-play/rake-information/
