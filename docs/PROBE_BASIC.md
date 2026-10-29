# Probe Basic（PB）界面

[English](PROBE_BASIC_EN.md)

## 安装

FMesa 的“操作界面”下拉框可选择 **Probe Basic (QtPyVCP)**。Probe Basic/QtPyVCP 应另行安装在运行 LinuxCNC 的目标电脑；它们不会被捆绑到 FMesa 的 Python/Qt6 运行时中。

按 KCJ Engineering 的 Debian 12 安装步骤安装，选择适合自己的 Stable 或 Develop，不要混用两个渠道的程序和模板：

- [Debian 12 文档入口](https://kcjengr.github.io/probe_basic/debian_12_bookworm/index.html)
- [Stable 安装](https://kcjengr.github.io/probe_basic/debian_12_bookworm/installation/probe_basic_apt_stable_install.html)
- [官方机床配置要求](https://kcjengr.github.io/probe_basic/debian_12_bookworm/configuration/machine_config.html)

## 在 FMesa 配置

1. 在操作界面页选择 Probe Basic。
2. 模板目录留空时自动查找本机官方 `machine_setup_files`，优先使用 `/usr/share/configs/machine_setup_files`。也可以点击浏览，选择与目标电脑 Probe Basic 版本配套的官方模板副本。不要选择现有机床配置作为模板。
3. 正常配置板卡、轴、输入输出、主轴和手轮。
4. 检查预览并导出到新目录。导出需要完整模板；缺文件时会提示缺少的名称，不会只改 DISPLAY 就报告成功。
5. 在安装了 Probe Basic 的目标系统用 LinuxCNC 打开导出的 INI。

模板未安装时，FMesa 自身仍可使用其他界面、离线编辑和打包；只在选择 PB 并生成配置时才需要 PB 模板。

## 生成内容

当前是**铣床、手动换刀**配置，支持 XYZ、XYZA、XYZAB，以及模板实际提供的 XYZAC/XYZBC；界面常用轴布局仍为 XYZ/XYZA/XYZAB。DRO、几何显示与偏置列跟随机床轴布局。

生成器设置 PB 启动项、custom_config.yml、独立 probe_basic.var、子程序路径和 on_abort，复制模板的用户面板/DRO/子程序等资源。使用单一 `probe_basic_postgui.hal`，接入 PB 自带换刀对话框和周期计时，不加载 AXIS/Gmoccapy 的换刀引脚。运动模块提供至少官方要求的数字/模拟通道；主卡驱动和机械参数仍由原生成器负责。

工具使用 mm 单位，启动设为 G21；官方英制示例的 F10 和 G64 P.001 在这里分别换算为 F254 与 P.0254。测量/对刀参数从所选模板复制，不把模拟机床参数当作你的实际标定。正式使用测量循环前，需要在 PB 中按实际探针和对刀仪设置参数。

如果配置了真实探针输入，它会同时连接 PB 探针指示灯。没有配置时不会加入模拟探针输出；也不把主轴指令转速冒充编码器实测转速。

此功能不启用 ATC、不生成 M6 remap、不配置数据库刀表，使用普通 `tool.tbl`。Probe Basic 的安装、可选自动换刀和实际测量调试需要另外完成。

## 验证范围

已通过配置生成、网络连接、模板完整性和导出回滚测试；本机使用已安装的 Probe Basic 0.6.0-118.dev 配套模板完成资源导出。没有代用户启动 LinuxCNC/PB，也不把这些软件测试称为实机验收。不同 PB 版本必须选用与其相符的资源目录。
