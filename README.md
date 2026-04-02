# ncm2mp3

一个基于 `PyQt5` 的桌面小工具，用来把选定文件夹里的所有 `.ncm` 文件批量转换成 `.mp3`。

## 功能

- 选择文件夹后在界面中显示当前路径
- 批量扫描该目录下全部 `.ncm` 文件
- 在子线程中执行转换，避免界面卡死
- 使用进度条实时反馈转换进度
- 对非 MP3 源流自动调用 `ffmpeg` 转码为 MP3

## 运行

```bash
uv sync
uv run python main.py
```

## 打包

```bash
uv run pyinstaller --noconfirm --windowed --name ncm2mp3 main.py
```

打包完成后：

- macOS：生成 `dist/ncm2mp3.app`
- 同时会生成 `ncm2mp3.spec`，可用于后续重复构建

如果你以后需要 Windows 的 `.exe`，需要在 Windows 环境里执行 PyInstaller 打包。

## 依赖

- `PyQt5`
- `pycryptodome`
- `ffmpeg`

macOS 安装 `ffmpeg` 示例：

```bash
brew install ffmpeg
```
