import os
import sys
from pathlib import Path

def get_readable_size(size_in_bytes):
    """Convert bytes into a human-readable size string (MB, GB, TB)."""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_in_bytes < 1024.0:
            return f"{size_in_bytes:.2f} {unit}"
        size_in_bytes /= 1024.0
    return f"{size_in_bytes:.2f} PB"

def scan_large_files(target_directory, top_n=15, min_size_mb=50):
    target_path = Path(target_directory).expanduser().resolve()
    
    if not target_path.exists():
        print(f"\n❌ Error: Directory '{target_directory}' does not exist.")
        return

    print(f"\n🔍 Scanning for files larger than {min_size_mb} MB in:")
    print(f"📁 {target_path}")
    print("-" * 65)

    min_bytes = min_size_mb * 1024 * 1024
    large_files = []

    # Safely walk through directory tree ignoring permission errors
    for root, dirs, files in os.walk(target_path):
        for file in files:
            file_path = Path(root) / file
            try:
                if file_path.is_file() and not file_path.is_symlink():
                    size = file_path.stat().st_size
                    if size >= min_bytes:
                        large_files.append((file_path, size))
            except (PermissionError, FileNotFoundError):
                continue

    if not large_files:
        print(f"✨ No files found larger than {min_size_mb} MB in this location!")
        return

    # Sort files by size descending
    large_files.sort(key=lambda x: x[1], reverse=True)

    print(f"\n🏆 Top {min(top_n, len(large_files))} Largest Files Found:\n")
    print(f"{'#':<3} | {'Size':<10} | {'File Path'}")
    print("-" * 65)

    for idx, (path, size) in enumerate(large_files[:top_n], start=1):
        readable_size = get_readable_size(size)
        print(f"{idx:<3} | {readable_size:<10} | {path}")

    print("-" * 65)
    print(f"💡 Found {len(large_files)} total files over {min_size_mb} MB.")

if __name__ == "__main__":
    print("=" * 65)
    print(" 🚨 DISK HOG: LARGE FILE FINDER")
    print("=" * 65)
    
    user_input = input("Enter directory path to scan (Press Enter for Home folder): ").strip()
    search_dir = user_input if user_input else "~"
    
    scan_large_files(search_dir)
