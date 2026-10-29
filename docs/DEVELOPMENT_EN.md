# Development

[中文](DEVELOPMENT.md)

Core modules:

- `app.py`: independent Qt configuration wizard.
- `config_core.py`: validation/export shared by GUI and CLI.
- `board_profiles.py`: profile registration, fixed/reserved/custom pins.
- `hostmot2_config.py`: discovered-resource Smart Serial and DPLL branches.
- `io_config.py`, `io_widgets.py`: IO targets and grouped signal selectors.
- `spindle_config.py`: ordinary PWM and Step/Dir spindle generation.
- `discovery.py`: mesaflash text/XML resource parsing with provenance.
- `firmware_update.py`, `mesa_update.py`, `updater/`: explicit SD maintenance.
- `sserial_monitor*.py`: read-only system-Python HAL monitor.
- `launcher.py`: distribution entry point and offline self-test.

Register additional boards with `BoardProfile`/`register_profile()` rather than
spreading product-specific pin checks across UI code. Separate the product name
from the HostMot2 device identity: F7I92 uses the 7i92 driver identity. Confirm
wiring, resource counts and firmware capabilities; do not generate guesses.

Reference tests in `tests/reference/` execute installed PNCconf generation
functions without starting its GUI or touching hardware. PNCconf is a test
reference, not a runtime dependency. Compare real connections and units rather
than variable names alone. Record firmware, wiring and observations separately
for hardware acceptance.

Keep workstation environments, generated machine configurations, credentials and
logs out of commits. After generator changes, verify GUI save/load and CLI export
agree. New example pulse scales are zero until the user supplies mechanics.
