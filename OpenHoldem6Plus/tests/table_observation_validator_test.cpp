#include "../TableObservationValidator.h"

#include <cassert>
#include <string>

namespace {

deepsix::TableObservation ValidObservation() {
  using namespace deepsix;
  TableObservation observation;
  observation.hand_id = "H1";
  observation.observation_seq = 7;
  observation.source_timestamp_ms = 1234;
  observation.street = Street::kFlop;
  observation.dealer_seat = 0;
  observation.hero_seat = 1;
  observation.hero_cards = {8, 34};
  observation.board = {6, 14, 21};
  observation.seats = {
      SeatObservation{0, true, false, false, 80, 20, 30},
      SeatObservation{1, true, false, false, 90, 10, 20},
  };
  observation.actions = {
      ActionEvent{1, Street::kPreflop, 1, ActionKind::kCall, -1},
      ActionEvent{2, Street::kPreflop, 0, ActionKind::kCheck, -1},
  };
  observation.ante = 10;
  observation.pot = 50;
  observation.to_call = 10;
  observation.min_raise_to = 30;
  observation.max_raise_to = 100;
  return observation;
}

}  // namespace

int main() {
  using namespace deepsix;
  std::string error;

  TableObservation observation = ValidObservation();
  assert(ValidateTableObservation(observation, &error));
  assert(error.empty());

  observation = ValidObservation();
  observation.board[0] = observation.hero_cards[0];
  assert(!ValidateTableObservation(observation, &error));

  observation = ValidObservation();
  observation.board.push_back(7);
  assert(!ValidateTableObservation(observation, &error));

  observation = ValidObservation();
  observation.seats[1].seat = 6;
  assert(!ValidateTableObservation(observation, &error));

  observation = ValidObservation();
  observation.actions[1].seq = 1;
  assert(!ValidateTableObservation(observation, &error));

  observation = ValidObservation();
  observation.actions[0].actor_seat = 5;
  assert(!ValidateTableObservation(observation, &error));

  observation = ValidObservation();
  observation.actions[0].amount_to = 20;
  assert(!ValidateTableObservation(observation, &error));

  observation = ValidObservation();
  observation.min_raise_to = 101;
  assert(!ValidateTableObservation(observation, &error));

  return 0;
}
