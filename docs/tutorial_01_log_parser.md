# チュートリアル 01 — ECU ログパーサー

> **対象読者:** C++ を読んだことがない。ログファイルとは何かも曖昧。そこからスタートする人向け。

---

## 1. まず「何をするツールか」を理解する

### ECU とログって何？

車には **ECU（Electronic Control Unit）** という小型コンピュータが何十個も入っています。エンジンを制御するECU、ブレーキを制御するECU、など役割ごとに分かれています。

これらのECUは動きながら「今エンジンが何回転か」「ブレーキ圧力はどれくらいか」といった情報を**ログ（記録）**として書き出します。

```
1.000 WARN ENGINE rpm=6200
```

これが1行のログです。「1.000秒時点で、ENGINEという部品が、警告（WARN）を出していて、回転数（rpm）が6200だった」という意味です。

### このツールが解く問題

ログは何百行・何千行と積み重なります。その中から「エンジン回転数が6000を超えた行だけ取り出したい」といった作業を、人間が目で探すのは大変です。

このツールはその抽出を自動でやってくれます。

---

## 2. サンプルのログファイルを読んでみよう

`01_log_parser/sample.log` を開いてください。

```
# ECU Sample Log - SiLS test data
0.000 INFO ENGINE rpm=1200
0.500 INFO ENGINE rpm=3500
1.000 WARN ENGINE rpm=6200
1.500 ERROR ENGINE rpm=7800
2.000 INFO BRAKE pressure=45
2.500 WARN BRAKE pressure=95
3.000 INFO ENGINE rpm=4100
```

各行の構造はこうなっています：

```
[時刻（秒）] [重大度] [部品名] [測定値=数値]
```

| 重大度 | 意味 |
|---|---|
| INFO | 正常な情報 |
| WARN | 注意（異常ではないが気をつけよう） |
| ERROR | 異常発生 |

`#` で始まる行はコメント（メモ）です。プログラムは無視します。

---

## 3. C++ の基本的な読み方

C++ を読んだことがない人向けに、最低限の知識を整理します。

### 構造体（struct）＝ データの入れ物

```cpp
struct LogEntry {
    double timestamp = 0.0;  // 時刻（秒）
    std::string level;       // "INFO" / "WARN" / "ERROR"
    std::string channel;     // "ENGINE" / "BRAKE"
    std::string message;     // "rpm=6200" のような文字列全体
    double value    = 0.0;   // 6200.0 のような数値（あれば）
    bool has_value  = false; // 数値が取れたかどうか
};
```

`struct` は「データをまとめた箱」です。1行のログを読んだら、この箱にデータを詰め込みます。

- `double` → 小数を扱える数値の型
- `std::string` → 文字列の型（`std::` は「標準ライブラリの」という意味）
- `bool` → true（正しい）か false（正しくない）の2択

### 関数（function）＝ 処理のまとまり

```cpp
bool LogParser::parse_line(const std::string& line, LogEntry& entry) {
    // ...
}
```

- 最初の `bool` は「この関数が true か false を返す」という宣言
- `const std::string& line` は「1行のテキストを受け取る」という意味
- `LogEntry& entry` は「パース結果を書き込む箱を受け取る」という意味（`&` は「参照渡し」＝元の変数を直接書き換える）

---

## 4. コアの実装を読んでみよう

`01_log_parser/src/log_parser.cpp` を開きます。

### parse_line 関数（1行を分解する）

```cpp
bool LogParser::parse_line(const std::string& line, LogEntry& entry) {
    // ① コメント行と空行をスキップ
    if (line.empty() || line[0] == '#') return false;

    // ② スペース区切りで3つのフィールドを読む
    std::istringstream ss(line);
    ss >> entry.timestamp >> entry.level >> entry.channel;
    if (ss.fail()) return false;

    // ③ 残りの文字列（"rpm=6200" の部分）を取り出す
    std::getline(ss, entry.message);
    if (!entry.message.empty() && entry.message[0] == ' ')
        entry.message = entry.message.substr(1); // 先頭のスペースを除去

    // ④ "=" が含まれていれば右辺を数値として読む
    auto eq = entry.message.find('=');
    if (eq != std::string::npos) {
        try {
            entry.value = std::stod(entry.message.substr(eq + 1));
            entry.has_value = true;
        } catch (const std::invalid_argument&) {
            entry.has_value = false;  // 数値でなければ false のまま
        } catch (const std::out_of_range&) {
            entry.has_value = false;  // 数値が大きすぎても false
        }
    }
    return true;
}
```

