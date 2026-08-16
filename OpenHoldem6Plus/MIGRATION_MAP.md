# OpenHoldem6Plus — migration map from the supplied operational source evidence

Source evidence: `repositorio_completo_openholdem.txt`  
SHA-256: `8a2809bf32b226775a237c9a51f970e8fd55148e777890f9a275b5fd6bd8521e`  
Audit date: 2026-08-16

This map is intentionally conservative. “Reuse” means reuse the mechanical capability after Short Deck tests; it never means accepting legacy poker semantics without review.

## Quantified legacy assumptions

A direct scan of the 393 embedded `.cpp/.h` files found:

| Legacy concept | Occurrences | Files |
|---|---:|---:|
| `1326` | 373 | 17 |
| `2652` | 31 | 5 |
| `Hand_EVAL*` | 19 | 8 |
| `prwin` | 430 | 33 |
| small-blind terms | 193 | 34 |
| big-blind terms | 213 | 41 |
| `dealposition` | 202 | 10 |

The density matters: 6+ cannot be made correct by replacing a single evaluator or formula.

## A. Mechanical layers to preserve first

These are candidates for maximum reuse because their primary job is observation/UI transport rather than Texas-Hold'em strategy:

- `CScraper` and tablemap regions;
- `CLazyScraper`, subject to removing blind-specific completion assumptions;
- `CTableState` player/card/chip snapshots;
- dealer button scraping / `CSymbolEngineDealerchair` as an observed physical chair;
- player-name, balance, current-bet and pot scraping;
- `CBetroundCalculator` community-card-based street detection, after dedicated 6+ regression tests;
- window attachment, heartbeat, logging and replay-support infrastructure;
- autoplayer mouse/keyboard transport primitives.

These components must still feed the versioned `TableObservation` validator before their data becomes strategic state.

## B. 52-card strategic layers to bypass or replace

The following must never be authoritative for DeepSix:

- `CSymbolEnginePrwin.cpp` — largest direct 1326/prwin concentration;
- `CIteratorThread.cpp` — 1326/range/equity simulation assumptions;
- `CSymbolEngineRange.cpp` — 1326 Hold'em range representation;
- `CSymbolEngineHandrank.cpp` — 1326/2652 rank universe;
- `CSymbolEngineVersus.cpp` and `CSymbolEngineVersusmod.cpp` — legacy evaluator/equity;
- `CSymbolEnginePokerval.cpp` — traditional hand evaluator semantics;
- `versus_table/versus_table.cpp` — explicitly enumerates player/opponent cards in the 52-card `0..51` universe;
- any symbol or formula path that derives strategy from `prwin`, 1326/2652 ranks or traditional `Hand_EVAL_N`.

OpenHoldem6Plus may leave some classes compiled temporarily for UI compatibility, but the DeepSix policy request must not depend on their output. Long term, unsafe symbols should be disabled or clearly marked unsupported in 6+ mode.

## C. Blind/position subsystem requiring native 6+ semantics

These are high-risk because KKPoker 6+ has no SB/BB:

- `CBlindGuesser.cpp` — highest concentration of SB/BB assumptions;
- `CSymbolEngineTableLimits.cpp` — blind-derived table limits;
- `CSymbolEngineChairs.cpp` — SB, BB, UTG and logical positions are derived from blind/deal-position semantics;
- `CSymbolEnginePositions.cpp`;
- `CSymbolEnginePokerAction.cpp` — large `dealposition` dependency;
- `CHandHistoryDealPhase.cpp` — explicitly searches for small blind and big blind posters;
- `CBlindLevels.cpp`;
- `CSymbolEngineBlinds.cpp`;
- blind-dependent parts of `CHandresetDetector.cpp`, rebuy and tournament helpers.

DeepSix replacements use Dealer-relative dealt-player order and ante/button-ante semantics. `ShortDeckRules::ActionOrderFromDealer()` already implements the first native C++ primitive and deliberately ignores waiting/sitting-out physical chairs.

## D. Hand reset and hand-history reconstruction

`CHandresetDetector.cpp` has 211 direct `handreset` references and also blind-related logic. We should preserve useful evidence such as Dealer changes, card transitions and hand-number changes, but create a 6+-specific reset policy rather than trusting the existing combined heuristic.

The current target is:

`raw scrape -> OH6Plus observation sequence -> validated TableObservation -> replay fixture -> canonical state`

Action history used by the policy must be reconstructed semantically (`FOLD`, `CHECK`, `CALL`, `RAISE_TO`) and must survive offline replay. A blind-based hand-history writer is not an acceptable source of truth.

## E. Betting/autoplayer

`BetpotCalculations.cpp` and the legacy BetPot action codes are useful evidence of how OpenHoldem transports a desired amount into the client, but they should not define DeepSix strategy.

DeepSix policy semantics are explicit:

- `FOLD`
- `CHECK`
- `CALL`
- `RAISE_TO <absolute table amount>`

The runtime must re-observe the table immediately before executing a decision, validate the `DecisionToken`, re-check `to_call/min_raise_to/max_raise_to`, and fail closed if the state changed.

This separates **strategy sizing** from **UI execution** and avoids translating a learned action back through ambiguous legacy `BetPot 1/2`, `BetPot 3/4`, etc. semantics.

## F. Physical chair ordering

The supplied OpenHoldem source itself treats chair IDs as circular physical order in multiple places; for example `CHandHistoryDealPhase` describes a clockwise search beginning at `(dealerchair + 1) % nchairs`. OpenHoldem6Plus therefore uses chair IDs `0..5` as a transport-level circular order for the KKPoker 6-seat table.

Strategic positions are **not** those physical IDs. The Core canonicalizer removes gaps/waiting chairs and renumbers only dealt players relative to the Dealer. A 3-handed hand in physical chairs `{0,2,5}` with Dealer at `5` becomes canonical positions `{1,2,0}` in clockwise action order, independent of the empty chairs.

This assumption must be revalidated against the final KKPoker tablemap once the operational fork is attached to the real client.

## First implementation tranche

1. Keep the existing scraper/card/dealer/chip mechanics behind an adapter.
2. Insert `ShortDeckRules` immediately after card decode; reject 2..5.
3. Build `TableObservation` from raw snapshots without consulting `prwin`, 1326, handrank or blind-derived strategic symbols.
4. Validate and serialize observations before any policy request.
5. Reconstruct 6+ action history independently of the old blind hand-history subsystem.
6. Prove replay equivalence and stale-state rejection.
7. Only then connect a policy result to the existing mouse/keyboard transport.

No autoplayer action is enabled by this migration map.
