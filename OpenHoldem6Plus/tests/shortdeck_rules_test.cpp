#include "../ShortDeckRules.h"

#include <cassert>
#include <set>
#include <vector>

int main() {
  using namespace deepsix;

  for (int rank = 2; rank <= 5; ++rank) {
    for (int suit = 0; suit < 4; ++suit) {
      assert(CoreCardIdFromRankSuit(rank, suit) == -1);
    }
  }

  std::set<int> ids;
  for (int rank = 6; rank <= 14; ++rank) {
    for (int suit = 0; suit < 4; ++suit) {
      const int id = CoreCardIdFromRankSuit(rank, suit);
      assert(id >= 0 && id < kShortDeckNumCards);
      ids.insert(id);
    }
  }

  assert(ids.size() == 36);
  assert(*ids.begin() == 0);
  assert(*ids.rbegin() == 35);
  assert(CoreCardIdFromRankSuit(6, 0) == 0);
  assert(CoreCardIdFromRankSuit(14, 3) == 35);
  assert(CoreCardIdFromRankSuit(6, -1) == -1);
  assert(CoreCardIdFromRankSuit(6, 4) == -1);

  // Full 6-max table, Dealer at chair 5: action starts chair 0 and Dealer last.
  const std::uint32_t full_mask = 0x3fU;
  assert((ActionOrderFromDealer(5, full_mask) ==
          std::vector<int>{0, 1, 2, 3, 4, 5}));

  // Waiting/sitting-out physical chairs do not alter dealt-player order.
  const std::uint32_t sparse_mask = (1U << 0) | (1U << 2) | (1U << 5);
  assert((ActionOrderFromDealer(5, sparse_mask) ==
          std::vector<int>{0, 2, 5}));
  assert(NextDealtChairClockwise(0, sparse_mask) == 2);
  assert(NextDealtChairClockwise(2, sparse_mask) == 5);
  assert(NextDealtChairClockwise(5, sparse_mask) == 0);

  // Dealer posts two antes total; other dealt players one; undealt zero.
  assert(ExpectedAnteContribution(5, 5, sparse_mask, 10) == 20);
  assert(ExpectedAnteContribution(0, 5, sparse_mask, 10) == 10);
  assert(ExpectedAnteContribution(2, 5, sparse_mask, 10) == 10);
  assert(ExpectedAnteContribution(1, 5, sparse_mask, 10) == 0);

  // Invalid dealer/dealt state fails closed.
  assert(ActionOrderFromDealer(5, (1U << 0) | (1U << 2)).empty());
  assert(ExpectedAnteContribution(0, 5, sparse_mask, 0) == 0);
  return 0;
}
