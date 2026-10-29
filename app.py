"""Mesa / SD整机配置台，Python 3.11+、PySide6。"""
import json
import os
import re
import sys
from pathlib import Path
from PySide6.QtCore import QThread, Signal, Qt, QTimer
from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import (QApplication,QMainWindow,QWidget,QVBoxLayout,QHBoxLayout,
    QFormLayout,QLabel,QLineEdit,QComboBox,QPushButton,QSpinBox,QDoubleSpinBox,
    QCheckBox,QListWidget,QStackedWidget,QTableWidget,QTableWidgetItem,QHeaderView,
    QPlainTextEdit,QFileDialog,QMessageBox,QTabWidget,QGroupBox,QDialog,QDialogButtonBox,QTabBar,QStyle)
from config_core import defaults, input_roles, output_roles, OUTPUT_ROLES, DISPLAYS, axis_defaults, validate, generate, export
from board_profiles import PROFILES,profile_for,effective_gpio,default_discovery,suppressed_gpio
from board_models import identify_hal_pin
import discovery
import spindle_config
from io_widgets import SignalCombo
from io_config import gpio_reason
from i18n import translate, translate_widgets


class Job(QThread):
    message = Signal(str)
    done = Signal(object)
    failed = Signal(str)
    def __init__(self, fn): super().__init__(); self.fn=fn
    def run(self):
        try: self.done.emit(self.fn(self.message.emit))
        except Exception as exc: self.failed.emit(str(exc))


def button(text, fn):
    b=QPushButton(text);b.clicked.connect(fn);return b


def number(value, integer=False, minimum=-1e9, maximum=1e9):
    w=QSpinBox() if integer else QDoubleSpinBox()
    if not integer: w.setDecimals(6)
    w.setRange(minimum,maximum);w.setValue(value);return w


