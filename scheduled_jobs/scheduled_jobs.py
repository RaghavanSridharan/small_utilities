#!/usr/bin/env python3
"""
Scheduled Jobs Inspector
--------------------------
Zero-dependency inspector for everything scheduled to run on this box —
cron (user, system-wide, /etc/cron.d, the periodic script dirs) and
systemd timers — translated into plain English instead of raw cron
syntax, with failures and easy-to-miss @reboot entries called out.

Completes the trilogy: Port Info (what's listening) -> Service Health
Snapshot (what's running now) -> Scheduled Jobs Inspector (what's
GOING to run). Read-only throughout — never edits crontabs or timers,
only reports on them.

Usage:
    python3 scheduled_jobs.py                        # full report
    python3 scheduled_jobs.py --no-other-users        # skip other users' crontabs
    python3 scheduled_jobs.py --frequent-threshold 5  # tune the "runs too often?" flag
    python3 scheduled_jobs.py --json out.json
    python3 scheduled_jobs.py --no-save --no-color
"""

import os
import sys
import json
import platform
import argparse
import subprocess
from datetime import datetime

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
        width = 78
        lines = ["=" * width, " SCHEDULED JOBS INSPECTOR",
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
        width = 78
        print()
        print(Style.bold("=" * width))
        print(Style.bold(" SCHEDULED JOBS INSPECTOR"))
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


def save_text_report(report, prefix="scheduled_jobs_report"):
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{prefix}_{ts}.txt"
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


# --------------------------------------------------------------------------
# Cron expression -> plain English
# --------------------------------------------------------------------------

SPECIAL_MAP = {
    "@reboot": "runs once, at every system boot",
    "@yearly": "runs once a year (Jan 1st, 12:00 AM)",
    "@annually": "runs once a year (Jan 1st, 12:00 AM)",
    "@monthly": "runs once a month (1st, 12:00 AM)",
    "@weekly": "runs once a week (Sunday, 12:00 AM)",
    "@daily": "runs once a day (12:00 AM)",
    "@midnight": "runs once a day (12:00 AM)",
    "@hourly": "runs every hour (at :00)",
}

WEEKDAY_NAMES = {0: "Sunday", 1: "Monday", 2: "Tuesday", 3: "Wednesday",
                  4: "Thursday", 5: "Friday", 6: "Saturday", 7: "Sunday"}


def format_time(hour, minute):
    h, m = int(hour), int(minute)
    period = "AM" if h < 12 else "PM"
    h12 = h % 12 or 12
    return f"{h12}:{m:02d} {period}"


def evenly_spaced_step(field, modulus):
    """Detects lists like '0,15,30,45' and expresses them as 'every 15
    minutes' instead of a raw comma list — handles the common case where
    someone wrote out a list instead of using a */N step."""
    if "," not in field:
        return None
    parts = field.split(",")
    if not all(p.isdigit() for p in parts):
        return None
    nums = sorted(int(p) for p in parts)
    if len(nums) < 2 or nums[0] != 0:
        return None
    diffs = {nums[i + 1] - nums[i] for i in range(len(nums) - 1)}
    if len(diffs) != 1:
        return None
    step = diffs.pop()
    if modulus - nums[-1] == step:
        return step
    return None


def describe_cron(minute, hour, dom, month, dow):
    """Returns a plain-English description for common cron patterns, or
    None if the expression is too complex to confidently describe — the
    caller falls back to showing the raw expression rather than guessing."""
    every = lambda f: f == "*"
    is_weekday_range = dow in ("1-5", "MON-FRI")
    is_weekend_set = dow in ("0,6", "6,0", "SAT,SUN", "SUN,SAT")

    # every N minutes (step form)
    if minute.startswith("*/") and every(hour) and every(dom) and every(month) and every(dow):
        n = minute[2:]
        if n.isdigit():
            return f"runs every {n} minute{'s' if n != '1' else ''}"

    # every N minutes (comma-list form)
    if every(hour) and every(dom) and every(month) and every(dow):
        step = evenly_spaced_step(minute, 60)
        if step:
            return f"runs every {step} minutes"

    # every N hours at a specific minute
    if minute.isdigit() and hour.startswith("*/") and every(dom) and every(month) and every(dow):
        n = hour[2:]
        if n.isdigit():
            return f"runs every {n} hour{'s' if n != '1' else ''}, at minute {minute}"

    # daily at a specific time
    if minute.isdigit() and hour.isdigit() and every(dom) and every(month) and every(dow):
        return f"runs daily at {format_time(hour, minute)}"

    # specific minute, every hour (e.g. "17 * * * *" -> runs at :17 past every hour)
    if minute.isdigit() and every(hour) and every(dom) and every(month) and every(dow):
        return f"runs every hour, at :{int(minute):02d}"

    # weekdays only
    if minute.isdigit() and hour.isdigit() and every(dom) and every(month) and is_weekday_range:
        return f"runs on weekdays at {format_time(hour, minute)}"

    # weekends only
    if minute.isdigit() and hour.isdigit() and every(dom) and every(month) and is_weekend_set:
        return f"runs on weekends at {format_time(hour, minute)}"

    # specific day of week
    if minute.isdigit() and hour.isdigit() and every(dom) and every(month) and dow.isdigit():
        day = WEEKDAY_NAMES.get(int(dow))
        if day:
            return f"runs every {day} at {format_time(hour, minute)}"

    # specific day of month, every month
    if minute.isdigit() and hour.isdigit() and dom.isdigit() and every(month) and every(dow):
        suffix = "th" if 11 <= int(dom) <= 13 else {1: "st", 2: "nd", 3: "rd"}.get(int(dom) % 10, "th")
        return f"runs monthly on the {dom}{suffix} at {format_time(hour, minute)}"

    # specific day + month (annual)
    if minute.isdigit() and hour.isdigit() and dom.isdigit() and month.isdigit() and every(dow):
        return f"runs annually on {month}/{dom} at {format_time(hour, minute)}"

    return None


def parse_cron_line(line, has_user_field=False):
    """Parses a single crontab line. has_user_field=True for system-style
    files (/etc/crontab, /etc/cron.d/*) which have an extra 'user' column
    between the schedule and the command."""
    line = line.rstrip("\n")
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        return None

    if stripped.startswith("@"):
        parts = stripped.split(None, 2 if has_user_field else 1)
        if has_user_field and len(parts) >= 3:
            keyword, user, command = parts[0], parts[1], parts[2]
        elif not has_user_field and len(parts) >= 2:
            keyword, user, command = parts[0], None, parts[1]
        else:
            return None
        desc = SPECIAL_MAP.get(keyword, f"special schedule: {keyword}")
        return {"schedule": keyword, "user": user, "command": command,
                "description": desc, "raw": stripped, "is_reboot": keyword == "@reboot"}

    field_count = 6 if has_user_field else 5
    fields = stripped.split(None, field_count)
    if len(fields) < field_count + 1:
        return None

    if has_user_field:
        minute, hour, dom, month, dow, user, command = fields
    else:
        minute, hour, dom, month, dow, command = fields
        user = None

    try:
        desc = describe_cron(minute, hour, dom, month, dow)
    except Exception:
        desc = None

    schedule = f"{minute} {hour} {dom} {month} {dow}"
    return {"schedule": schedule, "user": user, "command": command,
            "description": desc, "raw": stripped, "is_reboot": False,
            "minute": minute, "hour": hour, "dom": dom, "month": month, "dow": dow}


# --------------------------------------------------------------------------
# Frequency flagging
# --------------------------------------------------------------------------

def job_interval_minutes(entry):
    """Best-effort: returns an approximate run interval in minutes for
    frequency flagging, or None if it can't confidently tell (e.g. @reboot,
    complex expressions). Deliberately conservative — false negatives are
    fine here, false positives just add noise."""
    if entry.get("is_reboot"):
        return None
    minute = entry.get("minute", "")
    hour = entry.get("hour", "")
    if minute.startswith("*/") and hour == "*":
        try:
            return int(minute[2:])
        except ValueError:
            return None
    if minute == "*" and hour == "*":
        return 1
    return None


# --------------------------------------------------------------------------
# Cron sources
# --------------------------------------------------------------------------

def get_current_user_cron():
    out = run_cmd("crontab -l 2>/dev/null")
    if not out or "no crontab" in out.lower():
        return []
    entries = []
    for line in out.splitlines():
        e = parse_cron_line(line, has_user_field=False)
        if e:
            entries.append(e)
    return entries


def get_other_users_cron():
    """Reads cron spool files directly rather than shelling out to
    `crontab -l -u <user>` per user — faster, and avoids noisy errors for
    users with no crontab. Requires root to read other users' files;
    silently skips ones we can't read rather than erroring."""
    spool_dirs = ["/var/spool/cron/crontabs", "/var/spool/cron"]
    results = {}  # username -> entries
    for spool_dir in spool_dirs:
        if not os.path.isdir(spool_dir):
            continue
        try:
            usernames = os.listdir(spool_dir)
        except PermissionError:
            continue
        for username in usernames:
            path = os.path.join(spool_dir, username)
            if not os.path.isfile(path) or username == "root":
                continue  # root's own crontab is covered by get_current_user_cron when run as root
            try:
                with open(path) as f:
                    lines = f.readlines()
            except (PermissionError, OSError):
                continue
            entries = [e for e in (parse_cron_line(l, has_user_field=False) for l in lines) if e]
            if entries:
                results[username] = entries
        break  # only read whichever spool dir exists first
    return results


def get_system_cron():
    """/etc/crontab and every file in /etc/cron.d/ — both use the
    6-field-plus-user format."""
    entries = []
    for path in ["/etc/crontab"]:
        if os.path.isfile(path):
            try:
                with open(path) as f:
                    for line in f:
                        e = parse_cron_line(line, has_user_field=True)
                        if e:
                            e["source"] = "/etc/crontab"
                            entries.append(e)
            except (PermissionError, OSError):
                pass

    cron_d = "/etc/cron.d"
    if os.path.isdir(cron_d):
        try:
            files = sorted(os.listdir(cron_d))
        except PermissionError:
            files = []
        for fname in files:
            path = os.path.join(cron_d, fname)
            if not os.path.isfile(path):
                continue
            try:
                with open(path) as f:
                    for line in f:
                        e = parse_cron_line(line, has_user_field=True)
                        if e:
                            e["source"] = f"/etc/cron.d/{fname}"
                            entries.append(e)
            except (PermissionError, OSError):
                continue
    return entries


def get_periodic_script_dirs():
    """cron.hourly/daily/weekly/monthly aren't crontab syntax — they're
    directories of executable scripts run via run-parts, on a schedule
    controlled by /etc/crontab or anacron. We just list what's queued up
    in each, since that's often forgotten territory."""
    dirs = {
        "/etc/cron.hourly": "hourly",
        "/etc/cron.daily": "daily",
        "/etc/cron.weekly": "weekly",
        "/etc/cron.monthly": "monthly",
    }
    results = {}
    for path, label in dirs.items():
        if not os.path.isdir(path):
            continue
        try:
            scripts = sorted(f for f in os.listdir(path) if not f.startswith("."))
        except PermissionError:
            continue
        if scripts:
            results[label] = scripts
    return results


# --------------------------------------------------------------------------
# systemd timers — structured via `systemctl show`, not fragile table parsing
# --------------------------------------------------------------------------

def is_systemd():
    return os.path.isdir("/run/systemd/system")


def get_timer_units():
    out = run_cmd("systemctl list-units --type=timer --all --no-legend --plain --no-pager 2>/dev/null")
    units = []
    for line in out.splitlines():
        parts = line.split(maxsplit=4)
        if len(parts) >= 1:
            units.append(parts[0])
    return units


def get_unit_properties(unit, props):
    out = run_argv(["systemctl", "show", unit, f"--property={','.join(props)}", "--no-pager"])
    result = {}
    for line in out.splitlines():
        if "=" in line:
            k, _, v = line.partition("=")
            result[k] = v
    return result


def usec_to_datetime(usec_str):
    try:
        usec = int(usec_str)
    except (ValueError, TypeError):
        return None
    if usec <= 0:
        return None
    try:
        return datetime.fromtimestamp(usec / 1_000_000)
    except (ValueError, OSError):
        return None


def humanize_delta(dt, now=None):
    now = now or datetime.now()
    delta = dt - now
    secs = int(delta.total_seconds())
    future = secs >= 0
    secs = abs(secs)
    days, rem = divmod(secs, 86400)
    hours, rem = divmod(rem, 3600)
    minutes = rem // 60
    if days:
        s = f"{days}d {hours}h"
    elif hours:
        s = f"{hours}h {minutes}m"
    else:
        s = f"{minutes}m"
    return (f"in {s}" if future else f"{s} ago")


TIMER_PROPS = ["LoadState", "ActiveState", "NextElapseUSecRealtime",
               "LastTriggerUSec", "Unit"]
SERVICE_RESULT_PROPS = ["Result", "ActiveState", "ExecMainStatus"]


def collect_timer_row(timer_unit):
    props = get_unit_properties(timer_unit, TIMER_PROPS)
    if props.get("LoadState") != "loaded":
        return (timer_unit, "unit not found", "warn")

    next_dt = usec_to_datetime(props.get("NextElapseUSecRealtime"))
    next_str = f"next: {humanize_delta(next_dt)}" if next_dt else "next: not scheduled"

    associated_service = props.get("Unit", "")
    last_str = "last: unknown"
    kind = "info"
    if associated_service:
        svc_props = get_unit_properties(associated_service, SERVICE_RESULT_PROPS)
        result = svc_props.get("Result", "")
        if result == "success":
            last_str, kind = "last: success", "ok"
        elif result and result != "success":
            last_str, kind = f"last: FAILED ({result})", "fail"
        else:
            last_str, kind = "last: never run yet", "info"

    return (timer_unit, f"{next_str}   {last_str}", kind)


def collect_timers_section(report):
    rows = report.section("SYSTEMD TIMERS")
    if not is_systemd():
        rows.append(("systemd", "not detected on this system — skipping timers", "info"))
        return 0, 0
    units = get_timer_units()
    if not units:
        rows.append(("Timers", "none found", "info"))
        return 0, 0
    failed = 0
    for unit in units:
        label, value, kind = collect_timer_row(unit)
        rows.append((label, value, kind))
        if kind == "fail":
            failed += 1
    return len(units), failed


# --------------------------------------------------------------------------
# Rendering cron entries into report rows
# --------------------------------------------------------------------------

def cron_row(entry, frequent_threshold, label_prefix=""):
    desc = entry.get("description")
    raw = entry["raw"]
    command = entry.get("command", "").strip()
    label = command[:44] + ("..." if len(command) > 44 else "")
    if label_prefix:
        label = f"{label_prefix}{label}"

    interval = job_interval_minutes(entry)
    kind = "ok"
    if desc:
        value = desc
    else:
        value = f"custom schedule — {raw.split(None, 5)[0:5] and ' '.join(raw.split()[:5])}"
        kind = "info"

    if interval is not None and interval < frequent_threshold:
        kind = "warn"
        value += f"  (runs every {interval}m — verify this interval is intentional)"

    return (label, value, kind)


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def parse_args():
    p = argparse.ArgumentParser(description="Scheduled Jobs Inspector — cron + systemd timers, zero dependencies.")
    p.add_argument("--no-other-users", action="store_true",
                    help="Skip scanning other users' crontabs (only relevant when run as root).")
    p.add_argument("--frequent-threshold", type=int, default=15,
                    help="Flag cron jobs running more often than this many minutes (default: 15).")
    p.add_argument("--json", metavar="FILE", help="Also write the report as JSON to FILE.")
    p.add_argument("--no-save", action="store_true", help="Don't write the timestamped .txt report to disk.")
    p.add_argument("--no-color", action="store_true", help="Disable colored output.")
    return p.parse_args()


def main():
    args = parse_args()
    if args.no_color:
        Style.enabled = False

    report = Report()
    all_reboot_entries = []
    total_cron_jobs = 0

    # --- current user's cron ---
    current_user = run_cmd("whoami") or "current user"
    rows = report.section(f"CRON — CURRENT USER ({current_user})")
    current_entries = get_current_user_cron()
    if current_entries:
        for e in current_entries:
            rows.append(cron_row(e, args.frequent_threshold))
            total_cron_jobs += 1
            if e.get("is_reboot"):
                all_reboot_entries.append((f"{current_user}: {e['command'][:50]}", e["raw"]))
    else:
        rows.append(("Cron jobs", "none found for this user", "info"))

    # --- other users' cron (root only) ---
    if not args.no_other_users:
        other_cron = get_other_users_cron()
        if other_cron:
            rows2 = report.section("CRON — OTHER USERS")
            for username, entries in sorted(other_cron.items()):
                for e in entries:
                    row = cron_row(e, args.frequent_threshold, label_prefix=f"[{username}] ")
                    rows2.append(row)
                    total_cron_jobs += 1
                    if e.get("is_reboot"):
                        all_reboot_entries.append((f"{username}: {e['command'][:50]}", e["raw"]))
        elif run_cmd("whoami") == "root":
            rows2 = report.section("CRON — OTHER USERS")
            rows2.append(("Other users' crontabs", "none found", "info"))

    # --- system-wide cron ---
    rows3 = report.section("CRON — SYSTEM WIDE (/etc/crontab, /etc/cron.d/*)")
    system_entries = get_system_cron()
    if system_entries:
        for e in system_entries:
            label_prefix = f"[{e.get('source','')}] "
            row = cron_row(e, args.frequent_threshold, label_prefix=label_prefix)
            rows3.append(row)
            total_cron_jobs += 1
            if e.get("is_reboot"):
                all_reboot_entries.append((f"{e.get('source','')}: {e['command'][:50]}", e["raw"]))
    else:
        rows3.append(("System cron entries", "none found", "info"))

    # --- periodic script dirs ---
    rows4 = report.section("PERIODIC SCRIPT DIRS (cron.hourly/daily/weekly/monthly)")
    periodic = get_periodic_script_dirs()
    if periodic:
        for label, scripts in periodic.items():
            rows4.append((f"{label} ({len(scripts)} script{'s' if len(scripts) != 1 else ''})",
                           ", ".join(scripts), "info"))
            total_cron_jobs += len(scripts)
    else:
        rows4.append(("Periodic script dirs", "none found / empty", "info"))

    # --- @reboot rollup (easy to miss when scattered across sections) ---
    if all_reboot_entries:
        rows5 = report.section("@REBOOT ENTRIES (rolled up from all sources above)")
        for label, raw in all_reboot_entries:
            rows5.append((label, raw, "info"))

    # --- systemd timers ---
    timer_count, timer_failures = collect_timers_section(report)

    # --- summary ---
    summary = report.section("SUMMARY")
    summary.append(("Total scheduled jobs", f"{total_cron_jobs} cron/periodic, {timer_count} systemd timers", "info"))
    if timer_failures:
        summary.append(("Timers with last-run failures", str(timer_failures), "fail"))
    else:
        summary.append(("Timers with last-run failures", "none", "ok"))
    if all_reboot_entries:
        summary.append(("@reboot entries found", str(len(all_reboot_entries)), "info"))

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
        print("\n\nInspection cancelled by user. Exiting.")
        sys.exit(130)
