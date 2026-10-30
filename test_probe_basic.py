import configparser
import tempfile
import unittest
from pathlib import Path
from config_core import generate,export,validate,axis_defaults
from test_helpers import configured_defaults
from test_config import pin_graph

class ProbeBasicTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.template=self.root/'template';self.template.mkdir()
        (self.template/'custom_config.yml').write_text('data_plugins:\n  offsettable:\n    provider: qtpyvcp.plugins.offset_table:OffsetTable\n    kwargs:\n      columns: "XYZR"\n')
        (self.template/'probe_basic.var').write_text('3000 0\n3014 0\n5220 1\n')
        for folder in ('subroutines','user_tabs','user_buttons'):(self.template/folder).mkdir()
        (self.template/'subroutines/on_abort.ngc').write_text('o<on_abort> sub\nG90\no<on_abort> endsub\n')
        for coord in ('xyz','xyza','xyzab'):
            path=self.template/f'user_dro_display/{coord}_dros';path.mkdir(parents=True)
            (path/f'dros_{coord}.py').write_text('# Synthetic resource marker for export tests, not a PB screen.\n')
        self.c=configured_defaults();self.c.update(display='probe_basic',probe_basic_template=str(self.template))
    def test_pb_uses_manual_dialog_and_no_simulated_or_other_gui_pins(self):
        files=generate(self.c);ini=configparser.ConfigParser(strict=False);ini.read_string(files[self.c['name']+'.ini'])
        self.assertEqual(ini['DISPLAY']['DISPLAY'],'probe_basic')
        self.assertEqual(ini['DISPLAY']['CONFIG_FILE'],'custom_config.yml')
        self.assertEqual(ini['HAL']['POSTGUI_HALFILE'],'custom_postgui.hal')
        self.assertEqual(files[self.c['name']+'.ini'].count('POSTGUI_HALFILE = probe_basic_postgui.hal'),1)
        self.assertEqual(ini['HAL']['TWOPASS'],'on');self.assertEqual(ini['HAL']['HALUI'],'halui')
        self.assertIn('G21',ini['RS274NGC']['RS274NGC_STARTUP_CODE'].split())
        self.assertNotIn('G20',ini['RS274NGC']['RS274NGC_STARTUP_CODE'].split())
        self.assertEqual(ini['RS274NGC']['ON_ABORT_COMMAND'],'O<on_abort> CALL')
        text=files['machine.hal']+files['probe_basic_postgui.hal'];graph=pin_graph(text)
        self.assertEqual(graph['iocontrol.0.tool-change'],graph['qtpyvcp_manualtoolchange.change'])
        self.assertEqual(graph['iocontrol.0.tool-changed'],graph['qtpyvcp_manualtoolchange.changed'])
        self.assertIn('num_aio=3',files['machine.hal'])
        for forbidden in ('hal_manualtoolchange.','gmoccapy.','qtpyvcp.probe-in.out','spindle-encoder-rpm.in'):
            self.assertNotIn(forbidden,text)
        self.assertNotIn('postgui.hal',files)
        self.assertNotIn('REMAP',ini['RS274NGC'])
    def test_probe_indicator_reuses_real_probe_signal(self):
        self.c['inputs'][0]['role']='probe'
        files=generate(self.c);graph=pin_graph(files['machine.hal']+files['probe_basic_postgui.hal'])
        self.assertEqual(graph['motion.probe-input'],graph['qtpyvcp.probe-led.on'])
    def test_export_copies_version_matched_resources_and_axis_columns(self):
        for i,letter in enumerate('AB',3):
            axis=axis_defaults(letter,i);axis['scale']=100;self.c['axes'].append(axis)
        target=self.root/'machine';export(self.c,target)
        ini=configparser.ConfigParser(strict=False);ini.read(target/(self.c['name']+'.ini'))
        self.assertEqual(ini['DISPLAY']['DRO_DISPLAY'],'XYZAB')
        self.assertEqual(ini['TRAJ']['AXES'],'5')
        self.assertIn('"XYZABR"',(target/'custom_config.yml').read_text())
        for path in ('subroutines/on_abort.ngc','user_dro_display/xyzab_dros/dros_xyzab.py','probe_basic.var','blank.ngc'):
            self.assertTrue((target/path).is_file(),path)
    def test_missing_template_is_actionable_and_export_cannot_recurse(self):
        self.c['probe_basic_template']=str(self.root/'missing')
        self.assertTrue(any('Probe Basic模板缺少' in e for e in validate(self.c)[0]))
        self.c['probe_basic_template']=str(self.template)
        with self.assertRaises(ValueError):export(self.c,self.template/'nested')
        self.assertFalse((self.template/'nested').exists())
    def test_failed_asset_copy_does_not_leave_partial_machine(self):
        (self.template/'outside-link').symlink_to(self.root)
        target=self.root/'failed-machine'
        with self.assertRaises(ValueError):export(self.c,target)
        self.assertFalse(target.exists())

if __name__=='__main__':unittest.main()
