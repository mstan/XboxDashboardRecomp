// SPDX-License-Identifier: GPL-3.0-or-later
#include "dashboard_image.hpp"
#include <cstdio>
#include <exception>

int wmain(int argc, wchar_t** argv) {
    if (argc != 3) {
        std::fputs("Usage: dashboard-import ORIGINAL-HDD-IMAGE NEW-DIRECTORY\n", stderr);
        return 2;
    }
    try {
        const auto executable = dashboard::import_image(argv[1], argv[2]);
        std::puts(executable.u8string().c_str());
        return 0;
    } catch (const std::exception& error) {
        std::fprintf(stderr, "%s\n", error.what());
        return 1;
    }
}
