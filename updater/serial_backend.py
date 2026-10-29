"""共享串口后端：Windows/Linux、日志、Bootloader只读状态。"""
import json
import queue
import re
import struct
import threading
import time
from datetime import datetime
from pathlib import Path

import serial
from serial.tools import list_ports
from f407_update import crc, frame

PHASES = {0: "空应用 / 等待升级", 1: "接收暂存中", 2: "镜像校验完成", 3: "备份旧应用中", 4: "安装中", 5: "等待试启动确认", 6: "已确认应用", 7: "回退中"}
BOARDS = {1: "MPG", 2: "16出16进"}
ERRORS = {1: "Flash操作失败", 2: "长度或范围非法", 3: "当前状态不允许", 4: "板型不匹配", 5: "CRC/完整性失败", 6: "应用向量非法", 7: "分片顺序错误", 8: "元数据空间已满"}

def ports():
    """只枚举，不打开端口，不发探测数据。"""
    return [{"port": p.device, "description": p.description, "vid": p.vid, "pid": p.pid} for p in list_ports.comports()]

def hex_bytes(text):
    text = re.sub(r"(?i)0x", "", text)
    text = re.sub(r"[\s,:_-]+", "", text)
    if not text or len(text) % 2 or not re.fullmatch(r"[0-9a-fA-F]+", text):
        raise ValueError("HEX格式不正确，例如：46 34 55 50；每个字节必须两位")
    data = bytes.fromhex(text)
    if len(data) > 512:
        raise ValueError("单次调试发送最多512字节")
    return data

class SessionLog:
    def __init__(self, path=None):
        self.path = Path(path) if path else Path(__file__).resolve().parent / "logs" / (datetime.now().strftime("serial-%Y%m%d-%H%M%S-%f") + ".jsonl")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.Lock()

    def write(self, kind, **data):
        event = {"time": datetime.now().astimezone().isoformat(timespec="milliseconds"), "kind": kind, **data}
        with self.lock:
            with self.path.open("a", encoding="utf-8") as out:
                out.write(json.dumps(event, ensure_ascii=False) + "\n")
        return event

class Transport:
    """DTR/RTS在打开前设定，默认不主动拉高；没有升级或自动探测行为。"""
    def __init__(self, port, baud=115200, dtr=False, rts=False, log=None):
        self.log = log
        self.ser = serial.serial_for_url(port, do_not_open=True)
        self.ser.baudrate = baud
        self.ser.bytesize = serial.EIGHTBITS
        self.ser.parity = serial.PARITY_NONE
        self.ser.stopbits = serial.STOPBITS_ONE
        self.ser.timeout = 0.05
        self.ser.write_timeout = 2
        self.ser.xonxoff = self.ser.rtscts = self.ser.dsrdtr = False
        self.ser.dtr, self.ser.rts = dtr, rts
        self.ser.open()
        if self.log: self.log.write("connected", port=port, baud=baud, framing="8N1", dtr=dtr, rts=rts)

    def write(self, data):
        count = self.ser.write(data)
        if count != len(data): raise IOError("串口只发送了部分数据")
        if self.log: self.log.write("tx", hex=data.hex(" ").upper(), bytes=len(data))

    def read_some(self):
        data = self.ser.read(min(1024, max(1, self.ser.in_waiting)))
        if data and self.log: self.log.write("rx", hex=data.hex(" ").upper(), bytes=len(data))
        return data

    def read(self, size, deadline):
        """适配现有Bootloader Client；总截止时间不会被零星字节延长。"""
        data = bytearray()
        while len(data) < size:
            if time.monotonic() >= deadline: raise TimeoutError("未收到完整回复：检查接线、端口及Bootloader是否运行")
            chunk = self.ser.read(size - len(data))
            if chunk:
                data.extend(chunk)
                if self.log: self.log.write("rx", hex=chunk.hex(" ").upper(), bytes=len(chunk))
        return bytes(data)

    def close(self):
        if self.ser.is_open:
            self.ser.close()
            if self.log: self.log.write("disconnected")

def decode_status(payload, elapsed_ms=None):
    if len(payload) != 13: raise ValueError(f"HELLO状态长度应为13，实际{len(payload)}")
    phase, board, maximum, version = struct.unpack("<BIII", payload)
    result = {"phase": phase, "phase_name": PHASES.get(phase, "未知状态"), "board_id": board, "board_name": BOARDS.get(board, "未知板型"), "max_image_bytes": maximum, "active_version": version}
    if elapsed_ms is not None: result["round_trip_ms"] = round(elapsed_ms, 3)
    return result

