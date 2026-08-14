# Scheduled Jobs Inspector (`scheduled_jobs`)

A zero-dependency Python diagnostic utility that audits all scheduled background tasks across Linux environments. It consolidates user crontabs, system-wide cron files (`/etc/crontab`, `/etc/cron.d/*`), periodic script directories, and `systemd` timers into a single unified report.

It translates raw cron expressions into plain English and flags silent execution failures or overly aggressive execution frequencies.

---

## Features

* **Zero External Dependencies:** Built strictly using native Python standard libraries (`os`, `sys`, `json`, `platform`, `argparse`, `subprocess`).
* **Plain-English Cron Translator:** Converts standard cron syntax (`0 2 * * *`, `*/15 * * * *`, `0,15,30,45`, `@reboot`, `@daily`) into clear human-readable schedules.
* **Comprehensive Cron Auditing:** Inspects current user crontabs (`crontab -l`), other user spool directories (when run as root), system-wide `/etc/crontab`, `/etc/cron.d/*`, and periodic directories (`cron.hourly/daily/weekly/monthly`).
* **@reboot Rollup:** Aggregates all boot-triggered scripts scattered across multiple crontabs into a single dedicated section.
* **Systemd Timer & Service Verification:** Queries `systemd` timers via `systemctl show` and inspects linked `.service` units to surface hidden `Result` failures or non-zero exit codes.
* **Frequency Threshold Warning:** Flags jobs scheduled to execute more frequently than a configurable threshold (default: 15 minutes).
* **Report Persistence & JSON Export:** Auto-saves timestamped text reports to disk and supports `--json` export for machine readability.

---

## Requirements

* **Operating System:** Linux (RHEL, Ubuntu, Debian, CentOS, SUSE, Arch) or macOS (best-effort fallback).
* **Python Version:** Python 3.6+
* **Permissions:** Standard user access (inspecting other users' spool crontabs requires root/sudo).

---

## Usage

### Standard Inspection
```bash
python3 scheduled_jobs.py
