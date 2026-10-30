import configparser
import unittest
from display_config import repair_ini
from test_helpers import configured_defaults
from config_core import generate

class DisplayTest(unittest.TestCase):
    def test_startup_and_custom_hal_hooks(self):
        c=configured_defaults();files=generate(c)
        ini=configparser.ConfigParser(strict=False);ini.read_string(files[c['name']+'.ini'])
        self.assertEqual(ini['RS274NGC']['RS274NGC_STARTUP_CODE'],'G21 G40 G90 G94 G97 G64 P0.025')
        self.assertEqual(ini['HAL']['HALUI'],'halui')
        for key in ('POSTGUI_HALFILE','SHUTDOWN'):self.assertIn(ini['HAL'][key],files)
        self.assertIn('INCREMENTS',ini['DISPLAY'])
        self.assertEqual(float(ini['TRAJ']['DEFAULT_LINEAR_VELOCITY']),2.5)

    def test_lathe_and_rotary_trajectory(self):
        from config_core import axis_defaults
        c=configured_defaults();c['mpg']['enabled']=False
        c['axes']=[c['axes'][0],c['axes'][2]]
        ini=configparser.ConfigParser(strict=False);ini.read_string(generate(c)[c['name']+'.ini'])
        self.assertEqual(ini['DISPLAY']['LATHE'],'1')
        self.assertEqual(ini['DISPLAY']['GEOMETRY'],'xz')
        c['axes']=[axis_defaults(a,i) for i,a in enumerate('XYZA')]
        for axis in c['axes']:axis['scale']=400
        c['axes'][3]['velocity']=80
        ini.read_string(generate(c)[c['name']+'.ini'])
        self.assertEqual(float(ini['TRAJ']['MAX_ANGULAR_VELOCITY']),80)
        self.assertEqual(float(ini['TRAJ']['DEFAULT_ANGULAR_VELOCITY']),8)

    def test_gmoccapy_indicators_use_assigned_source(self):
        c=configured_defaults();c['display']='gmoccapy';c['inputs'][2]['role']='spindle-at-speed'
        files=generate(c)
        self.assertIn('net sd-input-02 => gmoccapy.spindle_at_speed_led',files['postgui.hal'])
        self.assertIn('motion.tooloffset.x => gmoccapy.tooloffset-x',files['postgui.hal'])
        self.assertIn('gmoccapy.toolchange-changed => iocontrol.0.tool-changed',files['postgui.hal'])

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
