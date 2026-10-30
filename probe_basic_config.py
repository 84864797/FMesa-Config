"""Probe Basic manual-toolchange integration using the target's official assets.

Reference: KCJ Engineering Debian 12 machine configuration documentation.
Assets are copied on export, not bundled or downloaded by FMesa Config.
"""
import re
import shutil
from pathlib import Path

DOC_URL='https://kcjengr.github.io/probe_basic/debian_12_bookworm/configuration/machine_config.html'

def template_dir(c):
    selected=c.get('probe_basic_template','').strip()
    if selected:return Path(selected).expanduser()
    choices=[Path('/usr/share/configs/machine_setup_files'),
             Path('/usr/share/configs/probe_basic_machine_config_setup_files'),
             Path.home()/'linuxcnc/configs/probe_basic_machine_config_setup_files',
             Path.home()/'linuxcnc/configs/machine_setup_files']
    return next((p for p in choices if (p/'custom_config.yml').is_file()),None)


def validate(c):
    coords=''.join(a['axis'] for a in c['axes'])
    if coords not in ('XYZ','XYZA','XYZAB','XYZAC','XYZBC'):
        return ['Probe Basic当前模板支持XYZ、XYZA、XYZAB、XYZAC、XYZBC铣床布局']
    root=template_dir(c)
    if root is None:return ['Probe Basic需要官方machine_setup_files模板，请安装Probe Basic或选择模板目录']
    required=['custom_config.yml','probe_basic.var','subroutines/on_abort.ngc',
              f'user_dro_display/{coords.lower()}_dros/dros_{coords.lower()}.py','user_buttons','user_tabs']
    absent=[name for name in required if not (root/name).exists()]
    if absent:return ['Probe Basic模板缺少：'+', '.join(absent)]
    return []


def set_ini(text,section,values):
    pattern=r'(?ms)^\['+re.escape(section)+r'\][^\n]*\n(.*?)(?=^\[|\Z)'
    match=re.search(pattern,text)
    if not match:return text+'\n['+section+']\n'+''.join(f'{k} = {v}\n' for k,v in values.items())
    body=match[1]
    for key,value in values.items():
        entry=r'(?m)^'+re.escape(key)+r'\s*=.*$'
        if re.search(entry,body):body=re.sub(entry,lambda _:f'{key} = {value}',body)
        else:body+=f'{key} = {value}\n'
    return text[:match.start(1)]+body+text[match.end(1):]


