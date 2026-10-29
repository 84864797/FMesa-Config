import json
import os
import struct
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch,MagicMock
from mesa_transport import Ethernet,SmartSerial,MailboxClient,layout,chunks
import mesa_update
from f407_update import package


def crc8(data):
    c=0
    for b in data:
        c^=b
        for _ in range(8):c=(c>>1)^0x8c if c&1 else c>>1
    return c


class FakeMesa:
    """只模拟HostMot2寄存器映射；实际LBP邮箱及Flash状态机由Rust联调器执行。"""
    def __init__(self,process=None):
        self.process=process;self.memory=bytearray(65536);self.status=0;self.writes=[];self.closed=False;self.dead=False
        self.memory[0x100:0x110]=struct.pack('<I8sI',0x55aacafe,b'HOSTMOT2',0x400)
        self.memory[0x400:0x440]=struct.pack('<III8s11I',3,0x40,0x100,b'MESA7I92',200,144,2,34,17,100000000,200000000,4,64,256,256)
        for i,(tag,base) in enumerate([(3,0x1000),(2,0xc00),(0xc1,0x5b00)]):
            self.memory[0x440+i*12:0x44c+i*12]=struct.pack('<BBBBHBBI',tag,0,1,1,base,6,0,0)
        self.memory[0x500+2*4:0x500+4*4]=bytes([1,0xc1,0,3,0x81,0xc1,0,3])
        self.locals={0:0x12,1:8,2:1,3:46,4:0,5:4,6:64,0x438:0xa0,0x439:0x25,0x43a:0x26,0x43b:0}

    def read(self,addr,size=4):
        if addr==0x5b00:return bytes(4)
        if addr==0x5c00:return struct.pack('<I',self.status)
        return bytes(self.memory[addr:addr+size])
    def read32(self,addr):return struct.unpack('<I',self.read(addr))[0]
    def write32(self,addr,value):
        self.writes.append((addr,value));self.memory[addr:addr+4]=struct.pack('<I',value)
        if addr!=0x5b00:return
        self.status=0
        if value&0x2000 and value&0x4000==0:self.status=self.locals.get(value&0x7ff,0)
        elif value==0x1001:
            cs=self.read32(0x5d00);command=cs>>24;address=cs&65535;size=1<<(command&3)
            raw=bytes([command])+struct.pack('<H',address)
            if command&0x20:raw+=self.read(0x5e00)+self.read(0x5f00) if size==8 else self.read(0x5e00)[:size]
            raw+=bytes([crc8(raw)])
            if self.process:
                self.process.stdin.write(raw.hex()+'\n');self.process.stdin.flush()
                line=self.process.stdout.readline();reply=bytes.fromhex(line.strip())
            else:reply=b''
            if not reply:self.status=1;return
            expected=1 if command&0x20 else size+1
            if len(reply)!=expected or crc8(reply[:-1])!=reply[-1]:raise AssertionError('Invalid Rust bridge reply')
            if not command&0x20:
                data=reply[:-1].ljust(8,b'\0');self.memory[0x5e00:0x5e04]=data[:4];self.memory[0x5f00:0x5f04]=data[4:8]
    def close(self):self.closed=True


