#!/usr/bin/env python3
"""
Dev Environment Auditor
------------------------
Zero-dependency environment diagnostic for developers joining a new team,
setting up a fresh machine, or debugging "why doesn't this work here."

Default mode: dev tooling, PATH, git identity, disk, proxy, DNS, your own
identity, and a live scan for known middleware/services actually running
on the box (web/app servers, containers, monitoring agents, databases).

Security-relevant info (sudo, firewall, SELinux, full user account list)
is opt-in via --security / --list-users, since it's sensitive to print
or paste into a ticket by default.

Usage:
    python3 dev_env_auditor.py                  # standard report
    python3 dev_env_auditor.py --full-scan       # also show NOT-FOUND products
    python3 dev_env_auditor.py --security        # + sudo/firewall/SELinux
    python3 dev_env_auditor.py --list-users       # + full account listing
    python3 dev_env_auditor.py --all              # everything
    python3 dev_env_auditor.py --json out.json    # machine-readable export
    python3 dev_env_auditor.py --no-save          # skip writing the .txt report
    python3 dev_env_auditor.py --no-color         # plain text output
"""

import os
import re
import sys
import json
import shutil
import socket
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
    def green(cls, t): return cls.wrap("32", t)
    @classmethod
    def red(cls, t): return cls.wrap("31", t)
    @classmethod
    def yellow(cls, t): return cls.wrap("33", t)
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

def run_cmd(cmd, timeout=6):
    try:
        res = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return res.stdout.strip()
    except Exception:
        return ""


def has(tool):
    return shutil.which(tool) is not None


