# Environment Details (`env_details`)

A zero-dependency Python diagnostic utility designed for Day 1 onboarding, jump boxes, bastion hosts, and new developer workstations. It audits developer tooling, PATH configurations, Git identities, DNS resolution, and system metrics into a clear, actionable report. Security-sensitive metrics (sudo privileges, active sessions, firewalls) are opt-in to keep standard reports safe for sharing.

---

## Features

* **Zero Third-Party Dependencies:** Relies exclusively on native Python standard libraries (`argparse`, `json`, `platform`, `subprocess`, `socket`, `shutil`).
* **Git Identity & Security Audit:** Checks global `user.name` and `user.email`, warns if personal email domains (`@gmail.com`, etc.) are configured for work commits, checks default branches, and inspects `~/.ssh` public keys.
* **PATH & Package Manager Diagnostics:** Identifies broken or non-existent directories on `$PATH`, catches duplicate PATH entries, and checks package managers (`brew`, `apt`, `dnf`, `yum`, etc.).
* **DNS Sanity Checks:** Validates network reachability to common package registries (`github.com`, `pypi.org`, `registry.npmjs.org`).
* **Tool Matrix:** Scans for installed developer tools (`python3`, `node`, `docker`, `git`, `kubectl`, `terraform`, `aws`, `gcloud`, `curl`, `openssl`) and retrieves their version strings.
* **Opt-In Security Posture (`--security`):** Inspects passwordless `sudo` privileges, active SSH daemons, total logged-in sessions, firewall state, SELinux mode, and system `ulimit` thresholds.
* **JSON Export & Styling:** Supports colored terminal output with standard status indicators (`✔`, `!`, `✘`, `•`) and machine-readable JSON exports.

---

## Requirements

* **Operating System:** Linux (RHEL, Ubuntu, Debian, CentOS) or macOS
* **Python Version:** Python 3.6+
* **Permissions:** Standard user access

---

## Usage

### Standard Dev Audit (Safe for sharing/Slack)
```bash
python3 env_details.py
