#include <gtest/gtest.h>
#include <algorithm>
#include "can_parser.h"

class CanParserTest : public ::testing::Test {
protected:
    CanParser parser = make_sample_parser();
};

TEST_F(CanParserTest, ParseHexFrame) {
    CanFrame f{};
    ASSERT_TRUE(CanParser::parse_hex("0C1", "68000000000000", f));
    EXPECT_EQ(f.id, 0x0C1u);
    EXPECT_EQ(f.dlc, 7u);
    EXPECT_EQ(f.data[0], 0x68);
}

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

TEST_F(CanParserTest, ParseLine) {
    auto signals = parser.parse_line("2B0#27100000000000");
    ASSERT_EQ(signals.size(), 1u);
    EXPECT_NEAR(signals[0].value, 100.0, 0.01);
}

TEST_F(CanParserTest, UnknownIdReturnsEmpty) {
    auto signals = parser.parse_line("FFF#0000000000000000");
    EXPECT_TRUE(signals.empty());
}
