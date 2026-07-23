from pathlib import Path

ROOT = Path.cwd()

def read(path: str) -> str:
    return (ROOT / path).read_text()

def write(path: str, text: str) -> None:
    full = ROOT / path
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(text)

def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise SystemExit(f"Could not find expected block while patching {label}:\n{old[:1000]}")
    return text.replace(old, new, 1)

def patch_app() -> None:
    path = "crates/neodash-app/src/main.rs"
    text = read(path)

    if "layout_mode: bool" in text and "no_desktop_hints: bool" in text:
        print("Layout mode support already appears to be applied.")
        return

    text = replace_once(
        text,
'''        #[arg(long, default_value_t = false)]
        desktop_hints: bool,
''',
'''        #[arg(long, default_value_t = false)]
        desktop_hints: bool,

        /// Disable desktop-widget window hints even if the profile requests them.
        ///
        /// This is useful when testing a profile that normally wants to live on
        /// the desktop layer but needs to be inspected as normal windows.
        #[arg(long, default_value_t = false)]
        no_desktop_hints: bool,

        /// Open widgets as normal movable/resizable windows for layout editing.
        ///
        /// This is a convenience mode equivalent to using normal decorations,
        /// allowing resize, and suppressing desktop-widget hints. It is meant for
        /// adjusting a dashboard before launching it as pinned desktop widgets.
        #[arg(long, default_value_t = false)]
        layout_mode: bool,
''',
        "GUI Cli desktop_hints field",
    )

    text = replace_once(
        text,
'''        let options = PreviewOptions {
            decorated: cli.decorated,
            resizable: cli.resizable,
            close_on_escape: !cli.no_escape_close,
            debug_frame: cli.debug_frame,
            desktop_hints: cli.desktop_hints || profile_desktop_hints,
        };
''',
'''        let desktop_hints = if cli.layout_mode || cli.no_desktop_hints {
            false
        } else {
            cli.desktop_hints || profile_desktop_hints
        };

        let options = PreviewOptions {
            decorated: cli.decorated || cli.layout_mode,
            resizable: cli.resizable || cli.layout_mode,
            close_on_escape: !cli.no_escape_close,
            debug_frame: cli.debug_frame,
            desktop_hints,
        };

        if cli.layout_mode {
            tracing::info!(
                "layout mode enabled: widget windows will be decorated, resizable, and free of desktop hints"
            );
        }
''',
        "GUI PreviewOptions construction",
    )

    write(path, text)

def patch_spacing() -> None:
    cli_path = "crates/neodash-cli/src/main.rs"
    text = read(cli_path)

    # Only move the uptime starter constant. Date remains at y=40; uptime moves
    # lower so window-frame extents and shadows are less likely to overlap.
    if 'id = "uptime-status"' in text and "y = 190" in text:
        text = text.replace("y = 190", "y = 230", 1)

    write(cli_path, text)

    uptime_path = ROOT / "examples/widgets/uptime.toml"
    if uptime_path.exists():
        u = uptime_path.read_text()
        if "y = 190" in u:
            u = u.replace("y = 190", "y = 230", 1)
        uptime_path.write_text(u)

def patch_docs() -> None:
    write(
        "docs/LAYOUT_MODE.md",
'''# Layout mode

NeoDash has two different preview behaviors:

```text
desktop-widget mode
  undecorated
  non-resizable by default
  may use X11 desktop hints
  intended to behave like pinned widgets

layout mode
  decorated
  resizable
  movable by the window manager
  desktop hints suppressed
  intended for arranging and debugging widgets
```

## Why layout mode exists

Desktop widgets are intentionally hard to treat like normal windows. On X11,
NeoDash may ask the window manager to keep them below normal windows, skip the
taskbar, skip the pager, and appear on all workspaces. The windows are also
undecorated by default.

That is useful for a final dashboard, but bad while tuning positions.

## Use layout mode

```bash
cargo run -p neodash-app --features gui,x11-desktop -- \\
  --profile default \\
  --layout-mode \\
  --debug-frame
```

In layout mode, the window manager should give each widget a normal titlebar and
resize handles. Move or resize the windows, then copy the useful `x`, `y`,
`width`, and `height` values back into the widget TOML files.

NeoDash does not yet save layout changes from dragged windows. That requires the
future editor/control app.

## Disable desktop hints manually

If you do not want the full layout-mode convenience behavior, you can suppress
profile-requested desktop hints directly:

```bash
cargo run -p neodash-app --features gui,x11-desktop -- \\
  --profile default \\
  --no-desktop-hints \\
  --decorated \\
  --resizable \\
  --debug-frame
```

## Normal desktop-widget launch

```bash
cargo run -p neodash-app --features gui,x11-desktop -- \\
  --profile default
```

If the profile sets `desktop_hints = true`, this launches the widgets in
desktop-widget mode.
''',
    )

    readme = ROOT / "README.md"
    if readme.exists():
        text = readme.read_text()
        if "## Layout mode" not in text:
            section = '''
## Layout mode

Desktop-widget mode intentionally creates undecorated, hard-to-grab windows.
Use layout mode when arranging or debugging a dashboard:

```bash
cargo run -p neodash-app --features gui,x11-desktop -- \\
  --profile default \\
  --layout-mode \\
  --debug-frame
```

Layout mode makes widget windows decorated and resizable while suppressing
desktop hints, so the window manager can move them normally. See
`docs/LAYOUT_MODE.md`.

'''
            marker = "## User config directory\n"
            if marker in text:
                text = text.replace(marker, section + marker, 1)
            else:
                text += "\n" + section
            readme.write_text(text)

    next_steps = ROOT / "docs/NEXT_STEPS.md"
    if next_steps.exists():
        text = next_steps.read_text()
        if "## Current usability target: save layout changes" not in text:
            text += '''

## Current usability target: save layout changes

Layout mode now makes widgets movable through the window manager, but NeoDash
does not yet persist moved window positions.

Current layout-debug command:

```bash
cargo run -p neodash-app --features gui,x11-desktop -- \\
  --profile default \\
  --layout-mode \\
  --debug-frame
```

Next targets:

- Display current geometry in logs or an overlay.
- Add a layout inspector surface.
- Save updated `x`, `y`, `width`, and `height` values back to widget TOML.
- Eventually support drag/resize directly inside NeoDash rather than relying on
  the window manager.
'''
            next_steps.write_text(text)

    roadmap = ROOT / "docs/ROADMAP.md"
    if roadmap.exists():
        text = roadmap.read_text()
        if "Layout mode for movable decorated preview windows." not in text:
            text += '''

## Layout usability checkpoint

Status: started.

Delivered:

- `--layout-mode` for movable decorated preview windows.
- `--no-desktop-hints` to override profile-requested desktop hints.
- Safer starter spacing for the date and uptime widgets.

Remaining:

- Persist moved window geometry.
- Add a visual layout/editor mode.
- Move geometry save behavior into the future GTK control app.
'''
            roadmap.write_text(text)

def main() -> None:
    patch_app()
    patch_spacing()
    patch_docs()

if __name__ == "__main__":
    main()
