// Validation for the versioned OH6Plus -> DeepSix observation boundary.

#pragma once

#include <string>

#include "TableObservation.h"

namespace deepsix {

// Returns true only for structurally valid transport observations.
// If error != nullptr, a stable diagnostic is written on failure.
bool ValidateTableObservation(const TableObservation& observation,
                              std::string* error = nullptr);

}  // namespace deepsix
