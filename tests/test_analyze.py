import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

MODULE = Path(__file__).resolve().parents[1] / "skills/disk-cleanup/scripts/analyze.py"
spec = importlib.util.spec_from_file_location("disk_analyze", MODULE)
scanner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scanner)


class AnalyzeTests(unittest.TestCase):
    def test_read_only_size_order_symlinks_and_hardlinks(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as outside:
            root = Path(tmp)
            small = root / "small"
            big = root / "large with spaces;$(echo unsafe)"
            small.write_bytes(b"a" * 10)
            big.write_bytes(b"b" * 8192)
            os.link(big, root / "hardlink")
            (Path(outside) / "external").write_bytes(b"z" * 20000)
            (root / "link").symlink_to(outside, target_is_directory=True)
            before = {p.name: p.lstat() for p in root.iterdir()}
            report = scanner.analyze(root, min_bytes=100, limit=1)
            self.assertEqual(report["files_scanned"], 2)
            self.assertEqual(report["skipped_symlinks"], 1)
            self.assertEqual(report["large_files"][0]["logical_bytes"], 8192)
            self.assertEqual(report["scan_error_count"], 0)
            after = {p.name: p.lstat() for p in root.iterdir()}
            self.assertEqual(before, after)
            self.assertEqual(big.read_bytes(), b"b" * 8192)

    def test_sparse_file_reports_both_sizes(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sparse"
            with path.open("wb") as handle:
                handle.truncate(20 * 1024**2)
            report = scanner.analyze(tmp, min_bytes=1024, limit=2)
            item = report["large_files"][0]
            self.assertEqual(item["logical_bytes"], 20 * 1024**2)
            self.assertEqual(item["allocated_bytes"], scanner.allocated(path.stat()))

    def test_known_cache_is_scoped_to_home(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cache = root / ".cache/uv"
            cache.mkdir(parents=True)
            (cache / "package").write_bytes(b"data" * 1024)
            with patch.object(scanner.Path, "home", return_value=root):
                report = scanner.analyze(root)
            self.assertEqual(len(report["cache_candidates"]), 1)
            self.assertEqual(report["cache_candidates"][0]["path"], str(cache.resolve()))
            with patch.object(scanner.Path, "home", return_value=root / "other"):
                self.assertEqual(scanner.analyze(root)["cache_candidates"], [])

    def test_permission_error_is_visible(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(scanner.os, "scandir", side_effect=PermissionError("denied")):
                report = scanner.analyze(tmp)
            self.assertEqual(report["scan_error_count"], 1)
            self.assertIn("denied", report["scan_errors"][0]["error"])

    def test_installed_cli_runs_outside_skill_directory(self):
        for harness in (".claude", ".agents"):
            for method in ("copy", "symlink"):
                with self.subTest(harness=harness, method=method):
                    with tempfile.TemporaryDirectory(prefix="disk cleanup ") as tmp:
                        workspace = Path(tmp)
                        canonical = workspace / "skill source" / "disk-cleanup"
                        shutil.copytree(MODULE.parent.parent, canonical)
                        # Execution must not depend on optional OpenAI UI metadata.
                        shutil.rmtree(canonical / "agents")
                        installed = workspace / harness / "skills" / "disk-cleanup"
                        installed.parent.mkdir(parents=True)
                        if method == "copy":
                            shutil.copytree(canonical, installed)
                        else:
                            installed.symlink_to(canonical, target_is_directory=True)
                        target = workspace / "scan target"
                        target.mkdir()
                        sample = target / "sample with spaces.bin"
                        sample.write_bytes(b"x" * 8192)
                        before = sample.stat()
                        working = workspace / "unrelated project"
                        working.mkdir()

                        result = subprocess.run(
                            [sys.executable, str(installed / "scripts" / "analyze.py"),
                             "--root", str(target), "--min-size-mb", "0", "--limit", "1"],
                            cwd=working, capture_output=True, text=True,
                            check=True, timeout=15,
                        )

                        report = json.loads(result.stdout)
                        self.assertEqual(report["root"], str(target.resolve()))
                        self.assertEqual(report["files_scanned"], 1)
                        self.assertEqual(report["scan_error_count"], 0)
                        self.assertEqual(report["large_files"][0]["path"], str(sample.resolve()))
                        self.assertEqual(report["large_files"][0]["logical_bytes"], 8192)
                        self.assertEqual(sample.stat(), before)
                        self.assertEqual(sample.read_bytes(), b"x" * 8192)


if __name__ == "__main__":
    unittest.main()
