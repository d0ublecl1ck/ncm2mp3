from __future__ import annotations

import base64
import json
import hashlib
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from Crypto.Cipher import AES
from PyQt5.QtCore import QThread, Qt, pyqtSignal
from PyQt5.QtGui import QColor, QFont
from PyQt5.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from PyQt5.QtWidgets import QSizePolicy, QAction

from licensing.activation_dialog import LicenseChecker


CORE_KEY = bytes.fromhex("687A4852416D736F356B496E62617857")
META_KEY = bytes.fromhex("2331346C6A6B5F215C5D2630553C2728")
NCM_HEADER = bytes.fromhex("4354454e4644414d")
DEFAULT_WINDOW_SIZE = (720, 420)
BUNDLED_FFMPEG_HASHES = {
    "darwin": {
        "binaries/macos/ffmpeg": "dfe6df9286909cc6a6bfbe867c8461fe79f732ce5ed996991ea2d43054b39b5e",
    },
    "win32": {
        "binaries/windows/ffmpeg.exe": "0692c94df5862bd09ba10c6572f27e6992c7640babb493bf8081161b1098a2f4",
        "binaries/windows/avcodec-62.dll": "2df72c409c1d3be23ece29418407c6975f38c0c330ebc7ff64f4908fb731a274",
        "binaries/windows/avdevice-62.dll": "f3d915bbeaba44e145e781f6df08c9cfb6ee3862d3926e517d60f908d38cd2e7",
        "binaries/windows/avfilter-11.dll": "60d0fef7a898c2c836097147ab63d8f208d105fd5bd02e6f767c5aa928124e20",
        "binaries/windows/avformat-62.dll": "342d05db0efcc2cd64a1494257aa477ac8197bb393bf7a820fa512d1ac9fdf43",
        "binaries/windows/avutil-60.dll": "068cbb59923354c3761256367582fc2ddbb77567648f3dd20aa1518e9aefa89d",
        "binaries/windows/swresample-6.dll": "481754633d53d7c39a1d32e2e52bb58a9f544fd6a5f867a10560f318f18e8540",
        "binaries/windows/swscale-9.dll": "2c499598b334dff9ccdcd51b252d7d5a2cc848efd436187cede9134fd31b60f1",
    },
}


class NCMError(Exception):
    """Raised when an NCM file cannot be decoded or transcoded."""


def xor_bytes(payload: bytes, value: int) -> bytes:
    return bytes(byte ^ value for byte in payload)


def remove_pkcs7_padding(payload: bytes) -> bytes:
    pad = payload[-1]
    if pad < 1 or pad > 16:
        raise NCMError("NCM 数据填充无效。")
    return payload[:-pad]


def aes_ecb_decrypt(key: bytes, payload: bytes) -> bytes:
    cipher = AES.new(key, AES.MODE_ECB)
    return remove_pkcs7_padding(cipher.decrypt(payload))


def strip_prefix(payload: bytes, prefix: bytes) -> bytes:
    if payload.startswith(prefix):
        return payload[len(prefix) :]
    return payload


def build_key_box(key_data: bytes) -> bytes:
    key_box = list(range(256))
    last_pos = 0
    key_length = len(key_data)
    for index in range(256):
        last_pos = (key_box[index] + last_pos + key_data[index % key_length]) & 0xFF
        key_box[index], key_box[last_pos] = key_box[last_pos], key_box[index]

    box = bytearray(256)
    for index in range(256):
        idx = (index + 1) & 0xFF
        swap_value = key_box[(idx + key_box[idx]) & 0xFF]
        box[index] = key_box[(key_box[idx] + swap_value) & 0xFF]
    return bytes(box)


@dataclass(slots=True)
class DecodedAudio:
    format_name: str
    audio_bytes: bytes


