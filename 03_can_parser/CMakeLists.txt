find_package(GTest REQUIRED)

include_directories(include)

add_library(can_parser src/can_parser.cpp)

add_executable(can_parser_bin src/main.cpp)
target_link_libraries(can_parser_bin can_parser)

add_executable(test_can_parser test/test_can_parser.cpp)
target_link_libraries(test_can_parser can_parser GTest::gtest GTest::gtest_main)
add_test(NAME CanParserTest COMMAND test_can_parser)
