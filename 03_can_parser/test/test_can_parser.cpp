#include <gtest/gtest.h>
#include <algorithm>
#include "can_parser.h"

class CanParserTest : public ::testing::Test {
protected:
    CanParser parser = make_sample_parser();
};

// ──────────────── parse_hex ────────────────

TEST_F(CanParserTest, ParseHexFrame) {
    CanFrame f{};
    ASSERT_TRUE(CanParser::parse_hex("0C1", "68000000000000", f));
    EXPECT_EQ(f.id, 0x0C1u);
    EXPECT_EQ(f.dlc, 7u);
    EXPECT_EQ(f.data[0], 0x68);
}

// DLC が 8 を超えるデータは false を返すこと
TEST_F(CanParserTest, ParseHexOverMaxDlc) {
    CanFrame f{};
    EXPECT_FALSE(CanParser::parse_hex("0C1", "001122334455667788", f));  // 9バイト
}

// 不正な hex 文字が含まれる場合は false を返すこと
TEST_F(CanParserTest, ParseHexInvalidCharacter) {
    CanFrame f{};
    EXPECT_FALSE(CanParser::parse_hex("GGG", "0000", f));
}

// ID が 0x7FF 以下は標準フレーム（is_extended=false）
TEST_F(CanParserTest, ParseHexStandardId) {
    CanFrame f{};
    ASSERT_TRUE(CanParser::parse_hex("7FF", "00", f));
    EXPECT_FALSE(f.is_extended);
}

// ID が 0x800 以上は拡張フレーム（is_extended=true）
TEST_F(CanParserTest, ParseHexExtendedId) {
    CanFrame f{};
    ASSERT_TRUE(CanParser::parse_hex("1FFFFFFF", "00", f));
    EXPECT_TRUE(f.is_extended);
}

// ──────────────── decode / extract_raw ────────────────

TEST_F(CanParserTest, DecodeEngineRPM) {
    // raw = 0x1A00 = 6656, value = 6656 * 0.25 = 1664.0 rpm
    CanFrame f{};
    CanParser::parse_hex("0C1", "1A005000000000", f);
    auto signals = parser.decode(f);

    ASSERT_GE(signals.size(), 1u);
    auto it = std::find_if(signals.begin(), signals.end(),
        [](const SignalValue& s){ return s.name == "ENGINE_RPM"; });
    ASSERT_NE(it, signals.end());
    EXPECT_DOUBLE_EQ(it->value, 1664.0);
    EXPECT_EQ(it->unit, "rpm");
}

TEST_F(CanParserTest, DecodeCoolantTemp) {
    // byte2=0x5A=90, 90 * 1.0 + (-40) = 50 degC
    CanFrame f{};
    CanParser::parse_hex("0C1", "1A005A00000000", f);
    auto signals = parser.decode(f);

    auto it = std::find_if(signals.begin(), signals.end(),
        [](const SignalValue& s){ return s.name == "COOLANT_TEMP"; });
    ASSERT_NE(it, signals.end());
    EXPECT_DOUBLE_EQ(it->value, 50.0);
}

TEST_F(CanParserTest, DecodeVehicleSpeed) {
    // 0x2710 = 10000, 10000 * 0.01 = 100.00 km/h
    CanFrame f{};
    CanParser::parse_hex("2B0", "27100000000000", f);
    auto signals = parser.decode(f);

    ASSERT_EQ(signals.size(), 1u);
    EXPECT_NEAR(signals[0].value, 100.0, 0.01);
    EXPECT_EQ(signals[0].unit, "km/h");
}

// BRAKE_PRESSURE のデコード確認
// 0x1388 = 5000, 5000 * 0.1 = 500.0 kPa
TEST_F(CanParserTest, DecodeBrakePressure) {
    CanFrame f{};
    CanParser::parse_hex("1A0", "13880000000000", f);
    auto signals = parser.decode(f);

    ASSERT_EQ(signals.size(), 1u);
    EXPECT_EQ(signals[0].name, "BRAKE_PRESSURE");
    EXPECT_NEAR(signals[0].value, 500.0, 0.01);
    EXPECT_EQ(signals[0].unit, "kPa");
}

