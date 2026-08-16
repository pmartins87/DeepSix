// DeepSix / OpenHoldem6Plus
// Short Deck-specific rules at the OpenHoldem observation boundary.
//
// This file is intentionally independent from legacy OpenHoldem poker evaluators.
// The legacy scraper may still decode cards in the normal 52-card rank/suit
// space, but only ranks 6..A are admitted to DeepSix.

#pragma once

#include <cstdint>

namespace deepsix {

constexpr int kShortDeckMinRank = 6;
constexpr int kShortDeckMaxRank = 14;
constexpr int kShortDeckNumRanks = 9;
constexpr int kShortDeckNumSuits = 4;
constexpr int kShortDeckNumCards = 36;
constexpr int kShortDeckMaxPlayers = 6;

bool IsValidShortDeckRank(int rank);
bool IsValidSuit(int suit);

// Returns compact DeepSix card id [0, 35].
// Returns -1 for any invalid rank/suit, including removed ranks 2..5.
int CoreCardIdFromRankSuit(int rank, int suit);

}  // namespace deepsix
