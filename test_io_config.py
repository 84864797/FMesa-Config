from test_helpers import configured_defaults as defaults
import unittest
from config_core import generate,validate
from test_config import pin_graph

class IOConfigTest(unittest.TestCase):
    def test_display_profiles_and_toolchange_ownership(self):
        for display,command,pin in [('axis','axis','hal_manualtoolchange.change'),
                                    ('gmoccapy','gmoccapy','gmoccapy.toolchange-change'),
                                    ('qtdragon','qtvcp qtdragon','hal_manualtoolchange.change'),
                                    ('qtdragon_hd','qtvcp qtdragon_hd','hal_manualtoolchange.change')]:
            with self.subTest(display=display):
                c=defaults();c['display']=display;files=generate(c)
                self.assertIn('DISPLAY = '+command+'\n',files['SD_Mill.ini'])
                if display=='axis':self.assertIn('loadusr -W hal_manualtoolchange',files['machine.hal'])
                else:
                    self.assertNotIn('loadusr -W hal_manualtoolchange',files['machine.hal'])
                    self.assertIn('POSTGUI_HALFILE = postgui.hal',files['SD_Mill.ini'])
                    self.assertIn(pin,files['postgui.hal'])
                    self.assertNotIn('gmoccapy.toolchange-changeed',files['postgui.hal'])
                pin_graph(files['machine.hal']+files.get('postgui.hal',''))
        c=defaults();del c['display'];self.assertIn('DISPLAY = axis\n',generate(c)['SD_Mill.ini'])
        c['display']='bad;command';self.assertTrue(validate(c)[0])

    def config(self):
        c=defaults()
        c['discovery']={'modules':{'stepgen':5,'pwmgen':1,'encoder':1},'pins':[
            {'io':i,'connector':'P1','secondarymodulename':'None'} for i in (0,1,2,20)] +
            [{'io':3,'secondarymodulename':'StepGen','channel':'0'},
             {'io':4,'secondarymodulename':'StepGen','channel':'5'}]}
        return c
    def test_main_inputs_estop_and_shared_home_limit(self):
        c=self.config();c['axes'][0].update(search=1,latch=.2)
        c['mesa_gpio']=[dict(io=0,direction='in',role='estop-ok',invert=True),dict(io=1,direction='in',role='home-both:0',invert=False)]
        files=generate(c);hal=files['machine.hal'];pin_graph(hal)
        self.assertIn('gpio.000.in_not => iocontrol.0.emc-enable-in',hal)
        self.assertNotIn('setp iocontrol.0.emc-enable-in FALSE',hal)
        for pin in ('home-sw-in','neg-lim-sw-in','pos-lim-sw-in'):self.assertIn('joint.0.'+pin,hal)
        self.assertIn('HOME_IGNORE_LIMITS = YES',files['SD_Mill.ini'])
    def test_output_grouping_across_boards_pwm_and_joint_enable(self):
        c=self.config();c['outputs'][0]='spindle-on';c['outputs'][1]='amp:0'
        c['mesa_gpio']=[dict(io=0,direction='open-drain',role='spindle-on',invert=True),dict(io=1,direction='out',role='amp:0',invert=False)]
        hal=generate(c)['machine.hal'];pins=pin_graph(hal)
        self.assertEqual(pins['spindle.0.on'],pins['hm2_7i92.0.gpio.000.out'])
        self.assertEqual(pins['joint.0.amp-enable-out'],pins['hm2_7i92.0.gpio.001.out'])
        self.assertIn('gpio.000.is_opendrain TRUE',hal);self.assertIn('gpio.000.invert_output TRUE',hal)
    def test_rejects_mux_reserved_unknown_and_duplicate_gpio(self):
        for index in (3,20,99):
            c=self.config();c['mesa_gpio']=[dict(io=index,direction='in',role='probe',invert=False)]
            self.assertTrue(validate(c)[0])
        c=self.config();c['mesa_gpio']=[dict(io=4,direction='in',role='probe',invert=False)]
        self.assertFalse(validate(c)[0])
        c['mesa_gpio'].append(dict(c['mesa_gpio'][0]));self.assertTrue(validate(c)[0])
    def test_combined_roles_cannot_drive_same_target_across_boards(self):
        c=self.config();c['inputs'][0]['role']='home-both:0'
        c['mesa_gpio']=[dict(io=0,direction='in',role='neg:0',invert=False)]
        self.assertTrue(any('重叠' in error for error in validate(c)[0]))
    def test_disable_sd_preserves_values_but_removes_hal_references(self):
        c=self.config();c['remote_enabled']=False;c['inputs'][0]['role']='estop-ok';c['outputs'][0]='spindle-on'
        hal=generate(c)['machine.hal']
        self.assertNotIn('sserial_port_0=',hal);self.assertNotIn('.sd01.',hal)
        c['discovery']={'modules':{'stepgen':5,'pwmgen':1,'encoder':1,'sserial':1},'pins':[]}
        self.assertIn('sserial_port_0=xxxxxxxx',generate(c)['machine.hal'])
        graph=pin_graph(hal)
        self.assertEqual(graph['iocontrol.0.user-enable-out'],graph['iocontrol.0.emc-enable-in'])
        self.assertEqual(c['inputs'][0]['role'],'estop-ok')
    def test_old_projects_and_halui(self):
        c=self.config();del c['mesa_gpio'];del c['remote_enabled']
        c['inputs'][0]['role']='cycle-start'
        files=generate(c)
        self.assertIn('HALUI = halui',files['SD_Mill.ini'])
        self.assertIn('halui.program.run',files['machine.hal'])
    def test_board_change_invalidates_gpio_discovery(self):
        c=self.config();c['discovery']['board']='7i92';c['board']='7i98';c['host']='hm2_7i98.0';c['remote_prefix']='hm2_7i98.0.sd01.0.0'
        self.assertTrue(any('重新读取' in error for error in validate(c)[0]))

    def test_all_shared_home_limits_mask_limits_during_homing(self):
        c=self.config();c['inputs'][0]['role']='all-home-limit'
        files=generate(c);hal=files['machine.hal'];pins=pin_graph(hal)
        self.assertEqual(pins['joint.0.home-sw-in'],pins['io-limit-home.in-0'])
        self.assertEqual(pins['joint.0.neg-lim-sw-in'],pins['io-limit-home.out'])
        self.assertNotEqual(pins['joint.0.home-sw-in'],pins['joint.0.neg-lim-sw-in'])
        self.assertLess(hal.index('loadrt lut5'),hal.index('addf io-any-homing'))
        self.assertLess(hal.index('addf io-limit-home'),hal.index('addf motion-command-handler'))
        self.assertEqual(files['SD_Mill.ini'].count('HOME_IS_SHARED = 1'),3)
        c['axes'][1]['home_sequence']=c['axes'][0]['home_sequence'];self.assertTrue(validate(c)[0])

if __name__=='__main__':unittest.main()
