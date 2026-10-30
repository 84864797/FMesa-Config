"""Optional PNCconf-style machine/joint settings; no hardware access."""
import copy
import math
import re
from pathlib import Path
from probe_basic_config import set_ini

MACHINE_DEFAULTS=dict(require_homing=True,restore_position=False,individual_homing=False,
    tool_change_with_spindle_on=False,tool_change_quill_up=False,random_toolchanger=False,
    mdi_commands='',editor='',image_filters=False)
JOINT_DEFAULTS=dict(drive='stepdir',pwm_channel=0,output_scale=10.,encoder=-1,encoder_scale=0.,
    home_use_index=False,backlash_enabled=False,backlash=0.,comp_file='',comp_type=0,
    p=-1.,i=0.,d=0.,ff0=0.,ff1=1.,ff2=0.,bias=0.,deadband=0.,max_output=0.,
    tandem_enabled=False,tandem_stepgen=3,tandem_scale=0.,tandem_home_offset=0.)


def joints(c):
    result=[]
    for a in c['axes']:
        extra={**JOINT_DEFAULTS,**a.get('advanced',{})}
        primary=copy.deepcopy(a);primary['advanced']=extra;result.append(primary)
        if extra['tandem_enabled']:
            primary['home_sequence']=-abs(a['home_sequence'])
            secondary=copy.deepcopy(primary)
            secondary.update(stepgen=extra['tandem_stepgen'],scale=extra['tandem_scale'],
                             home_offset=extra['tandem_home_offset'],_tandem=True)
            # Each gantry motor has its own home switch; encoder feedback belongs to the primary.
            secondary['advanced'].update(drive='stepdir',encoder=-1,home_use_index=False,
                tandem_enabled=False,backlash_enabled=False,comp_file='')
            result.append(secondary)
    return result


def validate(c):
    errors=[];used_enc={0:'MPG'} if c['mpg']['enabled'] else {};used_pwm={}
    if c['spindle']['enabled'] and c['spindle'].get('type','analog')=='analog':used_pwm[c['spindle']['channel']]='spindle'
    sp=c['spindle']
    if sp['enabled'] and sp.get('encoder',-1)>=0:used_enc[sp['encoder']]='spindle'
    axes=joints(c)
    machine={**MACHINE_DEFAULTS,**c.get('machine_options',{})}
    if any(a.get('_tandem') for a in axes) and machine['individual_homing']:errors.append('双驱同步回零不能启用单独回零')
    for key in ('editor',):
        if any(ch in machine[key] for ch in ('\n','\r','\x00')):errors.append('编辑器名称不能包含换行或空字符')
    if len(axes)>9:errors.append('LinuxCNC最多支持9个关节')
    for n,a in enumerate(axes):
        v=a['advanced'];prefix=f'关节{n}'
        if v['drive'] not in ('stepdir','pwm'):errors.append(prefix+'驱动方式无效')
        if any(not math.isfinite(float(v[k])) for k in ('output_scale','encoder_scale','backlash','p','i','d','ff0','ff1','ff2','bias','deadband','max_output')):errors.append(prefix+'高级参数不能为NaN或无穷大')
        if v['drive']=='pwm':
            channel=v['pwm_channel']
            if channel in used_pwm or not 0<=channel<c['pwmgens']:errors.append(prefix+'PWM通道越界或重复')
            used_pwm[channel]=prefix
            if v['encoder']<0 or v['output_scale']==0 or v['p']<0 or v['max_output']<=0:errors.append(prefix+'模拟伺服需要编码器、非零输出比例、明确PID增益和正数最大输出')
            if c.get('board_profile')=='F7I92':errors.append('F7I92固定PWM0用于主轴，不支持模拟伺服轴；请使用具有对应资源的自定义板卡')
        if v['encoder']>=0:
            channel=v['encoder']
            if channel in used_enc or not 0<=channel<c['encoders']:errors.append(prefix+'编码器通道越界或与手轮/主轴/其他轴重复')
            used_enc[channel]=prefix
            if v['encoder_scale']==0:errors.append(prefix+'编码器比例不能为零')
        if v['home_use_index'] and c.get('discovery'):
            pins=[p for p in c['discovery'].get('pins',[]) if p.get('secondarymodulename','').lower() in ('encoder','qcount','qcounter') and str(p.get('channel'))==str(v['encoder'])]
            if pins and not any('index' in p.get('secondaryfunctionname','').lower() for p in pins):errors.append(prefix+'实际固件没有编码器Index引脚')
        if v['home_use_index'] and (v['encoder']<0 or not a['search']):errors.append(prefix+'索引回零需要独立编码器和开关搜索速度')
        if v['backlash_enabled'] and v['comp_file']:errors.append(prefix+'反向间隙和补偿表不能同时启用')
        if v['backlash']<0:errors.append(prefix+'反向间隙不能为负数')
        if v['comp_file']:
            path=Path(v['comp_file']).expanduser()
            if not path.is_file():errors.append(prefix+'补偿文件不存在')
            elif v['comp_type'] not in (0,1):errors.append(prefix+'补偿表类型只能为0或1')
        if v['tandem_enabled']:
            if a['axis'] not in 'XYZ':errors.append('双驱只支持线性轴')
            if c.get('display') in ('qtdragon','qtdragon_hd'):errors.append('当前QtDragon界面不支持双驱关节；请选择AXIS、Gmoccapy或Probe Basic')
            if a['home_sequence']==0:errors.append('双驱同步回零需要大于0的回零顺序')
            if not a['search']:errors.append('双驱需要独立回零开关和非零搜索速度')
            from io_config import input_assignments,input_targets
            for index in (n,n+1):
                if not any(f'joint.{index}.home-sw-in' in input_targets(role,len(axes)) and not role.startswith('all-') for _,_,role in input_assignments(c)):
                    errors.append(f'双驱关节{index}需要独立回零开关')
    if any(a['advanced']['encoder']>=0 or a['advanced']['drive']=='pwm' for a in axes) and c.get('stepgen_control')!='velocity_pid':errors.append('外部反馈需要PNCconf速度/PID模式')
    return errors


