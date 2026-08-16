#include "../TableObservation.h"
#include "../TableObservationJson.h"
#include "../TableObservationValidator.h"

#include <cassert>
#include <iostream>
#include <string>

int main() {
  using namespace deepsix;

  TableObservation observation;
  observation.schema_version = kTableObservationSchemaVersion;
  observation.hand_id = "fixture-6plus-0001";
  observation.observation_seq = 42;
  observation.source_timestamp_ms = 1723780800123ULL;
  observation.street = Street::kFlop;
  observation.dealer_seat = 1;
  observation.hero_seat = 4;
  observation.hero_cards = {8, 25};
  observation.board = {0, 13, 33};
  observation.seats = {
      SeatObservation{1, true, false, false, 92, 0, 8},
      SeatObservation{2, true, false, false, 92, 0, 8},
      SeatObservation{4, true, false, false, 88, 0, 12},
  };
  observation.actions = {
      ActionEvent{0, Street::kPreflop, 2, ActionKind::kCall, -1},
      ActionEvent{1, Street::kPreflop, 4, ActionKind::kRaiseTo, 12},
      ActionEvent{2, Street::kPreflop, 1, ActionKind::kCall, -1},
  };
  observation.ante = 2;
  observation.pot = 30;
  observation.to_call = 0;
  observation.min_raise_to = 2;
  observation.max_raise_to = 88;

  std::string error;
  assert(ValidateTableObservation(observation, &error));

  const std::string full = CanonicalTableObservationJson(observation, true);
  const std::string semantic = CanonicalTableObservationJson(observation, false);

  const std::string expected_full =
      "{\"actions\":[{\"action\":\"call\",\"actor_seat\":2,\"amount_to\":null,\"seq\":0,\"street\":\"preflop\"},{\"action\":\"raise_to\",\"actor_seat\":4,\"amount_to\":12,\"seq\":1,\"street\":\"preflop\"},{\"action\":\"call\",\"actor_seat\":1,\"amount_to\":null,\"seq\":2,\"street\":\"preflop\"}],\"ante\":2,\"board\":[0,13,33],\"dealer_seat\":1,\"hand_id\":\"fixture-6plus-0001\",\"hero_cards\":[8,25],\"hero_seat\":4,\"max_raise_to\":88,\"min_raise_to\":2,\"observation_seq\":42,\"pot\":30,\"schema_version\":1,\"seats\":[{\"all_in\":false,\"committed_street\":0,\"committed_total\":8,\"dealt\":true,\"folded\":false,\"seat\":1,\"stack\":92},{\"all_in\":false,\"committed_street\":0,\"committed_total\":8,\"dealt\":true,\"folded\":false,\"seat\":2,\"stack\":92},{\"all_in\":false,\"committed_street\":0,\"committed_total\":12,\"dealt\":true,\"folded\":false,\"seat\":4,\"stack\":88}],\"source_timestamp_ms\":1723780800123,\"street\":\"flop\",\"to_call\":0}";
  const std::string expected_semantic =
      "{\"actions\":[{\"action\":\"call\",\"actor_seat\":2,\"amount_to\":null,\"seq\":0,\"street\":\"preflop\"},{\"action\":\"raise_to\",\"actor_seat\":4,\"amount_to\":12,\"seq\":1,\"street\":\"preflop\"},{\"action\":\"call\",\"actor_seat\":1,\"amount_to\":null,\"seq\":2,\"street\":\"preflop\"}],\"ante\":2,\"board\":[0,13,33],\"dealer_seat\":1,\"hero_cards\":[8,25],\"hero_seat\":4,\"max_raise_to\":88,\"min_raise_to\":2,\"pot\":30,\"schema_version\":1,\"seats\":[{\"all_in\":false,\"committed_street\":0,\"committed_total\":8,\"dealt\":true,\"folded\":false,\"seat\":1,\"stack\":92},{\"all_in\":false,\"committed_street\":0,\"committed_total\":8,\"dealt\":true,\"folded\":false,\"seat\":2,\"stack\":92},{\"all_in\":false,\"committed_street\":0,\"committed_total\":12,\"dealt\":true,\"folded\":false,\"seat\":4,\"stack\":88}],\"street\":\"flop\",\"to_call\":0}";

  assert(full == expected_full);
  assert(semantic == expected_semantic);

  std::cout << full << '\n' << semantic << '\n';
  return 0;
}
