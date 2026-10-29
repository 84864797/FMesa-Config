"""Packaged entry point; self-test never opens a hardware connection."""
import os
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
        from firmware_update import inspect
        from hostmot2_config import serial_option
        app=QApplication([]);setup_fonts();window=Window()
        c=window.collect()
        assert c==defaults()
        assert c['spindle']['frequency']==200 and c['spindle']['invert_pwm'] is True
        for axis in c['axes']:axis['scale']=100
        generated=generate(c);hal=generated['machine.hal']
        assert 'gpio.001.invert_output TRUE' in hal
        assert 'sserial_port_0=' not in hal
        for board in ('sd01','sd02'):
            inspect(Path(__file__).resolve().parent/'firmware/mesa-v3'/f'{board}-mesa-v5.fwup')
        window.close();print('Self-test passed: Qt GUI, config generation, firmware parsing; no hardware access.');return 0
    if '--cli' in sys.argv:
        sys.argv.remove('--cli')
        from cli import main as cli_main
        return cli_main()
    from app import main as gui_main
    return gui_main()

if __name__=='__main__':sys.exit(main())
