# Copyright and third-party notices

FMesa Config is distributed under **GNU GPL version 2 or any later version**.
See LICENSE. New project contributions: © 2026 FMesa Config contributors.

The configuration generator follows and adapts behavior from LinuxCNC PNCconf.
PNCconf notices include Copyright 2007 Jeff Epler and the 2014 Pncconf revamp by
Chris Morley. LinuxCNC/PNCconf are GPL-2.0-or-later. Reference source:
https://github.com/LinuxCNC/linuxcnc/tree/v2.9.8/src/emc/usr_intf/pncconf
The application does not ship, compile, replace or load LinuxCNC's HM2 driver.

Bundled binary distributions contain dynamically linked third-party components:

| Component | License / upstream source |
|---|---|
| CPython 3.11 | PSF license; https://www.python.org/downloads/source/ |
| Qt / PySide6 / Shiboken6 6.8.3 | LGPL-3.0 / GPL alternatives and Qt third-party notices; https://code.qt.io/cgit/qt/qtbase.git/?h=v6.8.3 and https://code.qt.io/cgit/pyside/pyside-setup.git/?h=v6.8.3 |
| pyserial 3.x | BSD-3-Clause; https://github.com/pyserial/pyserial |
| PyInstaller bootloader 6.11.1 | GPL-2.0-or-later with bootloader exception; https://github.com/pyinstaller/pyinstaller/tree/v6.11.1 |

The exact installed Python dependency versions are recorded in the release's
BUILD-INFO.txt. The PyInstaller build tools are not the application license.
Qt shared libraries are in the portable directory's `_internal/` tree and can
be replaced with compatible versions. Build instructions and source are provided
with each release; the application does not use static Qt linking.

Included STM32 SD firmware/source comes from the accompanying
firmware/mesa-v3/SD-Mesa-Firmware-Source.zip. Its newly written Rust code is MIT;
retain its included LICENSE and all dependency notices. It is a separate
experimental firmware project, not a prerequisite for configuring LinuxCNC.
Its license is copied to packaging/licenses/FIRMWARE-MIT.txt. Boot firmware is
not automatically installed by the desktop application or Debian package.
