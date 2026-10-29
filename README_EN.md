# FMesa Config

[中文](README.md) · [User guide](docs/USER_GUIDE_EN.md) · [Build instructions](docs/BUILD_EN.md) · [Development](docs/DEVELOPMENT_EN.md) · [Firmware](docs/FIRMWARE_EN.md)

Independent LinuxCNC configuration wizard for Debian 12, Mesa Ethernet boards,
F7I92 profiles and SD01/SD02 Smart Serial expansion boards. The UI and generation
rules follow PNCconf; this is its own application, not an embedded PNCconf UI.

This is a **test release**. Local software tests and package self-tests do not
constitute hardware acceptance for every machine, wiring arrangement or firmware.
No LinuxCNC HM2 driver is built, installed or replaced.

## Download and install

Open [Releases](https://github.com/84864797/FMesa-Config/releases).
For Debian 12 amd64, download the `.deb` and run:

```bash
sudo apt update
sudo apt install ./fmesa-config_0.2.0~test.1_amd64.deb
fmesa-config
```

The Debian package includes Python and Qt; apt installs the native GUI libraries
and fonts. Do not run the GUI as root. Alternatively extract the Linux portable
`.tar.xz`, enter its `fmesa-config` folder, and run `./fmesa-config`.
LinuxCNC and mesaflash are external tools, needed on the target hardware computer.

## Run and build from source

Python 3.11+ is required. Install `python3-venv`, `python3-pip`, git, Qt native
libraries and fonts as listed in the [Chinese README](README.md).

```bash
git clone https://github.com/84864797/FMesa-Config.git
cd FMesa-Config
bash install.sh
bash run.sh
# Native Debian build, outputs in dist/:
bash scripts/build.sh
```

Source distribution, portable bundle, Debian package and SHA256SUMS are produced.
See [BUILD_EN.md](docs/BUILD_EN.md) for dependencies, offline behavior and rebuild steps.

## Use

Create a project, select frontend and board, read the firmware resources, set
axis mechanics/homing, assign IO and optional SD IO, configure the spindle/MPG,
preview the generated files, and export to a **new** directory. Open its INI
with LinuxCNC. Initial axis pulse scales are zero and must be configured.

New PWM0 projects default to **inverted output at 200Hz**; verify polarity against
your actual circuit. An assigned external E-stop input controls the enable
input. With no assigned external E-stop input, generation uses PNCconf's software
E-stop loopback. This behavior has no separate mode selector.

The tool does not start LinuxCNC or flash a board automatically. Step/Dir spindle
feedback is estimated pulse output, not a measured motor encoder. Rigid tapping,
spindle orientation and external spindle encoder feedback are not implemented.
QtDragon templates currently support XYZ or XYZA.

```bash
fmesa-config --version
fmesa-config --self-test  # offline; no hardware access
fmesa-config --cli sample /tmp/project.json
# Edit the project to provide real pulse scales before validation/export.
QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest discover -p 'test_*.py' -q
```

PNCconf reference tests require its installed source and are skipped otherwise.
Optional HAL monitoring uses LinuxCNC's **system** Python and `python3-tk`:
`fmesa-monitor` for a Debian install, or `bash run_monitor.sh` from source.

Desktop code: GPL-2.0-or-later. Firmware source: its own MIT notices and dependency
licenses. See LICENSE and THIRD_PARTY_NOTICES.md.
