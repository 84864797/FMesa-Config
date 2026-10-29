"""界面本地化：HAL引脚、型号和用户输入保持原文。"""
import re

TEXT = {
 '已停机并退出LinuxCNC，允许进入Mesa维护模式':'Machine stopped; LinuxCNC closed. Allow Mesa maintenance takeover.',
 '正式链路：以太网 → Mesa → Smart Serial → SD板。需要配套Mesa版Boot V3；原USB Boot V2不支持转发。请在Debian电脑退出LinuxCNC后操作。':'Update route: Ethernet → Mesa → Smart Serial → SD board. Requires matching Mesa Boot V3; USB Boot V2 cannot forward updates. Run on Debian with LinuxCNC stopped.',
 '升级目标Mesa IP':'Update target Mesa IP',
 'Smart Serial通道 / 端口0':'Smart Serial channel / port 0',
 '机器已停止，已退出LinuxCNC；允许接管Mesa并将非串口GPIO置为输入':'Machine stopped and LinuxCNC closed; allow Mesa maintenance takeover and set non-serial GPIO to inputs',
 '读取Mesa链路信息':'Read Mesa link information',
 '通过Mesa开始升级':'Update through Mesa',
 '首次需用SWD安装匹配型号的新Boot。之后可经Mesa进入维护、上传、确认和启动；完成后重新启动LinuxCNC恢复硬件配置。':'First install the matching new bootloader via SWD. Later maintenance entry, transfer, confirmation and startup use Mesa. Restart LinuxCNC afterwards to restore hardware configuration.',
 '请先停止机器并退出LinuxCNC，再勾选维护接管确认':'Stop the machine, exit LinuxCNC, then confirm maintenance takeover',
 '正式Mesa升级请在Debian/LinuxCNC电脑运行；Windows可离线测试界面':'Run Mesa updates on the Debian/LinuxCNC PC; Windows supports offline UI testing',
 'LinuxCNC正在运行，请退出后升级':'LinuxCNC is running. Exit it before updating',
 'HAL仍加载Mesa驱动，请退出相关HAL会话后升级':'HAL still has a Mesa driver loaded. Exit the HAL session before updating',
 '升级包与目标SD型号不符，未连接Mesa':'The package does not match the target SD model. Mesa was not connected',
 '接管Mesa维护链路：非串口GPIO将置为输入；完成后重新启动LinuxCNC恢复配置。':'Taking over Mesa for maintenance. Non-serial GPIO will be inputs; restart LinuxCNC afterwards to restore configuration.',
 '请求SD应用关闭输出并进入维护Boot…':'Requesting the SD application to disable outputs and enter the maintenance bootloader…',
 '当前应用没有远程维护入口。请仅给SD板断电约2秒再上电，Mesa保持供电。':'The current application has no remote maintenance entry. Power-cycle only the SD board for about 2 seconds; keep Mesa powered.',
 '未找到Mesa升级Bootloader。旧Boot V2不支持转发，需要先通过SWD安装匹配的新Boot。':'Mesa upgrade bootloader not found. Boot V2 does not support forwarding; install the matching new bootloader via SWD first.',
 '实际目标板型/容量与镜像不符':'Actual target model/capacity does not match the image',
 '目标存在未完成试运行或安装，停止新升级':'A trial or installation is pending; new update stopped',
 '安装状态/版本不符':'Unexpected installation state/version',
 '试启动已准备，等待应用确认…':'Trial ready; waiting for application confirmation…',
 '新应用未确认，已启动回退版本。':'New application not confirmed; the rollback version was started.',
 '升级未确认：':'Update not confirmed: ',
 '已确认并启动。请重新启动LinuxCNC恢复板卡配置。':' confirmed and started. Restart LinuxCNC to restore board configuration.',
 'Mesa清理失败：':'Mesa cleanup failed: ',
 '工程名请用字母开头的英文、数字、下划线或短横线':'Use a project name starting with a letter, followed by letters, digits, underscores or hyphens',
 '此版本仅支持列出的以太网Mesa板卡':'This version supports the listed Ethernet Mesa models only',
 '未知从板型号':'Unknown remote model',
 '从板前缀必须属于本主卡和串口0，通道0～7':'Remote prefix must belong to this host, port 0, channel 0–7',
 '串口0模式需为8位0/x，仅启用已配置从板通道':'Port 0 modes must contain eight 0/x characters; enable the configured remote channel only',
 '伺服周期需在0.1～10ms之间':'Servo period must be between 0.1 and 10 ms',
 'Mesa看门狗至少需要两个伺服周期':'Mesa watchdog must cover at least two servo periods',
 '硬件资源数量超出支持范围':'Hardware resource count is out of range',
 '首版支持XYZ、XYZA、XYZAB、XZ独立轴；不含龙门双驱':'Supported layouts: independent XYZ, XYZA, XYZAB or XZ axes; no dual-drive gantries',
 'SD板需要16路输入和16路输出配置':'The SD board requires 16 input and 16 output assignments',
 '同一个输入功能不能重复分配':'An input function cannot be assigned twice',
 '存在非法输出功能':'An output function is invalid',
 '主轴PWM通道/满量程转速/频率无效':'Invalid spindle PWM channel, full-scale RPM or frequency',
 'Mesa地址需要有效IPv4':'A valid Mesa IPv4 address is required',
 '主卡HAL前缀必须与所选型号一致：':'Host HAL prefix must match the selected model: ',
 '从板前缀中的短名称与型号不符':'Remote prefix short name does not match the model',
 '从板通道未在串口模式中启用':'The remote channel is not enabled in the serial modes',
 '首版支持一块SD从板，只能启用其所在通道':'This version supports one SD remote; enable its channel only',
 ' StepGen越界或重复':' StepGen is out of range or duplicated',
 '参数不能为NaN/无穷大':' parameters cannot contain NaN or infinity',
 '比例不得为零，速度加速度需为正数':' scale must be nonzero; velocity and acceleration must be positive',
 '行程/回零位置无效':' has invalid travel limits or home position',
 '脉冲时序需为1～1000000ns':' step timings must be between 1 and 1000000 ns',
 '回零速度超过最大速度':' homing velocity exceeds maximum velocity',
 '开关回零需要回零输入和非零锁存速度':' switch homing requires a home input and nonzero latch velocity',
 '非法输入功能：':'Invalid input function: ',
 '超过发现的硬件资源':' exceeds the discovered hardware resources',
 '存在':' has ',
 '复用；XML未给出硬件通道，需核对文本readhmid':' alternate function; XML lacks its hardware channel. Check text readhmid output',
 'VGA保留GPIO':'Reserved VGA GPIO',
 '与已启用的':' conflicts with enabled ',
 '全局功能占用':' global function',
 '通道':' channel ', '冲突':' conflict', '被':' assigned to ',
 '发现记录过大':'Discovery file is too large',
 '没有找到模块数量；请导入mesaflash --readhmid原始文本或XML':'Module counts were not found. Import original mesaflash --readhmid text or XML',
 '不支持的Mesa型号':'Unsupported Mesa model',
 'HostMot2 XML不完整':'Incomplete HostMot2 XML',
 'Smart Serial扫描请在Debian/LinuxCNC停机后执行':'Run Smart Serial discovery on Debian with LinuxCNC stopped',
 '退出码':'Exit code ',
 'FMesa 配置工具':'FMesa Config',
 'FMesa 配置工具 · 整机配置与升级':'FMesa Config · Configuration and Firmware',
 '板卡发现 → 轴与主轴 → IO → 固定VGA手轮 → 检查与导出':'Discover → Axes & Spindle → I/O → Integrated MPG → Review & Export',
 '新建工程':'New project','打开工程':'Open project','保存工程':'Save project',
 '检查并预览':'Validate / preview','导出LinuxCNC配置':'Export LinuxCNC config',
 '01  硬件发现':'01  Hardware discovery','02  轴参数':'02  Axis setup',
 '03  主轴':'03  Spindle','04  输入输出':'04  Digital I/O','05  VGA手轮':'05  Integrated MPG',
 '06  检查与导出':'06  Review & export','07  SD固件升级':'07  Firmware update',
 '先填写主卡型号和IP，读取已安装固件的真实资源。也可导入PNCconf/mesaflash发现文本或XML。':'Enter the Mesa model and IP to read the installed firmware resources, or import a PNCconf/mesaflash discovery text or XML file.',
 '工程名称':'Project name','Mesa型号':'Mesa model','Mesa IP':'Mesa IP',
 '主卡HAL前缀':'Host HAL prefix','伺服周期 / ns':'Servo period / ns',
 'Mesa看门狗 / ns':'Mesa watchdog / ns','StepGen数量':'StepGen instances',
 'PWM数量':'PWM instances','Mesa编码器数量':'Mesa encoder instances',
 'SD从板型号':'SD remote model','实际从板HAL前缀':'Actual remote HAL prefix',
 '串口0通道模式':'Smart Serial port 0 modes',
 '同时扫描Smart Serial（需退出LinuxCNC，会操作通信端口）':'Scan Smart Serial too (exit LinuxCNC first; accesses the port)',
 '读取Mesa板卡':'Discover Mesa board','导入发现记录':'Import discovery',
 '读取运行中HAL引脚':'Read live HAL pins','尚未读取板卡；可离线编辑。':'No discovery loaded. Offline editing is available.',
 '硬件Step/Dir位置模式；XYZ/XYZA/XYZAB独立轴。线性单位mm，旋转轴degree。比例可为负值用于反向。':'Hardware Step/Dir position mode, independent XYZ/XYZA/XYZAB axes. Linear units: mm; rotary units: degrees. Use a negative scale to reverse direction.',
 '轴结构':'Axis layout','应用轴结构':'Apply axis layout','轴':'Axis','StepGen':'StepGen',
 '脉冲/单位':'Pulses / unit','最大速度/秒':'Max velocity / s','加速度/秒²':'Acceleration / s²',
 '负行程':'Min limit','正行程':'Max limit','HOME/偏置':'Home / offset',
 '搜索速度':'Home search velocity','锁存速度':'Home latch velocity','回零顺序':'Home sequence',
 '脉宽ns':'Step length ns','间隔ns':'Step space ns','方向建立ns':'Dir setup ns','方向保持ns':'Dir hold ns',
 '搜索速度为0时采用当前位置回零；使用回零开关时需在IO页分配对应输入，并填写搜索和锁存速度。':'A zero search velocity homes at the current position. Switch homing requires a home input and nonzero search/latch velocities.',
 'PWM满量程按实际驱动器填写。PWM与方向的物理针脚由Mesa固件决定；启停、正反转也可在IO页分配到SD输出。':'Match PWM full-scale RPM to the drive. Physical PWM/direction pins depend on the Mesa firmware. Run/forward/reverse signals can also use SD digital outputs.',
 '启用Mesa PWM主轴':'Enable Mesa PWM spindle','PWM通道':'PWM channel',
 '满量程转速 / rpm':'Full-scale speed / rpm','PWM频率 / Hz':'PWM frequency / Hz',
 'SD板PD0～PD15输入、PE0～PE15低有效输出。输入反相在HAL使用input-NN-not；输出FALSE对应物理关闭。':'SD inputs: PD0–PD15. Active-low outputs: PE0–PE15. Input inversion uses input-NN-not in HAL; FALSE turns an output off.',
 '输入针脚':'Input pin','输入功能':'Input function','输入反相':'Invert input',
 '输出针脚':'Output pin','输出功能':'Output function','未分配':'Unassigned',
 '外部急停链允许（TRUE允许）':'External E-stop permit (TRUE = permitted)',
 '探针':'Probe','冷却液':'Flood coolant','雾化':'Mist coolant','主轴运行':'Spindle run',
 '主轴正转':'Spindle forward','主轴反转':'Spindle reverse',
 '按已集成的VGA接口固定生成，不需要选择针脚。使用Mesa编码器00，和SD01的编码器字段分别处理。':'Uses the integrated VGA wiring directly. No pin selection is needed. Mesa encoder 00 is used, separately from the SD01 encoder field.',
 '专用保留：GPIO020、021、022、023、024、025、028、029及编码器00，不再分配他用。':'Reserved: GPIO020, 021, 022, 023, 024, 025, 028, 029 and encoder 00. No other assignments.',
 '固定：速度模式；X/Y/Z选轴025/023/021；倍率028/020；倍率0.025、0.0025、0.00025。':'Fixed velocity mode. X/Y/Z select: 025/023/021. Scale select: 028/020. Scales: 0.025, 0.0025, 0.00025.',
 '022/024/029保留但不自动生成A4/A5或急停逻辑，极性及用途需另行确认。':'022/024/029 remain reserved. No A4/A5 or E-stop logic is inferred; polarity and function need confirmation.',
 '生成完整AXIS整机配置及可重新打开的project.json。导出要求新目录，保留已有配置和手工修改。':'Generates a complete AXIS configuration and a reusable project.json. Export uses a new directory to preserve existing files.',
 '使用USB四线差分串口和现有Bootloader升级，不通过Mesa转发。仅接收专用.fwup包；原地址BIN不能直接上传。':'Uses a USB four-wire differential serial adapter and the existing bootloader, without Mesa forwarding. Only dedicated .fwup packages are accepted, not original-address BIN files.',
 '串口':'Serial port','目标型号':'Target model','升级包':'Firmware package',
 '刷新串口':'Refresh ports','选择并检查升级包':'Choose / inspect package',
 '开始升级并等待上电':'Update & wait for power-on',
 'SD01包已附带；SD02需另备匹配Bootloader及专用升级包。':'SD01 package included. SD02 requires a matching bootloader and dedicated upgrade package.',
 '离线编辑就绪；不自动连接、不启动LinuxCNC。':'Ready for offline editing. No automatic connection or LinuxCNC startup.',
 '操作未完成':'Operation failed','导出完成':'Export complete',
 '选择导出父目录（将创建工程名子目录）':'Choose parent directory (a project subfolder will be created)',
 '导入mesaflash发现记录':'Import mesaflash discovery file',
 '检查升级包':'Inspect firmware package','未知工程格式':'Unknown project format',
 '工程JSON (*.json)':'Project JSON (*.json)',
 '发现记录 (*.txt *.xml *.pin);;全部文件 (*)':'Discovery (*.txt *.xml *.pin);;All files (*)',
 'SD升级包 (*.fwup)':'SD firmware package (*.fwup)',
 '后台任务正在进行，请等待完成':'A background task is running. Please wait.',
 '后台任务尚未完成，请等待；升级期间保持供电。':'Wait for the background task to finish. Keep power connected during updates.',
 '正在读取板卡…':'Reading board information…',
 '发现完成；物理针脚以右侧原始信息为准。':'Discovery complete. Check the raw data for physical pin assignments.',
 '未找到唯一SD从板；旧名称7i69不能自动判定型号，请核对。':'No unique SD remote was found. The legacy name 7i69 does not identify our model.',
 '请先选择串口':'Select a serial port first',
 '手轮设置（固定VGA接口）':'MPG configuration (integrated VGA)',
 'sel0/sel1同时为1时使用in3，明确置零':'Both selectors high: in3 is explicitly zero',
 '未配置外部急停允许输入，生成配置保持禁止使能':'No external E-stop permit input is assigned; machine enable remains inhibited',
 '未导入实际板卡发现结果，资源数量及针脚分配尚未核对':'No board discovery loaded; resource counts and pin assignments are unverified',
 '本工具生成硬件Step/Dir位置模式配置；不含模拟伺服闭环或龙门双驱':'Generates hardware Step/Dir position mode only; no analog servo loops or dual-drive gantries',
 '固定VGA手轮模板需要XYZ轴':'The integrated VGA MPG requires X, Y and Z axes',
 '固定VGA手轮需要Mesa编码器00':'The integrated VGA MPG requires Mesa encoder 00',
 '请先退出再扫描Smart Serial':'Exit LinuxCNC before scanning Smart Serial',
 'LinuxCNC正在运行；':'LinuxCNC is running; ',
 '准备暂存区…':'Preparing staging area…','整镜像CRC校验…':'Verifying image CRC…',
 '备份旧应用并安装…':'Backing up and installing…','试启动已应答，等待应用确认…':'Trial start acknowledged; waiting for confirmation…',
 '等待维护握手：请给板卡断电约2秒，再上电。':'Waiting for maintenance handshake: power the board off for about 2 seconds, then on.',
 '维护握手超时；请核对串口、Bootloader和差分接线':'Maintenance handshake timed out. Check the port, bootloader and differential wiring.',
 '升级包与选择的板型不符，未打开串口':'The package does not match the selected model. Serial port was not opened.',
 '实际Bootloader板型与升级包不符，停止升级':'The bootloader board ID does not match the package. Update stopped.',
 '板卡存在待处理安装/试运行，请先检查状态':'An installation or trial is pending. Inspect the board state first.',
 '镜像超过目标容量':'Image exceeds the target capacity','安装后状态或版本错误':'Unexpected state or version after installation',
 '新固件未确认，可能已回退：':'New firmware not confirmed; it may have rolled back: ',
 '当前状态不允许':'Operation is not allowed in the current state',
 '未分配外部允许，保持禁止使能':'No external permit assigned; enable remains inhibited',
 'VGA专用GPIO，仅配置为输入，不提供其他用途分配':'Dedicated VGA GPIO inputs, unavailable for other assignments',
 '自动生成：机器单位mm/degree；主卡固件决定物理针脚':'Generated: machine units mm/degree; physical pins depend on the host firmware',
 'FMesa 配置工具生成；机械参数需按实际机器设置':'Generated by FMesa Config; set mechanical parameters for the actual machine',
 '用户扩展HAL':'User HAL extensions',
 '关节':'Joint ','回零':'Home','负限位':'Negative limit','正限位':'Positive limit',
 'M66数字输入':'M66 digital input ','M62/M64数字输出':'M62/M64 digital output ',
 '错误：':'Error: ','提示：':'Note: ','已导出：':'Exported: ','已识别：':'Detected: ',
 '；采用实际HAL大小写。':'; using the actual HAL spelling.',
 '上传 ':'Uploading ',
 '成功：版本':'Success: version ',
 '已确认并启动。串口已释放；Mesa业务需接回验证。':' confirmed and started. Serial port released; reconnect Mesa to verify operation.',
 'SD01 智能串口 MPG 板':'SD01 Smart Serial MPG board','SD02 智能串口 IO 板':'SD02 Smart Serial I/O board',
 '请选择新目录，避免覆盖手工修改的配置':'Choose a new directory to avoid overwriting edited configurations',
 '在Debian/LinuxCNC中打开':'Open in Debian/LinuxCNC: ',
 '；运行前核对发现记录及接线。':'; verify discovery data and wiring before running.',
}


