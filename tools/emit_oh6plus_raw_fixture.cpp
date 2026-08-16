#include "RawTableSnapshot.h"
#include "RawTableSnapshotJson.h"

#include <iostream>
#include <string>

int main() {
  using namespace deepsix6plus;

  RawTableSnapshot snapshot;
  snapshot.dealer_chair = 5;
  snapshot.hero_chair = -1;
  snapshot.community_card_count = 3;
  for (int chair = 0; chair < kRawMaxChairs; ++chair) {
    snapshot.seats[chair].chair = chair;
  }

  snapshot.board[0] = RawCard{true, true, false, 6, 0};
  snapshot.board[1] = RawCard{true, true, false, 14, 3};
  snapshot.board[2] = RawCard{true, true, false, 10, 1};
  snapshot.seats[5].seated = true;
  snapshot.seats[5].active = true;
  snapshot.seats[5].dealer = true;
  snapshot.seats[5].balance = 97.5;
  snapshot.seats[5].current_bet = 2.0;
  snapshot.seats[5].stack_including_current_bet = 99.5;
  snapshot.pots[0] = 12.5;

  std::string error;
  if (!ValidateRawSnapshotForShortDeck(snapshot, &error)) {
    std::cerr << error << '\n';
    return 1;
  }

  std::cout << RawTableSnapshotAuditJson(snapshot) << '\n';
  return 0;
}
