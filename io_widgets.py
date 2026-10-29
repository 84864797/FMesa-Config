"""Grouped signal selector for both main-board and remote-board IO."""
from PySide6.QtWidgets import QComboBox,QMenu
from i18n import translate

class SignalCombo(QComboBox):
    def set_roles(self,roles,value=''):
        self.clear()
        for key,label in roles.items():self.addItem(label,key)
        if value and self.findData(value)<0:self.addItem('原分配（当前不可用）：'+value,value)
        self.setCurrentIndex(max(0,self.findData(value)))

    def build_menu(self):
        menu=QMenu(self)
        groups={}
        actions=[]
        for i in range(self.count()):
            key=self.itemData(i);label=self.itemText(i)
            if not key:group=''
            elif key.startswith(('home','neg:','pos:','both:','all-')):group='回零与限位'
            elif key.startswith(('din:','dout:')):group='数字输入输出'
            elif key.startswith('spindle'):group='主轴'
            elif key in ('flood','mist'):group='冷却'
            else:group='机器控制'
            parent=menu
            if group:
                if group not in groups:
                    submenu=QMenu(translate(group,getattr(self.window(),'language','zh')),menu)
                    actions.append(menu.addMenu(submenu));groups[group]=submenu
                parent=groups[group]
            action=parent.addAction(label);action.setCheckable(True);action.setChecked(i==self.currentIndex())
            actions.append(action)
            action.triggered.connect(lambda checked=False,index=i:self.setCurrentIndex(index))
        menu._groups=groups
        menu._actions=actions
        return menu

    def showPopup(self):
        menu=self.build_menu()
        menu.exec(self.mapToGlobal(self.rect().bottomLeft()))
        menu.deleteLater()
