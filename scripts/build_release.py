"""Build local release assets without installing anything on the host."""
import argparse,hashlib,importlib.metadata,json,os,platform,shutil,subprocess,tarfile
from pathlib import Path
from release_manifest import ROOT,files

def run(*args,**kwargs):subprocess.run(args,check=True,**kwargs)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--source-only',action='store_true');parser.add_argument('--reuse-bundle',action='store_true',help='Repackage after packaging-only edits; not after application changes');args=parser.parse_args()
    version=(ROOT/'VERSION').read_text().strip();out=ROOT/'dist';out.mkdir(exist_ok=True)
    source=out/f'FMesa-Config-{version}-source.tar.gz'
    with tarfile.open(source,'w:gz') as archive:
        for p in files():archive.add(p,arcname=f'FMesa-Config-{version}/'+p.relative_to(ROOT).as_posix(),recursive=False)
    if not args.source_only:
        if not args.reuse_bundle:
            run(os.sys.executable,'-m','PyInstaller','--noconfirm','--clean','--distpath',str(ROOT/'build/frozen'),'--workpath',str(ROOT/'build/pyinstaller'),str(ROOT/'packaging/fmesa-config.spec'),cwd=ROOT)
        bundle=ROOT/'build/frozen/fmesa-config'
        shutil.copytree(ROOT/'packaging/licenses',bundle/'_internal/licenses',dirs_exist_ok=True)
        run(str(bundle/'fmesa-config'),'--self-test',env={**os.environ,'QT_QPA_PLATFORM':'offscreen'})
        arch=subprocess.check_output(['dpkg','--print-architecture'],text=True).strip()
        info='\n'.join([f'Version: {version}',f'Architecture: {arch}',f'Platform: {platform.platform()}',f'Python: {platform.python_version()}',*sorted(f'{d.metadata["Name"]}=={d.version}' for d in importlib.metadata.distributions())])+'\n'
        (bundle/'BUILD-INFO.txt').write_text(info)
        for name in ('README.md','README_EN.md','THIRD_PARTY_NOTICES.md','LICENSE'):
            shutil.copy2(ROOT/name,bundle/name)
        shutil.copytree(ROOT/'docs',bundle/'docs',dirs_exist_ok=True,ignore=shutil.ignore_patterns('HAL_PNCCONF_AUDIT.md','STARTUP_DIAGNOSTICS.md','PNCCONF_REFERENCE.md','BOARD_PROFILES.md','SPINDLE_PROFILES.md'))
        portable=out/f'fmesa-config-{version}-linux-{arch}.tar.xz'
        with portable.open('wb') as output:
            compressor=subprocess.Popen(['xz','-T2','-3','-c'],stdin=subprocess.PIPE,stdout=output)
            try:
                with tarfile.open(fileobj=compressor.stdin,mode='w|') as archive:archive.add(bundle,arcname='fmesa-config')
            finally:compressor.stdin.close()
            if compressor.wait():raise RuntimeError('Portable archive compression failed')
        stage=ROOT/'build/deb-root'
        if stage.exists():shutil.rmtree(stage)
        app=stage/'usr/lib/fmesa-config';shutil.copytree(bundle,app,symlinks=True)
        binary=stage/'usr/bin';binary.mkdir(parents=True)
        wrapper=binary/'fmesa-config';wrapper.write_text('#!/bin/sh\nexec /usr/lib/fmesa-config/fmesa-config "$@"\n');wrapper.chmod(0o755)
        tools=stage/'usr/share/fmesa-config/tools';tools.mkdir(parents=True)
        for name in ('sserial_monitor.py','sserial_monitor_core.py'):shutil.copy2(ROOT/name,tools/name)
        monitor=binary/'fmesa-monitor';monitor.write_text('#!/bin/sh\nexec /usr/bin/python3 /usr/share/fmesa-config/tools/sserial_monitor.py "$@"\n');monitor.chmod(0o755)
        for src,dest in [('fmesa-config.desktop','usr/share/applications/fmesa-config.desktop'),('fmesa-config.svg','usr/share/icons/hicolor/scalable/apps/fmesa-config.svg')]:
            target=stage/dest;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/'packaging'/src,target)
        control=stage/'DEBIAN';control.mkdir()
        deb_version=version.replace('-test.','~test.')
        installed_size=sum(p.stat().st_size for p in stage.rglob('*') if p.is_file() and not p.is_symlink())//1024
        dependencies='libc6 (>= 2.36), libstdc++6, libgcc-s1, zlib1g, libglib2.0-0, libgl1, libegl1, libdbus-1-3, libfontconfig1, libfreetype6, libx11-6, libx11-xcb1, libxcb1, libxcb-cursor0, libxcb-icccm4, libxcb-image0, libxcb-keysyms1, libxcb-randr0, libxcb-render-util0, libxcb-shape0, libxcb-sync1, libxcb-xfixes0, libxcb-xinerama0, libxcb-xkb1, libxkbcommon0, libxkbcommon-x11-0, procps, fonts-noto-cjk'
        (control/'control').write_text(f'Package: fmesa-config\nVersion: {deb_version}\nArchitecture: {arch}\nMaintainer: FMesa Config contributors <84864797@users.noreply.github.com>\nSection: electronics\nPriority: optional\nInstalled-Size: {installed_size}\nDepends: {dependencies}\nRecommends: mesaflash, python3-tk\nHomepage: https://github.com/84864797/FMesa-Config\nDescription: Mesa and Smart Serial LinuxCNC configuration wizard\n Own desktop wizard with F7I92 board profiles and INI/HAL generation.\n Includes its Python and Qt runtime; LinuxCNC and mesaflash remain external.\n')
        run('dpkg-deb','--root-owner-group','-Zxz','-z3','--threads-max=2','--build',str(stage),str(out/f'fmesa-config_{deb_version}_{arch}.deb'))
        (out/'BUILD-INFO.txt').write_text(info)
    assets=[p for p in out.iterdir() if p.is_file() and p.name!='SHA256SUMS']
    (out/'SHA256SUMS').write_text(''.join(f'{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}\n' for p in sorted(assets)))
    print('Release assets:',out)

if __name__=='__main__':main()