class Window(QMainWindow):
    def __init__(self):
        super().__init__();self.c=defaults();self.job=None;self.upgrading=False
        self.language='zh'
        self.setWindowTitle('FMesa 配置工具 · 整机配置与升级');self.resize(1280,860)
        self.setMinimumSize(1040,730)
        container=QWidget();self.setCentralWidget(container);outer=QVBoxLayout(container)
        outer.setContentsMargins(10,10,10,8);outer.setSpacing(10)
        header=QHBoxLayout();outer.addLayout(header)
        header.addWidget(button('帮助',self.show_help));header.addWidget(button('取消',self.close))
        brand=QLabel('FMesa');brand.setObjectName('brand');header.addWidget(brand)
        self.step_title=QLabel('');self.step_title.setObjectName('step_title');header.addWidget(self.step_title,1)
        header.addWidget(button('保存数据',self.save_project))
        self.back_button=button('上一步',self.wizard_back);header.addWidget(self.back_button)
        self.next_button=button('下一步',self.wizard_next);header.addWidget(self.next_button)
        self.language_box=QComboBox();self.language_box.addItems(['中文','English']);header.addWidget(self.language_box)
        self.language_box.currentIndexChanged.connect(lambda i:self.set_language('en' if i else 'zh'))
        self.wizard_tabs=QTabBar();self.wizard_tabs.setExpanding(False);self.wizard_tabs.setUsesScrollButtons(True);outer.addWidget(self.wizard_tabs)
        self.nav=QListWidget(self);self.nav.hide()
        self.stack=QStackedWidget();self.stack.setObjectName('wizard_pages');outer.addWidget(self.stack,1)
        self.nav.currentRowChanged.connect(self.page_selected)
        self.hardware_page();self.axes_page();self.spindle_page();self.io_page();self.mpg_page();self.preview_page();self.upgrade_page()
        self.pdm_frequency=number(self.c.get('pdm_frequency',6000000),True,1,100000000)
        self.hardware_form.addRow('PDM频率 / Hz',self.pdm_frequency)
        self.dpll_timer=number(self.c.get('dpll_timer_us',-50),True,-1000000,0)
        self.hardware_form.addRow('DPLL采样提前 / μs（固件支持时）',self.dpll_timer)
        removed=self.spindle_form.takeRow(self.sp['frequency'])
        if removed.labelItem:removed.labelItem.widget().hide();removed.labelItem.widget().deleteLater()
        self.hardware_form.addRow('PWM频率 / Hz',self.sp['frequency'])
        self.basic_page();self.screen_page();self.welcome_page()
        # Internal page IDs remain stable for saved workflows and existing callbacks.
        self.wizard_order=[9,7,8,0,1,3,2,4,5,6]
        for page_id in self.wizard_order:self.wizard_tabs.addTab(re.sub(r'^\d+\s+','',self.nav.item(page_id).text()))
        self.wizard_tabs.currentChanged.connect(lambda index:self.nav.setCurrentRow(self.wizard_order[index]))
        self.nav.setCurrentRow(9);self.populate()
        self.status('离线编辑就绪；不自动连接、不启动LinuxCNC。')

    def tr_text(self,text):return translate(text,self.language)

    def page_selected(self,index):
        self.stack.setCurrentIndex(index)
        if hasattr(self,'wizard_order'):
            position=self.wizard_order.index(index)
            self.wizard_tabs.blockSignals(True);self.wizard_tabs.setCurrentIndex(position);self.wizard_tabs.blockSignals(False)
            self.step_title.setText(re.sub(r'^\d+\s+','',self.nav.item(index).text()))
            self.back_button.setEnabled(position>0)
            self.next_button.setEnabled(index!=6)
            text='开始' if index==9 else '完成并导出' if index==5 else '下一步'
            self.next_button.setText(self.tr_text(text))
        if index==6 and hasattr(self,'up_ip') and not (self.job and self.job.isRunning()):
            self.up_ip.setText(self.hw['ip'].text().strip())
            self.up_model.setCurrentText(self.hw['remote_model'].currentText())
            suffix=self.hw['remote_prefix'].text().split('.')[-1]
            if suffix.isdigit() and 0<=int(suffix)<8:self.up_channel.setValue(int(suffix))

    def upgrade_model_changed(self,model):
        self.package.clear()
        if hasattr(self,'package_info'):self.package_info.setText('请选择匹配目标型号的升级包；发行版不包含固件。')

    def status(self,text):self.statusBar().showMessage(self.tr_text(text))

    def set_language(self,language):
        self.language=language;self.c['language']=language
        self.setWindowTitle(self.tr_text('FMesa 配置工具 · 整机配置与升级'))
        translate_widgets(self,language)
        if hasattr(self,'wizard_order'):
            for i,page_id in enumerate(self.wizard_order):self.wizard_tabs.setTabText(i,re.sub(r'^\d+\s+','',self.nav.item(page_id).text()))
            self.page_selected(self.nav.currentRow())
        self.status('离线编辑就绪；不自动连接、不启动LinuxCNC。')

    def page(self,title,hint):
        p=QWidget();layout=QVBoxLayout(p);label=QLabel(re.sub(r'^\d+\s+','',title));label.setObjectName('heading');layout.addWidget(label)
        text=QLabel(hint);text.setWordWrap(True);layout.addWidget(text)
        self.nav.addItem(title);self.stack.addWidget(p);return layout

    def wizard_back(self):
        position=self.wizard_order.index(self.nav.currentRow())
        if position:self.nav.setCurrentRow(self.wizard_order[position-1])

    def wizard_next(self):
        if self.job and self.job.isRunning():
            self.status('后台任务正在进行，请等待完成');return
        if self.nav.currentRow()==5:
            self.export_config();return
        try:self.c=self.collect()
        except (ValueError,TypeError) as exc:self.error(str(exc));return
        position=self.wizard_order.index(self.nav.currentRow())
        if position+1<len(self.wizard_order):
            target=self.wizard_order[position+1]
            if target==5:self.preview()
            else:self.nav.setCurrentRow(target)

    def show_help(self):
        QMessageBox.information(self,self.tr_text('帮助'),self.tr_text(
            '依次填写基本信息、操作界面、Mesa板卡、轴、输入输出及主轴参数。\n'
            '启用SD后，在输入输出页的SD智能串口板页签配置。\n'
            '可用页签或上一步/下一步切换。最后检查INI/HAL，再导出到新目录。\n'
            '配置向导不会自动连接板卡；硬件读取和升级需要单独点击。'))

    def basic_page(self):
        l=self.page('基本信息','设置工程名称和实时周期。机器单位：线性轴mm，旋转轴degree。')
        group=QGroupBox('机床信息');form=QFormLayout(group);l.addWidget(group)
        for key,label in [('name','工程名称'),('servo_ns','伺服周期 / ns')]:
            removed=self.hardware_form.takeRow(self.hw[key])
            if removed.labelItem:removed.labelItem.widget().hide();removed.labelItem.widget().deleteLater()
            form.addRow(label,self.hw[key])
        self.control_mode=QComboBox()
        self.control_mode.addItem('PNCconf：速度模式 + PID','velocity_pid')
        self.control_mode.addItem('直接位置模式（兼容旧工程）','position')
        self.control_mode.hide()
        form.addRow('轴驱动方式',QLabel('Step/Dir（脉冲＋方向，位置控制）'))
        l.addWidget(QLabel('新工程的脉冲当量默认为0，必须按实际机械填写后才能导出。'))
        l.addStretch()

    def screen_page(self):
        l=self.page('操作界面','选择运行LinuxCNC时使用的操作界面，配置向导本身保持FMesa界面。')
        removed=self.hardware_form.takeRow(self.display_box)
        if removed.labelItem:removed.labelItem.widget().hide();removed.labelItem.widget().deleteLater()
        form=QFormLayout();form.addRow('LinuxCNC 操作界面',self.display_box);l.addLayout(form)
        self.pb_template=QLineEdit();self.pb_template.setPlaceholderText('自动查找已安装的官方machine_setup_files目录')
        self.pb_row=QWidget();pb_layout=QHBoxLayout(self.pb_row);pb_layout.setContentsMargins(0,0,0,0)
        pb_layout.addWidget(self.pb_template);pb_layout.addWidget(button('浏览…',self.choose_pb_template))
        form.addRow('Probe Basic模板目录',self.pb_row);self.pb_label=form.labelForField(self.pb_row)
        self.display_box.currentIndexChanged.connect(self.update_display_options)
        self.update_display_options()
        text=QLabel('AXIS：经典界面。\nGmoccapy：适合触摸操作。\nQtDragon / QtDragon HD：QtVCP界面，当前模板支持XYZ、XYZA。\nProbe Basic：QtPyVCP界面；使用官方配套模板，当前生成手动换刀配置。\n目标电脑需要安装所选界面；相关换刀连接会随配置生成。')
        text.setWordWrap(True);l.addWidget(text);l.addStretch()

    def update_display_options(self,_=None):
        visible=self.display_box.currentData()=='probe_basic'
        self.pb_row.setVisible(visible);self.pb_label.setVisible(visible)

    def choose_pb_template(self):
        path=QFileDialog.getExistingDirectory(self,self.tr_text('选择Probe Basic官方模板目录'))
        if path:self.pb_template.setText(path)

    def welcome_page(self):
        l=self.page('欢迎','FMesa 机床配置向导')
        title=QLabel('创建您的 LinuxCNC 机床配置');title.setObjectName('welcome_title');l.addWidget(title)
        text=QLabel('本向导为Mesa主卡及SD01/SD02智能串口板创建INI和HAL配置文件。\n\n'
                    '先设置机床基本信息与操作界面，再配置硬件引脚、轴、主轴和手轮。\n'
                    '完成后检查生成结果，并导出到新的配置目录。')
        text.setWordWrap(True);l.addWidget(text)
        row=QHBoxLayout();row.addWidget(button('新建工程',self.new));row.addWidget(button('打开工程',self.open_project));row.addStretch();l.addLayout(row)
        l.addStretch()
        l.addWidget(button('SD 固件升级…',lambda:self.nav.setCurrentRow(6)))

    def hardware_page(self):
        l=self.page('01  硬件发现','先填写主卡型号和IP，读取已安装固件的真实资源。也可导入PNCconf/mesaflash发现文本或XML。')
        self.hw={};form=QFormLayout();self.hardware_form=form;l.addLayout(form)
        labels={'name':'工程名称','board':'底层Mesa型号','ip':'Mesa IP','host':'主卡HAL前缀','servo_ns':'伺服周期 / ns','watchdog_ns':'Mesa看门狗 / ns','stepgens':'StepGen数量','pwmgens':'PWM数量','encoders':'Mesa编码器数量','remote_model':'SD从板型号','remote_prefix':'实际从板HAL前缀','sserial':'串口0通道模式'}
        for key,label in labels.items():
            if key in ('board','remote_model'):
                w=QComboBox();w.addItems(['7i92','7i92t','7i96s','7i76e','7i98'] if key=='board' else ['SD01','SD02'])
            elif key in ('servo_ns','watchdog_ns','stepgens','pwmgens','encoders'): w=number(self.c[key],True,0,1000000000)
            else:w=QLineEdit()
            self.hw[key]=w
            if key not in ('remote_model','remote_prefix','sserial'):form.addRow(label,w)
        self.display_box=QComboBox()
        for key,label in DISPLAYS.items():self.display_box.addItem(label,key)
        form.addRow('LinuxCNC 操作界面',self.display_box)
        self.board_choice=QComboBox()
        for key,profile in PROFILES.items():self.board_choice.addItem(profile.label,key)
        self.board_choice.addItem('自定义','custom')
        form.insertRow(0,'板卡选择',self.board_choice)
        self.board_choice.currentIndexChanged.connect(self.profile_changed)
        self.profile_drafts={}
        self.hw['board'].currentTextChanged.connect(self.board_changed)
        self.remote_enabled=QCheckBox('启用 SD 智能串口板');l.addWidget(self.remote_enabled)
        self.remote_enabled.toggled.connect(lambda enabled:self.remote_toggled(enabled))
        self.sd_config_button=button('配置 SD 智能串口板…',self.show_sd_config);l.addWidget(self.sd_config_button)
        self.ss_scan=QCheckBox('同时扫描Smart Serial（需退出LinuxCNC，会操作通信端口）');l.addWidget(self.ss_scan)
        row=QHBoxLayout()
        for name,fn in [('读取Mesa板卡',self.discover),('导入发现记录',self.import_discovery),('读取运行中HAL引脚',self.read_hal)]:row.addWidget(button(name,fn))
        l.addLayout(row);self.discovery_text=QPlainTextEdit();self.discovery_text.setReadOnly(True);l.addWidget(self.discovery_text,1)

    def board_changed(self,board):
        self.hw['host'].setText('hm2_'+board+'.0')

    def axes_page(self):
        l=self.page('02  轴参数','硬件Step/Dir独立轴，按位置指令控制。线性单位mm，旋转轴degree。脉冲当量必须按实际机械填写，可用负值反向。')
        row=QHBoxLayout();self.layout_choice=QComboBox();self.layout_choice.addItems(['XYZ','XYZA','XYZAB']);row.addWidget(QLabel('轴结构'));row.addWidget(self.layout_choice)
        row.addWidget(button('应用轴结构',self.apply_axes));row.addStretch();l.addLayout(row)
        self.axis_keys=['axis','stepgen','scale','velocity','acceleration','minimum','maximum','home','home_offset','home_final_velocity','search','latch','home_sequence','ferror','min_ferror','steplen','stepspace','dirsetup','dirhold']
        self.axis_table=QTableWidget(0,len(self.axis_keys));self.axis_table.setHorizontalHeaderLabels(self.axis_keys)
        self.axis_table.hide()
        self.axis_tabs=QTabWidget();l.addWidget(self.axis_tabs,1)
        l.addWidget(QLabel('搜索速度为0时采用当前位置回零；使用回零开关时需在IO页分配对应输入，并填写搜索和锁存速度。'))

    def spindle_page(self):
        l=self.page('03  主轴','选择主轴驱动类型，再配置对应的控制信号。使能、正反转等数字信号按实际接线分配。')
        self.sp={};form=QFormLayout();self.spindle_form=form;l.addLayout(form)
        self.sp['enabled']=QCheckBox('启用主轴');form.addRow(self.sp['enabled'])
        self.spindle_type=QComboBox()
        self.spindle_type.addItem('0–10V 模拟量电主轴','analog')
        self.spindle_type.addItem('伺服电机主轴（Step/Dir）','stepdir')
        form.addRow('主轴类型',self.spindle_type)
        self.sp['rpm']=number(0,False,0,1000000);form.addRow('最高/满量程转速 / rpm',self.sp['rpm'])
        self.sp['frequency']=number(0,True,0,1000000);form.addRow('PWM频率 / Hz',self.sp['frequency'])
        self.spindle_pages=QStackedWidget();l.addWidget(self.spindle_pages)
        analog=QWidget();analog_layout=QVBoxLayout(analog);analog_form=QFormLayout();analog_layout.addLayout(analog_form)
        self.sp['channel']=number(0,True,0,15);analog_form.addRow('PWM通道',self.sp['channel'])
        self.pwm_invert=QCheckBox('PWM输出反向（按实际电路）');analog_form.addRow(self.pwm_invert)
        hint=QLabel('通过板卡PWM转0–10V电路调速；满量程转速对应10V。主轴正转、反转及运行输出在IO中配置。')
        hint.setWordWrap(True);analog_layout.addWidget(hint);analog_layout.addStretch();self.spindle_pages.addWidget(analog)
        servo=QWidget();servo_layout=QVBoxLayout(servo);servo_form=QFormLayout();servo_layout.addLayout(servo_form)
        self.servo_fields={}
        labels={'stepgen':'StepGen通道（不能与机床轴共用）','pulses_per_rev':'脉冲当量 / 主轴每转（必须填写）','acceleration':'主轴加速度 / rev/s²',
                'steplen':'脉冲宽度 / ns','stepspace':'脉冲间隔 / ns','dirsetup':'方向建立 / ns','dirhold':'方向保持 / ns'}
        for key,value in spindle_config.SERVO_DEFAULTS.items():
            integer=key not in ('pulses_per_rev','acceleration')
            editor=number(value,integer);self.servo_fields[key]=editor;servo_form.addRow(labels[key],editor)
        hint=QLabel('伺服驱动器接收脉冲＋方向。最高转速在上方以rpm填写，HAL使用转/秒；每转脉冲数需包含电子齿轮及机械传动比。\nStepGen速度仅为脉冲输出估计，不是电机实测转速；本页不生成外部编码器测速或同步攻丝配置。')
        hint.setWordWrap(True);servo_layout.addWidget(hint);self.spindle_pages.addWidget(servo)
        self.spindle_type.currentIndexChanged.connect(self.update_spindle_page)
        self.sp['enabled'].toggled.connect(self.update_spindle_page)
        self.profile_outputs=QGroupBox('板卡固定主轴输出');self.profile_output_form=QFormLayout(self.profile_outputs)
        self.profile_output_widgets={};self.profile_output_rules={};self.profile_output_inverts={};l.addWidget(self.profile_outputs)
        l.addStretch()

    def update_spindle_page(self,_=None):
        mode=self.spindle_type.currentData()
        self.spindle_pages.setCurrentIndex(1 if mode=='stepdir' else 0)
        self.spindle_pages.setEnabled(self.sp['enabled'].isChecked())
        self.sp['rpm'].setEnabled(self.sp['enabled'].isChecked())
        if hasattr(self,'profile_output_widgets'):
            c={'board_profile':self.board_choice.currentData(),'spindle':{'type':mode}}
            suppressed=suppressed_gpio(c)
            for index,combo in self.profile_output_widgets.items():self.profile_output_form.setRowVisible(combo.parentWidget(),index not in suppressed)
            self.profile_outputs.setVisible(any(index not in suppressed for index in self.profile_output_widgets))

    def io_page(self):
        l=self.page('04  输入输出','选择Mesa主卡或SD智能串口板分配输入输出功能。轴和手轮专用针脚不在通用IO列表显示。')
        self.io=QTableWidget(16,5);self.io.setHorizontalHeaderLabels(['输入针脚','输入功能','输入反相','输出针脚','输出功能'])
        self.io.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        for i in range(16):
            for col,value in [(0,f'input-{i:02}'),(3,f'output-{i:02}')]:
                item=QTableWidgetItem(value);item.setFlags(item.flags() & ~Qt.ItemIsEditable);self.io.setItem(i,col,item)
            incoming=SignalCombo()
            for value,label in input_roles().items():incoming.addItem(label,value)
            outgoing=SignalCombo()
            for value,label in output_roles().items():outgoing.addItem(label,value)
            self.io.setCellWidget(i,1,incoming);self.io.setCellWidget(i,2,QCheckBox());self.io.setCellWidget(i,4,outgoing)
        self.io_tabs=QTabWidget();self.io_tabs.setObjectName('io_tabs');l.addWidget(self.io_tabs)
        self.sd_page=QWidget()
        sd_layout=QVBoxLayout(self.sd_page);remote_form=QFormLayout();sd_layout.addLayout(remote_form)
        for key,label in [('remote_model','SD从板型号'),('remote_prefix','实际从板HAL前缀'),('sserial','串口0通道模式')]:remote_form.addRow(label,self.hw[key])
        hint=QLabel('按实际接线选择输入输出功能；配置随工程保存，关闭SD后保留分配。');hint.setWordWrap(True);sd_layout.addWidget(hint)
        sd_layout.addWidget(self.io)
        self.mesa_io=QTableWidget(0,6)
        self.mesa_io.setHorizontalHeaderLabels(['连接器 / 针脚','Mesa GPIO','固件功能 / 状态','类型','信号功能','反相'])
        self.mesa_io.setColumnHidden(0,True)
        self.mesa_io.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.mesa_io.horizontalHeader().setSectionResizeMode(4,QHeaderView.Stretch)
        self.io_tabs.addTab(self.mesa_io,'Mesa 主卡 IO')
        self.custom_io=QTableWidget(0,6)
        self.custom_io.setHorizontalHeaderLabels(['连接器 / 针脚','Mesa GPIO','固件功能 / 状态','类型','信号功能','反相'])
        self.custom_io.setColumnHidden(0,True)
        self.custom_io.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.custom_io.horizontalHeader().setSectionResizeMode(4,QHeaderView.Stretch)
        self.custom_io_page=QWidget();custom_layout=QVBoxLayout(self.custom_io_page)
        hint=QLabel('功能由已烧入的FPGA固件决定；刷固件后重新读取。轴引脚按StepGen通道配置，不作为普通GPIO；串口引脚由SD板通道设置使用。');hint.setWordWrap(True);custom_layout.addWidget(hint)
        row=QHBoxLayout()
        self.custom_read_button=button('读取Mesa卡信息（自定义引脚）',self.read_custom_pins);row.addWidget(self.custom_read_button)
        row.addWidget(button('到轴页配置',lambda:self.nav.setCurrentRow(1)));row.addStretch();custom_layout.addLayout(row)
        self.custom_resources=QLabel('');custom_layout.addWidget(self.custom_resources)
        custom_layout.addWidget(self.custom_io)
        self.io_tabs.addTab(self.custom_io_page,'自定义引脚')
        self.io_tabs.addTab(self.sd_page,'SD 智能串口板')
        self.gpio_hint=QLabel('先读取Mesa板卡或导入readhmid记录，主卡针脚将按实际固件显示。');self.gpio_hint.setWordWrap(True);l.addWidget(self.gpio_hint)
        l.addWidget(button('按当前硬件资源刷新针脚',self.refresh_gpio))

    def remote_toggled(self,enabled):
        if hasattr(self,'io'):self.io.setEnabled(enabled)
        for key in ('remote_model','remote_prefix','sserial'):self.hw[key].setEnabled(enabled)
        if hasattr(self,'ss_scan'):self.ss_scan.setEnabled(enabled)
        self.sd_config_button.setEnabled(enabled)
        if hasattr(self,'sd_page'):
            index=self.io_tabs.indexOf(self.sd_page)
            self.io_tabs.setTabVisible(index,enabled)
            if not enabled:self.io_tabs.setCurrentIndex(0)

    def show_sd_config(self):
        if self.remote_enabled.isChecked():
            self.nav.setCurrentRow(3)
            self.io_tabs.setCurrentWidget(self.sd_page)

    def collect_gpio(self):
        entries=[]
        for table in (self.mesa_io,self.custom_io):
            for row in range(table.rowCount()):
                direction=table.cellWidget(row,3).currentData()
                if direction:
                    entries.append(dict(io=table.item(row,1).data(Qt.UserRole),direction=direction,
                                        role=table.cellWidget(row,4).currentData(),invert=table.cellWidget(row,5).isChecked()))
        profile=PROFILES.get(self.board_choice.currentData())
        role=self.mpg_input29.currentData() or ''
        if role or profile and 29 in profile.fixed_gpio:
            entries.append(dict(io=29,direction='in',role=role,invert=self.mpg_input29_invert.isChecked()))
        for index,combo in self.profile_output_widgets.items():
            rule=self.profile_output_rules[index]
            entries.append(dict(io=index,direction=rule['direction'],invert=self.profile_output_inverts[index].isChecked(),role=combo.currentData()))
        return entries

    def profile_changed(self,_=None):
        if not hasattr(self,'custom_io'):return
        current=self.collect();previous=self.c.get('board_profile','custom')
        current['board_profile']=previous
        self.profile_drafts[previous]=json.loads(json.dumps(current))
        key=self.board_choice.currentData()
        if key in self.profile_drafts:
            self.c=json.loads(json.dumps(self.profile_drafts[key]))
        else:
            self.c=current;self.c['board_profile']=key;self.c['mesa_gpio']=[]
            self.c['discovery']=default_discovery(key);self.c['remote_enabled']=False
            if key in PROFILES:
                self.c['board']=PROFILES[key].device;self.c['host']='hm2_'+self.c['board']+'.0'
                modules=(self.c['discovery'] or {}).get('modules',{})
                for field,tag in [('stepgens','stepgen'),('pwmgens','pwmgen'),('encoders','encoder')]:self.c[field]=modules.get(tag,0)
        self.populate()

    def sync_profile_controls(self):
        profile=profile_for(self.c)
        field=self.hw['board'];field.setVisible(profile is None)
        self.hardware_form.labelForField(field).setVisible(profile is None)
        self.io_tabs.setTabVisible(self.io_tabs.indexOf(self.custom_io_page),bool(profile and profile.custom_pins))
        fixed=profile.fixed_pwm_channel if profile else None
        self.sp['channel'].setEnabled(fixed is None)
        if fixed is not None:self.sp['channel'].setValue(fixed)

    def show_custom_axis(self,channel):
        self.nav.setCurrentRow(1)
        for i in range(self.axis_table.rowCount()):
            if int(self.axis_table.item(i,self.axis_keys.index('stepgen')).text())==channel:
                self.axis_tabs.setCurrentIndex(i);break
        self.status(f'请在轴页选择要使用StepGen {channel}的轴；不会自动增加轴或修改已有绑定。')

    def read_custom_pins(self):
        try:
            c=self.collect();profile=profile_for(c)
            if not profile or not profile.custom_pins:raise ValueError('当前板卡没有自定义引脚定义')
            self.c=c;expected=(c['board_profile'],c['board'],c['ip'])
            self.start_job(lambda emit:discovery.read_custom_pins(c['board'],c['ip'],profile.custom_pins),
                           lambda result:self.custom_discovered(result,expected))
            self.custom_read_button.setEnabled(False)
            self.status('正在读取自定义引脚及板卡资源；不扫描Smart Serial。')
        except Exception as exc:self.error(str(exc))

    def custom_discovered(self,result,expected):
        c=self.collect()
        if (c.get('board_profile','custom'),c['board'],c['ip'])!=expected:
            self.status('板卡选择或IP已改变，忽略旧读取结果。');return
        self.discovered(result)
        self.io_tabs.setCurrentWidget(self.custom_io_page)
        self.status('自定义引脚和资源数量已更新；StepGen轴输出请在轴页配置。')

    def refresh_gpio(self,preserve=True):
        if not hasattr(self,'custom_io') or not hasattr(self,'mpg_enabled'):return
        c=self.collect() if preserve else self.c
        profile=profile_for(c);chosen={v['io']:v for v in effective_gpio(c)}
        custom=set(profile.custom_pins if profile else ())
        spindle={i for i,r in (profile.fixed_gpio.items() if profile else []) if r.get('page')=='spindle'}
        pins=list((c.get('discovery') or {}).get('pins',[]));known={p['io'] for p in pins}
        pins += [dict(io=i,secondarymodulename='unknown') for i in chosen if i not in known]
        for table,rows in [(self.mesa_io,[p for p in pins if p['io'] not in custom|spindle|{29}]),
                           (self.custom_io,[p for p in pins if p['io'] in custom])]:
            table.setRowCount(0)
            for pin in rows:
                row=table.rowCount();table.insertRow(row)
                index=pin['io'];v=chosen.get(index,{})
                reason=gpio_reason(c,pin) if index in known else '针脚未发现'
                module=pin.get('secondarymodulename','').lower();channel=pin.get('channel','')
                function=' '.join(str(pin.get(k,'')) for k in ('secondarymodulename','channel','secondaryfunctionname')).strip()
                values=['',f'{index:03}',reason or ('可用 GPIO' if module in ('none','') else function)]
                for col,value in enumerate(values):
                    item=QTableWidgetItem(value);item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                    if col==1:item.setData(Qt.UserRole,index)
                    table.setItem(row,col,item)
                direction=QComboBox()
                for label,key in [('未使用',''),('GPIO 输入','in'),('GPIO 输出','out'),('GPIO 开漏输出','open-drain')]:direction.addItem(label,key)
                direction.setCurrentIndex(max(0,direction.findData(v.get('direction',''))))
                roles=SignalCombo();invert=QCheckBox();invert.setChecked(v.get('invert',False))
                table.setCellWidget(row,3,direction);table.setCellWidget(row,4,roles);table.setCellWidget(row,5,invert)
                def fill_roles(_=None,direction=direction,roles=roles,value=v.get('role','')):
                    previous=roles.currentData() if roles.count() else value
                    roles.set_roles(input_roles(len(c['axes'])) if direction.currentData()=='in' else output_roles(len(c['axes'])),previous)
                    roles.setEnabled(bool(direction.currentData()))
                fill_roles();direction.currentIndexChanged.connect(fill_roles)
                direction.setEnabled(not reason or bool(v));roles.setEnabled(bool(direction.currentData()))
                direction.setToolTip(reason);invert.setEnabled(not reason or bool(v))
                rule=profile.fixed_gpio.get(index) if profile else None
                if rule:
                    direction.setEnabled(False)
                    if rule.get('lock_invert'):invert.setEnabled(False)
                occupied=bool(reason) and (module in ('stepgen','encoder','qcount','qcounter','pwm','pwmgen') or '专用' in reason)
                table.setRowHidden(row,table is self.mesa_io and occupied and not bool(v))
                if table is self.custom_io and reason and not v:
                    table.item(row,2).setText(function+'（固件固定）')
                    direction.clear();direction.addItem(module+' '+str(channel),'')
                    direction.setEnabled(False);invert.setEnabled(False)
                    if module=='stepgen' and str(channel).isdigit():
                        target=button('到轴页配置 StepGen '+str(channel),lambda checked=False,ch=int(channel):self.show_custom_axis(ch))
                        table.setCellWidget(row,4,target)
        self.custom_resources.setText(f'固件资源：StepGen {c["stepgens"]} 个；PWM {c["pwmgens"]} 个；编码器 {c["encoders"]} 个。StepGen为硬件通道数量，机床轴数在轴页设置。')
        while self.profile_output_form.rowCount():self.profile_output_form.removeRow(0)
        self.profile_output_widgets={}
        self.profile_output_rules={}
        self.profile_output_inverts={}
        for index in sorted(spindle):
            rule=profile.fixed_gpio[index]
            saved=chosen.get(index,next((v for v in c.get('mesa_gpio',[]) if v['io']==index),dict(role=rule.get('default_role',''),invert=rule.get('invert',False))))
            combo=SignalCombo();combo.set_roles(output_roles(len(c['axes'])),saved['role'])
            label=f'IO{index} 固定输出'+(' / 固定反相' if rule.get('invert') and rule.get('lock_invert') else '')
            field=QWidget();row=QHBoxLayout(field);row.setContentsMargins(0,0,0,0);row.addWidget(combo,1)
            invert=QCheckBox('反相');invert.setChecked(saved.get('invert',False));invert.setEnabled(not rule.get('lock_invert',False));row.addWidget(invert)
            self.profile_output_form.addRow(label,field);self.profile_output_widgets[index]=combo;self.profile_output_rules[index]=rule;self.profile_output_inverts[index]=invert
        self.update_spindle_page()
        if profile:self.gpio_hint.setText(profile.label+'：固定输入方向不可修改；主轴输出在主轴页，自定义引脚在独立页签。')
        else:self.gpio_hint.setText('读取Mesa板卡后按实际固件显示引脚；轴和手轮占用的针脚不在通用IO中显示。')

    def mpg_page(self):
        l=self.page('05  手轮MPG','固定VGA手轮使用Mesa编码器00；可选3、4、5轴，IO29作为独立固定输入配置。')
        self.mpg_enabled=QCheckBox('启用手轮MPG（编码器00）');l.addWidget(self.mpg_enabled)
        form=QFormLayout();l.addLayout(form)
        self.mpg_axes=QComboBox()
        for count,letters in [(3,'XYZ'),(4,'XYZA'),(5,'XYZAB')]:self.mpg_axes.addItem(f'{count}轴手轮 / {letters}',count)
        form.addRow('手轮轴数',self.mpg_axes)
        group=QGroupBox('IO29 固定输入');io_form=QFormLayout(group);l.addWidget(group)
        io_form.addRow('方向',QLabel('输入（固定）'))
        self.mpg_input29=SignalCombo();self.mpg_input29.set_roles(input_roles())
        self.mpg_input29_invert=QCheckBox('输入反相')
        io_form.addRow('输入功能',self.mpg_input29);io_form.addRow(self.mpg_input29_invert)
        label=QLabel('X/Y/Z选轴：IO25/23/21；轴选3（A）：IO22；轴选4（B）：IO24。\n倍率：IO28/20；三档0.025、0.0025、0.00025，同时有效时为0。\n手轮轴数不能超过轴页配置；IO29功能独立于手轮启用状态，不预设为急停。')
        label.setWordWrap(True);l.addWidget(label)
        self.mpg_text=QPlainTextEdit();self.mpg_text.setReadOnly(True);l.addWidget(self.mpg_text,1)
        self.mpg_enabled.toggled.connect(lambda _:self.refresh_gpio())
        for signal in (self.mpg_enabled.toggled,self.mpg_axes.currentIndexChanged,self.mpg_input29.currentIndexChanged,self.mpg_input29_invert.toggled):signal.connect(self.update_mpg_preview)

    def update_mpg_preview(self,_=None):
        if not hasattr(self,'mpg_text'):return
        from config_core import fixed_mpg
        from io_config import input_targets
        host=self.hw['host'].text() or self.c['host']
        text=fixed_mpg(host,self.mpg_axes.currentData()) if self.mpg_enabled.isChecked() else '# 手轮MPG未启用\n'
        role=self.mpg_input29.currentData() or ''
        text+=f'\nsetp {host}.gpio.029.is_output FALSE\n'
        if role:
            pin=f'{host}.gpio.029.'+('in_not' if self.mpg_input29_invert.isChecked() else 'in')
            count=self.axis_table.rowCount()
            if role not in input_roles(count):text+='# IO29功能与当前轴结构不匹配，请重新选择\n'
            else:
                targets=input_targets(role,count)
                if role=='all-home-limit':
                    targets=[f'joint.{i}.home-sw-in' for i in range(count)]+['io-limit-home.in-0']
                    text+='# 共用限位的回零屏蔽逻辑由生成器统一创建，完整连接见检查与导出页\n'
                text+='net mesa-input-029 '+pin+' => '+' '.join(targets)+'\n'
        self.mpg_text.setPlainText(text)

    def preview_page(self):
        l=self.page('06  检查与导出','按所选LinuxCNC操作界面生成整机配置及可重新打开的project.json。导出要求新目录，保留已有配置和手工修改。')
        row=QHBoxLayout();row.addWidget(button('检查并预览',self.preview));row.addWidget(button('导出LinuxCNC配置',self.export_config));row.addStretch();l.addLayout(row)
        self.checks=QLabel();self.checks.setWordWrap(True);l.addWidget(self.checks);self.tabs=QTabWidget();l.addWidget(self.tabs,1)

    def upgrade_page(self):
        l=self.page('07  SD固件升级','正式链路：以太网 → Mesa → Smart Serial → SD板。需要配套Mesa版Boot V3；原USB Boot V2不支持转发。请在Debian电脑退出LinuxCNC后操作。')
        form=QFormLayout();l.addLayout(form)
        self.up_ip=QLineEdit(self.c['ip']);form.addRow('升级目标Mesa IP',self.up_ip)
        self.up_channel=number(0,True,0,7);form.addRow('Smart Serial通道 / 端口0',self.up_channel)
        self.up_model=QComboBox();self.up_model.addItems(['SD01','SD02']);form.addRow('目标型号',self.up_model)
        self.package=QLineEdit();self.package.setPlaceholderText('请选择升级包；发行版不包含固件');form.addRow('升级包',self.package)
        self.up_model.currentTextChanged.connect(self.upgrade_model_changed)
        self.machine_stopped=QCheckBox('已停机并退出LinuxCNC，允许进入Mesa维护模式');l.addWidget(self.machine_stopped)
        row=QHBoxLayout();row.addWidget(button('读取Mesa链路信息',self.probe_mesa));row.addWidget(button('选择并检查升级包',self.choose_package))
        self.flash=button('通过Mesa开始升级',self.upgrade);row.addWidget(self.flash);l.addLayout(row)
        self.package_info=QLabel('首次需用SWD安装匹配型号的新Boot。之后可经Mesa进入维护、上传、确认和启动；完成后重新启动LinuxCNC恢复硬件配置。')
        self.package_info.setWordWrap(True);l.addWidget(self.package_info)
        self.up_log=QPlainTextEdit();self.up_log.setReadOnly(True);l.addWidget(self.up_log)

    def probe_mesa(self):
        try:
            import mesa_update
            address=self.up_ip.text().strip()
            self.start_job(lambda emit:mesa_update.probe(address),lambda result:self.up_log.appendPlainText(json.dumps(result,ensure_ascii=False,indent=2)))
        except Exception as exc:self.error(str(exc))

    def populate(self):
        self.board_choice.blockSignals(True);self.board_choice.setCurrentIndex(self.board_choice.findData(self.c.get('board_profile','custom')));self.board_choice.blockSignals(False)
        for k,w in self.hw.items():
            if isinstance(w,QComboBox):w.setCurrentText(str(self.c[k]))
            elif isinstance(w,QSpinBox):w.setValue(self.c[k])
            else:w.setText(str(self.c[k]))
        self.pb_template.setText(self.c.get('probe_basic_template',''))
        self.update_display_options()
        self.pdm_frequency.setValue(self.c.get('pdm_frequency',6000000))
        self.dpll_timer.setValue(self.c.get('dpll_timer_us',-50))
        self.control_mode.setCurrentIndex(self.control_mode.findData(self.c.get('stepgen_control','position')))
        self.display_box.setCurrentIndex(self.display_box.findData(self.c.get('display','axis')))
        self.remote_enabled.blockSignals(True);self.remote_enabled.setChecked(self.c.get('remote_enabled',True));self.remote_enabled.blockSignals(False)
        self.mpg_enabled.blockSignals(True);self.mpg_enabled.setChecked(self.c['mpg']['enabled']);self.mpg_enabled.blockSignals(False)
        self.remote_toggled(self.remote_enabled.isChecked())
        self.layout_choice.setCurrentText(''.join(a['axis'] for a in self.c['axes']))
        self.fill_axes()
        self.spindle_type.blockSignals(True);self.spindle_type.setCurrentIndex(self.spindle_type.findData(self.c['spindle'].get('type','analog')));self.spindle_type.blockSignals(False)
        for key,editor in self.servo_fields.items():editor.setValue(self.c['spindle'].get(key,spindle_config.SERVO_DEFAULTS[key]))
        self.pwm_invert.setChecked(self.c['spindle'].get('invert_pwm',False))
        self.sp['enabled'].setChecked(self.c['spindle']['enabled'])
        for k in ('channel','rpm','frequency'):self.sp[k].setValue(self.c['spindle'][k])
        self.update_spindle_page()
        for i in range(16):
            self.io.cellWidget(i,1).set_roles(input_roles(len(self.c['axes'])),self.c['inputs'][i]['role'])
            self.io.cellWidget(i,4).set_roles(output_roles(len(self.c['axes'])),self.c['outputs'][i])
            self.io.cellWidget(i,2).setChecked(self.c['inputs'][i]['invert'])
        self.mpg_axes.setCurrentIndex(self.mpg_axes.findData(self.c['mpg'].get('axes',3)))
        input29=self.c['mpg'].get('input29',{})
        self.mpg_input29.set_roles(input_roles(len(self.c['axes'])),input29.get('role',''))
        self.mpg_input29_invert.setChecked(input29.get('invert',False))
        self.update_mpg_preview()
        self.discovery_text.setPlainText((self.c.get('discovery') or {}).get('raw','尚未读取板卡；可离线编辑。'))
        self.language_box.setCurrentIndex(1 if self.c.get('language',self.language)=='en' else 0)
        self.refresh_gpio(preserve=False)
        self.sync_profile_controls()
        self.set_language(self.c.get('language',self.language))

    def fill_axes(self):
        self.axis_table.setRowCount(len(self.c['axes']))
        if hasattr(self,'mpg_input29'):self.mpg_input29.set_roles(input_roles(len(self.c['axes'])),self.mpg_input29.currentData() or '')
        while self.axis_tabs.count():
            widget=self.axis_tabs.widget(0);self.axis_tabs.removeTab(0);widget.deleteLater()
        labels=dict(zip(self.axis_keys,['轴','StepGen通道','脉冲当量 / 单位（必须填写）','最大速度 / 分钟','最大加速度 / 秒²','负向行程','正向行程','最终回零位置 HOME','开关位置 HOME_OFFSET','最终回零速度 / 分钟（0使用最大速度）','搜索速度 / 分钟（有符号）','锁存速度 / 分钟（有符号）','回零顺序','FERROR','MIN_FERROR','脉冲宽度 / ns','脉冲间隔 / ns','方向建立 / ns','方向保持 / ns']))
        motor_keys=['stepgen','scale','velocity','acceleration','steplen','stepspace','dirsetup','dirhold']
        integers={'stepgen','home_sequence','steplen','stepspace','dirsetup','dirhold'}
        for i,a in enumerate(self.c['axes']):
            for j,key in enumerate(self.axis_keys):
                item=QTableWidgetItem(str(a.get(key, a['home'] if key=='home_offset' else 0. if key=='home_final_velocity' else 1. if key=='ferror' else .25)));self.axis_table.setItem(i,j,item)
                if key=='axis':item.setFlags(item.flags() & ~Qt.ItemIsEditable)
            axis_page=QWidget();layout=QVBoxLayout(axis_page)
            title=QLabel(f'{a["axis"]} 轴 / 关节 {i}');title.setObjectName('heading');layout.addWidget(title)
            settings=QTabWidget();settings.setObjectName('axis_settings');layout.addWidget(settings)
            for title,keys in [('电机与驱动器',motor_keys),('行程与回零',[k for k in self.axis_keys if k not in motor_keys and k!='axis'])]:
                page=QWidget();form=QFormLayout(page)
                for key in keys:
                    factor=60 if key in ('velocity','search','latch','home_final_velocity') else 1
                    initial=float(self.axis_table.item(i,self.axis_keys.index(key)).text())*factor
                    editor=number(int(initial) if key in integers else initial,key in integers)
                    if key=='stepgen':
                        editor.setMinimum(0);editor.setMaximum(max(self.c['stepgens']-1,int(initial),0))
                    column=self.axis_keys.index(key)
                    editor.valueChanged.connect(lambda value,row=i,col=column,factor=factor:self.axis_table.item(row,col).setText(str(value/factor if factor!=1 else value)))
                    label=labels[key]
                    if factor==60:label += ' (degree)' if a['axis'] not in 'XYZ' else ' (mm)'
                    form.addRow(label,editor)
                settings.addTab(page,title)
            layout.addStretch()
            self.axis_tabs.addTab(axis_page,a['axis'])

    def collect(self):
        c=json.loads(json.dumps(self.c))
        for k,w in self.hw.items():
            c[k]=w.currentText() if isinstance(w,QComboBox) else w.value() if isinstance(w,QSpinBox) else w.text().strip()
        axes=[]
        ints={'stepgen','home_sequence','steplen','stepspace','dirsetup','dirhold'}
        for i in range(self.axis_table.rowCount()):
            a={}
            for j,k in enumerate(self.axis_keys):
                text=self.axis_table.item(i,j).text().strip()
                a[k]=text if k=='axis' else int(text) if k in ints else float(text)
            axes.append(a)
        c['axes']=axes;c['spindle']={'enabled':self.sp['enabled'].isChecked(),'type':self.spindle_type.currentData(),**{k:self.sp[k].value() for k in ('channel','rpm','frequency')},**{key:editor.value() for key,editor in self.servo_fields.items()}}
        c['inputs']=[dict(role=self.io.cellWidget(i,1).currentData(),invert=self.io.cellWidget(i,2).isChecked()) for i in range(16)]
        c['outputs']=[self.io.cellWidget(i,4).currentData() for i in range(16)]
        c['board_profile']=self.board_choice.currentData()
        c.pop('estop_mode',None) # Ignore the removed temporary UI option in old drafts.
        c['spindle']['invert_pwm']=self.pwm_invert.isChecked()
        c['dpll_timer_us']=self.dpll_timer.value()
        c['pdm_frequency']=self.pdm_frequency.value()
        c['stepgen_control']=self.control_mode.currentData()
        c['display']=self.display_box.currentData()
        c['probe_basic_template']=self.pb_template.text().strip()
        c['remote_enabled']=self.remote_enabled.isChecked()
        c['mpg']={'enabled':self.mpg_enabled.isChecked(),'axes':self.mpg_axes.currentData(),'input29':{'role':self.mpg_input29.currentData() or '','invert':self.mpg_input29_invert.isChecked()}}
        c['mesa_gpio']=self.collect_gpio()
        return c

    def apply_axes(self):
        try:
            self.c=self.collect();existing={a['axis']:a for a in self.c['axes']}
            self.c['axes']=[existing.get(a,axis_defaults(a,i)) for i,a in enumerate(self.layout_choice.currentText())];self.fill_axes()
            for i in range(16):
                self.io.cellWidget(i,1).set_roles(input_roles(len(self.c['axes'])),self.c['inputs'][i]['role'])
                self.io.cellWidget(i,4).set_roles(output_roles(len(self.c['axes'])),self.c['outputs'][i])
            self.refresh_gpio()
        except Exception as exc:self.error(str(exc))

    def new(self):
        self.c=defaults();self.c['language']=self.language;self.populate();self.tabs.clear();self.checks.setText('');self.nav.setCurrentRow(7)

    def open_project(self):
        path,_=QFileDialog.getOpenFileName(self,self.tr_text('打开工程'),filter=self.tr_text('工程JSON (*.json)'))
        if not path:return
        try:
            c=json.loads(Path(path).read_text(encoding='utf-8-sig'))
            if c.get('schema')!=1:raise ValueError('未知工程格式')
            errors,_=validate(c)
            self.c=c;self.populate();self.nav.setCurrentRow(7)
            if errors:self.status('工程已打开，导出前仍需修正：'+'；'.join(errors))
        except Exception as exc:self.error(str(exc))

    def save_project(self):
        try:
            c=self.collect();path,_=QFileDialog.getSaveFileName(self,self.tr_text('保存工程'),'project.json',self.tr_text('工程JSON (*.json)'))
            if path:Path(path).write_text(json.dumps(c,ensure_ascii=False,indent=2),encoding='utf-8');self.c=c
        except Exception as exc:self.error(str(exc))

    def preview(self):
        try:
            c=self.collect();errors,warnings=validate(c);self.checks.setText(self.tr_text('\n'.join(['错误：'+e for e in errors]+['提示：'+w for w in warnings])));self.tabs.clear();self.nav.setCurrentRow(5)
            if errors:return
            for name,content in generate(c).items():
                if name=='project.json':continue
                text=QPlainTextEdit(content);text.setReadOnly(True);self.tabs.addTab(text,name)
            translate_widgets(self,self.language)
            self.c=c
        except Exception as exc:self.error(str(exc))

    def export_config(self):
        try:
            c=self.collect();generate(c)
            parent=QFileDialog.getExistingDirectory(self,self.tr_text('选择导出父目录（将创建工程名子目录）'),str(Path.home()/'linuxcnc/configs'))
            if not parent:return
            path=export(c,Path(parent)/c['name']);self.status('已导出：'+str(path));QMessageBox.information(self,self.tr_text('导出完成'),self.tr_text(str(path)+'\n在Debian/LinuxCNC中打开'+c['name']+'.ini；运行前核对发现记录及接线。'))
        except Exception as exc:self.error(str(exc))

    def error(self,text):QMessageBox.critical(self,self.tr_text('操作未完成'),self.tr_text(text))

    def start_job(self,fn,done,logger=None):
        if self.job and self.job.isRunning():raise RuntimeError('后台任务正在进行，请等待完成')
        self.job=Job(fn);self.job.done.connect(done);self.job.failed.connect(self.task_failed)
        if logger:self.job.message.connect(lambda text:logger(self.tr_text(text)))
        self.job.finished.connect(self.task_finished);self.job.start()

    def log(self,text):self.up_log.appendPlainText(self.tr_text(text))

    def task_failed(self,text):
        self.log('错误：'+text);self.error(text)

    def task_finished(self):
        self.upgrading=False;self.flash.setEnabled(True)
        self.custom_read_button.setEnabled(True)

    def discover(self):
        try:
            self.c=self.collect();board,ip=self.c['board'],self.c['ip'];scan=self.ss_scan.isChecked() and self.remote_enabled.isChecked()
            self.status('正在读取板卡…')
            self.start_job(lambda emit:discovery.discover(board,ip,scan),self.discovered)
        except Exception as exc:self.error(str(exc))

    def discovered(self,d):
        self.c['discovery']=d;self.discovery_text.setPlainText(d['raw']+'\n'+d.get('sserial_raw','')+'\n'+d.get('sserial_error',''))
        for key,tag in [('stepgens','stepgen'),('pwmgens','pwmgen'),('encoders','encoder')]:
            if tag in d['modules']:self.hw[key].setValue(d['modules'][tag])
        self.c=self.collect();self.fill_axes();self.refresh_gpio()
        self.status(d.get('sserial_error') or '发现完成；物理针脚以右侧原始信息为准。')

    def import_discovery(self):
        path,_=QFileDialog.getOpenFileName(self,self.tr_text('导入mesaflash发现记录'),filter=self.tr_text('发现记录 (*.txt *.xml *.pin);;全部文件 (*)'))
        if path:
            try:self.discovered(discovery.parse(Path(path).read_text(encoding='utf-8-sig')))
            except Exception as exc:self.error(str(exc))

    def read_hal(self):
        try:self.start_job(lambda emit:discovery.live_hal(),self.hal_read)
        except Exception as exc:self.error(str(exc))

    def hal_read(self,text):
        found={}
        for token in text.split():
            board=identify_hal_pin(token)
            if board:found[board['hal_prefix']]=board
        self.discovery_text.setPlainText(text)
        host=self.hw['host'].text().strip()
        matching=[b for prefix,b in found.items() if prefix.startswith(host+'.')]
        if len(matching)==1:
            b=matching[0];self.hw['remote_model'].setCurrentText(b['model']);self.hw['remote_prefix'].setText(b['hal_prefix'])
            mode=['x']*8;mode[int(b['hal_prefix'].split('.')[-1])]='0';self.hw['sserial'].setText(''.join(mode))
            self.status('已识别：'+b['label']+'；采用实际HAL大小写。')
        else:self.status('未找到唯一SD从板；旧名称7i69不能自动判定型号，请核对。')

    def choose_package(self):
        path,_=QFileDialog.getOpenFileName(self,self.tr_text('检查升级包'),filter=self.tr_text('SD升级包 (*.fwup)'))
        if path:
            try:
                import firmware_update
                info=firmware_update.inspect(path);self.package.setText(path);self.package_info.setText(json.dumps(info,ensure_ascii=False))
            except Exception as exc:self.error(str(exc))

    def upgrade(self):
        try:
            import firmware_update,mesa_update
            if not self.machine_stopped.isChecked():raise ValueError('请先停止机器并退出LinuxCNC，再勾选维护接管确认')
            path=self.package.text().strip()
            if not path:raise ValueError('请先选择升级包；发行版不包含固件')
            address=self.up_ip.text().strip();channel=self.up_channel.value();model=self.up_model.currentText()
            firmware_update.inspect(path)
            self.start_job(lambda emit:mesa_update.deploy(path,address,channel,model,emit),lambda result:self.log(json.dumps(result,ensure_ascii=False)),self.up_log.appendPlainText)
            self.upgrading=True;self.flash.setEnabled(False)
        except Exception as exc:self.error(str(exc))

    def closeEvent(self,event):
        if self.job and self.job.isRunning():
            self.status('后台任务尚未完成，请等待；升级期间保持供电。');event.ignore()
        else:event.accept()


