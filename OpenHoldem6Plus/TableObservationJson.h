// Deterministic JSON serialization for the OH6Plus -> DeepSix observation contract.
//
// The key order intentionally matches Python json.dumps(..., sort_keys=True,
// separators=(",", ":")) so the exact bytes can be regression-tested across
// languages before hashing.

#pragma once

#include <string>

#include "TableObservation.h"

namespace deepsix {

std::string CanonicalTableObservationJson(const TableObservation& observation,
                                          bool include_transport = true);

}  // namespace deepsix
