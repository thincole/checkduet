"""
Version Manager for Shopee Duet Checker
Quản lý phiên bản tự động cho dự án
"""

import os
import sys

# Ensure UTF-8 output even in standard Windows cmd
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VERSION_FILE = os.path.join(BASE_DIR, "version.txt")
DEFAULT_VERSION = "1.1"


def get_current_version() -> str:
    """Đọc phiên bản hiện tại từ version.txt, mặc định là 1.1 nếu chưa có."""
    if os.path.exists(VERSION_FILE):
        try:
            with open(VERSION_FILE, "r", encoding="utf-8") as f:
                ver = f.read().strip()
                if ver:
                    return ver
        except Exception:
            pass
    return DEFAULT_VERSION


def calculate_next_version(current: str) -> str:
    """Tính phiên bản kế tiếp. Ví dụ: 1.1 -> 1.2, 1.9 -> 1.10, 1.2.3 -> 1.2.4."""
    if not current:
        return DEFAULT_VERSION

    parts = current.split(".")
    try:
        parts[-1] = str(int(parts[-1]) + 1)
        return ".".join(parts)
    except (ValueError, IndexError):
        return f"{current}.1"


def set_version(new_version: str) -> str:
    """Ghi phiên bản mới vào version.txt."""
    new_version = new_version.strip()
    if not new_version:
        new_version = DEFAULT_VERSION
    with open(VERSION_FILE, "w", encoding="utf-8") as f:
        f.write(new_version + "\n")
    return new_version


def bump_version() -> str:
    """Tự động tăng phiên bản và lưu vào file."""
    if not os.path.exists(VERSION_FILE):
        return set_version(DEFAULT_VERSION)
    cur = get_current_version()
    nxt = calculate_next_version(cur)
    return set_version(nxt)


def main():
    if len(sys.argv) > 1:
        arg = sys.argv[1].lower()
        if arg == "--current":
            if not os.path.exists(VERSION_FILE):
                print(f"Chua co (Mac dinh: {DEFAULT_VERSION})")
            else:
                print(get_current_version())
            return
        elif arg == "--next":
            if not os.path.exists(VERSION_FILE):
                print(DEFAULT_VERSION)
            else:
                print(calculate_next_version(get_current_version()))
            return
        elif arg == "--bump":
            print(bump_version())
            return
        elif arg == "--set" and len(sys.argv) > 2:
            print(set_version(sys.argv[2]))
            return
        elif arg in ("--help", "-h"):
            print("Usage: python version_mgr.py [--current | --next | --bump | --set <ver>]")
            return

    print(get_current_version())


if __name__ == "__main__":
    main()
