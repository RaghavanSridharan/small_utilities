#!/usr/bin/env python3
"""
Service Health Snapshot
------------------------
Zero-dependency systemd service health check. Answers the question Port
Info and Dev Environment Auditor don't: "what's SUPPOSED to be running
on this box, and is it actually healthy?"

Three layers of signal:
  1. Anything currently in a FAILED state (systemctl --failed) — catches
     the unexpected, whatever it is.
  2. A curated check of common infra services (ssh, docker, k3s, nginx,
     etc.) — catches "the thing I actually care about is quietly down."
  3. Crash-loop detection via restart counts — catches services that
     LOOK active right now but have been flapping.

Falls back cleanly (not a crash) on machines without systemd, e.g.
containers, WSL without systemd enabled, or macOS (best-effort launchd
summary included as a bonus, not the focus).

Usage:
    python3 service_health.py                       # standard snapshot
    python3 service_health.py --inspect nginx,docker # deep-dive specific units
    python3 service_health.py --watch redis,postgres # override curated list
    python3 service_health.py --restart-threshold 5  # tune crash-loop sensitivity
    python3 service_health.py --json out.json
    python3 service_health.py --no-save --no-color
"""

import os
import re
import sys
import json
import shlex
import platform
import argparse
import subprocess
from datetime import datetime
from collections import Counter

# --------------------------------------------------------------------------
# Terminal styling (auto-disables when not a TTY, or with --no-color)
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
# Shared helpers
# --------------------------------------------------------------------------

def run_cmd(cmd, timeout=8):
    try:
        res = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return res.stdout.strip()
    except Exception:
        return ""


def run_argv(args, timeout=8):
    """List-form subprocess call — no shell, so unit names (which come from
    curated lists or user input via --inspect/--watch) are never at risk of
    shell interpretation."""
    try:
        res = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
        return res.stdout.strip()
    except Exception:
        return ""


class Report:
    def __init__(self):
        self.sections = []

    def section(self, title):
        rows = []
        self.sections.append((title, rows))
        return rows

    def to_json(self):
        return {title: [{"label": l, "value": v, "status": k} for l, v, k in rows]
                for title, rows in self.sections}

    def render_lines(self):
        width = 76
        lines = ["=" * width, " SERVICE HEALTH SNAPSHOT",
                  f" Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", "=" * width]
        for title, rows in self.sections:
            lines.append("")
            lines.append(f" {title}")
            lines.append("-" * width)
            if not rows:
                lines.append("   (nothing to report)")
                continue
            label_width = max(len(label) for label, _, _ in rows) + 2
            for label, value, kind in rows:
                lines.append(f"  [{ICONS[kind]}] {label:<{label_width}} {value}")
        lines += ["", "=" * width]
        return lines

    def print(self):
        width = 76
        print()
        print(Style.bold("=" * width))
        print(Style.bold(" SERVICE HEALTH SNAPSHOT"))
        print(Style.dim(f" Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"))
        print(Style.bold("=" * width))
        for title, rows in self.sections:
            print("\n" + Style.cyan(Style.bold(f" {title}")))
            print(Style.dim("-" * width))
            if not rows:
                print(f"   {Style.dim('(nothing to report)')}")
                continue
            label_width = max(len(label) for label, _, _ in rows) + 2
            for label, value, kind in rows:
                print(f"  {icon(kind)} {label:<{label_width}} {value}")
        print()
        print(Style.bold("=" * width))
        print()


# --------------------------------------------------------------------------
# systemd detection
# --------------------------------------------------------------------------

def is_systemd():
    # The canonical check systemd itself uses (equivalent to sd_booted()):
    # this directory only exists when systemd is actually running as PID 1.
    return os.path.isdir("/run/systemd/system")


def get_system_state():
    out = run_cmd("systemctl is-system-running 2>/dev/null")
    state = out or "unknown"
    kind = {"running": "ok", "degraded": "fail", "starting": "warn",
            "maintenance": "warn"}.get(state, "info")
    return state, kind


# --------------------------------------------------------------------------
# Failed units — catches the unexpected
# --------------------------------------------------------------------------

