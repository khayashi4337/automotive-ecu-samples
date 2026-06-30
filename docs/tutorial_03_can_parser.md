# チュートリアル 03 — CAN フレームパーサー

> **対象読者:** 「CANって何？」という人向け。16進数・ビット操作も初めて。そこから説明します。

---

## 1. CAN バスとは何か

### 車の「神経」

車には何十個もの ECU が搭載されています。これらが互いに情報をやり取りするための通信規格が **CAN（Controller Area Network）** です。

簡単に言うと「車の中を走る社内ネットワーク（LAN）」のようなものです。

```
[エンジン ECU] ──┐
[ブレーキ ECU] ──┤── CAN バス（1本の線） ── [メーター ECU]
[ステアリング ECU]┘
```

### CAN フレームとは

CAN バスを流れる1つのデータのまとまりを **フレーム** と呼びます。フレームには以下が含まれます。

| フィールド | 意味 | 例 |
|---|---|---|
| ID | 誰が送ったか（送信元の識別子） | `0x0C1` |
| DLC | データが何バイトあるか | `8` |
| DATA | 実際のデータ（最大8バイト） | `1A005A00000000` |

---

## 2. 16進数（HEX）の読み方

### 16進数とは

コンピュータは 0 と 1 だけの**2進数**で動いています。しかし 2 進数は桁が多くなりすぎて人間に読みにくいです。そこで **16進数（0〜9・A〜F の16種類）** でまとめて表現します。

```
2進数:    1010 1011
         ↓ 4ビットずつ区切る
         1010  |  1011
          A    |   B
16進数:       AB
```

CAN のサンプルファイル `03_can_parser/sample.can` を見てみましょう。

```
# Format: ID#DATA
0C1#1A005A00000000
```

これは「IDが `0x0C1`、データが `1A 00 5A 00 00 00 00 00`（8バイト）」というフレームです。

---

## 3. 信号デコードとは

### バイトの中に複数の信号が詰まっている

CAN フレームの8バイトには、複数の信号（センサー値）が詰め込まれています。

例えば `0x0C1` フレームの場合：

```
バイト位置:  [0] [1] [2] [3] [4] [5] [6] [7]
データ:      1A  00  5A  00  00  00  00  00
             ↑──────↑  ↑
             ENGINE_RPM  COOLANT_TEMP
             (2バイト)   (1バイト)
```

- `byte0-1` → ENGINE_RPM（エンジン回転数）
- `byte2` → COOLANT_TEMP（冷却水温）

### 信号定義（SignalDef）

どのバイトにどの信号があるかを定義する設定を **SignalDef** と呼びます。

```cpp
struct SignalDef {
    std::string name;       // 信号名（例: "ENGINE_RPM"）
    std::string unit;       // 単位（例: "rpm"）
    uint8_t start_byte;    // 何バイト目から始まるか
    uint8_t length_bytes;  // 何バイト分あるか
    double scale;          // 生の値に掛ける係数
    double offset;         // 掛けた後に足す数値
    bool big_endian;       // バイトの並び順
};
```

### 物理値への変換

生の数値（raw）をそのまま使うのではなく、係数（scale）と基準値（offset）を使って実際の物理量に変換します。

```
物理値 = raw × scale + offset
```

例：`ENGINE_RPM` で raw が `0x1A00` だった場合

```
0x1A00 = 6656（10進数）
6656 × 0.25 + 0.0 = 1664.0 rpm
```

`COOLANT_TEMP` で raw が `0x5A`（= 90）だった場合

```
90 × 1.0 + (-40.0) = 50.0 degC
```

---

## 4. エンディアンとは

### バイトの並び順の違い

2バイトの数値 `0x1A00` をメモリに格納するとき、**バイトの並べ方が2種類あります**。

| 種類 | 並び方 | byte0 | byte1 |
|---|---|---|---|
| ビッグエンディアン（BE） | 大きい桁が先 | `1A` | `00` |
| リトルエンディアン（LE） | 小さい桁が先 | `00` | `1A` |

CAN では BE（ビッグエンディアン）が一般的です。

