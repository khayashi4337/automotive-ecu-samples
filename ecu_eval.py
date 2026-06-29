#!/usr/bin/env python3
"""ECU Evaluation Suite — 全ツールを一括実行して統合レポートを生成する"""

import argparse
import copy
import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# Windowsターミナルのcp932対策
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SCRIPT_DIR = Path(__file__).parent
DEFAULT_CONFIG = SCRIPT_DIR / "ecu_eval_config.json"
EXE = ".exe" if sys.platform == "win32" else ""

# ──────────────────────────────────────────────
# 設定ファイル読み込み
# ──────────────────────────────────────────────

_DEFAULTS: dict = {
    "msys2_bin": r"C:\msys64\mingw64\bin",
    "build_dir": "build",
    "tools": {
        "log_parser": {
            "subdir": "01_log_parser",
            "binary": "log_parser_bin",
            "sample": "01_log_parser/sample.log",
            "alert_channel": "ENGINE",
            "alert_threshold": 6000,
        },
        "gtest": {
            "subdir": "02_gtest_reporter",
            "binary": "sample_ecu_test",
            "report": "02_gtest_reporter/ecu_test_report.md",
        },
        "can_parser": {
            "subdir": "03_can_parser",
            "binary": "can_parser_bin",
            "sample": "03_can_parser/sample.can",
        },
    },
}


def _load_config(path: Path) -> dict:
    """設定ファイルを読み込む。ファイルが存在しない場合はデフォルト値を返す。"""
    cfg = copy.deepcopy(_DEFAULTS)
    if not path.exists():
        return cfg
    with open(path, encoding="utf-8") as f:
        overrides = json.load(f)
    for key, val in overrides.items():
        if key.startswith("_"):
            continue
        if isinstance(val, dict) and key in cfg and isinstance(cfg[key], dict):
            cfg[key].update(val)
        else:
            cfg[key] = val
    # tools はネストが2段階なので個別にマージ
    if "tools" in overrides:
        for tool, tval in overrides["tools"].items():
            if tool in cfg["tools"]:
                cfg["tools"][tool].update(tval)
            else:
                cfg["tools"][tool] = tval
    return cfg


def _build_tool_dict(tools_cfg: dict) -> dict:
    """設定の tools セクションから実行時 _TOOL dict を組み立てる（.exe 付加）。"""
    result = {}
    for name, t in tools_cfg.items():
        entry = dict(t)
        entry["binary"] = t["binary"] + EXE
        result[name] = entry
    return result


# ──────────────────────────────────────────────
# 各ツールの実行
# ──────────────────────────────────────────────

# 起動時はデフォルト値で初期化。main() でコンフィグ読み込み後に上書きされる。
MSYS2_BIN: str = _DEFAULTS["msys2_bin"]
DEFAULT_BUILD_DIR = SCRIPT_DIR / _DEFAULTS["build_dir"]
_TOOL: dict = _build_tool_dict(_DEFAULTS["tools"])


def _run(cmd: list, env: dict = None, cwd: Path = None) -> tuple:
    run_env = os.environ.copy()
    if MSYS2_BIN not in run_env.get("PATH", ""):
        run_env["PATH"] = MSYS2_BIN + os.pathsep + run_env.get("PATH", "")
    if env:
        run_env.update(env)
    result = subprocess.run(
        cmd, capture_output=True, text=True,
        encoding="utf-8", errors="replace",
        env=run_env, cwd=str(cwd) if cwd else None
    )
    return result.returncode, result.stdout or "", result.stderr or ""


