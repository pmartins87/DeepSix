#include "ShortDeckRules.h"

namespace deepsix {

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

}  // namespace deepsix
