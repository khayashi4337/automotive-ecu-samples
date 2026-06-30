# C++ 基礎補足 — Java を知っている人向け

> `tutorial_01_log_parser.md` で「???」となった4つの疑問に答えます。

---

## 疑問1: `std::` って何？

### 結論: Java の「パッケージ名」と同じです

Java では `java.util.ArrayList` のように、クラスにパッケージ名がついています。  
C++ では **名前空間（namespace）** という仕組みで同じことをしています。

`std` は **Standard Library（標準ライブラリ）** の名前空間です。

| Java | C++ | 意味 |
|---|---|---|
| `String` | `std::string` | 文字列 |
| `ArrayList<T>` | `std::vector<T>` | 可変長リスト |
| `System.out.println` | `std::cout` | コンソール出力 |
| `import java.util.*` | `using namespace std;` | 省略できるようにする宣言 |

```java
// Java
import java.util.ArrayList;
ArrayList<String> list = new ArrayList<>();
```

```cpp
// C++ — 名前空間 std:: を省略しない書き方
std::vector<std::string> list;

// C++ — "using namespace std;" を先頭に書けば省略できる
using namespace std;
vector<string> list;
```

このコードでは `using namespace std;` を書いていないので、いちいち `std::` を付けています。「どのパッケージから来たものか」を常に明示している状態です。

---

## 疑問2: `&` って何？

### Java のオブジェクト渡しと C++ のデフォルト動作の違い

**Java はオブジェクトを渡すとき、自動で参照渡し（同じオブジェクトを指す）になります。**

```java
// Java — String は参照型なので、渡すのは「参照（住所）」
void parse(String line) { ... }
```

**C++ は、デフォルトで「コピーして渡す（値渡し）」です。**

```cpp
// C++ — コピーが作られる（Javaにはこの概念がない）
void parse(std::string line) { ... }
```

大きな文字列をコピーするのは無駄なので、C++ では `&` を付けて **参照渡し（コピーしない）** にできます。

```cpp
// & を付けると「コピーせず、元の変数を直接参照する」
void parse(std::string& line) { ... }
```

これは Java のオブジェクト渡しと同じ動作です。

### `const` との組み合わせ

`const std::string& line` は **「読み取り専用の参照渡し」** です。

```cpp
// 「コピーしない」＋「書き換えない」を保証
bool parse_line(const std::string& line, LogEntry& entry)
//              ↑ 読み取り専用             ↑ 書き換えあり（out引数）
```

Java で同じことを書くなら：

```java
// Java では参照は自動なので const の概念がない
// （final を付けると変数の再代入禁止になるが、オブジェクトの中身は変えられる）
boolean parseLine(final String line, LogEntry entry) { ... }
```

### 整理表

| 書き方 | 意味 | Java との対応 |
|---|---|---|
| `std::string line` | コピーして受け取る | Java の int など **プリミティブ型** の値渡し |
| `std::string& line` | 参照で受け取る（書き換えあり） | Java のオブジェクト渡し（中身を変えられる） |
| `const std::string& line` | 参照で受け取る（読み取り専用） | Java の参照渡しで中身を変えない場合 |

---

## 疑問3: `auto` って何？

### 結論: Java 10 以降の `var` と全く同じです

型を自動で推論してくれるキーワードです。

```java
// Java 10以降
var eq = entry.message.indexOf('=');  // int 型と自動で推論される
```

```cpp
// C++
auto eq = entry.message.find('=');  // size_t 型と自動で推論される
```

なぜ `auto` を使うのか？ `find()` の返す型は `std::string::size_type`（長い！）です。これを毎回書くのが面倒なので `auto` で省略します。

```cpp
// auto を使わない場合（長い…）
std::string::size_type eq = entry.message.find('=');

// auto を使う場合（同じ意味・すっきり）
auto eq = entry.message.find('=');
```

### `auto` の for ループ

```java
// Java
for (LogEntry e : entries) { ... }
```

```cpp
// C++
for (const auto& e : entries) { ... }
//   ↑ auto が LogEntry に推論される
//   ↑ const & で「コピーしない・変更しない」
```

---

## 疑問4: `ss` って何？（`std::istringstream`）

### 結論: Java の `Scanner` クラスと同じです

`istringstream`（input string stream）は、文字列をストリーム（川）のように順番に読み取るクラスです。

```java
// Java — Scanner で文字列を分解する
Scanner sc = new Scanner("1.234 WARN ENGINE rpm=6200");
double timestamp = sc.nextDouble();  // 1.234
String level     = sc.next();        // "WARN"
String channel   = sc.next();        // "ENGINE"
```

```cpp
// C++ — istringstream で同じことをする
std::istringstream ss("1.234 WARN ENGINE rpm=6200");
double timestamp;
std::string level, channel;
ss >> timestamp;  // 1.234 を読む（Java の nextDouble() に相当）
ss >> level;      // "WARN" を読む（Java の next() に相当）
ss >> channel;    // "ENGINE" を読む
```

