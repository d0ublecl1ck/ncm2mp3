"""
客户端授权验证模块
包含：设备指纹生成、注册码验证、激活状态管理
使用 RSA 签名方案
"""

import base64
import hashlib
import json
import os
import subprocess
import sys
import uuid
from binascii import Error as BinasciiError
from pathlib import Path
from datetime import datetime

from Crypto.Hash import SHA256
from Crypto.PublicKey import RSA
from Crypto.Signature import pkcs1_15


# 嵌入的公钥（Base64 编码）
EMBEDDED_PUBLIC_KEY_B64 = """
LS0tLS1CRUdJTiBQVUJMSUMgS0VZLS0tLS0KTUlJQklqQU5CZ2txaGtpRzl3MEJBUUVGQUFPQ0FROEFNSUlCQ2dLQ0FRRUFveHU2M1N6MzJFck95YlVzSFJERwpGcHNWY1llTStyRlJhQ1lxL3ZnOGFNNk5ZT0V5cEVzUjJEUFdsTmM5dDg2bU4rMEx3bVJ1NkxyQXFsL2lwVWptCnN2VlRINDF0MVY3NnVvV2hKeEc1WW5ram4xcmxrMVcxMFNUWU5mdnhxRWRROS9MU3NuWVJaWEhtbjBlUHFYRFIKNmpYdnlHSXFaY2V5Sk8vTmd1VmVINStWVCtnekxZOFVFMDREbkdDSXlOeW8ycGFSRmt3UjBOeG5vOUNlb0w2dQoyS2t0cWxodTdkZVQxMW1xVy9lNzhlRGppTFdLVUppVFZrckwyN1AxcFdQYlBWSjJpKzVvdmkxMUgxcTlQaVhMCkFrNU1xQzBVV1M1cm1ZdG9JZlAwZDZ0bUloRGtkb1JBdisxdDJvZmt4dTNEUnllZE9PYlBETGJMWC9pNklIeGMKUVFJREFRQUIKLS0tLS1FTkQgUFVCTElDIEtFWS0tLS0t
""".strip()

# 许可证文件路径
LICENSE_FILE = Path.home() / ".ncm2mp3" / "license.json"
LICENSE_SCHEMA_VERSION = 1
MIN_REQUIRED_FINGERPRINT_FIELDS = ("cpu_id", "mac_address")
OPTIONAL_FINGERPRINT_FIELDS = ("disk_serial",)


def _get_mac_address() -> str:
    mac_value = uuid.getnode()
    if (mac_value >> 40) & 0x01:
        return ""
    mac_hex = f"{mac_value:012x}"
    return ":".join(mac_hex[index : index + 2] for index in range(0, 12, 2))


