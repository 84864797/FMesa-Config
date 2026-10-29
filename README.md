# FMesa Config · FMesa 配置工具

面向 **Debian 12 / LinuxCNC** 的独立配置向导。为 F7I92、Mesa 以太网主卡及 SD01/SD02 智能串口板生成 LinuxCNC INI/HAL；界面与生成规则参考 PNCconf，板卡选择和 SD 配置由本项目提供。

[English](README_EN.md) · [详细使用](docs/USER_GUIDE.md) · [源码运行与打包](docs/BUILD.md) · [添加板卡](docs/DEVELOPMENT.md) · [固件说明](docs/FIRMWARE.md) · [Probe Basic](docs/PROBE_BASIC.md)

**本仓库和安装包只发布配置工具，不包含固件 BIN、FWUP、固件源码 ZIP 或 manifest。升级包需另行提供。**

**当前版本属于测试发布。** 已做本机 Debian 12 的软件测试与安装包自检；不代表所有固件、接线或机床均完成硬件验证。它不会安装或替换 LinuxCNC 的 HM2 驱动。

## 下载安装（普通使用者）

到 [GitHub Releases](https://github.com/84864797/FMesa-Config/releases) 选择最新测试版。先用 `dpkg --print-architecture` 确认架构；本次提供 Debian 12 **amd64** 包。

| 下载文件 | 用途 |
|---|---|
| `fmesa-config_…_amd64.deb` | 推荐：安装后从应用菜单启动 |
| `fmesa-config-…-linux-amd64.tar.xz` | 免安装运行包，包含 Python/Qt |
| `FMesa-Config-…-source.tar.gz` | 完整源码，供修改、运行和重新打包 |
| `SHA256SUMS` | 文件完整性校验 |

下载 `.deb` 后，在其所在目录执行（文件名以实际下载为准）：

```bash
sudo apt update
sudo apt install ./fmesa-config_0.2.0~test.1_amd64.deb
fmesa-config
```

也可从应用菜单打开 **FMesa 配置工具**。安装包带 Python/Qt 运行时，无需 `pip install`。apt 可能联网安装系统图形库和中文字体。

卸载程序不会删除你自行导出的配置：

```bash
sudo apt remove fmesa-config
```

免安装包：解压后进入 `fmesa-config` 文件夹，运行 `./fmesa-config`。需 Debian 12 的图形桌面及系统库；缺库时优先使用 `.deb` 让 apt 安装依赖。不要用 sudo 启动图形界面。

如需读取板卡，在目标 LinuxCNC 电脑安装 `mesaflash`。通信监控另需 LinuxCNC 的系统 Python `hal` 模块及 `python3-tk`。离线编辑不要求连接板卡或运行 LinuxCNC。

## 从源码运行（开发者）

```bash
sudo apt update
sudo apt install git python3 python3-venv python3-pip libegl1 libgl1 libglib2.0-0 libxkbcommon-x11-0 libxcb-cursor0 libxcb-icccm4 libxcb-image0 libxcb-keysyms1 libxcb-render-util0 libxcb-xinerama0 fonts-noto-cjk
git clone https://github.com/84864797/FMesa-Config.git
cd FMesa-Config
bash install.sh
bash run.sh
```

`install.sh` 在当前目录创建 `.venv` 并安装依赖和当前用户菜单入口，不向系统 Python 安装包。无需编译 C/C++ 或 HM2 驱动。详细构建命令见 [BUILD.md](docs/BUILD.md)。

## 第一次使用

1. 新建工程，设置名称、机床轴布局，选择 AXIS、Gmoccapy、QtDragon、QtDragon HD 或 Probe Basic。Probe Basic 需要另装前端和选择其官方配套模板，见专门说明。
2. 硬件页选择 **F7I92** 或自定义板卡，填写 IP；读取与实际安装固件一致的板卡信息。
3. 轴页填写脉冲当量、速度、加速度、行程与回零参数。新轴脉冲当量默认为 0，必须填写后才能导出。界面速度单位为每分钟，INI 使用每秒。
4. 输入输出页分配主卡 GPIO；启用 SD 后，在本页的 SD 页签配置，不弹出独立窗口。没有启用的 SD 板不会生成从板 IO 连接。
5. 主轴页选择模拟量电主轴或 Step/Dir 伺服主轴。当前新工程 PWM0 **默认反向、200Hz**；应按具体板卡电路和固件核对。F7I92 固定 PWM0，IO0 是模拟主轴正转输出。
6. 手轮 MPG 页选择 3/4/5 轴和 IO29 功能。使用 4/5 轴手轮前先配置相应机床轴。
7. 检查 INI/HAL 预览，导出到一个**新的配置目录**，再用 LinuxCNC 选择其中的 `.ini`。工具拒绝覆盖已有目录，避免覆盖手工修改。

**急停遵循 PNCconf 的普通分支：**分配了外部急停输入就使用该输入（TRUE 表示允许）；没有分配有效外部输入就生成软件急停回路。没有额外的“急停方式”选择。

将导出配置用于实际机床前，按实际急停接线、输入极性和驱动使能核对。向导不自动启动 LinuxCNC、不自动刷写固件，也不会改变正在运行的 HAL 值。

## 功能范围

- F7I92 固定引脚规则、IO30～33 自定义引脚发现、可扩展板卡注册接口。
- 主卡 GPIO、SD 数字 IO 的功能下拉选择、反向与回零/限位连接。
- Step/Dir 机床轴；普通 PWM 主轴；Step/Dir 伺服主轴。
- 固件包含 DPLL 时生成对应采样提前设置；按发现到的资源生成 Smart Serial 加载选项。
- INI/HAL 预览、工程 JSON 保存与重新打开、命令行生成。
- 可选的 SD 固件维护与只读通信监控；详见单独说明。

QtDragon 模板目前只支持 XYZ/XYZA。伺服主轴的 StepGen 反馈是脉冲输出估计，本工具没有实现外部主轴编码器闭环、刚性攻丝或定向。软件不重新分配 FPGA 固件的物理功能；自定义引脚改变功能需要对应固件。

## 命令行与测试

```bash
.venv/bin/python cli.py sample /tmp/project.json
# 按实际机械修改 project.json（尤其是初始为 0 的脉冲当量）
.venv/bin/python cli.py validate /tmp/project.json
.venv/bin/python cli.py export /tmp/project.json /tmp/my-new-machine
QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest discover -p 'test_*.py' -q
```

安装包也支持 `fmesa-config --cli …`、`--version`、`--self-test`。自检只检查界面、生成器和升级包解析，不连接硬件。PNCconf 源码对照测试在装有 LinuxCNC/PNCconf 的系统上执行，否则跳过。

## 问题反馈

在仓库 [Issues](https://github.com/84864797/FMesa-Config/issues) 提供软件版本、Debian/LinuxCNC 版本、板卡及固件信息、完整错误和可复现步骤。请勿上传密码、访问令牌或机床的私密参数。源代码与构建脚本见本仓库；下载文件的具体测试情况见对应 Release 说明。

## 许可证

桌面工具 GPL-2.0-or-later；本仓库和安装包不包含固件或固件源码。见 [LICENSE](LICENSE) 与 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。LinuxCNC/PNCconf 原版权和许可声明保留。
