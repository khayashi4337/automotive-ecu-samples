find_package(GTest REQUIRED)

include_directories(include)

add_library(ecu_reporter src/ecu_reporter.cpp)
target_link_libraries(ecu_reporter GTest::gtest)

add_executable(sample_ecu_test test/sample_ecu_test.cpp)
target_link_libraries(sample_ecu_test ecu_reporter GTest::gtest)

add_test(NAME SampleEcuTest COMMAND sample_ecu_test)
