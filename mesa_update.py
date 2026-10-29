"""通过Mesa以太网与Smart Serial升级SD板；不访问USB串口。"""
import argparse
import json
import os
import re
import shutil
import struct
import subprocess
import time
from pathlib import Path
from firmware_update import inspect
from f407_update import unpack
from serial_backend import decode_status
from mesa_transport import Ethernet, SmartSerial, MailboxClient, RemoteError, layout


def idle_check():
    if os.name!='posix':raise RuntimeError('正式Mesa升级请在Debian/LinuxCNC电脑运行；Windows可离线测试界面')
    if subprocess.run(['pgrep','-x','milltask'],capture_output=True).returncode==0:
        raise RuntimeError('LinuxCNC正在运行，请退出后升级')
    if shutil.which('halcmd'):
        result=subprocess.run(['halcmd','show','comp'],capture_output=True,text=True,timeout=5)
        if 'hm2_eth' in result.stdout or 'hostmot2' in result.stdout or re.search(r'\bhm2_',result.stdout):
            raise RuntimeError('HAL仍加载Mesa驱动，请退出相关HAL会话后升级')


def wait_boot(remote,board,seconds,emit):
    client=MailboxClient(remote,emit);deadline=time.monotonic()+seconds
    while time.monotonic()<deadline:
        try:client.capability(board);return client
        except RemoteError:time.sleep(.1)
    raise TimeoutError('未找到Mesa升级Bootloader。旧Boot V2不支持转发，需要先通过SWD安装匹配的新Boot。')


def deploy(path,address,channel,model,emit=print):
    pkg=Path(path).read_bytes();info,image=unpack(pkg)
    board={'SD01':1,'SD02':2}[model]
    if info[0]!=board:raise ValueError('升级包与目标SD型号不符，未连接Mesa')
    idle_check()
    bus=Ethernet(address)
    try:remote=SmartSerial(bus,channel,emit)
    except Exception:bus.close();raise
    result={'transport':'Ethernet-LBP16/SSLBP/LBP-mailbox','address':address,'channel':channel,'model':model,'new_version':info[1]}
    try:
        emit('接管Mesa维护链路：非串口GPIO将置为输入；完成后重新启动LinuxCNC恢复配置。')
        remote.prepare()
        result['sslbp']=remote.interface
        try:
            already=remote.read(0x9000,8)
        except RemoteError:already=None
        if already is None:
            try:app=remote.read(0x43e0,8)
            except RemoteError:app=None
            if app and app[:6]==b'SDAP\x01\x00':
                time.sleep(.05)
                emit('请求SD应用关闭输出并进入维护Boot…');remote.write(0x43f0,struct.pack('<I',0x4d455341))
            else:
                emit('当前应用没有远程维护入口。请仅给SD板断电约2秒再上电，Mesa保持供电。')
        client=wait_boot(remote,board,120,emit)
        before=decode_status(client.call(1));result['before']=before
        if before['board_id']!=board or len(image)>before['max_image_bytes']:raise ValueError('实际目标板型/容量与镜像不符')
        if before['phase'] not in (0,1,2,6):raise RuntimeError('目标存在未完成试运行或安装，停止新升级')
        emit('准备暂存区…');client.call(2,struct.pack('<4I',*info))
        for offset in range(0,len(image),256):
            client.call(3,struct.pack('<I',offset)+image[offset:offset+256]);emit(f'上传 {min(offset+256,len(image))*100//len(image)}%')
        emit('整镜像CRC校验…');client.call(4)
        emit('备份旧应用并安装…');client.call(5)
        installed=decode_status(client.call(1));result['installed']=installed
        if installed['phase']!=5 or installed['active_version']!=info[1]:raise RuntimeError('安装状态/版本不符')
        emit('试启动已准备，等待应用确认…');client.call(7)
        time.sleep(.15)
        client=wait_boot(remote,board,30,emit);confirmed=decode_status(client.call(1));result['confirmed']=confirmed
        if confirmed['phase']!=6 or confirmed['active_version']!=info[1]:
            if confirmed['phase']==6:
                client.call(7);emit('新应用未确认，已启动回退版本。')
            raise RuntimeError('升级未确认：'+json.dumps(confirmed,ensure_ascii=False))
        client.call(7);result['result']='PASS'
        emit(f'成功：版本{info[1]}已确认并启动。请重新启动LinuxCNC恢复板卡配置。')
        return result
    except Exception as exc:
        result['result']='FAIL';result['error']=str(exc);raise
    finally:
        try:remote.close()
        except Exception as cleanup:
            result['cleanup_error']=str(cleanup);emit('Mesa清理失败：'+str(cleanup))
        directory=Path.home()/'.local/state/mesa-sd-tool';directory.mkdir(parents=True,exist_ok=True)
        (directory/('mesa-'+time.strftime('%Y%m%d-%H%M%S')+'.json')).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')


def probe(address):
    bus=Ethernet(address)
    try:
        d=layout(bus);return {'board':d['board'],'ports':d['ports'],'port_width':d['width'],'modules':d['modules']}
    finally:bus.close()


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--ip',required=True);p.add_argument('--probe',action='store_true')
    p.add_argument('--package',type=Path);p.add_argument('--channel',type=int,default=0);p.add_argument('--model',choices=['SD01','SD02'],default='SD01')
    a=p.parse_args()
    if a.probe:result=probe(a.ip)
    elif a.package:result=deploy(a.package,a.ip,a.channel,a.model,lambda s:print(s,flush=True))
    else:p.error('--probe or --package is required')
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
