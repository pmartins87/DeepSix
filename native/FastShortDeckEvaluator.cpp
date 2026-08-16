#include "FastShortDeckEvaluator.h"

#include <algorithm>
#include <array>
#include <stdexcept>

namespace deepsix {
namespace native {
namespace {

std::size_t Binomial(int n, int k) {
  if (k < 0 || n < 0 || k > n) {
    return 0;
  }
  if (k == 0 || k == n) {
    return 1;
  }
  if (k > n - k) {
    k = n - k;
  }
  std::size_t result = 1;
  for (int i = 1; i <= k; ++i) {
    result = result * static_cast<std::size_t>(n - k + i) /
             static_cast<std::size_t>(i);
  }
  return result;
}

std::array<int, 5> SortedFive(std::array<int, 5> cards) {
  std::sort(cards.begin(), cards.end());
  for (std::size_t i = 0; i < cards.size(); ++i) {
    if (!IsValidCoreCard(cards[i])) {
      throw std::invalid_argument("invalid Short Deck core card id");
    }
    if (i > 0 && cards[i] == cards[i - 1]) {
      throw std::invalid_argument("duplicate Short Deck core card id");
    }
  }
  return cards;
}

std::vector<int> SortedUnique(const std::vector<int>& cards) {
  if (cards.size() < 5 || cards.size() > 7) {
    throw std::invalid_argument("best-hand evaluation requires 5, 6 or 7 cards");
  }
  std::vector<int> sorted = cards;
  std::sort(sorted.begin(), sorted.end());
  for (std::size_t i = 0; i < sorted.size(); ++i) {
    if (!IsValidCoreCard(sorted[i])) {
      throw std::invalid_argument("invalid Short Deck core card id");
    }
    if (i > 0 && sorted[i] == sorted[i - 1]) {
      throw std::invalid_argument("duplicate Short Deck core card id");
    }
  }
  return sorted;
}

}  // namespace

std::size_t CombinationIndexFive(std::array<int, 5> sorted_cards) {
  for (std::size_t i = 0; i < sorted_cards.size(); ++i) {
    if (!IsValidCoreCard(sorted_cards[i])) {
      throw std::invalid_argument("invalid Short Deck core card id");
    }
    if (i > 0 && sorted_cards[i] <= sorted_cards[i - 1]) {
      throw std::invalid_argument("five-card combination must be strictly sorted");
    }
  }
  const std::size_t index =
      Binomial(sorted_cards[0], 1) +
      Binomial(sorted_cards[1], 2) +
      Binomial(sorted_cards[2], 3) +
      Binomial(sorted_cards[3], 4) +
      Binomial(sorted_cards[4], 5);
  if (index >= kFiveCardCombinationCount) {
    throw std::logic_error("five-card combinadic index out of range");
  }
  return index;
}

HandValue DecodeHandValue(std::uint64_t encoded) {
  HandValue value;
  const auto category = static_cast<std::uint8_t>((encoded >> 24) & 0x0fULL);
  const auto length = static_cast<std::uint8_t>((encoded >> 20) & 0x0fULL);
  if (category > static_cast<std::uint8_t>(HandCategory::kStraightFlush)) {
    throw std::invalid_argument("encoded hand category out of range");
  }
  if (length > 5) {
    throw std::invalid_argument("encoded hand tiebreak length out of range");
  }
  value.category = static_cast<HandCategory>(category);
  value.tiebreak_len = length;
  for (std::size_t i = 0; i < 5; ++i) {
    const int shift = static_cast<int>((4 - i) * 4);
    value.tiebreak[i] = static_cast<std::uint8_t>((encoded >> shift) & 0x0fULL);
  }
  return value;
}

FastShortDeckEvaluator::FastShortDeckEvaluator() {
  std::array<bool, kFiveCardCombinationCount> populated{};
  std::size_t count = 0;
  for (int a = 0; a < 32; ++a) {
    for (int b = a + 1; b < 33; ++b) {
      for (int c = b + 1; c < 34; ++c) {
        for (int d = c + 1; d < 35; ++d) {
          for (int e = d + 1; e < 36; ++e) {
            const std::array<int, 5> cards{{a, b, c, d, e}};
            const std::size_t index = CombinationIndexFive(cards);
            if (populated[index]) {
              throw std::logic_error("combinadic collision while building evaluator table");
            }
            table_[index] = EncodeHandValue(EvaluateFive(cards));
            populated[index] = true;
            ++count;
          }
        }
      }
    }
  }
  if (count != kFiveCardCombinationCount ||
      !std::all_of(populated.begin(), populated.end(), [](bool value) { return value; })) {
    throw std::logic_error("incomplete five-card evaluator lookup table");
  }
}

HandValue FastShortDeckEvaluator::EvaluateFiveFast(
    const std::array<int, 5>& cards) const {
  const std::array<int, 5> sorted = SortedFive(cards);
  return DecodeHandValue(table_[CombinationIndexFive(sorted)]);
}

std::uint64_t FastShortDeckEvaluator::EvaluateBestEncoded(
    const std::vector<int>& cards) const {
  const std::vector<int> sorted = SortedUnique(cards);
  const int n = static_cast<int>(sorted.size());
  std::uint64_t best = 0;
  bool initialized = false;
  for (int a = 0; a < n - 4; ++a) {
    for (int b = a + 1; b < n - 3; ++b) {
      for (int c = b + 1; c < n - 2; ++c) {
        for (int d = c + 1; d < n - 1; ++d) {
          for (int e = d + 1; e < n; ++e) {
            const std::array<int, 5> five{{
                sorted[a], sorted[b], sorted[c], sorted[d], sorted[e]}};
            const std::uint64_t encoded = table_[CombinationIndexFive(five)];
            if (!initialized || encoded > best) {
              best = encoded;
              initialized = true;
            }
          }
        }
      }
    }
  }
  if (!initialized) {
    throw std::logic_error("no five-card combination evaluated");
  }
  return best;
}

HandValue FastShortDeckEvaluator::EvaluateBestFast(
    const std::vector<int>& cards) const {
  return DecodeHandValue(EvaluateBestEncoded(cards));
}

}  // namespace native
}  // namespace deepsix