**処理の流れを日本語で追うと:**

1. `#` や空行なら「パース失敗」として false を返す
2. `istringstream`（文字列を分解するツール）で timestamp・level・channel を読む
3. 残りの文字列全体を message に入れる
4. `=` があれば右側を数値として変換、できなければ `has_value = false`

### filter_by_threshold 関数（条件で絞り込む）

```cpp
std::vector<LogEntry> LogParser::filter_by_threshold(
    const std::vector<LogEntry>& entries,
    const std::string& channel,
    double threshold)
{
    std::vector<LogEntry> result;
    for (const auto& e : entries) {
        if (e.channel == channel && e.has_value && e.value > threshold)
            result.push_back(e);
    }
    return result;
}
```

- `std::vector` はリスト（可変長配列）
- `for (const auto& e : entries)` は「entries の全要素を e として順に処理する」
- 3つの条件をすべて満たすエントリだけを result に追加する

---

## 5. 実際に動かしてみよう

### ビルド（コードをバイナリに変換する）

```bash
# リポジトリのルートで実行
cmake -S . -B build -G Ninja
cmake --build build
```

### 実行

```bash
./build/01_log_parser/log_parser_bin 01_log_parser/sample.log
```

**期待される出力:**

```
=== ECU Log Parser ===
Total entries : 7
ENGINE > 6000 : 2

[1] WARN ENGINE rpm=6200
[1.5] ERROR ENGINE rpm=7800
```

「Total entries: 7」は、コメント行と空行を除いた有効行数です。  
「ENGINE > 6000: 2」は、ENGINEチャンネルで6000を超えた行が2件ある、という意味です。

---

## 6. テストコードを読んでみよう

`01_log_parser/test/test_log_parser.cpp` を開きます。テストは「ツールが正しく動くことを証明する小さなプログラム」です。

```cpp
TEST(LogParserTest, FilterChannelIsolation) {
    std::vector<LogEntry> entries;
    LogEntry e1; LogParser::parse_line("1.0 WARN ENGINE rpm=7000", e1);
    LogEntry e2; LogParser::parse_line("2.0 WARN BRAKE pressure=800", e2);
    entries = {e1, e2};

    // ENGINE チャンネルだけが対象
    auto result = LogParser::filter_by_threshold(entries, "ENGINE", 6000.0);
    ASSERT_EQ(result.size(), 1u);
    EXPECT_EQ(result[0].channel, "ENGINE");
}
```

このテストは「BRAKE の値がいくら高くても、ENGINE でフィルタすると BRAKE は返ってこない」ことを確認しています。`ASSERT_EQ`・`EXPECT_EQ` は「これが等しくなければテスト失敗」という命令です。

### テストを実行する

```bash
./build/01_log_parser/test_log_parser.exe
```

---

## 7. 自分で変えてみよう（演習）

### 演習 1: 閾値を変える

`ecu_eval_config.json` を開いて `alert_threshold` を `6000` から `3000` に変えてみましょう。

```json
"alert_threshold": 3000
```

`python ecu_eval.py --env SiLS` を実行すると、アラート件数が増えるはずです。

### 演習 2: BRAKEチャンネルでフィルタする

`01_log_parser/src/main.cpp` を開いて、`"ENGINE"` と `6000.0` の部分を `"BRAKE"` と `50.0` に変えてみましょう。再ビルドしてから実行してみてください。

### 演習 3: 新しいテストを書く

`test_log_parser.cpp` に以下のテストを追加してみましょう。

```cpp
TEST(LogParserTest, ParseTimestamp) {
    LogEntry e;
    ASSERT_TRUE(LogParser::parse_line("2.5 INFO ENGINE rpm=4000", e));
    EXPECT_DOUBLE_EQ(e.timestamp, 2.5);
}
```

これは「タイムスタンプが正しく読めるか」を確認するテストです。ビルドして実行してみてください。

---

## 8. まとめ

| 学んだこと | 対応する概念 |
|---|---|
| ログの1行を分解する | `parse_line()` / `istringstream` |
| 条件に合う行だけ取り出す | `filter_by_threshold()` / `vector` / `for` ループ |
| データの入れ物を作る | `struct LogEntry` |
| 動作を自動検証する | GTest の `TEST()` / `EXPECT_EQ` |

次は **02_gtest_reporter** に進みましょう。テストの結果を「どのように記録するか」を学びます。
