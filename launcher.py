"""Packaged entry point; self-test never opens a hardware connection."""
import os
import struct
import sys
from pathlib import Path

def main():
    if '--version' in sys.argv:
        print((Path(__file__).resolve().parent/'VERSION').read_text().strip());return 0
    if '--self-test' in sys.argv:
        os.environ['QT_QPA_PLATFORM']='offscreen'
        from PySide6.QtWidgets import QApplication
        from app import Window,setup_fonts
        from config_core import defaults,generate
        import firmware_update
        from f407_update import package,unpack
        app=QApplication([]);setup_fonts();window=Window()
        c=window.collect()
        assert c==defaults()
        assert c['spindle']['frequency']==200 and c['spindle']['invert_pwm'] is True
        for axis in c['axes']:axis['scale']=100
        generated=generate(c);hal=generated['machine.hal']
        assert 'gpio.001.invert_output TRUE' in hal
        assert 'sserial_port_0=' not in hal
        synthetic=struct.pack('<II',0x2001fff0,0x08020009)+b'FMesa synthetic parser test data; not a working program'
        _,payload=unpack(package(synthetic,1,1));assert payload==synthetic
        window.close();print('Self-test passed: Qt GUI, config generation, package parser (synthetic data); no hardware access.');return 0
    if '--cli' in sys.argv:
        sys.argv.remove('--cli')
        from cli import main as cli_main
        return cli_main()
    from app import main as gui_main
    return gui_main()

if __name__=='__main__':sys.exit(main())
