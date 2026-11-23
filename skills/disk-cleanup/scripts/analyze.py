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

WINDOWS = os.name == "nt"
SUPPORTED_PLATFORMS = ("darwin", "linux", "win32")

# Windows file attributes and reparse tags (winnt.h). Defined here because
# the stat module only exposes some of them, and only on Windows.
FILE_ATTRIBUTE_SPARSE_FILE = 0x200
FILE_ATTRIBUTE_COMPRESSED = 0x800
FILE_ATTRIBUTE_OFFLINE = 0x1000
FILE_ATTRIBUTE_RECALL_ON_OPEN = 0x40000
FILE_ATTRIBUTE_RECALL_ON_DATA_ACCESS = 0x400000
CLOUD_ONLY_ATTRIBUTES = (FILE_ATTRIBUTE_OFFLINE | FILE_ATTRIBUTE_RECALL_ON_OPEN
                         | FILE_ATTRIBUTE_RECALL_ON_DATA_ACCESS)
# Symbolic links, junctions and mount points point at another path
# ("name surrogates"). Cloud placeholders and dedup files do not.
REPARSE_TAG_NAME_SURROGATE = 0x20000000

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
    (".gradle/caches", "Gradle caches"),
    (".gradle/wrapper/dists", "Gradle wrapper downloads"),
    (".cargo/registry/cache", "Cargo downloaded packages"),
    (".rustup/downloads", "Rustup downloads"),
    (".rustup/tmp", "Rustup temporary files"),
    (".bun/install/cache", "Bun package cache"),
    (".yarn/cache", "Yarn package cache"),
    ("Library/pnpm/store", "pnpm package store"),
    (".local/share/pnpm/store", "pnpm package store"),
    (".composer/cache", "Composer package cache"),
    (".local/share/NuGet/v3-cache", "NuGet HTTP cache"),
    (".local/share/NuGet/plugins-cache", "NuGet plugin cache"),
    # Windows defaults under %LOCALAPPDATA% (the user's AppData/Local).
    ("AppData/Local/npm-cache/_cacache", "npm package cache"),
    ("AppData/Local/npm-cache/_npx", "npx downloaded tools"),
    ("AppData/Local/pip/Cache", "pip package cache"),
    ("AppData/Local/uv/cache", "uv package cache"),
    ("AppData/Local/pypoetry/Cache", "Poetry cache"),
    ("AppData/Local/Yarn/Cache", "Yarn package cache"),
    ("AppData/Local/pnpm/store", "pnpm package store"),
    ("AppData/Local/pnpm-cache", "pnpm metadata cache"),
    ("AppData/Local/node-gyp/Cache", "node-gyp downloaded headers"),
    ("AppData/Local/ms-playwright", "Playwright browsers"),
    ("AppData/Local/ms-playwright-mcp", "Playwright MCP browsers"),
    ("AppData/Local/Cypress/Cache", "Cypress downloaded binaries"),
    ("AppData/Local/go-build", "Go build cache"),
    ("AppData/Local/Composer", "Composer package cache"),
    ("AppData/Local/NuGet/v3-cache", "NuGet HTTP cache"),
    ("AppData/Local/NuGet/plugins-cache", "NuGet plugin cache"),
    ("AppData/Local/Microsoft/Windows/INetCache", "Windows internet cache"),
    ("AppData/Local/CrashDumps", "Application crash dumps"),
)

# Relative to a project with a regular manifest/config file. Never classify
# whole dependency folders, build outputs, environments or framework state.
JS_MARKERS = ("package.json",)
PY_MARKERS = ("pyproject.toml", "setup.py", "setup.cfg", "requirements.txt", "pytest.ini")
PROJECT_CACHES = (
    (".next/cache", "Next.js build/runtime cache (stop the app before removal)", JS_MARKERS),
    (".angular/cache", "Angular build cache", ("angular.json",)),
    ("node_modules/.vite", "Vite dependency cache", JS_MARKERS),
    ("node_modules/.cache", "JavaScript tooling cache", JS_MARKERS),
    (".pytest_cache", "pytest run cache", PY_MARKERS),
    (".mypy_cache", "mypy type-check cache", PY_MARKERS),
    (".ruff_cache", "Ruff analysis cache", PY_MARKERS),
)
APP_CACHE_LABELS = {
    "go-build": "Go build cache", "composer": "Composer package cache",
    "yarn": "Yarn package cache", "pnpm": "pnpm cache/store (review contents)",
    "node-gyp": "node-gyp downloaded headers", "Cypress": "Cypress downloaded binaries",
    "ms-playwright": "Playwright browsers", "ms-playwright-mcp": "Playwright MCP browsers",
    "pip": "pip package cache", "uv": "uv package cache", "pypoetry": "Poetry cache",
}
# Folders whose immediate children are each classified as a cache entry.
CACHE_ROOTS = ("Library/Caches", ".cache")
TEMP_ROOT = "AppData/Local/Temp"


