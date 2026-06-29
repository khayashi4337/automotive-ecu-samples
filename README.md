# automotive-ecu-samples

**ECU evaluation tools and SiLS samples — C++17 / CMake / GTest / Python**

車載ECUソフトウェアの評価業務を想定した小規模ツール群です。
SiLS（Software in the Loop Simulation）環境での動作を前提に設計しています。

---

## Tools

| # | Tool | Description |
|---|---|---|
| 01 | [log_parser](01_log_parser/) | ECUログをパースして閾値超過を検出・レポート化 |
| 02 | [gtest_reporter](02_gtest_reporter/) | GTestのイベントを直接受け取り、要件IDつきMarkdownレポートを生成 |
| 03 | [can_parser](03_can_parser/) | CANフレームをバイナリからデコードして信号値に変換 |
| — | [ecu_eval.py](ecu_eval.py) | 全ツールを一括実行して統合レポートを生成するPythonスクリプト |

---

## Tech Stack

| | |
|---|---|
| Language | C++17, Python 3 |
| Build | CMake 4 + Ninja |
| Test | GoogleTest 1.17 |
| Compiler | GCC 16 (MinGW-w64 via MSYS2) |
| Platform | Windows 11 / Linux compatible |

---

## Setup

### Prerequisites

- [MSYS2](https://www.msys2.org/) with MinGW-w64 toolchain
- CMake ≥ 3.20
- Python ≥ 3.10

### Install dependencies (MSYS2)

```bash
pacman -S --noconfirm \
  mingw-w64-x86_64-gcc \
  mingw-w64-x86_64-cmake \
  mingw-w64-x86_64-ninja \
  mingw-w64-x86_64-gtest
```

### Build

```bash
cmake -S . -B build -G Ninja \
  -DCMAKE_CXX_COMPILER=g++ \
  -DCMAKE_BUILD_TYPE=Release
cmake --build build
```

### Run all tests

```bash
cmake --build build --target test
```

---

## Usage

### Run all tools at once (recommended)

```bash
# SiLS環境で全ツールを実行し統合レポートを生成
python ecu_eval.py --env SiLS

# HiLS環境
python ecu_eval.py --env HiLS
```

出力: `ecu_eval_report.md`

---

### 01 — ECU Log Parser

ECUログファイルを読み込み、指定チャンネルの閾値超過エントリを抽出します。

```bash
./build/01_log_parser/log_parser_bin 01_log_parser/sample.log
```

```
=== ECU Log Parser ===
Total entries : 7
ENGINE > 6000 : 2

[1] WARN ENGINE rpm=6200
[1.5] ERROR ENGINE rpm=7800
```

**Log format:**
```
# timestamp LEVEL CHANNEL key=value
1.000 WARN ENGINE rpm=6200
```

---

### 02 — GTest Reporter

GTestの `TestEventListener` API を使ったC++ネイティブ実装。
テスト名末尾の `_REQxxx` を自動抽出して要件IDとの対応を記録します。

```cpp
// テスト名に要件IDを埋め込む
TEST(EngineTest, OverRPM_REQ002) { ... }
```

```bash
ECU_TEST_ENV=SiLS ./build/02_gtest_reporter/sample_ecu_test
```

出力: `ecu_test_report.md`

| Suite | Test | Requirement | Result | Time (ms) |
|---|---|---|---|---|
| EngineTest | NormalRPM_REQ001 | REQ001 | ✅ PASS | 0.01 |
| EngineTest | OverRPM_REQ002 | REQ002 | ❌ FAIL | 0.29 |

---

### 03 — CAN Frame Parser

CANフレームのバイナリを信号定義に基づいてデコードします。
`make_sample_parser()` に ENGINE_RPM / COOLANT_TEMP / BRAKE_PRESSURE / VEHICLE_SPEED を定義済みです。

```bash
./build/03_can_parser/can_parser_bin 03_can_parser/sample.can
```

```
Frame 0C1#1A005A00000000
  ENGINE_RPM       = 1664.00 rpm
  COOLANT_TEMP     = 50.00 degC
Frame 2B0#27100000000000
  VEHICLE_SPEED    = 100.00 km/h
```

**Frame format:** `ID#DATA` (hex, e.g. `0C1#1A005A00000000`)

---

## Evaluation Flow

```
SiLS Environment
  │
  ├─ 01 Log Parser     ──→ 閾値超過の検出
  ├─ 02 GTest Reporter ──→ テスト結果 + 要件トレーサビリティ
  └─ 03 CAN Parser     ──→ 通信フレームの信号値確認
            │
            ▼
      ecu_eval.py  ──→  ecu_eval_report.md  (統合評価レポート)
```

---

## Directory Structure

```
automotive-ecu-samples/
├── 01_log_parser/
│   ├── include/log_parser.h
│   ├── src/
│   ├── test/
│   └── sample.log
├── 02_gtest_reporter/
│   ├── include/ecu_reporter.h
│   ├── src/
│   └── test/
├── 03_can_parser/
│   ├── include/can_parser.h
│   ├── src/
│   ├── test/
│   └── sample.can
├── ecu_eval.py
└── CMakeLists.txt
```

---

## Test Results

```
LogParserTest   : 4/4  PASSED
SampleEcuTest   : 4/5  PASSED  (1 intentional failure: OverRPM_REQ002)
CanParserTest   : 6/6  PASSED
```

`OverRPM_REQ002` は意図的な失敗です（RPM超過を検出できることのデモ）。

---

## Author

Kuniyuki Hayashi — [khayashi4337@gmail.com](mailto:khayashi4337@gmail.com)
