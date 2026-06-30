#include <gtest/gtest.h>
#include <fstream>
#include <cstdio>
#include "log_parser.h"

// ──────────────── parse_line ────────────────

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

// key=value がない行は has_value=false になること
TEST(LogParserTest, ParseLineNoValue) {
    LogEntry e;
    ASSERT_TRUE(LogParser::parse_line("2.0 INFO ENGINE status_ok", e));
    EXPECT_FALSE(e.has_value);
    EXPECT_EQ(e.message, "status_ok");
}

// value 部分が数値でない場合は has_value=false になること
TEST(LogParserTest, ParseLineNonNumericValue) {
    LogEntry e;
    ASSERT_TRUE(LogParser::parse_line("1.0 INFO ENGINE state=running", e));
    EXPECT_FALSE(e.has_value);
}

// 行末 \r が取り除かれること（CRLF ファイルを読んだとき）
TEST(LogParserTest, ParseLineCrlfStripped) {
    LogEntry e;
    ASSERT_TRUE(LogParser::parse_line("0.5 WARN BRAKE pressure=95\r", e));
    EXPECT_EQ(e.channel, "BRAKE");
    EXPECT_TRUE(e.has_value);
    EXPECT_DOUBLE_EQ(e.value, 95.0);
    // message の末尾に \r が残っていないこと
    EXPECT_TRUE(e.message.empty() || e.message.back() != '\r');
}

// INFO レベルの行もパースできること
TEST(LogParserTest, ParseLevelInfo) {
    LogEntry e;
    ASSERT_TRUE(LogParser::parse_line("0.0 INFO ENGINE rpm=1200", e));
    EXPECT_EQ(e.level, "INFO");
}

// ERROR レベルの行もパースできること
TEST(LogParserTest, ParseLevelError) {
    LogEntry e;
    ASSERT_TRUE(LogParser::parse_line("1.5 ERROR ENGINE rpm=7800", e));
    EXPECT_EQ(e.level, "ERROR");
    EXPECT_DOUBLE_EQ(e.value, 7800.0);
}

// フィールドが不足している行（timestamp だけなど）は false を返すこと
TEST(LogParserTest, ParseInsufficientFields) {
    LogEntry e;
    EXPECT_FALSE(LogParser::parse_line("1.0", e));
}

// ──────────────── filter_by_threshold ────────────────

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

// 閾値を超えるエントリがない場合は空リストを返すこと
TEST(LogParserTest, FilterEmptyResult) {
    std::vector<LogEntry> entries;
    LogEntry e; LogParser::parse_line("1.0 INFO ENGINE rpm=3000", e);
    entries = {e};

    auto result = LogParser::filter_by_threshold(entries, "ENGINE", 6000.0);
    EXPECT_TRUE(result.empty());
}

// 複数エントリが閾値超過の場合は全て返すこと
TEST(LogParserTest, FilterMultipleMatches) {
    std::vector<LogEntry> entries;
    LogEntry e1; LogParser::parse_line("1.0 WARN ENGINE rpm=6200", e1);
    LogEntry e2; LogParser::parse_line("2.0 ERROR ENGINE rpm=7800", e2);
    LogEntry e3; LogParser::parse_line("3.0 WARN ENGINE rpm=6500", e3);
    entries = {e1, e2, e3};

    auto result = LogParser::filter_by_threshold(entries, "ENGINE", 6000.0);
    ASSERT_EQ(result.size(), 3u);
}

// 別チャンネルのエントリはフィルタされないこと
TEST(LogParserTest, FilterChannelIsolation) {
    std::vector<LogEntry> entries;
    LogEntry e1; LogParser::parse_line("1.0 WARN ENGINE rpm=7000", e1);
    LogEntry e2; LogParser::parse_line("2.0 WARN BRAKE pressure=800", e2);
    entries = {e1, e2};

    // ENGINE チャンネルだけが対象
    auto result = LogParser::filter_by_threshold(entries, "ENGINE", 6000.0);
    ASSERT_EQ(result.size(), 1u);
    EXPECT_EQ(result[0].channel, "ENGINE");
}

// 閾値ちょうどの値はフィルタされること（> であり >= ではない）
TEST(LogParserTest, FilterExactThresholdNotIncluded) {
    std::vector<LogEntry> entries;
    LogEntry e; LogParser::parse_line("1.0 WARN ENGINE rpm=6000", e);
    entries = {e};

    auto result = LogParser::filter_by_threshold(entries, "ENGINE", 6000.0);
    EXPECT_TRUE(result.empty());
}

// has_value=false のエントリはフィルタされること
TEST(LogParserTest, FilterSkipsNoValueEntry) {
    std::vector<LogEntry> entries;
    LogEntry e; LogParser::parse_line("1.0 WARN ENGINE status_ok", e);
    entries = {e};

    auto result = LogParser::filter_by_threshold(entries, "ENGINE", 0.0);
    EXPECT_TRUE(result.empty());
}

// ──────────────── parse_file ────────────────

// 存在しないファイルは例外をスローすること
TEST(LogParserTest, ParseFileNotFound) {
    EXPECT_THROW(LogParser::parse_file("nonexistent_file.log"),
                 std::runtime_error);
}

// 有効なファイルを渡すと全エントリを返すこと（正常系）
TEST(LogParserTest, ParseFileValidContent) {
    const char* tmp = "test_parse_file_tmp.log";
    {
        std::ofstream f(tmp);
        f << "1.0 WARN ENGINE rpm=6200\n";
        f << "# comment line\n";
        f << "\n";
        f << "2.0 INFO BRAKE pressure=50\n";
    }

    auto entries = LogParser::parse_file(tmp);
    std::remove(tmp);

    ASSERT_EQ(entries.size(), 2u);
    EXPECT_DOUBLE_EQ(entries[0].timestamp, 1.0);
    EXPECT_EQ(entries[0].channel, "ENGINE");
    EXPECT_TRUE(entries[0].has_value);
    EXPECT_DOUBLE_EQ(entries[0].value, 6200.0);
    EXPECT_DOUBLE_EQ(entries[1].timestamp, 2.0);
    EXPECT_EQ(entries[1].channel, "BRAKE");
}