TEXT.update({
 '欢迎':'Welcome','基本信息':'Basic information','操作界面':'User interface',
 '保存数据':'Save data','上一步':'Back','下一步':'Next','开始':'Start','完成并导出':'Finish and export',
 '取消':'Cancel','帮助':'Help','机床信息':'Machine information',
 '电机与驱动器':'Motor and driver','行程与回零':'Travel and homing',
 '硬件发现':'Hardware discovery','轴参数':'Axis configuration','输入输出':'Inputs and outputs',
 'StepGen控制方式':'StepGen control mode',
 'PNCconf：速度模式 + PID':'PNCconf: velocity mode + PID',
 '直接位置模式（兼容旧工程）':'Direct position mode (legacy)',
 'LinuxCNC 操作界面':'LinuxCNC user interface',
 '配置 SD 智能串口板…':'Configure SD Smart Serial board…',
 '按实际接线选择输入输出功能；配置随工程保存，关闭SD后保留分配。':'Assign IO for the actual wiring. Settings are saved with the project and retained when SD is disabled.',
 '启用 SD 智能串口板':'Enable SD Smart Serial board',
 'SD 智能串口板':'SD Smart Serial board','Mesa 主卡 IO':'Mesa host IO',
 '回零与限位':'Homing and limits','数字输入输出':'Digital IO','机器控制':'Machine controls',
 'GPIO 输入':'GPIO input','GPIO 输出':'GPIO output','GPIO 开漏输出':'GPIO open-drain output',
 '连接器 / 针脚':'Connector / pin','固件功能 / 状态':'Firmware function / status',
 '信号功能':'Signal function','反相':'Invert','可用 GPIO':'Available GPIO',
 '按当前硬件资源刷新针脚':'Refresh pins for current resources',
 '先读取Mesa板卡或导入readhmid记录，主卡针脚将按实际固件显示。':'Read the Mesa board or import readhmid to display actual host pins.',
 '按当前StepGen/PWM/编码器数量判断复用；更改资源后点击刷新。被占用针脚不可新分配。':'Pin availability follows the selected StepGen/PWM/encoder counts. Refresh after changing resources. Occupied pins cannot be assigned.',
 '启用固定 VGA 手轮（占用专用GPIO及编码器00）':'Enable fixed VGA MPG (reserves GPIO and encoder 00)',
 '所有关节共用回零及正负限位':'Shared home and limits for all joints',
 '所有关节共用正负限位':'Shared limits for all joints','所有关节共用回零':'Shared home for all joints',
 '回零与正负限位':'Home and both limits','回零与负限位':'Home and negative limit',
 '回零与正限位':'Home and positive limit','正负限位':'Both limits',
 '进给保持（M53启用时有效）':'Feed hold (requires M53)','进给禁止':'Feed inhibit',
 '循环启动':'Cycle start','程序停止':'Program stop','程序单步':'Single step',
 '程序暂停':'Program pause','程序继续':'Program resume',
 '手动主轴正转':'Manual spindle forward','手动主轴反转':'Manual spindle reverse',
 '手动主轴停止':'Manual spindle stop','主轴到速':'Spindle at speed',
 '主轴刹车':'Spindle brake','整机使能':'Machine enabled',
 '驱动器使能':'Amplifier enable','急停复位输出':'E-stop reset output',
})

