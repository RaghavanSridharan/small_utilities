# Small Utilities

A curated collection of zero-dependency, lightweight command-line utilities designed to automate routine developer workflows, optimize storage hygiene, and provide instant host observability.

---

## Included Tools

| Utility | Language | Description |
| :--- | :--- | :--- |
| [**Downloads Organizer**](./downloads_organizer) | Python | Automatically categorizes messy download folders into structured subdirectories by file extension. |
| [**Large File Finder**](./large_file_finder) | Python | Scans directories to locate space-consuming files and hidden virtual disk allocations. |
| [**YouTube Unsubscribe**](./youtube_unsubscribe) | JavaScript | Browser console automation script to bulk unsubscribe from YouTube channels. |
| [**Port Info**](./port_info) | Python | CLI diagnostic tool to analyze active TCP ports, process chains, resource usage, and Docker bindings. |
| [**Environment Details**](./env_details) | Python | Day 1 environment auditor for jump boxes and new dev machines to inspect PATH, DNS, Git identity, tooling, and security posture. |
| [**Service Health Snapshot**](./service_health) | Python | Systemd-aware CLI diagnostic tool to detect failed services, crash loops, and monitor critical background daemons. |
| [**Scheduled Jobs Inspector**](./scheduled_jobs) | Python | CLI diagnostic tool to audit crontabs and systemd timers, translate cron expressions, and flag silent job failures. |

---

## Key Principles

* **Zero Third-Party Dependencies:** All scripts rely exclusively on native language standard libraries and built-in system utilities.
* **Cross-Platform Compatibility:** Designed and tested for Linux (RHEL, Ubuntu, Debian, CentOS) and macOS operating environments.
* **Safe & Read-Only First:** Built with explicit validation checks, non-destructive execution defaults, and clear confirmations prior to executing file modifications.

---
## 📄 License

This repository is licensed under the [MIT License](LICENSE).

---

## Getting Started

Clone the repository and execute any tool directly:

```bash
git clone [https://github.com/your-username/small_utilities.git](https://github.com/your-username/small_utilities.git)
cd small_utilities/service_health
python3 service_health.py
