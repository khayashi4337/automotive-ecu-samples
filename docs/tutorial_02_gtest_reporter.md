# チュートリアル 02 — GTest レポーター

> **対象読者:** テストとは何かわかる。でも「なぜテスト名に REQ001 を付けるの？」「レポートって何？」という段階の人向け。

---

## 1. 「テスト」が必要な理由を整理する

### バグを早期に見つけるための仕組み

エンジン制御ソフトにバグがあった場合、車が誤動作して事故になりかねません。だから車載ソフトウェアの開発では、**コードを書いたら必ずテストで動作を確認する** ことが業界標準になっています。

### テストと「要件」の繋がり

車載開発では **要件定義書** というものがあります。「エンジン回転数が7000rpmを超えたら警告を出すこと」のような仕様を文書化したものです。各要件には番号が振られます（例: REQ001）。

テストコードにもこの番号を紐付けることで、「どのテストがどの仕様を検証しているか」が追跡できます。これを **要件トレーサビリティ** と言います。ISO 26262（車載機能安全規格）では、このトレーサビリティが必須です。

このツールはその仕組みを自動化します。

---

## 2. GTest（Google Test）の基本

GTest は Google が作ったC++用のテストフレームワークです。

### テストを書く

```cpp
TEST(スイート名, テスト名) {
    // ここにテストコードを書く
    EXPECT_EQ(実際の値, 期待値);  // 等しいことを確認
    EXPECT_TRUE(条件);             // true であることを確認
}
```

`TEST(EngineTest, NormalRPM_REQ001)` と書いた場合：
- スイート名: `EngineTest`（テストのグループ名）
- テスト名: `NormalRPM_REQ001`（末尾の `_REQ001` が要件ID）

### サンプルテストを見てみよう

`02_gtest_reporter/test/sample_ecu_test.cpp` を開きます。

```cpp
TEST(EngineTest, NormalRPM_REQ001) {
    // 正常回転数（4000rpm）ではアラートなし
    double rpm = 4000.0;
    EXPECT_LT(rpm, 6000.0);  // rpm < 6000 であることを確認
}

TEST(EngineTest, OverRPM_REQ002) {
    // 意図的に失敗させる（デモ用）
    double rpm = 7800.0;
    EXPECT_LT(rpm, 6000.0);  // 7800 < 6000 → 失敗する！
}
```

`OverRPM_REQ002` は意図的に失敗させています。「高回転数を検知できる」というデモのためです。

---

## 3. イベントリスナーとは何か

### GTest の普通の出力

GTest をそのまま実行すると、コンソールに結果が表示されます。でもそれはターミナルに出るだけで、後から読み返せません。

### イベントリスナーで「記録」する

GTest には **イベントリスナー** という仕組みがあります。テストが始まった・終わったなどのイベントを検知して、自分のコードを動かす仕組みです。

```
テスト実行中
    ↓
GTest が「テスト終了」イベントを発生
    ↓
EcuMarkdownReporter が受け取る（イベントリスナー）
    ↓
Markdown ファイルに結果を書き込む
```

これがこのツールの核心です。

---

## 4. コアの実装を読んでみよう

`02_gtest_reporter/include/ecu_reporter.h` を開きます。

```cpp
class EcuMarkdownReporter : public testing::EmptyTestEventListener {
public:
    explicit EcuMarkdownReporter(const std::string& output_path,
                                 const std::string& env_tag = "SiLS");

    void OnTestStart(const testing::TestInfo& info) override;  // テスト開始時
    void OnTestEnd(const testing::TestInfo& info) override;    // テスト終了時
    void OnTestProgramEnd(const testing::UnitTest& unit_test) override; // 全テスト終了時

private:
    static std::string extract_req_id(const std::string& test_name);
    void write_report(const testing::UnitTest& unit_test) const;
    // ...
};
```

- `public testing::EmptyTestEventListener` → GTest のイベントリスナーを継承（拡張）している
- `override` → 親クラスのメソッドを上書きする宣言
- `static` → インスタンスなしで呼べるメソッド

