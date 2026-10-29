"""Board registry. Board wiring is separate from HostMot2 device/firmware identity.

Add profiles with register_profile(); UI and exporter consume the same rules.
Firmware functions are detected metadata, never arbitrary runtime pin remapping.
"""
from dataclasses import dataclass,field
from copy import deepcopy

@dataclass(frozen=True)
class BoardProfile:
    key: str
    label: str
    device: str
    fixed_gpio: dict = field(default_factory=dict)
    custom_pins: tuple = ()
    reserved_gpio: tuple = ()
    baseline: dict | None = None
    fixed_pwm_channel: int | None = None

PROFILES={}

def register_profile(profile):
    if profile.key in PROFILES:raise ValueError('Duplicate board profile: '+profile.key)
    if profile.key=='custom' or not profile.key:raise ValueError('Reserved/empty board profile key')
    if profile.device not in ('7i92','7i92t','7i96s','7i76e','7i98'):raise ValueError('Unsupported HostMot2 device')
    if profile.fixed_pwm_channel is not None and (type(profile.fixed_pwm_channel) is not int or not 0<=profile.fixed_pwm_channel<16):raise ValueError('Invalid fixed PWM channel')
    indices=list(profile.fixed_gpio)+list(profile.custom_pins)+list(profile.reserved_gpio)
    if any(type(i) is not int or not 0<=i<256 for i in indices):raise ValueError('Invalid GPIO index')
    if len(indices)!=len(set(indices)):raise ValueError('Overlapping board pin groups')
    for rule in profile.fixed_gpio.values():
        if rule.get('direction') not in ('in','out','open-drain'):raise ValueError('Invalid fixed GPIO direction')
        if type(rule.get('invert',False)) is not bool:raise ValueError('Invalid fixed GPIO inversion')
    PROFILES[profile.key]=deepcopy(profile)

def fixed_rule_errors(c):
    profile=profile_for(c)
    if not profile:return []
    errors=[]
    actual={p['io']:p for p in (c.get('discovery') or {}).get('pins',[])}
    for expected in (profile.baseline or {}).get('pins',[]):
        index=expected['io']
        if index in profile.custom_pins:continue
        pin=actual.get(index)
        if pin is None or pin.get('secondarymodulename','').lower()!=expected.get('secondarymodulename','').lower():
            errors.append(f'{profile.label} GPIO{index:03}固件功能不符合固定接线，请核对固件');continue
        if expected.get('channel') is not None and pin.get('channel')!=expected['channel']:
            errors.append(f'{profile.label} GPIO{index:03}固件通道不符合固定接线')
    return errors

def profile_for(c):
    return PROFILES.get(c.get('board_profile','custom'))

def default_discovery(key):
    profile=PROFILES.get(key)
    return deepcopy(profile.baseline) if profile and profile.baseline else None

def suppressed_gpio(c):
    profile=profile_for(c)
    mode=c.get('spindle',{}).get('type','analog')
    return {i for i,r in profile.fixed_gpio.items() if r.get('spindle_types') and mode not in r['spindle_types']} if profile else set()

def effective_gpio(c):
    suppressed=suppressed_gpio(c)
    entries=[deepcopy(v) for v in c.get('mesa_gpio',[]) if v['io'] not in suppressed];profile=profile_for(c)
    if profile:
        selected={v['io'] for v in entries}
        for index,rule in profile.fixed_gpio.items():
            if index in suppressed:continue
            if index not in selected:
                entries.append(dict(io=index,direction=rule['direction'],invert=rule.get('invert',False),role=rule.get('default_role','')))
    input29=c.get('mpg',{}).get('input29',{})
    if input29.get('role') or profile and 29 in profile.fixed_gpio:
        entries=[v for v in entries if v['io']!=29]+[dict(io=29,direction='in',role=input29.get('role',''),invert=input29.get('invert',False))]
    return entries


def f7i92_baseline():
    pins=[dict(io=i,secondarymodulename='None') for i in range(34)]
    pins[1].update(secondarymodulename='PWM',channel='0',secondaryfunctionname='PWM')
    for ch in range(5):
        for offset,function in ((0,'Step/Table1'),(1,'Dir/Table2')):
            pins[4+2*ch+offset].update(secondarymodulename='StepGen',channel=str(ch),secondaryfunctionname=function)
    pins[26].update(secondarymodulename='QCount',channel='0',secondaryfunctionname='Quad-B')
    pins[27].update(secondarymodulename='QCount',channel='0',secondaryfunctionname='Quad-A')
    db25=(1,14,2,15,3,16,4,17,5,6,7,8,9,10,11,12,13)
    for i,p in enumerate(pins):
        p.update(connector='P2' if i<17 else 'P1',pin=str(db25[i%17]))
    return dict(modules={'stepgen':5,'pwmgen':1,'encoder':1,'dpll':1},pins=pins,
                source='F7I92 supplied default firmware pinout',raw='F7I92 默认固件模板；读取板卡后以实际固件为准。')

register_profile(BoardProfile(
    key='F7I92',label='F7I92',device='7i92',custom_pins=(30,31,32,33),
    reserved_gpio=(20,21,22,23,24,25,28),
    fixed_pwm_channel=0,
    fixed_gpio={**{i:dict(direction='out',invert=True,lock_invert=True,page='spindle' if i==0 else 'io',spindle_types=('analog',) if i==0 else (),default_role='spindle-forward' if i==0 else '') for i in (0,2,3)},
                29:dict(direction='in',page='mpg'),
                **{i:dict(direction='in',page='io') for i in (14,15,16,17,18,19)}},
    baseline=f7i92_baseline()))