def apply(c,files):
    name=c['name']+'.ini';text=files[name];coords=''.join(a['axis'] for a in c['axes'])
    root=template_dir(c)
    text=set_ini(text,'DISPLAY',dict(DISPLAY='probe_basic',CONFIG_FILE='custom_config.yml',
        OPEN_FILE='blank.ngc',PREFERENCE_FILE='probe_basic.pref',PROGRAM_PREFIX='~/linuxcnc/nc_files',
        INTRO_GRAPHIC='pbsplash.png' if (root/'pbsplash.png').is_file() else '',INTRO_TIME=5,
        MAX_FEED_OVERRIDE='2.0',MAX_SPINDLE_OVERRIDE='2.0',MIN_SPINDLE_OVERRIDE='0.5',
        INCREMENTS='JOG .254mm .0254mm .00254mm',USER_TABS_PATH='user_tabs/',
        USER_BUTTONS_PATH='user_buttons/',USER_DROS_PATH='user_dro_display/',DRO_DISPLAY=coords,
        GEOMETRY=coords,OFFSET_COLUMNS=coords+'R',TOOL_TABLE_COLUMNS='TZDR',ATC_TAB_DISPLAY=0))
    # Official inch startup F10/G64 P.001 translated to metric F254/P.0254.
    text=set_ini(text,'RS274NGC',dict(RS274NGC_STARTUP_CODE='F254 S300 G21 G17 G40 G49 G54 G64 P.0254 G80 G90 G91.1 G92.1 G94 G97 G98',
        PARAMETER_FILE='probe_basic.var',OWORD_NARGS=1,NO_DOWNCASE_OWORD=1,
        SUBROUTINE_PATH='subroutines',ON_ABORT_COMMAND='O<on_abort> CALL'))
    text=set_ini(text,'HAL',dict(HALUI='halui',POSTGUI_HALFILE='probe_basic_postgui.hal',TWOPASS='on'))
    text=text.replace('POSTGUI_HALFILE = probe_basic_postgui.hal\n',
                      'POSTGUI_HALFILE = probe_basic_postgui.hal\nPOSTGUI_HALFILE = custom_postgui.hal\n')
    text=set_ini(text,'TRAJ',dict(AXES=len(c['axes'])))
    files[name]=text;files.pop('postgui.hal',None)
    files['machine.hal']=files['machine.hal'].replace('num_spindles=1 num_dio=16','num_spindles=1 num_dio=16 num_aio=3')
    custom=(root/'custom_config.yml').read_text(encoding='utf-8-sig')
    # Template variants use literal XYZ or INI/Jinja columns; adapt only the offset-table block.
    custom=re.sub(r'(?ms)(^  offsettable:\s*\n.*?^      columns:)[^\n]*',lambda m:m[1]+' "'+coords+'R"',custom)
    files['custom_config.yml']=custom
    files['probe_basic.var']=(root/'probe_basic.var').read_text(encoding='utf-8-sig')
    files['blank.ngc']='(FMesa Probe Basic blank program)\nM2\n'
    post=['# Probe Basic manual tool change and cycle timer; no simulation probe or spindle sources.',
          'loadrt time','loadrt not','addf time.0 servo-thread','addf not.0 servo-thread',
          'net pb-idle halui.program.is-idle => not.0.in',
          'net pb-paused halui.program.is-paused => time.0.pause',
          'net pb-running not.0.out => time.0.start',
          'net pb-seconds time.0.seconds => qtpyvcp.timerseconds.in',
          'net pb-minutes time.0.minutes => qtpyvcp.timerminutes.in',
          'net pb-hours time.0.hours => qtpyvcp.timerhours.in',
          'net sd-tool-number iocontrol.0.tool-prep-number => qtpyvcp_manualtoolchange.number',
          'net sd-tool-change iocontrol.0.tool-change => qtpyvcp_manualtoolchange.change',
          'net sd-tool-changed qtpyvcp_manualtoolchange.changed => iocontrol.0.tool-changed']
    from io_config import input_assignments
    for signal,pin,role in input_assignments(c):
        if role=='probe':post.append(f'net {signal} => qtpyvcp.probe-led.on')
    files['probe_basic_postgui.hal']='\n'.join(post)+'\n'
    files['PROBE_BASIC_SETUP.txt']='Probe Basic manual-toolchange configuration.\nInstall Probe Basic/QtPyVCP on the target system.\nOfficial support assets are copied from: '+str(root)+'\nConfigure probe/tool-setter parameters in Probe Basic before using measurement cycles.\nATC, toolchange remaps and simulated probe/spindle signals are not enabled.\nReference: '+DOC_URL+'\n'
    return files


def copy_assets(c,destination):
    source=template_dir(c).resolve();destination=Path(destination).resolve()
    if destination.is_relative_to(source):raise ValueError('导出目录不能位于Probe Basic模板目录内')
    for item in source.iterdir():
        if item.name.startswith('.') or item.name=='__pycache__':continue
        if item.is_symlink():raise ValueError('Probe Basic模板根目录不能包含符号链接，请选择完整的官方模板副本')
        target=destination/item.name
        if item.is_dir():shutil.copytree(item,target,ignore=shutil.ignore_patterns('__pycache__','*.pyc','.git'),symlinks=False)
        elif item.suffix not in ('.ini','.hal'):shutil.copy2(item,target)