def apply(c,files):
    """Apply optional INI policies and joint compensation; core wires feedback."""
    name=c['name']+'.ini';ini=files[name];machine={**MACHINE_DEFAULTS,**c.get('machine_options',{})}
    if not machine['require_homing']:ini=set_ini(ini,'TRAJ',{'NO_FORCE_HOMING':1})
    if machine['restore_position']:ini=set_ini(ini,'TRAJ',{'POSITION_FILE':'position.txt'})
    for field,key in [('tool_change_with_spindle_on','TOOL_CHANGE_WITH_SPINDLE_ON'),('tool_change_quill_up','TOOL_CHANGE_QUILL_UP'),('random_toolchanger','RANDOM_TOOLCHANGER')]:
        if machine[field]:ini=set_ini(ini,'EMCIO',{key:1})
    if machine['individual_homing']:ini=re.sub(r'(?m)^HOME_SEQUENCE = .*\n','',ini)
    commands=[line.strip() for line in machine['mdi_commands'].splitlines() if line.strip()]
    if commands:ini+='\n[HALUI]\n'+''.join('MDI_COMMAND = '+line+'\n' for line in commands)
    if machine['editor']:ini=set_ini(ini,'DISPLAY',{'EDITOR':machine['editor']})
    if machine['image_filters']:
        ini=ini.replace('[FILTER]\n','[FILTER]\nPROGRAM_EXTENSION = .png,.gif,.jpg Greyscale Depth Image\nPROGRAM_EXTENSION = .py Python Script\npng = image-to-gcode\ngif = image-to-gcode\njpg = image-to-gcode\npy = python\n')
    for n,a in enumerate(joints(c)):
        v=a['advanced'];values={}
        if v['backlash_enabled']:values['BACKLASH']=v['backlash']
        if v['comp_file']:
            target=f'joint-{n}-compensation.dat';files[target]=Path(v['comp_file']).expanduser().read_text()
            values.update(COMP_FILE=target,COMP_FILE_TYPE=v['comp_type'])
        if v['backlash_enabled'] or v['comp_file']:values.update(STEPGEN_MAXVEL=a['velocity']*2,STEPGEN_MAXACCEL=a['acceleration']*2)
        if v['home_use_index']:values['HOME_USE_INDEX']='YES'
        if values:ini=set_ini(ini,f'JOINT_{n}',values)
    files[name]=ini
    return files


def remap_joint_role(role,before,after):
    """Preserve an IO assignment's motor identity when tandem numbering changes."""
    if ':' not in role:return role
    kind,index=role.split(':',1)
    if kind not in ('home','neg','pos','both','home-neg','home-pos','home-both','amp'):return role
    old=joints(before);new=joints(after)
    if not index.isdigit() or int(index)>=len(old):return role
    identity=lambda a:(a['axis'],bool(a.get('_tandem')))
    target=identity(old[int(index)])
    return next((f'{kind}:{i}' for i,a in enumerate(new) if identity(a)==target),'')
