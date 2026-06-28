cmake_minimum_required(VERSION 3.20)
project(ecu_portfolio CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

enable_testing()

add_subdirectory(01_log_parser)
add_subdirectory(02_gtest_reporter)
