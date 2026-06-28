#!/usr/bin/env python3
"""ECU Evaluation Suite — 全ツールを一括実行して統合レポートを生成する"""

import argparse
import os
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


def _run(cmd: list, env: dict = None, cwd: Path = None) -> tuple:
    run_env = os.environ.copy()
    # MSYS2 DLLをPATHに追加（MinGWバイナリの依存解決）
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
    binary = build_dir / "01_log_parser" / "log_parser_bin.exe"
    sample  = SCRIPT_DIR / "01_log_parser" / "sample.log"

    if not binary.exists():
        return {"status": "error", "message": f"not found: {binary}"}

    rc, out, _ = _run([str(binary), str(sample)])

    total = alerts = 0
    for line in out.splitlines():
        if "Total entries" in line:
            total = int(line.split(":")[-1].strip())
        if "ENGINE > 6000" in line:
            alerts = int(line.split(":")[-1].strip())

    return {"status": "ok", "total_entries": total, "alerts": alerts, "raw": out}


def run_gtest(build_dir: Path, env_tag: str) -> dict:
    binary = build_dir / "02_gtest_reporter" / "sample_ecu_test.exe"

    if not binary.exists():
        return {"status": "error", "message": f"not found: {binary}"}

    rc, out, _ = _run([str(binary)], env={"ECU_TEST_ENV": env_tag},
                       cwd=build_dir / "02_gtest_reporter")

    import re
    passed = failed = 0
    for line in out.splitlines():
        # "[  PASSED  ] 4 tests." → split() → ['[','PASSED',']','4','tests.']
        m = re.search(r'\[\s+PASSED\s+\]\s+(\d+)', line)
        if m:
            passed = int(m.group(1))
        m = re.search(r'\[\s+FAILED\s+\]\s+(\d+)\s+test', line)
        if m:
            failed = int(m.group(1))

    # GTestレポーターが出力したMarkdownを読み込む
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
    binary = build_dir / "03_can_parser" / "can_parser_bin.exe"
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

    # 1. Log Parser
    lines += ["## 1. ECU Log Parser", ""]
    if log_r["status"] == "error":
        lines += [f"> {log_r['message']}", ""]
    else:
        lines += [
            f"- Total log entries    : **{log_r['total_entries']}**",
            f"- ENGINE > 6000 alerts : **{log_r['alerts']}**",
            "",
        ]

    # 2. GTest
    lines += ["## 2. GTest Reporter", ""]
    if gt_r["status"] == "error":
        lines += [f"> {gt_r['message']}", ""]
    else:
        total = gt_r["passed"] + gt_r["failed"]
        lines += [f"- Result : **{gt_r['passed']}/{total} PASSED**", ""]
        # GTestレポートのTest Detailsテーブルを埋め込む
        in_section = False
        for line in gt_r["report_md"].splitlines():
            if line.startswith("## Test Details"):
                in_section = True
            elif line.startswith("## ") and in_section:
                break
            if in_section:
                lines.append(line)
        lines.append("")

    # 3. CAN Parser
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


# ──────────────────────────────────────────────
# エントリーポイント
# ──────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="ECU Evaluation Suite — 全ツールを一括実行して統合レポートを生成"
    )
    parser.add_argument("--env", default="SiLS",
                        choices=["SiLS", "HiLS", "実車"],
                        help="評価環境 (default: SiLS)")
    parser.add_argument("--build-dir", default=None,
                        help="ビルドディレクトリ (default: ./build)")
    parser.add_argument("--output", default="ecu_eval_report.md",
                        help="出力レポートファイル名 (default: ecu_eval_report.md)")
    args = parser.parse_args()

    build_dir   = Path(args.build_dir) if args.build_dir else DEFAULT_BUILD_DIR
    output_path = SCRIPT_DIR / args.output

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
    print(f"Generating report → {output_path.name}")
    generate_report(results, args.env, output_path)
    print("Done.")


if __name__ == "__main__":
    main()