---

## 5. コアの実装を読んでみよう

`03_can_parser/src/can_parser.cpp` を開きます。

### parse_hex 関数（16進数文字列をフレームに変換）

```cpp
bool CanParser::parse_hex(const std::string& id_hex,
                          const std::string& data_hex,
                          CanFrame& frame) {
    try {
        frame.id  = static_cast<uint32_t>(std::stoul(id_hex, nullptr, 16));
        frame.dlc = static_cast<uint8_t>(data_hex.size() / 2);
        if (frame.dlc > 8) return false;  // DLC は最大8
        std::memset(frame.data, 0, sizeof(frame.data));  // まずゼロクリア
        for (uint8_t i = 0; i < frame.dlc; ++i) {
            // 2文字ずつ取り出して1バイトに変換
            frame.data[i] = static_cast<uint8_t>(
                std::stoul(data_hex.substr(i * 2, 2), nullptr, 16));
        }
        frame.is_extended = (frame.id > 0x7FF);  // 11bit超ならextended ID
    } catch (...) {
        return false;
    }
    return true;
}
```

`std::stoul(text, nullptr, 16)` は「16進数の文字列を数値に変換する」という標準関数です。

### extract_raw 関数（バイト列から生の数値を取り出す）

```cpp
uint64_t CanParser::extract_raw(const CanFrame& frame, const SignalDef& sig) {
    uint64_t raw = 0;
    if (sig.big_endian) {
        for (uint8_t i = 0; i < sig.length_bytes; ++i) {
            raw = (raw << 8) | frame.data[sig.start_byte + i];
        }
    } else {
        // リトルエンディアン：逆順に読む
        for (uint8_t i = sig.length_bytes; i > 0; --i) {
            raw = (raw << 8) | frame.data[sig.start_byte + i - 1];
        }
    }
    return raw;
}
```

`raw = (raw << 8) | data` は「rawを8ビット左にずらして、次のバイトをくっつける」操作です。

```
初期: raw = 0x00000000
i=0:  raw = (0 << 8) | 0x1A = 0x0000001A
i=1:  raw = (0x1A << 8) | 0x00 = 0x00001A00
```

### decode 関数（フレーム全体を物理値に変換）

```cpp
std::vector<SignalValue> CanParser::decode(const CanFrame& frame) const {
    std::vector<SignalValue> result;
    auto it = signal_map_.find(frame.id);  // このIDに対応する信号定義を探す
    if (it == signal_map_.end()) return result;  // なければ空を返す

    for (const auto& sig : it->second) {
        if (sig.start_byte + sig.length_bytes > frame.dlc) continue; // 境界チェック
        uint64_t raw = extract_raw(frame, sig);
        SignalValue sv;
        sv.name  = sig.name;
        sv.unit  = sig.unit;
        sv.value = raw * sig.scale + sig.offset;  // 物理値に変換
        result.push_back(sv);
    }
    return result;
}
```

---

## 6. サンプルのcan_parser.cpp（信号定義の登録）

```cpp
CanParser make_sample_parser() {
    CanParser p;

    // CAN ID 0x0C1: エンジン情報
    p.add_signal(0x0C1, {"ENGINE_RPM",   "rpm",  0, 2, 0.25,  0.0,  true});
    p.add_signal(0x0C1, {"COOLANT_TEMP", "degC", 2, 1, 1.0,  -40.0, true});

    // CAN ID 0x1A0: ブレーキ情報
    p.add_signal(0x1A0, {"BRAKE_PRESSURE", "kPa", 0, 2, 0.1, 0.0, true});

    // CAN ID 0x2B0: 車速
    p.add_signal(0x2B0, {"VEHICLE_SPEED", "km/h", 0, 2, 0.01, 0.0, true});

    return p;
}
```

---

## 7. 実際に動かしてみよう

### ビルドと実行

```bash
cmake -S . -B build -G Ninja
cmake --build build
./build/03_can_parser/can_parser_bin 03_can_parser/sample.can
```

**期待される出力:**

