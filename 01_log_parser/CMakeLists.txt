find_package(GTest REQUIRED)

include_directories(include)

add_library(log_parser src/log_parser.cpp)

add_executable(log_parser_bin src/main.cpp)
target_link_libraries(log_parser_bin log_parser)

add_executable(test_log_parser test/test_log_parser.cpp)
target_link_libraries(test_log_parser log_parser GTest::gtest GTest::gtest_main)
add_test(NAME LogParserTest COMMAND test_log_parser)
