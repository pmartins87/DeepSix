#pragma once

#include <array>
#include <cstddef>
#include <cstdint>
#include <vector>

#include "ShortDeckEvaluator.h"

namespace deepsix {
namespace native {

constexpr std::size_t kFiveCardCombinationCount = 376992;

class FastShortDeckEvaluator {
 public:
  FastShortDeckEvaluator();

  HandValue EvaluateFiveFast(const std::array<int, 5>& cards) const;
  HandValue EvaluateBestFast(const std::vector<int>& cards) const;
  std::uint64_t EvaluateBestEncoded(const std::vector<int>& cards) const;

 private:
  std::array<std::uint64_t, kFiveCardCombinationCount> table_{};
};

std::size_t CombinationIndexFive(std::array<int, 5> sorted_cards);
HandValue DecodeHandValue(std::uint64_t encoded);

}  // namespace native
}  // namespace deepsix