def key(path):
    """Comparison key for a path: case-insensitive on Windows."""
    return os.path.normcase(str(path))


def project_cache_label(path, home):
    if home not in path.parents:
        return None
    for relative, label, markers in PROJECT_CACHES:
        parts = Path(relative).parts
        if path.parts[-len(parts):] != parts:
            continue
        project = path.parents[len(parts) - 1]
        for marker in markers:
            try:
                if stat.S_ISREG((project / marker).lstat().st_mode):
                    return label
            except OSError:
                pass
    return None


def cache_locations(home):
    # Classify immediate children, never the whole cache root as one delete target.
    roots = {home / relative for relative in CACHE_ROOTS}
    roots.add(home / TEMP_ROOT)
    configured = os.environ.get("XDG_CACHE_HOME", "")
    if configured and Path(configured).is_absolute():
        path = Path(os.path.abspath(configured))
        if home in path.parents:
            roots.add(path)
    return {path for path in roots if not any(base in path.parents for base in roots)}


def is_link(info):
    """Symbolic links, plus Windows junctions and mount points."""
    return stat.S_ISLNK(info.st_mode) or bool(
        getattr(info, "st_reparse_tag", 0) & REPARSE_TAG_NAME_SURROGATE)


def is_cloud_only(info):
    """Windows cloud placeholder (OneDrive Files On-Demand and similar)."""
    return bool(getattr(info, "st_file_attributes", 0) & CLOUD_ONLY_ATTRIBUTES)


_compressed_size = None


def windows_compressed_size(path):
    """On-disk size of a compressed or sparse file. Reads metadata only."""
    global _compressed_size
    if _compressed_size is None:
        import ctypes
        from ctypes import wintypes
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        function = kernel32.GetCompressedFileSizeW
        function.argtypes = (wintypes.LPCWSTR, ctypes.POINTER(wintypes.DWORD))
        function.restype = wintypes.DWORD

        def size(name):
            high = wintypes.DWORD(0)
            low = function(name, ctypes.byref(high))
            if low == 0xFFFFFFFF:
                error = ctypes.get_last_error()
                if error:
                    raise ctypes.WinError(error)
            return (high.value << 32) + low
        _compressed_size = size
    return _compressed_size(str(path))


def allocated(info, path=None):
    blocks = getattr(info, "st_blocks", None)
    if blocks is not None:
        return blocks * 512
    # Windows does not report allocated blocks.
    if is_cloud_only(info):
        return 0
    attributes = getattr(info, "st_file_attributes", 0)
    if path is not None and attributes & (FILE_ATTRIBUTE_SPARSE_FILE | FILE_ATTRIBUTE_COMPRESSED):
        try:
            return windows_compressed_size(path)
        except (OSError, AttributeError, ImportError, ValueError):
            pass
    return info.st_size


