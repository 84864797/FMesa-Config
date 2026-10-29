import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import unittest
from PySide6.QtWidgets import QApplication
from app import Window,setup_fonts
from config_core import defaults,validate


class UITest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([]);setup_fonts()

    def setUp(self):self.w=Window()
    def tearDown(self):self.w.close()

    def test_default_form_roundtrip(self):self.assertEqual(self.w.collect(),defaults())


    def test_pwm_polarity_and_dpll_controls_roundtrip(self):
        self.w.pwm_invert.setChecked(True)
        self.w.dpll_timer.setValue(-75)
        c=self.w.collect()
        self.assertTrue(c['spindle']['invert_pwm'])
        self.assertEqual(c['dpll_timer_us'],-75)
        self.w.c=c;self.w.populate()
        self.assertTrue(self.w.pwm_invert.isChecked())
        self.assertEqual(self.w.dpll_timer.value(),-75)

    def test_f7i92_fixed_and_custom_pin_pages(self):
        self.assertEqual(self.w.board_choice.currentData(),'F7I92')
        self.assertEqual(self.w.custom_io.rowCount(),4)
        self.assertEqual([self.w.custom_io.item(row,1).data(256) for row in range(4)],[30,31,32,33])
        self.assertEqual(self.w.profile_output_widgets[0].currentData(),'spindle-forward')
        main={self.w.mesa_io.item(row,1).data(256):row for row in range(self.w.mesa_io.rowCount())}
        for index in (0,30,31,32,33):self.assertNotIn(index,main)
        for index in (2,3):
            row=main[index]
            self.assertEqual(self.w.mesa_io.cellWidget(row,3).currentData(),'out')
            self.assertFalse(self.w.mesa_io.cellWidget(row,3).isEnabled())
            self.assertTrue(self.w.mesa_io.cellWidget(row,5).isChecked())
            self.assertFalse(self.w.mesa_io.cellWidget(row,5).isEnabled())
        self.assertEqual(self.w.sp['channel'].value(),0)
        self.assertFalse(self.w.sp['channel'].isEnabled())
        for index in range(14,20):
            row=main[index]
            self.assertEqual(self.w.mesa_io.cellWidget(row,3).currentData(),'in')
            self.assertFalse(self.w.mesa_io.cellWidget(row,3).isEnabled())
            self.assertTrue(self.w.mesa_io.cellWidget(row,5).isEnabled())

    def test_custom_board_waits_for_read_and_preserves_profile_draft(self):
        row=next(row for row in range(self.w.mesa_io.rowCount()) if self.w.mesa_io.item(row,1).data(256)==2)
        combo=self.w.mesa_io.cellWidget(row,4);combo.setCurrentIndex(combo.findData('spindle-reverse'))
        self.w.board_choice.setCurrentIndex(self.w.board_choice.findData('custom'))
        self.assertEqual(self.w.mesa_io.rowCount(),0)
        self.assertIsNone(self.w.collect()['discovery'])
        self.assertFalse(self.w.io_tabs.isTabVisible(self.w.io_tabs.indexOf(self.w.custom_io_page)))
        self.w.board_choice.setCurrentIndex(self.w.board_choice.findData('F7I92'))
        row=next(row for row in range(self.w.mesa_io.rowCount()) if self.w.mesa_io.item(row,1).data(256)==2)
        self.assertEqual(self.w.mesa_io.cellWidget(row,4).currentData(),'spindle-reverse')

    def test_firmware_custom_stepgen_is_configured_in_axis_page(self):
        self.w.c['stepgens']=6;self.w.c['discovery']['modules']['stepgen']=6
        for index,name in ((30,'Step/Table1'),(31,'Dir/Table2')):
            self.w.c['discovery']['pins'][index].update(secondarymodulename='StepGen',channel='5',secondaryfunctionname=name)
        self.w.populate()
        self.w.custom_io.cellWidget(0,4).click()
        self.assertEqual(self.w.nav.currentRow(),1)
        self.assertEqual(self.w.collect()['axes'][0]['stepgen'],0)
        from PySide6.QtWidgets import QTabWidget,QFormLayout
        settings=self.w.axis_tabs.widget(0).findChild(QTabWidget,'axis_settings')
        editor=settings.widget(0).layout().itemAt(0,QFormLayout.FieldRole).widget()
        self.assertEqual(editor.maximum(),5)
        editor.setValue(5)
        c=self.w.collect()
        self.assertEqual(c['axes'][0]['stepgen'],5)
        self.assertNotIn(30,[v['io'] for v in c['mesa_gpio']])

    def test_io_labels_and_board_settings(self):
        self.assertTrue(self.w.mesa_io.isColumnHidden(0))
        self.assertEqual(self.w.io.item(0,0).text(),'input-00')
        self.assertEqual(self.w.io.item(0,3).text(),'output-00')
        at=self.w.wizard_order.index(0)
        self.assertEqual(self.w.wizard_order[at+1],1)
        self.assertEqual(self.w.pdm_frequency.value(),6000000)
        self.w.pdm_frequency.setValue(5000000)
        self.assertEqual(self.w.collect()['pdm_frequency'],5000000)

    def test_custom_read_updates_counts_and_ignores_stale_target(self):
        from copy import deepcopy
        data=deepcopy(self.w.c['discovery']);data['modules'].update(stepgen=6,pwmgen=1,encoder=2)
        self.w.hw['stepgens'].setValue(5)
        self.w.custom_discovered(data,('F7I92','7i92','10.10.10.10'))
        self.assertEqual(self.w.collect()['stepgens'],6)
        self.assertEqual(self.w.collect()['encoders'],2)
        self.assertIs(self.w.io_tabs.currentWidget(),self.w.custom_io_page)
        data['modules']['stepgen']=7
        self.w.custom_discovered(data,('F7I92','7i92','10.10.10.20'))
        self.assertEqual(self.w.collect()['stepgens'],6)

    def test_wizard_navigation_and_tabs(self):
        self.assertEqual(self.w.nav.currentRow(),9)
        self.assertFalse(self.w.back_button.isEnabled())
        self.w.wizard_next();self.assertEqual(self.w.nav.currentRow(),7)
        self.w.wizard_next();self.assertEqual(self.w.nav.currentRow(),8)
        self.w.wizard_back();self.assertEqual(self.w.nav.currentRow(),7)
        self.w.wizard_tabs.setCurrentIndex(self.w.wizard_order.index(0))
        self.assertEqual(self.w.stack.currentIndex(),0)

    def test_per_axis_editor_updates_project(self):
        from PySide6.QtWidgets import QTabWidget,QFormLayout
        page=self.w.axis_tabs.widget(0)
        settings=page.findChild(QTabWidget,'axis_settings')
        form=settings.widget(0).layout()
        scale=form.itemAt(1,QFormLayout.FieldRole).widget()
        scale.setValue(123.5)
        self.assertEqual(self.w.collect()['axes'][0]['scale'],123.5)
        self.w.c=self.w.collect();self.w.populate()
        self.assertEqual(self.w.collect()['axes'][0]['scale'],123.5)

    def test_velocity_editor_converts_minutes_to_seconds(self):
        from PySide6.QtWidgets import QTabWidget,QFormLayout
        settings=self.w.axis_tabs.widget(0).findChild(QTabWidget,'axis_settings')
        editor=settings.widget(0).layout().itemAt(2,QFormLayout.FieldRole).widget()
        self.assertEqual(editor.value(),1500.)
        editor.setValue(600.)
        self.assertEqual(self.w.collect()['axes'][0]['velocity'],10.)

    def test_unfinished_project_can_be_reopened(self):
        import tempfile,json
        from pathlib import Path
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'draft.json';path.write_text(json.dumps(defaults()))
            with patch('app.QFileDialog.getOpenFileName',return_value=(str(path),'')),patch.object(self.w,'error') as error:
                self.w.open_project();error.assert_not_called()
            self.assertEqual(self.w.collect()['axes'][0]['scale'],0.)

    def test_sd_enable_switch_preserves_assignments(self):
        self.w.io.cellWidget(0,1).setCurrentIndex(self.w.io.cellWidget(0,1).findData('probe'))
        self.w.remote_enabled.setChecked(False)
        self.assertFalse(self.w.io.isEnabled())
        self.assertFalse(self.w.hw['remote_prefix'].isEnabled())
        self.assertFalse(self.w.collect()['remote_enabled'])
        self.assertFalse(self.w.io_tabs.isTabVisible(self.w.io_tabs.indexOf(self.w.sd_page)))
        self.w.remote_enabled.setChecked(True)
        self.assertFalse(hasattr(self.w,'sd_dialog'))
        self.assertTrue(self.w.io_tabs.isTabVisible(self.w.io_tabs.indexOf(self.w.sd_page)))
        self.w.show_sd_config()
        self.assertEqual(self.w.nav.currentRow(),3)
        self.assertIs(self.w.io_tabs.currentWidget(),self.w.sd_page)
        self.assertEqual(self.w.collect()['inputs'][0]['role'],'probe')

    def test_display_selection_roundtrip(self):
        self.w.display_box.setCurrentIndex(self.w.display_box.findData('gmoccapy'))
        self.w.c=self.w.collect();self.w.populate()
        self.assertEqual(self.w.collect()['display'],'gmoccapy')

    def test_spindle_type_switches_pages_and_preserves_parameters(self):
        self.assertEqual(self.w.spindle_pages.currentIndex(),0)
        self.w.spindle_type.setCurrentIndex(self.w.spindle_type.findData('stepdir'))
        self.assertEqual(self.w.spindle_pages.currentIndex(),1)
        self.assertTrue(self.w.profile_outputs.isHidden())
        self.w.servo_fields['pulses_per_rev'].setValue(2048.)
        self.w.servo_fields['stepgen'].setValue(4)
        self.w.c=self.w.collect();self.w.populate()
        self.assertEqual(self.w.collect()['spindle']['type'],'stepdir')
        self.assertEqual(self.w.servo_fields['pulses_per_rev'].value(),2048.)
        self.w.spindle_type.setCurrentIndex(self.w.spindle_type.findData('analog'))
        self.assertEqual(self.w.spindle_pages.currentIndex(),0)
        self.assertFalse(self.w.profile_outputs.isHidden())
        self.assertEqual(self.w.servo_fields['pulses_per_rev'].value(),2048.)
        self.assertFalse(self.w.sp['channel'].isEnabled())

    def test_mpg_axis_selection_and_input29_roundtrip(self):
        self.assertIn('手轮MPG',self.w.nav.item(4).text())
        self.w.layout_choice.setCurrentText('XYZAB');self.w.apply_axes()
        self.w.mpg_axes.setCurrentIndex(self.w.mpg_axes.findData(5))
        self.w.mpg_input29.setCurrentIndex(self.w.mpg_input29.findData('probe'))
        self.w.mpg_input29_invert.setChecked(True)
        self.w.c=self.w.collect();self.w.populate()
        self.assertEqual(self.w.collect()['mpg']['axes'],5)
        self.assertEqual(self.w.collect()['mpg']['input29'],dict(role='probe',invert=True))
        self.assertIn('axis.b.jog-enable',self.w.mpg_text.toPlainText())
        self.assertIn('gpio.029.in_not',self.w.mpg_text.toPlainText())
        main=[self.w.mesa_io.item(row,1).data(256) for row in range(self.w.mesa_io.rowCount())]
        self.assertNotIn(29,main)
        self.w.mpg_input29.setCurrentIndex(self.w.mpg_input29.findData('all-home-limit'))
        self.assertIn('io-limit-home.in-0',self.w.mpg_text.toPlainText())

    def test_mesa_gpio_form_roundtrip_and_reserved_pins(self):
        self.w.c['board_profile']='custom';self.w.c['mesa_gpio']=[]
        self.w.board_choice.blockSignals(True);self.w.board_choice.setCurrentIndex(self.w.board_choice.findData('custom'));self.w.board_choice.blockSignals(False)
        self.w.c['discovery']={'modules':{'stepgen':5,'pwmgen':1,'encoder':1},'pins':[
            dict(io=0,connector='P1',raw='1 0 IOPort None',secondarymodulename='None'),
            dict(io=20,secondarymodulename='None')]}
        self.w.refresh_gpio(preserve=False)
        self.assertEqual(self.w.mesa_io.rowCount(),2)
        self.assertFalse(self.w.mesa_io.cellWidget(1,3).isEnabled())
        self.assertTrue(self.w.mesa_io.isRowHidden(1))
        self.w.mesa_io.cellWidget(0,3).setCurrentIndex(1)
        combo=self.w.mesa_io.cellWidget(0,4)
        combo.setCurrentIndex(combo.findData('home-both:0'))
        self.w.mesa_io.cellWidget(0,5).setChecked(True)
        self.assertEqual(self.w.collect()['mesa_gpio'],[dict(io=0,direction='in',role='home-both:0',invert=True)])
        self.w.c=self.w.collect();self.w.populate()
        self.assertEqual(self.w.collect()['mesa_gpio'][0]['role'],'home-both:0')

    def test_grouped_menu_selects_actual_signal(self):
        combo=self.w.io.cellWidget(0,1);menu=combo.build_menu()
        home=next(a.menu() for a in menu.actions() if a.text()=='回零与限位')
        action=next(a for a in home.actions() if a.text()=='关节0 回零与正负限位')
        action.trigger()
        self.assertEqual(combo.currentData(),'home-both:0')
        menu.deleteLater()

    def test_language_roundtrip_preserves_values(self):
        self.w.io.cellWidget(3,1).setCurrentIndex(self.w.io.cellWidget(3,1).findData('home:0'))
        before=self.w.collect()
        self.w.language_box.setCurrentIndex(1)
        self.assertEqual(self.w.nav.item(0).text(),'01  Hardware discovery')
        after=self.w.collect();after['language']='zh';self.assertEqual(after,before)
        self.w.language_box.setCurrentIndex(0)
        self.assertEqual(self.w.nav.item(0).text(),'01  硬件发现')

    def test_preview_and_rotary_axis(self):
        self.w.layout_choice.setCurrentText('XYZA');self.w.apply_axes();
        for row in range(self.w.axis_table.rowCount()):self.w.axis_table.item(row,self.w.axis_keys.index('scale')).setText('400')
        self.assertEqual(self.w.axis_table.rowCount(),4)
        self.assertFalse(validate(self.w.collect())[0]);self.w.preview();self.assertEqual(self.w.tabs.count(),5)

    def test_actual_hal_prefix_and_channel(self):
        self.w.hal_read('36 bit OUT FALSE hm2_7i92.0.SD02.0.2.input-00')
        c=self.w.collect();self.assertEqual(c['remote_prefix'],'hm2_7i92.0.SD02.0.2');self.assertEqual(c['sserial'],'xx0xxxxx')

    def test_mesa_upgrade_page_uses_configured_target(self):
        self.w.hw['ip'].setText('10.10.10.20')
        self.w.hw['remote_model'].setCurrentText('SD02')
        self.w.hw['remote_prefix'].setText('hm2_7i92.0.sd02.0.2')
        self.w.nav.setCurrentRow(6)
        self.assertEqual(self.w.up_ip.text(),'10.10.10.20');self.assertEqual(self.w.up_channel.value(),2)
        self.assertTrue(self.w.package.text().endswith('sd02-mesa-v5.fwup'))
        self.assertFalse(hasattr(self.w,'port'))

    def test_upgrade_requires_maintenance_takeover(self):
        from unittest.mock import patch
        with patch.object(self.w,'error') as error,patch.object(self.w,'start_job') as job:
            self.w.upgrade();job.assert_not_called();error.assert_called_once()


if __name__=='__main__':unittest.main()
