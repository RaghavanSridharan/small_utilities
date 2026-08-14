# small_utilities
Everyday useful utilities
# 🛠️ Small Utilities & Productivity Tools

A collection of lightweight, zero-dependency automation scripts and utilities designed to solve everyday friction points.

---

## Included Tools

| Utility | Language | Description |
| :--- | :--- | :--- |
| [**Downloads Organizer**](./downloads_organizer) | Python | Automatically categorizes messy download folders into structured subdirectories by file extension. |
| [**Large File Finder**](./large_file_finder) | Python | Scans directories to locate space-consuming files and hidden virtual disk allocations. |
| [**YouTube Unsubscribe**](./youtube_unsubscribe) | JavaScript | Browser console automation script to bulk unsubscribe from YouTube channels. |
| [**Port Info**](./port_info) | Python | CLI diagnostic tool to analyze active TCP ports, process chains, resource usage, and Docker bindings. |
| [**Environment Details**](./env_details) | Python | CLI auditor for jump boxes and new dev machines to inspect PATH, DNS, Git identity, tooling, and security posture. |
| [**Scheduled Jobs Inspector**](./scheduled_jobs) | Python | CLI diagnostic tool to audit crontabs and systemd timers, translate cron expressions, and flag silent job failures. |

---

## Key Principles

* **Zero Third-Party Dependencies:** All scripts rely exclusively on native language standard libraries and built-in system utilities.
* **Cross-Platform Compatibility:** Designed and tested for macOS and Linux operating environments.
* **Safe & Non-Destructive:** Built with explicit validation checks and confirmations prior to executing destructive actions.

---

## Getting Started

Clone the repository and run any tool directly:

```bash
git clone [https://github.com/your-username/small_utilities.git](https://github.com/your-username/small_utilities.git)
cd small_utilities/
python3 .py

## 📄 License

This repository is licensed under the [MIT License](LICENSE).
