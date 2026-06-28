#include "can_parser.h"
#include <iostream>
#include <iomanip>
#include <fstream>
#include <string>

int main(int argc, char* argv[]) {
    auto parser = make_sample_parser();

    // 引数なし: 標準入力から読む。ファイル指定あり: ファイルから読む
    std::istream* in = &std::cin;
    std::ifstream file;
    if (argc >= 2) {
        file.open(argv[1]);
        if (!file.is_open()) {
            std::cerr << "Cannot open: " << argv[1] << "\n";
            return 1;
        }
        in = &file;
    }

    std::cout << "=== CAN Frame Decoder ===\n\n";
    std::string line;
    while (std::getline(*in, line)) {
        if (line.empty() || line[0] == '#') continue;
        auto signals = parser.parse_line(line);
        if (signals.empty()) {
            std::cout << "[" << line << "] → unknown ID\n";
            continue;
        }
        std::cout << "Frame " << line << "\n";
        for (const auto& sv : signals) {
            std::cout << "  " << std::left << std::setw(16) << sv.name
                      << " = " << std::fixed << std::setprecision(2)
                      << sv.value << " " << sv.unit << "\n";
        }
    }
    return 0;
}
