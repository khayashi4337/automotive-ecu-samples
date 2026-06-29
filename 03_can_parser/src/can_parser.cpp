#include "can_parser.h"
#include <stdexcept>
#include <sstream>
#include <iomanip>
#include <cstring>

void CanParser::add_signal(uint32_t can_id, const SignalDef& sig) {
    signal_map_[can_id].push_back(sig);
}

bool CanParser::parse_hex(const std::string& id_hex,
                           const std::string& data_hex,
                           CanFrame& frame) {
    try {
        frame.id  = static_cast<uint32_t>(std::stoul(id_hex, nullptr, 16));
        frame.dlc = static_cast<uint8_t>(data_hex.size() / 2);
        if (frame.dlc > 8) return false;
        std::memset(frame.data, 0, sizeof(frame.data));
        for (uint8_t i = 0; i < frame.dlc; ++i) {
            frame.data[i] = static_cast<uint8_t>(
                std::stoul(data_hex.substr(i * 2, 2), nullptr, 16));
        }
        frame.is_extended = (frame.id > 0x7FF);
    } catch (...) {
        return false;
    }
    return true;
}

uint64_t CanParser::extract_raw(const CanFrame& frame, const SignalDef& sig) {
    // decode() が事前に境界チェックしているが、直接呼び出し時のクラッシュを防ぐ
    if (sig.start_byte + sig.length_bytes > frame.dlc) return 0;

    uint64_t raw = 0;
    if (sig.big_endian) {
        for (uint8_t i = 0; i < sig.length_bytes; ++i) {
            raw = (raw << 8) | frame.data[sig.start_byte + i];
        }
    } else {
        // リトルエンディアン
        for (uint8_t i = sig.length_bytes; i > 0; --i) {
            raw = (raw << 8) | frame.data[sig.start_byte + i - 1];
        }
    }
    return raw;
}

std::vector<SignalValue> CanParser::decode(const CanFrame& frame) const {
    std::vector<SignalValue> result;
    auto it = signal_map_.find(frame.id);
    if (it == signal_map_.end()) return result;

    for (const auto& sig : it->second) {
        if (sig.start_byte + sig.length_bytes > frame.dlc) continue;
        uint64_t raw = extract_raw(frame, sig);
        SignalValue sv;
        sv.name  = sig.name;
        sv.unit  = sig.unit;
        sv.value = raw * sig.scale + sig.offset;
        result.push_back(sv);
    }
    return result;
}

std::vector<SignalValue> CanParser::parse_line(const std::string& line) const {
    // 形式: "0C1#001AF4002B000000"
    auto sep = line.find('#');
    if (sep == std::string::npos) return {};
    CanFrame frame{};
    if (!parse_hex(line.substr(0, sep), line.substr(sep + 1), frame))
        return {};
    return decode(frame);
}

// サンプル用: よく使う信号定義を登録済みのパーサーを返す
CanParser make_sample_parser() {
    CanParser p;

    // CAN ID 0x0C1: エンジン情報
    // byte0-1: 回転数 (scale=0.25, unit=rpm)
    // byte2:   水温   (scale=1.0, offset=-40, unit=degC)
    p.add_signal(0x0C1, {"ENGINE_RPM",   "rpm",  0, 2, 0.25,  0.0,  true});
    p.add_signal(0x0C1, {"COOLANT_TEMP", "degC", 2, 1, 1.0,  -40.0, true});

    // CAN ID 0x1A0: ブレーキ情報
    // byte0-1: ブレーキ圧力 (scale=0.1, unit=kPa)
    p.add_signal(0x1A0, {"BRAKE_PRESSURE", "kPa", 0, 2, 0.1, 0.0, true});

    // CAN ID 0x2B0: 車速
    // byte0-1: 車速 (scale=0.01, unit=km/h)
    p.add_signal(0x2B0, {"VEHICLE_SPEED", "km/h", 0, 2, 0.01, 0.0, true});

    return p;
}
