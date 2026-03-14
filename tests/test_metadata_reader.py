import unittest
from pathlib import Path
from unittest.mock import patch

from music_folder_builder.infrastructure.metadata.reader import MetadataReadResult, MetadataReader


class FakeTextFrame:
    def __init__(self, *text: str) -> None:
        self.text = list(text)


class MetadataReaderTests(unittest.TestCase):
    def test_reads_vorbis_style_tags(self) -> None:
        audio = {
            "artist": ["Harvest"],
            "albumartist": ["(K)NoW_NAME"],
            "album": ["Harvest"],
            "title": ["01 Harvest"],
            "tracknumber": ["1/10"],
            "discnumber": ["1/1"],
            "date": ["2024-03-01"],
        }

        result = MetadataReader()._build_result(Path("song.flac"), audio)

        self.assertEqual(
            MetadataReadResult(
                artist="Harvest",
                album_artist="(K)NoW_NAME",
                album="Harvest",
                title="01 Harvest",
                track_no=1,
                disc_no=1,
                year=2024,
                metadata_status="ok",
                metadata_error=None,
            ),
            result,
        )

    def test_reads_id3_style_tags(self) -> None:
        audio = {
            "TPE1": FakeTextFrame("Artist"),
            "TPE2": FakeTextFrame("Album Artist"),
            "TALB": FakeTextFrame("Album"),
            "TIT2": FakeTextFrame("Song"),
            "TRCK": FakeTextFrame("02/09"),
            "TPOS": FakeTextFrame("1/2"),
            "TDRC": FakeTextFrame("2023"),
        }

        result = MetadataReader()._build_result(Path("song.mp3"), audio)

        self.assertEqual("Artist", result.artist)
        self.assertEqual("Album Artist", result.album_artist)
        self.assertEqual("Album", result.album)
        self.assertEqual("Song", result.title)
        self.assertEqual(2, result.track_no)
        self.assertEqual(1, result.disc_no)
        self.assertEqual(2023, result.year)
        self.assertEqual("ok", result.metadata_status)

    def test_falls_back_to_stem_when_title_missing(self) -> None:
        result = MetadataReader()._build_result(Path("03 rainy tone.mp3"), {})
        self.assertEqual("03 rainy tone", result.title)
        self.assertEqual("partial", result.metadata_status)

    def test_returns_error_when_mutagen_cannot_read_file(self) -> None:
        with patch("music_folder_builder.infrastructure.metadata.reader._load_mutagen_file", return_value=None):
            result = MetadataReader().read(Path("broken.mp3"))

        self.assertEqual("error", result.metadata_status)
        self.assertEqual("unsupported_or_unreadable_file", result.metadata_error)


if __name__ == "__main__":
    unittest.main()
