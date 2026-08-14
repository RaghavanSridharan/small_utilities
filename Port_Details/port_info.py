import subprocess
import sys
import shutil

def run_cmd(cmd):
    """Executes a system command silently and returns stripped stdout."""
    try:
        res = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=5)
        return res.stdout.strip()
    except Exception:
        return ""

def get_listening_ports():
    """Returns a sorted list of unique TCP ports currently in LISTEN state."""
    lsof_out = run_cmd("lsof -iTCP -sTCP:LISTEN -P -n")
    ports = set()
    if lsof_out:
        lines = lsof_out.splitlines()[1:]  # Skip header row
        for line in lines:
            parts = line.split()
            if len(parts) >= 9:
                address = parts[8]  # Address column e.g., *:6001 or 127.0.0.1:8080
                if ":" in address:
                    port_str = address.rsplit(":", 1)[1]
                    if port_str.isdigit():
                        ports.add(int(port_str))
    return sorted(list(ports))

def display_dashboard():
    """Displays terminal header with total counts and sample ports."""
    occupied_ports = get_listening_ports()
    total_occupied = len(occupied_ports)
    total_available = 65535 - total_occupied

    # Sample occupied ports (up to 5)
    sample_occupied = [str(p) for p in occupied_ports[:5]]
    
    # Sample free ports (checking common developer ports first)
    common_dev_ports = [3000, 5000, 8000, 8080, 9000, 4200, 5173, 8443]
    sample_free = []
    for p in common_dev_ports:
        if p not in occupied_ports:
            sample_free.append(str(p))
        if len(sample_free) == 5:
            break

    print("\n" + "=" * 68)
    print(" PORT INSPECTOR DASHBOARD")
    print("=" * 68)
    print(f"  Occupied Ports: {total_occupied:<6} | Available Ports: {total_available}")
    print("-" * 68)
    print(f"  Sample Occupied Ports : {', '.join(sample_occupied) if sample_occupied else 'None'}")
    print(f"  Sample Free Ports     : {', '.join(sample_free)}")
    print("=" * 68 + "\n")

def inspect_port(port):
    """Performs deep inspection on a specific port."""
    lsof_out = run_cmd(f"lsof -iTCP:{port} -sTCP:LISTEN -P -n")
    
    if not lsof_out:
        print("\n" + "=" * 68)
        print(f" PORT INSPECTOR: DEEP DIVE (Port {port})")
        print("=" * 68)
        print(f"  Status:          FREE")
        print(f"  Port:            {port} (TCP)")
        print(f"  Action Advice:   Port is currently available for binding.")
        print("=" * 68 + "\n")
        return

    lines = lsof_out.splitlines()
    if len(lines) < 2:
        print("\n" + "=" * 68)
        print(f" PORT INSPECTOR: DEEP DIVE (Port {port})")
        print("=" * 68)
        print(f"  Status:          FREE")
        print(f"  Port:            {port} (TCP)")
        print(f"  Action Advice:   Port is currently available for binding.")
        print("=" * 68 + "\n")
        return

    # Extract PID and Process Name
    parts = lines[1].split()
    proc_name = parts[0]
    pid = parts[1]

    # Query process metrics via ps
    etime = run_cmd(f"ps -p {pid} -o etime=").strip()
    lstart = run_cmd(f"ps -p {pid} -o lstart=").strip()
    cpu = run_cmd(f"ps -p {pid} -o %cpu=").strip()
    mem = run_cmd(f"ps -p {pid} -o %mem=").strip()
    full_cmd = run_cmd(f"ps -p {pid} -o command=").strip()

    # -------------------------------------------------------------
    # Process Classification & Safety Detection
    # -------------------------------------------------------------
    is_system_proc = False
    system_paths = ["/System/", "/usr/libexec/", "/sbin/", "/usr/sbin/"]
    
    for sys_path in system_paths:
        if full_cmd.startswith(sys_path):
            is_system_proc = True
            break

    # Check Docker Container Details if applicable
    is_docker = False
    docker_container_info = ""
    if shutil.which("docker"):
        docker_out = run_cmd("docker ps --format '{{.Names}}\t{{.Image}}\t{{.Ports}}'")
        if docker_out:
            for line in docker_out.splitlines():
                if f":{port}->" in line or f":{port}/" in line:
                    d_parts = line.split('\t')
                    is_docker = True
                    docker_container_info = f"Docker Container ({d_parts[0]} | Image: {d_parts[1]})"
                    break

    # Format Classification & Action Advice
    if is_system_proc:
        proc_type = "macOS Core System Process"
        safety_advice = "WARNING: DO NOT KILL - Required operating system service."
    elif is_docker:
        proc_type = docker_container_info
        safety_advice = "SAFE TO STOP - Manage via Docker CLI or Desktop."
    else:
        proc_type = "User / Application Process"
        safety_advice = "SAFE TO KILL - User-level process or application."

    # Build Parent Process Chain up to Root (PID 1)
    chain = []
    curr_pid = pid
    visited = set()
    while curr_pid and curr_pid not in visited and curr_pid != "0":
        visited.add(curr_pid)
        c_name = run_cmd(f"ps -p {curr_pid} -o comm=").strip()
        chain.append(f"[PID {curr_pid}] {c_name if c_name else 'unknown'}")
        curr_pid = run_cmd(f"ps -p {curr_pid} -o ppid=").strip()

    # Output Deep Dive Report
    print("\n" + "=" * 68)
    print(f" PORT INSPECTOR: DEEP DIVE (Port {port})")
    print("=" * 68)
    print(f"  Status:          OCCUPIED")
    print(f"  Port:            {port} (TCP)")
    print(f"  Process Name:    {proc_name}")
    print(f"  PID:             {pid}")
    print(f"  Classification:  {proc_type}")
    print(f"  Action Advice:   {safety_advice}")
    print("-" * 68)
    print(" RESOURCE METRICS & TIMING")
    print(f"  CPU Usage:       {cpu if cpu else '0.0'}%")
    print(f"  Memory Usage:    {mem if mem else '0.0'}%")
    print(f"  Uptime:          {etime if etime else 'N/A'}")
    print(f"  Started At:      {lstart if lstart else 'N/A'}")
    print("-" * 68)
    print(" PARENT PROCESS CHAIN")
    for idx, node in enumerate(reversed(chain)):
        indent = "  " + "   " * idx + ("+-- " if idx > 0 else "")
        print(f"{indent}{node}")
    print("-" * 68)
    print(" FULL COMMAND ARGUMENTS")
    print(f"  {full_cmd if full_cmd else proc_name}")
    print("=" * 68 + "\n")

def main():
    display_dashboard()

    while True:
        user_input = input("Enter Port Number, 'd' for Dashboard, or '2' to Exit: ").strip()

        if user_input == "2" or user_input.lower() in ["exit", "quit", "q"]:
            print("\nExiting Port Inspector.\n")
            sys.exit(0)
        elif user_input.isdigit():
            inspect_port(user_input)
        elif user_input.lower() in ["d", "dashboard"]:
            display_dashboard()
        else:
            print("\nError: Invalid input. Enter a valid port number, 'd', or '2'.\n")

if __name__ == "__main__":
    main()
