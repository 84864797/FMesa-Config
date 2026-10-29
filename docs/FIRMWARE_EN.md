# Upgrade packages are supplied separately

[中文](FIRMWARE.md)

This repository and all public application packages **exclude firmware BIN,
FWUP, firmware source ZIP and firmware manifests**. Local development copies,
if present, are excluded by both the publish list and packaging scripts.

LinuxCNC configuration does not require reflashing a board. The desktop
maintenance client remains available, but users must obtain compatible upgrade
packages separately from a trusted provider and check board, boot and application
versions. The application does not download or flash firmware automatically.

The upgrade page starts with no file selected. Changing the target model clears
the previous package selection. With no package selected, upgrade is rejected
before a hardware job starts.

- `.fwup`: an application package the maintenance client can inspect.
- `.bin`: a raw MCU image, not interchangeable with `.fwup`; application installation
  does not program it.

Close LinuxCNC/HAL board ownership before maintenance, verify the model and package,
and establish recovery procedures. Main-card discovery, checksum or maintenance
handshake success is not full field acceptance of the IO application.

The software self-test uses non-executable synthetic data to check package parsing.
It requires no real firmware files and accesses no hardware.
