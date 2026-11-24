cmake_minimum_required(VERSION 3.20)
project(XboxDashboardRecomp VERSION 0.2.0 LANGUAGES C CXX)

if(NOT WIN32)
    message(FATAL_ERROR "The Dashboard player is currently a Windows x64 build")
endif()

add_subdirectory(xboxllr/src/storage storage EXCLUDE_FROM_ALL)
add_library(dashboard_image STATIC src/dashboard_image.cpp)
target_compile_features(dashboard_image PUBLIC cxx_std_17)
target_include_directories(dashboard_image PRIVATE xboxllr/src/storage)
target_link_libraries(dashboard_image PRIVATE xboxllr_storage_core bcrypt)

add_executable(dashboard-import src/import_main.cpp)
target_link_libraries(dashboard-import PRIVATE dashboard_image)
target_link_options(dashboard-import PRIVATE $<$<CXX_COMPILER_ID:GNU>:-municode>)

find_package(SDL2 CONFIG REQUIRED)
add_executable(XboxDashboard WIN32 src/menu_launcher.cpp)
target_link_libraries(XboxDashboard PRIVATE dashboard_image SDL2::SDL2-static shell32)
target_link_options(XboxDashboard PRIVATE $<$<CXX_COMPILER_ID:GNU>:-municode;-static>)
set(RECOMP_UI_ROOT "${CMAKE_CURRENT_SOURCE_DIR}/recomp-ui")
include("${RECOMP_UI_ROOT}/recomp_ui.cmake")
recomp_target_launcher_ui(XboxDashboard CONSOLE all)