// 同一フレームに複数シグナルが含まれる場合は全てデコードされること
TEST_F(CanParserTest, DecodeMultipleSignalsInFrame) {
    // 0C1 フレームは ENGINE_RPM と COOLANT_TEMP の2シグナル
    CanFrame f{};
    CanParser::parse_hex("0C1", "1A005A00000000", f);
    auto signals = parser.decode(f);

    EXPECT_EQ(signals.size(), 2u);
    bool has_rpm  = std::any_of(signals.begin(), signals.end(),
        [](const SignalValue& s){ return s.name == "ENGINE_RPM"; });
    bool has_temp = std::any_of(signals.begin(), signals.end(),
        [](const SignalValue& s){ return s.name == "COOLANT_TEMP"; });
    EXPECT_TRUE(has_rpm);
    EXPECT_TRUE(has_temp);
}

// DLC が信号定義の範囲に満たない場合はシグナルをスキップすること（境界チェック）
TEST_F(CanParserTest, DecodeBoundaryShortFrame) {
    // ENGINE_RPM は byte0-1 が必要（dlc >= 2）
    // DLC=1 のフレームでは ENGINE_RPM と COOLANT_TEMP がスキップされる
    CanParser p;
    p.add_signal(0x100, {"SIG_2BYTE", "unit", 0, 2, 1.0, 0.0, true});

    CanFrame f{};
    CanParser::parse_hex("100", "AA", f);  // dlc=1
    auto signals = p.decode(f);
    EXPECT_TRUE(signals.empty());
}

// リトルエンディアンの信号が正しくデコードされること
TEST_F(CanParserTest, DecodeLittleEndian) {
    CanParser p;
    // byte0=0xAA byte1=0xBB → LE raw = 0xBBAA
    p.add_signal(0x200, {"LE_SIG", "unit", 0, 2, 1.0, 0.0, false});

    CanFrame f{};
    CanParser::parse_hex("200", "AABB000000000000", f);
    auto signals = p.decode(f);

    ASSERT_EQ(signals.size(), 1u);
    EXPECT_DOUBLE_EQ(signals[0].value, static_cast<double>(0xBBAA));
}

// ──────────────── parse_line ────────────────

TEST_F(CanParserTest, ParseLine) {
    auto signals = parser.parse_line("2B0#27100000000000");
    ASSERT_EQ(signals.size(), 1u);
    EXPECT_NEAR(signals[0].value, 100.0, 0.01);
}

// '#' がない行は空リストを返すこと
TEST_F(CanParserTest, ParseLineMissingHash) {
    auto signals = parser.parse_line("0C11A005A00000000");
    EXPECT_TRUE(signals.empty());
}

// データ部分が空の行は空リストを返すこと
TEST_F(CanParserTest, ParseLineEmptyData) {
    auto signals = parser.parse_line("0C1#");
    // DLC=0 → 信号範囲チェックで全スキップ
    EXPECT_TRUE(signals.empty());
}

// 未登録 ID は空リストを返すこと
TEST_F(CanParserTest, UnknownIdReturnsEmpty) {
    auto signals = parser.parse_line("FFF#0000000000000000");
    EXPECT_TRUE(signals.empty());
}

// offset が適用されること（COOLANT_TEMP: raw=0 → 0 * 1.0 + (-40) = -40 degC）
TEST_F(CanParserTest, DecodeOffsetApplied) {
    CanFrame f{};
    CanParser::parse_hex("0C1", "00000000000000", f);
    auto signals = parser.decode(f);

    auto it = std::find_if(signals.begin(), signals.end(),
        [](const SignalValue& s){ return s.name == "COOLANT_TEMP"; });
    ASSERT_NE(it, signals.end());
    EXPECT_DOUBLE_EQ(it->value, -40.0);
}
