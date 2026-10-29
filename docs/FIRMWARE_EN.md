# Firmware and maintenance

[中文](FIRMWARE.md)

Configuring LinuxCNC does not require reflashing Mesa or SD firmware. Installing
the desktop package and running its self-test never flashes a board.

`firmware/mesa-v3/` contains the supplied SD01/SD02 test images, packages, manifest
and `SD-Mesa-Firmware-Source.zip`. The ZIP contains its Rust workspace, toolchain
configuration and MIT notice; dependencies retain their own licenses. Follow that
workspace's build files for firmware builds. Building the desktop distribution
does not compile firmware.

- `.fwup`: application upgrade package with header/checksum.
- `.bin`: raw MCU image; boot and application images use different addresses and
  must not be interchanged.
- `manifest.json`: model, sizes, hashes and build-stage record. Software/model
  testing is not equivalent to field flashing or electrical verification.

Close LinuxCNC/HAL ownership before maintenance, select the matching board and
package, and establish a recovery procedure. Boot maintenance and normal
application communication are different stages. A successful main-card read,
checksum or maintenance handshake does not prove the complete IO application.
The bundled `.fwup` is a selectable default, not an automatic installation.

Report both main-card FPGA and remote boot/application versions when debugging.