class TransportTest(unittest.TestCase):
    def test_lbp16_packet_format(self):
        with patch('mesa_transport.socket.socket') as socket:
            s=socket.return_value;s.recv.side_effect=[bytes(8),struct.pack('<I',0x55aacafe)]
            b=Ethernet('10.10.10.10');b.read(0x104,8);b.write32(0x5b00,0x1001)
            self.assertEqual(s.send.call_args_list[0].args[0],bytes.fromhex('82420401'))
            self.assertEqual(s.send.call_args_list[1].args[0],struct.pack('<HHIHH',0xc201,0x5b00,0x1001,0x4201,0x100))

    def test_timeout_poisons_without_replay(self):
        with patch('mesa_transport.socket.socket') as socket:
            s=socket.return_value;s.recv.side_effect=TimeoutError()
            b=Ethernet('10.10.10.10')
            with self.assertRaises(TimeoutError):b.write32(0x5b00,1)
            with self.assertRaises(RuntimeError):b.read(0x100)
            self.assertEqual(s.send.call_count,1)

    def test_layout_and_prepare_use_rom46_offsets(self):
        b=FakeMesa();d=layout(b);self.assertEqual(d['ports'],2)
        ss=SmartSerial(b,0)
        with patch('mesa_transport.time.sleep'):ss.prepare()
        self.assertIn((0x1100,0),b.writes);self.assertIn((0x1100,8),b.writes)
        self.assertEqual(ss.local(0x438),0xa0);ss.close();self.assertTrue(b.closed)

    def test_unsupported_rom_reports_both_versions_before_remote_setup(self):
        b=FakeMesa();b.locals[2]=2;b.locals[3]=43
        messages=[];ss=SmartSerial(b,0,messages.append)
        try:
            with self.assertRaisesRegex(ValueError,'revision=2, ROM=43'):
                ss.prepare()
            self.assertNotIn((ss.base,0x0f01),b.writes)
        finally:ss.close()

    def test_rom43_layout_and_setup(self):
        b=FakeMesa();b.locals.update({3:43,4:112,5:50,6:216,7:1})
        for i,v in enumerate(struct.pack('<I',2500000)):b.locals[112+42+i]=v
        ss=SmartSerial(b,0)
        try:
            ss.prepare()
            self.assertEqual(ss.interface,dict(revision=1,rom=43,start=112,stride=50,baud=2500000))
            self.assertIn((ss.base,0x0f01),b.writes)
            self.assertNotIn((ss.base,0x2438),b.writes)
        finally:ss.close()

    def test_rom43_channel_stride_and_invalid_layout_or_baud(self):
        b=FakeMesa();b.locals.update({3:43,4:112,5:50})
        for i,v in enumerate(struct.pack('<I',2500000)):b.locals[112+7*50+42+i]=v
        ss=SmartSerial(b,7)
        self.assertEqual(ss.interface_layout()['baud'],2500000)
        b.locals[5]=20
        with self.assertRaisesRegex(ValueError,'ROM43 channel table'):ss.interface_layout()
        b.locals[5]=50;b.locals[112+7*50+42+2]=0
        with self.assertRaisesRegex(ValueError,'baud'):ss.interface_layout()
        ss.close()

    def test_mailbox_sequence_crc_and_chunk_sizes(self):
        self.assertEqual([len(b) for _,b in chunks(bytes(15))],[8,4,2,1])
        from f407_update import frame
        remote=MagicMock();response=frame(1,0x81,b'\0hello')
        remote.read.side_effect=[bytes([0,0,len(response),0]),*[response[i:i+len(b)] for i,b in chunks(response)]]
        self.assertEqual(MailboxClient(remote).call(1),b'hello')
        self.assertEqual(remote.write.call_args_list[-1].args[0],0x9300)

    def test_wrong_package_never_connects(self):
        with tempfile.TemporaryDirectory() as tmp,patch('mesa_update.Ethernet') as ethernet:
            p=Path(tmp)/'x.fwup';p.write_bytes(package(struct.pack('<II',0x2001fff0,0x08020009)+b'x'*32,1,5))
            with self.assertRaises(ValueError):mesa_update.deploy(p,'10.10.10.10',0,'SD02')
            ethernet.assert_not_called()

    @unittest.skipUnless(os.environ.get('MESA_BRIDGE_SIM'),'Build Rust bridge sim and set MESA_BRIDGE_SIM for integration')
    def test_python_to_real_rust_upgrade_state_machine(self):
        process=subprocess.Popen([os.environ['MESA_BRIDGE_SIM']],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        try:
            bus=FakeMesa(process)
            with tempfile.TemporaryDirectory() as tmp,patch.object(Path,'home',return_value=Path(tmp)),patch('mesa_update.idle_check'),patch('mesa_update.Ethernet',return_value=bus),patch('mesa_transport.time.sleep'),patch('mesa_update.time.sleep'):
                p=Path(tmp)/'x.fwup';p.write_bytes(package(struct.pack('<II',0x2001fff0,0x08020009)+b'x'*600,1,5))
                result=mesa_update.deploy(p,'10.10.10.10',0,'SD01',lambda _:None)
                self.assertEqual(result['result'],'PASS');self.assertEqual(result['confirmed']['active_version'],5);self.assertEqual(result['confirmed']['phase'],6)
                self.assertTrue(bus.closed)
        finally:
            process.stdin.close();process.wait(timeout=5);process.stdout.close();process.stderr.close()


if __name__=='__main__':unittest.main()