class FrameReader:
    """流式接收：分片、粘包、噪声及坏CRC后重新寻找F4UP，缓存有界。"""
    def __init__(self):
        self.buffer = bytearray()
        self.crc_errors = self.length_errors = 0
    def feed(self, data):
        self.buffer.extend(data)
        if len(self.buffer) > 4096: del self.buffer[:-4096]
        result = []
        while True:
            at = self.buffer.find(b"F4UP")
            if at < 0:
                self.buffer[:] = self.buffer[-3:]
                break
            if at: del self.buffer[:at]
            if len(self.buffer) < 9: break
            seq, op, length = struct.unpack_from("<HBH", self.buffer, 4)
            if length > 287:
                self.length_errors += 1
                del self.buffer[0]
                continue
            n = length + 13
            if len(self.buffer) < n: break
            raw = bytes(self.buffer[:n])
            if crc(raw[:-4]) != struct.unpack("<I", raw[-4:])[0]:
                self.crc_errors += 1
                del self.buffer[0]
                continue
            del self.buffer[:n]
            result.append((seq, op, raw[9:-4]))
        return result

class Worker(threading.Thread):
    """工作线程独占串口；UI只发命令、收事件，不在主线程阻塞。"""
    def __init__(self, port, baud, commands, events, log, dtr=False, rts=False, factory=Transport, timeout=3):
        super().__init__(daemon=True)
        self.port, self.baud, self.commands, self.events, self.log = port, baud, commands, events, log
        self.dtr, self.rts, self.factory, self.timeout = dtr, rts, factory, timeout
        self.stopping = threading.Event()
    def event(self, kind, **data):
        self.events.put(self.log.write(kind, **data))
    def run(self):
        transport = None
        pending = None
        sequence = 0
        reader = FrameReader()
        try:
            transport = self.factory(self.port, self.baud, self.dtr, self.rts)
            self.event("connected", port=self.port, baud=self.baud, framing="8N1", dtr=self.dtr, rts=self.rts)
            while not self.stopping.is_set():
                # 每轮限制命令数，避免大量发送操作饿死接收及超时检查。
                for _ in range(4):
                    try: command = self.commands.get_nowait()
                    except queue.Empty: break
                    if command[0] == "stop": self.stopping.set(); break
                    if pending:
                        self.event("notice", message="状态查询尚未完成，忽略本次发送")
                        continue
                    if command[0] == "status":
                        sequence = (sequence + 1) & 65535
                        data = frame(sequence, 1, b"")
                        started = time.monotonic()
                        pending = (sequence, started, started + self.timeout, command[1] if len(command)>1 else None)
                    elif command[0] == "raw": data = command[1]
                    else: continue
                    transport.write(data)
                    self.event("tx", hex=data.hex(" ").upper(), bytes=len(data))
                if self.stopping.is_set(): break
                data = transport.read_some()
                if data:
                    self.event("rx", hex=data.hex(" ").upper(), bytes=len(data))
                    previous = (reader.crc_errors, reader.length_errors)
                    frames = reader.feed(data)
                    if reader.crc_errors > previous[0]: self.event("error", message="收到 F4UP 帧，但 CRC32 校验失败，已丢弃并重新同步")
                    if reader.length_errors > previous[1]: self.event("error", message="收到非法帧长度，已丢弃并重新同步")
                    for seq, op, body in frames:
                        if pending and seq == pending[0] and op == 0x81:
                            elapsed = (time.monotonic() - pending[1]) * 1000
                            request_id = pending[3]
                            pending = None
                            if not body: self.event("error", message="状态回复缺少状态码")
                            elif body[0]: self.event("error", message=ERRORS.get(body[0], f"设备错误码{body[0]}"))
                            else: self.event("status", request_id=request_id, **decode_status(body[1:], elapsed))
                        else: self.event("frame", sequence=seq, opcode=op, payload=body.hex(" ").upper())
                if pending and time.monotonic() >= pending[2]:
                    request_id = pending[3]
                    pending = None
                    self.event("error", request_id=request_id, message="状态查询超时，未自动重发；检查四线交叉接线、波特率及维护模式")
        except Exception as exc: self.event("error", message=str(exc))
        finally:
            if transport:
                try: transport.close()
                except Exception: pass
            self.event("disconnected")
