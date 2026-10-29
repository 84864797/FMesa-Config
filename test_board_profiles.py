import copy
import unittest
from board_profiles import PROFILES,BoardProfile,register_profile,default_discovery,effective_gpio
from config_core import defaults,generate,validate
from test_config import pin_graph

class ProfileTest(unittest.TestCase):
    def configured(self):
        c=defaults()
        for axis in c['axes']:axis['scale']=400.
        return c
    def test_default_pinout_and_locked_outputs(self):
        c=self.configured();self.assertFalse(validate(c)[0])
        pins={p['io']:p for p in c['discovery']['pins']}
        self.assertEqual(pins[1]['secondarymodulename'],'PWM')
        self.assertEqual(pins[4]['secondaryfunctionname'],'Step/Table1')
        self.assertEqual(pins[26]['secondaryfunctionname'],'Quad-B')
        hal=generate(c)['machine.hal'];pin_graph(hal)
        for index in (0,2,3):
            self.assertIn(f'gpio.{index:03}.is_output TRUE',hal)
            self.assertIn(f'gpio.{index:03}.invert_output TRUE',hal)
        self.assertIn('spindle.0.forward => hm2_7i92.0.gpio.000.out',hal)
        for index in range(14,20):self.assertIn(f'gpio.{index:03}.is_output FALSE',hal)
    def test_reject_tampered_fixed_rules_and_firmware(self):
        c=self.configured();c['spindle']['channel']=1
        self.assertTrue(any('PWM通道固定为0' in e for e in validate(c)[0]))
        for index,direction,invert in [(0,'in',True),(0,'out',False),(14,'out',False)]:
            c=self.configured();v=next(v for v in c['mesa_gpio'] if v['io']==index)
            v.update(direction=direction,invert=invert)
            self.assertTrue(validate(c)[0])
        c=self.configured();c['discovery']['pins'][14]['secondarymodulename']='StepGen'
        self.assertTrue(any('固定接线' in e for e in validate(c)[0]))
    def test_custom_gpio_and_axis_pair(self):
        c=self.configured();c['mesa_gpio'].append(dict(io=30,direction='in',role='probe',invert=True))
        self.assertIn('gpio.030.in_not => motion.probe-input',generate(c)['machine.hal'])
        c['mesa_gpio']=[v for v in c['mesa_gpio'] if v['io']!=30]
        c['stepgens']=6;c['discovery']['modules']['stepgen']=6
        c['axes'][0]['stepgen']=5
        c['discovery']['pins'][30].update(secondarymodulename='StepGen',channel='5',secondaryfunctionname='Step/Table1')
        self.assertTrue(any('Step/Dir' in e for e in validate(c)[0]))
        c['discovery']['pins'][31].update(secondarymodulename='StepGen',channel='5',secondaryfunctionname='Dir/Table2')
        hal=generate(c)['machine.hal']
        self.assertIn('stepgen.05.velocity-cmd',hal);self.assertNotIn('gpio.030.is_output',hal)
    def test_serial_requires_matching_pair(self):
        c=self.configured();c['remote_enabled']=True
        self.assertTrue(any('TX/RX' in e for e in validate(c)[0]))
        for index,name in [(30,'TXData0'),(31,'RXData0')]:c['discovery']['pins'][index].update(secondarymodulename='SSerial',channel='0',secondaryfunctionname=name)
        self.assertFalse(validate(c)[0])
    def test_registry_is_extensible_and_baseline_copies_are_isolated(self):
        p=BoardProfile('TEST_BOARD','Test board','7i92',custom_pins=(30,),baseline=default_discovery('F7I92'))
        try:
            register_profile(p)
            self.assertIn('TEST_BOARD',PROFILES)
            with self.assertRaises(ValueError):register_profile(p)
            a=default_discovery('TEST_BOARD');a['pins'][0]['io']=999
            self.assertEqual(default_discovery('TEST_BOARD')['pins'][0]['io'],0)
        finally:PROFILES.pop('TEST_BOARD',None)

if __name__=='__main__':unittest.main()
