// SPDX-License-Identifier: GPL-3.0-or-later
#include "dashboard_image.hpp"
#include "fatx_volume.hpp"

#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <bcrypt.h>

#include <algorithm>
#include <array>
#include <cctype>
#include <fstream>
#include <set>
#include <stdexcept>
#include <string>

namespace dashboard {
namespace fs = std::filesystem;
using xllr::storage::FatxEntry;
using xllr::storage::FatxVolume;
using xllr::storage::XboxDisk;

namespace {
constexpr unsigned system_partition = 2;
constexpr char dashboard_name[] = "xboxdash.xbe";

std::string lower(std::string name) {
    for (char& byte : name) byte = static_cast<char>(std::tolower(static_cast<unsigned char>(byte)));
    return name;
}

std::string sha256(std::vector<uint8_t>& bytes) {
    BCRYPT_ALG_HANDLE provider = nullptr;
    if (BCryptOpenAlgorithmProvider(&provider, BCRYPT_SHA256_ALGORITHM, nullptr, 0) != 0) {
        throw std::runtime_error("Windows could not initialize SHA-256");
    }
    std::array<uint8_t, 32> digest{};
    BCRYPT_HASH_HANDLE hash = nullptr;
    auto status = BCryptCreateHash(provider, &hash, nullptr, 0, nullptr, 0, 0);
    if (status == 0) {
        status = BCryptHashData(hash, bytes.data(), static_cast<ULONG>(bytes.size()), 0);
        if (status == 0) {
            status = BCryptFinishHash(hash, digest.data(), static_cast<ULONG>(digest.size()), 0);
        }
        BCryptDestroyHash(hash);
    }
    BCryptCloseAlgorithmProvider(provider, 0);
    if (status != 0) throw std::runtime_error("Windows could not hash the Dashboard executable");
    constexpr char hex[] = "0123456789abcdef";
    std::string result;
    for (const uint8_t byte : digest) {
        result += hex[byte >> 4];
        result += hex[byte & 15];
    }
    return result;
}

std::vector<uint8_t> checked_xbe(FatxVolume& volume) {
    const auto executable = volume.lookup(dashboard_name);
    if (executable.directory() || executable.size() < 512 || executable.size() > 8 * 1024 * 1024) {
        throw std::runtime_error("The C partition has no supported Dashboard executable");
    }
    std::vector<uint8_t> bytes(executable.size());
    if (volume.read(executable, 0, bytes.data(), bytes.size()) != bytes.size() ||
        sha256(bytes) != supported_xbe_sha256) {
        throw std::runtime_error("Select an original Xbox HDD image containing Dashboard 5960");
    }
    return bytes;
}

std::string validate_name(const FatxEntry& entry) {
    const auto name = entry.name();
    if (name.empty() || name == "." || name == ".." ||
        name.front() == ' ' || name.back() == ' ' || name.back() == '.') {
        throw std::runtime_error("Unsupported Dashboard asset name");
    }
    for (const unsigned char byte : name) {
        if (byte < 32 || byte > 126 || std::string("<>:\"/\\|?*").find(byte) != std::string::npos) {
            throw std::runtime_error("Unsupported Dashboard asset name");
        }
    }
    const auto stem = lower(name.substr(0, name.find('.')));
    if (stem == "con" || stem == "prn" || stem == "aux" || stem == "nul" ||
        (stem.size() == 4 && (stem.compare(0, 3, "com") == 0 || stem.compare(0, 3, "lpt") == 0) &&
         stem.back() >= '0' && stem.back() <= '9')) {
        throw std::runtime_error("Reserved Windows name in Dashboard assets");
    }
    return name;
}

bool dashboard_asset(const FatxEntry& entry) {
    const auto name = lower(entry.name());
    if (entry.directory()) {
        return name == "audio" || name == "fonts" || name == "xodash" || name == "xboxdashdata.185ead00";
    }
    return name == dashboard_name || name == "xbox.xtf" || name == "xbox book.xtf";
}

class Import {
    FatxVolume& volume_;
    std::set<uint32_t> directories_;
    std::array<char, 64 * 1024> buffer_{};

public:
    explicit Import(FatxVolume& volume) : volume_(volume) {}

    void copy(const FatxEntry& entry, const fs::path& directory) {
        const auto destination = directory / validate_name(entry);
        if (fs::exists(destination)) throw std::runtime_error("Duplicate name in Dashboard assets");
        if (entry.directory()) {
            if (!directories_.insert(entry.cluster()).second) throw std::runtime_error("Repeated Dashboard directory");
            fs::create_directory(destination);
            for (const auto& child : volume_.list(entry)) copy(child, destination);
            return;
        }
        std::ofstream out(destination, std::ios::binary);
        if (!out) throw std::runtime_error("Could not create a Dashboard asset");
        for (uint64_t offset = 0; offset < entry.size();) {
            const auto count = std::min<uint64_t>(buffer_.size(), entry.size() - offset);
            if (volume_.read(entry, offset, buffer_.data(), static_cast<size_t>(count)) != count) {
                throw std::runtime_error("The original HDD image ended inside a Dashboard asset");
            }
            out.write(buffer_.data(), static_cast<std::streamsize>(count));
            if (!out) throw std::runtime_error("Failed while writing a Dashboard asset");
            offset += count;
        }
    }
};
}

std::vector<uint8_t> read_xbe(const fs::path& image) {
    XboxDisk disk(image.u8string(), false);
    return checked_xbe(*disk.partitions[system_partition]);
}

fs::path import_image(const fs::path& image, const fs::path& destination) {
    XboxDisk disk(image.u8string(), false);
    auto& volume = *disk.partitions[system_partition];
    checked_xbe(volume);
    const auto entries = volume.list(volume.root());
    if (std::none_of(entries.begin(), entries.end(), [](const FatxEntry& entry) {
        return entry.directory() && lower(entry.name()) == "xboxdashdata.185ead00";
    })) throw std::runtime_error("Dashboard 5960 assets are missing from the C partition");
    if (!fs::create_directory(destination)) throw std::runtime_error("Use a fresh Dashboard import directory");
    Import importer(volume);
    for (const auto& entry : entries) {
        if (dashboard_asset(entry)) importer.copy(entry, destination);
    }
    return destination / dashboard_name;
}
}
