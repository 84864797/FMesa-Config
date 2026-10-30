"""LinuxCNC 2.9 整机配置模型与生成器；不访问硬件。"""
import ipaddress
import json
import math
import re
from pathlib import Path
from io_config import input_targets, input_assignments, gpio_reason
from board_profiles import profile_for,effective_gpio,default_discovery,PROFILES,fixed_rule_errors
import spindle_config
import advanced_config
import probe_basic_config
from display_config import repair_ini
from hostmot2_config import serial_option,dpll_settings

# 固定VGA手轮：IO22/24为A/B轴选，IO29是独立可配置固定输入。
MPG_RESERVED = {20:'倍率sel1',21:'Z选轴',22:'轴选3 / A',23:'Y选轴',
                24:'轴选4 / B',25:'X选轴',28:'倍率sel0'}
MPG_GPIO_INPUTS = {20,21,22,23,24,25,28,29}
DISPLAYS = {'axis':'AXIS', 'gmoccapy':'Gmoccapy', 'qtdragon':'QtDragon', 'qtdragon_hd':'QtDragon HD', 'probe_basic':'Probe Basic (QtPyVCP)'}


def axis_defaults(letter, index):
    """PNCconf 2.9 metric defaults; pulse scale must be supplied for the machine."""
    rotary=letter not in 'XYZ'
    return dict(axis=letter,stepgen=index,scale=0.,advanced=dict(advanced_config.JOINT_DEFAULTS),
                velocity=360. if rotary else 25.,acceleration=1200. if rotary else 750.,
                minimum=-9999. if rotary else -100. if letter=='Z' else 0.,
                maximum=9999. if rotary else 0. if letter=='Z' else 200.,
                home=0.,home_offset=0.,home_final_velocity=0.,search=0.,latch=0.,
                home_sequence={'X':2,'Y':3,'Z':1,'A':4,'B':5}.get(letter,index+1),
                ferror=.5 if rotary else 10.,min_ferror=.05 if rotary else 1.,
                steplen=5000,stepspace=5000,dirsetup=10000,dirhold=10000)


def defaults():
    c = {
        'machine_options':dict(advanced_config.MACHINE_DEFAULTS), 'schema': 1, 'language': 'zh', 'display':'axis', 'probe_basic_template':'', 'name': 'SD_Mill', 'board': '7i92', 'board_profile':'F7I92', 'ip': '10.10.10.10',
        'host': 'hm2_7i92.0', 'servo_ns': 1000000, 'watchdog_ns': 5000000, 'stepgen_control':'velocity_pid',
        'stepgens': 5, 'pwmgens': 1, 'encoders': 1, 'pdm_frequency':6000000, 'dpll_timer_us':-50,
        'remote_model': 'SD01', 'remote_prefix': 'hm2_7i92.0.sd01.0.0', 'remote_enabled': False,
        'sserial': '0xxxxxxx', 'axes': [axis_defaults(a,i) for i,a in enumerate('XYZ')],
        'spindle': spindle_config.defaults(),
        'inputs': [{'role': '', 'invert': False} for _ in range(16)],
        'outputs': ['' for _ in range(16)],
        'mesa_gpio': [],
        'mpg': {'enabled': True,'axes':3,'input29':{'role':'','invert':False}},
        'discovery': default_discovery('F7I92'),
    }
    c['mesa_gpio']=sorted(effective_gpio(c),key=lambda v:(profile_for(c).fixed_gpio[v['io']].get('page')=='spindle',v['io']))
    return c


def input_roles(count=5):
    return {'': '未分配', 'estop-ok': '外部急停链允许（TRUE允许）', 'probe': '探针',
            'feed-hold':'进给保持（M53启用时有效）', 'feed-inhibit':'进给禁止',
            'spindle-at-speed':'主轴到速', 'cycle-start':'循环启动', 'abort':'程序停止',
            'single-step':'程序单步', 'program-pause':'程序暂停', 'program-resume':'程序继续',
            'spindle-manual-cw':'手动主轴正转', 'spindle-manual-ccw':'手动主轴反转', 'spindle-manual-stop':'手动主轴停止',
            'all-home':'所有关节共用回零', 'all-limit':'所有关节共用正负限位',
            'all-home-limit':'所有关节共用回零及正负限位',
            **{f'{kind}:{i}': f'关节{i} {label}' for i in range(count)
               for kind, label in [('home', '回零'), ('neg', '负限位'), ('pos', '正限位'),
                                   ('both','正负限位'),('home-neg','回零与负限位'),
                                   ('home-pos','回零与正限位'),('home-both','回零与正负限位')]},
            **{f'din:{i}': f'M66数字输入{i}' for i in range(16)}}


OUTPUT_ROLES = {'': '未分配', 'flood': '冷却液', 'mist': '雾化', 'spindle-on': '主轴运行',
                'spindle-brake':'主轴刹车', 'machine-enabled':'整机使能', 'estop-out':'急停复位输出',
                'spindle-forward': '主轴正转', 'spindle-reverse': '主轴反转',
                **{f'dout:{i}': f'M62/M64数字输出{i}' for i in range(16)}}


