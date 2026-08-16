#include "ShortDeckRules.h"

namespace deepsix {
namespace {

bool IsValidChair(int chair) {
  return chair >= 0 && chair < kShortDeckMaxPlayers;
}

bool IsDealt(int chair, std::uint32_t dealt_mask) {
  return IsValidChair(chair) && ((dealt_mask >> chair) & 1U) != 0;
}

}  // namespace

bool IsValidShortDeckRank(int rank) {
  return rank >= kShortDeckMinRank && rank <= kShortDeckMaxRank;
}

bool IsValidSuit(int suit) {
  return suit >= 0 && suit < kShortDeckNumSuits;
}

int CoreCardIdFromRankSuit(int rank, int suit) {
  if (!IsValidShortDeckRank(rank) || !IsValidSuit(suit)) {
    return -1;
  }
  const int rank_index = rank - kShortDeckMinRank;
  return suit * kShortDeckNumRanks + rank_index;
}

int NextDealtChairClockwise(int from_chair, std::uint32_t dealt_mask) {
  if (!IsValidChair(from_chair)) {
    return -1;
  }
  for (int offset = 1; offset <= kShortDeckMaxPlayers; ++offset) {
    const int chair = (from_chair + offset) % kShortDeckMaxPlayers;
    if (IsDealt(chair, dealt_mask)) {
      return chair;
    }
  }
  return -1;
}

std::vector<int> ActionOrderFromDealer(int dealer_chair,
                                       std::uint32_t dealt_mask) {
  std::vector<int> order;
  if (!IsValidChair(dealer_chair) || !IsDealt(dealer_chair, dealt_mask)) {
    return order;
  }

  int chair = dealer_chair;
  for (int steps = 0; steps < kShortDeckMaxPlayers - 1; ++steps) {
    chair = NextDealtChairClockwise(chair, dealt_mask);
    if (chair < 0 || chair == dealer_chair) {
      break;
    }
    order.push_back(chair);
  }
  order.push_back(dealer_chair);
  return order;
}

std::int64_t ExpectedAnteContribution(int chair,
                                      int dealer_chair,
                                      std::uint32_t dealt_mask,
                                      std::int64_t ante) {
  if (!IsValidChair(chair) || !IsValidChair(dealer_chair) || ante <= 0 ||
      !IsDealt(chair, dealt_mask) || !IsDealt(dealer_chair, dealt_mask)) {
    return 0;
  }
  return chair == dealer_chair ? 2 * ante : ante;
}

}  // namespace deepsix
