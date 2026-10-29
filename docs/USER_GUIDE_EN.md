# User guide

[中文](USER_GUIDE.md)

## Install and launch

Install the Debian package as described in README_EN.md, then launch **FMesa Config**
from the application menu or run `fmesa-config`. For a source checkout, use
`bash run.sh`. Do not launch the GUI with sudo. The wizard does not connect to a
board or launch LinuxCNC automatically.

## Configuration sequence

1. **Machine information:** enter a project name, axis layout and servo period.
   Linear axes use mm; rotary axes use degrees.
2. **Frontend:** choose AXIS, Gmoccapy, QtDragon, QtDragon HD or Probe Basic.
   Probe Basic needs its installed official template; see [PB setup](PROBE_BASIC_EN.md). The target machine
   must have the chosen LinuxCNC frontend installed. QtDragon templates currently
   support XYZ or XYZA only.
3. **Hardware discovery:** select F7I92 or a custom board, enter the board IP, and
   read the firmware resources. Resource counts describe hardware channels; they
   do not automatically add machine axes.
4. **Axes:** set a unique StepGen channel, pulses per machine unit, speed,
   acceleration, travel and homing parameters for each axis. A new pulse scale is
   zero and must be set before export. UI speeds are per minute; INI speeds are
   per second.
5. **Inputs/outputs:** assign ordinary GPIO on the main-card and custom-pin tabs.
   Enabling an SD board adds an SD tab in the same page. Input inversion is
   selectable. Do not assign a firmware StepGen/PWM/encoder pin as ordinary IO.
6. **Spindle:** analog mode uses the board's PWM-to-0–10V circuit; F7I92 uses PWM0.
   New projects default to **inverted PWM at 200Hz**. Verify this against your
   circuit. A Step/Dir spindle needs a separate StepGen channel, pulses/revolution,
   maximum RPM, acceleration and pulse timing.
7. **MPG handwheel:** select 3, 4 or 5 axes, after adding the corresponding machine
   axes. The fixed VGA wiring uses encoder00, GPIO25/23/21/22/24 for X/Y/Z/A/B,
   and GPIO28/20 for scale selection. GPIO29 is an ordinary input configured here.
8. **Preview/export:** resolve errors and export to a **new directory**. Existing
   directories are rejected to protect hand edits. Open the exported INI through
   LinuxCNC yourself.

## F7I92 wiring rules

- GPIO0: fixed inverted output, normally analog spindle forward. It is omitted
  when using the Step/Dir servo spindle profile.
- GPIO2/3: fixed inverted outputs, assigned on the main-card IO tab.
- GPIO14–19: fixed inputs with selectable input inversion.
- GPIO1: PWM0, with output inversion set on the spindle page.
- GPIO30–33: custom-pin page; read their actual firmware functions. Step/Dir pins
  belong to axis configuration; Smart Serial requires the proper TX/RX functions.

These are F7I92 product rules, not universal Mesa wiring. Changing a pin's FPGA
function requires matching firmware; this software cannot remap it arbitrarily.

## E-stop

The ordinary PNCconf rule is used automatically. If an external E-stop input is
assigned, TRUE permits reset and FALSE keeps E-stop asserted. Choose inversion
according to the actual circuit. If no active external E-stop input is assigned,
the generated HAL uses the software E-stop loopback. There is no separate mode
selector. An SD input on a disabled SD board is not an active external input.

## Save and reload

Save Project writes JSON. Export writes LinuxCNC files and a JSON copy. Editing
the project does not update a running LinuxCNC session or a previously exported
directory. Export a new directory and reload it through LinuxCNC after closing
the old session. The wizard does not change live HAL values.

## Troubleshooting

- **Qt xcb/missing shared library:** launch from a terminal to see the exact
  library name. Prefer installing the `.deb` with apt to resolve dependencies.
- **mesaflash missing:** install it on the target machine and check
  `mesaflash --help` in a terminal.
- **Discovery failure:** check the network interface, IP/subnet, power and actual
  FPGA firmware. A saved preset is not a fresh discovery result.
- **Smart Serial timeout:** reading the main board does not prove the remote is
  online. Exit LinuxCNC before scanning; check power, TX/RX, channel, mode and
  application firmware. Boot maintenance mode is not normal application mode.
- **Cannot reset E-stop:** inspect the exported HAL and actual input state. The
  frontend's external-E-stop error message is not proof that an input was assigned.
- **Wrong spindle speed:** compare PWM frequency, polarity and full-scale RPM
  against a known working configuration and the actual analog circuit.

## Optional read-only monitor

Installed package: `fmesa-monitor`. Source: `bash run_monitor.sh`. This needs
LinuxCNC's system Python `hal` module and `python3-tk`, not the bundled Python.
It observes HAL values and does not write them. Monitoring is separate from
firmware maintenance.
