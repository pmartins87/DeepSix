#include "TableObservationJson.h"

#include <cstdint>
#include <string>

namespace deepsix {
namespace {

void AppendQuoted(const std::string& value, std::string* out) {
  static const char kHex[] = "0123456789abcdef";
  out->push_back('"');
  for (unsigned char ch : value) {
    switch (ch) {
      case '"': *out += "\\\""; break;
      case '\\': *out += "\\\\"; break;
      case '\b': *out += "\\b"; break;
      case '\f': *out += "\\f"; break;
      case '\n': *out += "\\n"; break;
      case '\r': *out += "\\r"; break;
      case '\t': *out += "\\t"; break;
      default:
        if (ch < 0x20) {
          *out += "\\u00";
          out->push_back(kHex[(ch >> 4) & 0x0f]);
          out->push_back(kHex[ch & 0x0f]);
        } else {
          out->push_back(static_cast<char>(ch));
        }
    }
  }
  out->push_back('"');
}

const char* StreetName(Street street) {
  switch (street) {
    case Street::kPreflop: return "preflop";
    case Street::kFlop: return "flop";
    case Street::kTurn: return "turn";
    case Street::kRiver: return "river";
  }
  return "invalid";
}

const char* ActionName(ActionKind action) {
  switch (action) {
    case ActionKind::kFold: return "fold";
    case ActionKind::kCheck: return "check";
    case ActionKind::kCall: return "call";
    case ActionKind::kRaiseTo: return "raise_to";
  }
  return "invalid";
}

void AppendInt(std::int64_t value, std::string* out) {
  *out += std::to_string(value);
}

void AppendUInt(std::uint64_t value, std::string* out) {
  *out += std::to_string(value);
}

void AppendBool(bool value, std::string* out) {
  *out += value ? "true" : "false";
}

void AppendIntVector(const std::vector<int>& values, std::string* out) {
  out->push_back('[');
  for (std::size_t i = 0; i < values.size(); ++i) {
    if (i != 0) out->push_back(',');
    *out += std::to_string(values[i]);
  }
  out->push_back(']');
}

void AppendActions(const std::vector<ActionEvent>& actions, std::string* out) {
  out->push_back('[');
  for (std::size_t i = 0; i < actions.size(); ++i) {
    if (i != 0) out->push_back(',');
    const ActionEvent& action = actions[i];
    *out += "{\"action\":";
    AppendQuoted(ActionName(action.action), out);
    *out += ",\"actor_seat\":";
    *out += std::to_string(action.actor_seat);
    *out += ",\"amount_to\":";
    if (action.action == ActionKind::kRaiseTo) {
      AppendInt(action.amount_to, out);
    } else {
      *out += "null";
    }
    *out += ",\"seq\":";
    AppendUInt(action.seq, out);
    *out += ",\"street\":";
    AppendQuoted(StreetName(action.street), out);
    out->push_back('}');
  }
  out->push_back(']');
}

void AppendSeats(const std::vector<SeatObservation>& seats, std::string* out) {
  out->push_back('[');
  for (std::size_t i = 0; i < seats.size(); ++i) {
    if (i != 0) out->push_back(',');
    const SeatObservation& seat = seats[i];
    *out += "{\"all_in\":";
    AppendBool(seat.all_in, out);
    *out += ",\"committed_street\":";
    AppendInt(seat.committed_street, out);
    *out += ",\"committed_total\":";
    AppendInt(seat.committed_total, out);
    *out += ",\"dealt\":";
    AppendBool(seat.dealt, out);
    *out += ",\"folded\":";
    AppendBool(seat.folded, out);
    *out += ",\"seat\":";
    *out += std::to_string(seat.seat);
    *out += ",\"stack\":";
    AppendInt(seat.stack, out);
    out->push_back('}');
  }
  out->push_back(']');
}

}  // namespace

std::string CanonicalTableObservationJson(const TableObservation& observation,
                                          bool include_transport) {
  std::string out;
  out.reserve(1024);
  out += "{\"actions\":";
  AppendActions(observation.actions, &out);
  out += ",\"ante\":";
  AppendInt(observation.ante, &out);
  out += ",\"board\":";
  AppendIntVector(observation.board, &out);
  out += ",\"dealer_seat\":";
  out += std::to_string(observation.dealer_seat);
  if (include_transport) {
    out += ",\"hand_id\":";
    AppendQuoted(observation.hand_id, &out);
  }
  out += ",\"hero_cards\":";
  AppendIntVector(observation.hero_cards, &out);
  out += ",\"hero_seat\":";
  out += std::to_string(observation.hero_seat);
  out += ",\"max_raise_to\":";
  AppendInt(observation.max_raise_to, &out);
  out += ",\"min_raise_to\":";
  AppendInt(observation.min_raise_to, &out);
  if (include_transport) {
    out += ",\"observation_seq\":";
    AppendUInt(observation.observation_seq, &out);
  }
  out += ",\"pot\":";
  AppendInt(observation.pot, &out);
  out += ",\"schema_version\":";
  out += std::to_string(observation.schema_version);
  out += ",\"seats\":";
  AppendSeats(observation.seats, &out);
  if (include_transport) {
    out += ",\"source_timestamp_ms\":";
    AppendUInt(observation.source_timestamp_ms, &out);
  }
  out += ",\"street\":";
  AppendQuoted(StreetName(observation.street), &out);
  out += ",\"to_call\":";
  AppendInt(observation.to_call, &out);
  out.push_back('}');
  return out;
}

}  // namespace deepsix
