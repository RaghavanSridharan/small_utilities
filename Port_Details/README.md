# Port Info

A zero-dependency Python command-line diagnostic utility for developers and system administrators to inspect active TCP ports. It analyzes port occupancy, extracts process lineage, tracks CPU and memory consumption, detects Docker container bindings, and flags core operating system processes to prevent accidental termination.

---

## Features

* **Zero External Dependencies:** Relies strictly on native Python standard modules and system utilities (`lsof`, `ps`, `docker`).
* **System Overview:** Displays total occupied vs. available TCP ports alongside sample active and free developer ports.
* **Process Lineage:** Traverses the Parent Process ID (PPID) hierarchy up to root (`launchd`/`init`).
* **Safety Classification:** Identifies core operating system processes and warns against terminating critical system services.
* **Docker Awareness:** Detects if a port is mapped to a Docker container and extracts container name and image metadata.
* **Scrollable Terminal View:** Retains terminal scrollback history for easy reference across multiple port queries.

---

## Requirements

* **Operating System:** macOS or Linux
* **Python Version:** Python 3.6+
* **Permissions:** Standard user access (certain restricted system ports may require elevated privileges for full argument details)

---

## Usage

1. Navigate to the utility directory:
   ```bash
   cd port_info
