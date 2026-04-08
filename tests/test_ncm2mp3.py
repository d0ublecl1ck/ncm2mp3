import tempfile
import unittest
from unittest import mock
from pathlib import Path

from PyQt5.QtWidgets import QApplication

from licensing import LicenseManager, fingerprint_hash, normalize_fingerprint, validate_fingerprint
from ncm2mp3 import (
    DecodedAudio,
    MainWindow,
    build_key_box,
    file_sha256,
    strip_prefix,
    transcode_to_mp3,
    verify_bundled_ffmpeg,
)


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

    def test_verify_bundled_ffmpeg_accepts_expected_hashes(self) -> None:
        verify_bundled_ffmpeg(Path("."), "darwin")

    def test_verify_bundled_ffmpeg_rejects_tampered_binary(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            target = root / "binaries" / "macos"
            target.mkdir(parents=True, exist_ok=True)
            (target / "ffmpeg").write_bytes(b"tampered")
            with self.assertRaisesRegex(Exception, "校验失败"):
                verify_bundled_ffmpeg(root, "darwin")


class LicenseTests(unittest.TestCase):
    def test_env_public_key_no_longer_overrides_embedded_key(self) -> None:
        with mock.patch.dict("os.environ", {"NCM2MP3_PUBLIC_KEY": "ZmFrZQ=="}, clear=False):
            manager = LicenseManager()
        self.assertIsNotNone(manager.public_key)

    def test_fingerprint_requires_cpu_and_mac_address(self) -> None:
        valid, message = validate_fingerprint(
            normalize_fingerprint({"cpu_id": "", "mac_address": "", "disk_serial": "", "platform": "darwin"})
        )
        self.assertFalse(valid)
        self.assertIn("关键标识", message)

    def test_fingerprint_hash_is_stable(self) -> None:
        payload = {
            "cpu_id": "cpu-123",
            "mac_address": "aa:bb:cc:dd:ee:ff",
            "disk_serial": "disk-123",
            "platform": "darwin",
        }
        self.assertEqual(fingerprint_hash(payload), fingerprint_hash(dict(payload)))


class WindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_window_defaults(self) -> None:
        window = MainWindow()
        self.assertEqual(window.windowTitle(), "NCM/FLAC 转 MP3")
        self.assertFalse(window.convert_button.isEnabled())
        self.assertEqual(window.progress_bar.value(), 0)


if __name__ == "__main__":
    unittest.main()
