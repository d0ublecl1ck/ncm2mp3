import tempfile
import unittest
from pathlib import Path

from PyQt5.QtWidgets import QApplication

from ncm2mp3 import DecodedAudio, MainWindow, build_key_box, strip_prefix, transcode_to_mp3


class HelperTests(unittest.TestCase):
    def test_strip_prefix_removes_matching_prefix(self) -> None:
        self.assertEqual(strip_prefix(b"prefix-data", b"prefix-"), b"data")
        self.assertEqual(strip_prefix(b"plain-data", b"prefix-"), b"plain-data")

    def test_build_key_box_returns_permutation(self) -> None:
        box = build_key_box(b"sample-key")
        other_box = build_key_box(b"sample-key")
        self.assertEqual(len(box), 256)
        self.assertEqual(box, other_box)
        self.assertGreater(len(set(box)), 32)

    def test_mp3_passthrough_writes_file(self) -> None:
        decoded = DecodedAudio(format_name="mp3", audio_bytes=b"fake-mp3-bytes")
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "song.mp3"
            transcode_to_mp3(decoded, output)
            self.assertTrue(output.exists())
            self.assertEqual(output.read_bytes(), b"fake-mp3-bytes")


class WindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_window_defaults(self) -> None:
        window = MainWindow()
        self.assertEqual(window.windowTitle(), "NCM 转 MP3")
        self.assertFalse(window.convert_button.isEnabled())
        self.assertEqual(window.progress_bar.value(), 0)


if __name__ == "__main__":
    unittest.main()
