"""Explicit publish list excludes workstation configuration, caches and logs."""
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
DOCS=('USER_GUIDE.md','USER_GUIDE_EN.md','BUILD.md','BUILD_EN.md','DEVELOPMENT.md','DEVELOPMENT_EN.md','FIRMWARE.md','FIRMWARE_EN.md','PROBE_BASIC.md','PROBE_BASIC_EN.md')

def files():
    selected=list(ROOT.glob('*.py'))
    selected += [ROOT/name for name in ('README.md','README_EN.md','LICENSE','THIRD_PARTY_NOTICES.md','VERSION','requirements.txt','requirements-build.txt','install.sh','run.sh','run_monitor.sh','.gitignore')]
    for directory in ('scripts','packaging','tests/reference','updater','.github/workflows'):
        selected += [p for p in (ROOT/directory).rglob('*') if p.is_file() and '__pycache__' not in p.parts]
    selected += [ROOT/'docs'/name for name in DOCS]
    return sorted(set(p for p in selected if p.exists() and p.name!='FIRMWARE-MIT.txt'),key=lambda p:p.relative_to(ROOT).as_posix())

if __name__=='__main__':
    print('\n'.join(p.relative_to(ROOT).as_posix() for p in files()))