def decode_ncm_file(file_path: Path) -> DecodedAudio:
    raw = file_path.read_bytes()
    offset = 0

    header = raw[offset : offset + 8]
    offset += 8
    if header != NCM_HEADER:
        raise NCMError(f"{file_path.name} 不是有效的 NCM 文件。")

    offset += 2

    key_length = int.from_bytes(raw[offset : offset + 4], "little")
    offset += 4
    key_data = xor_bytes(raw[offset : offset + key_length], 0x64)
    offset += key_length
    key_data = aes_ecb_decrypt(CORE_KEY, key_data)
    key_data = strip_prefix(key_data, b"neteasecloudmusic")
    key_box = build_key_box(key_data)

    metadata_length = int.from_bytes(raw[offset : offset + 4], "little")
    offset += 4
    metadata = xor_bytes(raw[offset : offset + metadata_length], 0x63)
    offset += metadata_length
    metadata = strip_prefix(metadata, b"163 key(Don't modify):")
    metadata = base64.b64decode(metadata)
    metadata = aes_ecb_decrypt(META_KEY, metadata)
    metadata = strip_prefix(metadata, b"music:")
    metadata_json = json.loads(metadata.decode("utf-8"))

    offset += 4
    offset += 5

    image_size = int.from_bytes(raw[offset : offset + 4], "little")
    offset += 4 + image_size

    encrypted_audio = raw[offset:]
    audio = bytearray(encrypted_audio)
    for index in range(len(audio)):
        audio[index] ^= key_box[index & 0xFF]

    format_name = str(metadata_json.get("format") or "bin").lower()
    return DecodedAudio(format_name=format_name, audio_bytes=bytes(audio))


def get_ffmpeg_path() -> str | None:
    """获取 ffmpeg 路径，优先使用内置版本。"""
    # 检查是否是 PyInstaller 打包环境
    if getattr(sys, "frozen", False):
        # 打包后的可执行文件目录
        base_path = Path(sys._MEIPASS)
    else:
        # 开发环境：项目根目录
        base_path = Path(__file__).parent

    # 根据平台选择内置 ffmpeg
    if sys.platform == "darwin":
        bundled = base_path / "binaries" / "macos" / "ffmpeg"
    elif sys.platform == "win32":
        bundled = base_path / "binaries" / "windows" / "ffmpeg.exe"
    else:
        bundled = None

    if bundled and bundled.exists():
        verify_bundled_ffmpeg(base_path, sys.platform)
        return str(bundled)

    # 回退到系统 PATH
    return shutil.which("ffmpeg")


def file_sha256(file_path: Path) -> str:
    digest = hashlib.sha256()
    with file_path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_bundled_ffmpeg(base_path: Path, platform_name: str) -> None:
    expected_hashes = BUNDLED_FFMPEG_HASHES.get(platform_name, {})
    for relative_path, expected_hash in expected_hashes.items():
        file_path = base_path / relative_path
        if not file_path.is_file():
            raise NCMError(f"内置 FFmpeg 文件缺失：{relative_path}")
        actual_hash = file_sha256(file_path)
        if actual_hash != expected_hash:
            raise NCMError(f"内置 FFmpeg 文件校验失败：{relative_path}")


def transcode_to_mp3(decoded_audio: DecodedAudio, output_file: Path) -> None:
    output_file.parent.mkdir(parents=True, exist_ok=True)

    if decoded_audio.format_name == "mp3":
        output_file.write_bytes(decoded_audio.audio_bytes)
        return

    ffmpeg_path = get_ffmpeg_path()
    if ffmpeg_path is None:
        raise NCMError("未检测到 ffmpeg，无法把非 MP3 源音频转成 MP3。")

    with tempfile.NamedTemporaryFile(
        suffix=f".{decoded_audio.format_name}",
        delete=False,
    ) as temp_file:
        temp_path = Path(temp_file.name)
        temp_file.write(decoded_audio.audio_bytes)

    try:
        command = [
            ffmpeg_path,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(temp_path),
            "-vn",
            "-c:a",
            "libmp3lame",
            "-q:a",
            "2",
            str(output_file),
        ]
        completed = subprocess.run(command, capture_output=True, text=True, check=False)
        if completed.returncode != 0:
            stderr = completed.stderr.strip() or completed.stdout.strip() or "未知错误"
            raise NCMError(f"ffmpeg 转码失败：{stderr}")
    finally:
        temp_path.unlink(missing_ok=True)


def transcode_flac_to_mp3(flac_file: Path, output_file: Path) -> None:
    """使用 ffmpeg 将 FLAC 文件转码为 MP3。"""
    output_file.parent.mkdir(parents=True, exist_ok=True)

    ffmpeg_path = get_ffmpeg_path()
    if ffmpeg_path is None:
        raise NCMError("未检测到 ffmpeg，无法将 FLAC 转成 MP3。")

    command = [
        ffmpeg_path,
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-i",
        str(flac_file),
        "-vn",
        "-c:a",
        "libmp3lame",
        "-q:a",
        "2",
        str(output_file),
    ]
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        stderr = completed.stderr.strip() or completed.stdout.strip() or "未知错误"
        raise NCMError(f"ffmpeg 转码失败：{stderr}")


