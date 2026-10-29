"""Read-only comparison against installed PNCconf; never starts LinuxCNC or hardware."""
import configparser
import json
from pathlib import Path
import subprocess
import unittest
from config_core import defaults,axis_defaults,generate,validate
from test_helpers import configured_defaults

class ReferenceTest(unittest.TestCase):
    @unittest.skipUnless(Path('/usr/lib/python3/dist-packages/pncconf/build_INI.py').exists(),'PNCconf source not installed')
    def test_spindle_display_branch_executes_actual_pncconf_code(self):
        script='''import ast,builtins,io,json,types
builtins._=lambda s:s
from pncconf.private_data import Private_Data
from pncconf.data import Data
p=Private_Data(None,'/usr/bin','/usr');d=Data(None,p,'/usr','reference')
source=open('/usr/lib/python3/dist-packages/pncconf/build_INI.py').read()
nodes=[n for n in ast.walk(ast.parse(source)) if isinstance(n,ast.If) and ast.unparse(n.test)=='self.d.frontend == _PD._QTDRAGON' and 'DEFAULT_SPINDLE_0_SPEED' in ast.get_source_segment(source,n)]
assert len(nodes)==1
code=compile(ast.Module(body=nodes,type_ignores=[]),'<PNCconf spindle display branch>','exec')
result={}
for label,frontend in [('gmoccapy',p._GMOCCAPY),('qtdragon',p._QTDRAGON)]:
    d.frontend=frontend;output=io.StringIO()
    exec(code,dict(self=types.SimpleNamespace(d=d),_PD=p,file=output))
    result[label]=dict(line.strip().split(' = ',1) for line in output.getvalue().splitlines())
print(json.dumps(result))
'''
        from display_config import settings
        reference=json.loads(subprocess.check_output(['/usr/bin/python3','-c',script],text=True))
        for display,fields in reference.items():
            ours={k:v for k,v in settings(display,24000).items() if 'SPINDLE' in k}
            self.assertEqual(set(ours),set(fields))
            for key,value in ours.items():self.assertEqual(float(value),float(fields[key]))

    @unittest.skipUnless(Path('/usr/lib/python3/dist-packages/pncconf/data.py').exists(),'PNCconf source not installed')
    def test_defaults_against_actual_pncconf_metric_data(self):
        script='''import builtins,json
builtins._=lambda s:s
from pncconf.private_data import Private_Data
from pncconf.data import Data
p=Private_Data(None,'/usr/bin','/usr');d=Data(None,p,'/usr','reference')
d.set_axis_unit_defaults(False)
fields=['maxvel','maxacc','minlim','maxlim','homepos','homesw','homefinalvel','maxferror','minferror','steptime','stepspace','dirsetup','dirhold','stepscale','homesequence']
print(json.dumps({a:{f:getattr(d,a+f) for f in fields} for a in 'xyza'}))
'''
        reference=json.loads(subprocess.check_output(['/usr/bin/python3','-c',script],text=True))
        mapping={'velocity':'maxvel','acceleration':'maxacc','minimum':'minlim','maximum':'maxlim','home':'homepos','home_offset':'homesw',
                 'home_final_velocity':'homefinalvel','ferror':'maxferror','min_ferror':'minferror','steplen':'steptime','stepspace':'stepspace',
                 'dirsetup':'dirsetup','dirhold':'dirhold','scale':'stepscale'}
        for i,letter in enumerate('XYZA'):
            ours=axis_defaults(letter,i)
            for field,upstream in mapping.items():
                with self.subTest(axis=letter,field=field):self.assertEqual(ours[field],reference[letter.lower()][upstream])
            self.assertEqual(ours['home_sequence'],reference[letter.lower()]['homesequence']+1)
    def test_unset_scale_blocks_export(self):
        self.assertTrue(any('比例不得为零' in e for e in validate(defaults())[0]))
        with self.assertRaises(ValueError):generate(defaults())
    def test_pid_and_function_order(self):
        c=configured_defaults();files=generate(c);hal=files['machine.hal']
        ini=configparser.ConfigParser(strict=False);ini.read_string(files[c['name']+'.ini'])
        self.assertEqual(float(ini['JOINT_0']['P']),1e9/c['servo_ns'])
        self.assertEqual(float(ini['JOINT_0']['STEPGEN_MAXVEL']),c['axes'][0]['velocity']*1.25)
        self.assertIn('stepgen.00.control-type 1',hal)
        self.assertIn('pid.x.output => hm2_7i92.0.stepgen.00.velocity-cmd',hal)
        self.assertNotIn('=> hm2_7i92.0.stepgen.00.position-cmd',hal)
        for function in ('hm2_7i92.0.read','motion-controller','pid.x.do-pid-calcs','mux4.0'):
            self.assertLess(hal.index('addf '+function+' servo-thread'),hal.index('addf hm2_7i92.0.write servo-thread'))
    def test_home_is_distinct_from_switch_offset(self):
        c=configured_defaults();c['axes'][0].update(home=5.,home_offset=-10.,search=-1.,latch=-.5,home_final_velocity=.2)
        c['inputs'][0]['role']='home:0';files=generate(c)
        ini=configparser.ConfigParser(strict=False);ini.read_string(files[c['name']+'.ini'])
        joint=ini['JOINT_0'];self.assertEqual(float(joint['HOME']),5);self.assertEqual(float(joint['HOME_OFFSET']),-10)
        self.assertEqual(float(joint['HOME_FINAL_VEL']),.2)
    def test_legacy_mode_and_parameters_are_preserved(self):
        c=configured_defaults();del c['stepgen_control']
        for a in c['axes']:
            a.update(velocity=10.,acceleration=100.,dirsetup=5000,dirhold=5000)
            for key in ('home_offset','home_final_velocity','ferror','min_ferror'):del a[key]
        files=generate(c);hal=files['machine.hal']
        self.assertIn('stepgen.00.control-type 0',hal);self.assertNotIn('loadrt pid',hal)
        self.assertIn('stepgen.00.dirsetup 5000',hal)

if __name__=='__main__':unittest.main()
