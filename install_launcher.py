"""安装当前用户菜单快捷方式，不修改系统文件。"""
from pathlib import Path
import os
root=Path(__file__).resolve().parent
if any(c in str(root) for c in '\n\r'):raise ValueError('Unsupported installation path')
def quote(path):
    return '"'+str(path).replace('\\','\\\\').replace('"','\\"').replace('`','\\`').replace('$','\\$').replace('%','%%')+'"'
target=Path(os.environ.get('XDG_DATA_HOME',Path.home()/'.local/share'))/'applications'
target.mkdir(parents=True,exist_ok=True)
(target/'fmesa-config.desktop').write_text(
    '[Desktop Entry]\nType=Application\nName=FMesa Config\nName[zh_CN]=FMesa 配置工具\n'
    f'Exec={quote(root/".venv/bin/python")} {quote(root/"app.py")}\n'
    'Terminal=false\nCategories=Development;Engineering;\n',encoding='utf-8')
print(target/'fmesa-config.desktop')
