# 03 — CAN Frame Parser

CANフレームのバイナリペイロードを信号定義に基づいてデコードするC++ライブラリ＋CLIツール。

## Overview

```
入力: CAN フレーム (ID#DATA hex文字列 または .can ファイル)
出力: デコードされた信号名・値・単位
```

## Build

```bash
cmake -S .. -B ../build -G Ninja
cmake --build ../build --target can_parser_bin
```

## Usage

```bash
./build/03_can_parser/can_parser_bin 03_can_parser/sample.can
```

```
=== CAN Frame Decoder ===

Frame 0C1#1A005A00000000
  ENGINE_RPM       = 1664.00 rpm
  COOLANT_TEMP     = 50.00 degC
Frame 2B0#27100000000000
  VEHICLE_SPEED    = 100.00 km/h
[FFF#DEADBEEF00000000] → unknown ID
```

## Frame Format

```
ID#DATA
```

| フィールド | 説明 | 例 |
|---|---|---|
| `ID` | CAN ID (hex, 標準11bit または 拡張29bit) | `0C1` |
| `DATA` | ペイロード (hex, 最大8バイト=16文字) | `1A005A00000000` |

`.can` ファイルは1行1フレームの形式です。`#` 始まりはコメント。

## API

```cpp
#include "can_parser.h"

// 信号定義を登録したパーサーを取得
CanParser parser = make_sample_parser();

// 1行テキストをパース・デコード
auto signals = parser.parse_line("0C1#1A005A00000000");
for (const auto& sv : signals) {
    // sv.name, sv.value, sv.unit
}
```

### `SignalDef` 構造体

```cpp
struct SignalDef {
    std::string name;       // 信号名 (例: "ENGINE_RPM")
    std::string unit;       // 単位  (例: "rpm")
    uint8_t  start_byte;    // 開始バイト位置
    uint8_t  length_bytes;  // バイト長 (1 or 2)
    double   scale;         // 値 = raw * scale + offset
    double   offset;
    bool     big_endian;    // バイト順
};
```

### `CanParser` クラス

| メソッド | 説明 |
|---|---|
| `add_signal(id, sig)` | 信号定義を登録 |
| `decode(frame)` | フレームの全信号をデコード |
| `parse_line(line)` | テキスト1行 → パース → デコードを一括実行 |
| `parse_hex(id, data, frame)` | hex文字列 → `CanFrame` に変換（static） |

## Sample Signals (`make_sample_parser()`)

| CAN ID | 信号名 | バイト | Scale | Offset | 単位 |
|---|---|---|---|---|---|
| `0x0C1` | `ENGINE_RPM` | 0-1 | 0.25 | 0 | rpm |
| `0x0C1` | `COOLANT_TEMP` | 2 | 1.0 | -40 | degC |
| `0x1A0` | `BRAKE_PRESSURE` | 0-1 | 0.1 | 0 | kPa |
| `0x2B0` | `VEHICLE_SPEED` | 0-1 | 0.01 | 0 | km/h |

## Tests

```bash
cmake --build ../build --target CanParserTest
./build/03_can_parser/CanParserTest
```

| テスト名 | 内容 |
|---|---|
| `ParseHexFrame` | hex文字列 → `CanFrame` 変換（ID・DLC・data確認） |
| `DecodeEngineRPM` | `0x0C1` ENGINE_RPM デコード値確認 |
| `DecodeCoolantTemp` | `0x0C1` COOLANT_TEMP デコード値確認（offset=-40） |
| `DecodeVehicleSpeed` | `0x2B0` VEHICLE_SPEED デコード値確認 |
| `ParseLine` | `parse_line()` の一括パース確認 |
| `UnknownIdReturnsEmpty` | 未登録IDに対して空リストを返すことを確認 |
