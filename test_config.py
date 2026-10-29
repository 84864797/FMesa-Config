from test_helpers import configured_defaults as defaults
import configparser
import copy
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from config_core import generate, validate, export, MPG_RESERVED
from discovery import parse, discover
from i18n import translate


def pin_graph(text):
    pins={}
    for line in text.splitlines():
        parts=line.split('#')[0].split()
        if parts and parts[0]=='net':
            for pin in parts[2:]:
                if pin in ('<=','=>','<=>'):continue
                if pin in pins and pins[pin]!=parts[1]:raise AssertionError('Pin in two signals: '+pin)
                pins[pin]=parts[1]
    return pins


class ConfigTest(unittest.TestCase):
    def test_complete_ini_and_graph(self):
        # LinuxCNC允许多个HALFILE，标准ConfigParser需禁用重复项报错。
        c=defaults();files=generate(c);ini=configparser.ConfigParser(strict=False);ini.read_string(files['SD_Mill.ini'])
        self.assertEqual(ini['KINS']['JOINTS'],'3');self.assertEqual(ini['EMCMOT']['SERVO_PERIOD'],'1000000')
        self.assertEqual(ini['JOINT_2']['TYPE'],'LINEAR');pin_graph(files['machine.hal'])

    def test_spindle_and_repeated_outputs_share_signal(self):
        c=defaults();c['outputs'][0]=c['outputs'][1]='spindle-on'
        pins=pin_graph(generate(c)['machine.hal'])
        self.assertEqual(pins[c['host']+'.pwmgen.00.enable'],pins[c['remote_prefix']+'.output-00'])

    def test_fixed_vga_and_reserved_inputs(self):
        c=defaults();hal=generate(c)['machine.hal']
        for n in MPG_RESERVED:self.assertIn(f'gpio.{n:03}.is_output FALSE',hal)
        self.assertIn('encoder-counts <= hm2_7i92.0.encoder.00.count',hal)
        self.assertNotIn('sd01.0.0.encoder.count',hal)
        for a,p in [('x',25),('y',23),('z',21)]:
            self.assertIn(f'axis.{a}.jog-vel-mode 1',hal)
            self.assertIn(f'net mpg-{a} axis.{a}.jog-enable <= hm2_7i92.0.gpio.{p:03}.in_not',hal)
        self.assertIn('setp mux4.0.in0 0.025',hal);self.assertIn('setp mux4.0.in1 0.0025',hal)
        self.assertIn('setp mux4.0.in2 0.00025',hal);self.assertIn('setp mux4.0.in3 0',hal)

    def test_missing_estop_uses_software_loopback(self):
        graph=pin_graph(generate(defaults())['machine.hal'])
        self.assertEqual(graph['iocontrol.0.user-enable-out'],graph['iocontrol.0.emc-enable-in'])

    def test_estop_mapping_uses_actual_polarity(self):
        c=defaults();c['inputs'][0]={'role':'estop-ok','invert':True};hal=generate(c)['machine.hal']
        self.assertIn('input-00-not => iocontrol.0.emc-enable-in',hal)
        self.assertNotIn('setp iocontrol.0.emc-enable-in FALSE',hal)

    def test_duplicate_stepgen_rejected(self):
        c=defaults();c['axes'][1]['stepgen']=0
        with self.assertRaises(ValueError):generate(c)

    def test_nan_and_injection_rejected(self):
        for key,value in [('name','../bad'),('ip','10.0.0.1; reboot'),('remote_prefix','bad\nloadrt fake')]:
            c=defaults();c[key]=value;self.assertTrue(validate(c)[0])
        c=defaults();c['axes'][0]['scale']=float('nan');self.assertTrue(validate(c)[0])

    def test_homing_requires_switch_and_latch(self):
        c=defaults();c['axes'][0]['search']=1;self.assertTrue(validate(c)[0])
        c['axes'][0]['latch']=.5;c['inputs'][3]['role']='home:0';self.assertFalse(validate(c)[0])

    def test_discovered_resource_limit_and_reserved_conflict(self):
        c=defaults();c['discovery']={'modules':{'stepgen':2},'pins':[]};self.assertTrue(validate(c)[0])
        c['discovery']={'modules':{'stepgen':5,'encoder':1,'pwmgen':1},'pins':[{'io':20,'secondarymodulename':'StepGen','channel':'4'}]}
        self.assertTrue(any('GPIO020' in e for e in validate(c)[0]))
        c['stepgens']=3;self.assertFalse(validate(c)[0])

    def test_output_directions_and_unchanged_names(self):
        c=defaults();c['remote_model']='SD02';c['remote_prefix']='hm2_7i92.0.SD02.0.0'
        files=generate(c);self.assertIn('SD02.0.0.output-15',files['machine.hal'])

    def test_export_roundtrip_and_no_overwrite(self):
        c=defaults()
        with tempfile.TemporaryDirectory() as t:
            target=Path(t)/'new';export(c,target)
            self.assertEqual(json.loads((target/'project.json').read_text(encoding='utf-8')),c)
            with self.assertRaises(FileExistsError):export(c,target)

    def test_rotary_axis_configuration(self):
        c=defaults();c['axes'].append({**c['axes'][0],'axis':'A','stepgen':3,'home_sequence':3})
        ini=generate(c)['SD_Mill.ini'];self.assertIn('coordinates=XYZA',ini);self.assertIn('[JOINT_3]\nTYPE = ANGULAR',ini)

    def test_language_does_not_change_hal_identifiers(self):
        c=defaults();c['language']='en';f=generate(c)
        self.assertIn('hm2_7i92.0.sd01.0.0.input-00',f['machine.hal'])
        self.assertEqual(translate('01  硬件发现','en'),'01  Hardware discovery')


