# 学習チュートリアル — ECU Portfolio

このフォルダには、4つのツールを「ゼロから理解する」ための学習ドキュメントが入っています。  
C++ / Python を読んだことがない人を起点に、順番に進んでください。

---

## 学習順序

| 順番 | ファイル | 学べること |
|---|---|---|
| 1 | [tutorial_01_log_parser.md](tutorial_01_log_parser.md) | ログとは何か / C++ の構造体・関数・for ループの読み方 |
| 2 | [tutorial_02_gtest_reporter.md](tutorial_02_gtest_reporter.md) | テストとは何か / 要件トレーサビリティ / イベントリスナー |
| 3 | [tutorial_03_can_parser.md](tutorial_03_can_parser.md) | CAN バス / 16進数 / エンディアン / バイト操作 |
| 4 | [tutorial_04_ecu_eval_py.md](tutorial_04_ecu_eval_py.md) | Python の基本 / JSON 設定 / subprocess / 統合レポート |

---

## 各ドキュメントの構成

どのドキュメントも以下の流れで進みます：

1. **何をするツールか** — 背景と目的を説明
2. **サンプルデータを読む** — 実際のファイルを見ながら理解
3. **C++/Python の基本** — 必要な構文の最小限の解説
4. **コアの実装を読む** — 重要な関数を行単位で追う
5. **動かしてみよう** — ビルドと実行手順
6. **演習** — 自分で変更して確認する課題

---

## 前提：ビルド環境

ドキュメントの手順を実際に試すには、以下が必要です。

- **MSYS2** (MinGW64): `C:\msys64\mingw64\bin` に g++.exe・ninja.exe があること
- **CMake**: リポジトリルートで `cmake -S . -B build -G Ninja && cmake --build build` を実行してビルド済みであること
- **Python 3.x**: `python ecu_eval.py --env SiLS` が実行できること
