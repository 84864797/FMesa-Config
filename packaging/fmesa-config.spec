# Rebuildable on Debian 12 with requirements-build.txt.
from pathlib import Path
root=Path(SPECPATH).parent
files=['VERSION','LICENSE','THIRD_PARTY_NOTICES.md']
datas=[(str(root/name),'.') for name in files]
datas += [(str(root/'packaging/licenses'),'licenses')]
a=Analysis([str(root/'launcher.py')],pathex=[str(root),str(root/'updater')],
    binaries=[],datas=datas,hiddenimports=['mesa_update','firmware_update','f407_update','serial_backend','serial.tools.list_ports'],
    hookspath=[],hooksconfig={},runtime_hooks=[],excludes=['tkinter','PySide6.QtWebEngineCore','PySide6.QtWebEngineWidgets'])
pyz=PYZ(a.pure)
exe=EXE(pyz,a.scripts,[],exclude_binaries=True,name='fmesa-config',debug=False,
    bootloader_ignore_signals=False,strip=False,upx=False,console=True)
coll=COLLECT(exe,a.binaries,a.datas,strip=False,upx=False,name='fmesa-config')
