"""
激活对话框模块
"""

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QLineEdit,
    QTextEdit,
    QMessageBox,
    QSizePolicy,
)

from licensing import license_manager


class ActivationDialog(QDialog):
    """激活对话框"""

    activated = pyqtSignal()  # 激活成功信号

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("软件激活")
        self.setMinimumSize(560, 420)
        self._init_ui()
        self._apply_styles()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # 标题
        title = QLabel("🔒 软件激活")
        title_font = QFont()
        title_font.setPointSize(20)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        # 说明
        desc = QLabel(
            "本软件需要激活后才能使用。请将下面的机器码复制发送给管理员，"
            "获取注册码后输入激活。"
        )
        desc.setWordWrap(True)
        desc.setAlignment(Qt.AlignCenter)
        layout.addWidget(desc)

        layout.addSpacing(12)

        # 机器码区域
        machine_code_label = QLabel("您的机器码：")
        machine_code_label.setStyleSheet("font-weight: 600;")
        layout.addWidget(machine_code_label)

        self.machine_code_text = QTextEdit()
        self.machine_code_text.setReadOnly(True)
        self.machine_code_text.setMaximumHeight(80)
        self.machine_code_text.setStyleSheet(
            "background: #f5f5f4; border: 1px solid #d4d4d4; border-radius: 8px; padding: 8px;"
        )

        # 生成机器码
        self.machine_code_error = ""
        try:
            machine_code = license_manager.generate_machine_code()
        except Exception as exc:
            machine_code = ""
            self.machine_code_error = str(exc)
        self.machine_code_text.setText(machine_code or "无法生成机器码")
        layout.addWidget(self.machine_code_text)

        # 复制按钮
        copy_btn = QPushButton("📋 复制机器码")
        copy_btn.clicked.connect(self._copy_machine_code)
        layout.addWidget(copy_btn)

        layout.addSpacing(16)

        # 注册码输入区域
        license_label = QLabel("请输入注册码：")
        license_label.setStyleSheet("font-weight: 600;")
        layout.addWidget(license_label)

        self.license_input = QTextEdit()
        self.license_input.setMaximumHeight(100)
        self.license_input.setPlaceholderText(
            "请将管理员提供的注册码粘贴到此处..."
        )
        self.license_input.setStyleSheet(
            "border: 2px solid #d4d4d4; border-radius: 8px; padding: 8px;"
        )
        layout.addWidget(self.license_input)

        # 按钮区域
        button_layout = QHBoxLayout()
        button_layout.setSpacing(12)

        self.activate_btn = QPushButton("✓ 激活")
        self.activate_btn.setStyleSheet(
            "background: #16a34a; color: white; font-weight: 600; padding: 12px 24px;"
        )
        self.activate_btn.clicked.connect(self._on_activate)
        self.activate_btn.setCursor(Qt.PointingHandCursor)

        exit_btn = QPushButton("退出")
        exit_btn.setStyleSheet(
            "background: #525252; color: white; padding: 12px 24px;"
        )
        exit_btn.clicked.connect(self.reject)
        exit_btn.setCursor(Qt.PointingHandCursor)

        button_layout.addWidget(exit_btn)
        button_layout.addWidget(self.activate_btn)
        layout.addLayout(button_layout)

        # 状态标签
        self.status_label = QLabel("")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet("color: #dc2626; font-weight: 500; padding-top: 8px;")
        if self.machine_code_error:
            self.status_label.setText(f"❌ {self.machine_code_error}")
            self.activate_btn.setEnabled(False)
        layout.addWidget(self.status_label)

    def _apply_styles(self):
        self.setStyleSheet("""
            QDialog {
                background: #ffffff;
            }
            QLabel {
                color: #171717;
            }
            QPushButton {
                border: none;
                border-radius: 8px;
                min-height: 40px;
            }
            QPushButton:hover {
                opacity: 0.9;
            }
            QTextEdit {
                font-family: monospace;
                font-size: 12px;
            }
        """)

    def _copy_machine_code(self):
        """复制机器码到剪贴板"""
        clipboard = self.machine_code_text.toPlainText()
        if not clipboard or self.machine_code_error:
            self.status_label.setStyleSheet("color: #dc2626; font-weight: 500; padding-top: 8px;")
            self.status_label.setText("❌ 当前设备无法生成可用机器码")
            return
        from PyQt5.QtWidgets import QApplication
        QApplication.clipboard().setText(clipboard)
        self.status_label.setStyleSheet("color: #16a34a; font-weight: 500; padding-top: 8px;")
        self.status_label.setText("✓ 机器码已复制到剪贴板")

    def _on_activate(self):
        """激活按钮点击"""
        license_key = self.license_input.toPlainText().strip()

        if not license_key:
            self.status_label.setStyleSheet("color: #dc2626; font-weight: 500; padding-top: 8px;")
            self.status_label.setText("❌ 请输入注册码")
            return

        # 验证注册码
        is_valid, message = license_manager.verify_license(license_key)

        if is_valid:
            # 保存注册码
            if license_manager.save_license(license_key):
                QMessageBox.information(
                    self, "激活成功",
                    "🎉 软件已成功激活！\n\n"
                    "感谢您购买正版软件，现在可以开始使用 NCM2MP3。"
                )
                self.activated.emit()
                self.accept()
            else:
                self.status_label.setStyleSheet("color: #dc2626; font-weight: 500; padding-top: 8px;")
                self.status_label.setText("❌ 保存注册码失败，请重试")
        else:
            self.status_label.setStyleSheet("color: #dc2626; font-weight: 500; padding-top: 8px;")
            self.status_label.setText(f"❌ {message}")


class LicenseChecker:
    """许可证检查器"""

    @staticmethod
    def check_and_prompt(parent=None) -> bool:
        """
        检查许可证，如果未激活则弹出激活对话框
        返回: 是否已激活（可以继续使用）
        """
        if license_manager.is_activated():
            return True

        dialog = ActivationDialog(parent)
        result = dialog.exec_()

        return result == QDialog.Accepted

    @staticmethod
    def show_activation_info(parent=None):
        """显示激活信息（用于菜单中的"关于"）"""
        if license_manager.is_activated():
            QMessageBox.information(
                parent, "激活状态",
                "✓ 软件已激活\n\n"
                f"机器码: {license_manager.generate_machine_code()[:32]}...\n"
                "感谢您的支持！"
            )
        else:
            QMessageBox.warning(
                parent, "激活状态",
                "❌ 软件未激活\n\n"
                "请联系管理员获取注册码。"
            )
