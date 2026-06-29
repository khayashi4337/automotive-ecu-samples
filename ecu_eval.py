#!/usr/bin/env python3
"""ECU Evaluation Suite — 全ツールを一括実行して統合レポートを生成する"""

import argparse
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
DEFAULT_BUILD_DIR = SCRIPT_DIR / "build"


# ──────────────────────────────────────────────
# 各ツールの実行
# ──────────────────────────────────────────────

MSYS2_BIN = r"C:\msys64\mingw64\bin"
EXE = ".exe" if __import__("sys").platform == "win32" else ""


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
    binary = build_dir / "01_log_parser" / f"log_parser_bin{EXE}"
    sample  = SCRIPT_DIR / "01_log_parser" / "sample.log"

    if not binary.exists():
        return {"status": "error", "message": f"not found: {binary}"}

    rc, out, _ = _run([str(binary), str(sample)])

    total = alerts = 0
    for line in out.splitlines():
        if "Total entries" in line:
            try:
                total = int(line.split(":")[-1].strip())
            except ValueError:
                pass
        if "ENGINE > 6000" in line:
            try:
                alerts = int(line.split(":")[-1].strip())
            except ValueError:
                pass

    return {"status": "ok", "total_entries": total, "alerts": alerts, "raw": out}


def run_gtest(build_dir: Path, env_tag: str) -> dict:
    binary = build_dir / "02_gtest_reporter" / f"sample_ecu_test{EXE}"

    if not binary.exists():
        return {"status": "error", "message": f"not found: {binary}"}

    rc, out, _ = _run([str(binary)], env={"ECU_TEST_ENV": env_tag},
                       cwd=build_dir / "02_gtest_reporter")

    passed = failed = 0
    for line in out.splitlines():
        m = re.search(r'\[\s+PASSED\s+\]\s+(\d+)', line)
        if m:
            passed = int(m.group(1))
        m = re.search(r'\[\s+FAILED\s+\]\s+(\d+)\s+test', line)
        if m:
            failed = int(m.group(1))

    report_md = ""
    report_file = build_dir / "02_gtest_reporter" / "ecu_test_report.md"
    if report_file.exists():
        report_md = report_file.read_text(encoding="utf-8")

    return {
        "status": "ok" if rc == 0 else "failed",
        "passed": passed, "failed": failed,
        "report_md": report_md, "raw": out,
    }


def run_can_parser(build_dir: Path) -> dict:
    binary = build_dir / "03_can_parser" / f"can_parser_bin{EXE}"
    sample  = SCRIPT_DIR / "03_can_parser" / "sample.can"

    if not binary.exists():
        return {"status": "error", "message": f"not found: {binary}"}

    rc, out, _ = _run([str(binary), str(sample)])

    decoded = sum(1 for l in out.splitlines() if l.startswith("Frame"))
    unknown = sum(1 for l in out.splitlines() if "unknown ID" in l)

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
        in_section = False
        for line in gt_r["report_md"].splitlines():
            if line.startswith("## Test Details"):
                in_section = True
            elif line.startswith("## ") and in_section:
                break
            if in_section:
                lines.append(line)
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

def _parse_md_table(md_text: str, section_header: str) -> list:
    lines = md_text.splitlines()
    in_section = False
    headers = []
    rows = []

    for line in lines:
        if line.startswith(f"## {section_header}"):
            in_section = True
            continue
        if in_section and line.startswith("## "):
            break
        if not in_section or not line.startswith("|"):
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
    if status == "error":
        return '<span class="badge badge-error">ERROR</span>'
    if failed > 0:
        return f'<span class="badge badge-warn">{failed} FAILED</span>'
    return '<span class="badge badge-ok">OK</span>'


def _html_result_cell(result: str) -> str:
    if result.strip().endswith("PASS"):
        return '<td><span class="result-pass">PASS</span></td>'
    return '<td><span class="result-fail">FAIL</span></td>'


