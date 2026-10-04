import os
import subprocess
from pathlib import Path

import tempfile
import unittest

from music_folder_builder.infrastructure.fs.path_safety import is_reparse_point, validate_path
from music_folder_builder.infrastructure.fs.mutation_gateway import FileMutationGateway
from music_folder_builder.infrastructure.fs.walker import FileWalker


def paths(tmp_path):
    source_root = tmp_path / "source"
    target_root = tmp_path / "target"
    source_root.mkdir(); target_root.mkdir()
    source = source_root / "日本語🎵.flac"
    target = target_root / "album" / source.name
    source.write_bytes(b"test music")
    return source_root, target_root, source, target



class PathSecurityTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.tmp_path = Path(directory.name)

    def test_root_escape_and_normalization(self):
        tmp_path = self.tmp_path
        source_root, target_root, source, target = paths(tmp_path)
        with self.assertRaisesRegex(ValueError, "outside_root"):
            validate_path(target_root / ".." / "outside", target_root)
        validate_path(target_root / "album" / ".." / "valid", target_root)


    @unittest.skipUnless(os.name == "nt", "Destructive operations require native Windows")
    def test_move_and_rollback_preserve_unicode(self):
        tmp_path = self.tmp_path
        source_root, target_root, source, target = paths(tmp_path)
        gateway = FileMutationGateway()
        with gateway.guarded_paths(source, target, source_root, target_root):
            gateway.move(source, target)
        assert not source.exists() and target.read_bytes() == b"test music"
        with gateway.guarded_paths(target, source, target_root, source_root):
            gateway.move(target, source)
        assert source.read_bytes() == b"test music" and not target.exists()


    @unittest.skipUnless(os.name == "nt", "Windows sharing semantics")
    def test_copy_delete_preserves_times(self):
        tmp_path = self.tmp_path
        source_root, target_root, source, target = paths(tmp_path)
        os.utime(source, (1600000000, 1600000000))
        gateway = FileMutationGateway()
        with gateway.guarded_paths(source, target, source_root, target_root):
            gateway.copy(source, target)
            gateway.delete(source)
        assert not source.exists() and target.read_bytes() == b"test music"
        assert target.stat().st_mtime == 1600000000


    @unittest.skipUnless(os.name == "nt", "Windows sharing semantics")
    def test_pinned_source_and_parent_cannot_be_substituted(self):
        tmp_path = self.tmp_path
        source_root, target_root, source, target = paths(tmp_path)
        gateway = FileMutationGateway()
        with gateway.guarded_paths(source, target, source_root, target_root):
            with self.assertRaises(OSError): source.rename(source.with_suffix(".old"))
            with self.assertRaises(OSError): target.parent.rename(target.parent.with_name("old"))
            with self.assertRaises(OSError): source.write_bytes(b"replacement")
            gateway.move(source, target)
        assert target.read_bytes() == b"test music"


    @unittest.skipUnless(os.name == "nt", "Windows create-new semantics")
    def test_competing_destination_is_not_overwritten(self):
        tmp_path = self.tmp_path
        source_root, target_root, source, target = paths(tmp_path)
        gateway = FileMutationGateway()
        with gateway.guarded_paths(source, target, source_root, target_root):
            target.write_bytes(b"existing")
            with self.assertRaises(OSError): gateway.move(source, target)
            with self.assertRaises(OSError): gateway.copy(source, target)
        assert target.read_bytes() == b"existing" and source.read_bytes() == b"test music"


    @unittest.skipUnless(os.name == "nt", "Windows junction")
    def test_junction_is_rejected_without_touching_target(self):
        tmp_path = self.tmp_path
        root = tmp_path / "root"; outside = tmp_path / "outside"
        root.mkdir(); outside.mkdir()
        sentinel = outside / "sentinel.flac"; sentinel.write_bytes(b"keep")
        junction = root / "junction"
        environment = os.environ.copy()
        environment["TEST_JUNCTION"] = str(junction)
        environment["TEST_JUNCTION_TARGET"] = str(outside)
        subprocess.run(["powershell.exe", "-NoProfile", "-Command",
            "New-Item -ItemType Junction -Path $env:TEST_JUNCTION -Target $env:TEST_JUNCTION_TARGET | Out-Null"],
            env=environment, check=True, capture_output=True)
        try:
            assert is_reparse_point(junction)
            with self.assertRaisesRegex(ValueError, "reparse"):
                validate_path(junction / "sentinel.flac", root)
            with self.assertRaisesRegex(ValueError, "reparse"):
                validate_path(sentinel, junction)
            entries = list(FileWalker(follow_links=True).walk(root))
            self.assertEqual(1, len(entries))
            self.assertEqual("ignored", entries[0].file_type)
            assert sentinel.read_bytes() == b"keep"
        finally:
            junction.rmdir()


    @unittest.skipUnless(os.name == "nt", "Windows symbolic links")
    def test_symbolic_links_are_rejected_without_touching_target(self):
        root = self.tmp_path / "root"
        outside = self.tmp_path / "outside"
        root.mkdir(); outside.mkdir()
        sentinel = outside / "sentinel.flac"
        sentinel.write_bytes(b"keep")
        directory_link = root / "directory-link"
        file_link = root / "file-link.flac"
        try:
            directory_link.symlink_to(outside, target_is_directory=True)
            file_link.symlink_to(sentinel)
        except OSError as error:
            if os.environ.get("SECURITY_REQUIRE_SYMLINK") == "1":
                raise
            self.skipTest(f"Symbolic-link creation is unavailable: {error}")
        finally:
            self.addCleanup(lambda: directory_link.unlink(missing_ok=True))
            self.addCleanup(lambda: file_link.unlink(missing_ok=True))
        for link in [directory_link / sentinel.name, file_link]:
            with self.assertRaisesRegex(ValueError, "reparse"):
                validate_path(link, root)
        entries = list(FileWalker(follow_links=True).walk(root))
        self.assertEqual(2, len(entries))
        self.assertTrue(all(entry.file_type == "ignored" for entry in entries))
        self.assertEqual(b"keep", sentinel.read_bytes())
