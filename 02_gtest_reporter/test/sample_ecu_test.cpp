#include "ecu_reporter.h"
#include <gtest/gtest.h>
#include <cstdlib>

// ---- ECUっぽいサンプルテスト（SiLS想定） ----
// テスト名末尾の _REQxxx が要件IDとしてレポートに記録される

// エンジン制御テスト
TEST(EngineTest, NormalRPM_REQ001) {
    int rpm = 3000;
    EXPECT_GE(rpm, 0);
    EXPECT_LE(rpm, 8000);
}

TEST(EngineTest, OverRPM_REQ002) {
    int rpm = 9500;
    EXPECT_LE(rpm, 8000) << "RPM exceeded maximum limit";
}

// ブレーキ制御テスト
TEST(BrakeTest, NormalPressure_REQ010) {
    double pressure_kpa = 450.0;
    EXPECT_GT(pressure_kpa, 0.0);
    EXPECT_LT(pressure_kpa, 1000.0);
}

TEST(BrakeTest, EmergencyBrake_REQ011) {
    double pressure_kpa = 950.0;
    EXPECT_GE(pressure_kpa, 800.0) << "Emergency brake pressure too low";
}

// 温度センサーテスト
TEST(ThermalTest, CoolantTemp_REQ020) {
    double temp_c = 88.0;
    EXPECT_GE(temp_c, 70.0);
    EXPECT_LE(temp_c, 105.0);
}

// ---- main: レポーターを登録してテスト実行 ----
int main(int argc, char** argv) {
    testing::InitGoogleTest(&argc, argv);

    // 環境変数 ECU_TEST_ENV で SiLS/HiLS/実車 を切り替え
    const char* env = std::getenv("ECU_TEST_ENV");
    std::string env_tag = env ? env : "SiLS";

    auto& listeners = testing::UnitTest::GetInstance()->listeners();
    listeners.Append(new EcuMarkdownReporter("ecu_test_report.md", env_tag));

    return RUN_ALL_TESTS();
}
