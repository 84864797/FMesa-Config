import json,subprocess,unittest
from pathlib import Path
from config_core import generate,validate
from test_helpers import configured_defaults
from test_config import pin_graph

ROOT=Path(__file__).parent

class Hostmot2AlignmentTest(unittest.TestCase):
    def test_load_lines_match_executed_pncconf_branches(self):
        if not Path('/usr/bin/pncconf').exists():self.skipTest('PNCconf not installed')
        reference=json.loads(subprocess.check_output(['/usr/bin/python3',str(ROOT/'tests/reference/pncconf_load_reference.py')],text=True))['cases']
        cases=[('no_serial_port',False,{}),('serial_port_all_disabled',False,{'sserial':1}),('serial_channel_0',True,{'sserial':1})]
        for label,enabled,modules in cases:
            c=configured_defaults();c['remote_enabled']=enabled;c['discovery']={'modules':{'stepgen':5,'pwmgen':1,'encoder':1,**modules},'pins':[]}
            actual=next(line for line in generate(c)['machine.hal'].splitlines() if line.startswith('loadrt hm2_eth'))
            expected=next(line.strip() for line in reference[label]['load'] if line.startswith('loadrt hm2_eth'))
            with self.subTest(branch=label):self.assertEqual(actual,expected)
    def test_dpll_requires_firmware_resource_and_uses_pncconf_values(self):
        c=configured_defaults();c['remote_enabled']=False
        self.assertNotIn('.dpll.',generate(c)['machine.hal'])
        c['discovery']={'modules':{'stepgen':5,'pwmgen':1,'encoder':1,'dpll':1},'pins':[]}
        hal=generate(c)['machine.hal']
        self.assertIn('setp hm2_7i92.0.dpll.01.timer-us -50',hal)
        self.assertIn('setp hm2_7i92.0.stepgen.timer-number 1',hal)
    def test_pwm_polarity_only_affects_discovered_pwm_pin(self):
        c=configured_defaults();c['discovery']={'modules':{'stepgen':5,'pwmgen':1,'encoder':1},'pins':[{'io':1,'secondarymodulename':'PWM','channel':'0','secondaryfunctionname':'PWM'}]}
        c['spindle']['invert_pwm']=True
        hal=generate(c)['machine.hal'];pin_graph(hal)
        self.assertIn('setp hm2_7i92.0.gpio.001.invert_output TRUE',hal)
        self.assertNotIn('gpio.001.is_output',hal)
        c['discovery']=None
        self.assertTrue(any('PWM反向' in e for e in validate(c)[0]))
    def test_at_speed_fallback_does_not_override_external_input(self):
        c=configured_defaults();hal=generate(c)['machine.hal'];pin_graph(hal)
        self.assertIn('sets spindle-at-speed TRUE',hal)
        c['inputs'][0]['role']='spindle-at-speed';hal=generate(c)['machine.hal'];pin_graph(hal)
        self.assertNotIn('sets spindle-at-speed',hal)
    def test_pwm_control_connections_match_executed_pncconf(self):
        if not Path('/usr/bin/pncconf').exists():self.skipTest('PNCconf not installed')
        subprocess.check_call(['/usr/bin/python3',str(ROOT/'tests/reference/pncconf_joint_reference.py')],cwd=ROOT,stdout=subprocess.DEVNULL)
        reference=pin_graph((ROOT/'test-results/pncconf-reference-spindle-pwm0.hal').read_text())
        actual=pin_graph(generate(configured_defaults())['machine.hal'])
        for source,destination in [('spindle.0.speed-out','hm2_7i92.0.pwmgen.00.value'),('spindle.0.on','hm2_7i92.0.pwmgen.00.enable'),('spindle.0.speed-out','pid.s.command'),('spindle.0.on','pid.s.enable'),('spindle.0.index-enable','pid.s.index-enable')]:
            self.assertEqual(reference[source],reference[destination])
            self.assertEqual(actual[source],actual[destination])
        self.assertNotEqual(actual['pid.s.output'],actual['hm2_7i92.0.pwmgen.00.value'])

if __name__=='__main__':unittest.main()
