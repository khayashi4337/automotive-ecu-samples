#include "log_parser.h"
#include <fstream>
#include <sstream>
#include <stdexcept>

// ログフォーマット: "timestamp LEVEL CHANNEL message [value]"
// 例: "1.234 WARN ENGINE rpm=6700"
bool LogParser::parse_line(const std::string& line, LogEntry& entry) {
    if (line.empty() || line[0] == '#') return false;

    std::istringstream ss(line);
    ss >> entry.timestamp >> entry.level >> entry.channel;
    if (ss.fail()) return false;

    std::getline(ss, entry.message);
    if (!entry.message.empty() && entry.message[0] == ' ')
        entry.message = entry.message.substr(1);

    // "key=value" 形式の数値を抽出
    auto eq = entry.message.find('=');
    if (eq != std::string::npos) {
        try {
            entry.value = std::stod(entry.message.substr(eq + 1));
            entry.has_value = true;
        } catch (...) {
            entry.has_value = false;
        }
    } else {
        entry.has_value = false;
        entry.value = 0.0;
    }
    return true;
}

std::vector<LogEntry> LogParser::parse_file(const std::string& filepath) {
    std::ifstream f(filepath);
    if (!f.is_open()) throw std::runtime_error("Cannot open: " + filepath);

    std::vector<LogEntry> entries;
    std::string line;
    while (std::getline(f, line)) {
        LogEntry e;
        if (parse_line(line, e)) entries.push_back(e);
    }
    return entries;
}

std::vector<LogEntry> LogParser::filter_by_threshold(
    const std::vector<LogEntry>& entries,
    const std::string& channel,
    double threshold)
{
    std::vector<LogEntry> result;
    for (const auto& e : entries) {
        if (e.channel == channel && e.has_value && e.value > threshold)
            result.push_back(e);
    }
    return result;
}
