# Probe Basic (PB)

[中文](PROBE_BASIC.md)

## Install the frontend

Select **Probe Basic (QtPyVCP)** on FMesa's frontend page. Install Probe Basic and
QtPyVCP separately on the target LinuxCNC computer; they are not bundled into
FMesa's Python/Qt6 runtime.

Follow KCJ Engineering's [Debian 12 guide](https://kcjengr.github.io/probe_basic/debian_12_bookworm/index.html),
[Stable installation](https://kcjengr.github.io/probe_basic/debian_12_bookworm/installation/probe_basic_apt_stable_install.html)
and [machine configuration requirements](https://kcjengr.github.io/probe_basic/debian_12_bookworm/configuration/machine_config.html).
Do not mix Stable and Develop application/template versions.

## Configure and export

1. Select Probe Basic in the frontend dropdown.
2. Leave the template path blank to discover the installed official
   `machine_setup_files`, preferring `/usr/share/configs/machine_setup_files`.
   Alternatively browse to an official template copy matching the target version.
   Do not use an existing machine's personal configuration as the template.
3. Configure hardware, axes, IO, spindle and MPG normally.
4. Preview and export to a new directory. Missing template resources produce an
   actionable error rather than an incomplete DISPLAY-only configuration.
5. Open the exported INI with LinuxCNC on a system with Probe Basic installed.

FMesa can still run, edit other profiles and build without Probe Basic installed;
its templates are only required to generate/export the PB profile.

## Scope

This is a **mill with manual tool changes**. XYZ, XYZA, XYZAB and template-provided
XYZAC/XYZBC layouts are supported. DRO, geometry and offset columns follow the
configured axes. The usual wizard layouts remain XYZ/XYZA/XYZAB.

The exporter writes PB startup options, custom_config.yml, a separate
probe_basic.var and subroutine/on_abort paths. It copies version-matched user
panels, DROs, subroutines and supporting assets from the selected template.
A single probe_basic_postgui.hal connects PB's own manual toolchange dialog and
cycle timer. AXIS/Gmoccapy toolchange pins are not used. The motion module has the
required digital/analog channels; Mesa and mechanical generation remain shared.

The project uses millimetres (G21). The official inch example's F10 and G64 P.001
are converted to F254 and P.0254. Probe/toolsetter parameters come from the
selected template and must be calibrated in PB for the real equipment before
using measurement routines; sample parameters are not machine acceptance.

A configured real probe signal also feeds PB's probe indicator. No simulated
probe source is added, and commanded spindle RPM is not presented as measured
encoder feedback. No ATC, M6 remap or database tool table is enabled; the profile
uses a normal tool.tbl.

Generation, signal wiring, template completeness and failed-export cleanup are
tested. The installed PB 0.6.0-118.dev template was exported locally. LinuxCNC/PB
was not launched as a hardware test; use matching assets for each PB version.