class Report:
    """Collects (section -> rows) for pretty-print, JSON export, and plain-text file."""

    def __init__(self):
        self.sections = []

    def section(self, title):
        rows = []
        self.sections.append((title, rows))
        return rows

    def to_json(self):
        return {title: [{"label": l, "value": v, "status": k} for l, v, k in rows]
                for title, rows in self.sections}

    def render_lines(self, colored=True):
        width = 74
        lines = []
        lines.append("=" * width)
        lines.append(" DEV ENVIRONMENT AUDITOR")
        lines.append(f" Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("=" * width)
        for title, rows in self.sections:
            lines.append("")
            lines.append(f" {title}")
            lines.append("-" * width)
            if not rows:
                lines.append("   (nothing to report)")
                continue
            label_width = max(len(label) for label, _, _ in rows) + 2
            for label, value, kind in rows:
                mark = ICONS[kind]  # plain marker for file output
                lines.append(f"  [{mark}] {label:<{label_width}} {value}")
        lines.append("")
        lines.append("=" * width)
        return lines

    def print(self):
        width = 74
        print()
        print(Style.bold("=" * width))
        print(Style.bold(" DEV ENVIRONMENT AUDITOR"))
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
# Identity (who am I — always shown, not sensitive since it's just "you")
# --------------------------------------------------------------------------

def collect_identity_section(report):
    rows = report.section("IDENTITY")
    user = run_cmd("whoami")
    uid = run_cmd("id -u")
    gid = run_cmd("id -g")
    groups = run_cmd("groups")
    rows.append(("Logged in as", f"{user} (uid={uid}, gid={gid})", "info"))
    rows.append(("Group membership", groups or "unknown", "info"))


# --------------------------------------------------------------------------
# System & network
# --------------------------------------------------------------------------

def get_ip_addresses():
    ips = []
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ips.append(s.getsockname()[0])
        s.close()
    except Exception:
        pass
    if not ips:
        if platform.system() == "Darwin":
            ip_out = run_cmd("ipconfig getifaddr en0") or run_cmd("ipconfig getifaddr en1")
            if ip_out:
                ips = [ip_out]
        else:
            ip_out = run_cmd("hostname -I")
            if ip_out:
                ips = ip_out.split()
    return ", ".join(ips) if ips else "unknown"


def collect_system_section(report):
    rows = report.section("SYSTEM & NETWORK")
    rows.append(("Hostname", socket.gethostname(), "info"))
    rows.append(("IP Address(es)", get_ip_addresses(), "info"))
    rows.append(("OS / Kernel", f"{platform.system()} {platform.release()} ({platform.machine()})", "info"))
    rows.append(("Timezone", run_cmd("date +'%Z (%z)'") or "unknown", "info"))
    rows.append(("Uptime", run_cmd("uptime -p") or run_cmd("uptime") or "unknown", "info"))


# --------------------------------------------------------------------------
# DNS sanity check
# --------------------------------------------------------------------------

def collect_dns_section(report):
    rows = report.section("DNS RESOLUTION")
    for host in ["github.com", "pypi.org", "registry.npmjs.org"]:
        try:
            socket.setdefaulttimeout(3)
            ip = socket.gethostbyname(host)
            rows.append((host, ip, "ok"))
        except Exception:
            rows.append((host, "could not resolve", "fail"))


# --------------------------------------------------------------------------
# Git identity
# --------------------------------------------------------------------------

def collect_git_section(report):
    rows = report.section("GIT IDENTITY")
    if not has("git"):
        rows.append(("git", "not installed", "fail"))
        return
    name = run_cmd("git config --global user.name")
    email = run_cmd("git config --global user.email")
    default_branch = run_cmd("git config --global init.defaultBranch")
    cred_helper = run_cmd("git config --global credential.helper")

    rows.append(("user.name", name or "NOT SET", "ok" if name else "warn"))
    rows.append(("user.email", email or "NOT SET", "ok" if email else "warn"))
    if email:
        personal = ("gmail.com", "yahoo.com", "outlook.com", "hotmail.com", "icloud.com")
        if any(d in email.lower() for d in personal):
            rows.append(("email check", f"looks personal ({email}) — confirm this is intended", "warn"))
        else:
            rows.append(("email check", "looks like a work address", "ok"))
    rows.append(("init.defaultBranch", default_branch or "unset (git default)", "info"))
    rows.append(("credential.helper", cred_helper or "NOT SET (will prompt each push)", "ok" if cred_helper else "warn"))

    ssh_dir = os.path.expanduser("~/.ssh")
    if os.path.exists(ssh_dir):
        keys = [f for f in os.listdir(ssh_dir) if f.endswith(".pub")]
        rows.append(("SSH public keys", f"{len(keys)} found" if keys else "none found", "ok" if keys else "warn"))
    else:
        rows.append(("SSH public keys", "~/.ssh does not exist", "warn"))


# --------------------------------------------------------------------------
# PATH diagnostics
# --------------------------------------------------------------------------

def collect_path_section(report):
    rows = report.section("PATH DIAGNOSTICS")
    entries = os.environ.get("PATH", "").split(os.pathsep)
    seen, duplicates, missing = set(), set(), []
    for e in entries:
        if e in seen:
            duplicates.add(e)
        seen.add(e)
        if e and not os.path.isdir(e):
            missing.append(e)

    rows.append(("Total PATH entries", str(len(entries)), "info"))
    rows.append(("Duplicate entries", f"{len(duplicates)} found" if duplicates else "none",
                  "warn" if duplicates else "ok"))
    rows.append(("Non-existent directories", f"{len(missing)} entries" if missing else "none",
                  "warn" if missing else "ok"))

    common_dirs = [os.path.expanduser("~/.local/bin"), os.path.expanduser("~/bin"),
                   "/opt/homebrew/bin" if platform.system() == "Darwin" else "/usr/local/bin"]
    for d in common_dirs:
        if os.path.isdir(d) and d not in entries:
            rows.append(("Not on PATH", f"{d} exists but isn't in PATH", "warn"))


# --------------------------------------------------------------------------
# Package manager
# --------------------------------------------------------------------------

def collect_package_manager_section(report):
    rows = report.section("PACKAGE MANAGER")
    if platform.system() == "Darwin":
        if has("brew"):
            v = run_cmd("brew --version")
            rows.append(("Homebrew", v.splitlines()[0] if v else "installed", "ok"))
        else:
            rows.append(("Homebrew", "not installed", "warn"))
    else:
        found = [pm for pm in ["apt", "dnf", "yum", "pacman", "zypper"] if has(pm)]
        if found:
            for pm in found:
                rows.append((pm, "available", "ok"))
        else:
            rows.append(("package manager", "none of apt/dnf/yum/pacman/zypper found", "warn"))


# --------------------------------------------------------------------------
# Dev CLI tool matrix (static, PATH-based — languages, build tools, CLIs)
# --------------------------------------------------------------------------

TOOL_VERSION_CMDS = {
    "python3": "python3 --version", "node": "node -v", "npm": "npm -v",
    "docker": "docker --version", "git": "git --version",
    "kubectl": "kubectl version --client --short 2>/dev/null || kubectl version --client",
    "terraform": "terraform -v", "curl": "curl --version", "openssl": "openssl version",
    "aws": "aws --version", "gcloud": "gcloud --version", "java": "java -version 2>&1",
}
DEFAULT_TOOLS = ["python3", "node", "npm", "docker", "git", "kubectl",
                  "terraform", "curl", "openssl", "aws", "gcloud", "java"]


def get_tool_version(tool):
    if not has(tool):
        return None
    cmd = TOOL_VERSION_CMDS.get(tool, f"{tool} --version")
    out = run_cmd(cmd)
    return out.splitlines()[0].strip()[:60] if out else "installed (version unknown)"


def collect_tools_section(report, tools):
    rows = report.section("DEV TOOLS (CLI, on PATH)")
    for tool in tools:
        v = get_tool_version(tool)
        rows.append((tool, v, "ok") if v else (tool, "not installed", "fail"))


# --------------------------------------------------------------------------
# Live middleware/service scan — process + port + filesystem signatures.
# This replaces guessing "does this team run AppD or Prometheus" with an
# actual scan: whatever's running gets found, regardless of the team's stack.
# --------------------------------------------------------------------------

SIGNATURES = {
    "WEB & APPLICATION MIDDLEWARE": [
        {"name": "IBM WebSphere Application Server", "proc": [r"was\.install\.root", r"AppSrv.*java"],
         "ports": [9080, 9443, 9060], "paths": ["/opt/IBM/WebSphere", "/opt/ibm/WebSphere"]},
        {"name": "IBM HTTP Server (IHS)", "proc": [r"ihsserver", r"httpd\.ihs"],
         "ports": [], "paths": ["/opt/IBM/HTTPServer", "/opt/ibm/HTTPServer"]},
        {"name": "Apache HTTP Server", "proc": [r"\bapache2\b", r"\bhttpd\b"],
         "ports": [80, 443], "paths": ["/etc/apache2", "/etc/httpd"]},
        {"name": "nginx", "proc": [r"\bnginx\b"], "ports": [80, 443], "paths": ["/etc/nginx"]},
        {"name": "Apache Tomcat", "proc": [r"catalina", r"\btomcat\b"],
         "ports": [8080, 8443], "paths": ["/opt/tomcat", "/usr/share/tomcat"]},
        {"name": "Jenkins", "proc": [r"jenkins\.war", r"\bjenkins\b"],
         "ports": [8080, 50000], "paths": ["/var/lib/jenkins", "/opt/jenkins"]},
    ],
    "CONTAINERS & ORCHESTRATION": [
        {"name": "Docker", "proc": [r"dockerd"], "ports": [2375, 2376],
         "paths": ["/var/run/docker.sock", "/etc/docker"]},
        {"name": "Kubernetes (kubelet)", "proc": [r"\bkubelet\b", r"kube-apiserver"],
         "ports": [6443, 10250], "paths": ["/etc/kubernetes"]},
        {"name": "containerd", "proc": [r"\bcontainerd\b"], "ports": [], "paths": ["/etc/containerd"]},
    ],
    "MONITORING & OBSERVABILITY": [
        {"name": "Prometheus", "proc": [r"\bprometheus\b"], "ports": [9090], "paths": ["/etc/prometheus"]},
        {"name": "node_exporter", "proc": [r"node_exporter"], "ports": [9100], "paths": []},
        {"name": "Grafana", "proc": [r"grafana-server"], "ports": [3000], "paths": ["/etc/grafana"]},
        {"name": "AppDynamics", "proc": [r"appdynamics", r"machineagent"],
         "ports": [], "paths": ["/opt/appdynamics", "/opt/AppDynamics"]},
        {"name": "Datadog Agent", "proc": [r"datadog-agent"], "ports": [8125], "paths": ["/etc/datadog-agent"]},
    ],
    "DATABASES & MESSAGING": [
        {"name": "PostgreSQL", "proc": [r"\bpostgres\b"], "ports": [5432], "paths": ["/etc/postgresql"]},
        {"name": "MySQL / MariaDB", "proc": [r"mysqld", r"mariadbd"], "ports": [3306], "paths": ["/etc/mysql"]},
        {"name": "MongoDB", "proc": [r"\bmongod\b"], "ports": [27017], "paths": ["/etc/mongod.conf"]},
        {"name": "Redis", "proc": [r"redis-server"], "ports": [6379], "paths": ["/etc/redis"]},
        {"name": "Kafka", "proc": [r"kafka\.Kafka"], "ports": [9092], "paths": ["/opt/kafka"]},
        {"name": "RabbitMQ", "proc": [r"rabbitmq_server", r"beam\.smp.*rabbit"],
         "ports": [5672, 15672], "paths": ["/etc/rabbitmq"]},
        {"name": "Elasticsearch", "proc": [r"elasticsearch"], "ports": [9200], "paths": ["/etc/elasticsearch"]},
    ],
}


def get_running_processes_text():
    return run_cmd("ps -eo args 2>/dev/null") or run_cmd("ps aux")


def get_listening_ports():
    out = (run_cmd("ss -tln 2>/dev/null")
           or run_cmd("netstat -tln 2>/dev/null")
           or run_cmd("lsof -iTCP -sTCP:LISTEN -P -n 2>/dev/null"))
    return set(int(p) for p in re.findall(r"[:.](\d{2,5})\s", out or ""))


def detect_signature(sig, proc_text, open_ports):
    if any(re.search(p, proc_text, re.I) for p in sig["proc"]):
        return "running", "ok", None
    matched_ports = [p for p in sig["ports"] if p in open_ports]
    if matched_ports:
        return f"running (port {matched_ports[0]} open)", "ok", None
    for path in sig["paths"]:
        if os.path.exists(path):
            return "installed, not currently running", "warn", path
    return "not found", "info", None


def collect_middleware_sections(report, full_scan):
    proc_text = get_running_processes_text()
    open_ports = get_listening_ports()

    for category, sigs in SIGNATURES.items():
        results = []
        for sig in sigs:
            status, kind, path = detect_signature(sig, proc_text, open_ports)
            label = sig["name"] if not path else f"{sig['name']}"
            value = status if not path else f"{status} ({path})"
            results.append((label, value, kind, status == "not found"))

        detected = [(l, v, k) for l, v, k, is_missing in results if not is_missing]
        missing_count = sum(1 for *_, is_missing in results if is_missing)

        rows = report.section(category)
        if detected:
            rows.extend(detected)
        if full_scan:
            for l, v, k, is_missing in results:
                if is_missing:
                    rows.append((l, v, k))
        elif missing_count:
            rows.append((f"({missing_count} more not found)", "use --full-scan to list them", "info"))
        if not detected and not full_scan and not missing_count:
            pass  # nothing to report, section will just show empty


# --------------------------------------------------------------------------
# Disk & proxy
# --------------------------------------------------------------------------

def collect_disk_section(report):
    rows = report.section("DISK USAGE")
    mounts, seen = ["/", "/opt", "/var", "/tmp", os.path.expanduser("~")], set()
    for m in mounts:
        if m in seen or not os.path.exists(m):
            continue
        seen.add(m)
        try:
            stat = os.statvfs(m)
            total = (stat.f_blocks * stat.f_frsize) / (1024 ** 3)
            free = (stat.f_bavail * stat.f_frsize) / (1024 ** 3)
            used_pct = int(((total - free) / total) * 100) if total > 0 else 0
            kind = "fail" if used_pct >= 90 else ("warn" if used_pct >= 75 else "ok")
            rows.append((m, f"{used_pct}% used, {free:.1f} GB free", kind))
        except Exception:
            continue


def collect_proxy_section(report):
    rows = report.section("ENVIRONMENT & PROXY")
    rows.append(("HTTP_PROXY", os.environ.get("http_proxy") or os.environ.get("HTTP_PROXY") or "not set", "info"))
    rows.append(("HTTPS_PROXY", os.environ.get("https_proxy") or os.environ.get("HTTPS_PROXY") or "not set", "info"))
    rows.append(("JAVA_HOME", os.environ.get("JAVA_HOME") or "not set", "info"))
    rows.append(("Default shell", os.environ.get("SHELL") or "unknown", "info"))


# --------------------------------------------------------------------------
# User accounts — counts by default, full listing only with --list-users
# --------------------------------------------------------------------------

NOLOGIN_SHELLS = ("/usr/sbin/nologin", "/sbin/nologin", "/bin/false",
                   "/usr/bin/false", "/bin/sync", "/usr/bin/true")


def get_macos_users():
    """macOS keeps real accounts in Open Directory, not /etc/passwd — that file
    is a legacy stub and misses interactive users while still listing a pile
    of system entries. dscl is the correct source on Darwin."""
    out = run_cmd("dscl . -list /Users UniqueID")
    entries = []
    for line in out.splitlines():
        parts = line.split()
        if len(parts) < 2:
            continue
        name, uid = parts[0], parts[1]
        shell_out = run_cmd(f"dscl . -read /Users/{name} UserShell 2>/dev/null")
        shell = shell_out.split(":")[-1].strip() if shell_out else "/usr/bin/false"
        entries.append({"name": name, "uid": uid, "shell": shell or "/usr/bin/false"})
    return entries


def get_passwd_entries():
    if platform.system() == "Darwin":
        mac_entries = get_macos_users()
        if mac_entries:
            return mac_entries
        # fall through to /etc/passwd only if dscl gave nothing usable

    out = run_cmd("getent passwd")
    if not out and os.path.exists("/etc/passwd"):
        with open("/etc/passwd") as f:
            out = f.read()
    entries = []
    for line in (out or "").splitlines():
        parts = line.split(":")
        if len(parts) >= 7:
            entries.append({"name": parts[0], "uid": parts[2], "shell": parts[6]})
    return entries


def collect_users_section(report, list_users):
    rows = report.section("USER ACCOUNTS")
    entries = get_passwd_entries()
    if not entries:
        rows.append(("Account lookup", "unavailable on this system", "warn"))
        return

    human_threshold = 500 if platform.system() == "Darwin" else 1000
    human, system, login_capable = 0, 0, 0
    for e in entries:
        try:
            uid = int(e["uid"])
        except ValueError:
            uid = -1
        if uid >= human_threshold:
            human += 1
        else:
            system += 1
        if e["shell"] not in NOLOGIN_SHELLS and "nologin" not in e["shell"]:
            login_capable += 1

    rows.append(("Total accounts", str(len(entries)), "info"))
    rows.append(("Human-range accounts (uid >= {})".format(human_threshold), str(human), "info"))
    rows.append(("System/service accounts", str(system), "info"))
    rows.append(("Accounts with a usable login shell", str(login_capable), "info"))

    if list_users:
        for e in sorted(entries, key=lambda x: int(x["uid"]) if x["uid"].isdigit() else 0):
            rows.append((f"  {e['name']}", f"uid={e['uid']}  shell={e['shell']}", "info"))
    else:
        rows.append(("Full account list", "use --list-users to see individual accounts", "info"))


# --------------------------------------------------------------------------
# Security posture (opt-in — --security / --all)
# --------------------------------------------------------------------------

def check_sudo():
    res = subprocess.run("sudo -n true", shell=True, capture_output=True, text=True)
    if res.returncode == 0:
        return "passwordless sudo available", "warn"
    groups_out = run_cmd("groups")
    if any(g in groups_out for g in ("sudo", "wheel", "admin")):
        return "sudo group member (password required)", "info"
    return "standard user / restricted", "ok"


def get_ssh_service_status():
    if run_cmd("pgrep sshd"):
        return "active (sshd daemon running)", "info"
    if has("systemctl"):
        out = run_cmd("systemctl is-active sshd || systemctl is-active ssh")
        return ("active (systemctl)", "info") if out == "active" else ("inactive / disabled", "ok")
    return "unknown", "info"


def get_firewall_status():
    if has("ufw"):
        out = run_cmd("ufw status")
        return ("UFW active", "ok") if "active" in out else ("UFW inactive", "warn")
    if has("firewall-cmd"):
        out = run_cmd("firewall-cmd --state")
        return ("firewalld running", "ok") if out == "running" else ("firewalld inactive", "warn")
    if has("pfctl"):
        return "macOS PF present", "info"
    return "unknown / none detected", "warn"


def get_selinux_status():
    if not has("sestatus"):
        return "not installed (N/A)", "info"
    out = run_cmd("sestatus")
    if "enabled" in out.lower():
        mode = run_cmd("getenforce")
        return f"enabled ({mode or 'enforcing'})", "ok"
    return "disabled", "warn"


def collect_security_section(report):
    rows = report.section("SECURITY POSTURE (sensitive — review before sharing)")
    d, k = check_sudo(); rows.append(("Sudo privileges", d, k))
    d, k = get_ssh_service_status(); rows.append(("SSH daemon", d, k))
    who_out = run_cmd("who")
    rows.append(("Active login sessions", str(len(who_out.splitlines()) if who_out else 0), "info"))
    d, k = get_firewall_status(); rows.append(("Firewall", d, k))
    d, k = get_selinux_status(); rows.append(("SELinux", d, k))
    rows.append(("Max open files (ulimit -n)", run_cmd("bash -c 'ulimit -n'") or "unknown", "info"))
    rows.append(("Max processes (ulimit -u)", run_cmd("bash -c 'ulimit -u'") or "unknown", "info"))


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def parse_args():
    p = argparse.ArgumentParser(description="Dev Environment Auditor — enterprise-aware health check.")
    p.add_argument("--security", action="store_true", help="Include sudo/firewall/SELinux/session info.")
    p.add_argument("--list-users", action="store_true", help="List every account, not just counts.")
    p.add_argument("--full-scan", action="store_true", help="Also list middleware/services NOT found.")
    p.add_argument("--all", action="store_true", help="Enable --security, --list-users, and --full-scan.")
    p.add_argument("--json", metavar="FILE", help="Also write the report as JSON to FILE.")
    p.add_argument("--tools", metavar="TOOL,TOOL,...", help="Override the default dev-tool list.")
    p.add_argument("--no-save", action="store_true", help="Don't write the timestamped .txt report to disk.")
    p.add_argument("--no-color", action="store_true", help="Disable colored output.")
    return p.parse_args()


def main():
    args = parse_args()
    if args.no_color:
        Style.enabled = False

    security = args.security or args.all
    list_users = args.list_users or args.all
    full_scan = args.full_scan or args.all

    report = Report()
    collect_identity_section(report)
    collect_system_section(report)
    collect_git_section(report)
    collect_path_section(report)
    collect_package_manager_section(report)

    tools = [t.strip() for t in (args.tools.split(",") if args.tools else DEFAULT_TOOLS) if t.strip()]
    collect_tools_section(report, tools)

    collect_middleware_sections(report, full_scan)
    collect_disk_section(report)
    collect_proxy_section(report)
    collect_dns_section(report)
    collect_users_section(report, list_users)

    if security:
        collect_security_section(report)

    report.print()

    if not args.no_save:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"dev_audit_report_{ts}.txt"
        with open(filename, "w") as f:
            f.write("\n".join(report.render_lines()))
        print(f"Report saved to ./{filename}")

    if args.json:
        with open(args.json, "w") as f:
            json.dump(report.to_json(), f, indent=2)
        print(f"JSON report written to {args.json}")

    print()


if __name__ == "__main__":
    main()