def generate_html_report(results: dict, env_tag: str, output: Path):
    log_r = results["log_parser"]
    gt_r  = results["gtest"]
    can_r = results["can_parser"]
    now   = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    gtest_rows = _parse_md_table(gt_r.get("report_md", ""), "Test Details")

    all_ok = (
        log_r.get("status") == "ok" and
        gt_r.get("failed", 0) == 0 and
        can_r.get("status") == "ok"
    )
    overall_class = "overall-ok" if all_ok else "overall-warn"
    overall_text  = "ALL PASS" if all_ok else "CHECK REQUIRED"

    gtest_table_html = ""
    if gtest_rows:
        rows_html = ""
        for row in gtest_rows:
            result = row.get("Result", "")
            is_pass = "PASS" in result
            row_class = "tr-pass" if is_pass else "tr-fail"
            rows_html += (
                f'<tr class="{row_class}">'
                f'<td>{_h(row.get("Suite",""))}</td>'
                f'<td>{_h(row.get("Test",""))}</td>'
                f'<td class="req-id">{_h(row.get("Requirement",""))}</td>'
                + _html_result_cell(result) +
                f'<td>{_h(row.get("Time (ms)",""))}</td>'
                f'</tr>'
            )
        gtest_table_html = (
            '<table class="data-table">'
            '<thead><tr>'
            '<th>Suite</th><th>Test</th><th>Requirement</th>'
            '<th>Result</th><th>Time (ms)</th>'
            '</tr></thead>'
            f'<tbody>{rows_html}</tbody>'
            '</table>'
        )

    can_output_html = ""
    if can_r.get("raw"):
        escaped = (can_r["raw"]
                   .replace("&", "&amp;")
                   .replace("<", "&lt;")
                   .replace(">", "&gt;"))
        can_output_html = f'<pre class="code-block">{escaped}</pre>'

    if log_r.get("status") == "error":
        log_body = f'<div class="err-msg">{_h(log_r.get("message",""))}</div>'
    else:
        alerts = log_r.get("alerts", 0)
        alert_style = ' style="color:#f85149"' if alerts > 0 else ""
        log_body = (
            '<div class="stat-row">'
            '<div class="stat"><div class="stat-label">Total Entries</div>'
            f'<div class="stat-value">{log_r.get("total_entries",0)}</div></div>'
            '<div class="stat"><div class="stat-label">ENGINE &gt; 6000 Alerts</div>'
            f'<div class="stat-value"{alert_style}>{alerts}</div></div>'
            '</div>'
        )

    if gt_r.get("status") == "error":
        gt_body = f'<div class="err-msg">{_h(gt_r.get("message",""))}</div>'
    else:
        total = gt_r.get("passed", 0) + gt_r.get("failed", 0)
        gt_body = (
            '<div class="stat-row" style="margin-bottom:16px">'
            '<div class="stat"><div class="stat-label">Total</div>'
            f'<div class="stat-value">{total}</div></div>'
            '<div class="stat"><div class="stat-label">Passed</div>'
            f'<div class="stat-value" style="color:#3fb950">{gt_r.get("passed",0)}</div></div>'
            '<div class="stat"><div class="stat-label">Failed</div>'
            f'<div class="stat-value" style="color:#f85149">{gt_r.get("failed",0)}</div></div>'
            f'</div>{gtest_table_html}'
        )

    if can_r.get("status") == "error":
        can_body = f'<div class="err-msg">{_h(can_r.get("message",""))}</div>'
    else:
        can_body = (
            '<div class="stat-row" style="margin-bottom:16px">'
            '<div class="stat"><div class="stat-label">Decoded Frames</div>'
            f'<div class="stat-value">{can_r.get("decoded",0)}</div></div>'
            '<div class="stat"><div class="stat-label">Unknown IDs</div>'
            f'<div class="stat-value">{can_r.get("unknown",0)}</div></div>'
            f'</div>{can_output_html}'
        )

    css = """
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
    .stat {
        background: #0d1117; border: 1px solid #21262d;
        border-radius: 4px; padding: 8px 16px; min-width: 120px;
    }
    .stat-label { font-size: 11px; color: #8b949e; margin-bottom: 2px; }
    .stat-value { font-size: 22px; font-weight: 700; color: #58a6ff; }
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

    html = (
        '<!DOCTYPE html>\n'
        '<html lang="ja">\n'
        '<head>\n'
        '<meta charset="UTF-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1.0">\n'
        f'<title>ECU Evaluation Dashboard</title>\n'
        f'<style>{css}</style>\n'
        '</head>\n'
        '<body>\n'
        '<div class="header">\n'
        '  <h1>ECU Evaluation Dashboard</h1>\n'
        f'  <div class="meta">Environment: <strong>{env_tag}</strong> &nbsp;|&nbsp; {now}</div>\n'
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
# エントリーポイント
# ──────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="ECU Evaluation Suite — 全ツールを一括実行して統合レポートを生成"
    )
    parser.add_argument("--env", default="SiLS",
                        choices=["SiLS", "HiLS"],
                        help="評価環境 (default: SiLS)")
    parser.add_argument("--build-dir", default=None,
                        help="ビルドディレクトリ (default: ./build)")
    parser.add_argument("--output", default="ecu_eval_report.md",
                        help="出力レポートファイル名 (default: ecu_eval_report.md); also generates .html dashboard with the same stem")
    args = parser.parse_args()

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
