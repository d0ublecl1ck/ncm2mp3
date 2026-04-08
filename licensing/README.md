# 软件授权系统使用说明

## 系统架构

本软件采用 **RSA 数字签名** + **机器码绑定** 的授权机制，实现一机一码。

```
机器码生成流程:
┌─────────────┐                              ┌─────────────┐
│   客户端     │  1. 收集设备信息              │   服务端     │
│             │  2. Base64 编码机器码 ──────> │             │
│             │                              │             │
│             │  3. 私钥签名设备哈希           │             │
│             │  4. Base64 编码注册码 <────── │             │
│             │                              │             │
│             │  5. 公钥验证签名              │             │
└─────────────┘                              └─────────────┘
```

**技术方案：**
- 使用 **RSA-PKCS1-v1.5** 签名方案
- 设备指纹包含：CPU ID、MAC 地址、磁盘序列号、平台标识
- 注册码有效期：永久（可扩展为限时）
- 防复制：注册码与设备指纹哈希绑定

## 文件说明

### 服务端文件（仅管理员使用）

| 文件 | 说明 |
|------|------|
| `licensing/server_license.py` | 服务端脚本，运行生成注册码 |

私钥文件不应放在仓库中，也不应随客户端分发。服务端脚本通过环境变量 `NCM2MP3_PRIVATE_KEY_PATH` 读取仓库外的私钥文件。

### 客户端文件（随软件分发）

| 文件 | 说明 |
|------|------|
| `licensing/public_key.pem` | 公钥参考文件，用于维护和轮换公钥 |
| `licensing/__init__.py` | 授权验证模块 |
| `licensing/activation_dialog.py` | 激活界面 |

## 使用流程

### 1. 生成密钥对（首次使用）

```bash
uv run python licensing/generate_keys.py
```

这将生成：
- `~/.ncm2mp3-admin/private_key.pem` - 默认生成在仓库外的私钥，请妥善保管
- `~/.ncm2mp3-admin/public_key.pem` - 默认生成在仓库外的公钥参考文件

建议流程：

1. 运行脚本生成密钥对
2. 保持私钥留在仓库外的安全目录
3. 将公钥内容同步到客户端常量 `EMBEDDED_PUBLIC_KEY_B64`
4. 如需在仓库中保留公钥参考文件，仅同步公钥，不要复制私钥

### 2. 打包客户端

打包前确保公钥已嵌入 `licensing/__init__.py`：

```bash
uv run pyinstaller ncm2mp3.spec
```

### 3. 用户激活流程

1. **用户首次启动软件**，弹出激活窗口
2. **用户复制机器码**，发送给管理员
3. **管理员生成注册码**：
   ```bash
   export NCM2MP3_PRIVATE_KEY_PATH=/secure/path/private_key.pem
   uv run python licensing/server_license.py
   ```
4. **用户输入注册码**，完成激活

### 4. 管理员生成注册码

```bash
export NCM2MP3_PRIVATE_KEY_PATH=/secure/path/private_key.pem
uv run python licensing/server_license.py
```

按提示粘贴用户提供的机器码，程序输出注册码。

## 安全说明

⚠️ **重要安全提示：**

1. **私钥保密**：私钥文件必须保存在仓库外，不能提交到 Git，不能随客户端分发
2. **一机一码**：注册码与设备硬件信息绑定，无法在其他机器使用
3. **防篡改**：客户端固定内置公钥，不接受环境变量覆盖发布版信任根
4. **完整性校验**：客户端会校验本地许可证文件和内置 FFmpeg 的完整性
5. **硬件变更**：如果用户更换关键硬件标识，需要重新激活

## 重置激活

如果需要重置某台机器的激活（测试或硬件变更）：

```python
from licensing import license_manager
license_manager.clear_license()
```

或删除用户目录下的许可证文件：
- macOS: `~/.ncm2mp3/license.json`
- Windows: `%USERPROFILE%\.ncm2mp3\license.json`
