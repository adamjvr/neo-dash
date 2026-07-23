# Config directory

NeoDash can now resolve and initialize a user config directory.

The default layout is:

```text
~/.config/neodash/
  profiles/
    default.toml
  widgets/
    date.toml
    uptime.toml
  themes/
```

The config root can be overridden with:

```bash
export NEODASH_CONFIG_DIR=/path/to/neodash-config
```

If `NEODASH_CONFIG_DIR` is not set, NeoDash follows XDG-style behavior:

1. `$XDG_CONFIG_HOME/neodash`
2. `$HOME/.config/neodash`

## Inspect config paths

```bash
cargo run -p neodash-cli -- config-dir
```

## Initialize starter config

```bash
cargo run -p neodash-cli -- config-init
```

Use `--force` to overwrite existing starter files:

```bash
cargo run -p neodash-cli -- config-init --force
```

## Profile selector behavior

A profile can still be passed as an explicit path:

```bash
cargo run -p neodash-app --features gui,x11-desktop -- \
  --profile examples/profiles/default.toml
```

A bare profile name resolves through the user config directory:

```bash
cargo run -p neodash-app --features gui,x11-desktop -- \
  --profile default \
  --debug-frame
```

`default` resolves to:

```text
~/.config/neodash/profiles/default.toml
```

The same selector rule applies to CLI profile commands:

```bash
cargo run -p neodash-cli -- profile-info default
cargo run -p neodash-cli -- profile-check default
```

## What this phase intentionally does not do

This phase does not add the daemon yet. It only makes local app-style config
paths real and testable.

The next runtime step is for the daemon to own profile loading and widget
processes instead of the GTK preview app owning them directly.
