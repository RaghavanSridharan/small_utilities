# Scheduled Jobs Inspector (`scheduled_jobs`)

A zero-dependency Python diagnostic utility that inspects cron jobs and systemd timers across Linux environments. It aggregates user crontabs, system-wide cron files (`/etc/crontab`, `/etc/cron.d/*`), and systemd timers into a unified report, translating raw cron syntax into human-readable schedules and flagging silent execution failures.

---

## Features

* **Zero Third-Party Dependencies:** Relies strictly on native Python standard modules (`re`, `os`, `glob`, `json`, `subprocess`, `argparse`).
* **Cron Expression Translator:** Automatically parses cron syntax (`0 2 * * *`, `*/15 * * * *`, `@reboot`, `@daily`) into plain English descriptions.
* **Multi-Source Cron Auditing:** Scans individual user crontabs (`crontab -l`), system-wide configurations (`/etc/crontab`), and drop-in directories (`/etc/cron.d/*`).
* **Systemd Timer & Service Verification:** Lists active systemd timers and verifies the `Result` and `ExecMainStatus` of their linked `.service` units to surface hidden failures.
* **Non-Systemd / macOS Resilience:** Falls back gracefully on non-systemd environments (Docker containers, WSL) and macOS without throwing errors.
* **Report Persistence & JSON Export:** Auto-saves timestamped text reports to disk and supports `--json` export for machine readability.

---

## Requirements

* **Operating System:** Linux (RHEL, Ubuntu, Debian, CentOS, SUSE, Arch) or macOS
* **Python Version:** Python 3.6+
* **Permissions:** Standard user access (inspecting other users' crontabs requires elevated privileges)

---

## Usage

### Standard Inspection
```bash
python3 scheduled_jobs.py
