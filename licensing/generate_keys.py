#!/usr/bin/env python3
"""
RSA 密钥对生成工具
运行此脚本生成新的密钥对
"""

import base64
from pathlib import Path

from Crypto.PublicKey import RSA


DEFAULT_OUTPUT_DIR = Path.home() / ".ncm2mp3-admin"


def generate_key_pair():
    """生成 2048 位 RSA 密钥对"""
    key = RSA.generate(2048)

    # 私钥（保存在服务端）
    private_key = key.export_key().decode('utf-8')

    # 公钥（嵌入客户端）
    public_key = key.publickey().export_key().decode('utf-8')

    return private_key, public_key


def save_keys(private_key: str, public_key: str, output_dir: str | Path = DEFAULT_OUTPUT_DIR):
    """保存密钥到文件"""
    output_dir = Path(output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    # 保存私钥（服务端使用）
    private_path = output_dir / "private_key.pem"
    with open(private_path, "w", encoding="utf-8") as f:
        f.write(private_key)
    private_path.chmod(0o600)
    print(f"私钥已保存到: {private_path}")

    # 保存公钥（供嵌入客户端）
    public_path = output_dir / "public_key.pem"
    with open(public_path, "w", encoding="utf-8") as f:
        f.write(public_key)
    print(f"公钥已保存到: {public_path}")

    # 生成 Python 常量格式（方便嵌入代码）
    public_key_b64 = base64.b64encode(public_key.encode()).decode()
    print(f"\n公钥 Base64（嵌入客户端代码）:\n{public_key_b64}")

    return private_path, public_path


if __name__ == "__main__":
    print("生成 RSA 密钥对...")
    private_key, public_key = generate_key_pair()

    save_keys(private_key, public_key)

    print("\n" + "="*60)
    print("密钥生成完成！")
    print(f"私钥默认保存在仓库外目录: {DEFAULT_OUTPUT_DIR}")
    print("请妥善保管 private_key.pem，不要泄露！")
    print("将 public_key.pem 的内容嵌入客户端代码中。")
    print("="*60)
