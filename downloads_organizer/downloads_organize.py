import os
import shutil
from pathlib import Path

# Define file categories and their extensions
CATEGORY_MAP = {
    "Documents": [".pdf", ".docx", ".doc", ".txt", ".xlsx", ".pptx", ".csv", ".epub"],
    "Images": [".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp", ".bmp", ".ico"],
    "Archives": [".zip", ".tar", ".gz", ".7z", ".rar", ".iso"],
    "Media": [".mp4", ".mp3", ".mkv", ".wav", ".mov", ".avi", ".flac"],
    "Executables": [".exe", ".msi", ".dmg", ".pkg", ".deb"],
    "Code": [".py", ".js", ".html", ".css", ".json", ".sh", ".yaml", ".yml", ".sql"]
}

def organize_downloads():
    # Automatically locates the user's Downloads directory across OS platform
    downloads_path = Path.home() / "Downloads"
    
    if not downloads_path.exists():
        print("Error: Downloads folder not found.")
        return

    print(f"Scanning: {downloads_path}\n" + "-" * 40)
    
    moved_count = 0

    for item in downloads_path.iterdir():
        # Skip subdirectories and hidden files
        if item.is_dir() or item.name.startswith("."):
            continue

        file_ext = item.suffix.lower()
        target_category = "Others"

        # Match extension to category
        for category, extensions in CATEGORY_MAP.items():
            if file_ext in extensions:
                target_category = category
                break

        # Create destination directory if it doesn't exist
        dest_dir = downloads_path / target_category
        dest_dir.mkdir(exist_ok=True)

        # Target file path
        target_path = dest_dir / item.name

        # Prevent overwriting existing files
        if not target_path.exists():
            shutil.move(str(item), str(target_path))
            print(f"✅ Moved: {item.name} ➔ {target_category}/")
            moved_count += 1
        else:
            print(f"⚠️ Skipped (already exists): {item.name}")

    print("-" * 40)
    print(f"Clean up complete! {moved_count} file(s) organized.")

if __name__ == "__main__":
    organize_downloads()