def get_failed_units():
    out = run_cmd("systemctl --failed --no-legend --plain --no-pager 2>/dev/null")
    units = []
    for line in out.splitlines():
        parts = line.split(maxsplit=4)
        if len(parts) >= 4:
            unit, load, active, sub = parts[0], parts[1], parts[2], parts[3]
            desc = parts[4] if len(parts) > 4 else ""
            units.append({"unit": unit, "load": load, "active": active, "sub": sub, "desc": desc})
    return units


# --------------------------------------------------------------------------
# Overall service counts
# --------------------------------------------------------------------------

def get_service_counts():
    out = run_cmd("systemctl list-units --type=service --all --no-legend --plain --no-pager 2>/dev/null")
    counter = Counter()
    total = 0
    for line in out.splitlines():
        parts = line.split(maxsplit=4)
        if len(parts) >= 4:
            total += 1
            counter[parts[2]] += 1  # ACTIVE column
    return total, counter


# --------------------------------------------------------------------------
# Per-unit property inspection (structured, not table-parsed)
# --------------------------------------------------------------------------

def get_unit_properties(unit, props):
    if not unit.endswith(".service"):
        unit_full = unit + ".service"
    else:
        unit_full = unit
    out = run_argv(["systemctl", "show", unit_full, f"--property={','.join(props)}", "--no-pager"])
    result = {}
    for line in out.splitlines():
        if "=" in line:
            k, _, v = line.partition("=")
            result[k] = v
    return result


def human_bytes(value):
    try:
        n = int(value)
    except (ValueError, TypeError):
        return None
    if n <= 0:
        return None
    for unit in ["B", "KB", "MB", "GB"]:
        if n < 1024:
            return f"{n:.0f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def human_since(timestamp_str):
    """systemd timestamps look like 'Thu 2026-08-14 09:15:31 UTC'. Python's
    %Z directive is unreliable across locales/timezone abbreviations, so
    after a quick native attempt, fall back to GNU `date -d` (systemd only
    runs on Linux, so coreutils' date is a safe bet) which parses timezone
    strings far more robustly than manually enumerating strptime formats.
    Falls back to the raw string if nothing can parse it, since that's
    still more useful than nothing."""
    if not timestamp_str or timestamp_str in ("n/a", ""):
        return None

    dt = None
    for fmt in ("%a %Y-%m-%d %H:%M:%S %Z", "%a %Y-%m-%d %H:%M:%S"):
        try:
            dt = datetime.strptime(timestamp_str, fmt)
            break
        except ValueError:
            continue

    if dt is None:
        epoch = run_cmd(f"date -d {shlex.quote(timestamp_str)} +%s 2>/dev/null")
        if epoch.isdigit():
            try:
                dt = datetime.fromtimestamp(int(epoch))
            except (ValueError, OSError):
                dt = None

    if dt is None:
        return timestamp_str

    delta = datetime.now() - dt
    secs = int(delta.total_seconds())
    if secs < 0:
        return timestamp_str
    days, rem = divmod(secs, 86400)
    hours, rem = divmod(rem, 3600)
    minutes = rem // 60
    if days:
        return f"{days}d {hours}h ago"
    if hours:
        return f"{hours}h {minutes}m ago"
    return f"{minutes}m ago"


# --------------------------------------------------------------------------
# Curated "expected services" check
# --------------------------------------------------------------------------

DEFAULT_EXPECTED = {
    "SSH daemon": ["sshd", "ssh"],
    "Cron": ["cron", "crond"],
    "Rsyslog": ["rsyslog"],
    "Journald": ["systemd-journald"],
    "Network manager": ["NetworkManager", "systemd-networkd"],
    "Docker": ["docker"],
    "containerd": ["containerd"],
    "K3s": ["k3s", "k3s-agent"],
    "Kubelet": ["kubelet"],
    "nginx": ["nginx"],
    "Apache": ["apache2", "httpd"],
}

PROPS = ["LoadState", "ActiveState", "SubState", "NRestarts",
         "ExecMainStartTimestamp", "MemoryCurrent", "MainPID"]


