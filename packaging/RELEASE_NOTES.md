## FMesa 配置工具 · 测试版

- 提供 Debian 12 amd64 安装包、免安装运行包、配置工具源码和 SHA256 校验清单。
- 包含 Probe Basic (QtPyVCP) 界面配置：使用目标电脑配套的官方模板，当前支持铣床手动换刀，不启用 ATC。
- PWM0 新工程默认反向、200Hz；没有外部急停输入时按 PNCconf 生成软件急停回路。
- **不包含任何固件 BIN、FWUP、固件源码 ZIP 或固件 manifest。**升级包由使用者另行提供。
- 修正早期测试版的 GitHub 资产文件名与校验清单不一致问题。

[中文安装与使用](https://github.com/84864797/FMesa-Config/blob/main/README.md) · [Probe Basic说明](https://github.com/84864797/FMesa-Config/blob/main/docs/PROBE_BASIC.md)

已通过软件测试和离线自检；没有代用户启动机床或完成 Probe Basic 实机验收。安装包适用 Debian 12 amd64，不代表所有系统或固件已通过硬件验证。

## FMesa Config · Test release

- Includes a Debian 12 amd64 installer, portable runtime, configuration-tool source and SHA256SUMS.
- Probe Basic (QtPyVCP) mill/manual-toolchange profile uses the target's matching official template. ATC is not enabled.
- New PWM0 projects default to inverted output at 200Hz. With no external E-stop input assigned, generation uses PNCconf's software E-stop loopback.
- **No firmware BIN, FWUP, firmware source ZIP or firmware manifest is distributed.** Upgrade packages must be supplied separately.
- Corrects the earlier preview's GitHub asset filename/checksum-list mismatch.

[English installation and usage](https://github.com/84864797/FMesa-Config/blob/main/README_EN.md) · [Probe Basic guide](https://github.com/84864797/FMesa-Config/blob/main/docs/PROBE_BASIC_EN.md)

Software tests and offline self-tests passed. No machine was started and no Probe Basic hardware acceptance was performed. This installer targets Debian 12 amd64; other systems and firmware combinations require their own verification.
