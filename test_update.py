import struct
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import firmware_update as fw
from f407_update import package


class UpdateTest(unittest.TestCase):
    def prepare(self,confirmed):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);root=Path(temp.name)
        p=root/'app.fwup';p.write_bytes(package(struct.pack('<II',0x2001fff0,0x08020009)+b'x'*600,1,4))
        self.enterContext(patch.object(Path,'home',return_value=root))
        capture=self.enterContext(patch.object(fw,'capture',side_effect=[{'phase':6,'active_version':3,'max_image_bytes':131072},confirmed]))
        transport=self.enterContext(patch.object(fw,'Transport'))
        client=self.enterContext(patch.object(fw,'Client'))
        client.return_value.call.return_value=struct.pack('<BIII',5,1,131072,4)
        return p,capture,transport,client

    def test_confirmation_then_final_start(self):
        p,cap,transport,client=self.prepare({'phase':6,'active_version':4})
        messages=[];result=fw.deploy(p,'test','SD01',messages.append)
        ops=[c.args[0] for c in client.return_value.call.call_args_list]
        self.assertEqual(ops,[2,3,3,3,4,5,1,7,7]);self.assertEqual(result['confirmed']['active_version'],4)
        self.assertTrue(any('100%' in m for m in messages));self.assertEqual(transport.return_value.close.call_count,2)

    def test_rollback_never_reports_success(self):
        p,cap,transport,client=self.prepare({'phase':6,'active_version':3})
        with self.assertRaises(RuntimeError):fw.deploy(p,'test','SD01',lambda _:None)
        self.assertEqual([c.args[0] for c in client.return_value.call.call_args_list].count(7),1)

    def test_wrong_target_before_serial_access(self):
        p,cap,transport,client=self.prepare({'phase':6,'active_version':4})
        with self.assertRaises(ValueError):fw.deploy(p,'test','SD02')
        cap.assert_not_called();transport.assert_not_called()

    def test_corrupt_package_before_serial_access(self):
        p,cap,transport,client=self.prepare({});p.write_bytes(b'bad')
        with self.assertRaises(ValueError):fw.deploy(p,'test','SD01')
        cap.assert_not_called();transport.assert_not_called()


if __name__=='__main__':unittest.main()
