#
# Copyright (c) 2024 Nordic Semiconductor
#
# SPDX-License-Identifier: LicenseRef-Nordic-5-Clause
#

cmake_minimum_required(VERSION 3.20.0)
find_package(Zephyr REQUIRED HINTS $ENV{ZEPHYR_BASE})
project(nrf_connect_sdk_intermediate)

target_sources(app PRIVATE src/main.c)
target_sources(app PRIVATE src/bma400.c)

# Add CMSIS-NN source files
file(GLOB_RECURSE CMSIS_NN_SOURCES
    "CMSIS-NN/Source/*.c"
)

target_sources(app PRIVATE ${CMSIS_NN_SOURCES})

# Add CMSIS-NN include directories
target_include_directories(app PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}/include
    ${CMAKE_CURRENT_SOURCE_DIR}/include/NN
    ${CMAKE_CURRENT_SOURCE_DIR}/CMSIS-NN/Include
)