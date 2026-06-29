# 02 — GTest Reporter

GTestの `TestEventListener` API を使い、テスト結果＋要件IDを Markdown レポートとして自動生成するC++ライブラリ。

## Overview

```
入力: GTestテスト実行（テスト名に _REQxxx を埋め込む）
出力: ecu_test_report.md（要件トレーサビリティ付き）
```

## Design

`EcuMarkdownReporter` は `testing::EmptyTestEventListener` を継承し、テスト開始・終了・プログラム終了のイベントを受け取ってレポートを生成します。テスト名末尾の `_REQxxx` パターンを自動抽出して要件IDとして記録します。

```cpp
// テスト名に要件IDを埋め込む
TEST(EngineTest, OverRPM_REQ002) {
    int rpm = 9500;
    EXPECT_LE(rpm, 8000) << "RPM exceeded maximum limit";
}
```

## Build

```bash
cmake -S .. -B ../build -G Ninja
cmake --build ../build --target sample_ecu_test
```

## Usage

```bash
# SiLS環境でテスト実行
ECU_TEST_ENV=SiLS ./build/02_gtest_reporter/sample_ecu_test
```

出力ファイル: `build/02_gtest_reporter/ecu_test_report.md`

```markdown
| Suite      | Test               | Requirement | Result  | Time (ms) |
|---|---|---|---|---|
| EngineTest | NormalRPM_REQ001   | REQ001      | ✅ PASS | 0.01      |
| EngineTest | OverRPM_REQ002     | REQ002      | ❌ FAIL | 0.24      |
```

## API

```cpp
#include "ecu_reporter.h"

// main() でリスナーを登録するだけ
auto& listeners = testing::UnitTest::GetInstance()->listeners();
listeners.Append(new EcuMarkdownReporter("ecu_test_report.md", "SiLS"));
RUN_ALL_TESTS();
```

### コンストラクタ

```cpp
EcuMarkdownReporter(const std::string& output_path,
                    const std::string& env_tag = "SiLS");
```

| 引数 | 説明 |
|---|---|
| `output_path` | レポートの出力先ファイルパス |
| `env_tag` | 評価環境タグ（`SiLS` / `HiLS` / `実車` など自由文字列） |

### 要件ID抽出ルール

テスト名末尾の `REQ\d+` パターンを抽出します。

| テスト名 | 抽出される要件ID |
|---|---|
| `CheckRPM_REQ001` | `REQ001` |
| `BrakeTest_REQ010` | `REQ010` |
| `SimpleTest` | `-`（なし） |

## Report Structure

生成される Markdown の構成:

1. **ヘッダー** — 環境タグ・合計/合格/失敗数・実行時間
2. **全体判定** — ✅ ALL PASSED / ❌ FAILED
3. **Suite Summary** — スイート別の集計表
4. **Test Details** — テストごとの要件ID・結果・時間
5. **Failure Details** — 失敗したテストのエラーメッセージ

## Sample Tests

`sample_ecu_test.cpp` に5件のサンプルテストが含まれています。

| テスト | 要件ID | 説明 | 期待結果 |
|---|---|---|---|
| `NormalRPM_REQ001` | REQ001 | 正常RPM範囲チェック | PASS |
| `OverRPM_REQ002` | REQ002 | RPM超過検出（意図的失敗） | FAIL |
| `NormalPressure_REQ010` | REQ010 | 正常ブレーキ圧チェック | PASS |
| `EmergencyBrake_REQ011` | REQ011 | 緊急ブレーキ圧チェック | PASS |
| `CoolantTemp_REQ020` | REQ020 | 冷却水温チェック | PASS |

`OverRPM_REQ002` は意図的な失敗です（RPM超過を検出できることのデモ）。