class DiscoveryTest(unittest.TestCase):
    @patch('discovery.run')
    def test_read_custom_pins_reads_descriptors_without_sserial_scan(self,run):
        from discovery import read_custom_pins
        run.return_value='There are 6 of StepGen in configuration\nThere are 1 of PWM in configuration\nIO Connections for P1\n'+''.join(f'1 {index} IOPort None\n' for index in range(30,34))
        result=read_custom_pins('7i92','10.10.10.10',(30,31,32,33))
        self.assertEqual(result['modules']['stepgen'],6)
        self.assertEqual([p['io'] for p in result['custom_pins']],[30,31,32,33])
        self.assertEqual(run.call_count,1)
        self.assertEqual(run.call_args.args[0][-1],'--readhmid')
        with self.assertRaisesRegex(ValueError,'缺少'):read_custom_pins('7i92','10.10.10.10',(29,30))
    @patch('discovery.subprocess.run')
    @patch('discovery.run')
    def test_scan_timeout_preserves_main_board_and_partial_output(self,run,process):
        process.return_value.returncode=1
        run.side_effect=['There are 5 of StepGen in configuration',
                         subprocess.TimeoutExpired(['mesaflash'],60,output=b'SSLBP Version: 1.43')]
        d=discover('7i92','10.10.10.10',True)
        self.assertEqual(d['modules']['stepgen'],5)
        self.assertIn('1.43',d['sserial_raw'])
        self.assertIn('从板尚未确认',d['sserial_error'])

    def test_text(self):
        d=parse('There are 5 of StepGen in configuration\nThere are 1 of QCount in configuration\nThere are 1 of PWM in configuration\nIO Connections for P1\n14 20 IOPort StepGen 4 Step (Out)\n')
        self.assertEqual(d['modules'],{'stepgen':5,'encoder':1,'pwmgen':1})
        self.assertEqual(d['pins'][0]['io'],20);self.assertEqual(d['pins'][0]['channel'],'4')

    def test_xml(self):
        d=parse('prefix\n<hostmot2><modules><module><tagname>StepGen</tagname><numinstances>5</numinstances></module></modules><pins><pin><connector>P1</connector><secondarymodulename>None</secondarymodulename></pin></pins></hostmot2>')
        self.assertEqual(d['modules']['stepgen'],5);self.assertEqual(d['pins'][0]['io'],0)

    def test_invalid_does_not_create_resources(self):
        for text in ('nothing','<hostmot2>broken'):
            with self.assertRaises(ValueError):parse(text)

    @patch('discovery.run')
    def test_discovery_uses_argument_list(self,run):
        run.return_value='There are 5 of StepGen in configuration'
        discover('7i92','10.10.10.10')
        self.assertEqual(run.call_args.args[0],['mesaflash','--device','7i92','--addr','10.10.10.10','--readhmid'])
        with self.assertRaises(ValueError):discover('7i92','10.0.0.1;bad')


if __name__=='__main__':unittest.main()
