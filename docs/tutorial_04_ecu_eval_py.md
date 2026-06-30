# チュートリアル 04 — ECU 統合評価スクリプト（ecu_eval.py）

> **対象読者:** Python をほぼ書いたことがない。「.py ってどうやって動かすの？」から説明します。

---

## 1. このスクリプトが何をするか（全体像）

### 3ツールを「まとめて」実行する

これまでの3つのツール（LogParser / GTest Reporter / CAN Parser）はそれぞれ別々の実行ファイルでした。

`ecu_eval.py` は、それらを **1つのコマンドで全部実行して、1つのレポートにまとめる** スクリプトです。

```
python ecu_eval.py --env SiLS
         ↓ 自動的に以下を順番に実行
  [01] log_parser_bin sample.log     → LogParser 結果
  [02] sample_ecu_test               → GTest 結果
  [03] can_parser_bin sample.can     → CAN Parser 結果
         ↓ 全結果を集約
  ecu_eval_report.md（統合レポート）
```

---

## 2. Python と C++ の違いを押さえる

| 比較項目 | C++ | Python |
|---|---|---|
| 実行前の変換 | コンパイル（バイナリに変換）が必要 | そのまま実行できる |
| 文法 | セミコロン・波括弧が必要 | インデント（字下げ）で構造を表す |
| 速度 | 非常に高速 | やや遅いが書きやすい |
| 向いている用途 | リアルタイム制御・高速処理 | スクリプト・データ処理・ツール作成 |

このプロジェクトでは「高速処理が必要な部分は C++、まとめる・管理する部分は Python」という役割分担をしています。

---

## 3. Python コードの基本的な読み方

### 変数と型

```python
# 文字列
name = "SiLS"

# 数値
count = 42

# リスト（C++ の vector に相当）
items = ["a", "b", "c"]

# 辞書（C++ の map に相当）
result = {"status": "ok", "count": 7}
```

### 関数の書き方

```python
def 関数名(引数1, 引数2):
    # 処理
    return 戻り値
```

C++ では `{` `}` で囲んでいた部分を、Python では **インデント（4スペースの字下げ）** で表します。

### if 文・for 文

```python
# if 文
if status == "error":
    print("エラーです")

# for ループ（リストの全要素を処理）
for line in lines:
    print(line)
```

---

## 4. 設定ファイル（JSON）とは

### ecu_eval_config.json

`ecu_eval_config.json` は、スクリプトの設定を外から変えるためのファイルです。

```json
{
    "_comment": "ローカル設定（必要な項目だけ記述すればよい）",
    "tools": {
        "log_parser": {
            "alert_channel": "ENGINE",
            "alert_threshold": 6000
        }
    }
}
```

このファイルを変えると、スクリプト本体（.py）を触らなくても閾値などを変更できます。

**JSON とは何か:**

- `{` `}` はオブジェクト（辞書）
- `[` `]` はリスト
- `"key": "value"` はキーと値のペア
- 人間が読み書きしやすいデータ形式

---

## 5. コアの実装を読んでみよう

### _exec_binary 関数（バイナリの実行をまとめる）

```python
def _exec_binary(binary: Path, args: "list | None" = None, *,
                 env: "dict | None" = None,
                 cwd: "Path | None" = None) -> "dict | tuple[int, str, str]":
    if not binary.exists():
        return {"status": "error", "message": f"not found: {binary}"}
    return _run([str(binary)] + (args or []), env=env, cwd=cwd)
```

- `Path` は「ファイルのパス（場所）」を扱うクラス
- `binary.exists()` は「そのファイルが存在するか」を確認
- 存在しなければエラー辞書を返す
- 存在すれば `_run()` で実際に実行する
- 戻り値は「error の辞書」か「(終了コード, 標準出力, 標準エラー) のタプル」

### _check_prerequisites 関数（事前チェック）

```python
def _check_prerequisites(build_dir: Path) -> tuple:
    items = []
    all_ok = True

    def add(icon: str, label: str, advice: str = "") -> None:
        nonlocal all_ok
        items.append((icon, label, advice))
        if icon == "NG":
            all_ok = False

    # ビルドディレクトリの存在確認
    if build_dir.is_dir():
        add("OK", f"build dir: {build_dir}")
    else:
        add("NG", f"build dir not found: {build_dir}", "cmake --build build を実行してください")

    return all_ok, items
```

`add()` は内部関数（`_check_prerequisites` の中だけで使える関数）です。  
`nonlocal all_ok` は「外側の変数 `all_ok` を変更する」という宣言です。

### run_log_parser 関数（LogParser を実行して結果を解析）

```python
def run_log_parser(build_dir: Path) -> dict:
    t = _TOOL["log_parser"]  # 設定を取得
    result = _exec_binary(
        build_dir / t["subdir"] / t["binary"],  # バイナリのパス
        [str(SCRIPT_DIR / t["sample"])]          # 引数（サンプルファイル）
    )
    if isinstance(result, dict):  # エラーが返ってきた場合
        return result
    rc, out, err = result  # 正常時: (終了コード, 出力, エラー)

    # 出力から数値を抜き出す
    for line in out.splitlines():
        if "Total entries" in line:
            total = int(line.split(":")[-1].strip())
        if alert_pat in line:
            alerts = int(line.split(":")[-1].strip())

    return {"status": "ok", "total_entries": total, "alerts": alerts}
```

