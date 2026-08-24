# Restart to Windows

A focused Decky plugin that exposes one confirmed **Restart to Windows** action
for Bazzite systems configured for Windows dual boot.

The plugin delegates the operation to Bazzite's `boot-windows` helper installed
by `ujust setup-boot-windows-steam`. It discovers that helper through the
platform's trusted system command path. It does not assume a username, home
directory, hostname, Steam account, executable path, or EFI boot number.

## Prerequisite

Configure Bazzite's supported Windows boot helper once from a terminal:

```sh
ujust setup-boot-windows-steam
```

The plugin does not install a second boot script or broaden the sudo rule
created by that setup command.

## Behavior

- Shows the action only when Bazzite's supported helper is available.
- Re-checks support when the action is confirmed.
- Lets Bazzite find Windows and set the one-time EFI target.
- Does not duplicate or modify Bazzite's EFI implementation.
- Verifies that `BootNext` exactly matches `Windows Boot Manager` before the
  frontend asks Steam's native `RestartPC` API to restart the device.
- Does not request Decky root privileges; the ujust-installed sudo rule remains
  narrowly scoped to `efibootmgr`.

## Development

```sh
pnpm install
pnpm test
pnpm build
```
