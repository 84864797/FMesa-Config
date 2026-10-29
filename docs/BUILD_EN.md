# Source and build instructions

[中文](BUILD.md)

## Environment

The release targets **Debian 12 amd64**, built using Python 3.11. Runtime pins are
PySide6 6.8.3 and pyserial 3.x; build pins are PyInstaller 6.11.1 and
pyinstaller-hooks-contrib 2024.10. Python source runs directly: there is no need
to compile LinuxCNC, HM2 or a C/C++ driver. Packaging freezes this application's
Python/Qt runtime only.

For a different OS, CPU architecture or older glibc, rebuild on that target;
PyInstaller does not make this Debian binary universal.

## Dependencies

```bash
sudo apt update
sudo apt install git python3 python3-venv python3-pip binutils patchelf dpkg-dev build-essential libglib2.0-0 libegl1 libgl1 libdbus-1-3 libxkbcommon-x11-0 libxcb-cursor0 libxcb-icccm4 libxcb-image0 libxcb-keysyms1 libxcb-render-util0 libxcb-xinerama0 fonts-noto-cjk
```

## Run the source

```bash
git clone https://github.com/84864797/FMesa-Config.git
cd FMesa-Config
bash install.sh
bash run.sh
```

`install.sh` creates `.venv`, installs runtime dependencies there and creates a
current-user menu shortcut. It does not install pip packages into system Python.
Do not use sudo for this step. Initial dependency downloads require Internet.

## Build release assets

```bash
bash scripts/build.sh
```

This creates `.build-venv` from requirements-build.txt and produces in `dist/`:

- Full source archive.
- Linux portable archive including Python and Qt.
- Native `.deb` with menu entry and declared GUI-library dependencies.
- BUILD-INFO.txt and SHA256SUMS.

Intermediate files are in `build/`. The script does not install the output on
the host. Any failed subprocess stops the build. A software self-test checks Qt
startup, configuration generation and package parsing using non-executable synthetic data, with no board,
serial, HAL or LinuxCNC connection.

Only package source, without downloading Python dependencies:

```bash
python3 scripts/build_release.py --source-only
```

## Validate

```bash
build/frozen/fmesa-config/fmesa-config --version
build/frozen/fmesa-config/fmesa-config --self-test
QT_QPA_PLATFORM=offscreen .build-venv/bin/python -m unittest discover -p 'test_*.py' -q
cd dist
sha256sum -c SHA256SUMS
```

PNCconf reference tests require its installed source; they skip otherwise.
An optional Rust/Mesa integration test may also skip without its extra setup.
Skipped tests are not hardware validation.

The final `.deb` should also be tested in a clean Debian 12 amd64 VM: install with
`sudo apt install ./filename.deb`, launch from the menu, export a configuration,
and remove with `sudo apt remove fmesa-config`. Local extraction/self-tests do
not replace that clean-system installation check or real-machine acceptance.

## Automatic builds and releases

GitHub Actions builds in a Debian 12 container on pushes/PRs. A new VERSION on
main, or a `v…` tag, publishes a test release after a successful build. Existing
releases are not overwritten; bump VERSION for new assets. Build artifacts are
also available from Actions. A workflow file being committed is not proof that
its build or Release has succeeded: check the actual run result.

## Publish list

`scripts/release_manifest.py` explicitly selects source, tests, documentation,
packaging scripts and license notices. Firmware images, packages, manifests and firmware source archives are excluded. It excludes workstation
configs, virtual environments, caches, debug ELF and runtime logs. Review that
list before publishing. Do not include credentials or private machine settings.
