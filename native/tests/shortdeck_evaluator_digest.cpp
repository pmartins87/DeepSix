#include "../ShortDeckEvaluator.h"

#include <array>
#include <cstdint>
#include <iomanip>
#include <iostream>
#include <numeric>
#include <vector>

namespace {

constexpr std::uint64_t kFnvOffset = 14695981039346656037ULL;
constexpr std::uint64_t kFnvPrime = 1099511628211ULL;

std::uint64_t FnvUpdate(std::uint64_t hash, std::uint64_t value) {
  for (int i = 0; i < 8; ++i) {
    hash ^= (value >> (i * 8)) & 0xffULL;
    hash *= kFnvPrime;
  }
  return hash;
}

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

std::vector<int> SampleUniqueCards(Lcg64* rng, int count) {
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

std::uint64_t SampleBestDigest(int card_count,
                               int samples,
                               std::uint64_t seed) {
  Lcg64 rng(seed);
  std::uint64_t digest = kFnvOffset;
  for (int i = 0; i < samples; ++i) {
    const auto cards = SampleUniqueCards(&rng, card_count);
    digest = FnvUpdate(
        digest,
        deepsix::native::EncodeHandValue(deepsix::native::EvaluateBest(cards)));
  }
  return digest;
}

void PrintHex(const char* key, std::uint64_t value) {
  std::cout << key << "=" << std::hex << std::setw(16) << std::setfill('0')
            << value << std::dec << "\n";
}

}  // namespace

int main() {
  using deepsix::native::EncodeHandValue;
  using deepsix::native::EvaluateFive;

  std::uint64_t digest = kFnvOffset;
  std::array<std::uint64_t, 9> counts{};
  std::uint64_t total = 0;

  for (int a = 0; a < 32; ++a) {
    for (int b = a + 1; b < 33; ++b) {
      for (int c = b + 1; c < 34; ++c) {
        for (int d = c + 1; d < 35; ++d) {
          for (int e = d + 1; e < 36; ++e) {
            const auto value = EvaluateFive({{a, b, c, d, e}});
            digest = FnvUpdate(digest, EncodeHandValue(value));
            ++counts[static_cast<std::size_t>(value.category)];
            ++total;
          }
        }
      }
    }
  }

  std::cout << "five_total=" << total << "\n";
  PrintHex("five_digest", digest);
  std::cout << "five_counts=";
  for (std::size_t i = 0; i < counts.size(); ++i) {
    if (i != 0) {
      std::cout << ",";
    }
    std::cout << counts[i];
  }
  std::cout << "\n";

  constexpr int kSixSamples = 4000;
  constexpr int kSevenSamples = 6000;
  std::cout << "six_samples=" << kSixSamples << "\n";
  PrintHex(
      "six_digest",
      SampleBestDigest(6, kSixSamples, 0x6d5a56da2d4f1b3cULL));
  std::cout << "seven_samples=" << kSevenSamples << "\n";
  PrintHex(
      "seven_digest",
      SampleBestDigest(7, kSevenSamples, 0x9e3779b97f4a7c15ULL));
  return 0;
}