def check_curated_service(label, variants, restart_threshold):
    tried = []
    for name in variants:
        props = get_unit_properties(name, PROPS)
        tried.append(name)
        if props.get("LoadState") == "loaded":
            return build_service_row(label, name, props, restart_threshold)
    return (label, f"not installed (checked: {', '.join(tried)})", "info")


def build_service_row(label, unit_name, props, restart_threshold):
    active = props.get("ActiveState", "unknown")
    sub = props.get("SubState", "")
    restarts = props.get("NRestarts", "0")
    try:
        restart_count = int(restarts)
    except ValueError:
        restart_count = 0

    if active == "failed":
        kind, status = "fail", f"FAILED ({sub})"
    elif active == "active":
        kind, status = "ok", f"running ({sub})"
    elif active in ("activating", "reloading", "deactivating"):
        kind, status = "warn", f"{active} ({sub})"
    elif active == "inactive":
        kind, status = "warn", "installed but not running (inactive)"
    else:
        kind, status = "info", f"{active} ({sub})"

    if restart_count >= restart_threshold and kind == "ok":
        kind = "warn"
        status += f" — restarted {restart_count}x (possible crash loop)"
    elif restart_count > 0:
        status += f" — {restart_count} restart(s)"

    since = human_since(props.get("ExecMainStartTimestamp", ""))
    if since and active == "active":
        status += f", up {since}"

    return (f"{label} ({unit_name}.service)", status, kind)


def collect_expected_services_section(report, expected_map, restart_threshold):
    rows = report.section("EXPECTED SERVICES")
    for label, variants in expected_map.items():
        rows.append(check_curated_service(label, variants, restart_threshold))


# --------------------------------------------------------------------------
# Deep-dive inspection for specific units (--inspect)
# --------------------------------------------------------------------------

INSPECT_PROPS = PROPS + ["FragmentPath", "UnitFileState", "Restart", "ExecMainPID"]


def collect_inspect_sections(report, units):
    for unit in units:
        rows = report.section(f"INSPECT: {unit}")
        props = get_unit_properties(unit, INSPECT_PROPS)
        if props.get("LoadState") != "loaded":
            rows.append(("Status", f"unit not found (checked {unit}.service)", "warn"))
            continue
        rows.append(("Load state", props.get("LoadState", "unknown"), "info"))
        rows.append(("Active state", f"{props.get('ActiveState','?')} ({props.get('SubState','?')})",
                      "ok" if props.get("ActiveState") == "active" else "warn"))
        rows.append(("Unit file", props.get("FragmentPath", "unknown"), "info"))
        rows.append(("Enabled at boot", props.get("UnitFileState", "unknown"), "info"))
        rows.append(("Main PID", props.get("MainPID", "0"), "info"))
        rows.append(("Restart policy", props.get("Restart", "unknown"), "info"))
        restarts = props.get("NRestarts", "0")
        rows.append(("Restart count", restarts, "warn" if restarts not in ("0", "") else "ok"))
        mem = human_bytes(props.get("MemoryCurrent"))
        rows.append(("Memory (current)", mem or "not set / not running", "info"))
        since = human_since(props.get("ExecMainStartTimestamp", ""))
        rows.append(("Running since", since or "unknown", "info"))


# --------------------------------------------------------------------------
# macOS bonus — best-effort launchd summary (not the focus of this tool)
# --------------------------------------------------------------------------

