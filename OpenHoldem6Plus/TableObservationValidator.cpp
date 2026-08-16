#include "TableObservationValidator.h"

#include <array>
#include <cstddef>

#include "ShortDeckRules.h"

namespace deepsix {
namespace {

bool Fail(const char* message, std::string* error) {
  if (error != nullptr) {
    *error = message;
  }
  return false;
}

bool IsValidStreet(Street street) {
  const int value = static_cast<int>(street);
  return value >= static_cast<int>(Street::kPreflop) &&
         value <= static_cast<int>(Street::kRiver);
}

bool IsValidActionKind(ActionKind action) {
  const int value = static_cast<int>(action);
  return value >= static_cast<int>(ActionKind::kFold) &&
         value <= static_cast<int>(ActionKind::kRaiseTo);
}

std::size_t ExpectedBoardCards(Street street) {
  switch (street) {
    case Street::kPreflop:
      return 0;
    case Street::kFlop:
      return 3;
    case Street::kTurn:
      return 4;
    case Street::kRiver:
      return 5;
  }
  return 999;
}

}  // namespace

bool ValidateTableObservation(const TableObservation& observation,
                              std::string* error) {
  if (observation.schema_version != kTableObservationSchemaVersion) {
    return Fail("unsupported schema version", error);
  }
  if (observation.hand_id.empty()) {
    return Fail("hand_id is required", error);
  }
  if (!IsValidStreet(observation.street)) {
    return Fail("invalid street", error);
  }
  if (observation.seats.size() < 2 ||
      observation.seats.size() > kShortDeckMaxPlayers) {
    return Fail("seat count must be 2..6", error);
  }

  std::array<bool, kShortDeckMaxPlayers> seat_seen{};
  for (const SeatObservation& seat : observation.seats) {
    if (seat.seat < 0 || seat.seat >= kShortDeckMaxPlayers) {
      return Fail("seat must be 0..5", error);
    }
    if (seat_seen[seat.seat]) {
      return Fail("duplicate seat", error);
    }
    seat_seen[seat.seat] = true;
    if (seat.stack < 0 || seat.committed_street < 0 ||
        seat.committed_total < 0) {
      return Fail("negative seat amount", error);
    }
    if (seat.committed_street > seat.committed_total) {
      return Fail("street commitment exceeds total commitment", error);
    }
    if (seat.folded && seat.all_in) {
      return Fail("seat cannot be folded and all-in", error);
    }
  }

  if (observation.dealer_seat < 0 ||
      observation.dealer_seat >= kShortDeckMaxPlayers ||
      !seat_seen[observation.dealer_seat]) {
    return Fail("dealer seat missing", error);
  }
  if (observation.hero_seat < 0 ||
      observation.hero_seat >= kShortDeckMaxPlayers ||
      !seat_seen[observation.hero_seat]) {
    return Fail("hero seat missing", error);
  }
  if (observation.hero_cards.size() != 2) {
    return Fail("hero must have two cards", error);
  }
  if (observation.board.size() != ExpectedBoardCards(observation.street)) {
    return Fail("board-card count does not match street", error);
  }

  std::array<bool, kShortDeckNumCards> card_seen{};
  const auto validate_card = [&](int card) -> bool {
    if (card < 0 || card >= kShortDeckNumCards) {
      return false;
    }
    if (card_seen[card]) {
      return false;
    }
    card_seen[card] = true;
    return true;
  };
  for (int card : observation.hero_cards) {
    if (!validate_card(card)) {
      return Fail("invalid or duplicate hero card", error);
    }
  }
  for (int card : observation.board) {
    if (!validate_card(card)) {
      return Fail("invalid or duplicate board card", error);
    }
  }

  if (observation.ante < 0 || observation.pot < 0 ||
      observation.to_call < 0 || observation.min_raise_to < 0 ||
      observation.max_raise_to < 0) {
    return Fail("negative table amount", error);
  }
  if (observation.min_raise_to > observation.max_raise_to) {
    return Fail("min raise exceeds max raise", error);
  }

  bool first_action = true;
  std::uint64_t previous_seq = 0;
  for (const ActionEvent& action : observation.actions) {
    if (!IsValidStreet(action.street)) {
      return Fail("invalid action street", error);
    }
    if (!IsValidActionKind(action.action)) {
      return Fail("invalid action kind", error);
    }
    if (action.actor_seat < 0 ||
        action.actor_seat >= kShortDeckMaxPlayers ||
        !seat_seen[action.actor_seat]) {
      return Fail("action actor seat missing", error);
    }
    if (!first_action && action.seq <= previous_seq) {
      return Fail("action sequence not increasing", error);
    }
    first_action = false;
    previous_seq = action.seq;

    if (action.action == ActionKind::kRaiseTo) {
      if (action.amount_to < 0) {
        return Fail("raise-to action requires amount", error);
      }
    } else if (action.amount_to != -1) {
      return Fail("non-raise action must not carry amount", error);
    }
  }

  if (error != nullptr) {
    error->clear();
  }
  return true;
}

}  // namespace deepsix