def output_roles(count=5):
    return {**OUTPUT_ROLES, **{f'amp:{i}':f'关节{i} 驱动器使能' for i in range(count)}}


def validate(c):
    errors, warnings = [], []
    if c.get('stepgen_control','position') not in ('position','velocity_pid'):errors.append('未知StepGen控制模式')
    profile=profile_for(c)
    if c.get('board_profile','custom')!='custom' and not profile:errors.append('未知板卡配置')
    if profile and c['board']!=profile.device:errors.append('板卡配置与底层Mesa型号不一致')
    errors.extend(fixed_rule_errors(c))
    errors.extend(advanced_config.validate(c))
    display=c.get('display','axis')
    if display not in DISPLAYS:errors.append('未知LinuxCNC操作界面')
    if display=='probe_basic':errors.extend(probe_basic_config.validate(c))
    if display in ('qtdragon','qtdragon_hd') and ''.join(a['axis'] for a in c['axes']) not in ('XYZ','XYZA'):
        errors.append('当前QtDragon模板支持XYZ或XYZA，请为其他轴布局选择AXIS或Gmoccapy')
    if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]{0,47}', c['name']):
        errors.append('工程名请用字母开头的英文、数字、下划线或短横线')
    try:
        if ipaddress.ip_address(c['ip']).version != 4: raise ValueError()
    except ValueError: errors.append('Mesa地址需要有效IPv4')
    if c['board'] not in ('7i92', '7i92t', '7i96s', '7i76e', '7i98'):
        errors.append('此版本仅支持列出的以太网Mesa板卡')
    expected = 'hm2_' + c['board'] + '.0'
    if c['host'] != expected: errors.append('主卡HAL前缀必须与所选型号一致：' + expected)
    if c['remote_model'] not in ('SD01', 'SD02'): errors.append('未知从板型号')
    prefix = re.fullmatch(re.escape(c['host']) + r'\.([A-Za-z0-9]{4})\.0\.([0-7])', c['remote_prefix'])
    if not prefix: errors.append('从板前缀必须属于本主卡和串口0，通道0～7')
    elif prefix[1].upper() != c['remote_model']: errors.append('从板前缀中的短名称与型号不符')
    if not re.fullmatch(r'[0x]{8}', c['sserial']): errors.append('串口0模式需为8位0/x，仅启用已配置从板通道')
    elif prefix and c.get('remote_enabled',True):
        ch = int(prefix[2])
        if c['sserial'][ch] != '0': errors.append('从板通道未在串口模式中启用')
        if c['sserial'].count('0') != 1: errors.append('首版支持一块SD从板，只能启用其所在通道')
    if not 100000 <= c['servo_ns'] <= 10000000: errors.append('伺服周期需在0.1～10ms之间')
    if c['watchdog_ns'] < 2 * c['servo_ns']: errors.append('Mesa看门狗至少需要两个伺服周期')
    if not 1 <= c['stepgens'] <= 32 or not 0 <= c['pwmgens'] <= 16 or not 0 <= c['encoders'] <= 16:
        errors.append('硬件资源数量超出支持范围')
    axes = advanced_config.joints(c); letters = ''.join(a['axis'] for a in c['axes'])
    if letters not in ('XYZ', 'XYZA', 'XYZAB', 'XZ'): errors.append('首版支持XYZ、XYZA、XYZAB、XZ独立轴；不含龙门双驱')
    seen = set()
    for i, a in enumerate(axes):
        if a['advanced']['drive']=='stepdir':
            if a['stepgen'] in seen or not 0 <= a['stepgen'] < c['stepgens']: errors.append(f'关节{i} StepGen越界或重复')
            seen.add(a['stepgen'])
        if not all(math.isfinite(float(a[k])) for k in ('scale','velocity','acceleration','minimum','maximum','home','search','latch')):
            errors.append(f'关节{i}参数不能为NaN/无穷大')
        if (a['advanced']['drive']=='stepdir' and a['scale'] == 0) or a['velocity'] <= 0 or a['acceleration'] <= 0: errors.append(f'关节{i}比例不得为零，速度加速度需为正数')
        extra=[a.get('home_offset',a['home']),a.get('home_final_velocity',0.),a.get('ferror',1.),a.get('min_ferror',.25)]
        if not all(math.isfinite(float(value)) for value in extra):errors.append(f'关节{i}回零/跟随误差参数不能为NaN/无穷大')
        if not 0<=a.get('home_final_velocity',0.)<=a['velocity']:errors.append(f'关节{i}最终回零速度需在0和最大速度之间')
        if not 0<a.get('min_ferror',.25)<=a.get('ferror',1.):errors.append(f'关节{i}跟随误差需为正数且MIN_FERROR不超过FERROR')
        if not a['minimum'] <= a['home'] <= a['maximum'] or a['minimum'] >= a['maximum']: errors.append(f'关节{i}行程/回零位置无效')
        if any(not 1 <= a[k] <= 1000000 for k in ('steplen','stepspace','dirsetup','dirhold')): errors.append(f'关节{i}脉冲时序需为1～1000000ns')
        if abs(a['search']) > a['velocity'] or abs(a['latch']) > a['velocity']: errors.append(f'关节{i}回零速度超过最大速度')
        if a['search'] and (not a['latch'] or not any(f'joint.{i}.home-sw-in' in input_targets(role,len(axes)) for _,_,role in input_assignments(c) if role in input_roles(len(axes)))): errors.append(f'关节{i}开关回零需要回零输入和非零锁存速度')
    if len(c['inputs']) != 16 or len(c['outputs']) != 16: errors.append('SD板需要16路输入和16路输出配置')
    assigned = [role for _,_,role in input_assignments(c) if role]
    if len(set(assigned)) != len(assigned): errors.append('同一个输入功能不能重复分配')
    for role in assigned:
        if role not in input_roles(len(axes)): errors.append('非法输入功能：' + role)
    destinations = []
    for role in assigned:
        if role in input_roles(len(axes)):destinations.extend(input_targets(role,len(axes)))
    if len(destinations)!=len(set(destinations)):errors.append('输入功能重叠：同一HAL输入不能由多个针脚驱动')
    if any(role in ('all-home','all-home-limit') for role in assigned):
        sequences=[abs(a['home_sequence']) for a in axes]
        if len(sequences)!=len(set(sequences)):errors.append('共用回零开关需要各关节使用不同回零顺序')
    seen_gpio=set();pins={p['io']:p for p in (c.get('discovery') or {}).get('pins',[])}
    for v in effective_gpio(c):
        index=v.get('io');direction=v.get('direction');role=v.get('role','')
        if type(index) is not int or index<0 or index in seen_gpio:
            errors.append('Mesa GPIO编号无效或重复');continue
        seen_gpio.add(index)
        if profile and index in profile.fixed_gpio:
            rule=profile.fixed_gpio[index]
            if direction!=rule['direction']:errors.append(f'GPIO{index:03}为板卡固定{rule["direction"]}，不可修改方向')
            if rule.get('lock_invert') and v.get('invert',False)!=rule['invert']:errors.append(f'GPIO{index:03}固定反相，不可修改')
        if index not in pins:errors.append(f'GPIO{index:03}没有实际板卡针脚记录');continue
        reason=gpio_reason(c,pins[index])
        if reason:errors.append(f'GPIO{index:03}不可分配：{reason}')
        if direction not in ('in','out','open-drain'):errors.append('Mesa GPIO方向无效')
        if direction=='in' and role not in input_roles(len(axes)):errors.append('Mesa GPIO输入功能无效')
        if direction in ('out','open-drain') and role not in output_roles(len(axes)):errors.append('Mesa GPIO输出功能无效')
        if type(v.get('invert',False)) is not bool:errors.append('Mesa GPIO反相值无效')
    if any(role not in output_roles(len(axes)) for role in c['outputs']): errors.append('存在非法输出功能')
    sp = c['spindle']
    if profile and profile.fixed_pwm_channel is not None and sp['channel']!=profile.fixed_pwm_channel:errors.append(f'{profile.label}主轴PWM通道固定为{profile.fixed_pwm_channel}')
    if type(c.get('pdm_frequency',6000000)) is not int or not 1<=c.get('pdm_frequency',6000000)<=100000000:errors.append('PDM频率需为1～100000000Hz的整数')
    if type(c.get('dpll_timer_us',-50)) is not int or not -1000000<=c.get('dpll_timer_us',-50)<=0:errors.append('DPLL采样提前需为-1000000～0μs的整数')
    if c['pwmgens'] and not 1<=sp['frequency']<=1000000:errors.append('PWM频率需为1～1000000Hz')
    spindle_validation=dict(c,axes=axes)
    errors.extend(spindle_config.validate(spindle_validation))
    if sp['enabled'] and sp.get('type')=='stepdir' and sp.get('encoder',-1)<0:warnings.append('伺服主轴采用Step/Dir速度指令；StepGen速度是脉冲估计，无外部编码器实测反馈，不生成同步螺纹/刚性攻丝配置')
    if c['mpg']['enabled']:
        count=c['mpg'].get('axes',3)
        if type(count) is not int or count not in (3,4,5):errors.append('手轮MPG只支持3、4、5轴')
        elif not all(letter in letters for letter in 'XYZAB'[:count]):errors.append('手轮轴数超过已配置机床轴，请先配置对应的XYZ/XYZA/XYZAB轴')
        if c['encoders'] < 1: errors.append('固定VGA手轮需要Mesa编码器00')
    d = c.get('discovery')
    if profile and c.get('remote_enabled',True):
        serial=[p for p in (d or {}).get('pins',[]) if p.get('secondarymodulename','').lower()=='sserial']
        channel=int(prefix[2]) if prefix else -1
        pair=set()
        for pin in serial:
            match=re.search(r'(tx|rx)(?:data)?\s*([0-7])',pin.get('secondaryfunctionname',''),re.I)
            if match and int(match[2])==channel:pair.add(match[1].lower())
        if pair!={'tx','rx'}:errors.append('当前板卡固件没有所选Smart Serial通道的完整TX/RX引脚，请刷入对应固件后重新读取')
    if profile:
        fixed_channels={int(p['channel']) for p in (profile.baseline or d or {}).get('pins',[]) if p['io'] not in profile.custom_pins and p.get('secondarymodulename','').lower()=='stepgen' and str(p.get('channel','')).isdigit()}
        outputs=[a for a in axes if a['advanced']['drive']=='stepdir']+([{'stepgen':sp.get('stepgen',4)}] if sp['enabled'] and sp.get('type')=='stepdir' else [])
        for axis in outputs:
            channel=axis['stepgen']
            if channel in fixed_channels:continue
            functions=[p.get('secondaryfunctionname','').lower() for p in (d or {}).get('pins',[]) if p['io'] in profile.custom_pins and p.get('secondarymodulename','').lower()=='stepgen' and p.get('channel')==str(channel)]
            if not any('step' in f for f in functions) or not any('dir' in f for f in functions):errors.append(f'StepGen{channel}在自定义引脚中缺少完整Step/Dir对')
    if not d: warnings.append('未导入实际板卡发现结果，资源数量及针脚分配尚未核对')
    else:
        if d.get('source'):warnings.append('正在使用板卡预设固件布局，实机运行前请读取板卡核对')
        if d.get('board',c['board'])!=c['board'] or d.get('address',c['ip'])!=c['ip']:
            errors.append('板卡型号或IP已改变，请重新读取实际针脚记录')
        for k, tag in [('stepgens','stepgen'),('pwmgens','pwmgen'),('encoders','encoder')]:
            if c[k] > d['modules'].get(tag,0): errors.append(f'{k}超过发现的硬件资源')
        if c['mpg']['enabled']:
            for pin in d.get('pins',[]):
                index = pin.get('io')
                if index not in MPG_RESERVED: continue
                module = pin.get('secondarymodulename','').lower()
                if module in ('','none'): continue
                channel = pin.get('channel')
                if channel is None:
                    warnings.append(f'VGA GPIO{index:03}存在{module}复用；XML未给出硬件通道，需核对文本readhmid')
                    continue
                try: unit=int(channel)
                except ValueError:
                    errors.append(f'VGA GPIO{index:03}被{module}全局功能占用');continue
                limit = c['stepgens'] if module=='stepgen' else c['pwmgens'] if module in ('pwm','pwmgen') else c['encoders'] if module in ('qcount','encoder') else None
                if limit is None or unit < limit:
                    errors.append(f'VGA保留GPIO{index:03}与已启用的{module}通道{unit}冲突')
    if any(a['advanced']['drive']=='pwm' for a in axes):warnings.append('模拟伺服PID必须在目标机床上调试，导出不代表已完成整定')
    return errors, warnings


