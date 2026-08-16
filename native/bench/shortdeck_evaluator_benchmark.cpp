#include "../FastShortDeckEvaluator.h"
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

struct Measurement {
  double seconds = 0.0;
  double per_second = 0.0;
  std::uint64_t checksum = 0;
};

template <typename Evaluator>
Measurement Measure(const std::vector<std::vector<int>>& hands, Evaluator evaluator) {
  std::uint64_t checksum = 0;
  const auto start = std::chrono::steady_clock::now();
  for (const auto& cards : hands) {
    checksum += evaluator(cards);
  }
  const auto end = std::chrono::steady_clock::now();
  const std::chrono::duration<double> elapsed = end - start;
  return Measurement{
      elapsed.count(),
      static_cast<double>(hands.size()) / elapsed.count(),
      checksum};
}

}  // namespace

int main() {
  constexpr int kWarmup = 10000;
  constexpr int kEvaluations = 200000;
  Lcg64 rng(0xd1b54a32d192ed03ULL);

  std::vector<std::vector<int>> warmup;
  warmup.reserve(kWarmup);
  for (int i = 0; i < kWarmup; ++i) {
    warmup.push_back(SampleSeven(&rng));
  }
  std::vector<std::vector<int>> hands;
  hands.reserve(kEvaluations);
  for (int i = 0; i < kEvaluations; ++i) {
    hands.push_back(SampleSeven(&rng));
  }

  deepsix::native::FastShortDeckEvaluator fast;
  for (const auto& cards : warmup) {
    const auto baseline = deepsix::native::EncodeHandValue(
        deepsix::native::EvaluateBest(cards));
    const auto lookup = fast.EvaluateBestEncoded(cards);
    if (baseline != lookup) {
      std::cerr << "benchmark warmup parity mismatch\n";
      return 2;
    }
  }

  const Measurement baseline = Measure(
      hands,
      [](const std::vector<int>& cards) {
        return deepsix::native::EncodeHandValue(
            deepsix::native::EvaluateBest(cards));
      });
  const Measurement lookup = Measure(
      hands,
      [&](const std::vector<int>& cards) {
        return fast.EvaluateBestEncoded(cards);
      });
  if (baseline.checksum != lookup.checksum) {
    std::cerr << "benchmark checksum parity mismatch\n";
    return 3;
  }

  std::cout << "native_evaluator_benchmark_v2\n";
  std::cout << "seven_card_evaluations=" << kEvaluations << "\n";
  std::cout << std::fixed << std::setprecision(6)
            << "baseline_seconds=" << baseline.seconds << "\n"
            << "lookup_seconds=" << lookup.seconds << "\n";
  std::cout << std::setprecision(2)
            << "baseline_evaluations_per_second=" << baseline.per_second << "\n"
            << "lookup_evaluations_per_second=" << lookup.per_second << "\n"
            << "speedup=" << (lookup.per_second / baseline.per_second) << "\n";
  std::cout << "checksum=" << baseline.checksum << "\n";
  return 0;
}
