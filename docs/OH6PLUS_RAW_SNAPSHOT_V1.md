# OH6Plus RawTableSnapshot v1

Status: **read-only boundary implemented on `pmartins87/myoh_private:deepsix_6plus`**  
Operational OH base pin: `3aa8a28944e3759fecc9323fb9f7361d54d4c9af`  
First DeepSix branch commit: `2ad23a4153854cd0d756867f8696d4d49818eab8`

## Purpose

`RawTableSnapshot` is deliberately below `TableObservation`.

It captures only facts that the existing OpenHoldem scraper/table state already
exposes. It must not invent action history, folds, positions, legal sizings or
other strategic meaning from one frame.

The path is therefore:

`KKPoker pixels -> existing OH scraper -> RawTableSnapshot -> state reconstructor -> TableObservation -> CanonicalState`

No policy inference or mouse/keyboard action belongs before the final stages of
that path.

## Current raw fields

### Table

- schema version;
- dealer chair;
- Hero chair, with `-1` explicitly allowed while observing;
- number of visible community cards;
- five raw board-card slots;
- ten raw OpenHoldem chair slots;
- ten raw OpenHoldem pot slots.

The raw layer intentionally preserves OpenHoldem's physical 10-chair capacity.
The target game may later validate that only 2..6 chairs are dealt. Physical
chair IDs are not strategic positions.

### Seat

For every physical chair:

- `seated`;
- `active`;
- OpenHoldem dealer flag;
- `IsAllin()` raw result;
- whether any cards are present;
- whether known cards are present;
- scraped balance;
- current scraped bet;
- `stack()` as currently exposed by OpenHoldem;
- two raw hole-card slots.

### Card

For every hole/board slot:

- any-card flag;
- known-card flag;
- card-back flag;
- OpenHoldem rank;
- OpenHoldem suit.

A known card is structurally rejected for Short Deck if its rank is outside
6..A or its suit is outside 0..3. Duplicate known cards are also rejected.
Unknown/card-back slots remain raw evidence and are not guessed.

## Intentionally NOT inferred here

`RawTableSnapshot` does not determine:

- whether a player was dealt this hand solely from `active`/cardback state;
- whether a player folded;
- action sequence;
- limp/call/raise semantics;
- total contribution across prior streets;
- `to_call`;
- minimum/full-raise semantics;
- reopen rights after short all-ins;
- terminality;
- pot/side-pot ownership;
- rake or jackpot deductions;
- strategic position names;
- any 52-card `prwin`, 1326/2652 or legacy hand-evaluator result.

Those require successive snapshots plus the DeepSix rules/state machine.

## Money boundary

The operational OpenHoldem stores scraped money as `double`. The raw snapshot
preserves those values because they are scraper evidence, but **no strategic
fingerprint or trainer state may depend directly on raw floating-point money**.
Before `TableObservation`, the reconstructor must convert values to an exact
integer unit under a versioned stake/table configuration and prove the
conversion in replay tests.

The exact displayed chip/currency precision for the target KKPoker 6+ stake is
still client-evidence dependent.

## Current implementation state

The dedicated OH branch now contains:

- `OpenHoldem/DeepSix6Plus/README.md`;
- `OpenHoldem/DeepSix6Plus/RawTableSnapshot.h`;
- `OpenHoldem/DeepSix6Plus/RawTableSnapshot.cpp`.

The capture reads `CTableState`, `CPlayer`, `Card`, dealer-chair and user-chair
APIs only. It does not invoke the autoplayer and is not yet wired into a
heartbeat or Visual Studio project target. That deliberate isolation lets us
audit the boundary before it can affect a live table.

## Next gate

1. serialize this raw snapshot deterministically;
2. create synthetic/raw replay fixtures and a Python-side parser;
3. wire **logging only** into a dedicated OH6Plus build;
4. validate frames against real 6+ screenshots/tablemaps;
5. only after that derive `TableObservation` from successive frames.
