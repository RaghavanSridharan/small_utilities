#!/usr/bin/env python3
"""
Node / Cluster Diff Tool
--------------------------
Zero-dependency drift detector for multi-node infrastructure. Ingests the
--json output of any tool in this repo that uses the shared Report shape
({section: [{"label","value","status"}, ...]}) — Dev Environment Auditor,
Service Health Snapshot, Scheduled Jobs Inspector, all work — collected
from 2 or more nodes, and shows ONLY what's different between them.

Two rendering modes, chosen automatically based on node count (override
with --matrix / --majority):

  MATRIX MODE (<=4 nodes by default): clean side-by-side comparison —
  readable in a normal terminal without wrapping.

  MAJORITY MODE (5+ nodes): groups nodes by value and shows counts —
  "24.0.7 on 15/16 nodes, outlier: node9 = 24.0.5" — because a wide
  N-column table stops being readable long before N gets interesting,
  and grouping is actually a BETTER way to spot the rogue node in a
  big rack than scanning 16 columns by eye.

Fields expected to vary per node (hostname, IP, uptime) are excluded
from the diff automatically — you only see real drift, not noise.

Usage:
    python3 node_diff.py node1.json node2.json
    python3 node_diff.py rack/*.json --names node1,node2,node3,node4
    python3 node_diff.py rack/*.json --majority --show-all
    python3 node_diff.py n1.json n2.json --exclude "Timezone,JAVA_HOME"
    python3 node_diff.py n1.json n2.json --json drift.json --no-save
"""

import os
import re
import sys
import json
import shutil
import argparse
from datetime import datetime
from collections import defaultdict, OrderedDict

# --------------------------------------------------------------------------
# Terminal styling
# --------------------------------------------------------------------------

class Style:
    enabled = sys.stdout.isatty()

    @classmethod
    def wrap(cls, code, text):
        return text if not cls.enabled else f"\033[{code}m{text}\033[0m"

    @classmethod
    def bold(cls, t): return cls.wrap("1", t)
    @classmethod
    def dim(cls, t): return cls.wrap("2", t)
    @classmethod
    def cyan(cls, t): return cls.wrap("36", t)


ICONS = {"ok": "OK", "warn": "!!", "fail": "XX", "info": ".."}
COLOR_ICONS = {"ok": "\033[32mOK\033[0m", "warn": "\033[33m!!\033[0m",
               "fail": "\033[31mXX\033[0m", "info": "\033[2m..\033[0m"}


def icon(kind):
    return COLOR_ICONS[kind] if Style.enabled else ICONS[kind]


# --------------------------------------------------------------------------
# Fields excluded from diffing by default — expected to differ per node,
# so diffing them would just be noise, not signal.
# --------------------------------------------------------------------------

DEFAULT_EXCLUDE = {
    "hostname", "ip address(es)", "uptime", "logged in as",
    "generated", "total accounts",  # accounts count varies benignly with LDAP sync timing etc.
}

MISSING_PATTERNS = re.compile(
    r"\bnot installed\b|\bnot found\b|\bmissing\b|\bnot detected\b|\bnone found\b|\bunavailable\b",
    re.IGNORECASE,
)


# --------------------------------------------------------------------------
# Loading node reports
# --------------------------------------------------------------------------

def derive_node_name(path, index):
    stem = os.path.splitext(os.path.basename(path))[0]
    # strip common noisy suffixes like "_report_20260814_123000" if present
    stem = re.sub(r"_report(_\d{8}_\d{6})?$", "", stem)
    stem = re.sub(r"(_\d{8}_\d{6})$", "", stem)
    return stem or f"node{index+1}"


def load_node_report(path):
    with open(path) as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"{path}: expected a JSON object of sections, got {type(data).__name__}")
    return data


# --------------------------------------------------------------------------
# Building the comparison matrix:
# comparison[section][label] = {node_name: (value, status)}
# --------------------------------------------------------------------------

def build_comparison(node_reports, exclude_labels):
    comparison = OrderedDict()
    for node_name, report in node_reports.items():
        for section, rows in report.items():
            if not isinstance(rows, list):
                continue
            for row in rows:
                label = row.get("label", "")
                if label.strip().lower() in exclude_labels:
                    continue
                value = row.get("value", "")
                status = row.get("status", "info")
                comparison.setdefault(section, OrderedDict())
                comparison[section].setdefault(label, {})
                comparison[section][label][node_name] = (value, status)
    return comparison


def has_drift(label_data, node_names):
    values = [label_data.get(n, (None, None))[0] for n in node_names]
    present = [v for v in values if v is not None]
    if len(set(present)) > 1:
        return True
    if len(present) != len(node_names):  # present on some nodes, absent on others
        return True
    return False


