import unittest
from config_core import defaults,axis_defaults,generate,validate,fixed_mpg
from test_config import pin_graph

class MPGTest(unittest.TestCase):
    def configured(self,count=3):
        c=defaults();c['axes']=[axis_defaults(a,i) for i,a in enumerate('XYZAB'[:count])]
        for axis in c['axes']:axis['scale']=400.
        c['mpg']['axes']=count
        return c
    def test_three_four_five_axis_mpg_wiring(self):
        for count in (3,4,5):
            c=self.configured(count);hal=generate(c)['machine.hal'];pin_graph(hal)
            for letter,pin in list(zip('xyzab',(25,23,21,22,24)))[:count]:
                self.assertIn(f'setp axis.{letter}.jog-vel-mode 1',hal)
                self.assertIn(f'net mpg-{letter} axis.{letter}.jog-enable <= hm2_7i92.0.gpio.{pin:03}.in_not',hal)
                self.assertIn(f'net mpg-scale => axis.{letter}.jog-scale',hal)
                self.assertIn(f'net encoder-counts => axis.{letter}.jog-counts',hal)
            if count==3:self.assertNotIn('axis.a.jog-enable',hal)
            if count==4:self.assertNotIn('axis.b.jog-enable',hal)
            self.assertIn('setp mux4.0.in3 0',hal)
    def test_more_mpg_axes_than_machine_is_rejected(self):
        c=self.configured();c['mpg']['axes']=5
        self.assertTrue(any('手轮轴数' in e for e in validate(c)[0]))
        with self.assertRaises(ValueError):fixed_mpg(c['host'],2)
    def test_io29_estop_and_independent_input(self):
        c=self.configured();c['mpg']['input29']=dict(role='estop-ok',invert=True)
        hal=generate(c)['machine.hal'];pin_graph(hal)
        self.assertIn('gpio.029.in_not => iocontrol.0.emc-enable-in',hal)
        self.assertNotIn('setp iocontrol.0.emc-enable-in FALSE',hal)
        c['mpg']['enabled']=False;c['mpg']['input29']=dict(role='probe',invert=False)
        hal=generate(c)['machine.hal']
        self.assertIn('gpio.029.is_output FALSE',hal)
        self.assertIn('gpio.029.in => motion.probe-input',hal)
        self.assertNotIn('loadrt mux4',hal)
    def test_servo_never_generates_gpio0_but_keeps_stored_analog_role(self):
        c=self.configured();c['spindle'].update(type='stepdir',pulses_per_rev=1000.)
        hal=generate(c)['machine.hal'];pin_graph(hal)
        self.assertNotIn('.gpio.000',hal)
        self.assertNotIn('sd-out-spindle-forward',hal)
        self.assertEqual(next(v for v in c['mesa_gpio'] if v['io']==0)['role'],'spindle-forward')
        c['spindle']['type']='analog'
        self.assertIn('spindle.0.forward => hm2_7i92.0.gpio.000.out',generate(c)['machine.hal'])

if __name__=='__main__':unittest.main()