def run_log_parser(build_dir: Path) -> dict:
    t = _TOOL["log_parser"]
    binary = build_dir / t["subdir"] / t["binary"]
    sample  = SCRIPT_DIR / t["sample"]

    if not binary.exists():
        return {"status": "error", "message": f"not found: {binary}"}

    rc, out, err = _run([str(binary), str(sample)])
    if rc != 0:
        return {"status": "error", "message": err.strip() or f"exited with rc={rc}"}

    alert_pat = f'{t["alert_channel"]} > {t["alert_threshold"]}'
    total = alerts = 0
    for line in out.splitlines():
        if "Total entries" in line:
            try:
                total = int(line.split(":")[-1].strip())
            except ValueError:
                pass
        if alert_pat in line:
            try:
                alerts = int(line.split(":")[-1].strip())
            except ValueError:
                pass

    return {"status": "ok", "total_entries": total, "alerts": alerts, "raw": out}


def run_gtest(build_dir: Path, env_tag: str) -> dict:
    t = _TOOL["gtest"]
    binary = build_dir / t["subdir"] / t["binary"]

    if not binary.exists():
        return {"status": "error", "message": f"not found: {binary}"}

    rc, out, err = _run([str(binary)], env={"ECU_TEST_ENV": env_tag},
                        cwd=build_dir / t["subdir"])
    if rc not in (0, 1):
        return {"status": "error", "message": err.strip() or f"exited with rc={rc}",
                "passed": 0, "failed": 0, "report_md": "", "raw": out}

    passed = failed = 0
    for line in out.splitlines():
        m = re.search(r'\[\s+PASSED\s+\]\s+(\d+)', line)
        if m:
            passed = int(m.group(1))
        m = re.search(r'\[\s+FAILED\s+\]\s+(\d+)\s+test', line)
        if m:
            failed = int(m.group(1))

    report_md = ""
    report_file = build_dir / t["report"]
    if report_file.exists():
        report_md = report_file.read_text(encoding="utf-8")

    return {
        "status": "ok" if rc in (0, 1) else "error",  # rc=1 = test failures (normal GTest exit)
        "passed": passed, "failed": failed,
        "report_md": report_md, "raw": out,
    }


def run_can_parser(build_dir: Path) -> dict:
    t = _TOOL["can_parser"]
    binary = build_dir / t["subdir"] / t["binary"]
    sample  = SCRIPT_DIR / t["sample"]

    if not binary.exists():
        return {"status": "error", "message": f"not found: {binary}"}

    rc, out, err = _run([str(binary), str(sample)])
    if rc != 0:
        return {"status": "error", "message": err.strip() or f"exited with rc={rc}"}

    lines = out.splitlines()
    decoded = sum(1 for line in lines if line.startswith("Frame"))
    unknown = sum(1 for line in lines if "unknown ID" in line)

    return {"status": "ok", "decoded": decoded, "unknown": unknown, "raw": out}


# ──────────────────────────────────────────────
# 統合Markdownレポート生成
# ──────────────────────────────────────────────

def _icon(r: dict) -> str:
    if r.get("status") == "error":
        return "❌ ERROR"
    if r.get("failed", 0) > 0:
        return f"⚠️ {r['failed']} FAILED"
    return "✅ OK"


def generate_report(results: dict, env_tag: str, output: Path):
    log_r = results["log_parser"]
    gt_r  = results["gtest"]
    can_r = results["can_parser"]
    now   = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    lines = [
        "# ECU Evaluation Report", "",
        "| Item | Value |", "|---|---|",
        f"| Environment | {env_tag} |",
        f"| Date        | {now} |", "",
        "## Overall Status", "",
        "| Tool | Result |", "|---|---|",
        f"| 01 Log Parser     | {_icon(log_r)} |",
        f"| 02 GTest Reporter | {_icon(gt_r)} |",
        f"| 03 CAN Parser     | {_icon(can_r)} |",
        "",
    ]

    lines += ["## 1. ECU Log Parser", ""]
    if log_r["status"] == "error":
        lines += [f"> {log_r['message']}", ""]
    else:
        lines += [
            f"- Total log entries    : **{log_r['total_entries']}**",
            f"- ENGINE > 6000 alerts : **{log_r['alerts']}**",
            "",
        ]

    lines += ["## 2. GTest Reporter", ""]
    if gt_r["status"] == "error":
        lines += [f"> {gt_r['message']}", ""]
    else:
        total = gt_r["passed"] + gt_r["failed"]
        lines += [f"- Result : **{gt_r['passed']}/{total} PASSED**", ""]
        lines += _extract_md_section(gt_r["report_md"], "Test Details")
        lines.append("")

    lines += ["## 3. CAN Parser", ""]
    if can_r["status"] == "error":
        lines += [f"> {can_r['message']}", ""]
    else:
        lines += [
            f"- Decoded frames : **{can_r['decoded']}**",
            f"- Unknown frames : **{can_r['unknown']}**",
            "",
            "```", can_r["raw"].strip(), "```", "",
        ]

    output.write_text("\n".join(lines), encoding="utf-8")