def collect_launchd_section(report):
    rows = report.section("LAUNCHD SERVICES (macOS best-effort)")
    out = run_cmd("launchctl list 2>/dev/null")
    if not out:
        rows.append(("launchctl", "unavailable or returned nothing", "warn"))
        return
    total, crashed = 0, []
    for line in out.splitlines()[1:]:  # skip header
        parts = line.split(maxsplit=2)
        if len(parts) < 3:
            continue
        pid, status, label = parts[0], parts[1], parts[2]
        total += 1
        if pid == "-" and status not in ("0", "-"):
            crashed.append((label, status))
    rows.append(("Total loaded services", str(total), "info"))
    if crashed:
        rows.append((f"Non-zero last exit ({len(crashed)})", "see below — not necessarily currently broken", "warn"))
        for label, status in crashed[:20]:
            rows.append((f"  {label}", f"last exit code {status}", "warn"))
    else:
        rows.append(("Services with nonzero last exit", "none found", "ok"))


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def parse_args():
    p = argparse.ArgumentParser(description="Service Health Snapshot — systemd-aware, zero dependencies.")
    p.add_argument("--inspect", metavar="UNIT,UNIT,...",
                    help="Deep-dive specific units (comma-separated, .service suffix optional).")
    p.add_argument("--watch", metavar="UNIT,UNIT,...",
                    help="Override the default curated 'expected services' list entirely.")
    p.add_argument("--restart-threshold", type=int, default=3,
                    help="Flag a currently-active service as a possible crash loop if NRestarts >= this (default: 3).")
    p.add_argument("--json", metavar="FILE", help="Also write the report as JSON to FILE.")
    p.add_argument("--no-save", action="store_true", help="Don't write the timestamped .txt report to disk.")
    p.add_argument("--no-color", action="store_true", help="Disable colored output.")
    return p.parse_args()


def save_text_report(report):
    """Writes the timestamped .txt report; degrades to a warning instead of
    a crash if the current directory isn't writable (e.g. running from a
    read-only path like /usr/local/bin)."""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"service_health_report_{ts}.txt"
    try:
        with open(filename, "w") as f:
            f.write("\n".join(report.render_lines()))
        print(f"Report saved to ./{filename}")
    except PermissionError:
        print(f"Warning: could not write report to ./{filename} (permission denied)")
    except OSError as e:
        print(f"Warning: could not write report to ./{filename} ({e})")


def save_json_report(report, path):
    try:
        with open(path, "w") as f:
            json.dump(report.to_json(), f, indent=2)
        print(f"JSON report written to {path}")
    except PermissionError:
        print(f"Warning: could not write JSON report to {path} (permission denied)")
    except OSError as e:
        print(f"Warning: could not write JSON report to {path} ({e})")


def main():
    args = parse_args()
    if args.no_color:
        Style.enabled = False

    report = Report()

    if not is_systemd():
        rows = report.section("SYSTEMD")
        rows.append(("systemd", "not detected on this system (/run/systemd/system absent)", "warn"))
        rows.append(("What this means", "this box isn't running systemd as PID 1 — common in "
                                          "containers, WSL without systemd, or non-systemd distros", "info"))
        if platform.system() == "Darwin":
            rows.append(("macOS detected", "showing a best-effort launchd summary instead", "info"))
            collect_launchd_section(report)
        report.print()
        if not args.no_save:
            save_text_report(report)
            print()
        return

    state, kind = get_system_state()
    rows = report.section("SYSTEMD OVERVIEW")
    rows.append(("systemd version", (run_cmd("systemctl --version").splitlines() or ["unknown"])[0], "info"))
    rows.append(("System state", state, kind))

    total, counts = get_service_counts()
    rows.append(("Total service units", str(total), "info"))
    for state_name in ["active", "inactive", "failed", "activating"]:
        if counts.get(state_name):
            k = "fail" if state_name == "failed" else "info"
            rows.append((f"  {state_name}", str(counts[state_name]), k))

    failed_rows = report.section("FAILED SERVICES")
    failed = get_failed_units()
    if failed:
        for f in failed:
            failed_rows.append((f["unit"], f"{f['active']}/{f['sub']} — {f['desc']}", "fail"))
    else:
        failed_rows.append(("Failed units", "none — nothing in a failed state", "ok"))

    if args.watch:
        expected_map = {name.strip(): [name.strip()] for name in args.watch.split(",") if name.strip()}
    else:
        expected_map = DEFAULT_EXPECTED
    collect_expected_services_section(report, expected_map, args.restart_threshold)

    if args.inspect:
        units = [u.strip() for u in args.inspect.split(",") if u.strip()]
        collect_inspect_sections(report, units)

    report.print()

    if not args.no_save:
        save_text_report(report)

    if args.json:
        save_json_report(report, args.json)

    print()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nSnapshot cancelled by user. Exiting.")
        sys.exit(130)
