# 📂 Downloads Folder Auto-Organizer

A zero-dependency, cross-platform Python utility that automatically scans your messy `Downloads` directory and organizes files into clean, structured subfolders by file type.

---

## ✨ Features

* **Zero Dependencies:** Uses Python's native standard libraries (`pathlib` and `shutil`)—no `pip install` required.
* **Cross-Platform:** Works seamlessly on Windows, macOS, and Linux.
* **Overwrite Protection:** Automatically checks if a file already exists in the target directory to prevent accidental overwriting.
* **Smart Categorization:** Automatically routes files to specific folders:
  * 📄 **Documents:** `.pdf`, `.docx`, `.xlsx`, `.txt`, `.csv`, `.epub`, etc.
  * 🖼️ **Images:** `.jpg`, `.png`, `.gif`, `.webp`, `.svg`, etc.
  * 📦 **Archives:** `.zip`, `.tar`, `.gz`, `.7z`, `.rar`, etc.
  * 🎥 **Media:** `.mp4`, `.mp3`, `.mkv`, `.mov`, `.wav`, etc.
  * ⚙️ **Executables:** `.exe`, `.msi`, `.dmg`, `.pkg`, etc.
  * 💻 **Code:** `.py`, `.js`, `.html`, `.json`, `.yaml`, etc.

---

## 🚀 How to Run

1. Open your terminal or command prompt.
2. Navigate to this folder or run the script using Python 3:

```bash
python downloads_organize.py