def translate(text, language='zh'):
    if language != 'en': return text
    if text in TEXT:return TEXT[text]
    # Longest-first keeps complete hints intact; parameters and HAL identifiers remain literal.
    for source in sorted(TEXT,key=len,reverse=True):text=text.replace(source,TEXT[source])
    return text


def translate_widgets(root, language):
    from PySide6.QtWidgets import QLabel,QAbstractButton,QComboBox,QListWidget,QTableWidget,QPlainTextEdit,QTabWidget
    def apply(obj,getter,setter,key):
        current=getter();source=obj.property(key);last=obj.property(key+'_last')
        if source is None or current != last: source=current;obj.setProperty(key,source)
        value=translate(source,language);setter(value);obj.setProperty(key+'_last',value)
    for obj in root.findChildren(QLabel)+root.findChildren(QAbstractButton):
        apply(obj,obj.text,obj.setText,'source_text')
    for obj in root.findChildren(QPlainTextEdit):
        if obj.isReadOnly():apply(obj,obj.toPlainText,obj.setPlainText,'source_content')
    for obj in root.findChildren(QComboBox):
        for i in range(obj.count()):
            source=obj.itemData(i,33001)
            if source is None:source=obj.itemText(i);obj.setItemData(i,source,33001)
            obj.setItemText(i,translate(source,language))
    for obj in root.findChildren(QListWidget):
        for i in range(obj.count()):
            item=obj.item(i);source=item.data(33001)
            if source is None:source=item.text();item.setData(33001,source)
            item.setText(translate(source,language))
    for obj in root.findChildren(QTableWidget):
        for i in range(obj.columnCount()):
            item=obj.horizontalHeaderItem(i)
            if item:
                source=item.data(33001)
                if source is None:source=item.text();item.setData(33001,source)
                item.setText(translate(source,language))
    for obj in root.findChildren(QTabWidget):
        if obj.objectName() not in ('io_tabs','axis_settings'):continue
        sources=getattr(obj,'_source_tabs',{})
        for i in range(obj.count()):
            if i not in sources:sources[i]=obj.tabText(i)
            obj.setTabText(i,translate(sources[i],language))
        obj._source_tabs=sources
