# 开发与板卡扩展

[English](DEVELOPMENT_EN.md)

- `app.py`：自有 Qt 配置向导。
- `config_core.py`：校验与 INI/HAL 导出，GUI/CLI 共用。
- `board_profiles.py`：板卡规则注册表；新增板卡通过 `BoardProfile`/`register_profile()`，避免把专用引脚判断散落进界面。
- `hostmot2_config.py`：按发现资源生成串口与 DPLL 参数。
- `io_config.py`/`io_widgets.py`：功能列表、输入目标和分组下拉菜单。
- `spindle_config.py`：PWM 与 Step/Dir 主轴生成。
- `discovery.py`：mesaflash 文本/XML 解析；保留模块和针脚来源。
- `firmware_update.py`/`mesa_update.py`/`updater/`：SD 维护通道及升级包解析。
- `sserial_monitor*.py`：系统 Python 运行的只读 HAL 监控。
- `launcher.py`：独立发行版入口与离线自检。

新增板卡需确定底层 HostMot2 设备名、固定/保留/自定义引脚组、PWM 通道和固件基线。保留“产品板卡名”和“HostMot2 设备名”的区分；F7I92 使用 7i92 驱动标识。没有板卡数据的功能不得通过猜测生成。

新功能应以目标 LinuxCNC/PNCconf 源码为参照，比较实际信号连接和参数单位。`tests/reference/` 的适配器只供测试，直接执行系统安装的 PNCconf 函数，不把它作为软件运行依赖。核心软件测试不连接硬件。硬件验证需要另记固件版本、接线、操作和结果。

请勿提交 `.venv`、build/dist、中间 ELF、用户机床配置、密码或访问令牌。修改生成器后检查 GUI 往返保存和 CLI 输出是否一致。CLI 示例工程的轴脉冲数初始为 0，必须先设置再导出。