def _h(s: str) -> str:
    return (s.replace("&", "&amp;")
              .replace("<", "&lt;")
              .replace(">", "&gt;")
              .replace('"', "&quot;"))


# ──────────────────────────────────────────────
# HTML ダッシュボード生成
# ──────────────────────────────────────────────

_DASHBOARD_CSS = """
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
        background: #0d1117; color: #e6edf3;
        font-family: 'Courier New', Consolas, monospace;
        font-size: 14px; line-height: 1.6;
    }
    .header {
        background: #161b22; border-bottom: 2px solid #21262d;
        padding: 18px 32px;
        display: flex; align-items: center; justify-content: space-between;
    }
    .header h1 { font-size: 18px; font-weight: 700; color: #58a6ff; letter-spacing: 1px; }
    .header .meta { font-size: 12px; color: #8b949e; }
    .header .meta strong { color: #c9d1d9; }
    .overall-bar {
        padding: 10px 32px; font-size: 13px; font-weight: 700;
        letter-spacing: 2px; text-align: center;
    }
    .overall-ok   { background: #0d2218; color: #3fb950; border-bottom: 1px solid #2ea043; }
    .overall-warn { background: #2d1e00; color: #d29922; border-bottom: 1px solid #9e6a03; }
    .container { max-width: 1100px; margin: 0 auto; padding: 24px 32px; }
    .section {
        background: #161b22; border: 1px solid #30363d;
        border-radius: 6px; margin-bottom: 20px; overflow: hidden;
    }
    .section-header {
        background: #21262d; padding: 10px 18px;
        display: flex; align-items: center; gap: 12px;
        border-bottom: 1px solid #30363d;
    }
    .section-title { font-size: 13px; font-weight: 700; color: #c9d1d9; letter-spacing: 0.5px; }
    .section-body { padding: 16px 20px; }
    .badge {
        display: inline-block; padding: 2px 10px; border-radius: 12px;
        font-size: 11px; font-weight: 700; letter-spacing: 0.5px;
    }
    .badge-ok    { background: #0d2218; color: #3fb950; border: 1px solid #2ea043; }
    .badge-warn  { background: #2d1e00; color: #d29922; border: 1px solid #9e6a03; }
    .badge-error { background: #2a0f0f; color: #f85149; border: 1px solid #b91c1c; }
    .stat-row { display: flex; gap: 20px; flex-wrap: wrap; }
    .stat-row-spaced { display: flex; gap: 20px; flex-wrap: wrap; margin-bottom: 16px; }
    .stat {
        background: #0d1117; border: 1px solid #21262d;
        border-radius: 4px; padding: 8px 16px; min-width: 120px;
    }
    .stat-label { font-size: 11px; color: #8b949e; margin-bottom: 2px; }
    .stat-value { font-size: 22px; font-weight: 700; color: #58a6ff; }
    .stat-value.alert { color: #f85149; }
    .stat-value.pass  { color: #3fb950; }
    .stat-value.fail  { color: #f85149; }
    .data-table { width: 100%; border-collapse: collapse; font-size: 13px; margin-top: 4px; }
    .data-table th {
        background: #21262d; color: #8b949e; font-weight: 600;
        padding: 7px 12px; text-align: left; border-bottom: 1px solid #30363d;
    }
    .data-table td { padding: 7px 12px; border-bottom: 1px solid #21262d; }
    .tr-pass { border-left: 3px solid #2ea043; }
    .tr-fail { border-left: 3px solid #b91c1c; background: rgba(248,81,73,0.04); }
    .result-pass {
        background: #0d2218; color: #3fb950; border: 1px solid #2ea043;
        padding: 1px 8px; border-radius: 10px; font-size: 11px; font-weight: 700;
    }
    .result-fail {
        background: #2a0f0f; color: #f85149; border: 1px solid #b91c1c;
        padding: 1px 8px; border-radius: 10px; font-size: 11px; font-weight: 700;
    }
    .req-id { color: #79c0ff; font-weight: 600; }
    .code-block {
        background: #0d1117; border: 1px solid #21262d; border-radius: 4px;
        padding: 12px 16px; font-size: 12px; color: #8b949e;
        overflow-x: auto; white-space: pre; margin-top: 4px;
    }
    .err-msg { color: #f85149; font-size: 13px; }
    .footer {
        text-align: center; padding: 16px; margin-top: 8px;
        font-size: 11px; color: #484f58; border-top: 1px solid #21262d;
    }
"""


