# 源码运行与重新打包

[English](BUILD_EN.md)

## 支持环境

首个安装包在 Debian 12 amd64、Python 3.11 上构建。运行依赖固定为 PySide6 6.8.3 和 pyserial 3.x；构建器固定 PyInstaller 6.11.1 与 hooks-contrib 2024.10。不是跨平台编译：Windows、其他 CPU 或旧版 glibc 系统应在相应环境重新构建，不能把 Debian 12 amd64 二进制直接搬过去。

Python 源码可以直接运行，不需要编译 LinuxCNC、HM2 驱动或 C/C++ 项目。`build_release.py` 仅冻结本应用的 Python/Qt 运行时并封装 Debian 包。

## 安装构建依赖

```bash
sudo apt update
sudo apt install python3 python3-venv python3-pip git binutils patchelf dpkg-dev build-essential libglib2.0-0 libegl1 libgl1 libdbus-1-3 libxkbcommon-x11-0 libxcb-cursor0 libxcb-icccm4 libxcb-image0 libxcb-keysyms1 libxcb-render-util0 libxcb-xinerama0 fonts-noto-cjk
```

## 一键构建

在项目根目录执行：

```bash
bash scripts/build.sh
```

脚本创建独立 `.build-venv`，安装 `requirements-build.txt`，生成源码压缩包、包含 Python/Qt 的运行包、`.deb`、构建依赖版本记录和 SHA256 校验。首次构建需要联网下载 PyPI 依赖。全部输出位于 `dist/`，中间文件位于 `build/`；不会安装到系统，也不会执行 `sudo`。

自检会实例化 Qt 界面、生成示例 INI/HAL、用不可执行的合成数据检查升级包解析器；不连接串口、Mesa、HAL 或 LinuxCNC。构建失败会立即停止，不生成成功报告。

仅生成源码包，不下载依赖：

```bash
python3 scripts/build_release.py --source-only
```

已有构建环境：

```bash
.build-venv/bin/python scripts/build_release.py
```

## 本地验证

```bash
build/frozen/fmesa-config/fmesa-config --version
build/frozen/fmesa-config/fmesa-config --self-test
cd dist
sha256sum -c SHA256SUMS
```

Debian 包应在干净的 Debian 12 amd64 虚拟机再次验证：`sudo apt install ./包名.deb`、从菜单启动、导出配置、`sudo apt remove fmesa-config`。本机构建/解包自检和干净系统安装是不同层级的验证；发布说明须如实标明完成了哪一种。

## 测试

```bash
QT_QPA_PLATFORM=offscreen .build-venv/bin/python -m unittest discover -p 'test_*.py' -q
```

本机已安装 PNCconf 时，测试会提取并执行它的生成函数，比较加载参数、主轴连接和急停分支；不会启动其界面或操作硬件。没有 LinuxCNC 的构建机应跳过这些对照。一个可选的 Rust/Mesa 集成测试需要额外环境，可能跳过；基础发布不能把跳过当成硬件通过。

## GitHub 自动构建

仓库包含 GitHub Actions 工作流：push/PR 构建 Debian 12 包并保存 artifacts；推送 `v…` 标签时将同一批文件发布为测试 Release。首次向 main 推送新 VERSION 时也会自动创建对应测试 Release；已有版本不会被覆盖，需先提升 VERSION 才发布新文件。仓库创建并首次上传后可在 Actions 查看结果；不能仅凭提交了工作流就称 Release 已发布。

## 发布内容

`scripts/release_manifest.py` 使用明确的白名单，排除 `.venv`、个人 LinuxCNC 配置、开发日志、调试 ELF 和缓存。源码包只包含配置工具代码、构建说明、测试及许可证；不包含任何固件、固件 manifest 或固件源码。发布前仍应检查清单，确认没有私密文件或凭据。