`>>` は「右に流し込む」演算子です。`ss >> timestamp` は「ss から読んで timestamp に入れる」という意味です。

### log_parser.cpp の該当部分を読み返そう

```cpp
std::istringstream ss(line);         // line 全体を Scanner に渡すイメージ
ss >> entry.timestamp                // 最初のスペース区切りを double として読む
   >> entry.level                    // 次のスペース区切りを string として読む
   >> entry.channel;                 // さらに次を string として読む
```

`>>` を連鎖させて書けるのが Java と少し違うところです。

### `std::getline` について

```java
// Java — Scanner の残り全部を1行として読む
String rest = sc.nextLine();
```

```cpp
// C++ — istringstream の残り全部を文字列として読む
std::getline(ss, entry.message);
```

`ss >> channel` まで読んだ後、残りの `" rpm=6200"` の部分を `entry.message` に入れます。

---

## 練習問題

### 問題 1: `std::` を補完しよう

以下の空欄に `std::` をつけるべき箇所はどこか答えてください。

```cpp
string name = "hello";
vector<int> scores = {90, 85, 78};
cout << name << endl;
```

<details>
<summary>答えを見る</summary>

```cpp
std::string name = "hello";
std::vector<int> scores = {90, 85, 78};
std::cout << name << std::endl;
```

3箇所すべてに `std::` が必要です。

</details>

---

### 問題 2: `&` の有無による違いを答えよう

以下の2つの関数、どちらが「コピーせずに元の変数を直接参照するか」答えてください。

```cpp
// (A)
void print(std::string msg) {
    std::cout << msg;
}

// (B)
void print(const std::string& msg) {
    std::cout << msg;
}
```

<details>
<summary>答えを見る</summary>

**(B)** が参照渡し（コピーなし）です。

- (A) は `msg` に `std::string` のコピーが作られてから関数に渡されます。
- (B) は元の文字列を直接参照します（Java のオブジェクト渡しと同じ）。

大きな文字列を扱うときは (B) の方が高速です。

</details>

---

### 問題 3: `auto` を使わない書き方に直そう

```cpp
auto result = LogParser::filter_by_threshold(entries, "ENGINE", 6000.0);
```

`filter_by_threshold` の戻り値型は `std::vector<LogEntry>` です。  
`auto` を使わずに書き直してください。

<details>
<summary>答えを見る</summary>

```cpp
std::vector<LogEntry> result = LogParser::filter_by_threshold(entries, "ENGINE", 6000.0);
```

`auto` はこの長い型名を省略してくれています。

</details>

---

### 問題 4: `ss` を Java の `Scanner` で書き直そう

以下の C++ コードを Java の `Scanner` を使ったコードに書き直してください。

```cpp
std::istringstream ss("2.5 WARN BRAKE pressure=95");
double t;
std::string lv, ch;
ss >> t >> lv >> ch;
```

<details>
<summary>答えを見る</summary>

```java
Scanner sc = new Scanner("2.5 WARN BRAKE pressure=95");
double t  = sc.nextDouble();
String lv = sc.next();
String ch = sc.next();
```

C++ の `ss >> t >> lv >> ch;` は Java の `sc.nextXxx()` 3回分に対応します。

</details>

---

### 問題 5: 総合問題

以下の C++ コードを読んで、何をしているか日本語で説明してください。

```cpp
bool LogParser::parse_line(const std::string& line, LogEntry& entry) {
    if (line.empty() || line[0] == '#') return false;
    std::istringstream ss(line);
    ss >> entry.timestamp >> entry.level >> entry.channel;
    if (ss.fail()) return false;
    std::getline(ss, entry.message);
    return true;
}
```

<details>
<summary>答えを見る</summary>

1. `const std::string& line` → line をコピーせず読み取り専用で受け取る
2. `LogEntry& entry` → entry を参照で受け取る（中を書き換える）
3. 空行や `#` で始まる行は false を返して終了
4. `istringstream ss(line)` → line を Scanner のように分解できる状態にする
5. `ss >> entry.timestamp >> entry.level >> entry.channel` → スペース区切りで timestamp・level・channel を読む
6. `ss.fail()` → 3つ読めなかったら false で終了（Java の `sc.hasNext()` の逆）
7. `std::getline(ss, entry.message)` → 残りの文字列を message に入れる
8. `return true` → 正常にパースできた

</details>

---

## まとめ対応表（Java → C++）

| Java | C++ | 備考 |
|---|---|---|
| `java.util.ArrayList` | `std::vector` | `std::` が「パッケージ名」相当 |
| オブジェクト渡し（自動） | `型& 変数名` | C++ は明示的に `&` が必要 |
| `final String s` | `const std::string& s` | 読み取り専用 |
| `var` (Java 10+) | `auto` | 型推論 |
| `new Scanner(str)` | `std::istringstream ss(str)` | 文字列をスペース区切りで読む |
| `sc.nextDouble()` | `ss >> 変数名` | 次のトークンを読む |
| `sc.nextLine()` | `std::getline(ss, str)` | 残り全部を1行として読む |