def _extract_md_section(md_text: str, section_header: str) -> list:
    """## section_header から次の ## までの行リストを返す（ヘッダ行自体は含まない）"""
    lines = md_text.splitlines()
    in_section = False
    result = []
    for line in lines:
        if line.startswith(f"## {section_header}"):
            in_section = True
            continue
        if in_section and line.startswith("## "):
            break
        if in_section:
            result.append(line)
    return result


def _parse_md_table(md_text: str, section_header: str) -> list:
    headers: list = []
    rows: list = []
    for line in _extract_md_section(md_text, section_header):
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if all(re.fullmatch(r"-+", c) for c in cells if c):
            continue
        if not headers:
            headers = cells
        else:
            rows.append(dict(zip(headers, cells)))
    return rows


def _html_badge(status: str, failed: int = 0) -> str:
    if status in ("error", "failed"):
        return '<span class="badge badge-error">ERROR</span>'
    if failed > 0:
        return f'<span class="badge badge-warn">{failed} FAILED</span>'
    return '<span class="badge badge-ok">OK</span>'


def _html_result_cell(result: str) -> str:
    if result.strip().endswith("PASS"):
        return '<td><span class="result-pass">PASS</span></td>'
    return '<td><span class="result-fail">FAIL</span></td>'


def _build_gtest_table(gtest_rows: list) -> str:
    if not gtest_rows:
        return ""
    rows_html = ""
    for row in gtest_rows:
        result = row.get("Result", "")
        row_class = "tr-pass" if result.strip().endswith("PASS") else "tr-fail"
        rows_html += (
            f'<tr class="{row_class}">'
            f'<td>{_h(row.get("Suite",""))}</td>'
            f'<td>{_h(row.get("Test",""))}</td>'
            f'<td class="req-id">{_h(row.get("Requirement",""))}</td>'
            + _html_result_cell(result) +
            f'<td>{_h(row.get("Time (ms)",""))}</td>'
            f'</tr>'
        )
    return (
        '<table class="data-table">'
        '<thead><tr>'
        '<th>Suite</th><th>Test</th><th>Requirement</th>'
        '<th>Result</th><th>Time (ms)</th>'
        '</tr></thead>'
        f'<tbody>{rows_html}</tbody>'
        '</table>'
    )


def _log_section_body(log_r: dict) -> str:
    if log_r.get("status") == "error":
        return f'<div class="err-msg">{_h(log_r.get("message",""))}</div>'
    alerts = log_r.get("alerts", 0)
    alert_class = ' class="stat-value alert"' if alerts > 0 else ' class="stat-value"'
    return (
        '<div class="stat-row">'
        '<div class="stat"><div class="stat-label">Total Entries</div>'
        f'<div class="stat-value">{log_r.get("total_entries",0)}</div></div>'
        '<div class="stat"><div class="stat-label">ENGINE &gt; 6000 Alerts</div>'
        f'<div{alert_class}>{alerts}</div></div>'
        '</div>'
    )


