#pragma once
#include <gtest/gtest.h>
#include <chrono>
#include <string>
#include <vector>

struct TestResult {
    std::string suite_name;
    std::string test_name;
    std::string requirement_id;  // テスト名の REQ\d+ パターン ("REQ001") から抽出
    bool passed;
    double elapsed_ms;
    std::string failure_message;
};

// GTestのイベントを直接受け取りMarkdownレポートを生成する
class EcuMarkdownReporter : public testing::EmptyTestEventListener {
public:
    // output_path: レポートの出力先, env_tag: "SiLS" / "HiLS" / "実車"
    explicit EcuMarkdownReporter(const std::string& output_path,
                                 const std::string& env_tag = "SiLS");

    void OnTestStart(const testing::TestInfo& info) override;
    void OnTestEnd(const testing::TestInfo& info) override;
    void OnTestProgramEnd(const testing::UnitTest& unit_test) override;

private:
    static std::string extract_req_id(const std::string& test_name);
    void write_report(const testing::UnitTest& unit_test) const;

    std::string output_path_;
    std::string env_tag_;
    std::vector<TestResult> results_;
    std::chrono::steady_clock::time_point test_start_;
};
