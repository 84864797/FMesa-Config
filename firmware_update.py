"""SD板串口升级流程；包校验先于串口打开，确认版本后才报告成功。"""
import json
import struct
import sys
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent/'updater'))
from f407_update import Client, unpack, frame
from serial_backend import Transport, FrameReader, SessionLog, decode_status


def inspect(path):
    info, image = unpack(Path(path).read_bytes())
    return dict(zip(('board_id','version','bytes','crc32'), info))


def capture(port, board, seconds, log, emit):
    transport = Transport(port, log=log)
    reader = FrameReader(); sequence = 0; next_send = 0; deadline = time.monotonic()+seconds
    try:
        emit('等待维护握手：请给板卡断电约2秒，再上电。')
        while time.monotonic() < deadline:
            now = time.monotonic()
            if now >= next_send:
                sequence = (sequence+1)&65535
                transport.write(frame(sequence,1,b'')); next_send = now+.2
            for seq, op, body in reader.feed(transport.read_some()):
                if 1 <= seq <= sequence and op == 0x81 and len(body)==14 and body[0]==0:
                    status = decode_status(body[1:])
                    if status['board_id'] != board: raise ValueError('实际Bootloader板型与升级包不符，停止升级')
                    return status
        raise TimeoutError('维护握手超时；请核对串口、Bootloader和差分接线')
    finally: transport.close()


def deploy(path, port, model, emit=print):
    pkg = Path(path).read_bytes(); info, image = unpack(pkg)
    expected = {'SD01':1,'SD02':2}[model]
    if info[0] != expected: raise ValueError('升级包与选择的板型不符，未打开串口')
    directory = Path.home()/'.local/state/mesa-sd-tool'; directory.mkdir(parents=True,exist_ok=True)
    log = SessionLog(directory/(time.strftime('upgrade-%Y%m%d-%H%M%S')+'.jsonl'))
    before = capture(port,expected,120,log,emit)
    if before['phase'] not in (0,1,2,6): raise RuntimeError('板卡存在待处理安装/试运行，请先检查状态')
    if len(image) > before['max_image_bytes']: raise ValueError('镜像超过目标容量')
    transport = Transport(port,log=log)
    try:
        client = Client(transport,15)
        emit('准备暂存区…');client.call(2,struct.pack('<4I',*info))
        for offset in range(0,len(image),256):
            client.call(3,struct.pack('<I',offset)+image[offset:offset+256])
            emit(f'上传 {min(offset+256,len(image))*100//len(image)}%')
        emit('整镜像CRC校验…');client.call(4)
        emit('备份旧应用并安装…');client.call(5)
        installed = decode_status(client.call(1))
        if installed['phase']!=5 or installed['active_version']!=info[1]: raise RuntimeError('安装后状态或版本错误')
        client.call(7)
    finally: transport.close()
    emit('试启动已应答，等待应用确认…')
    confirmed = capture(port,expected,25,log,lambda _:None)
    if confirmed['phase']!=6 or confirmed['active_version']!=info[1]:
        raise RuntimeError('新固件未确认，可能已回退：'+json.dumps(confirmed,ensure_ascii=False))
    transport = Transport(port,log=log)
    try: Client(transport,15).call(7)
    finally: transport.close()
    emit(f'成功：版本{info[1]}已确认并启动。串口已释放；Mesa业务需接回验证。')
    return {'before':before,'confirmed':confirmed,'log':str(log.path)}
