"""First-stage laboratory UART updater, not a Mesa/setsserial adapter. Standard library only."""
import argparse,os,select,struct,time,zlib
from pathlib import Path
MAGIC=b'F407UP01';BASE=0x08020000;LIMIT=128*1024
def crc(data):return zlib.crc32(data)&0xffffffff
def check_image(image):
    if not 8<=len(image)<=LIMIT:raise ValueError('Image must be 8..131072 bytes')
    stack,entry=struct.unpack_from('<II',image)
    if not (0x20000000<=stack<=0x2001fff0 and stack%8==0 and entry&1 and BASE+8<=entry&~1<BASE+len(image)):
        raise ValueError('Invalid vector table: requires application linked at 0x08020000; old raw BIN is rejected')
def package(image,board,version):
    check_image(image)
    if board not in (1,2):raise ValueError('Unknown board')
    header=struct.pack('<8s6I',MAGIC,board,version,len(image),crc(image),BASE,1)
    return header+struct.pack('<I',crc(header))+image
def unpack(data):
    if len(data)<36:raise ValueError('Short package')
    magic,board,version,length,checksum,base,fmt,header_crc=struct.unpack_from('<8s7I',data)
    if magic!=MAGIC or base!=BASE or fmt!=1 or board not in (1,2) or header_crc!=crc(data[:32]):raise ValueError('Invalid package header')
    image=data[36:]
    if len(image)!=length or crc(image)!=checksum:raise ValueError('Image length/CRC mismatch')
    check_image(image);return (board,version,length,checksum),image
def frame(seq,op,payload):
    if len(payload)>287:raise ValueError('Frame too large')
    raw=b'F4UP'+struct.pack('<HBH',seq,op,len(payload))+payload
    return raw+struct.pack('<I',crc(raw))
class TTY:
    def __init__(self,path):
        if os.name!='posix':raise RuntimeError('UART upload backend currently supports Linux only')
        import termios
        self.termios=termios;self.fd=os.open(path,os.O_RDWR|os.O_NOCTTY|os.O_NONBLOCK);self.old=termios.tcgetattr(self.fd)
        attrs=termios.tcgetattr(self.fd);attrs[0]=0;attrs[1]=0;attrs[2]=termios.CLOCAL|termios.CREAD|termios.CS8;attrs[3]=0;attrs[4]=termios.B115200;attrs[5]=termios.B115200;attrs[6][termios.VMIN]=0;attrs[6][termios.VTIME]=0
        termios.tcsetattr(self.fd,termios.TCSANOW,attrs);termios.tcflush(self.fd,termios.TCIOFLUSH)
    def read(self,n,deadline):
        out=bytearray()
        while len(out)<n:
            left=deadline-time.monotonic()
            if left<=0:raise TimeoutError('No upgrade reply; no automatic retransmit. Reconnect and restart BEGIN if interrupted')
            if select.select([self.fd],[],[],left)[0]:out.extend(os.read(self.fd,n-len(out)))
        return bytes(out)
    def write(self,data):
        deadline=time.monotonic()+15
        while data:
            left=deadline-time.monotonic()
            if left<=0:raise TimeoutError('UART transmit timeout')
            if select.select([],[self.fd],[],left)[1]:
                try:n=os.write(self.fd,data)
                except BlockingIOError:continue
                data=data[n:]
    def close(self):
        try:self.termios.tcsetattr(self.fd,self.termios.TCSANOW,self.old)
        finally:os.close(self.fd)
class Client:
    def __init__(self,port,timeout=15):self.port=port;self.timeout=timeout;self.sequence=0
    def call(self,op,payload=b''):
        self.sequence=(self.sequence+1)&65535;self.port.write(frame(self.sequence,op,payload));deadline=time.monotonic()+self.timeout
        magic=b''
        while magic!=b'F4UP':magic=(magic+self.port.read(1,deadline))[-4:]
        rest=self.port.read(5,deadline);seq,reply_op,length=struct.unpack('<HBH',rest)
        if length>287:raise ValueError('Oversized reply')
        body=self.port.read(length+4,deadline)
        if seq!=self.sequence or reply_op!=op|0x80 or struct.unpack('<I',body[-4:])[0]!=crc(magic+rest+body[:-4]):raise ValueError('Invalid reply sequence/op/CRC')
        if not body[:-4] or body[0]:raise RuntimeError(f'Bootloader rejected operation {op}: status {body[0] if length else "missing"}')
        return body[1:-4]
def upload(client,pkg,reboot=True):
    info,image=unpack(pkg);hello=client.call(1)
    if len(hello)!=13:raise ValueError('Invalid HELLO')
    phase,board,limit,version=struct.unpack('<BIII',hello)
    if board!=info[0] or info[2]>limit:raise ValueError('Target board/size mismatch')
    if phase not in (0,1,2,6):raise RuntimeError('Target has pending install/trial; inspect or reboot before a new upload')
    client.call(2,struct.pack('<4I',*info))
    for offset in range(0,len(image),256):client.call(3,struct.pack('<I',offset)+image[offset:offset+256])
    client.call(4);client.call(5)
    if reboot:client.call(7)
    return version,info[1]
def open_transport(path):
    if os.name == 'nt':
        from serial_backend import Transport
        return Transport(path)
    return TTY(path)

def main():
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='command',required=True)
    p=sub.add_parser('pack');p.add_argument('image',type=Path);p.add_argument('output',type=Path);p.add_argument('--board',choices=['mpg','io16'],required=True);p.add_argument('--version',type=int,required=True)
    p=sub.add_parser('inspect');p.add_argument('package',type=Path)
    p=sub.add_parser('upload');p.add_argument('package',type=Path);p.add_argument('--port',required=True);p.add_argument('--timeout',type=float,default=15);p.add_argument('--no-reboot',action='store_true')
    for name in ['status','reboot','rollback']:
        p=sub.add_parser(name);p.add_argument('--port',required=True);p.add_argument('--timeout',type=float,default=15)
    args=parser.parse_args()
    if args.command=='pack':args.output.write_bytes(package(args.image.read_bytes(),{'mpg':1,'io16':2}[args.board],args.version));print('Package written:',args.output)
    elif args.command=='inspect':print(dict(zip(['board','version','length','crc32'],unpack(args.package.read_bytes())[0])))
    elif args.command=='upload':
        pkg=args.package.read_bytes();unpack(pkg);tty=open_transport(args.port)
        try:old,new=upload(Client(tty,args.timeout),pkg,not args.no_reboot);print(f'Transfer/install complete: {old} -> {new}; real application trial confirmation still requires successful reboot')
        finally:tty.close()
    else:
        tty=open_transport(args.port)
        try:
            client=Client(tty,args.timeout)
            if args.command=='status':print(dict(zip(['phase','board','max_image','active_version'],struct.unpack('<BIII',client.call(1)))))
            else:client.call({'rollback':6,'reboot':7}[args.command]);print('Command accepted')
        finally:tty.close()
if __name__=='__main__':main()
