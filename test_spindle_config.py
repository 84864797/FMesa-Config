import configparser
import unittest
from config_core import generate,validate
from test_helpers import configured_defaults
from test_config import pin_graph

class SpindleTest(unittest.TestCase):
    def servo(self):
        c=configured_defaults();c['spindle'].update(type='stepdir',stepgen=4,pulses_per_rev=1000.,rpm=3000.,acceleration=100.)
        return c
    def test_servo_units_and_separate_stepgen_configuration(self):
        c=self.servo();files=generate(c);hal=files['machine.hal'];pin_graph(hal)
        ini=configparser.ConfigParser(strict=False);ini.read_string(files[c['name']+'.ini'])
        section=ini['SPINDLE_0']
        self.assertEqual(float(section['MAX_FORWARD_VELOCITY']),3000.)
        self.assertEqual(float(section['STEP_SCALE']),1000.)
        self.assertEqual(float(section['STEPGEN_MAXVEL']),62.5)
        self.assertEqual(float(section['STEPGEN_MAXACCEL']),125.)
        self.assertIn('spindle.0.speed-out-rps => hm2_7i92.0.stepgen.04.velocity-cmd',hal)
        self.assertIn('stepgen.04.control-type 1',hal)
        self.assertIn('stepgen.04.velocity-fb => spindle.0.speed-in',hal)
        self.assertNotIn('pwmgen.00.value',hal)
        self.assertNotIn('pid.s',hal)
        self.assertLess(hal.index('addf pid.x'),hal.index('addf hm2_7i92.0.write'))
    def test_channel_conflicts_scaling_and_pulse_limits(self):
        for field,value in [('stepgen',0),('stepgen',5),('pulses_per_rev',0),('pulses_per_rev',100000),('acceleration',0),('steplen',0)]:
            c=self.servo();c['spindle'][field]=value
            with self.subTest(field=field,value=value):self.assertTrue(validate(c)[0])
    def test_shared_machine_enable_signal_has_one_net(self):
        c=self.servo();c['outputs'][0]='machine-enabled'
        hal=generate(c)['machine.hal'];pins=pin_graph(hal)
        self.assertEqual(pins['motion.motion-enabled'],pins['hm2_7i92.0.stepgen.04.enable'])
        self.assertEqual(pins['motion.motion-enabled'],pins['hm2_7i92.0.sd01.0.0.output-00'])
    def test_analog_scale_and_legacy_pwm_command(self):
        c=configured_defaults();hal=generate(c)['machine.hal']
        self.assertIn('spindle.0.speed-out => hm2_7i92.0.pwmgen.00.value',hal)
        self.assertNotIn('stepgen.04.velocity-cmd',hal)
        del c['spindle']['type'];hal=generate(c)['machine.hal']
        self.assertIn('spindle.0.speed-out => hm2_7i92.0.pwmgen.00.value',hal)
    def test_servo_without_pwm_resource_and_disabled_spindle(self):
        c=self.servo();c['pwmgens']=0;self.assertFalse(validate(c)[0])
        self.assertNotIn('setp hm2_7i92.0.pwmgen.',generate(c)['machine.hal'])
        c['spindle']['enabled']=False;c['spindle']['pulses_per_rev']=0
        self.assertNotIn('[SPINDLE_0]',generate(c)[c['name']+'.ini'])

if __name__=='__main__':unittest.main()
