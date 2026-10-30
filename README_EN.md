# FMesa Config

[中文](README.md) · [User guide](docs/USER_GUIDE_EN.md) · [Build instructions](docs/BUILD_EN.md) · [Development](docs/DEVELOPMENT_EN.md) · [Firmware](docs/FIRMWARE_EN.md) · [Probe Basic](docs/PROBE_BASIC_EN.md)

Independent LinuxCNC configuration wizard for Debian 12, Mesa Ethernet boards,
F7I92 profiles and SD01/SD02 Smart Serial expansion boards. The UI and generation
rules follow PNCconf; this is its own application, not an embedded PNCconf UI.

**This repository and its application packages do not include firmware BIN, FWUP, firmware source ZIP or manifest. Supply upgrade packages separately.**

This is a **test release**. Local software tests and package self-tests do not
constitute hardware acceptance for every machine, wiring arrangement or firmware.
No LinuxCNC HM2 driver is built, installed or replaced.

## Download and install

Open [Releases](https://github.com/84864797/FMesa-Config/releases).
For Debian 12 amd64, download the `.deb` and run:

```bash
sudo apt update
sudo apt install ./fmesa-config_0.3.0-test.2_amd64.deb
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

Create a project, select frontend (including Probe Basic) and board, read the firmware resources, set
axis mechanics/homing, assign IO and optional SD IO, configure the spindle/MPG,
preview the generated files, and export to a **new** directory. Open its INI
with LinuxCNC. Initial axis pulse scales are zero and must be configured.

New PWM0 projects default to **inverted output at 200Hz**; verify polarity against
your actual circuit. An assigned external E-stop input controls the enable
input. With no assigned external E-stop input, generation uses PNCconf's software
E-stop loopback. This behavior has no separate mode selector.

The tool does not start LinuxCNC or flash a board automatically. Without an external
encoder, Step/Dir spindle feedback is estimated pulse output. External encoder
feedback and speed PID are optional. Synchronized machining requires suitable
index wiring and commissioning; spindle orientation is not generated.
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

Desktop code: GPL-2.0-or-later. Firmware and firmware source are not distributed. See LICENSE and THIRD_PARTY_NOTICES.md.

Probe Basic requires its own installation and matching official machine template. See [PB setup](docs/PROBE_BASIC_EN.md); FMesa generates the manual-toolchange mill profile and copies its installed supporting assets.

## 0.3 advanced machine settings (test release)

- Basic information: require homing, restore joint position, individual homing, tool-change policies (spindle on, quill up, random pockets), MDI commands, editor, image/Python filters. Defaults still require homing and do not restore saved positions.
- Axis feedback/compensation/tandem tab: Step/Dir or PWM analog servo, dedicated encoder and index homing, PID gains, backlash OR compensation table, and secondary motor StepGen/scale/switch offset. Compensation files are copied into exported configurations.
- Tandem joints are numbered in coordinate order, such as X,Y,second Y,Z. Existing IO assignments retain their motor identity when tandem numbering changes; recheck all joint-number assignments. Each motor requires a separate home input. Negative HOME_SEQUENCE values synchronize homing; trivkins uses kinstype=BOTH. The secondary Step/Dir motor inherits velocity, timing and PID from the primary; its step scale and switch offset are independent.
- PWM servo axes require an available PWM channel, dedicated encoder, output scale, explicit PID gains and maximum output. F7I92 reserves its fixed PWM0 for the spindle; analog axes therefore require a suitable custom board.
- Spindle encoder/PID tab: counts per revolution, closed-loop speed control, PID and at-speed tolerance. Use quadrature counts, not the encoder nameplate line count. No encoder may be shared with MPG/axes. Feedback disabled preserves open-loop behavior. With feedback enabled, actual encoder velocity/position/index connect to speed-in/revs/index-enable; Step/Dir PID output is converted from RPM to rev/s. Synchronized machining additionally requires physical index wiring and suitable hardware; generated connections are not tapping acceptance tests.
- Index homing requires an index pin and a home switch. Backlash/compensation increases StepGen velocity and acceleration headroom to 2x, following PNCconf.
- Defaults/generation were compared against installed LinuxCNC 2.9 PNCconf source and tested offline. No machine motion, loop tuning or live startup was performed. Advanced settings require hardware-specific commissioning. Probe Basic remains an official-template manual-toolchange profile; ATC and spindle orientation are not generated.
