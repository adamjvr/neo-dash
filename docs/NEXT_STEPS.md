# Next steps

## Commit 1: scaffold

Commit everything in this starter as the baseline.

Suggested commit message:

```text
Initial NeoDash Rust workspace scaffold
```

## Commit 2: make CLI fully useful

- Add `neodash run --watch` loop
- Add command timeout killing
- Add stderr toggle
- Add JSON output mode for debugging

## Commit 3: first GTK window

- Create `gtk::Application`
- Create transparent undecorated window
- Render one command output label
- Apply basic CSS from `StyleConfig`

## Commit 4: first desktop backend

- Wire `gtk4-layer-shell` for supported Wayland sessions
- Add X11 fallback notes/stubs
- Add backend warnings in GUI

## Commit 5: config loader

- Load widgets from `~/.config/neodash/widgets/*.toml`
- Support `--config-dir`
- Render multiple shell widgets
