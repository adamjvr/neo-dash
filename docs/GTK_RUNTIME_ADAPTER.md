# GTK runtime adapter

The GTK host is now a presentation adapter over `neodash-runtime`.

```text
WidgetConfig
    |
    v
neodash-runtime worker
    |  RuntimeEvent::{Started, Frame, Error, Stopped}
    v
GTK main-loop adapter
    |
    v
gtk::Label
```

## Ownership boundary

`neodash-runtime` owns:

- shell-command execution;
- timeout and exit-status normalization;
- refresh timing from `source.interval_ms`;
- worker lifetime and cancellation;
- renderer-neutral frames and lifecycle events.

The GTK frontend owns:

- creating native GTK windows;
- draining events without blocking the GTK main loop;
- applying frame text to GTK widgets;
- requesting worker shutdown when a window closes.

The 16 ms GLib source is only an event-delivery pump. It does not execute widget
sources and does not control their configured refresh interval.

## Manual test

```bash
cargo run -p neodash-app --features gui,x11-desktop -- \
  --profile default \
  --layout-mode \
  --debug-frame
```

The date and uptime windows should continue refreshing, but all source execution
now occurs in named `neodash-widget-*` runtime workers.
