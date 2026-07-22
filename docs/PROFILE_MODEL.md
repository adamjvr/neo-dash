# Shared profile model

NeoDash profile parsing now lives in `neodash-core`.

This matters because profiles are not only a GTK app feature. The CLI, daemon,
editor, and any future import/export tooling all need to agree on the same
profile format and path resolution rules.

## Current profile format

```toml
id = "default"
name = "Default NeoDash Example Dashboard"

widget_dirs = ["../widgets"]
widgets = []
desktop_hints = true
```

## Shared core API

The shared model currently exposes:

```text
ProfileConfig
LoadedProfile
load_profile_from_toml_str
load_profile_from_path
resolve_profile_path
collect_profile_widget_paths
discover_widget_paths
```

## Path resolution rule

Relative paths inside a profile are resolved relative to the profile file's
parent directory.

Example:

```text
examples/
  profiles/
    default.toml
  widgets/
    date.toml
    uptime.toml
```

Inside `examples/profiles/default.toml`, this points at `examples/widgets`:

```toml
widget_dirs = ["../widgets"]
```

The resolver intentionally does not canonicalize paths. This keeps editing
friendly because a profile can refer to files that do not exist yet.

## CLI inspection

Use this command to inspect a profile without opening GTK windows:

```bash
cargo run -p neodash-cli -- profile-info examples/profiles/default.toml
```

The command prints the profile id, name, desktop-hints setting, and resolved
widget files.

## Current limitations

- No duplicate widget ID validation yet.
- No profile inheritance yet.
- No theme/default loading yet.
- No per-widget override layer yet.
- No user config discovery yet.
- The daemon does not own profile state yet.

## Next step

The next phase should add a user config layout and a command that can resolve:

```text
~/.config/neodash/profiles/default.toml
```

from a simple profile name like:

```bash
neodash profile-info default
```
