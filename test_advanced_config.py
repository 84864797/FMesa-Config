import configparser
import tempfile
import unittest
from pathlib import Path
from config_core import generate,validate,axis_defaults
from test_helpers import configured_defaults
from test_config import pin_graph

class AdvancedTest(unittest.TestCase):
    def config(self):
        c=configured_defaults();c['mpg']['enabled']=False;c['stepgens']=8;c['encoders']=4;c['pwmgens']=3
        return c
    def ini(self,c):
        files=generate(c);ini=configparser.ConfigParser(strict=False);ini.read_string(files[c['name']+'.ini']);pin_graph(files['machine.hal']+files.get('postgui.hal',''));return ini,files
    @unittest.skipUnless(Path('/usr/lib/python3/dist-packages/pncconf/build_INI.py').exists(),'PNCconf source not installed')
    def test_joint_fields_against_executed_pncconf_generator(self):
        import json,subprocess
        reference=json.loads(subprocess.check_output(['/usr/bin/python3','tests/reference/pncconf_advanced_reference.py'],text=True))
        with tempfile.TemporaryDirectory() as directory:
            comp=Path(directory)/'fixture.dat';comp.write_text('0 0 0\n1 0 0\n')
            for mode,fields in reference.items():
                c=self.config();c['axes'][0].update(search=-1,latch=-.2)
                c['inputs'][0]['role']='home:0'
                c['axes'][0]['advanced'].update(encoder=1,encoder_scale=1000,home_use_index=True)
                if mode=='backlash':c['axes'][0]['advanced'].update(backlash_enabled=True,backlash=.03)
                if mode=='compensation':c['axes'][0]['advanced'].update(comp_file=str(comp),comp_type=1)
                if mode=='tandem':
                    c['axes'][0]['advanced'].update(tandem_enabled=True,tandem_stepgen=3,tandem_scale=400)
                    c['inputs'][1]['role']='home:1'
                ini,_=self.ini(c)
                for key in ('stepgen_maxvel','stepgen_maxaccel','home_sequence','home_use_index','backlash','comp_file_type'):
                    if key in fields:
                        if key=='home_use_index':self.assertEqual(ini['JOINT_0'][key],fields[key])
                        else:self.assertEqual(float(ini['JOINT_0'][key]),float(fields[key]))

    def test_backlash_and_compensation_margin_and_packaged_file(self):
        c=self.config();c['axes'][0]['advanced'].update(backlash_enabled=True,backlash=.03)
        ini,_=self.ini(c);self.assertEqual(float(ini['JOINT_0']['BACKLASH']),.03)
        self.assertEqual(float(ini['JOINT_0']['STEPGEN_MAXACCEL']),1500)
        with tempfile.TemporaryDirectory() as d:
            source=Path(d)/'comp.txt';source.write_text('0 0 0\n1 0.1 0.1\n')
            c['axes'][0]['advanced'].update(backlash_enabled=False,comp_file=str(source),comp_type=1)
            ini,files=self.ini(c);self.assertEqual(files[ini['JOINT_0']['COMP_FILE']],source.read_text())
        self.assertTrue(validate(c)[0])
    def test_index_homing_and_encoder_feedback(self):
        c=self.config();c['axes'][0].update(search=1,latch=.2);c['inputs'][0]['role']='home:0'
        c['axes'][0]['advanced'].update(encoder=1,encoder_scale=1000,home_use_index=True)
        ini,files=self.ini(c);hal=files['machine.hal'];graph=pin_graph(hal)
        self.assertEqual(ini['JOINT_0']['HOME_USE_INDEX'],'YES')
        self.assertEqual(graph['joint.0.motor-pos-fb'],graph[c['host']+'.encoder.01.position'])
        self.assertEqual(graph['joint.0.index-enable'],graph[c['host']+'.encoder.01.index-enable'])
        self.assertNotIn(c['host']+'.stepgen.00.position-fb',hal)
    def test_analog_axis_pid_owns_pwm(self):
        c=self.config();c['axes'][0]['advanced'].update(drive='pwm',pwm_channel=1,encoder=1,encoder_scale=400,p=10,max_output=10,ff1=0)
        _,files=self.ini(c);hal=files['machine.hal'];graph=pin_graph(hal)
        self.assertNotIn(c['host']+'.stepgen.00.',hal)
        self.assertEqual(graph['pid.x.output'],graph[c['host']+'.pwmgen.01.value'])
        c['axes'][0]['advanced']['pwm_channel']=0;self.assertTrue(validate(c)[0])
    def test_tandem_joint_coordinates_and_separate_home(self):
        c=self.config();c['axes'][1].update(search=-1,latch=-.1)
        c['axes'][1]['advanced'].update(tandem_enabled=True,tandem_stepgen=3,tandem_scale=-400,tandem_home_offset=2)
        c['inputs'][0]['role']='home:1';c['inputs'][1]['role']='home:2'
        ini,files=self.ini(c)
        self.assertEqual(ini['KINS']['JOINTS'],'4');self.assertIn('XYYZ',ini['KINS']['KINEMATICS'])
        self.assertIn('kinstype=BOTH',ini['KINS']['KINEMATICS'])
        self.assertEqual(ini['JOINT_1']['HOME_SEQUENCE'],ini['JOINT_2']['HOME_SEQUENCE'])
        self.assertLess(int(ini['JOINT_2']['HOME_SEQUENCE']),0)
        self.assertEqual(float(ini['JOINT_2']['STEP_SCALE']),-400)
        self.assertEqual(float(ini['JOINT_2']['HOME_OFFSET']),2)
        self.assertIn('pid.y_tandem',files['machine.hal'])
        c['inputs'][1]['role']='';self.assertTrue(validate(c)[0])
    def test_spindle_encoder_closed_loop_analog_and_stepdir(self):
        for mode in ('analog','stepdir'):
            c=self.config();c['spindle'].update(type=mode,encoder=1,encoder_scale=4096,closed_loop=True,p=.1,pulses_per_rev=1000)
            _,files=self.ini(c);graph=pin_graph(files['machine.hal'])
            self.assertEqual(graph['spindle.0.revs'],graph[c['host']+'.encoder.01.position'])
            self.assertIn('spindle-speed.out',files['machine.hal'])
            if mode=='analog':self.assertEqual(graph['pid.s.output'],graph[c['host']+'.pwmgen.00.value'])
            else:self.assertIn('spindle-rpm-to-rps.out => '+c['host']+'.stepgen.04.velocity-cmd',files['machine.hal'])
    def test_legacy_backlash_margin_and_encoder_resource_rejection(self):
        c=self.config();c['stepgen_control']='position';c['axes'][0]['advanced'].update(backlash_enabled=True,backlash=.02)
        _,files=self.ini(c);self.assertIn('.stepgen.00.maxaccel 1500.0',files['machine.hal'])
        c['axes'][0]['advanced'].update(encoder=0,encoder_scale=400)
        self.assertTrue(validate(c)[0])
        c['stepgen_control']='velocity_pid';c['mpg']['enabled']=True
        self.assertTrue(any('编码器' in e for e in validate(c)[0]))

    def test_policy_defaults_and_opt_in(self):
        c=self.config();ini,_=self.ini(c);self.assertNotIn('NO_FORCE_HOMING',ini['TRAJ'])
        c['machine_options'].update(require_homing=False,restore_position=True,individual_homing=True,tool_change_quill_up=True,mdi_commands='G0 X0\nG0 Z0')
        ini,_=self.ini(c);self.assertEqual(ini['TRAJ']['NO_FORCE_HOMING'],'1');self.assertEqual(ini['TRAJ']['POSITION_FILE'],'position.txt')
        self.assertNotIn('HOME_SEQUENCE',ini['JOINT_0']);self.assertEqual(ini['EMCIO']['TOOL_CHANGE_QUILL_UP'],'1')

if __name__=='__main__':unittest.main()
