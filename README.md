# Restart to Windows

A focused [Decky Loader](https://github.com/SteamDeckHomebrew/decky-loader) plugin that adds a single **Restart to Windows** action to the Steam Quick Access Menu (QAM) on Bazzite dual-boot systems.

The plugin delegates the boot arming step entirely to Bazzite's trusted `boot-windows` helper. It reads back the EFI `BootNext` entry before invoking Steam's native `RestartPC()` API — so the restart only proceeds when Windows is verifiably the next boot target. No root privileges are requested from Decky; the narrowly-scoped `efibootmgr` sudo rule installed by Bazzite's setup command is sufficient.

---

## System prerequisites

These must be in place on the **Bazzite device** before the plugin will work.

### 1. Bazzite with Windows dual boot

| Requirement | Details |
|---|---|
| OS | [Bazzite](https://bazzite.gg) stable (image-based, immutable) |
| Dual boot | Windows must be installed and have an EFI boot entry labelled **`Windows Boot Manager`** |
| Boot helper | `/usr/bin/boot-windows` — installed by the setup command below |
| Sudo rule | `/etc/sudoers.d/bazzite-*` entry for `efibootmgr` — installed by the setup command |

Run this once from a terminal on the device (Desktop Mode → Konsole):

```sh
ujust setup-boot-windows-steam
```

This creates the `boot-windows` helper and the narrow `efibootmgr` sudoers rule that lets `boot-windows` write `BootNext` without a password. The plugin discovers the helper through the platform's trusted system command path only — it never searches user-writable directories.

> **Verify the helper exists before installing the plugin:**
> ```sh
> which boot-windows
> # Expected: /usr/bin/boot-windows
> ```

### 2. Decky Loader

| Requirement | Version |
|---|---|
| Decky Loader | ≥ `v3.2.8` (earlier builds have a QAM rendering regression — Decky issue [#948](https://github.com/SteamDeckHomebrew/decky-loader/issues/948)) |

Install or update Decky from Gaming Mode:

```sh
# Desktop Mode terminal — installs the latest stable Decky build
curl -L https://github.com/SteamDeckHomebrew/decky-installer/releases/latest/download/install_release.sh | sh
```

Or update through Decky's own **Settings → Updates** tab in Gaming Mode.

### 3. `efibootmgr` available on the system PATH

Bazzite includes `efibootmgr` by default. The plugin uses it (via the `boot-windows` helper) to set `BootNext` and then reads it back directly to verify the Windows entry was armed before requesting the reboot.

---

## Plugin installation

### From the Decky Plugin Store *(pending acceptance)*

Once accepted, search for **"Restart to Windows"** in the Decky Store tab.

### Manual / sideload install

```sh
# On the Bazzite device, from Desktop Mode
curl -L https://github.com/nileshchakraborty/restart-to-windows/releases/latest/download/restart-to-windows.zip -o /tmp/restart-to-windows.zip
unzip /tmp/restart-to-windows.zip -d ~/.local/share/decky-loader/plugins/restart-to-windows
# Then restart Decky from its Settings tab or reboot
```

---

## How it works

1. On load the frontend calls `get_restart_support` to check whether `boot-windows` is reachable on the system command path.
2. If the helper is absent the QAM tile shows a message directing the user to run `ujust setup-boot-windows-steam`.
3. When the user presses **Restart to Windows** a confirmation modal appears.
4. On confirm the backend re-checks support, then calls `boot-windows` which writes `BootNext` via `efibootmgr`.
5. The backend reads back `efibootmgr` output and verifies that `BootNext` matches an entry labelled exactly `Windows Boot Manager`.
6. Only after that check passes does the frontend call `SteamClient.System.RestartPC()` — Steam handles the actual reboot.

The plugin requests **no Decky root flag**. The helper's exit code is treated as diagnostic only; the EFI read-back is authoritative.

---

## Development

### Prerequisites

| Tool | Version |
|---|---|
| Node.js | ≥ 18 LTS |
| pnpm | ≥ 9 (`npm install -g pnpm`) |
| Python | ≥ 3.11 |
| TypeScript | installed via `pnpm install` |

### Setup

```sh
git clone https://github.com/nileshchakraborty/restart-to-windows.git
cd restart-to-windows
pnpm install
```

### Running tests

```sh
# Python backend unit tests + TypeScript type-check
pnpm test

# Python tests only
python3 -m unittest discover -s tests -v

# TypeScript type-check only
npx tsc --noEmit
```

### Building

```sh
pnpm build
# Output: dist/index.js
```

### Watch mode (for active frontend development)

```sh
pnpm watch
```

### Deploying to the device for live testing

The [Decky CLI](https://github.com/SteamDeckHomebrew/decky-cli) can deploy directly over SSH:

```sh
# Install decky CLI once
curl -L https://github.com/SteamDeckHomebrew/decky-cli/releases/latest/download/decky -o cli/decky
chmod +x cli/decky

# Deploy (replace steamos.local with your device hostname or IP)
cli/decky plugin deploy -h nilesh@steamos.local
```

---

## Repository structure

```
restart-to-windows/
├── main.py            # Python backend — helper discovery, EFI verification
├── plugin.json        # Decky plugin manifest
├── src/
│   ├── index.tsx      # React frontend — QAM tile, confirmation modal
│   └── types.d.ts     # Shared TypeScript types
├── tests/
│   └── test_main.py   # Python unit tests (15 cases)
├── py_modules/        # Vendored Python runtime dependencies
├── package.json       # Node dependencies and build scripts
├── rollup.config.js   # Frontend bundler config
└── tsconfig.json      # TypeScript compiler config
```

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| Plugin shows "not configured" message | `boot-windows` helper is missing | Run `ujust setup-boot-windows-steam` in a terminal |
| Action grayed out / unavailable | Plugin failed to detect helper on system path | Verify with `which boot-windows`; helper must be in `/usr/bin` or `/usr/sbin` |
| Confirmation hangs, no reboot | `efibootmgr` timed out or returned an error | Check `journalctl -u plugin_loader` in Desktop Mode for backend errors |
| Device rebooted back to Bazzite | `BootNext` was not set before Steam's `RestartPC()` was called | Check that the EFI verification step passed (backend logs) |
| QAM tab disappeared after Decky update | Decky regression — issue [#948](https://github.com/SteamDeckHomebrew/decky-loader/issues/948) | Update Decky to ≥ `v3.2.8` |

---

## License

[BSD 3-Clause](./LICENSE) — © Nilesh Chakraborty
