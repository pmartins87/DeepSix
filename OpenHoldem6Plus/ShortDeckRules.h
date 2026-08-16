// DeepSix / OpenHoldem6Plus
// Short Deck-specific rules at the OpenHoldem observation boundary.
//
// This file is intentionally independent from legacy OpenHoldem poker evaluators.
// The legacy scraper may still decode cards in the normal 52-card rank/suit
// space, but only ranks 6..A are admitted to DeepSix.

#pragma once

#include <cstdint>
#include <vector>

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

// Physical OH6Plus chair ids are 0..5 and advance clockwise by +1 mod 6.
// Returns the next dealt chair after `from_chair`, or -1 if none exists.
int NextDealtChairClockwise(int from_chair, std::uint32_t dealt_mask);

// KKPoker 6+: first action is immediately left of Dealer on every street,
// then proceeds clockwise, with Dealer last. Returned chairs include only
// dealt players and therefore ignore waiting/sitting-out seats.
std::vector<int> ActionOrderFromDealer(int dealer_chair,
                                       std::uint32_t dealt_mask);

// KKPoker 6+: every dealt player posts one ante; Dealer posts a second ante.
// Returns total forced contribution expected for a dealt chair, 0 otherwise.
std::int64_t ExpectedAnteContribution(int chair,
                                      int dealer_chair,
                                      std::uint32_t dealt_mask,
                                      std::int64_t ante);

}  // namespace deepsix
