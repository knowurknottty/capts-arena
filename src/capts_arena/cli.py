from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .pairwise import compare_pair
from .kingboard import build_kingboard
from .failure_museum import export_failure_museum
from .promotion_gate import decide_promotion
from .bench_matrix import run_matrix as _run_matrix
from . import __version__


def _load_json(path: str) -> dict:
    with open(path) as f:
        return json.load(f)


def _dump_json(obj: dict, path: str) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(obj, f, indent=2)


def cmd_compare(args: argparse.Namespace) -> None:
    baseline = _load_json(args.baseline)
    challenger = _load_json(args.challenger)
    result = compare_pair(baseline, challenger)
    _dump_json(result, args.out)
    print(f"Won: {result['winner']}")
    print(f"Wrote: {args.out}")


def cmd_kingboard(args: argparse.Namespace) -> None:
    pairwise_dir = Path(args.pairwise_reports)
    reports = [json.loads(p.read_text()) for p in pairwise_dir.glob("*.json") if p.is_file()]
    kb = build_kingboard(reports, args.benchmark_suite or "unknown")
    _dump_json(kb, args.out)
    print(f"King: {kb['current_king']}")
    print(f"Rankings: {len(kb['rankings'])} candidates")
    print(f"Wrote: {args.out}")


def cmd_museum(args: argparse.Namespace) -> None:
    pairwise_dir = Path(args.pairwise_reports)
    reports = [json.loads(p.read_text()) for p in pairwise_dir.glob("*.json") if p.is_file()]
    entries = export_failure_museum(reports)
    museum_dir = Path(args.out_dir)
    museum_dir.mkdir(parents=True, exist_ok=True)
    for entry in entries:
        _dump_json(entry, str(museum_dir / f"{entry['museum_id']}.json"))
    print(f"Entries: {len(entries)}")
    print(f"Wrote to: {args.out_dir}")


def cmd_promote(args: argparse.Namespace) -> None:
    candidate = _load_json(args.candidate)
    kb = _load_json(args.kingboard)
    pairwise_dir = Path(args.pairwise_reports)
    reports = [json.loads(p.read_text()) for p in pairwise_dir.glob("*.json") if p.is_file()]
    decision = decide_promotion(candidate["candidate_id"], kb, reports)
    print(json.dumps(decision, indent=2))


def cmd_bench_matrix(args: argparse.Namespace) -> None:
    report = _run_matrix(args.matrix)
    if args.out:
        _dump_json(report, args.out)
    # Print summary to stdout
    print(f"Arena run: {report['arena_run_id']}")
    print(f"Benchmark: {report['benchmark_suite']}")
    print(f"King: {report['kingboard']['current_king']}")
    print(f"Candidates: {report['kingboard']['rankings']} ranked")
    print(f"Pairwise reports: {report['pairwise_count']}")
    print(f"Failure museum: {report['failure_museum_entries']} entries")
    print(f"Wrote: {args.out}")


def main() -> None:
    parser = argparse.ArgumentParser(prog="capts-arena", description="Inversion Arena — CAPT delta benchmarking")
    sub = parser.add_subparsers(dest="command", required=True)

    p_compare = sub.add_parser("compare")
    p_compare.add_argument("--baseline", required=True)
    p_compare.add_argument("--challenger", required=True)
    p_compare.add_argument("--out", default="pairwise_report.json")

    p_kb = sub.add_parser("kingboard")
    p_kb.add_argument("--pairwise-reports", required=True)
    p_kb.add_argument("--benchmark-suite", default=None)
    p_kb.add_argument("--out", default="kingboard.json")

    p_museum = sub.add_parser("museum")
    p_museum.add_argument("--pairwise-reports", required=True)
    p_museum.add_argument("--out-dir", default="failure_museum")

    p_promote = sub.add_parser("promote")
    p_promote.add_argument("--candidate", required=True)
    p_promote.add_argument("--kingboard", required=True)
    p_promote.add_argument("--pairwise-reports", required=True)

    p_bm = sub.add_parser("bench-matrix")
    p_bm.add_argument("matrix")
    p_bm.add_argument("--out", default=".capts-arena/run_report.json")

    args = parser.parse_args()

    if args.command == "compare":
        cmd_compare(args)
    elif args.command == "kingboard":
        cmd_kingboard(args)
    elif args.command == "museum":
        cmd_museum(args)
    elif args.command == "promote":
        cmd_promote(args)
    elif args.command == "bench-matrix":
        cmd_bench_matrix(args)


if __name__ == "__main__":
    main()