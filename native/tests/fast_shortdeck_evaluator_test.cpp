#include "../FastShortDeckEvaluator.h"

#include <array>
#include <cassert>
#include <cstdint>
#include <iostream>
#include <numeric>
#include <vector>

namespace {

class Lcg64 {
 public:
  explicit Lcg64(std::uint64_t seed) : state_(seed) {}
  std::uint32_t NextU32() {
    state_ = state_ * 6364136223846793005ULL + 1442695040888963407ULL;
    return static_cast<std::uint32_t>(state_ >> 32);
  }
 private:
  std::uint64_t state_;
};

std::vector<int> SampleUnique(Lcg64* rng, int count) {
  std::array<int, deepsix::native::kShortDeckCards> deck{};
  std::iota(deck.begin(), deck.end(), 0);
  for (int i = 0; i < count; ++i) {
    const int remaining = deepsix::native::kShortDeckCards - i;
    const int j = i + static_cast<int>(rng->NextU32() % remaining);
    const int tmp = deck[i];
    deck[i] = deck[j];
    deck[j] = tmp;
  }
  return std::vector<int>(deck.begin(), deck.begin() + count);
}

}  // namespace

int main() {
  using namespace deepsix::native;
  FastShortDeckEvaluator fast;

  std::array<bool, kFiveCardCombinationCount> seen{};
  std::size_t exhaustive = 0;
  for (int a = 0; a < 32; ++a) {
    for (int b = a + 1; b < 33; ++b) {
      for (int c = b + 1; c < 34; ++c) {
        for (int d = c + 1; d < 35; ++d) {
          for (int e = d + 1; e < 36; ++e) {
            const std::array<int, 5> cards{{a, b, c, d, e}};
            const std::size_t index = CombinationIndexFive(cards);
            assert(index < seen.size());
            assert(!seen[index]);
            seen[index] = true;
            assert(fast.EvaluateFiveFast(cards) == EvaluateFive(cards));
            ++exhaustive;
          }
        }
      }
    }
  }
  assert(exhaustive == kFiveCardCombinationCount);
  for (bool value : seen) {
    assert(value);
  }

  Lcg64 rng(0x243f6a8885a308d3ULL);
  constexpr int kSixSamples = 10000;
  constexpr int kSevenSamples = 20000;
  for (int i = 0; i < kSixSamples; ++i) {
    const auto cards = SampleUnique(&rng, 6);
    assert(fast.EvaluateBestFast(cards) == EvaluateBest(cards));
  }
  for (int i = 0; i < kSevenSamples; ++i) {
    const auto cards = SampleUnique(&rng, 7);
    assert(fast.EvaluateBestFast(cards) == EvaluateBest(cards));
  }

  std::cout << "fast evaluator parity PASS: " << exhaustive
            << " exhaustive five-card hands, " << kSixSamples
            << " six-card samples, " << kSevenSamples
            << " seven-card samples\n";
  return 0;
}
