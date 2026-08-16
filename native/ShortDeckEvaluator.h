#pragma once

#include <array>
#include <cstdint>
#include <vector>

namespace deepsix {
namespace native {

constexpr int kShortDeckCards = 36;
constexpr int kShortDeckRanks = 9;
constexpr int kShortDeckSuits = 4;

enum class HandCategory : std::uint8_t {
  kHighCard = 0,
  kOnePair = 1,
  kTwoPair = 2,
  kThreeOfAKind = 3,
  kStraight = 4,
  kFullHouse = 5,
  kFlush = 6,
  kFourOfAKind = 7,
  kStraightFlush = 8,
};

struct HandValue {
  HandCategory category = HandCategory::kHighCard;
  std::array<std::uint8_t, 5> tiebreak{{0, 0, 0, 0, 0}};
  std::uint8_t tiebreak_len = 0;
};

bool operator==(const HandValue& lhs, const HandValue& rhs);
bool operator!=(const HandValue& lhs, const HandValue& rhs);
bool operator<(const HandValue& lhs, const HandValue& rhs);
bool operator>(const HandValue& lhs, const HandValue& rhs);

bool IsValidCoreCard(int card);
int CoreCardRank(int card);  // 6..14
int CoreCardSuit(int card);  // 0..3

HandValue EvaluateFive(const std::array<int, 5>& cards);
HandValue EvaluateBest(const std::vector<int>& cards);  // 5, 6 or 7 cards

// Compact deterministic representation used only for cross-language regression
// digests. It is not a public poker-hand rank API.
std::uint64_t EncodeHandValue(const HandValue& value);

}  // namespace native
}  // namespace deepsix
