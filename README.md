# ncm2mp3

一个基于 `PyQt5` 的桌面小工具，用来把选定文件夹里的所有 `.ncm` 和 `.flac` 文件批量转换成 `.mp3`。

## 功能

- 选择文件夹后在界面中显示当前路径
- 批量扫描该目录下全部 `.ncm` 和 `.flac` 文件
- 在子线程中执行转换，避免界面卡死
- 使用进度条实时反馈转换进度
- 对非 MP3 源流自动调用 `ffmpeg` 转码为 MP3
- **新增**: 支持直接将 `.flac` 文件转换为 `.mp3`

## 运行

```bash
uv sync
uv run python ncm2mp3.py
```

## 内置 FFmpeg

本项目已支持将 `ffmpeg` 打包到应用内，用户无需手动安装。
程序会先校验内置二进制的 SHA-256，再决定是否执行，避免打包产物中的 `ffmpeg` 或依赖 DLL 被静默替换。

### 准备 ffmpeg 二进制文件

打包前需要将对应平台的 ffmpeg 放入 `binaries` 目录：

```
binaries/
├── macos/
│   └── ffmpeg          # macOS 版本（需要可执行权限）
└── windows/
    └── ffmpeg.exe      # Windows 版本
```

### 下载地址

- **macOS**: https://evermeet.cx/ffmpeg/ （下载静态编译版）或 `brew install ffmpeg` 后复制 `/opt/homebrew/bin/ffmpeg`
- **Windows**: https://github.com/BtbN/FFmpeg-Builds/releases （下载 `ffmpeg-master-latest-win64-gpl.zip`，解压取 `ffmpeg.exe`）

更新内置二进制后，需要同步更新 [ncm2mp3.py](/Users/d0ublecl1ck/ncm2mp3/ncm2mp3.py) 里的 `BUNDLED_FFMPEG_HASHES`，否则程序会拒绝执行被替换的文件。

### macOS 准备 ffmpeg 示例

```bash
mkdir -p binaries/macos
# 如果使用 Homebrew 安装的 ffmpeg
cp $(which ffmpeg) binaries/macos/ffmpeg
# 添加可执行权限
chmod +x binaries/macos/ffmpeg
```

## 打包

使用 spec 文件打包（已配置自动包含 ffmpeg）：

```bash
# macOS
uv run pyinstaller ncm2mp3.spec

# Windows
pyinstaller ncm2mp3.spec
```

打包完成后：

- macOS：生成 `dist/ncm2mp3.app`
- Windows：生成 `dist/ncm2mp3.exe`

如果你以后需要 Windows 的 `.exe`，需要在 Windows 环境里执行 PyInstaller 打包。

## 依赖

- `PyQt5`
- `pycryptodome`
- `ffmpeg`（已内置）

## 软件授权（一机一码）

本软件采用 **RSA 数字签名** + **机器码绑定** 的授权机制：

1. **首次启动**：显示激活窗口，生成机器码
2. **用户操作**：复制机器码发送给管理员
3. **管理员操作**：在仓库外保存私钥，并通过环境变量指定私钥路径后生成注册码
4. **激活**：用户输入注册码完成激活

默认的密钥生成脚本会把新密钥写到 `~/.ncm2mp3-admin/`，避免把私钥落进仓库。

### 生成注册码（管理员）

```bash
export NCM2MP3_PRIVATE_KEY_PATH=/secure/path/private_key.pem
uv run python licensing/server_license.py
```

详细说明参见 [`licensing/README.md`](licensing/README.md)