def truncate(s, width):
    s = str(s)
    return s if len(s) <= width else s[: width - 1] + "…"


def drift_kind(label_data, node_names):
    """Escalate to 'fail' if any of the differing values look like a missing/
    broken state (not installed, not found, etc.); otherwise 'warn'."""
    for n in node_names:
        value, status = label_data.get(n, (None, None))
        if value is None:
            return "fail"  # present on some nodes, absent on others = notable
        if status == "fail" or MISSING_PATTERNS.search(str(value)):
            return "fail"
    return "warn"


# --------------------------------------------------------------------------
# Matrix rendering (small N)
# --------------------------------------------------------------------------

def render_matrix(comparison, node_names, show_all, value_width=22):
    lines = []
    total_drift = 0
    for section, labels in comparison.items():
        section_lines = []
        for label, label_data in labels.items():
            drift = has_drift(label_data, node_names)
            if not drift and not show_all:
                continue
            kind = drift_kind(label_data, node_names) if drift else "ok"
            total_drift += 1 if drift else 0
            parts = []
            for n in node_names:
                value, _status = label_data.get(n, (None, None))
                shown = truncate(value, value_width) if value is not None else "(not present)"
                parts.append(f"{Style.dim(n)}: {shown}")
            section_lines.append(f"  {icon(kind)} {label:<28} " + "   ".join(parts))
        if section_lines:
            lines.append("\n " + Style.cyan(Style.bold(section)))
            lines.append(" " + "-" * 78)
            lines.extend(section_lines)
    return lines, total_drift


# --------------------------------------------------------------------------
# Majority/outlier rendering (large N)
# --------------------------------------------------------------------------