def setup_fonts():
    # Windows离线渲染器可能不枚举系统字体；显式加载系统自带字体，不分发字体文件。
    if os.name=='nt':
        candidate=Path(os.environ.get('WINDIR','C:/Windows'))/'Fonts/msyh.ttc'
        if candidate.exists():QFontDatabase.addApplicationFont(str(candidate))
    QApplication.setFont(QFont('Microsoft YaHei' if os.name=='nt' else 'Noto Sans CJK SC',10))


WIZARD_STYLE = """
QMainWindow { background: #f0f0f0; }
QWidget { font-size: 13px; }
QLabel#brand { font-size: 22px; font-weight: bold; color: #303030; padding: 8px; }
QLabel#step_title { font-size: 20px; font-weight: bold; padding: 8px; }
QLabel#welcome_title { font-size: 23px; font-weight: bold; margin: 22px 0; }
QLabel#heading { font-size: 18px; font-weight: bold; margin: 8px 0; }
QStackedWidget#wizard_pages { border: 1px solid #a9a9a9; background: #f7f7f7; }
QPushButton { padding: 6px 13px; min-height: 24px; }
QLineEdit,QComboBox,QSpinBox,QDoubleSpinBox { min-height: 25px; }
QTabBar::tab { padding: 8px 13px; }
QGroupBox { margin-top: 12px; padding-top: 12px; }
QPlainTextEdit { font-family: "DejaVu Sans Mono"; font-size: 12px; background: white; }
"""

def main():
    app=QApplication(sys.argv);app.setStyle('Fusion')
    setup_fonts()
    app.setStyleSheet(WIZARD_STYLE)
    w=Window();w.show();return app.exec()


if __name__=='__main__':sys.exit(main())
