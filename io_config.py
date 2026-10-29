"""Shared digital IO roles and discovered Mesa GPIO availability."""
from board_profiles import profile_for,effective_gpio
def input_targets(role, count):
    fixed = {'estop-ok':['iocontrol.0.emc-enable-in'], 'probe':['motion.probe-input'],
             'feed-hold':['motion.feed-hold'], 'feed-inhibit':['motion.feed-inhibit'],
             'spindle-at-speed':['spindle.0.at-speed'], 'cycle-start':['halui.program.run'],
             'abort':['halui.program.stop'], 'single-step':['halui.program.step'],
             'program-pause':['halui.program.pause'], 'program-resume':['halui.program.resume'],
             'spindle-manual-cw':['halui.spindle.0.forward'], 'spindle-manual-ccw':['halui.spindle.0.reverse'],
             'spindle-manual-stop':['halui.spindle.0.stop']}
    if role in fixed:return fixed[role]
    if role.startswith('din:'):return [f'motion.digital-in-{int(role.split(":")[1]):02}']
    kinds = {'home':['home-sw-in'], 'neg':['neg-lim-sw-in'], 'pos':['pos-lim-sw-in'],
             'both':['neg-lim-sw-in','pos-lim-sw-in'],
             'home-neg':['home-sw-in','neg-lim-sw-in'],
             'home-pos':['home-sw-in','pos-lim-sw-in'],
             'home-both':['home-sw-in','neg-lim-sw-in','pos-lim-sw-in']}
    if role in ('all-home','all-limit','all-home-limit'):
        fields = ['home-sw-in'] if role=='all-home' else ['neg-lim-sw-in','pos-lim-sw-in'] if role=='all-limit' else kinds['home-both']
        return [f'joint.{i}.{field}' for i in range(count) for field in fields]
    if ':' in role:
        kind, index = role.split(':')
        return [f'joint.{int(index)}.{field}' for field in kinds.get(kind,[])]
    return []


def gpio_reason(c, pin):
    """Empty means available; unrecognized muxes stay blocked."""
    from config_core import MPG_RESERVED
    index = pin['io']
    profile=profile_for(c)
    if profile and index in profile.reserved_gpio:return '板卡手轮专用'
    if c['mpg']['enabled'] and index in MPG_RESERVED:return 'VGA手轮专用'
    if 'secondarymodulename' not in pin:return '固件复用信息缺失'
    module = pin.get('secondarymodulename','').lower()
    if profile and profile.baseline and index not in profile.custom_pins and module not in ('none',''):
        return '板卡固定功能：'+module
    if module in ('','none','null','ioport'):return ''
    limits = {'stepgen':c['stepgens'],'pwm':c['pwmgens'],'pwmgen':c['pwmgens'],
              'qcount':c['encoders'],'qcounter':c['encoders'],'encoder':c['encoders']}
    try:channel=int(pin.get('channel',''))
    except (ValueError,TypeError):return f'{module}复用，通道未确认'
    if module=='sserial' and channel==0 and not c.get('remote_enabled',True):return ''
    if module in limits and channel >= limits[module]:return ''
    return f'{module}通道{channel}占用'


def input_assignments(c):
    entries = [(f'sd-input-{i:02}',f'{c["remote_prefix"]}.input-{i:02}'+('-not' if v['invert'] else ''),v['role']) for i,v in enumerate(c['inputs'])] if c.get('remote_enabled',True) else []
    entries += [(f'mesa-input-{v["io"]:03}',f'{c["host"]}.gpio.{v["io"]:03}.'+('in_not' if v.get('invert') else 'in'),v['role']) for v in effective_gpio(c) if v.get('direction')=='in']
    return entries
