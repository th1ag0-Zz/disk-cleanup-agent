#!/usr/bin/env python3
"""Read-only local disk inventory. No dependencies, content reads or deletion."""
import argparse
import heapq
import json
import os
from pathlib import Path
import shutil
import stat
import sys

CACHE_PATHS = (
    ("Library/Caches/ms-playwright", "Playwright browsers"),
    ("Library/Caches/ms-playwright-mcp", "Playwright MCP browsers"),
    ("Library/Developer/Xcode/DerivedData", "Xcode build outputs"),
    (".expo/ios-simulator-app-cache", "Expo iOS app cache"),
    (".expo/android-apk-cache", "Expo Android APK cache"),
    (".expo/expo-go", "Expo Go downloads"),
    (".cache/uv", "uv package cache"),
    ("Library/Caches/uv", "uv package cache"),
    (".npm/_cacache", "npm package cache"),
    (".npm/_npx", "npx downloaded tools"),
    (".cache/pip", "pip package cache"),
    ("Library/Caches/pip", "pip package cache"),
)


def allocated(info):
    return getattr(info, "st_blocks", (info.st_size + 511) // 512) * 512


def analyze(root, min_bytes=500 * 1024**2, limit=30):
    root = Path(root).expanduser().resolve(strict=True)
    if not root.is_dir():
        raise ValueError("root must be a directory")
    root_device = root.stat().st_dev
    disk = shutil.disk_usage(root)
    home = Path.home().resolve()
    candidates = {}
    for relative, label in CACHE_PATHS:
        path = home / relative
        if path == root or root in path.parents:
            candidates[str(path)] = {"path": str(path), "kind": label,
                                     "allocated_bytes": 0, "scan_complete": True}
    errors, mounts, top, large = [], [], {}, []
    error_count = skipped_links = visited = total = 0
    seen = set()
    # Each iterator is closed on exit, including errors and interruption.
    stack = [(root, None)]
    while stack:
        directory, group = stack.pop()
        try:
            with os.scandir(directory) as entries:
                for entry in entries:
                    path = Path(entry.path)
                    bucket = group or entry.name
                    try:
                        info = entry.stat(follow_symlinks=False)
                        if stat.S_ISLNK(info.st_mode):
                            skipped_links += 1
                            continue
                        if info.st_dev != root_device:
                            if len(mounts) < 100:
                                mounts.append(str(path))
                            continue
                        if stat.S_ISDIR(info.st_mode):
                            stack.append((path, bucket))
                            continue
                        if not stat.S_ISREG(info.st_mode):
                            continue
                        identity = (info.st_dev, info.st_ino)
                        if identity in seen:
                            continue
                        seen.add(identity)
                        visited += 1
                        size = allocated(info)
                        total += size
                        top[bucket] = top.get(bucket, 0) + size
                        ancestors = {str(parent) for parent in path.parents}
                        for base, item in candidates.items():
                            if base in ancestors:
                                item["allocated_bytes"] += size
                        if info.st_size >= min_bytes:
                            record = (info.st_size, str(path), size)
                            if len(large) < limit:
                                heapq.heappush(large, record)
                            elif record > large[0]:
                                heapq.heapreplace(large, record)
                    except OSError as exc:
                        error_count += 1
                        if len(errors) < 100:
                            errors.append({"path": str(path), "error": str(exc)})
        except OSError as exc:
            error_count += 1
            if len(errors) < 100:
                errors.append({"path": str(directory), "error": str(exc)})
    # Any scan error can make candidate totals incomplete; be conservative.
    for item in candidates.values():
        item["scan_complete"] = error_count == 0
    return {
        "root": str(root), "platform": sys.platform,
        "disk": {"total_bytes": disk.total, "used_bytes": disk.used,
                 "free_bytes": disk.free},
        "scanned_allocated_bytes": total, "files_scanned": visited,
        "top_directories": [{"path": str(root / name), "allocated_bytes": size}
                            for name, size in sorted(top.items(), key=lambda x: (-x[1], x[0]))],
        "cache_candidates": sorted((x for x in candidates.values() if x["allocated_bytes"]),
                                   key=lambda x: -x["allocated_bytes"]),
        "large_files": [{"path": path, "logical_bytes": logical, "allocated_bytes": size}
                        for logical, path, size in sorted(large, reverse=True)],
        "scan_error_count": error_count, "scan_errors": errors,
        "skipped_symlinks": skipped_links, "skipped_mounts": mounts,
        "notes": ["Sizes exclude directory metadata. Hard-linked files counted once; attribution follows traversal order.",
                  "Logical file size may exceed physical allocation. Totals are estimates, not guaranteed reclaimable space.",
                  "Only known cache paths under the current user's home are classified. Custom cache paths require manual review."]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=str(Path.home()))
    parser.add_argument("--min-size-mb", type=float, default=500,
                        help="Minimum logical size in MiB (default: 500)")
    parser.add_argument("--limit", type=int, default=30)
    args = parser.parse_args()
    if args.limit < 1 or args.min_size_mb < 0:
        parser.error("limit must be positive and min-size-mb nonnegative")
    if sys.platform not in ("darwin", "linux"):
        parser.error("supported platforms: macOS and Linux")
    try:
        report = analyze(args.root, int(args.min_size_mb * 1024**2), args.limit)
    except (OSError, ValueError) as exc:
        parser.exit(2, str(exc) + "\n")
    print(json.dumps(report, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