def _gtest_section_body(gt_r: dict) -> str:
    if gt_r.get("status") == "error":
        return f'<div class="err-msg">{_h(gt_r.get("message",""))}</div>'
    total = gt_r.get("passed", 0) + gt_r.get("failed", 0)
    gtest_rows = _parse_md_table(gt_r.get("report_md", ""), "Test Details")
    table_html = _build_gtest_table(gtest_rows)
    return (
        '<div class="stat-row stat-row-spaced">'
        '<div class="stat"><div class="stat-label">Total</div>'
        f'<div class="stat-value">{total}</div></div>'
        '<div class="stat"><div class="stat-label">Passed</div>'
        f'<div class="stat-value pass">{gt_r.get("passed",0)}</div></div>'
        '<div class="stat"><div class="stat-label">Failed</div>'
        f'<div class="stat-value fail">{gt_r.get("failed",0)}</div></div>'
        f'</div>{table_html}'
    )


def _can_section_body(can_r: dict) -> str:
    if can_r.get("status") == "error":
        return f'<div class="err-msg">{_h(can_r.get("message",""))}</div>'
    raw_html = f'<pre class="code-block">{_h(can_r["raw"])}</pre>' if can_r.get("raw") else ""
    return (
        '<div class="stat-row stat-row-spaced">'
        '<div class="stat"><div class="stat-label">Decoded Frames</div>'
        f'<div class="stat-value">{can_r.get("decoded",0)}</div></div>'
        '<div class="stat"><div class="stat-label">Unknown IDs</div>'
        f'<div class="stat-value">{can_r.get("unknown",0)}</div></div>'
        f'</div>{raw_html}'
    )


def generate_html_report(results: dict, env_tag: str, output: Path):
    log_r = results["log_parser"]
    gt_r  = results["gtest"]
    can_r = results["can_parser"]
    now   = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    all_ok = (
        log_r.get("status") == "ok" and
        log_r.get("alerts", 0) == 0 and
        gt_r.get("failed", 0) == 0 and
        can_r.get("status") == "ok"
    )
    overall_class = "overall-ok" if all_ok else "overall-warn"
    overall_text  = "ALL PASS" if all_ok else "CHECK REQUIRED"

    log_body = _log_section_body(log_r)
    gt_body  = _gtest_section_body(gt_r)
    can_body = _can_section_body(can_r)

    html = (
        '<!DOCTYPE html>\n'
        '<html lang="ja">\n'
        '<head>\n'
        '<meta charset="UTF-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1.0">\n'
        f'<title>ECU Evaluation Dashboard</title>\n'
        f'<style>{_DASHBOARD_CSS}</style>\n'
        '</head>\n'
        '<body>\n'
        '<div class="header">\n'
        '  <h1>ECU Evaluation Dashboard</h1>\n'
        f'  <div class="meta">Environment: <strong>{_h(env_tag)}</strong> &nbsp;|&nbsp; {now}</div>\n'
        '</div>\n'
        f'<div class="overall-bar {overall_class}">{overall_text}</div>\n'
        '<div class="container">\n\n'
        '  <div class="section">\n'
        '    <div class="section-header">\n'
        '      <span class="section-title">01 &mdash; ECU Log Parser</span>\n'
        f'      {_html_badge(log_r.get("status","error"))}\n'
        '    </div>\n'
        f'    <div class="section-body">{log_body}</div>\n'
        '  </div>\n\n'
        '  <div class="section">\n'
        '    <div class="section-header">\n'
        '      <span class="section-title">02 &mdash; GTest Reporter &mdash; Requirement Traceability</span>\n'
        f'      {_html_badge(gt_r.get("status","error"), gt_r.get("failed",0))}\n'
        '    </div>\n'
        f'    <div class="section-body">{gt_body}</div>\n'
        '  </div>\n\n'
        '  <div class="section">\n'
        '    <div class="section-header">\n'
        '      <span class="section-title">03 &mdash; CAN Frame Parser</span>\n'
        f'      {_html_badge(can_r.get("status","error"))}\n'
        '    </div>\n'
        f'    <div class="section-body">{can_body}</div>\n'
        '  </div>\n\n'
        '  <div class="footer">automotive-ecu-samples &mdash; generated by ecu_eval.py</div>\n'
        '</div>\n'
        '</body>\n'
        '</html>'
    )

    output.write_text(html, encoding="utf-8")