def analyze(root, min_bytes=500 * 1024**2, limit=30):
    root = Path(root).expanduser().resolve(strict=True)
    if not root.is_dir():
        raise ValueError("root must be a directory")
    root_device = os.stat(root).st_dev
    disk = shutil.disk_usage(root)
    home = Path.home().resolve()
    cache_roots = cache_locations(home)
    labels = {home / relative: label for relative, label in CACHE_PATHS}
    candidates = {}
    incomplete = set()

    def add_candidate(path, label):
        if key(path) not in candidates and not any(
                key(parent) in candidates for parent in path.parents):
            candidates[key(path)] = {"path": str(path), "kind": label,
                                     "allocated_bytes": 0, "scan_complete": True}

    def mark_incomplete(path):
        for ancestor in (path, *path.parents):
            if key(ancestor) in candidates:
                incomplete.add(key(ancestor))

    for relative, label in CACHE_PATHS:
        path = home / relative
        if (path == root or root in path.parents) and not any(
                base in path.parents for base in cache_roots):
            add_candidate(path, label)
    # A targeted scan can start at or below an application cache.
    for base in cache_roots:
        if base in root.parents:
            child = base / root.relative_to(base).parts[0]
            add_candidate(root, labels.get(child, "Application cache (review contents)"))
    root_label = project_cache_label(root, home)
    if root_label:
        add_candidate(root, root_label)
    errors, mounts, top, large = [], [], {}, []
    error_count = skipped_links = cloud_only = visited = total = 0
    seen = set()

    def record_error(path, exc):
        nonlocal error_count
        error_count += 1
        mark_incomplete(path)
        if len(errors) < 100:
            errors.append({"path": str(path), "error": str(exc)})

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
                        # On Windows, DirEntry.stat() leaves st_dev, st_ino and
                        # st_nlink at zero; lstat fills them without following
                        # links or junctions.
                        info = (os.lstat(entry.path) if WINDOWS
                                else entry.stat(follow_symlinks=False))
                        if is_link(info):
                            skipped_links += 1
                            mark_incomplete(path.parent)
                            continue
                        if info.st_dev != root_device:
                            if len(mounts) < 100:
                                mounts.append(str(path))
                            mark_incomplete(path.parent)
                            continue
                        if path.parent in cache_roots and (
                                stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode)):
                            add_candidate(path, labels.get(path, APP_CACHE_LABELS.get(
                                path.name, "Application cache (review contents)")))
                        if stat.S_ISDIR(info.st_mode):
                            label = project_cache_label(path, home)
                            if label:
                                add_candidate(path, label)
                            stack.append((path, bucket))
                            continue
                        if not stat.S_ISREG(info.st_mode):
                            continue
                        if info.st_nlink > 1:
                            identity = (info.st_dev, info.st_ino)
                            if identity in seen:
                                continue
                            seen.add(identity)
                        visited += 1
                        if is_cloud_only(info):
                            cloud_only += 1
                        size = allocated(info, path)
                        total += size
                        top[bucket] = top.get(bucket, 0) + size
                        for ancestor in (path, *path.parents):
                            item = candidates.get(key(ancestor))
                            if item is not None:
                                item["allocated_bytes"] += size
                        if info.st_size >= min_bytes:
                            record = (info.st_size, str(path), size)
                            if len(large) < limit:
                                heapq.heappush(large, record)
                            elif record > large[0]:
                                heapq.heapreplace(large, record)
                    except OSError as exc:
                        record_error(path, exc)
        except OSError as exc:
            record_error(directory, exc)
    # Errors, links or mounts inside a candidate make its total an estimate.
    for name, item in candidates.items():
        item["scan_complete"] = name not in incomplete
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
        "cloud_only_files": cloud_only,
        "notes": ["Sizes exclude directory metadata. Hard-linked files counted once; attribution follows traversal order.",
                  "Logical file size may exceed physical allocation. Totals are estimates, not guaranteed reclaimable space.",
                  "The entire scan root is inventoried, including hidden directories. Cache classification does not authorize deletion.",
                  "Application cache roots and known tool paths under the current user's home are classified. Other locations require manual review.",
                  "Symbolic links, Windows junctions and mount points are skipped. Cloud-only placeholder files count as 0 allocated bytes."]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=str(Path.home()),
                        help="Directory to scan (default: current user's home)")
    parser.add_argument("--min-size-mb", type=float, default=500,
                        help="Minimum logical size in MiB for large_files "
                             "(default: 500)")
    parser.add_argument("--limit", type=int, default=30,
                        help="Maximum number of large_files (default: 30)")
    args = parser.parse_args()
    if args.limit < 1 or args.min_size_mb < 0:
        parser.error("limit must be positive and min-size-mb nonnegative")
    if sys.platform not in SUPPORTED_PLATFORMS:
        parser.error("supported platforms: macOS, Linux and Windows")
    try:
        report = analyze(args.root, int(args.min_size_mb * 1024**2), args.limit)
    except (OSError, ValueError) as exc:
        parser.exit(2, str(exc) + "\n")
    print(json.dumps(report, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
