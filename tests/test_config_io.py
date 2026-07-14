import tempfile
import unittest
from pathlib import Path

from music_folder_builder.cli.config import load_config, save_config


class ConfigIoTests(unittest.TestCase):
    def test_save_and_load_config_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config_path = Path(tmp_dir) / "local.toml"
            save_config(
                config_path,
                {
                    "scan": {"source": "/music", "db": "/workspace/state.db"},
                    "display": {"timezone": "Asia/Tokyo"},
                    "naming": {
                        "filename_template": "[{track_no:02d}_]{title}{extension}",
                        "duplicate_suffix_template": "_{source_stem}",
                        "use_source_filename": True,
                        "use_source_image_filename": True,
                    },
                },
            )

            loaded = load_config(config_path)

            self.assertEqual("/music", loaded["scan"]["source"])
            self.assertEqual("Asia/Tokyo", loaded["display"]["timezone"])
            self.assertEqual(
                "[{track_no:02d}_]{title}{extension}",
                loaded["naming"]["filename_template"],
            )
            self.assertEqual("_{source_stem}", loaded["naming"]["duplicate_suffix_template"])
            self.assertTrue(loaded["naming"]["use_source_filename"])
            self.assertTrue(loaded["naming"]["use_source_image_filename"])


if __name__ == "__main__":
    unittest.main()