# ──────────────────────────────────────────────
# 前提条件チェック
# ──────────────────────────────────────────────

def _check_prerequisites(cfg: dict) -> bool:
    """前提条件を検査する。問題があれば修正方法を表示し、Falseを返す。"""

    def _cmd_ok(cmd: list) -> bool:
        try:
            return subprocess.run(cmd, capture_output=True).returncode == 0
        except FileNotFoundError:
            return False

    items: list = []  # (icon, label, advice)
    all_ok = True

    # 1. Python バージョン
    major, minor = sys.version_info.major, sys.version_info.minor
    if (major, minor) >= (3, 8):
        items.append(("OK", f"Python {major}.{minor}", ""))
    else:
        items.append(("NG", f"Python {major}.{minor}",
                      "Python 3.8 以上が必要です。https://www.python.org/ からインストールしてください。"))
        all_ok = False

    # 2. MSYS2_BIN ディレクトリ（Windows のみ）
    if sys.platform == "win32":
        msys2 = Path(cfg["msys2_bin"])
        if msys2.is_dir():
            items.append(("OK", f"MSYS2_BIN  {msys2}", ""))
        else:
            items.append(("NG", f"MSYS2_BIN  {msys2}",
                          "ディレクトリが見つかりません。\n"
                          "対処: MSYS2 (https://www.msys2.org/) をインストールし、\n"
                          "      ecu_eval_config.json の msys2_bin を実際のパスに変更してください。"))
            all_ok = False

    # 3. g++ コンパイラ
    if sys.platform == "win32":
        gpp = Path(cfg["msys2_bin"]) / "g++.exe"
        if gpp.exists():
            items.append(("OK", f"g++        {gpp}", ""))
        else:
            items.append(("NG", f"g++        {gpp}",
                          "MinGW-w64 ツールチェーンが見つかりません。\n"
                          "対処: MSYS2 ターミナルで以下を実行してください:\n"
                          "      pacman -S mingw-w64-x86_64-gcc"))
            all_ok = False
    else:
        if _cmd_ok(["g++", "--version"]):
            items.append(("OK", "g++", ""))
        else:
            items.append(("NG", "g++  not found",
                          "対処: sudo apt install g++  (または brew install gcc)"))
            all_ok = False

    # 4. CMake
    if _cmd_ok(["cmake", "--version"]):
        items.append(("OK", "cmake", ""))
    else:
        items.append(("NG", "cmake  not found",
                      "対処(MSYS2): pacman -S mingw-w64-x86_64-cmake\n"
                      "対処(直接):  https://cmake.org/download/ からインストールしてください。"))
        all_ok = False

    # 5. Ninja（推奨・必須ではない）
    if _cmd_ok(["ninja", "--version"]):
        items.append(("OK", "ninja", ""))
    else:
        items.append(("WN", "ninja  not found",
                      "必須ではありませんが、推奨ビルドツールです。\n"
                      "対処(MSYS2): pacman -S mingw-w64-x86_64-ninja"))

    # 6. サンプルファイル
    for key in ("log_parser", "can_parser"):
        sample = SCRIPT_DIR / cfg["tools"][key]["sample"]
        if sample.exists():
            items.append(("OK", f"sample     {sample.name}", ""))
        else:
            items.append(("NG", f"sample     {sample}",
                          "サンプルファイルが見つかりません。\n"
                          "対処: リポジトリが完全にクローンされているか確認してください。"))
            all_ok = False

    # 7. ビルドディレクトリ
    build_dir = SCRIPT_DIR / cfg["build_dir"]
    if build_dir.is_dir():
        items.append(("OK", f"build dir  {build_dir}", ""))
    else:
        items.append(("WN", f"build dir  {build_dir}  (未作成)",
                      "初回ビルドが必要です。以下を実行してください:\n"
                      "  cmake -S . -B build -G Ninja\n"
                      "  cmake --build build"))

    # ── 結果表示 ──
    icon_map = {"OK": "✅", "NG": "❌", "WN": "⚠️ "}
    print("=== 前提条件チェック ===")
    for status, label, advice in items:
        print(f"  {icon_map[status]} {label}")
        if advice:
            for line in advice.splitlines():
                print(f"        {line}")
    print()

    if not all_ok:
        print("❌  前提条件を満たしていない項目があります。")
        print("    上記の「対処」を参考に環境を整えてから再実行してください。")
        print("    設定値に誤りがある場合は ecu_eval_config.json を見直してください。")
        print()

    return all_ok


