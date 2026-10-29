# SD 固件与维护功能

[English](FIRMWARE_EN.md)

配置 LinuxCNC 不要求重新刷写 SD 或 Mesa 固件。向导的升级功能仅在操作者明确选择时运行；Debian 安装和软件自检不会刷写设备。

`firmware/mesa-v3/` 包含随项目提供的 SD01/SD02 测试固件、升级包、manifest 和 `SD-Mesa-Firmware-Source.zip`。源码 ZIP 包含 Rust 工程和 MIT 许可；其依赖保留原许可。详细源码构建要求以 ZIP 内的 Cargo.toml、rust-toolchain.toml 和工程说明为准。桌面工具打包不会重编译固件。

- `.fwup`：给维护流程使用的带包头/校验的应用升级包。
- `.bin`：原始 MCU 镜像，包括 boot 与 application，不可混用写入地址。
- `manifest.json`：提供包大小、摘要、型号和构建阶段信息。该阶段注明“软件/模型测试”，不能等同为每个设备的现场刷写验证。

维护前退出 LinuxCNC/HAL 的板卡占用，使用正确的型号和包，并确认恢复方法。Boot 与业务应用不是同一个通信阶段。工具不把主卡读取成功、包校验通过或维护握手成功当作完整的业务运行验证。

配置工具默认路径指向随包提供的 `.fwup`，但不自动安装它们；如使用其他版本，应由操作者选择与实际从板相符的文件。报告问题时注明主卡 FPGA 固件和从板业务/Boot 固件版本。
