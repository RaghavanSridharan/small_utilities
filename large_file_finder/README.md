# 🚨 "Disk Hog" Large File Finder

A lightweight, zero-dependency Python utility that scans your hard drive or chosen folders to locate the top largest files taking up valuable storage space.

---

## ✨ Features

* **Zero Dependencies:** Built entirely using Python's native `os` and `pathlib` standard modules—no `pip install` required.
* **Smart Permission Handling:** Automatically skips system/protected files without crashing.
* **Readable Sizes:** Converts raw bytes into clean `MB` and `GB` formatting.
* **Interactive Prompt:** Allows you to scan your entire home folder or specify a specific directory (like `Downloads` or `Documents`).

---

## 🚀 How to Run

1. Open your terminal or command prompt.
2. Run the script using Python 3:

```bash
python find_large_files.py