`out.splitlines()` は出力テキストを行ごとのリストに分割します。  
`"Total entries" in line` は「その文字列がその行に含まれるか」を確認します。

---

## 6. レポートの生成

### generate_report 関数

```python
def generate_report(results: dict, env_tag: str, output: Path):
    log_r = results["log_parser"]
    gt_r  = results["gtest"]
    can_r = results["can_parser"]

    lines = [
        "# ECU Evaluation Report",
        f"| Environment | {env_tag} |",
        f"| 01 Log Parser | {_icon(log_r)} |",
        ...
    ]
    output.write_text("\n".join(lines), encoding="utf-8")
```

`f"..."` は **f-string** といって、`{}` の中に変数を埋め込めます。  
例えば `f"Environment: {env_tag}"` は `env_tag` が `"SiLS"` なら `"Environment: SiLS"` になります。

---

## 7. 実際に動かしてみよう

### 前提：C++ ツールをビルドしておく

```bash
cmake -S . -B build -G Ninja
cmake --build build
```

### スクリプトを実行する

```bash
python ecu_eval.py --env SiLS
```

または設定ファイルを指定する場合：

```bash
python ecu_eval.py --env SiLS --config ecu_eval_config.json
```

### 出力を確認する

実行後に `ecu_eval_report.md` が生成されます。内容例：

```markdown
# ECU Evaluation Report

| Item | Value |
|---|---|
| Environment | SiLS |
| Date | 2026-06-30 10:00:00 |

## Overall Status

| Tool | Result |
|---|---|
| 01 Log Parser     | ✅ OK |
| 02 GTest Reporter | ⚠️ 1 FAILED |
| 03 CAN Parser     | ✅ OK |

## 1. ECU Log Parser
- Total log entries : **7**
- ENGINE > 6000 Alerts : **2**
```

---

## 8. コマンドライン引数の仕組み

### `--env SiLS` が何をしているか

```python
parser = argparse.ArgumentParser()
parser.add_argument("--env", default="SiLS",
                    help="テスト環境タグ (例: SiLS, HiLS)")
args = parser.parse_args()
env_tag = args.env  # "SiLS" が入る
```

`argparse` はコマンドライン引数を解析するための標準ライブラリです。  
`--env SiLS` と書くと `args.env` に `"SiLS"` が入ります。

---

## 9. 自分で変えてみよう（演習）

### 演習 1: 閾値を変えてアラート件数を変える

`ecu_eval_config.json` を開いて `alert_threshold` を変えてみましょう。

```json
{
    "tools": {
        "log_parser": {
            "alert_threshold": 3000
        }
    }
}
```

再実行すると `ecu_eval_report.md` のアラート件数が変わります。

### 演習 2: 環境タグを変えてみる

```bash
python ecu_eval.py --env HiLS
```

レポートの `Environment` 欄が `HiLS` になります。

### 演習 3: スクリプトの _icon 関数を読む

```python
def _icon(r: dict) -> str:
    if r.get("status") == "error":
        return "❌ ERROR"
    if r.get("failed", 0) > 0:
        return f"⚠️ {r['failed']} FAILED"
    return "✅ OK"
```

`r.get("status")` は「辞書 r から "status" キーの値を取得する。なければ None を返す」という意味です。

この関数を改造して、エラー時に「🔴 ERROR」と表示されるようにしてみましょう。

---

## 10. 全体の流れをまとめた図

```
[ecu_eval.py --env SiLS]
         |
         ├─ _load_config()          設定ファイルを読む
         ├─ _check_prerequisites()  ビルド済みか確認
         |
         ├─ run_log_parser()    → 01_log_parser/log_parser_bin を呼ぶ
         ├─ run_gtest()         → 02_gtest_reporter/sample_ecu_test を呼ぶ
         └─ run_can_parser()    → 03_can_parser/can_parser_bin を呼ぶ
                  |
                  ↓
         generate_report()      全結果をまとめてMarkdownに書き出す
                  |
                  ↓
         ecu_eval_report.md     ✅ 完成
```

---

## 11. まとめ

| 学んだこと | 対応する概念 |
|---|---|
| 複数ツールを1つのコマンドで実行する | `subprocess.run()` / `_exec_binary()` |
| 外部設定で動作を変える | JSON 設定ファイル / `_load_config()` |
| コマンドライン引数を受け取る | `argparse` / `--env` |
| 実行結果を解析して数値を取り出す | 文字列の `split()` / `re.search()` |
| 複数ツールの結果をまとめてレポートにする | `generate_report()` / f-string |

これで4つのツールのチュートリアルが完成です。

---

## 次のステップ

4つのチュートリアルを順番に読んで手を動かしたら、以下を試してみましょう。

1. **新しい CAN 信号を追加してエンドツーエンドで動かす**  
   `make_sample_parser()` に信号を追加 → ビルド → `ecu_eval.py` で統合確認

2. **テストケースを自分で書く**  
   `test_log_parser.cpp` か `test_can_parser.cpp` に1件追加 → ビルド → レポートで確認

3. **新しい閾値でアラートが出ることを確認する**  
   `ecu_eval_config.json` の `alert_threshold` を変える → `ecu_eval.py` 実行 → レポート確認
