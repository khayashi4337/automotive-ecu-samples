#include "ecu_reporter.h"
#include <fstream>
#include <iomanip>
#include <regex>
#include <sstream>

EcuMarkdownReporter::EcuMarkdownReporter(const std::string& output_path,
                                         const std::string& env_tag)
    : output_path_(output_path), env_tag_(env_tag) {}

void EcuMarkdownReporter::OnTestStart(const testing::TestInfo& /*info*/) {
    test_start_ = std::chrono::steady_clock::now();
}

void EcuMarkdownReporter::OnTestEnd(const testing::TestInfo& info) {
    auto elapsed = std::chrono::steady_clock::now() - test_start_;
    double ms = std::chrono::duration<double, std::milli>(elapsed).count();

    TestResult r;
    r.suite_name  = info.test_suite_name();
    r.test_name   = info.name();
    r.requirement_id = extract_req_id(info.name());
    r.passed      = info.result()->Passed();
    r.elapsed_ms  = ms;

    if (!r.passed && info.result()->Failed()) {
        const auto& part = info.result()->GetTestPartResult(0);
        r.failure_message = part.message();
    }
    results_.push_back(r);
}

void EcuMarkdownReporter::OnTestProgramEnd(const testing::UnitTest& unit_test) {
    write_report(unit_test);
}

std::string EcuMarkdownReporter::extract_req_id(const std::string& test_name) {
    // テスト名の [REQ-XXX] を抽出する。例: "CheckRPM_REQ001" → "REQ-001"
    std::smatch m;
    if (std::regex_search(test_name, m, std::regex(R"((REQ\d+))")))
        return m[1].str();
    return "-";
}

void EcuMarkdownReporter::write_report(const testing::UnitTest& unit_test) const {
    std::ofstream f(output_path_);
    if (!f.is_open()) {
        std::cerr << "[EcuMarkdownReporter] Cannot open report file: " << output_path_ << "\n";
        return;
    }

    int total   = unit_test.total_test_count();
    int passed  = unit_test.successful_test_count();
    int failed  = unit_test.failed_test_count();
    double total_ms = unit_test.elapsed_time();

    // ヘッダー
    f << "# ECU Test Report\n\n";
    f << "| Item | Value |\n|---|---|\n";
    f << "| Environment | " << env_tag_ << " |\n";
    f << "| Total | " << total << " |\n";
    f << "| Passed | " << passed << " |\n";
    f << "| Failed | " << failed << " |\n";
    f << "| Time (ms) | " << std::fixed << std::setprecision(1) << total_ms << " |\n\n";

    // 全体判定
    f << (failed == 0 ? "**Result: ✅ ALL PASSED**\n\n"
                      : "**Result: ❌ FAILED**\n\n");

    // スイート別サマリー
    f << "## Suite Summary\n\n";
    f << "| Suite | Tests | Passed | Failed |\n|---|---|---|---|\n";
    for (int i = 0; i < unit_test.total_test_suite_count(); ++i) {
        const auto* s = unit_test.GetTestSuite(i);
        f << "| " << s->name()
          << " | " << s->total_test_count()
          << " | " << s->successful_test_count()
          << " | " << s->failed_test_count() << " |\n";
    }

    // テスト詳細（要件IDつき）
    f << "\n## Test Details\n\n";
    f << "| Suite | Test | Requirement | Result | Time (ms) |\n"
         "|---|---|---|---|---|\n";
    for (const auto& r : results_) {
        f << "| " << r.suite_name
          << " | " << r.test_name
          << " | " << r.requirement_id
          << " | " << (r.passed ? "✅ PASS" : "❌ FAIL")
          << " | " << std::fixed << std::setprecision(2) << r.elapsed_ms << " |\n";
    }

    // 失敗詳細
    bool has_failure = false;
    for (const auto& r : results_) {
        if (!r.passed && !r.failure_message.empty()) {
            if (!has_failure) {
                f << "\n## Failure Details\n";
                has_failure = true;
            }
            f << "\n### " << r.suite_name << "." << r.test_name << "\n";
            f << "```\n" << r.failure_message << "\n```\n";
        }
    }
}
