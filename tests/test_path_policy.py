import unittest
from pathlib import PureWindowsPath

from music_folder_builder.domain.policies.path_policy import PathPolicy, PathRisk
from music_folder_builder.domain.policies.path_sanitization import PathSanitizer


class PathSanitizerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.sanitizer = PathSanitizer()

    def test_replaces_invalid_windows_characters(self) -> None:
        sanitized = self.sanitizer.sanitize_component('AC:DC?*<>|"')
        self.assertEqual("AC_DC______", sanitized)

    def test_sanitizes_reserved_names(self) -> None:
        sanitized = self.sanitizer.sanitize_component("CON")
        self.assertEqual("_CON", sanitized)

    def test_removes_invalid_trailing_space_and_period(self) -> None:
        sanitized = self.sanitizer.sanitize_component("Album . ")
        self.assertEqual("Album", sanitized)

    def test_sanitizes_each_component_in_path(self) -> None:
        path = PureWindowsPath(r"Artist\CON\Best:Hits.\Track 01? ")
        sanitized = self.sanitizer.sanitize_path(path)
        self.assertEqual(PureWindowsPath(r"Artist\_CON\Best_Hits\Track 01_"), sanitized)


class PathPolicyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = PathPolicy(max_component_length=12, max_path_length=40)

    def test_detects_component_length_risk(self) -> None:
        risk = self.policy.assess(PureWindowsPath(r"Artist\VeryLongAlbumName\Track.flac"))
        self.assertEqual(PathRisk("invalid_target", "component_too_long"), risk)

    def test_detects_full_path_length_risk(self) -> None:
        policy = PathPolicy(max_component_length=64, max_path_length=20)
        risk = policy.assess(PureWindowsPath(r"Artist\Album\123456789012.flac"))
        self.assertEqual(PathRisk("path_too_long", "path_length_exceeded"), risk)

    def test_returns_none_for_safe_path(self) -> None:
        risk = self.policy.assess(PureWindowsPath(r"Artist\Album\Track.flac"))
        self.assertEqual(PathRisk("none", None), risk)


if __name__ == "__main__":
    unittest.main()
