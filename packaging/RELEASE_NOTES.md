## FMesa 配置工具 0.3.0-test.2

- 补齐公制启动代码、点动步距、车床标志、TRAJ速度、HAL扩展入口和Gmoccapy指示连接。
- 新增反向间隙/补偿表、编码器索引回零、Step/Dir双驱、PWM模拟伺服轴与PID。
- 新增主轴实测编码器、速度PID、到速判断和Step/Dir转速单位转换。
- 新增回零、位置恢复、换刀、MDI、编辑器与过滤器选项；保留原默认行为。
- 中英文使用说明已更新。提供Debian12 amd64安装包、免安装包、源码、SHA256SUMS。
- 不包含固件。Probe Basic保留手动换刀；不生成ATC和主轴定向。

已完成软件组合测试及离线自检，未启动LinuxCNC或进行机床运动、伺服整定与实机验收。高级功能需按硬件接线和机械参数调试。

## FMesa Config 0.3.0-test.2

- Completes metric startup code, jog increments, lathe flag, trajectory speeds, custom HAL hooks and Gmoccapy indicators.
- Adds backlash/compensation tables, encoder-index homing, Step/Dir tandem joints and PWM servo axes with PID.
- Adds measured spindle encoder feedback, speed PID, at-speed checks and RPM-to-rev/s conversion for Step/Dir.
- Adds homing, position restore, tool-change, MDI, editor and filter settings while retaining existing defaults.
- Updated Chinese/English instructions. Includes Debian12 amd64 installer, portable runtime, source and SHA256SUMS.
- No firmware included. Probe Basic uses manual toolchange; ATC and spindle orientation are not generated.

Software combination tests and offline self-tests were performed. LinuxCNC/machine motion, servo tuning and hardware acceptance were not run. Commission advanced settings for the actual wiring and mechanics.

[中文说明](https://github.com/84864797/FMesa-Config/blob/main/README.md) · [English](https://github.com/84864797/FMesa-Config/blob/main/README_EN.md)
