"""Mesa发现：通过参数列表调用工具，不拼接shell命令。"""
import ipaddress
import os
import re
import subprocess
import xml.etree.ElementTree as ET


def run(args, timeout=25):
    env = dict(os.environ, LC_ALL='C', LANG='C')
    result = subprocess.run(args, capture_output=True, text=True, encoding='utf-8',
                            errors='replace', timeout=timeout, env=env)
    if result.returncode:
        raise RuntimeError((result.stderr or result.stdout or f'退出码{result.returncode}').strip())
    return result.stdout


def parse(text):
    if len(text) > 2_000_000: raise ValueError('发现记录过大')
    modules, pins = {}, []
    def norm(name):
        n = re.sub(r'[^a-z0-9]', '', name.lower())
        return {'qcount':'encoder','qcounter':'encoder','encoder':'encoder',
                'stepgen':'stepgen','pwm':'pwmgen','pwmgen':'pwmgen','sserial':'sserial'}.get(n,n)
    start = text.find('<hostmot2>')
    if start >= 0:
        end = text.find('</hostmot2>',start)
        if end < 0: raise ValueError('HostMot2 XML不完整')
        root = ET.fromstring(text[start:end+len('</hostmot2>')])
        for m in root.findall('.//module'):
            name = m.findtext('tagname',''); count = int(m.findtext('numinstances','0'))
            modules[norm(name)] = count
        for index, p in enumerate(root.findall('.//pin')):
            pins.append({'io':index, **{child.tag:(child.text or '').strip() for child in p}})
    else:
        for count, name in re.findall(r'There are\s+(\d+)\s+of\s+(.+?)\s+in configuration',text,re.I):
            modules[norm(name)] = int(count)
        connector = ''
        for line in text.splitlines():
            if line.startswith('IO Connections for '): connector = line.removeprefix('IO Connections for ').strip()
            elif connector and re.match(r'^\s*\d+\s+\d+\s+',line):
                fields=line.split()
                pin={'connector':connector,'raw':line.strip(),'io':int(fields[1])}
                if len(fields)>=4:pin['secondarymodulename']=fields[3]
                if len(fields)>=6:pin.update(channel=fields[4],secondaryfunctionname=fields[5])
                pins.append(pin)
    if not modules: raise ValueError('没有找到模块数量；请导入mesaflash --readhmid原始文本或XML')
    return {'modules':modules,'pins':pins,'raw':text}


def discover(board, address, sserial=False):
    if board not in ('7i92','7i92t','7i96s','7i76e','7i98'): raise ValueError('不支持的Mesa型号')
    ipaddress.IPv4Address(address)
    if sserial:
        if os.name != 'posix': raise RuntimeError('Smart Serial扫描请在Debian/LinuxCNC停机后执行')
        if subprocess.run(['pgrep','-x','milltask'],capture_output=True).returncode == 0:
            raise RuntimeError('LinuxCNC正在运行；请先退出再扫描Smart Serial')
    base = ['mesaflash','--device',board,'--addr',address]
    text = run(base+['--readhmid'])
    result = parse(text)
    result.update(board=board,address=address)
    if sserial:
        try:
            result['sserial_raw'] = run(base+['--sserial'],60)
        except (subprocess.TimeoutExpired, RuntimeError) as exc:
            if isinstance(exc, subprocess.TimeoutExpired):
                message = 'Smart Serial扫描60秒超时；主卡读取成功，从板尚未确认。'
                partial = exc.stdout or ''
                if isinstance(partial, bytes):partial = partial.decode('utf-8', errors='replace')
            else:
                message = 'Smart Serial扫描失败；主卡读取成功，从板尚未确认：' + str(exc)
                partial = ''
            result['sserial_raw'] = partial
            result['sserial_error'] = message + ' 请检查SD板供电、TX/RX接线及通道；Boot维护状态不等于可扫描的业务应用。扫描可能已改变端口状态，恢复运行前重新启动LinuxCNC。'
    return result


def live_hal():
    return run(['halcmd','show','pin'])


def read_custom_pins(board,address,indices):
    """Read firmware descriptors only; no Smart Serial scan or maintenance takeover.

    mesaflash reads the descriptor table as a whole so module counts and pin
    functions come from the same snapshot. Only requested pins are returned in
    custom_pins; full descriptors remain available for board wiring validation.
    """
    if not indices or len(set(indices))!=len(indices) or any(type(i) is not int or not 0<=i<256 for i in indices):
        raise ValueError('自定义引脚编号无效')
    result=discover(board,address,sserial=False)
    pins={p['io']:p for p in result['pins']}
    missing=[i for i in indices if i not in pins]
    if missing:raise ValueError('固件记录中缺少自定义引脚：'+','.join(map(str,missing)))
    result['custom_pins']=[pins[i] for i in indices]
    return result
