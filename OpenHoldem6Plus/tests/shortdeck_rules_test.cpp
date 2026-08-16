#include "../ShortDeckRules.h"

#include <cassert>
#include <set>

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
  return 0;
}