def generate(c):
    errors, warnings = validate(c)
    if errors: raise ValueError('\n'.join(errors))
    h, r, axes = c['host'], c['remote_prefix'], advanced_config.joints(c)
    coord = ''.join(a['axis'] for a in axes)
    def tag(a):return a['axis'].lower()+('_tandem' if a.get('_tandem') else '')
    linear = [a for a in axes if a['axis'] in 'XYZ']
    maxv = max(a['velocity'] for a in linear)
    display=c.get('display','axis')
    display_command='qtvcp '+display if display.startswith('qtdragon') else display
    ini = f'''# FMesa 配置工具生成；机械参数需按实际机器设置
[EMC]
MACHINE = {c['name']}
VERSION = 1.1
[DISPLAY]
DISPLAY = {display_command}
POSITION_OFFSET = RELATIVE
POSITION_FEEDBACK = ACTUAL
MAX_FEED_OVERRIDE = 1.2
DEFAULT_LINEAR_VELOCITY = {min(6., maxv)}
MAX_LINEAR_VELOCITY = {maxv}
DEFAULT_ANGULAR_VELOCITY = 12
MAX_ANGULAR_VELOCITY = 180
[KINS]
JOINTS = {len(axes)}
KINEMATICS = trivkins coordinates={coord} kinstype=BOTH
[EMCMOT]
EMCMOT = motmod
COMM_TIMEOUT = 1.0
SERVO_PERIOD = {c['servo_ns']}
[TASK]
TASK = milltask
CYCLE_TIME = 0.010
[RS274NGC]
PARAMETER_FILE = linuxcnc.var
RS274NGC_STARTUP_CODE = G21 G40 G90 G94 G97 G64 P0.025
[HAL]
HALUI = halui
HALFILE = machine.hal
HALFILE = custom.hal
POSTGUI_HALFILE = custom_postgui.hal
SHUTDOWN = shutdown.hal
[TRAJ]
COORDINATES = {coord}
LINEAR_UNITS = mm
ANGULAR_UNITS = degree
DEFAULT_LINEAR_VELOCITY = {min(maxv,max(.1,maxv/10.))}
MAX_LINEAR_VELOCITY = {maxv}
SPINDLES = 1
[EMCIO]
EMCIO = io
CYCLE_TIME = 0.100
TOOL_TABLE = tool.tbl
'''
    display_geometry=''.join(a['axis'] for a in c['axes']).lower()
    ini=ini.replace('[DISPLAY]\n',f'[DISPLAY]\nGEOMETRY = {display_geometry}\n')
    if coord=='XZ':ini=ini.replace('[DISPLAY]\n','[DISPLAY]\nLATHE = 1\n')
    if display=='axis':
        ini=ini.replace('[DISPLAY]\n','[DISPLAY]\nPROGRAM_PREFIX = ~/linuxcnc/nc_files\nINCREMENTS = 5mm 1mm .5mm .1mm .05mm .01mm .005mm\n')
    rotary=[a for a in axes if a['axis'] not in 'XYZ']
    if rotary:
        angular_max=max(a['velocity'] for a in rotary)
        ini=ini.replace('[TRAJ]\n',f'[TRAJ]\nMAX_ANGULAR_VELOCITY = {angular_max}\nDEFAULT_ANGULAR_VELOCITY = {min(60.,angular_max/10.)}\n')
    if display not in ('axis','probe_basic'):
        ini=ini.replace('POSTGUI_HALFILE = custom_postgui.hal','POSTGUI_HALFILE = postgui.hal\nPOSTGUI_HALFILE = custom_postgui.hal')
        preference=f'WORKINGFOLDER/{display}.pref' if display.startswith('qtdragon') else 'gmoccapy_preferences'
        ini=ini.replace('[DISPLAY]\n',f'[DISPLAY]\nPREFERENCE_FILE_PATH = {preference}\nPROGRAM_PREFIX = .\nINCREMENTS = 5mm 1mm .5mm .1mm .05mm .01mm .005mm\n')
    hal = ['# 自动生成：机器单位mm/degree；主卡固件决定物理针脚',
           'loadrt [KINS]KINEMATICS',
           'loadrt [EMCMOT]EMCMOT servo_period_nsec=[EMCMOT]SERVO_PERIOD num_joints=[KINS]JOINTS num_spindles=1 num_dio=16',
           'loadrt hostmot2',
           f'loadrt hm2_eth board_ip="{c["ip"]}" config="num_encoders={c["encoders"]} num_pwmgens={c["pwmgens"]} num_stepgens={c["stepgens"]}{serial_option(c)}"',
           f'setp {h}.watchdog.timeout_ns {c["watchdog_ns"]}',
           f'addf {h}.read servo-thread', 'addf motion-command-handler servo-thread',
           'addf motion-controller servo-thread']
    hal += [f'addf {h}.write servo-thread', '']
    if c['pwmgens']:
        hal += [f'setp {h}.pwmgen.pwm_frequency {c["spindle"]["frequency"]}',f'setp {h}.pwmgen.pdm_frequency {c.get("pdm_frequency",6000000)}']
    velocity_pid=c.get('stepgen_control','position')=='velocity_pid'
    if velocity_pid:
        names=['pid.'+tag(a) for a in axes]
        if c['spindle']['enabled'] and (c['spindle'].get('type','analog')=='analog' or c['spindle'].get('closed_loop')):names.append('pid.s')
        hal.append('loadrt pid names='+','.join(names))
        hal += [f'addf pid.{tag(a)}.do-pid-calcs servo-thread' for a in axes]
        if 'pid.s' in names:hal.append('addf pid.s.do-pid-calcs servo-thread')
    hal+=dpll_settings(c)
    if c['mpg']['enabled']:
        hal += ['# VGA专用GPIO，仅配置为输入，不提供其他用途分配']
        hal += [f'setp {h}.gpio.{n:03}.is_output FALSE' for n in sorted(MPG_RESERVED)]
        if not any(v['io']==29 for v in effective_gpio(c)):hal.append(f'setp {h}.gpio.029.is_output FALSE')
    for i, a in enumerate(axes):
        letter, sg = a['axis'], f'{h}.stepgen.{a["stepgen"]:02}'
        minimum,maximum=a['minimum'],a['maximum']
        if velocity_pid:
            if minimum==a['home']:minimum-=.01
            elif maximum==a['home']:maximum+=.01
        if not a.get('_tandem'):ini += f'\n[AXIS_{letter}]\nMAX_VELOCITY = {a["velocity"]}\nMAX_ACCELERATION = {a["acceleration"]}\nMIN_LIMIT = {minimum}\nMAX_LIMIT = {maximum}\n'
        ini += f'\n[JOINT_{i}]\nTYPE = {"LINEAR" if letter in "XYZ" else "ANGULAR"}\n'
        for key, value in [('MAX_VELOCITY',a['velocity']),('MAX_ACCELERATION',a['acceleration']),('MIN_LIMIT',minimum),('MAX_LIMIT',maximum),('HOME',a['home']),('HOME_OFFSET',a.get('home_offset',a['home']) if a['search'] else a['home']),('HOME_SEARCH_VEL',a['search']),('HOME_LATCH_VEL',a['latch']),('HOME_SEQUENCE',a['home_sequence']),('HOME_FINAL_VEL',a.get('home_final_velocity',0.)),('FERROR',a.get('ferror',1.)),('MIN_FERROR',a.get('min_ferror',.25))]: ini += f'{key} = {value}\n'
        if velocity_pid:
            values=dict(STEPGEN_MAXVEL=a['velocity']*1.25,STEPGEN_MAXACCEL=a['acceleration']*1.25,
                        STEP_SCALE=a['scale'],STEPLEN=a['steplen'],STEPSPACE=a['stepspace'],DIRSETUP=a['dirsetup'],DIRHOLD=a['dirhold'],
                        P=1e9/c['servo_ns'] if a['advanced']['p']<0 else a['advanced']['p'],I=a['advanced']['i'],D=a['advanced']['d'],
                        FF0=a['advanced']['ff0'],FF1=a['advanced']['ff1'],FF2=a['advanced']['ff2'],BIAS=a['advanced']['bias'],DEADBAND=a['advanced']['deadband'],MAX_OUTPUT=a['advanced']['max_output'])
            ini+=''.join(f'{key} = {value}\n' for key,value in values.items())
        shared_home=any(f'joint.{i}.home-sw-in' in input_targets(role,len(axes)) and
                        any(f'joint.{i}.{side}-lim-sw-in' in input_targets(role,len(axes)) for side in ('neg','pos'))
                        for _,_,role in input_assignments(c))
        if shared_home:ini += 'HOME_IGNORE_LIMITS = YES\n'
        if a['search']:ini += 'HOME_USE_INDEX = NO\n'
        if any(role in ('all-home','all-home-limit') for _,_,role in input_assignments(c)):
            ini += 'HOME_IS_SHARED = 1\n'
        margin=2. if a['advanced']['backlash_enabled'] or a['advanced']['comp_file'] else 1.25
        start=len(hal)
        signal_letter=letter+('_tandem' if a.get('_tandem') else '')
        hal += [f'# {letter}轴 / 关节{i}', f'setp {sg}.step_type 0', f'setp {sg}.control-type 0',
                f'setp {sg}.position-scale {a["scale"]}', f'setp {sg}.maxvel {a["velocity"] * margin}', f'setp {sg}.maxaccel {a["acceleration"] * margin}']
        hal += [f'setp {sg}.{k} {a[k]}' for k in ('steplen','stepspace','dirsetup','dirhold')]
        hal += [f'net sd-{signal_letter}-enable joint.{i}.amp-enable-out => {sg}.enable',
                f'net sd-{signal_letter}-command joint.{i}.motor-pos-cmd => {sg}.position-cmd',
                f'net sd-{signal_letter}-feedback {sg}.position-fb => joint.{i}.motor-pos-fb', '']
        if velocity_pid:
            pid='pid.'+tag(a)
            hal.remove(f'net sd-{signal_letter}-command joint.{i}.motor-pos-cmd => {sg}.position-cmd')
            for j,line in enumerate(hal):
                if line==f'setp {sg}.control-type 0':hal[j]=f'setp {sg}.control-type 1'
            for name in ('maxvel','maxaccel','position-scale','steplen','stepspace','dirsetup','dirhold'):
                ini_key={'maxvel':'STEPGEN_MAXVEL','maxaccel':'STEPGEN_MAXACCEL','position-scale':'STEP_SCALE'}.get(name,name.upper())
                prefix=f'setp {sg}.{name} '
                for j,line in enumerate(hal):
                    if line.startswith(prefix):hal[j]=prefix+f'[JOINT_{i}]{ini_key}'
            for parameter,ini_key in [('Pgain','P'),('Igain','I'),('Dgain','D'),('FF0','FF0'),('FF1','FF1'),('FF2','FF2'),('bias','BIAS'),('deadband','DEADBAND'),('maxoutput','MAX_OUTPUT')]:
                hal.append(f'setp {pid}.{parameter} [JOINT_{i}]{ini_key}')
            hal += [f'setp {pid}.error-previous-target TRUE',f'setp {pid}.maxerror 0.0127',
                    f'net sd-{signal_letter}-enable => {pid}.enable',
                    f'net sd-{signal_letter}-command joint.{i}.motor-pos-cmd => {pid}.command',
                    f'net sd-{signal_letter}-feedback => {pid}.feedback',
                    f'net sd-{signal_letter}-output {pid}.output => {sg}.velocity-cmd']
        v=a['advanced']
        if v['encoder']>=0:
            encoder=f"{h}.encoder.{v['encoder']:02}"
            ini+=f"ENCODER_SCALE = {v['encoder_scale']}\n"
            hal[start:]=[line.replace(f'{sg}.position-fb',f'{encoder}.position') for line in hal[start:]]
            hal += [f'setp {encoder}.counter-mode 0',f'setp {encoder}.filter 1',
                    f'setp {encoder}.index-invert 0',f'setp {encoder}.index-mask 0',
                    f'setp {encoder}.index-mask-invert 0',f'setp {encoder}.scale [JOINT_{i}]ENCODER_SCALE',
                    f'net sd-{signal_letter}-index joint.{i}.index-enable <=> {encoder}.index-enable',
                    f'net sd-{signal_letter}-index => {pid}.index-enable']
        if v['drive']=='pwm':
            pwm=f"{h}.pwmgen.{v['pwm_channel']:02}"
            # Remove all StepGen setup/wires while keeping the joint PID/encoder graph.
            hal[start:]=[line for line in hal[start:] if sg+'.' not in line and line!=f'setp {pid}.maxerror 0.0127']
            ini+=f"OUTPUT_SCALE = {v['output_scale']}\n"
            hal += [f'setp {pwm}.output-type 1',f'setp {pwm}.scale [JOINT_{i}]OUTPUT_SCALE',
                    f'net sd-{signal_letter}-output {pid}.output => {pwm}.value',
                    f'net sd-{signal_letter}-enable joint.{i}.amp-enable-out => {pwm}.enable']
    for v in effective_gpio(c):
        pin=f'{h}.gpio.{v["io"]:03}'
        output=v['direction']!='in'
        hal.append(f'setp {pin}.is_output {str(output).upper()}')
        if output:
            hal += [f'setp {pin}.is_opendrain {str(v["direction"]=="open-drain").upper()}',
                    f'setp {pin}.invert_output {str(v.get("invert",False)).upper()}']
    if any(role=='all-home-limit' for _,_,role in input_assignments(c)):
        hal += ['setp io-any-homing.function 0xfffffffe',
                'setp io-limit-home.function 0x22222222']
        for i in range(len(axes)):hal.append(f'net io-homing-{i} joint.{i}.homing => io-any-homing.in-{i}')
        hal.append('net io-any-homing io-any-homing.out => io-limit-home.in-1')
        # Process the switch before motion reads the limit inputs.
        at=hal.index('addf motion-command-handler servo-thread')
        hal[at:at]=['loadrt lut5 names=io-any-homing,io-limit-home','addf io-any-homing servo-thread','addf io-limit-home servo-thread']
        hal.append('net io-shared-limit io-limit-home.out => '+' '.join(f'joint.{i}.{side}-lim-sw-in' for i in range(len(axes)) for side in ('neg','pos')))
    for signal,pin,role in input_assignments(c):
        targets=input_targets(role,len(axes))
        if role=='all-home-limit':targets=[f'joint.{i}.home-sw-in' for i in range(len(axes))]+['io-limit-home.in-0']
        hal.append(f'net {signal} {pin}'+(' => '+' '.join(targets) if targets else ''))
    if not any(role=='estop-ok' for _,_,role in input_assignments(c)):
        # PNCconf: with no external E-stop assigned, use the software loopback.
        roles=(c['outputs'] if c.get('remote_enabled',True) else [])+[v.get('role','') for v in effective_gpio(c) if v['direction']!='in']
        signal='sd-out-estop-out' if 'estop-out' in roles else 'estop-out'
        hal += [f'net {signal} iocontrol.0.user-enable-out => iocontrol.0.emc-enable-in']
    sources = {'spindle-brake':'spindle.0.brake','machine-enabled':'motion.motion-enabled','estop-out':'iocontrol.0.user-enable-out','flood':'iocontrol.0.coolant-flood','mist':'iocontrol.0.coolant-mist','spindle-on':'spindle.0.on','spindle-forward':'spindle.0.forward','spindle-reverse':'spindle.0.reverse', **{f'dout:{i}':f'motion.digital-out-{i:02}' for i in range(16)}}
    sources.update({f'amp:{i}':f'joint.{i}.amp-enable-out' for i in range(len(axes))})
    grouped = {}
    for i, role in enumerate(c['outputs'] if c.get('remote_enabled',True) else []):
        if role: grouped.setdefault(role, []).append(f'{r}.output-{i:02}')
        else: hal.append(f'setp {r}.output-{i:02} FALSE')
    for v in effective_gpio(c):
        if v['direction']=='in':continue
        pin=f'{h}.gpio.{v["io"]:03}.out'
        if v['role']:grouped.setdefault(v['role'],[]).append(pin)
        else:hal.append(f'setp {pin} FALSE')
    for role, pins in grouped.items():
        if role.startswith('amp:'):
            axis=axes[int(role.split(':')[1])]
            signal='sd-'+axis['axis']+('_tandem' if axis.get('_tandem') else '')+'-enable'
        else:signal='sd-out-'+role.replace(':','-')
        hal.append(f'net {signal} {sources[role]} => ' + ' '.join(pins))
    spindle_ini,spindle_hal=spindle_config.generate(c,grouped)
    ini+=spindle_ini;hal+=spindle_hal
    ini=repair_ini(ini,display,c['spindle']['rpm'])
    if any(a.get('_tandem') for a in axes):
        ini=ini.replace('KINEMATICS = trivkins coordinates='+coord+'\n','KINEMATICS = trivkins coordinates='+coord+' kinstype=BOTH\n')
    if c['mpg']['enabled']:
        hal += fixed_mpg(h,c['mpg'].get('axes',3)).splitlines()
    tool_lines = ['net sd-tool-number iocontrol.0.tool-prep-number => hal_manualtoolchange.number',
            'net sd-tool-change iocontrol.0.tool-change => hal_manualtoolchange.change',
            'net sd-tool-changed hal_manualtoolchange.changed => iocontrol.0.tool-changed']
    if display=='axis':hal += ['loadusr -W hal_manualtoolchange']+tool_lines
    elif display=='gmoccapy':
        tool_lines=[line.replace('hal_manualtoolchange.number','gmoccapy.toolchange-number').replace('hal_manualtoolchange.change','gmoccapy.toolchange-change') for line in tool_lines]
        tool_lines += ['net tooloffset-x motion.tooloffset.x => gmoccapy.tooloffset-x',
                       'net tooloffset-z motion.tooloffset.z => gmoccapy.tooloffset-z']
        if c['spindle']['enabled']:
            speed_signal=next((signal for signal,_,role in input_assignments(c) if role=='spindle-at-speed'),'spindle-at-speed')
            tool_lines.append(f'net {speed_signal} => gmoccapy.spindle_at_speed_led')
    hal += ['net sd-tool-prepared iocontrol.0.tool-prepare => iocontrol.0.tool-prepared']
    # PNCconf schedules hardware writes after motion and all signal-processing components.
    writes=[line for line in hal if line.startswith('addf ') and '.write servo-thread' in line]
    hal=[line for line in hal if line not in writes]+writes
    files = {c['name']+'.ini':ini, 'machine.hal':'\n'.join(hal)+'\n', 'custom.hal':'# 用户扩展HAL\n',
             'custom_postgui.hal':'# 用户界面加载后的扩展HAL\n','shutdown.hal':'# 用户退出时的扩展HAL\n', 'tool.tbl':'T1 P1 Z0 ; Default tool\n',
             'project.json':json.dumps(c,ensure_ascii=False,indent=2)+'\n', 'CHECKS.txt':'\n'.join(warnings)+'\n'}
    if display!='axis':files['postgui.hal']='\n'.join(tool_lines)+'\n'
    if display=='probe_basic':files=probe_basic_config.apply(c,files)
    files=advanced_config.apply(c,files)
    if c.get('language')=='en':
        from i18n import translate
        files={name:(content if name=='project.json' else translate(content,'en')) for name,content in files.items()}
    return files


