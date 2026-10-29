import configparser
import unittest
from display_config import repair_ini
from test_helpers import configured_defaults
from config_core import generate

class DisplayTest(unittest.TestCase):
    def test_repair_preserves_mechanical_values_and_is_idempotent(self):
        text='[DISPLAY]\nDISPLAY = gmoccapy\n[KINS]\nKINEMATICS = trivkins coordinates=XYZAB kinstype=BOTH\n[JOINT_0]\nSTEP_SCALE = -123.456\nHOME_OFFSET = 8\n'
        fixed=repair_ini(text,'gmoccapy',2000)
        self.assertEqual(fixed,repair_ini(fixed,'gmoccapy',2000))
        self.assertIn('STEP_SCALE = -123.456',fixed)
        self.assertIn('HOME_OFFSET = 8',fixed)
        self.assertNotIn('kinstype=BOTH',fixed)
        ini=configparser.ConfigParser();ini.read_string(fixed)
        self.assertEqual(ini['DISPLAY']['CYCLE_TIME'],'100')
        self.assertIn('PROGRAM_EXTENSION',ini['FILTER'])
    def test_frontend_defaults_are_present_in_exports(self):
        c=configured_defaults();c['display']='gmoccapy'
        ini=configparser.ConfigParser(strict=False);ini.read_string(generate(c)[c['name']+'.ini'])
        self.assertNotIn('DEFAULT_SPINDLE_SPEED',ini['DISPLAY'])
        self.assertNotIn('DEFAULT_SPINDLE_0_SPEED',ini['DISPLAY'])
        self.assertIn('MIN_LINEAR_VELOCITY',ini['DISPLAY'])
        c['display']='qtdragon'
        ini=configparser.ConfigParser(strict=False);ini.read_string(generate(c)[c['name']+'.ini'])
        for key,value in [('DEFAULT_SPINDLE_0_SPEED',500),('MIN_SPINDLE_0_SPEED',100),('MAX_SPINDLE_0_SPEED',2500)]:
            self.assertEqual(int(ini['DISPLAY'][key]),value)

    def test_repair_existing_decimal_display_speeds(self):
        original='[DISPLAY]\nDEFAULT_SPINDLE_0_SPEED = 300.0\nMAX_SPINDLE_0_SPEED = 2000.0\nDEFAULT_SPINDLE_SPEED = 300.0\n[SPINDLE_0]\nOUTPUT_SCALE = 2000.0\n'
        fixed=repair_ini(original,'gmoccapy',2000.)
        ini=configparser.ConfigParser();ini.read_string(fixed)
        self.assertEqual(int(ini['DISPLAY']['DEFAULT_SPINDLE_0_SPEED']),300)
        self.assertEqual(int(ini['DISPLAY']['MAX_SPINDLE_0_SPEED']),2000)
        self.assertEqual(int(ini['DISPLAY']['DEFAULT_SPINDLE_SPEED']),300)
        self.assertEqual(ini['SPINDLE_0']['OUTPUT_SCALE'],'2000.0')
        self.assertEqual(fixed,repair_ini(fixed,'gmoccapy',2000.))

if __name__=='__main__':unittest.main()
