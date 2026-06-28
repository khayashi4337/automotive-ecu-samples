#include <gtest/gtest.h>
#include "log_parser.h"

TEST(LogParserTest, ParseValidLine) {
    LogEntry e;
    ASSERT_TRUE(LogParser::parse_line("1.234 WARN ENGINE rpm=6700", e));
    EXPECT_DOUBLE_EQ(e.timestamp, 1.234);
    EXPECT_EQ(e.level, "WARN");
    EXPECT_EQ(e.channel, "ENGINE");
    EXPECT_TRUE(e.has_value);
    EXPECT_DOUBLE_EQ(e.value, 6700.0);
}

TEST(LogParserTest, SkipCommentLine) {
    LogEntry e;
    EXPECT_FALSE(LogParser::parse_line("# this is a comment", e));
}

TEST(LogParserTest, SkipEmptyLine) {
    LogEntry e;
    EXPECT_FALSE(LogParser::parse_line("", e));
}

TEST(LogParserTest, FilterByThreshold) {
    std::vector<LogEntry> entries;

    LogEntry e1; LogParser::parse_line("1.0 INFO ENGINE rpm=5000", e1);
    LogEntry e2; LogParser::parse_line("2.0 WARN ENGINE rpm=7200", e2);
    LogEntry e3; LogParser::parse_line("3.0 WARN BRAKE pressure=80", e3);
    entries = {e1, e2, e3};

    auto result = LogParser::filter_by_threshold(entries, "ENGINE", 6000.0);
    ASSERT_EQ(result.size(), 1u);
    EXPECT_DOUBLE_EQ(result[0].value, 7200.0);
}
