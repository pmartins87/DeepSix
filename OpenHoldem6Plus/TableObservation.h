// Versioned OpenHoldem6Plus -> DeepSix observation DTO.
//
// No strategic evaluation belongs here. This structure is transport only.
// Monetary values use integer table units to avoid float equality drift.

#pragma once

#include <cstdint>
#include <string>
#include <vector>

namespace deepsix {

constexpr int kTableObservationSchemaVersion = 1;

enum class Street {
  kPreflop = 0,
  kFlop = 1,
  kTurn = 2,
  kRiver = 3,
};

enum class ActionKind {
  kFold = 0,
  kCheck = 1,
  kCall = 2,
  kRaiseTo = 3,
};

struct SeatObservation {
  int seat = -1;
  bool dealt = false;
  bool folded = false;
  bool all_in = false;
  std::int64_t stack = 0;
  std::int64_t committed_street = 0;
  std::int64_t committed_total = 0;
};

struct ActionEvent {
  std::uint64_t seq = 0;
  Street street = Street::kPreflop;
  int actor_seat = -1;
  ActionKind action = ActionKind::kFold;
  // Only meaningful for kRaiseTo. -1 means not present.
  std::int64_t amount_to = -1;
};

struct TableObservation {
  int schema_version = kTableObservationSchemaVersion;
  std::string hand_id;
  std::uint64_t observation_seq = 0;
  std::uint64_t source_timestamp_ms = 0;

  Street street = Street::kPreflop;
  int dealer_seat = -1;
  int hero_seat = -1;

  // Compact DeepSix card ids 0..35.
  std::vector<int> hero_cards;
  std::vector<int> board;

  std::vector<SeatObservation> seats;
  std::vector<ActionEvent> actions;

  std::int64_t ante = 0;
  std::int64_t pot = 0;
  std::int64_t to_call = 0;
  std::int64_t min_raise_to = 0;
  std::int64_t max_raise_to = 0;
};

}  // namespace deepsix