```
=== CAN Parser ===
0C1  ENGINE_RPM     =   1664.00 rpm
0C1  COOLANT_TEMP   =     50.00 degC
1A0  BRAKE_PRESSURE =    500.00 kPa
2B0  VEHICLE_SPEED  =    100.00 km/h
FFF  (no matching signals)
```

`FFF` は未登録のIDなので信号が出ません。

### 計算を追ってみよう

`sample.can` の `0C1#1A005A00000000` を手動で計算してみましょう。

| バイト位置 | 16進数 | 10進数 |
|---|---|---|
| byte0 | `1A` | 26 |
| byte1 | `00` | 0 |
| byte2 | `5A` | 90 |

```
ENGINE_RPM : 0x1A00 = 6656 → 6656 × 0.25 = 1664.0 rpm
COOLANT_TEMP: 0x5A  =  90  → 90 × 1.0 + (-40) = 50.0 degC
```

---

## 8. テストを読んでみよう

`03_can_parser/test/test_can_parser.cpp` を開きます。

```cpp
// ビッグエンディアンの信号が正しくデコードされること
TEST_F(CanParserTest, DecodeBrakePressure) {
    CanFrame f{};
    CanParser::parse_hex("1A0", "1388000000000000", f);
    auto signals = parser.decode(f);
    ASSERT_EQ(signals.size(), 1u);
    EXPECT_EQ(signals[0].name, "BRAKE_PRESSURE");
    EXPECT_NEAR(signals[0].value, 500.0, 0.001);
}
```

`0x1388` = 5000（10進数）→ `5000 × 0.1 = 500.0 kPa` が確認できます。

`EXPECT_NEAR(実際値, 期待値, 許容誤差)` は浮動小数点数の比較に使います（浮動小数点は計算のたびにごく微小な誤差が出るため、完全一致を求めずに「誤差が 0.001 未満なら OK」と確認します）。

---

## 9. 自分で変えてみよう（演習）

### 演習 1: 新しい信号を追加してみよう

`03_can_parser/src/can_parser.cpp` の `make_sample_parser()` に、バッテリー電圧の信号を追加してみましょう。

```cpp
// CAN ID 0x300: バッテリー情報
// byte0-1: 電圧（scale=0.01, unit=V）
p.add_signal(0x300, {"BATTERY_VOLTAGE", "V", 0, 2, 0.01, 0.0, true});
```

`sample.can` に対応する行を追加します。

```
300#5DC0000000000000
```

`0x5DC0` = 24000 → `24000 × 0.01 = 240.0 V`（例としてのデモ値）

再ビルドして出力を確認してください。

### 演習 2: 手計算でデコードしてみよう

`sample.can` の `2B0#27100000000000` を手動でデコードしてみましょう。

```
byte0 = 0x27 = 39
byte1 = 0x10 = 16
→ big endian: 0x2710 = 10000（10進数）
→ VEHICLE_SPEED: 10000 × 0.01 = 100.0 km/h
```

計算が合っているか実行結果と照合してください。

### 演習 3: テストを1つ書いてみよう

```cpp
TEST_F(CanParserTest, DecodeVehicleSpeed) {
    CanFrame f{};
    CanParser::parse_hex("2B0", "2710000000000000", f);
    auto signals = parser.decode(f);
    ASSERT_EQ(signals.size(), 1u);
    EXPECT_EQ(signals[0].name, "VEHICLE_SPEED");
    EXPECT_NEAR(signals[0].value, 100.0, 0.001);
}
```

テストファイルに追加して実行してみてください。

---

## 10. まとめ

| 学んだこと | 対応する概念 |
|---|---|
| 車の中の通信 | CAN バス / フレーム / ID |
| 16進数の読み方 | `stoul(text, nullptr, 16)` |
| バイトの並び順 | ビッグエンディアン / リトルエンディアン |
| 生の値を物理値に変換 | `raw × scale + offset` |
| 信号定義の登録 | `add_signal()` / `SignalDef` |

次は **04_ecu_eval_py** に進みましょう。4つのツールを「まとめて実行する」オーケストレーターを学びます。