def _collect_platform_fingerprint() -> dict[str, str]:
    fingerprint = {
        "cpu_id": "",
        "mac_address": _get_mac_address(),
        "disk_serial": "",
        "platform": sys.platform,
    }

    if sys.platform == "darwin":
        result = subprocess.run(
            ["system_profiler", "SPHardwareDataType", "-json"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            data = json.loads(result.stdout)
            hardware = data.get("SPHardwareDataType", [{}])[0]
            fingerprint["cpu_id"] = hardware.get("platform_UUID", "").strip()
            fingerprint["disk_serial"] = hardware.get("serial_number", "").strip()
    elif sys.platform == "win32":
        bios_result = subprocess.run(
            ["wmic", "bios", "get", "serialnumber", "/value"],
            capture_output=True,
            text=True,
            check=False,
        )
        if bios_result.returncode == 0:
            for line in bios_result.stdout.strip().splitlines():
                if "SerialNumber=" in line:
                    fingerprint["cpu_id"] = line.split("=", 1)[1].strip()
                    break

        disk_result = subprocess.run(
            ["wmic", "diskdrive", "get", "serialnumber", "/value"],
            capture_output=True,
            text=True,
            check=False,
        )
        if disk_result.returncode == 0:
            for line in disk_result.stdout.strip().splitlines():
                if "SerialNumber=" in line:
                    fingerprint["disk_serial"] = line.split("=", 1)[1].strip()
                    break

    return fingerprint


def normalize_fingerprint(fingerprint: dict[str, object]) -> dict[str, str]:
    normalized = {
        "cpu_id": str(fingerprint.get("cpu_id", "")).strip(),
        "mac_address": str(fingerprint.get("mac_address", "")).strip().lower(),
        "disk_serial": str(fingerprint.get("disk_serial", "")).strip(),
        "platform": str(fingerprint.get("platform", sys.platform)).strip(),
    }
    return normalized


def validate_fingerprint(fingerprint: dict[str, str]) -> tuple[bool, str]:
    missing_required = [field for field in MIN_REQUIRED_FINGERPRINT_FIELDS if not fingerprint.get(field)]
    if missing_required:
        missing_text = "、".join(missing_required)
        return False, f"设备指纹不完整，缺少关键标识：{missing_text}"

    available_count = sum(
        1 for field in (*MIN_REQUIRED_FINGERPRINT_FIELDS, *OPTIONAL_FINGERPRINT_FIELDS) if fingerprint.get(field)
    )
    if available_count < 2:
        return False, "设备指纹强度不足，无法生成安全许可证"

    return True, ""


def fingerprint_payload(fingerprint: dict[str, str]) -> dict[str, str]:
    normalized = normalize_fingerprint(fingerprint)
    valid, message = validate_fingerprint(normalized)
    if not valid:
        raise ValueError(message)
    return normalized


def fingerprint_hash(fingerprint: dict[str, object]) -> bytes:
    payload = fingerprint_payload(normalize_fingerprint(fingerprint))
    payload_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload_json.encode("utf-8")).digest()


class LicenseManager:
    """许可证管理器"""

    def __init__(self):
        self.public_key = self._load_public_key()
        self._ensure_license_dir()

    def _ensure_license_dir(self):
        """确保许可证目录存在"""
        LICENSE_FILE.parent.mkdir(parents=True, exist_ok=True)

    def _load_public_key(self) -> RSA.RsaKey:
        """加载嵌入的公钥"""
        public_key_pem = base64.b64decode(EMBEDDED_PUBLIC_KEY_B64).decode("utf-8")
        return RSA.import_key(public_key_pem)

    @staticmethod
    def get_machine_fingerprint() -> dict:
        """
        获取机器指纹信息
        收集多个硬件标识符来确保唯一性
        """
        try:
            return normalize_fingerprint(_collect_platform_fingerprint())
        except Exception as exc:
            raise RuntimeError(f"获取设备指纹失败: {exc}") from exc

    def get_machine_code(self) -> str:
        """
        获取机器码（设备指纹的 JSON 字符串）
        用于显示给用户，服务端计算哈希后签名
        """
        fingerprint = fingerprint_payload(self.get_machine_fingerprint())
        return json.dumps(fingerprint, sort_keys=True)

    def generate_machine_code(self) -> str:
        """
        生成机器码（Base64 编码的设备指纹）
        用户将此码发送给服务端
        """
        fingerprint = fingerprint_payload(self.get_machine_fingerprint())
        fingerprint_json = json.dumps(fingerprint, sort_keys=True, separators=(",", ":"))
        return base64.b64encode(fingerprint_json.encode("utf-8")).decode("utf-8")

    def verify_license(self, license_key: str) -> tuple[bool, str]:
        """
        验证注册码
        注册码是服务端使用私钥对设备指纹哈希的签名
        返回: (是否有效, 错误信息)
        """
        try:
            # 解码注册码（Base64）
            signature = base64.b64decode(license_key, validate=True)

            # 计算当前设备指纹哈希
            current_fingerprint_hash = fingerprint_hash(self.get_machine_fingerprint())

            # 使用公钥验证签名
            try:
                pkcs1_15.new(self.public_key).verify(SHA256.new(current_fingerprint_hash), signature)
                return True, "验证成功"
            except (ValueError, TypeError):
                return False, "注册码无效或与本机不匹配"
        except (ValueError, RuntimeError) as exc:
            return False, str(exc)
        except (BinasciiError, TypeError):
            return False, "注册码格式无效"
        except Exception as e:
            return False, f"验证失败: {e}"

    def save_license(self, license_key: str) -> bool:
        """保存注册码到本地"""
        try:
            is_valid, message = self.verify_license(license_key)
            if not is_valid:
                raise ValueError(message)

            license_data = {
                "schema_version": LICENSE_SCHEMA_VERSION,
                "license_key": license_key,
                "activated_at": datetime.now().isoformat(),
                "machine_code": self.generate_machine_code(),
            }
            temp_path = LICENSE_FILE.with_suffix(".tmp")
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(license_data, f, indent=2)
            os.chmod(temp_path, 0o600)
            os.replace(temp_path, LICENSE_FILE)
            return True
        except Exception as e:
            print(f"保存许可证失败: {e}")
            return False

    def load_saved_license(self) -> str | None:
        """加载已保存的注册码"""
        if not LICENSE_FILE.exists():
            return None

        try:
            with open(LICENSE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if data.get("schema_version") != LICENSE_SCHEMA_VERSION:
                return None
            machine_code = data.get("machine_code")
            if machine_code != self.generate_machine_code():
                return None
            return data.get("license_key")
        except Exception as e:
            print(f"加载许可证失败: {e}")
            return None

    def is_activated(self) -> bool:
        """检查是否已激活"""
        license_key = self.load_saved_license()
        if not license_key:
            return False

        is_valid, _ = self.verify_license(license_key)
        return is_valid

    def clear_license(self):
        """清除许可证（用于测试或重置）"""
        if LICENSE_FILE.exists():
            LICENSE_FILE.unlink()


# 全局许可证管理器实例
license_manager = LicenseManager()
