from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from . import __version__
from .bench_matrix import run_matrix as _run_matrix
from .failure_museum import export_failure_museum
from .kingboard import build_kingboard
from .pairwise import compare_pair
from .promotion_gate import decide_promotion
from .score_report import load_json, load_score_reports, write_json


def _read_json_reports_dir(directory: str) -> list[dict[str, Any]]:
    path = Path(directory)
    if not path.exists():
        raise SystemExit(f"Directory not found: {directory}")
    reports: list[dict[str, Any]] = []
    for file_path in sorted(path.glob("*.json")):
        data = load_json(file_path)
        if isinstance(data, dict) and isinstance(data.get("reports"), list):
            reports.extend(data["reports"])
        elif isinstance(data, list):
            reports.extend(data)
        else:
            reports.append(data)
    return reports


def cmd_compare(args: argparse.Namespace) -> None:
    baseline_reports = load_score_reports(args.baseline)
    challenger_reports = load_score_reports(args.challenger)
    baseline_by_case = {report["case_id"]: report for report in baseline_reports}
    challenger_by_case = {report["case_id"]: report for report in challenger_reports}
    case_ids = sorted(set(baseline_by_case).intersection(challenger_by_case))
    if not case_ids:
        raise SystemExit("No shared case_id values between baseline and challenger reports.")

    results = [compare_pair(baseline_by_case[case_id], challenger_by_case[case_id]) for case_id in case_ids]
    output: Any = results[0] if len(results) == 1 else {"reports": results}
    write_json(args.out, output)
    print(f"Compared {len(results)} case(s). Wrote: {args.out}")


def cmd_kingboard(args: argparse.Namespace) -> None:
    reports = _read_json_reports_dir(args.pairwise_reports)
    kb = build_kingboard(reports, args.benchmark_suite or "unknown")
    write_json(args.out, kb)
    print(f"King: {kb['current_king']}")
    print(f"Rankings: {len(kb['rankings'])} candidates")
    print(f"Wrote: {args.out}")


def cmd_museum(args: argparse.Namespace) -> None:
    reports = _read_json_reports_dir(args.pairwise_reports)
    entries = export_failure_museum(reports)
    museum_dir = Path(args.out_dir)
    museum_dir.mkdir(parents=True, exist_ok=True)
    for entry in entries:
        write_json(museum_dir / f"{entry['museum_id']}.json", entry)
    print(f"Entries: {len(entries)}")
    print(f"Wrote to: {args.out_dir}")


def cmd_promote(args: argparse.Namespace) -> None:
    kb = load_json(args.kingboard)
    reports = _read_json_reports_dir(args.pairwise_reports)
    decision = decide_promotion(args.candidate_id, kb, reports)
    print(json.dumps(decision, indent=2, sort_keys=True))


def cmd_bench_matrix(args: argparse.Namespace) -> None:
    report = _run_matrix(args.matrix)
    if args.out:
        write_json(args.out, report)
    print(f"Arena run: {report['arena_run_id']}")
    print(f"Benchmark: {report['benchmark_suite']}")
    print(f"King: {report['kingboard']['current_king']}")
    print(f"Pairwise reports: {report['pairwise_count']}")
    print(f"Failure museum: {report['failure_museum_entries']} entries")
    print(f"Wrote: {args.out}")


def main() -> None:
    parser = argparse.ArgumentParser(prog="capts-arena", description="Inversion Arena — CAPT delta benchmarking")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p_compare = sub.add_parser("compare", help="Compare baseline/challenger score reports by shared case_id")
    p_compare.add_argument("--baseline", required=True)
    p_compare.add_argument("--challenger", required=True)
    p_compare.add_argument("--out", default="pairwise_report.json")
    p_compare.set_defaults(func=cmd_compare)

    p_kb = sub.add_parser("kingboard", help="Build ranking table from pairwise reports")
    p_kb.add_argument("--pairwise-reports", required=True)
    p_kb.add_argument("--benchmark-suite", default=None)
    p_kb.add_argument("--out", default="kingboard.json")
    p_kb.set_defaults(func=cmd_kingboard)

    p_museum = sub.add_parser("museum", help="Export failure museum entries from pairwise reports")
    p_museum.add_argument("--pairwise-reports", required=True)
    p_museum.add_argument("--out-dir", default="failure_museum")
    p_museum.set_defaults(func=cmd_museum)

    p_promote = sub.add_parser("promote", help="Evaluate promotion decision for a candidate")
    p_promote.add_argument("--candidate-id", required=True)
    p_promote.add_argument("--kingboard", required=True)
    p_promote.add_argument("--pairwise-reports", required=True)
    p_promote.set_defaults(func=cmd_promote)

    p_bm = sub.add_parser("bench-matrix", help="Run an Arena matrix from candidate score reports")
    p_bm.add_argument("matrix")
    p_bm.add_argument("--out", default=".capts-arena/run_report.json")
    p_bm.set_defaults(func=cmd_bench_matrix)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
