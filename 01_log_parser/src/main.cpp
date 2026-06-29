#include "log_parser.h"
#include <iostream>

int main(int argc, char* argv[]) {
    if (argc < 2) {
        std::cerr << "Usage: log_parser <logfile>\n";
        return 1;
    }

    try {
        auto entries = LogParser::parse_file(argv[1]);
        // サンプル用固定値。ecu_eval_config.json の alert_channel/alert_threshold を変えても
        // このバイナリの結果は変わらない。Python 側のラベル表示のみ追従する。
        auto alerts  = LogParser::filter_by_threshold(entries, "ENGINE", 6000.0);

        std::cout << "=== ECU Log Parser ===\n";
        std::cout << "Total entries : " << entries.size() << "\n";
        std::cout << "ENGINE > 6000 : " << alerts.size() << "\n\n";

        for (const auto& e : alerts) {
            std::cout << "[" << e.timestamp << "] " << e.level
                      << " " << e.channel << " " << e.message << "\n";
        }
    } catch (const std::exception& ex) {
        std::cerr << "Error: " << ex.what() << "\n";
        return 1;
    }
    return 0;
}