def export(c, destination):
    files = generate(c)
    path = Path(destination)
    if path.exists(): raise FileExistsError('请选择新目录，避免覆盖手工修改的配置')
    if c.get('display')=='probe_basic':
        source=probe_basic_config.template_dir(c).resolve()
        if path.resolve().is_relative_to(source):raise ValueError('导出目录不能位于Probe Basic模板目录内')
        import tempfile,shutil
        path.parent.mkdir(parents=True,exist_ok=True)
        stage=Path(tempfile.mkdtemp(prefix='.fmesa-pb-',dir=path.parent))
        try:
            probe_basic_config.copy_assets(c,stage)
            for name,content in files.items():(stage/name).write_text(content,encoding='utf-8')
            if path.exists():raise FileExistsError('导出目录已存在')
            stage.rename(path)
        except Exception:
            shutil.rmtree(stage,ignore_errors=True)
            raise
        return path
    path.mkdir(parents=True)
    for name, content in files.items(): (path/name).write_text(content,encoding='utf-8')
    return path


def fixed_mpg(host, axes=3):
    """Confirmed fixed MPG wiring; the machine axes must be configured separately."""
    if type(axes) is not int or axes not in (3,4,5):raise ValueError('手轮MPG只支持3、4、5轴')
    letters='xyzab'[:axes];pins=dict(x=25,y=23,z=21,a=22,b=24)
    lines=['#*********************','#   手轮MPG（固定VGA接口）','#*********************',
           'loadrt mux4 count=1','addf mux4.0 servo-thread']
    lines += [f'setp axis.{letter}.jog-vel-mode 1' for letter in letters]
    lines += ['setp mux4.0.in0 0.025','setp mux4.0.in1 0.0025','setp mux4.0.in2 0.00025',
              '# sel0/sel1同时为1时使用in3，明确置零','setp mux4.0.in3 0',
              f'net scale1 mux4.0.sel0 <= {host}.gpio.028.in_not',
              f'net scale2 mux4.0.sel1 <= {host}.gpio.020.in_not','net mpg-scale <= mux4.0.out']
    lines += [f'net mpg-scale => axis.{letter}.jog-scale' for letter in letters]
    lines += [f'net encoder-counts <= {host}.encoder.00.count']
    lines += [f'net mpg-{letter} axis.{letter}.jog-enable <= {host}.gpio.{pins[letter]:03}.in_not' for letter in letters]
    lines += [f'net encoder-counts => axis.{letter}.jog-counts' for letter in letters]
    return '\n'.join(lines)+'\n'
