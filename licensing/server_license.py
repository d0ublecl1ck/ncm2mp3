#!/usr/bin/env python3
"""
服务端私钥脚本 - 用于生成注册码
注意：私钥必须放在仓库外，通过环境变量或命令行参数传入。
"""

import base64
import json
import os
from pathlib import Path

from Crypto.Hash import SHA256
from Crypto.PublicKey import RSA
from Crypto.Signature import pkcs1_15

from licensing import fingerprint_hash, fingerprint_payload


PRIVATE_KEY_ENV = "NCM2MP3_PRIVATE_KEY_PATH"


def resolve_private_key_path() -> Path:
    env_value = os.environ.get(PRIVATE_KEY_ENV, "").strip()
    if not env_value:
        raise RuntimeError(
            f"未设置私钥路径。请先设置环境变量 {PRIVATE_KEY_ENV} 指向仓库外的 private_key.pem"
        )
    private_key_path = Path(env_value).expanduser().resolve()
    if not private_key_path.is_file():
        raise RuntimeError(f"私钥文件不存在：{private_key_path}")
    return private_key_path


def load_private_key(private_key_path: Path) -> RSA.RsaKey:
    """加载私钥"""
    with open(private_key_path, "r", encoding="utf-8") as f:
        private_key = f.read()
    return RSA.import_key(private_key)


def generate_license_key(machine_code: str) -> str:
    """
    生成注册码
    流程：
    1. 解码机器码获取设备信息
    2. 计算设备指纹哈希
    3. 使用私钥签名哈希
    4. 返回签名作为注册码
    """
    try:
        # 解码机器码（Base64）
        machine_json = base64.b64decode(machine_code, validate=True).decode("utf-8")
        machine_info = json.loads(machine_json)
    except Exception as e:
        raise ValueError(f"机器码格式无效: {e}")

    normalized_machine_info = fingerprint_payload(machine_info)
    print(f"\n设备信息: {json.dumps(normalized_machine_info, indent=2, ensure_ascii=False)}")

    # 计算设备指纹哈希（与客户端使用相同算法）
    digest = fingerprint_hash(normalized_machine_info)

    print(f"\n指纹哈希: {digest.hex()[:32]}...")

    # 使用私钥签名
    private_key = load_private_key(resolve_private_key_path())
    signature = pkcs1_15.new(private_key).sign(SHA256.new(digest))

    # Base64 编码签名作为注册码
    license_key = base64.b64encode(signature).decode('utf-8')

    return license_key


def interactive_generate():
    """交互式生成注册码"""
    print("="*60)
    print("NCM2MP3 注册码生成器")
    print("="*60)
    print(f"\n私钥来源环境变量: {PRIVATE_KEY_ENV}")
    print("\n请粘贴用户提供的机器码（按 Ctrl+D 或输入 'END' 结束）：")

    lines = []
    while True:
        try:
            line = input()
            if line.strip().upper() == 'END':
                break
            lines.append(line)
        except EOFError:
            break

    machine_code = ''.join(lines).strip()

    if not machine_code:
        print("错误：机器码为空！")
        return

    print("\n" + "="*60)
    print("正在生成注册码...")

    try:
        license_key = generate_license_key(machine_code)

        print("\n" + "="*60)
        print("注册码生成成功！")
        print("="*60)
        print(f"\n{license_key}")
        print("\n" + "="*60)
        print("请将以上注册码复制给用户。")
        print("此注册码仅对该设备有效，一机一码。")
        print("="*60)
    except Exception as e:
        print(f"\n错误：生成失败 - {e}")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == '--check':
        # 验证模式
        print("验证注册码格式...")
    else:
        interactive_generate()
