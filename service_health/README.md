# Service Health Snapshot (`service_health`)

A zero-dependency Python diagnostic utility to inspect systemd service health, detect failed or crashed daemons, identify crash-looping background processes, and monitor core infrastructure units across Linux hosts.

It answers the critical observability question: **"What is supposed to be running on this box, and is it actually healthy?"**

---

## Features

* **Zero Third-Party Dependencies:** Built exclusively with standard Python standard libraries (`argparse`, `json`, `platform`, `subprocess`, `shlex`).
* **Failed Unit Detection:** Directly queries `systemctl --failed` to catch unexpected service crashes or unit failures instantly.
* **Curated Service Monitor:** Automatically checks for standard core infrastructure services (`sshd`, `docker`, `containerd`, `k3s`, `kubelet`, `nginx`, `cron`, `rsyslog`, `journald`, etc.).
* **Crash-Loop & Flapping Detection:** Tracks unit restart counts (`NRestarts`) and flags active services as flapping if they exceed configurable thresholds.
* **Deep-Dive Unit Inspection (`--inspect`):** Provides detailed metrics (memory usage, PID, unit file paths, enable status on boot, restart policy, uptime) for target services.
* **Non-Systemd / macOS Fallback:** Safely detects non-systemd environments (WSL, Docker containers) and provides a best-effort `launchd` service summary on macOS without crashing.
* **Report Persistence & JSON Export:** Auto-saves timestamped plain-text diagnostic logs to disk and supports `--json` exports for machine-readable logging or Slack alerting.

---

## Requirements

* **Operating System:** Linux distributions utilizing `systemctl` (RHEL, Ubuntu, Debian, CentOS, SUSE, Arch) or macOS (best-effort fallback).
* **Python Version:** Python 3.6+
* **Permissions:** Standard user access.

---

## Usage

### Standard Health Snapshot
```bash
python3 service_health.py
