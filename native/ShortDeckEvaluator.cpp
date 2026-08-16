#include "ShortDeckEvaluator.h"

#include <algorithm>
#include <array>
#include <initializer_list>
#include <stdexcept>

namespace deepsix {
namespace native {
namespace {

HandValue MakeValue(HandCategory category, std::initializer_list<int> values) {
  if (values.size() > 5) {
    throw std::invalid_argument("too many tiebreak values");
  }
  HandValue out;
  out.category = category;
  out.tiebreak_len = static_cast<std::uint8_t>(values.size());
  std::size_t index = 0;
  for (int value : values) {
    if (value < 0 || value > 15) {
      throw std::invalid_argument("tiebreak rank outside packed range");
    }
    out.tiebreak[index++] = static_cast<std::uint8_t>(value);
  }
  return out;
}

void ValidateFive(const std::array<int, 5>& cards) {
  std::array<bool, kShortDeckCards> seen{};
  for (int card : cards) {
    if (!IsValidCoreCard(card)) {
      throw std::invalid_argument("invalid Short Deck core card id");
    }
    if (seen[card]) {
      throw std::invalid_argument("duplicate Short Deck core card id");
    }
    seen[card] = true;
  }
}

int StraightHigh(const std::array<int, 15>& counts) {
  int unique = 0;
  for (int rank = 6; rank <= 14; ++rank) {
    if (counts[rank] > 0) {
      ++unique;
    }
  }
  if (unique != 5) {
    return -1;
  }
  if (counts[14] && counts[6] && counts[7] && counts[8] && counts[9]) {
    return 9;
  }
  for (int high = 14; high >= 10; --high) {
    bool straight = true;
    for (int rank = high - 4; rank <= high; ++rank) {
      if (counts[rank] == 0) {
        straight = false;
        break;
      }
    }
    if (straight) {
      return high;
    }
  }
  return -1;
}

}  // namespace

bool operator==(const HandValue& lhs, const HandValue& rhs) {
  if (lhs.category != rhs.category || lhs.tiebreak_len != rhs.tiebreak_len) {
    return false;
  }
  for (std::size_t i = 0; i < lhs.tiebreak_len; ++i) {
    if (lhs.tiebreak[i] != rhs.tiebreak[i]) {
      return false;
    }
  }
  return true;
}

bool operator!=(const HandValue& lhs, const HandValue& rhs) {
  return !(lhs == rhs);
}

bool operator<(const HandValue& lhs, const HandValue& rhs) {
  const auto lhs_category = static_cast<int>(lhs.category);
  const auto rhs_category = static_cast<int>(rhs.category);
  if (lhs_category != rhs_category) {
    return lhs_category < rhs_category;
  }
  const std::size_t common = std::min<std::size_t>(lhs.tiebreak_len, rhs.tiebreak_len);
  for (std::size_t i = 0; i < common; ++i) {
    if (lhs.tiebreak[i] != rhs.tiebreak[i]) {
      return lhs.tiebreak[i] < rhs.tiebreak[i];
    }
  }
  return lhs.tiebreak_len < rhs.tiebreak_len;
}

bool operator>(const HandValue& lhs, const HandValue& rhs) {
  return rhs < lhs;
}

bool IsValidCoreCard(int card) {
  return card >= 0 && card < kShortDeckCards;
}

int CoreCardRank(int card) {
  if (!IsValidCoreCard(card)) {
    throw std::invalid_argument("invalid Short Deck core card id");
  }
  return (card % kShortDeckRanks) + 6;
}

int CoreCardSuit(int card) {
  if (!IsValidCoreCard(card)) {
    throw std::invalid_argument("invalid Short Deck core card id");
  }
  return card / kShortDeckRanks;
}

HandValue EvaluateFive(const std::array<int, 5>& cards) {
  ValidateFive(cards);

  std::array<int, 15> counts{};
  std::array<int, 5> ranks{};
  std::array<int, 5> suits{};
  for (std::size_t i = 0; i < cards.size(); ++i) {
    ranks[i] = CoreCardRank(cards[i]);
    suits[i] = CoreCardSuit(cards[i]);
    ++counts[ranks[i]];
  }

  const bool is_flush = std::all_of(
      suits.begin() + 1,
      suits.end(),
      [&](int suit) { return suit == suits[0]; });
  const int straight_high = StraightHigh(counts);

  if (is_flush && straight_high >= 0) {
    return MakeValue(HandCategory::kStraightFlush, {straight_high});
  }

  int quad = -1;
  int trip = -1;
  std::array<int, 2> pairs{{-1, -1}};
  int pair_count = 0;
  for (int rank = 14; rank >= 6; --rank) {
    if (counts[rank] == 4) {
      quad = rank;
    } else if (counts[rank] == 3) {
      trip = rank;
    } else if (counts[rank] == 2 && pair_count < 2) {
      pairs[pair_count++] = rank;
    }
  }

  if (quad >= 0) {
    int kicker = -1;
    for (int rank = 14; rank >= 6; --rank) {
      if (counts[rank] == 1) {
        kicker = rank;
        break;
      }
    }
    return MakeValue(HandCategory::kFourOfAKind, {quad, kicker});
  }

  // KKPoker Short Deck: flush outranks full house.
  if (is_flush) {
    std::sort(ranks.begin(), ranks.end(), std::greater<int>());
    return MakeValue(
        HandCategory::kFlush,
        {ranks[0], ranks[1], ranks[2], ranks[3], ranks[4]});
  }

  if (trip >= 0 && pair_count >= 1) {
    return MakeValue(HandCategory::kFullHouse, {trip, pairs[0]});
  }

  if (straight_high >= 0) {
    return MakeValue(HandCategory::kStraight, {straight_high});
  }

  if (trip >= 0) {
    std::array<int, 2> kickers{{-1, -1}};
    int kicker_index = 0;
    for (int rank = 14; rank >= 6; --rank) {
      if (counts[rank] == 1) {
        kickers[kicker_index++] = rank;
      }
    }
    return MakeValue(
        HandCategory::kThreeOfAKind,
        {trip, kickers[0], kickers[1]});
  }

  if (pair_count == 2) {
    int kicker = -1;
    for (int rank = 14; rank >= 6; --rank) {
      if (counts[rank] == 1) {
        kicker = rank;
        break;
      }
    }
    return MakeValue(
        HandCategory::kTwoPair,
        {pairs[0], pairs[1], kicker});
  }

  if (pair_count == 1) {
    std::array<int, 3> kickers{{-1, -1, -1}};
    int kicker_index = 0;
    for (int rank = 14; rank >= 6; --rank) {
      if (counts[rank] == 1) {
        kickers[kicker_index++] = rank;
      }
    }
    return MakeValue(
        HandCategory::kOnePair,
        {pairs[0], kickers[0], kickers[1], kickers[2]});
  }

  std::sort(ranks.begin(), ranks.end(), std::greater<int>());
  return MakeValue(
      HandCategory::kHighCard,
      {ranks[0], ranks[1], ranks[2], ranks[3], ranks[4]});
}

HandValue EvaluateBest(const std::vector<int>& cards) {
  if (cards.size() < 5 || cards.size() > 7) {
    throw std::invalid_argument("best-hand evaluation requires 5, 6 or 7 cards");
  }
  std::array<bool, kShortDeckCards> seen{};
  for (int card : cards) {
    if (!IsValidCoreCard(card)) {
      throw std::invalid_argument("invalid Short Deck core card id");
    }
    if (seen[card]) {
      throw std::invalid_argument("duplicate Short Deck core card id");
    }
    seen[card] = true;
  }

  bool initialized = false;
  HandValue best;
  const int n = static_cast<int>(cards.size());
  for (int a = 0; a < n - 4; ++a) {
    for (int b = a + 1; b < n - 3; ++b) {
      for (int c = b + 1; c < n - 2; ++c) {
        for (int d = c + 1; d < n - 1; ++d) {
          for (int e = d + 1; e < n; ++e) {
            const HandValue value = EvaluateFive(
                {{cards[a], cards[b], cards[c], cards[d], cards[e]}});
            if (!initialized || value > best) {
              best = value;
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

std::uint64_t EncodeHandValue(const HandValue& value) {
  if (value.tiebreak_len > 5) {
    throw std::invalid_argument("invalid tiebreak length");
  }
  std::uint64_t encoded = static_cast<std::uint8_t>(value.category);
  encoded = (encoded << 4) | value.tiebreak_len;
  for (std::size_t i = 0; i < 5; ++i) {
    const std::uint8_t rank = i < value.tiebreak_len ? value.tiebreak[i] : 0;
    if (rank > 15) {
      throw std::invalid_argument("tiebreak rank outside packed range");
    }
    encoded = (encoded << 4) | rank;
  }
  return encoded;
}

}  // namespace native
}  // namespace deepsix
