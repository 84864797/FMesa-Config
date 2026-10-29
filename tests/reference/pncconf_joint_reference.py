"""Run actual PNCconf connect_joint without GUI or hardware."""
import builtins,io
from pathlib import Path
builtins._=lambda s:s
from pncconf.private_data import Private_Data
from pncconf.data import Data
from pncconf.build_HAL import HAL
p=Private_Data(None,'/usr/bin','/usr');d=Data(None,p,'/usr','reference');d.set_axis_unit_defaults(False)
d.useinisubstitution=False;d.spwmtype=p.PWMP
class Adapter:
    def __init__(self):self.d=d;self._p=p
    def pwmgen_sig(self,axis):return 'spwm' if axis=='s' else None
    def stepgen_sig(self,axis):return 'xstep' if axis=='x' else None
    def make_pinname(self,pin,**kwargs):return {'spwm':'hm2_7i92.0.pwmgen.00','xstep':'hm2_7i92.0.stepgen.00'}.get(pin)
    def pwmgen_invert_pins(self,pin):return []
    def stepgen_invert_pins(self,pin):return ([],[])
    def tppwmgen_has_6(self,axis):return False
    def __getattr__(self,name):
        if name in ('encoder_sig','resolver_sig','amp_8i20_sig','potoutput_sig','tppwmgen_sig','findsignal','home_sig','min_lim_sig','max_lim_sig'):return lambda *args:None
        raise AttributeError(name)
Path('test-results').mkdir(exist_ok=True)
h=HAL(Adapter())
for name,joint,letter in [('axis-x',0,'x'),('spindle-pwm0',0,'s')]:
    output=io.StringIO();h.connect_joint(output,joint,letter)
    Path('test-results/pncconf-reference-'+name+'.hal').write_text(output.getvalue())
