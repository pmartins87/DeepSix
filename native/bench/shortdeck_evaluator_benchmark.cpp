#include "../ShortDeckEvaluator.h"

#include <array>
#include <chrono>
#include <cstdint>
#include <iomanip>
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

std::vector<int> SampleSeven(Lcg64* rng) {
  std::array<int, deepsix::native::kShortDeckCards> deck{};
  std::iota(deck.begin(), deck.end(), 0);
  for (int i = 0; i < 7; ++i) {
    const int remaining = deepsix::native::kShortDeckCards - i;
    const int j = i + static_cast<int>(rng->NextU32() % remaining);
    const int tmp = deck[i];
    deck[i] = deck[j];
    deck[j] = tmp;
  }
  return std::vector<int>(deck.begin(), deck.begin() + 7);
}

}  // namespace

int main() {
  constexpr int kWarmup = 10000;
  constexpr int kEvaluations = 200000;
  Lcg64 rng(0xd1b54a32d192ed03ULL);
  std::uint64_t checksum = 0;

  for (int i = 0; i < kWarmup; ++i) {
    checksum ^= deepsix::native::EncodeHandValue(
        deepsix::native::EvaluateBest(SampleSeven(&rng)));
  }

  const auto start = std::chrono::steady_clock::now();
  for (int i = 0; i < kEvaluations; ++i) {
    checksum += deepsix::native::EncodeHandValue(
        deepsix::native::EvaluateBest(SampleSeven(&rng)));
  }
  const auto end = std::chrono::steady_clock::now();
  const std::chrono::duration<double> elapsed = end - start;
  const double per_second = kEvaluations / elapsed.count();

  std::cout << "native_evaluator_benchmark_v1\n";
  std::cout << "seven_card_evaluations=" << kEvaluations << "\n";
  std::cout << std::fixed << std::setprecision(6)
            << "elapsed_seconds=" << elapsed.count() << "\n";
  std::cout << std::setprecision(2)
            << "evaluations_per_second=" << per_second << "\n";
  std::cout << "checksum=" << checksum << "\n";
  return 0;
}
