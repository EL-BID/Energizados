#!/usr/bin/env python3
"""Extract metrics from all experiment evaluation_report.json files.

Usage:
    python extract_metrics.py <exp_dir> [--format table|json|csv]

Output goes to stdout. Use it to feed the _results.md generation.
"""

import argparse
import glob
import json
import re
import sys
from pathlib import Path


def parse_exp_name(dirname: str) -> dict:
    m = re.match(
        r"^(fase\d+_exp\d+[a-z0-9_-]*?)(?:-(\d{8}_\d{4}))?$",
        dirname,
    )
    if not m:
        return {"name": dirname, "phase": 0, "exp": dirname, "timestamp": ""}
    name = m.group(1)
    ts = m.group(2) or ""
    phase_m = re.match(r"fase(\d+)", name)
    phase = int(phase_m.group(1)) if phase_m else 0
    return {"name": name, "phase": phase, "exp": dirname, "timestamp": ts}


def extract_metrics(report_path: str) -> dict | None:
    try:
        with open(report_path) as f:
            d = json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return None

    m = d.get("metrics", {})
    mi = d.get("model_info", {})
    cal = d.get("calibration", {})
    cm = m.get("confusion_matrix", {})
    gains = m.get("cumulative_gains", {})

    return {
        "auc": m.get("auc"),
        "auc_val": m.get("auc_val"),
        "auc_diff": m.get("auc_diff"),
        "precision": m.get("precision"),
        "recall": m.get("recall"),
        "f1": m.get("f1"),
        "threshold": m.get("threshold"),
        "tp": cm.get("tp"),
        "fp": cm.get("fp"),
        "fn": cm.get("fn"),
        "tn": cm.get("tn"),
        "model_class": mi.get("model_class", ""),
        "inner_model": mi.get("inner_model", ""),
        "ensemble_method": mi.get("method", ""),
        "base_models": mi.get("base_models", []),
        "calibration_enabled": cal.get("enabled", False),
        "calibration_method": cal.get("method", ""),
        "calibration_threshold": cal.get("threshold_used"),
        "gains_deciles": gains.get("deciles", []),
        "gains_cumulative_gain": gains.get("cumulative_gain", []),
        "gains_cumulative_population": gains.get("cumulative_population", []),
    }


def fmt(val, decimals=4, default=""):
    if val is None:
        return default
    return f"{val:.{decimals}f}"


def main():
    parser = argparse.ArgumentParser(description="Extract experiment metrics")
    parser.add_argument("exp_dir", help="Directory containing experiment outputs")
    parser.add_argument(
        "--format",
        choices=["table", "json", "csv"],
        default="json",
        help="Output format (default: json)",
    )
    args = parser.parse_args()

    exp_dir = Path(args.exp_dir)
    if not exp_dir.is_dir():
        print(f"Error: {args.exp_dir} is not a directory", file=sys.stderr)
        sys.exit(1)

    pattern = str(exp_dir / "*" / "reports" / "evaluation" / "evaluation_report.json")
    files = [f for f in sorted(glob.glob(pattern)) if "/.cache/" not in f]

    if not files:
        print(f"No evaluation_report.json found in {args.exp_dir}", file=sys.stderr)
        sys.exit(1)

    results = []
    for f in files:
        exp_dir_name = Path(f).parent.parent.parent.name
        parsed = parse_exp_name(exp_dir_name)
        metrics = extract_metrics(f)
        if metrics is None:
            continue
        results.append({**parsed, **metrics})

    results.sort(key=lambda x: (x.get("phase") or 0, x.get("name") or ""))

    if args.format == "json":
        json.dump(results, sys.stdout, indent=2, ensure_ascii=False)
    elif args.format == "csv":
        cols = [
            "exp",
            "name",
            "model_class",
            "auc",
            "auc_val",
            "auc_diff",
            "precision",
            "recall",
            "f1",
            "threshold",
        ]
        print(",".join(cols))
        for r in results:
            print(",".join(str(r.get(c, "")) for c in cols))
    elif args.format == "table":
        print(
            f"{'Experiment':<50} {'Model':<20} {'AUC val':>8} {'AUC test':>9} "
            f"{'Prec':>7} {'Recall':>7} {'F1':>7} {'Thr':>6} {'Diff':>7}"
        )
        print("-" * 125)
        for r in results:
            print(
                f"{r['exp']:<50} {r['model_class']:<20} "
                f"{fmt(r['auc_val']):>8} {fmt(r['auc']):>9} "
                f"{fmt(r['precision']):>7} {fmt(r['recall']):>7} "
                f"{fmt(r['f1']):>7} {r['threshold']:>6} "
                f"{fmt(r['auc_diff']):>7}"
            )

    best = max(results, key=lambda x: x.get("auc", 0))
    print(f"\nBest AUC test: {best['auc']:.4f} ({best['exp']})", file=sys.stderr)


if __name__ == "__main__":
    main()
