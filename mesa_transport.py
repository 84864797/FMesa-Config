"""Ethernet LBP16 → HostMot2 SSLBP → SD远程LBP邮箱。不是原版setsserial烧录格式。"""
import ipaddress
import socket
import struct
import time


class RemoteError(RuntimeError): pass


class Ethernet:
    def __init__(self,address,timeout=2):
        ipaddress.IPv4Address(address)
        self.socket=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
        self.socket.settimeout(timeout);self.socket.connect((address,27181));self.dead=False

    def exchange(self,packet,size):
        if self.dead:raise RuntimeError('LBP16 connection is unusable after a timeout; reconnect')
        try:
            self.socket.send(packet);data=self.socket.recv(2048)
            if len(data)!=size:raise ValueError('LBP16 reply length mismatch')
            return data
        except (OSError,ValueError):
            self.dead=True;self.socket.close();raise

    def read(self,address,size=4):
        if address%4 or size%4 or not 0<size<=508 or not 0<=address<=65536-size:raise ValueError('Invalid HostMot2 read range')
        return self.exchange(struct.pack('<HH',0x4280|size//4,address),size)

    def read32(self,address):return struct.unpack('<I',self.read(address))[0]

    def write32(self,address,value):
        if address%4 or not 0<=address<=65532:raise ValueError('Invalid HostMot2 write address')
        # 写和cookie读在同一个UDP包，读回作为顺序屏障；超时绝不自动重发写。
        p=struct.pack('<HHIHH',0xc201,address,value,0x4201,0x100)
        if self.exchange(p,4)!=struct.pack('<I',0x55aacafe):
            self.dead=True;self.socket.close();raise ValueError('HostMot2 cookie changed')

    def close(self):self.socket.close()


def layout(bus):
    if bus.read32(0x100)!=0x55aacafe or bus.read(0x104,8)!=b'HOSTMOT2':raise ValueError('Not HostMot2 firmware')
    at=bus.read32(0x10c)
    if at%4 or not 0x100<=at<=0xf000:raise ValueError('Invalid IDROM address')
    data=struct.unpack('<III8s11I',bus.read(at,64))
    port_count,port_width=data[6],data[8]
    if data[0] not in (2,3) or not 1<=port_count<=8 or not 1<=port_width<=32 or data[7]!=port_count*port_width:raise ValueError('Unsupported IDROM layout')
    modules={}
    for i in range(32):
        tag,version,clock,count,base,regs,strides,bitmap=struct.unpack('<BBBBHBBI',bus.read(at+data[1]+12*i,12))
        if tag==0:break
        if strides&15 not in (0,1):raise ValueError('Unsupported register stride selector')
        modules[tag]={'base':base,'version':version,'count':count,'stride':data[13+(strides&15)]}
    if 0xc1 not in modules or 3 not in modules:raise ValueError('SSerial or GPIO module missing')
    ss=modules[0xc1]
    if ss['stride']!=0x100:raise ValueError('This bridge requires classic SSLBP with 0x100 register stride')
    pins=[]
    for i in range(port_count*port_width):
        secpin,tag,unit,primary=bus.read(at+data[2]+4*i,4)
        pins.append((secpin,tag,unit,primary))
    return {'board':data[3].decode('ascii',errors='replace').strip('\0 '),'ports':port_count,'width':port_width,'modules':modules,'pins':pins}


class SmartSerial:
    """仅串口0；独占维护模式，完成后需重新启动LinuxCNC恢复运动配置。"""
    def __init__(self,bus,channel,emit=lambda _:None):
        if not 0<=channel<8:raise ValueError('Channel must be 0..7')
        self.bus=bus;self.channel=channel;self.emit=emit;self.info=layout(bus)
        self.base=self.info['modules'][0xc1]['base'];self.mask=1<<channel;self.prepared=False

    def wait(self,seconds=3):
        deadline=time.monotonic()+seconds
        while self.bus.read32(self.base):
            if time.monotonic()>deadline:raise TimeoutError('SSLBP command did not clear; no automatic command retry')
            time.sleep(.001)

    def command(self,value,seconds=3):
        self.bus.write32(self.base,value);self.wait(seconds)
        result=self.bus.read32(self.base+0x100)
        if result&self.mask:raise RemoteError(f'SSLBP remote error, status 0x{result:08x}')
        return result

    def local(self,address):
        if not 0<=address<0x800:raise ValueError('Invalid SSLBP local address')
        self.bus.write32(self.base,0x2000|address);self.wait()
        return self.bus.read32(self.base+0x100)&255

    def interface_layout(self):
        """ROM43 uses byte start/stride at 4/5; ROM46 uses u16 start at 4/5."""
        revision, minor = self.local(2), self.local(3)
        if revision != 1 or minor not in (43, 46):
            raise ValueError(f'Unsupported SSLBP: revision={revision}, ROM={minor}; supported: 1.43, 1.46')
        if self.local(0) != 0x12 or not self.channel < self.local(1) <= 8:
            raise ValueError('Unsupported SSLBP interface type/width')
        if minor == 43:
            start, stride, baud_offset = self.local(4), self.local(5), 42
            if start < 8 or stride < baud_offset + 4 or start + 8 * stride > 0x800:
                raise ValueError('Invalid ROM43 channel table layout')
        else:
            start, stride, baud_offset = self.local(4) | (self.local(5) << 8), self.local(6), 0x38
            if (start, stride) != (0x400, 0x40):
                raise ValueError('Unexpected ROM46 channel table layout')
        baud = sum(self.local(start + stride*self.channel + baud_offset+i) << (8*i) for i in range(4))
        if not 2400000 <= baud <= 2600000:
            raise ValueError(f'SSLBP baud {baud} is incompatible; expected approximately 2.5 Mbaud')
        result = dict(revision=revision, rom=minor, start=start, stride=stride, baud=baud)
        self.emit(f'SSLBP {revision}.{minor}: channel table=0x{start:x}, stride={stride}, baud={baud}')
        return result

    def prepare(self):
        info=self.info;gpio=info['modules'][3]['base'];width=info['width']
        selected=[(i,p) for i,p in enumerate(info['pins']) if p[1]==0xc1 and p[2]==0 and p[0]&15==self.channel+1]
        if not any(p[0]&0x80 for _,p in selected) or not any(not p[0]&0x80 for _,p in selected):raise ValueError('Selected Smart Serial channel has no complete TX/RX pin pair')
        # 维护接管前将所有GPIO置输入、清除复用，避免保留上次运动配置的输出。
        self.prepared=True
        for port in range(info['ports']):
            self.bus.write32(gpio+0x100+port*4,0)
            self.bus.write32(gpio+0x200+port*4,0)
        watchdog=info['modules'].get(2)
        if watchdog:
            self.bus.write32(watchdog['base'],0x80000000)
            self.bus.write32(watchdog['base']+0x100,0)
        for port in range(info['ports']):
            source=direction=0
            for i,p in selected:
                if i//width==port:
                    source|=1<<(i%width)
                    if p[0]&0x80:direction|=1<<(i%width)
            self.bus.write32(gpio+0x300+port*4,0)
            self.bus.write32(gpio+0x400+port*4,0)
            self.bus.write32(gpio+0x200+port*4,source)
            self.bus.write32(gpio+0x100+port*4,direction)
        self.bus.write32(self.base,0x48ff);self.bus.write32(self.base,0x8ff);self.wait(5)
        self.interface = self.interface_layout()
        baud = self.interface['baud']
        for ch in range(8):self.bus.write32(self.base+0x200+ch*4,0)
        self.command(0x0f00|self.mask,10)
        self.emit(f'Mesa {info["board"]}, channel {self.channel}, baud {baud}')

    def remote(self,address,size,data=None):
        if size not in (1,2,4,8) or not 0<=address<=65536-size:raise ValueError('Invalid remote access')
        code={1:0,2:1,4:2,8:3}[size]
        if data is not None and len(data)!=size:raise ValueError('Remote write size mismatch')
        cs=self.base+0x200+self.channel*4;rw=self.base+0x300+self.channel*4
        if data is not None:
            padded=data.ljust(8,b'\0');a,b=struct.unpack('<II',padded)
            self.bus.write32(rw,a)
            if size==8:self.bus.write32(rw+0x100,b)
        self.bus.write32(cs,((0x64 if data is not None else 0x44)|code)<<24|address)
        try:
            self.command(0x1000|self.mask)
            if data is None:
                answer=struct.pack('<I',self.bus.read32(rw))
                if size==8:answer+=struct.pack('<I',self.bus.read32(rw+0x100))
                return answer[:size]
        finally:
            # 不在传输已失效时继续发送任何写命令。
            if not getattr(self.bus,'dead',False):self.bus.write32(cs,0)

    def read(self,address,size):return self.remote(address,size)
    def write(self,address,data):return self.remote(address,len(data),data)

    def close(self):
        if self.prepared and not getattr(self.bus,'dead',False):
            try:
                self.bus.write32(self.base,0x8ff);self.wait(5)
                gpio=self.info['modules'][3]['base']
                for port in range(self.info['ports']):
                    self.bus.write32(gpio+0x100+port*4,0);self.bus.write32(gpio+0x200+port*4,0)
            finally:self.bus.close()
        else:self.bus.close()


def chunks(data):
    offset=0
    while offset<len(data):
        size=next(n for n in (8,4,2,1) if n<=len(data)-offset)
        yield offset,data[offset:offset+size];offset+=size


class MailboxClient:
    def __init__(self,remote,emit=lambda _:None):self.remote=remote;self.sequence=0;self.emit=emit
    def capability(self,board):
        value=self.remote.read(0x9000,8)
        if value[:6]!=b'SDUP\x01\x00' or value[6]!=board:raise ValueError('Mesa upgrade mailbox version/board ID mismatch')
        return value

    def call(self,opcode,payload=b''):
        from firmware_update import frame
        from f407_update import crc
        self.sequence=(self.sequence+1)&65535;request=frame(self.sequence,opcode,payload)
        if len(request)>300:raise ValueError('Request too large')
        for offset,block in chunks(request):self.remote.write(0x9100+offset,block)
        self.remote.write(0x9300,struct.pack('<H',len(request)))
        # 不让Mesa在F407单Bank长擦写时持续发串口请求。
        quiet=12 if opcode==2 else 30 if opcode in (5,6) else 0
        if quiet:self.emit(f'Flash busy: wait {quiet}s');time.sleep(quiet)
        deadline=time.monotonic()+120
        while True:
            try:status=self.remote.read(0x9008,4)
            except RemoteError:
                if time.monotonic()>=deadline:raise
                time.sleep(.2);continue
            busy,length=status[0],struct.unpack_from('<H',status,2)[0]
            if not busy and 14<=length<=300:break
            if time.monotonic()>=deadline:raise TimeoutError('Upgrade operation did not complete; writes will not be replayed')
            time.sleep(.1)
        answer=bytearray()
        for offset,block in chunks(bytes(length)):answer+=self.remote.read(0x9400+offset,len(block))
        if answer[:4]!=b'F4UP' or struct.unpack_from('<HB',answer,4)!=(self.sequence,opcode|0x80):raise ValueError('Upgrade reply sequence/opcode mismatch')
        declared=struct.unpack_from('<H',answer,7)[0]
        if declared+13!=len(answer) or struct.unpack_from('<I',answer,len(answer)-4)[0]!=crc(answer[:-4]):raise ValueError('Upgrade reply CRC/length mismatch')
        if answer[9]:raise RuntimeError(f'Bootloader operation {opcode} failed, status {answer[9]}')
        return bytes(answer[10:-4])
