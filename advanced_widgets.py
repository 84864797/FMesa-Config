"""Reusable typed option forms used inside wizard pages, not modal dialogs."""
from PySide6.QtWidgets import QWidget,QFormLayout,QCheckBox,QComboBox,QLineEdit,QPlainTextEdit,QDoubleSpinBox,QSpinBox
from PySide6.QtCore import Signal

class OptionForm(QWidget):
    changed=Signal()
    def __init__(self,defaults,labels,choices=None,parent=None):
        super().__init__(parent);self.editors={};self.defaults=defaults;form=QFormLayout(self);choices=choices or {}
        for key,value in defaults.items():
            if key in choices:
                editor=QComboBox()
                for text,data in choices[key]:editor.addItem(text,data)
                editor.currentIndexChanged.connect(lambda *_:self.changed.emit())
            elif isinstance(value,bool):editor=QCheckBox();editor.toggled.connect(lambda *_:self.changed.emit())
            elif isinstance(value,int):
                editor=QSpinBox();editor.setRange(-1000000000,1000000000);editor.valueChanged.connect(lambda *_:self.changed.emit())
            elif isinstance(value,float):
                editor=QDoubleSpinBox();editor.setDecimals(6);editor.setRange(-1e12,1e12);editor.valueChanged.connect(lambda *_:self.changed.emit())
            elif key=='mdi_commands':editor=QPlainTextEdit();editor.setMaximumHeight(100);editor.textChanged.connect(lambda *_:self.changed.emit())
            else:editor=QLineEdit();editor.textChanged.connect(lambda *_:self.changed.emit())
            self.editors[key]=editor;form.addRow(labels.get(key,key),editor)
        self.set_values({})
    def set_values(self,values):
        for key,editor in self.editors.items():
            value=values.get(key,self.defaults[key]);editor.blockSignals(True)
            if isinstance(editor,QComboBox):editor.setCurrentIndex(editor.findData(value))
            elif isinstance(editor,QCheckBox):editor.setChecked(value)
            elif isinstance(editor,(QSpinBox,QDoubleSpinBox)):editor.setValue(value)
            elif isinstance(editor,QPlainTextEdit):editor.setPlainText(value)
            else:editor.setText(value)
            editor.blockSignals(False)
    def values(self):
        result={}
        for key,editor in self.editors.items():
            result[key]=(editor.currentData() if isinstance(editor,QComboBox) else editor.isChecked() if isinstance(editor,QCheckBox) else editor.value() if isinstance(editor,(QSpinBox,QDoubleSpinBox)) else editor.toPlainText() if isinstance(editor,QPlainTextEdit) else editor.text())
        return result

MACHINE_LABELS=dict(require_homing='要求回零 / Require homing',restore_position='恢复关节位置 / Restore joint position',individual_homing='单独回零 / Individual homing',tool_change_with_spindle_on='换刀允许主轴运行 / Tool change with spindle on',tool_change_quill_up='换刀抬升Z轴 / Tool change quill up',random_toolchanger='随机刀库 / Random tool changer',mdi_commands='MDI命令（每行一条） / MDI commands',editor='程序编辑器 / Editor',image_filters='图像/Python过滤器 / Image and Python filters')
JOINT_LABELS=dict(drive='驱动方式 / Drive',pwm_channel='PWM通道 / PWM channel',output_scale='模拟输出比例 / Output scale',encoder='编码器通道（-1关闭） / Encoder channel (-1 off)',encoder_scale='编码器比例 / Encoder scale',home_use_index='编码器索引回零 / Home using index',backlash_enabled='反向间隙补偿 / Backlash compensation',backlash='反向间隙 / Backlash',comp_file='补偿表路径 / Compensation file',comp_type='补偿表类型（0/1） / Compensation type',p='P（-1为StepGen默认值） / P (-1 StepGen default)',i='I',d='D',ff0='FF0',ff1='FF1',ff2='FF2',bias='BIAS',deadband='DEADBAND',max_output='最大输出 / Maximum output',tandem_enabled='龙门双驱 / Tandem joint',tandem_stepgen='第二电机StepGen / Tandem StepGen',tandem_scale='第二电机脉冲当量 / Tandem step scale',tandem_home_offset='第二电机开关位置 / Tandem home offset')