def render_majority(comparison, node_names, show_all, max_named_nodes=6):
    lines = []
    total_drift = 0
    n_total = len(node_names)
    for section, labels in comparison.items():
        section_lines = []
        for label, label_data in labels.items():
            drift = has_drift(label_data, node_names)
            if not drift and not show_all:
                continue

            groups = defaultdict(list)
            for n in node_names:
                value, _status = label_data.get(n, (None, None))
                key = "(not present)" if value is None else str(value)
                groups[key].append(n)
            groups_sorted = sorted(groups.items(), key=lambda kv: len(kv[1]), reverse=True)

            if not drift:
                only_value, only_nodes = groups_sorted[0]
                section_lines.append(f"  {icon('ok')} {label:<28} {only_value}  (same on all {n_total} nodes)")
                continue

            total_drift += 1
            kind = drift_kind(label_data, node_names)
            section_lines.append(f"  {icon(kind)} {label}")
            for value, nodes in groups_sorted:
                count_str = f"{len(nodes)}/{n_total} nodes"
                if len(nodes) <= max_named_nodes:
                    node_list = f"  ({', '.join(nodes)})"
                else:
                    node_list = ""
                section_lines.append(f"        {truncate(value, 40):<42} -> {count_str}{node_list}")
        if section_lines:
            lines.append("\n " + Style.cyan(Style.bold(section)))
            lines.append(" " + "-" * 78)
            lines.extend(section_lines)
    return lines, total_drift


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def parse_args():
    p = argparse.ArgumentParser(
        description="Node/Cluster Diff Tool — compares --json reports from 2+ nodes, shows only drift.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("files", nargs="+", help="Two or more JSON report files to compare.")
    p.add_argument("--names", metavar="NAME,NAME,...",
                    help="Comma-separated node names, in the same order as the files (default: derived from filename).")
    p.add_argument("--matrix", action="store_true", help="Force side-by-side matrix mode regardless of node count.")
    p.add_argument("--majority", action="store_true", help="Force majority/outlier grouping mode regardless of node count.")
    p.add_argument("--show-all", action="store_true", help="Also show fields that match across all nodes, not just drift.")
    p.add_argument("--exclude", metavar="LABEL,LABEL,...", default="",
                    help="Additional field labels to exclude from the diff, on top of the built-in defaults.")
    p.add_argument("--json", metavar="FILE", help="Write the drift result as JSON to FILE.")
    p.add_argument("--no-save", action="store_true", help="Don't write the timestamped .txt report to disk.")
    p.add_argument("--no-color", action="store_true", help="Disable colored output.")
    return p.parse_args()


def main():
    args = parse_args()
    if args.no_color:
        Style.enabled = False

    if len(args.files) < 2:
        print("Error: need at least 2 JSON report files to compare.", file=sys.stderr)
        sys.exit(1)

    if args.names:
        names = [n.strip() for n in args.names.split(",")]
        if len(names) != len(args.files):
            print(f"Error: --names has {len(names)} entries but {len(args.files)} files were given.", file=sys.stderr)
            sys.exit(1)
    else:
        names = [derive_node_name(f, i) for i, f in enumerate(args.files)]

    node_reports = OrderedDict()
    for name, path in zip(names, args.files):
        try:
            node_reports[name] = load_node_report(path)
        except FileNotFoundError:
            print(f"Error: file not found: {path}", file=sys.stderr)
            sys.exit(1)
        except json.JSONDecodeError as e:
            print(f"Error: {path} is not valid JSON ({e}).", file=sys.stderr)
            sys.exit(1)
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)

    node_names = list(node_reports.keys())
    exclude_labels = set(DEFAULT_EXCLUDE)
    exclude_labels |= {e.strip().lower() for e in args.exclude.split(",") if e.strip()}

    comparison = build_comparison(node_reports, exclude_labels)

    if args.matrix:
        mode = "matrix"
    elif args.majority:
        mode = "majority"
    else:
        term_width = shutil.get_terminal_size(fallback=(100, 24)).columns
        # Matrix mode needs roughly 30 (label) + N * ~26 (value column) chars.
        fits_matrix = len(node_names) <= 4 and (30 + len(node_names) * 26) <= max(term_width, 80)
        mode = "matrix" if fits_matrix else "majority"

    width = 82
    header = []
    header.append("=" * width)
    header.append(f" CLUSTER DRIFT DETECTOR  ({len(node_names)} nodes, {mode} mode)")
    header.append(f" Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    header.append(f" Nodes: {', '.join(node_names)}")
    header.append("=" * width)

    if mode == "matrix":
        body_lines, total_drift = render_matrix(comparison, node_names, args.show_all)
    else:
        body_lines, total_drift = render_majority(comparison, node_names, args.show_all)

    footer = []
    footer.append("")
    footer.append("=" * width)
    if total_drift == 0:
        footer.append(f" DRIFT SUMMARY: no differences detected across {len(node_names)} nodes.")
    else:
        footer.append(f" DRIFT SUMMARY: {total_drift} field(s) differ across {len(node_names)} nodes.")
    if not args.show_all:
        footer.append(" Matching fields suppressed — use --show-all to see everything.")
    footer.append("=" * width)

    all_lines_plain = header + [re.sub(r"\033\[\d+m", "", l) for l in body_lines] + footer

    # --- print (colored) ---
    print()
    print(Style.bold("=" * width))
    print(Style.bold(f" CLUSTER DRIFT DETECTOR  ({len(node_names)} nodes, {mode} mode)"))
    print(Style.dim(f" Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"))
    print(Style.dim(f" Nodes: {', '.join(node_names)}"))
    print(Style.bold("=" * width))
    if body_lines:
        for line in body_lines:
            print(line)
    else:
        print("\n   (nothing to compare — check your input files)")
    print()
    print(Style.bold("=" * width))
    if total_drift == 0:
        print(Style.bold(f" DRIFT SUMMARY: no differences detected across {len(node_names)} nodes."))
    else:
        print(Style.bold(f" DRIFT SUMMARY: {total_drift} field(s) differ across {len(node_names)} nodes."))
    if not args.show_all:
        print(Style.dim(" Matching fields suppressed — use --show-all to see everything."))
    print(Style.bold("=" * width))
    print()

    if not args.no_save:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"node_diff_report_{ts}.txt"
        try:
            with open(filename, "w") as f:
                f.write("\n".join(all_lines_plain))
            print(f"Report saved to ./{filename}")
        except PermissionError:
            print(f"Warning: could not write report to ./{filename} (permission denied)")
        except OSError as e:
            print(f"Warning: could not write report to ./{filename} ({e})")

    if args.json:
        drift_export = {
            "nodes": node_names,
            "mode": mode,
            "total_drift": total_drift,
            "sections": {},
        }
        for section, labels in comparison.items():
            section_out = {}
            for label, label_data in labels.items():
                if not has_drift(label_data, node_names) and not args.show_all:
                    continue
                section_out[label] = {n: label_data.get(n, (None, None))[0] for n in node_names}
            if section_out:
                drift_export["sections"][section] = section_out
        try:
            with open(args.json, "w") as f:
                json.dump(drift_export, f, indent=2)
            print(f"JSON report written to {args.json}")
        except PermissionError:
            print(f"Warning: could not write JSON report to {args.json} (permission denied)")
        except OSError as e:
            print(f"Warning: could not write JSON report to {args.json} ({e})")

    print()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nComparison cancelled by user. Exiting.")
        sys.exit(130)
