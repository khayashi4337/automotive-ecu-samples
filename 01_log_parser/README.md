# 01 — ECU Log Parser

ECUログファイルをパースし、指定チャンネルの閾値超過エントリを抽出するC++ライブラリ＋CLIツール。

## Overview

```
入力: テキストログファイル (timestamp LEVEL CHANNEL key=value 形式)
出力: 閾値超過エントリの一覧とサマリー
```

## Build

```bash
cmake -S .. -B ../build -G Ninja
cmake --build ../build --target log_parser_bin
```

## Usage

```bash
./build/01_log_parser/log_parser_bin 01_log_parser/sample.log
```

```
=== ECU Log Parser ===
Total entries : 7
ENGINE > 6000 : 2

[1.5] WARN ENGINE rpm=6200
[2.0] ERROR ENGINE rpm=7800
```

## Log Format

```
# コメント行（スキップ）
timestamp  LEVEL  CHANNEL  key=value
1.234      WARN   ENGINE   rpm=6700
```

| フィールド | 型 | 説明 |
|---|---|---|
| `timestamp` | double | 経過時間（秒） |
| `LEVEL` | string | `INFO` / `WARN` / `ERROR` |
| `CHANNEL` | string | ECUチャンネル名（例: `ENGINE`, `BRAKE`） |
| `key=value` | string | 任意のキーと数値 |

## API

```cpp
#include "log_parser.h"

// ファイル全体をパース
std::vector<LogEntry> entries = LogParser::parse_file("sample.log");

// 閾値超過エントリを抽出
auto alerts = LogParser::filter_by_threshold(entries, "ENGINE", 6000.0);
```

### `LogEntry` 構造体

| フィールド | 型 | 説明 |
|---|---|---|
| `timestamp` | double | タイムスタンプ |
| `level` | string | ログレベル |
| `channel` | string | チャンネル名 |
| `message` | string | メッセージ本文 |
| `value` | double | 抽出された数値（`has_value` が true のとき有効） |
| `has_value` | bool | 数値が取得できたか |

## Tests

```bash
cmake --build ../build --target LogParserTest
./build/01_log_parser/LogParserTest
```

| テスト名 | 内容 |
|---|---|
| `ParseValidLine` | 正常行のパース（timestamp / level / channel / value） |
| `SkipCommentLine` | `#` 始まりの行をスキップ |
| `SkipEmptyLine` | 空行をスキップ |
| `FilterByThreshold` | 閾値超過フィルタ（チャンネル絞り込み込み） |
