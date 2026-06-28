#pragma once
#include <cstdint>
#include <string>
#include <vector>
#include <unordered_map>

// CANフレーム: ID + 最大8バイトのデータ
struct CanFrame {
    uint32_t id;           // CAN ID (11bit standard or 29bit extended)
    uint8_t  dlc;          // Data Length Code (0-8)
    uint8_t  data[8];      // ペイロード
    bool     is_extended;  // 29bit拡張IDかどうか
};

// 信号定義: CANデータのどこを読めば何の値か
struct SignalDef {
    std::string name;       // 例: "ENGINE_RPM"
    std::string unit;       // 例: "rpm"
    uint8_t  start_byte;    // 開始バイト位置
    uint8_t  length_bytes;  // バイト長 (1 or 2)
    double   scale;         // 値 = raw * scale + offset
    double   offset;
    bool     big_endian;    // バイト順
};

// デコード済みの信号値
struct SignalValue {
    std::string name;
    std::string unit;
    double value;
};

// CANフレームの解析器
class CanParser {
public:
    // 信号定義を登録する (CAN ID → 信号リスト)
    void add_signal(uint32_t can_id, const SignalDef& sig);

    // バイナリ文字列 "1A2B3C..." をCanFrameに変換する
    static bool parse_hex(const std::string& id_hex,
                          const std::string& data_hex,
                          CanFrame& frame);

    // フレームの全信号をデコードして返す
    std::vector<SignalValue> decode(const CanFrame& frame) const;

    // 1行テキスト "ID#DATA" をパースしてデコードまで一括で行う
    // 形式例: "0C1#001AF4002B000000"
    std::vector<SignalValue> parse_line(const std::string& line) const;

private:
    static uint64_t extract_raw(const CanFrame& frame, const SignalDef& sig);

    // CAN ID → 信号定義リスト
    std::unordered_map<uint32_t, std::vector<SignalDef>> signal_map_;
};

// 車載ECUでよく使う信号定義をあらかじめ登録したパーサーを返す
CanParser make_sample_parser();
