"""Execute installed PNCconf INI joint generation without GUI/hardware."""
import builtins,configparser,io,json
builtins._=lambda text:text
from pncconf.private_data import Private_Data
from pncconf.data import Data
from pncconf.build_INI import INI
p=Private_Data(None,'/usr/bin','/usr');d=Data(None,p,'/usr','reference');d.set_axis_unit_defaults(False);d.units=p._METRIC
class Adapter:
    def __init__(self):self.d=d;self._p=p
    def stepgen_sig(self,axis):return 'step0'
    def encoder_sig(self,axis):return 'encoder0'
    def pwmgen_sig(self,axis):return None
    def resolver_sig(self,axis):return None
    def tppwmgen_sig(self,axis):return None
    def potoutput_sig(self,axis):return None
    def findsignal(self,name):return name=='home-x'
app=Adapter();writer=INI(app);result={}
for mode in ('normal','backlash','compensation','tandem'):
    d.xusebacklash=mode=='backlash';d.xbacklash=.03
    d.xusecomp=mode=='compensation';d.xcompfilename='fixture.dat';d.xcomptype=1
    d.xusehomeindex=True;d.xhomesearchvel=1;d.xhomelatchvel=.2
    out=io.StringIO();writer.write_one_joint(out,0,'x','LINEAR',True,mode=='tandem')
    ini=configparser.ConfigParser();ini.read_string(out.getvalue());result[mode]=dict(ini['JOINT_0'])
print(json.dumps(result))