### `extract_req_id` — テスト名から要件IDを抽出する

```cpp
std::string EcuMarkdownReporter::extract_req_id(const std::string& test_name) {
    static const std::regex kReqPattern(R"((REQ\d+))");
    std::smatch m;
    if (std::regex_search(test_name, m, kReqPattern))
        return m[1].str();
    return "-";
}
```

`std::regex` は **正規表現**（文字列のパターンマッチング）です。

`R"((REQ\d+))"` は「REQ という文字の後に数字が1文字以上続くパターン」を意味します。

- `NormalRPM_REQ001` → `REQ001` を抽出
- `SomeTest` → `-` を返す（REQ番号なし）

---

## 5. 生成されるレポートを読んでみよう

ツールを実行すると `ecu_test_report.md` が生成されます。内容はこんな感じです：

```markdown
# ECU Test Report

| Item     | Value |
|---|---|
| Environment | SiLS |
| Total    | 5 |
| Passed   | 4 |
| Failed   | 1 |

**Result: ❌ FAILED**

## Suite Summary

| Suite      | Tests | Passed | Failed |
|---|---|---|---|
| EngineTest | 5     | 4      | 1      |

## Test Details

| Suite      | Test             | Requirement | Result  | Time (ms) |
|---|---|---|---|---|
| EngineTest | NormalRPM_REQ001 | REQ001      | ✅ PASS | 0.01      |
| EngineTest | OverRPM_REQ002   | REQ002      | ❌ FAIL | 0.29      |
```

**ポイント:**
- `Requirement` 列が自動で埋まっている → 要件トレーサビリティが実現されている
- `Time (ms)` → 各テストがどれだけ時間がかかったかも記録される

---

## 6. 実際に動かしてみよう

### ビルドと実行

```bash
# ビルド
cmake -S . -B build -G Ninja
cmake --build build

# 実行（ECU_TEST_ENV はレポートに記載される環境名）
ECU_TEST_ENV=SiLS ./build/02_gtest_reporter/sample_ecu_test
```

Windowsの場合:

```powershell
$env:ECU_TEST_ENV="SiLS"
.\build\02_gtest_reporter\sample_ecu_test.exe
```

実行後に `ecu_test_report.md` が生成されているか確認してください。

---

## 7. 自分で変えてみよう（演習）

### 演習 1: 新しいテストを追加する

`02_gtest_reporter/test/sample_ecu_test.cpp` に以下を追加してみましょう。

```cpp
TEST(BrakeTest, NormalPressure_REQ003) {
    double pressure = 45.0;
    EXPECT_LT(pressure, 100.0);  // 圧力が100未満であること
}
```

再ビルドして実行すると、レポートに `BrakeTest` スイートが追加され、`Requirement` 列に `REQ003` が入ります。

### 演習 2: 環境タグを変える

```bash
ECU_TEST_ENV=HiLS ./build/02_gtest_reporter/sample_ecu_test
```

生成されたレポートの `Environment` が `HiLS` になります。SiLS（Software in the Loop）と HiLS（Hardware in the Loop）の違いを意識して使い分けます。

### 演習 3: 意図的な失敗を直す

`OverRPM_REQ002` のテストを「成功するように」書き直してみましょう。

```cpp
TEST(EngineTest, OverRPM_REQ002) {
    double rpm = 7800.0;
    EXPECT_GT(rpm, 6000.0);  // 7800 > 6000 → 成功！ (GT = Greater Than)
}
```

再ビルドして実行すると、`Result: ✅ ALL PASSED` になります。

---

## 8. まとめ

| 学んだこと | 対応する概念 |
|---|---|
| テスト名に REQ001 を入れると自動でレポートに反映される | `extract_req_id()` / 正規表現 |
| テストの開始・終了を検知して処理できる | `TestEventListener` / `OnTestEnd` |
| 結果を Markdown ファイルに書き出す | `write_report()` / `ofstream` |
| テスト失敗の詳細も記録される | `GetTestPartResult()` |

次は **03_can_parser** に進みましょう。車の「神経」である CAN バスを学びます。
