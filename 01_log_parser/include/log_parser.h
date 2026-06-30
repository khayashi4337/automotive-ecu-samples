#pragma once
#include <string>
#include <vector>

struct LogEntry {
    double timestamp = 0.0;
    std::string level;    // INFO / WARN / ERROR
    std::string channel;  // ECU channel name (e.g. "ENGINE", "BRAKE")
    std::string message;
    double value    = 0.0;
    bool has_value  = false;
};

class LogParser {
public:
    // 1行のログ文字列をパースしてLogEntryに変換する
    static bool parse_line(const std::string& line, LogEntry& entry);

    // ファイル全体を読み込んでエントリ一覧を返す
    static std::vector<LogEntry> parse_file(const std::string& filepath);

    // 閾値超過エントリだけを抽出する
    static std::vector<LogEntry> filter_by_threshold(
        const std::vector<LogEntry>& entries,
        const std::string& channel,
        double threshold);
};
