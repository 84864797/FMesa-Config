"""Spindle profiles: RPM at motion interface, rev/s at StepGen interface.

Step/Dir follows PNCconf's no-external-encoder spindle path: velocity mode,
machine enable, speed-out-rps and estimated step-generator velocity feedback.
"""
import math
from io_config import input_assignments

SERVO_DEFAULTS=dict(stepgen=4,pulses_per_rev=0.,acceleration=300.,steplen=5000,stepspace=5000,dirsetup=10000,dirhold=10000)

def pwm_gpio(c):
    channel=c['spindle']['channel']
    return [p['io'] for p in (c.get('discovery') or {}).get('pins',[])
            if p.get('secondarymodulename','').lower() in ('pwm','pwmgen')
            and str(p.get('channel'))==str(channel)
            and p.get('secondaryfunctionname','').lower()=='pwm']


def at_speed(c):
    if any(role=='spindle-at-speed' for _,_,role in input_assignments(c)):return []
    return ['net spindle-at-speed => spindle.0.at-speed','sets spindle-at-speed TRUE']


def defaults():
    return dict(enabled=True,type='analog',channel=0,rpm=2000.,frequency=200,invert_pwm=True,**SERVO_DEFAULTS)

def validate(c):
    sp=c['spindle'];errors=[]
    mode=sp.get('type','analog')
    if mode not in ('analog','stepdir'):return ['未知主轴类型']
    if not sp['enabled']:return errors
    if not math.isfinite(sp['rpm']) or sp['rpm']<=0:return ['主轴最高/满量程转速必须为正数']
    if mode=='analog':
        if type(sp.get('invert_pwm',False)) is not bool:errors.append('PWM反向必须为开关值')
        if not 0<=sp['channel']<c['pwmgens']:errors.append('主轴PWM通道无效')
        if sp.get('invert_pwm',False) and not pwm_gpio(c):errors.append('PWM反向需要读取固件，确认PWM实际GPIO引脚')
        return errors
    values={**SERVO_DEFAULTS,**sp}
    channel=values['stepgen']
    if type(channel) is not int or not 0<=channel<c['stepgens']:errors.append('伺服主轴StepGen通道越界')
    if any(a['stepgen']==channel for a in c['axes']):errors.append('伺服主轴StepGen不能与机床轴重复')
    if not math.isfinite(values['pulses_per_rev']) or values['pulses_per_rev']==0:errors.append('伺服主轴必须填写非零每转脉冲数')
    if not math.isfinite(values['acceleration']) or values['acceleration']<=0:errors.append('伺服主轴加速度必须为正数，单位rev/s²')
    timing=all(type(values[k]) is int and 1<=values[k]<=1000000 for k in ('steplen','stepspace','dirsetup','dirhold'))
    if not timing:errors.append('伺服主轴脉冲时序需为1～1000000ns的整数')
    elif math.isfinite(values['pulses_per_rev']) and sp['rpm']/60*abs(values['pulses_per_rev'])>1e9/(values['steplen']+values['stepspace']):
        errors.append('伺服主轴最高转速所需脉冲频率超过所填脉宽/间隔允许值')
    return errors

def generate(c,grouped):
    sp=c['spindle'];h=c['host']
    if not sp['enabled']:return '',[]
    mode=sp.get('type','analog')
    ini=f'\n[SPINDLE_0]\nMAX_FORWARD_VELOCITY = {sp["rpm"]}\nMAX_REVERSE_VELOCITY = {sp["rpm"]}\n'
    if mode=='analog':
        pwm=f'{h}.pwmgen.{sp["channel"]:02}'
        ini+=f'OUTPUT_SCALE = {sp["rpm"]}\n'
        # PNCconf ordinary open-loop mainboard PWM path uses signed RPM.
        signal='sd-out-spindle-on' if 'spindle-on' in grouped else 'sd-spindle-enable'
        hal=[f'setp {pwm}.output-type 1',f'setp {pwm}.scale [SPINDLE_0]OUTPUT_SCALE']
        if sp.get('invert_pwm',False):
            hal += [f'setp {h}.gpio.{io:03}.invert_output TRUE' for io in pwm_gpio(c)]
        hal += [f'net sd-spindle-speed spindle.0.speed-out => {pwm}.value',
                f'net {signal} spindle.0.on => {pwm}.enable']
        if c.get('stepgen_control')=='velocity_pid':
            # PNCconf also declares pid.s in this open-loop branch; PWM still
            # receives speed-out directly, not pid.s.output.
            values=dict(P=0,I=0,D=0,BIAS=0,FF0=1,FF1=0,FF2=0,DEADBAND=0,MAX_OUTPUT=sp['rpm'])
            ini+=''.join(f'{key} = {value}\n' for key,value in values.items())
            for pin,key in [('Pgain','P'),('Igain','I'),('Dgain','D'),('bias','BIAS'),('FF0','FF0'),('FF1','FF1'),('FF2','FF2'),('deadband','DEADBAND'),('maxoutput','MAX_OUTPUT')]:
                hal.append(f'setp pid.s.{pin} [SPINDLE_0]{key}')
            hal += ['setp pid.s.error-previous-target TRUE',
                    'net sd-spindle-speed => pid.s.command',f'net {signal} => pid.s.enable',
                    'net spindle-index-enable spindle.0.index-enable <=> pid.s.index-enable',
                    'net spindle-vel-fb-rpm => pid.s.feedback','net spindle-output <= pid.s.output']
        return ini,hal+at_speed(c)
    values={**SERVO_DEFAULTS,**sp}
    params=dict(STEP_SCALE=values['pulses_per_rev'],STEPGEN_MAXVEL=sp['rpm']/60*1.25,
                STEPGEN_MAXACCEL=values['acceleration']*1.25,
                STEPLEN=values['steplen'],STEPSPACE=values['stepspace'],DIRSETUP=values['dirsetup'],DIRHOLD=values['dirhold'])
    ini+=''.join(f'{key} = {value}\n' for key,value in params.items())
    sg=f'{h}.stepgen.{values["stepgen"]:02}'
    hal=[f'setp {sg}.step_type 0',f'setp {sg}.control-type 1']
    for field,key in [('position-scale','STEP_SCALE'),('maxvel','STEPGEN_MAXVEL'),('maxaccel','STEPGEN_MAXACCEL'),('steplen','STEPLEN'),('stepspace','STEPSPACE'),('dirsetup','DIRSETUP'),('dirhold','DIRHOLD')]:
        hal.append(f'setp {sg}.{field} [SPINDLE_0]{key}')
    signal='sd-out-machine-enabled' if 'machine-enabled' in grouped else 'sd-spindle-machine-enable'
    hal += [f'net {signal} motion.motion-enabled => {sg}.enable',
            f'net sd-spindle-speed-rps spindle.0.speed-out-rps => {sg}.velocity-cmd',
            '# StepGen速度为脉冲输出估计，不是电机编码器实测反馈',
            f'net sd-spindle-estimated-speed {sg}.velocity-fb => spindle.0.speed-in']
    return ini,hal+at_speed(c)