class ConvertWorker(QThread):
    progress_changed = pyqtSignal(int)
    status_changed = pyqtSignal(str)
    finished_success = pyqtSignal(str)
    failed = pyqtSignal(str)

    def __init__(self, folder: Path) -> None:
        super().__init__()
        self.folder = folder

    def run(self) -> None:
        try:
            # 同时支持 .ncm 和 .flac 文件
            ncm_files = sorted(self.folder.glob("*.ncm"))
            flac_files = sorted(self.folder.glob("*.flac"))
            all_files = ncm_files + flac_files

            if not all_files:
                raise NCMError("所选文件夹中没有找到 .ncm 或 .flac 文件。")

            total = len(all_files)
            self.progress_changed.emit(0)

            for index, audio_file in enumerate(all_files, start=1):
                self.status_changed.emit(f"正在转换：{audio_file.name}")
                output_path = audio_file.with_suffix(".mp3")

                if audio_file.suffix.lower() == ".ncm":
                    # NCM 文件：先解密，再转码（如果需要）
                    decoded_audio = decode_ncm_file(audio_file)
                    transcode_to_mp3(decoded_audio, output_path)
                elif audio_file.suffix.lower() == ".flac":
                    # FLAC 文件：直接使用 ffmpeg 转码
                    transcode_flac_to_mp3(audio_file, output_path)

                progress = int(index / total * 100)
                self.progress_changed.emit(progress)

            self.status_changed.emit("全部转换完成。")
            self.finished_success.emit(f"成功转换 {total} 个文件。")
        except Exception as exc:  # pragma: no cover - GUI thread signal path
            self.failed.emit(str(exc))


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.selected_folder: Path | None = None
        self.worker: ConvertWorker | None = None
        self.setWindowTitle("NCM/FLAC 转 MP3")
        self.resize(*DEFAULT_WINDOW_SIZE)
        self.setMinimumSize(680, 380)
        self._init_ui()

    def _init_ui(self) -> None:
        # 创建菜单栏
        self._create_menu_bar()

        self.setStyleSheet(
            """
            QMainWindow {
                background: #f5f5f4;
            }
            QLabel {
                color: #171717;
            }
            QLabel[pathRole="muted"] {
                color: #525252;
            }
            QFrame#Card {
                background: #ffffff;
                border: 1px solid #e5e5e5;
                border-radius: 22px;
            }
            QPushButton {
                background: #171717;
                color: #ffffff;
                border: none;
                border-radius: 14px;
                padding: 0 22px;
                min-height: 52px;
            }
            QPushButton:hover {
                background: #262626;
            }
            QPushButton:disabled {
                background: #a3a3a3;
                color: #f5f5f5;
            }
            QPushButton[secondary="true"] {
                background: #ffffff;
                color: #171717;
                border: 1px solid #d4af37;
            }
            QPushButton[secondary="true"]:hover {
                background: #faf7ea;
            }
            QProgressBar {
                background: #f5f5f4;
                border: 1px solid #e7e5e4;
                border-radius: 10px;
                text-align: center;
                min-height: 18px;
                color: #171717;
                font-weight: 600;
            }
            QProgressBar::chunk {
                background: #d4af37;
                border-radius: 9px;
            }
            """
        )

        central = QWidget()
        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(28, 28, 28, 28)

        card = QFrame()
        card.setObjectName("Card")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(28, 28, 28, 28)
        card_layout.setSpacing(18)

        title = QLabel("NCM/FLAC 批量转 MP3")
        title_font = QFont()
        title_font.setPointSize(24)
        title_font.setBold(True)
        title.setFont(title_font)

        subtitle = QLabel("选择一个文件夹后，程序会把其中所有 .ncm 和 .flac 文件转换成同名 .mp3 文件。")
        subtitle.setWordWrap(True)
        subtitle.setProperty("pathRole", "muted")

        path_label_title = QLabel("当前文件夹")
        path_label_title.setStyleSheet("font-weight: 600;")

        self.path_value_label = QLabel("尚未选择文件夹")
        self.path_value_label.setWordWrap(True)
        self.path_value_label.setProperty("pathRole", "muted")
        self.path_value_label.setMinimumHeight(56)
        self.path_value_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.path_value_label.setStyleSheet(
            "background:#fafaf9;border:1px solid #e7e5e4;border-radius:14px;padding:12px;"
        )

        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("%p%")

        self.status_label = QLabel("等待选择文件夹。")
        self.status_label.setProperty("pathRole", "muted")
        self.status_label.setWordWrap(True)

        button_row = QHBoxLayout()
        button_row.setSpacing(12)

        self.select_button = QPushButton("选择文件夹")
        self._apply_button_metrics(self.select_button)
        self.select_button.setProperty("secondary", True)
        self.select_button.clicked.connect(self.choose_folder)
        self.select_button.setCursor(Qt.PointingHandCursor)
        self.select_button.style().unpolish(self.select_button)
        self.select_button.style().polish(self.select_button)

        self.convert_button = QPushButton("开始转换")
        self._apply_button_metrics(self.convert_button)
        self.convert_button.clicked.connect(self.start_conversion)
        self.convert_button.setCursor(Qt.PointingHandCursor)
        self.convert_button.setEnabled(False)

        button_row.addWidget(self.select_button)
        button_row.addWidget(self.convert_button)

        card_layout.addWidget(title)
        card_layout.addWidget(subtitle)
        card_layout.addSpacing(8)
        card_layout.addWidget(path_label_title)
        card_layout.addWidget(self.path_value_label)
        card_layout.addSpacing(4)
        card_layout.addWidget(self.progress_bar)
        card_layout.addWidget(self.status_label)
        card_layout.addSpacing(10)
        card_layout.addLayout(button_row)

        root_layout.addWidget(card)
        self.setCentralWidget(central)

    def _create_menu_bar(self) -> None:
        """创建菜单栏"""
        menubar = self.menuBar()

        # 帮助菜单
        help_menu = menubar.addMenu("帮助")

        # 激活状态菜单项
        license_action = QAction("🔒 激活状态", self)
        license_action.triggered.connect(self._show_license_info)
        help_menu.addAction(license_action)

        # 关于菜单项
        about_action = QAction("关于", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    def _show_license_info(self) -> None:
        """显示许可证信息"""
        LicenseChecker.show_activation_info(self)

    def _show_about(self) -> None:
        """显示关于对话框"""
        QMessageBox.information(
            self, "关于",
            "NCM2MP3 - 音频格式转换工具\n\n"
            "支持 .ncm 和 .flac 格式批量转换为 MP3\n\n"
            "© 2025 All Rights Reserved"
        )

    def _apply_button_metrics(self, button: QPushButton) -> None:
        font = QFont()
        font.setPointSize(14)
        font.setWeight(QFont.DemiBold)
        button.setFont(font)
        button.setMinimumHeight(52)
        button.setMinimumWidth(180)
        button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def choose_folder(self) -> None:
        chosen = QFileDialog.getExistingDirectory(self, "选择包含 NCM/FLAC 文件的文件夹")
        if not chosen:
            return

        self.selected_folder = Path(chosen)
        self.path_value_label.setText(str(self.selected_folder))
        self.status_label.setText("文件夹已选择，可以开始转换。")
        self.progress_bar.setValue(0)
        self.convert_button.setEnabled(True)

    def start_conversion(self) -> None:
        if self.selected_folder is None:
            QMessageBox.warning(self, "未选择文件夹", "请先选择一个文件夹。")
            return

        if self.worker is not None and self.worker.isRunning():
            QMessageBox.information(self, "任务进行中", "当前正在转换，请稍候。")
            return

        self.worker = ConvertWorker(self.selected_folder)
        self.worker.progress_changed.connect(self.progress_bar.setValue)
        self.worker.status_changed.connect(self.status_label.setText)
        self.worker.finished_success.connect(self.on_conversion_success)
        self.worker.failed.connect(self.on_conversion_failed)
        self.worker.finished.connect(self.worker.deleteLater)

        self.select_button.setEnabled(False)
        self.convert_button.setEnabled(False)
        self.status_label.setText("准备开始转换。")
        self.worker.start()

    def on_conversion_success(self, message: str) -> None:
        self.worker = None
        self.select_button.setEnabled(True)
        self.convert_button.setEnabled(True)
        QMessageBox.information(self, "转换完成", message)

    def on_conversion_failed(self, message: str) -> None:
        self.worker = None
        self.select_button.setEnabled(True)
        self.convert_button.setEnabled(True)
        self.status_label.setText("转换失败。")
        QMessageBox.critical(self, "转换失败", message)


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("ncm2mp3")
    app.setStyle("Fusion")

    palette = app.palette()
    palette.setColor(palette.Window, QColor("#f5f5f4"))
    palette.setColor(palette.WindowText, QColor("#171717"))
    palette.setColor(palette.Base, QColor("#ffffff"))
    palette.setColor(palette.Text, QColor("#171717"))
    palette.setColor(palette.Button, QColor("#171717"))
    palette.setColor(palette.ButtonText, QColor("#ffffff"))
    app.setPalette(palette)

    # 检查许可证（启动时验证）
    if not LicenseChecker.check_and_prompt():
        # 用户取消激活或激活失败，退出程序
        sys.exit(0)

    window = MainWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
