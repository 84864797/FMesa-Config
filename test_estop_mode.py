"""E-stop follows PNCconf input assignment, with no separate mode setting."""
import subprocess,unittest
from pathlib import Path
from config_core import generate
from test_helpers import configured_defaults
from test_config import pin_graph

class EstopRuleTest(unittest.TestCase):
    def test_no_external_input_uses_software_loopback(self):
        hal=generate(configured_defaults())['machine.hal'];graph=pin_graph(hal)
        self.assertEqual(graph['iocontrol.0.user-enable-out'],graph['iocontrol.0.emc-enable-in'])
        self.assertNotIn('setp iocontrol.0.emc-enable-in FALSE',hal)
    def test_assigned_external_input_always_controls_enable(self):
        c=configured_defaults();c['estop_mode']='software' # Obsolete field must not override an input.
        c['inputs'][0]=dict(role='estop-ok',invert=True)
        graph=pin_graph(generate(c)['machine.hal'])
        self.assertEqual(graph[c['remote_prefix']+'.input-00-not'],graph['iocontrol.0.emc-enable-in'])
        self.assertNotIn('iocontrol.0.user-enable-out',graph)
    def test_estop_output_fanout_keeps_one_signal(self):
        c=configured_defaults();c['outputs'][0]='estop-out'
        graph=pin_graph(generate(c)['machine.hal'])
        self.assertEqual(graph['iocontrol.0.user-enable-out'],graph['iocontrol.0.emc-enable-in'])
        self.assertEqual(graph['iocontrol.0.user-enable-out'],graph[c['remote_prefix']+'.output-00'])
    @unittest.skipUnless(Path('/usr/lib/python3/dist-packages/pncconf/build_HAL.py').exists(),'PNCconf not installed')
    def test_loopback_matches_execution_of_actual_pncconf_branch(self):
        script='''import ast,io,types
+source=open('/usr/lib/python3/dist-packages/pncconf/build_HAL.py').read()
+tree=ast.parse(source)
+branch=next(n for n in ast.walk(tree) if isinstance(n,ast.If) and ast.unparse(n.test)=='self.d.classicladder and self.d.ladderhaltype == 1 and self.d.ladderconnect')
+sourcepin=next(n for n in ast.walk(tree) if isinstance(n,ast.Expr) and isinstance(n.value,ast.Call) and n.value.args and isinstance(n.value.args[0],ast.Constant) and isinstance(n.value.args[0].value,str) and 'net estop-out' in n.value.args[0].value and 'iocontrol.0.user-enable-out' in n.value.args[0].value)
+output=io.StringIO()
+exec(compile(ast.Module(body=[sourcepin,branch],type_ignores=[]),'<actual PNCconf E-stop branch>','exec'),dict(self=types.SimpleNamespace(d=types.SimpleNamespace(classicladder=False)),estop=False,file=output))
+print(output.getvalue())
+'''.replace('\n+','\n')
        reference=pin_graph(subprocess.check_output(['/usr/bin/python3','-c',script],text=True))
        actual=pin_graph(generate(configured_defaults())['machine.hal'])
        for graph in (reference,actual):self.assertEqual(graph['iocontrol.0.user-enable-out'],graph['iocontrol.0.emc-enable-in'])

if __name__=='__main__':unittest.main()
