# GeekTool feature map for NeoDash

This is the behavior we want to carry forward conceptually. Do not copy GeekTool branding, UI art, or closed-source code.

## Original GeekTool object types

| GeekTool type | NeoDash type | Notes |
|---|---|---|
| File geeklet | Log widget | Tail files, follow new lines, support rotation, filters |
| Shell geeklet | Shell widget | Run commands/scripts on intervals, display output |
| Image geeklet | Image widget | Local image, generated graph, folder slideshow, remote webcam/image |
| Web geeklet | Web widget | URL, local HTML, generated HTML |

## Features NeoDash should clone conceptually

- Drag module onto desktop
- Inspector/config panel
- Font/color/alignment/background styling
- Refresh interval per widget
- Per-widget size and position
- Groups/profiles
- Export/import packs
- ANSI terminal output handling
- Regex filters for log widgets
- Log rotation handling
- Show/hide groups
- Lock layout mode

## NeoDash upgrades

- Linux-first Wayland/X11 backend split
- TOML config files
- CLI control
- Built-in widget pack permission review
- Command timeout/kill policy
- Source/Transform/Renderer split
- DBus/MPRIS/PipeWire/NetworkManager helpers later