# ──────────────────────────────────────────────
# エントリーポイント
# ──────────────────────────────────────────────

def main():
    global MSYS2_BIN, DEFAULT_BUILD_DIR, _TOOL

    parser = argparse.ArgumentParser(
        description="ECU Evaluation Suite — 全ツールを一括実行して統合レポートを生成"
    )
    parser.add_argument("--env", default="SiLS",
                        choices=["SiLS", "HiLS"],
                        help="評価環境 (default: SiLS)")
    parser.add_argument("--build-dir", default=None,
                        help="ビルドディレクトリ (default: ./build or config value)")
    parser.add_argument("--output", default="ecu_eval_report.md",
                        help="出力レポートファイル名 (default: ecu_eval_report.md); also generates .html dashboard with the same stem")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG),
                        help=f"設定ファイルパス (default: {DEFAULT_CONFIG.name})")
    parser.add_argument("--no-check", action="store_true",
                        help="前提条件チェックをスキップする")
    args = parser.parse_args()

    cfg = _load_config(Path(args.config))
    MSYS2_BIN        = cfg["msys2_bin"]
    DEFAULT_BUILD_DIR = SCRIPT_DIR / cfg["build_dir"]
    _TOOL            = _build_tool_dict(cfg["tools"])

    if not args.no_check:
        if not _check_prerequisites(cfg):
            sys.exit(1)

    build_dir   = Path(args.build_dir) if args.build_dir else DEFAULT_BUILD_DIR
    output_md   = SCRIPT_DIR / args.output
    output_html = output_md.with_suffix(".html")

    print("=== ECU Evaluation Suite ===")
    print(f"Environment : {args.env}")
    print(f"Build dir   : {build_dir}")
    print()

    results = {}

    print("[1/3] Log Parser ...")
    results["log_parser"] = run_log_parser(build_dir)
    r = results["log_parser"]
    print(f"      {_icon(r)}  entries={r.get('total_entries','-')}  alerts={r.get('alerts','-')}")

    print("[2/3] GTest Reporter ...")
    results["gtest"] = run_gtest(build_dir, args.env)
    r = results["gtest"]
    print(f"      {_icon(r)}  passed={r.get('passed','-')}  failed={r.get('failed','-')}")

    print("[3/3] CAN Parser ...")
    results["can_parser"] = run_can_parser(build_dir)
    r = results["can_parser"]
    print(f"      {_icon(r)}  decoded={r.get('decoded','-')}  unknown={r.get('unknown','-')}")

    print()
    print(f"Generating report    -> {output_md.name}")
    generate_report(results, args.env, output_md)

    print(f"Generating dashboard -> {output_html.name}")
    generate_html_report(results, args.env, output_html)

    print("Done.")


if __name__ == "__main__":
    main()
