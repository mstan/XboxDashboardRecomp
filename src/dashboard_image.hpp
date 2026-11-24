// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
#include <cstdint>
#include <filesystem>
#include <vector>

namespace dashboard {
inline constexpr char supported_xbe_sha256[] =
    "832862490c762a723856350142f49ded92b7ad966741eeb5b89e683006b16a0d";

std::vector<uint8_t> read_xbe(const std::filesystem::path& image);
std::filesystem::path import_image(const std::filesystem::path& image,
                                   const std::filesystem::path& destination);
}
