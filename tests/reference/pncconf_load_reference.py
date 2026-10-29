"""Execute installed PNCconf's generator only; no UI, HAL or hardware calls."""
import ast,builtins,json,hashlib
from pathlib import Path
from types import SimpleNamespace
builtins._=lambda s:s
from pncconf.private_data import Private_Data
from pncconf.data import Data
p=Private_Data(None,'/usr/bin','/usr');d=Data(None,p,'/usr','reference')
source=Path('/usr/bin/pncconf').read_text()
node=next(n for n in ast.walk(ast.parse(source)) if isinstance(n,ast.FunctionDef) and n.name=='hostmot2_command_string')
ns={'_PD':p};exec(compile(ast.Module(body=[node],type_ignores=[]),'<installed PNCconf hostmot2_command_string>','exec'),ns)
firm=[0]*64
for key,value in [('_BOARDNAME','7i92'),('_HALDRIVER','hm2_eth'),('_DIRECTORY','7i92'),('_FIRMWARE','F7I92'),('_MAXSTEP',5)]:firm[getattr(p,key)]=value
d.number_mesa=1
for board in (0,1):
    for key,value in dict(currentfirmwaredata=firm,card_addrs='10.10.10.10',numof_resolvers=0,numof_tppwmgens=0,numof_encodergens=1,numof_pwmgens=1,numof_stepgens=5,pwm_frequency=200,pdm_frequency=6000000,watchdog_timeout=5000000).items():setattr(d,f'mesa{board}_'+key,value)
d.mesa1_card_addrs='' # Second card is unused; do not assign it an Ethernet address.
d['mesa0sserial0_0subboard']='SD01'
result={}
for label,ports,channels in [('no_serial_port',0,0),('serial_port_all_disabled',1,0),('serial_channel_0',1,1)]:
    d.mesa0_numof_sserialports=ports;d.mesa0_numof_sserialchannels=channels
    load,read,write=ns['hostmot2_command_string'](SimpleNamespace(d=d))
    result[label]=dict(load=load,read=read,write=write)
print(json.dumps(dict(source='/usr/bin/pncconf',sha256=hashlib.sha256(source.encode()).hexdigest(),cases=result),ensure_ascii=False,indent=2))
