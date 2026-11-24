// SPDX-License-Identifier: GPL-3.0-or-later
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <shellapi.h>

#include "dashboard_image.hpp"
#include "launcher_profile.h"
#include "recomp_launcher.h"

#include <cstdlib>
#include <cstdio>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <functional>
#include <stdexcept>
#include <string>

namespace fs = std::filesystem;

namespace {
int read_dashboard(void*, const char* path, uint8_t** bytes, size_t* size,
                   char* error, size_t error_size) {
    try {
        const auto xbe = dashboard::read_xbe(fs::u8path(path));
        *bytes = static_cast<uint8_t*>(std::malloc(xbe.size()));
        if (!*bytes) return 0;
        *size = xbe.size();
        std::memcpy(*bytes, xbe.data(), *size);
        return 1;
    } catch (const std::exception& failure) {
        std::snprintf(error, error_size, "%s", failure.what());
        return 0;
    }
}

void free_dashboard(void*, uint8_t* bytes) {
    std::free(bytes);
}

fs::path import_dashboard(const fs::path& image, const fs::path& cache) {
    const auto identity = image.native() + L"\n" + std::to_wstring(fs::file_size(image)) +
        L"\n" + std::to_wstring(fs::last_write_time(image).time_since_epoch().count());
    const auto destination = cache / std::to_wstring(std::hash<std::wstring>{}(identity));
    const auto xbe = destination / "xboxdash.xbe";
    if (fs::is_regular_file(xbe)) return xbe;

    fs::create_directories(cache);
    const auto pending = cache / (L"import-" + std::to_wstring(GetCurrentProcessId()));
    if (!fs::create_directory(pending)) throw std::runtime_error("Could not reserve a Dashboard import");
    try {
        const auto files = pending / "C";
        dashboard::import_image(image, files);
        std::error_code rename_error;
        fs::rename(files, destination, rename_error);
        if (rename_error && !fs::is_regular_file(xbe)) {
            throw fs::filesystem_error("Could not save the Dashboard import", files, destination, rename_error);
        }
    } catch (...) {
        std::error_code ignored;
        fs::remove_all(pending, ignored);
        throw;
    }
    std::error_code ignored;
    fs::remove_all(pending, ignored);
    return xbe;
}

int boot(const fs::path& root, const fs::path& image, bool prepare_only, unsigned volume) {
    const auto runtime = root / "runtime";
    const auto xbe = import_dashboard(image, runtime / "data" / "dashboard-import");
    const auto python = runtime / "python" / "pythonw.exe";
    const auto driver = root / "launch_dashboard.py";
    std::wstring command = L"\"" + python.native() + L"\" -B \"" + driver.native() +
        L"\" \"" + xbe.native() + L"\" --volume " + std::to_wstring(volume);
    if (prepare_only) command += L" --prepare-only";
    STARTUPINFOW startup{};
    startup.cb = sizeof(startup);
    PROCESS_INFORMATION child{};
    if (!CreateProcessW(python.c_str(), command.data(), nullptr, nullptr, FALSE,
                        CREATE_NO_WINDOW, nullptr, root.c_str(), &startup, &child)) {
        throw std::runtime_error("Could not start the packaged Dashboard runtime");
    }
    CloseHandle(child.hThread);
    WaitForSingleObject(child.hProcess, INFINITE);
    DWORD result = 2;
    GetExitCodeProcess(child.hProcess, &result);
    CloseHandle(child.hProcess);
    return static_cast<int>(result);
}
}

int WINAPI wWinMain(HINSTANCE, HINSTANCE, PWSTR, int) {
    bool automated = false;
    try {
        std::wstring executable(32768, L'\0');
        const DWORD length = GetModuleFileNameW(nullptr, executable.data(), static_cast<DWORD>(executable.size()));
        if (!length || length == executable.size()) return 2;
        executable.resize(length);
        const auto root = fs::path(executable).parent_path();

        int argc = 0;
        LPWSTR* argv = CommandLineToArgvW(GetCommandLineW(), &argc);
        if (!argv) return 2;
        if (argc >= 3 && std::wstring(argv[1]) == L"--hdd") {
            const fs::path image = argv[2];
            automated = argc == 4 && std::wstring(argv[3]) == L"--prepare-only";
            LocalFree(argv);
            return boot(root, fs::absolute(image), automated, 100);
        }
        LocalFree(argv);

        const auto preference = root / "menu-hdd.cfg";
        std::string last;
        std::ifstream config(preference);
        std::getline(config, last);
        RecompLauncherCSettings settings{};
        settings.window_scale = 2;
        settings.enable_audio = 1;
        settings.audio_freq = 48000;
        settings.volume = 100;
        config >> settings.volume;

        RecompLauncherCGameInfo game{};
        launcher_profile_apply("xbox", &game);
        static const char* patterns[] = {"*.img", "*.bin", "*.qcow2"};
        static const RecompLauncherCRomRevision revisions[] = {
            {"Original Xbox Dashboard 5960", dashboard::supported_xbe_sha256, nullptr, nullptr, 1, nullptr},
        };
        game.name = "Xbox Dashboard";
        game.platform = "XBOX";
        game.rom_noun = "Xbox HDD image";
        game.rom_filter_desc = "Xbox HDD image";
        game.rom_patterns = patterns;
        game.num_rom_patterns = 3;
        game.rom_revisions = revisions;
        game.num_rom_revisions = 1;
        game.rom_read = read_dashboard;
        game.rom_read_free = free_dashboard;
        game.has_bios = 0;
        game.setup_wizard_supported = 1;
        char selected[2048]{};
        const auto assets = (root / "assets").u8string();
        const auto result = recomp_launcher_run_window("Xbox Dashboard", &settings, &game,
            assets.c_str(), last.c_str(), selected, sizeof selected);
        if (result == RECOMP_LAUNCHER_RESULT_QUIT) return 0;
        if (result != RECOMP_LAUNCHER_RESULT_LAUNCH || !selected[0]) return 2;
        std::ofstream(preference) << selected << '\n' << settings.volume << '\n';
        return boot(root, fs::absolute(fs::u8path(selected)), false, settings.enable_audio ? settings.volume : 0);
    } catch (const std::exception& error) {
        if (!automated) MessageBoxA(nullptr, error.what(), "Xbox Dashboard setup", MB_OK | MB_ICONERROR);
        return 2;
    }
}
