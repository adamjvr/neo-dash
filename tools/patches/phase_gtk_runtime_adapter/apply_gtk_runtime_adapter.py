from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path.cwd().resolve()


def read(path: str) -> str:
    target = ROOT / path
    if not target.exists():
        raise SystemExit(f"Required file is missing: {path}")
    return target.read_text(encoding="utf-8")


def write(path: str, text: str) -> None:
    target = ROOT / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")


def require_runtime_phase() -> None:
    runtime = read("crates/neodash-runtime/src/lib.rs")
    required = (
        "pub enum RuntimeEvent",
        "pub struct WidgetRuntimeHandle",
        "pub fn spawn_widget_runtime",
    )
    missing = [marker for marker in required if marker not in runtime]
    if missing:
        joined = ", ".join(missing)
        raise SystemExit(
            "The daemon-owned runtime event-stream phase must be applied first; "
            f"missing: {joined}"
        )


def patch_app_cargo() -> None:
    path = "crates/neodash-app/Cargo.toml"
    text = read(path)

    # neodash-app still needs neodash-runtime, but command execution is no longer
    # a frontend responsibility after this phase.
    text = text.replace('neodash-exec = { path = "../neodash-exec" }\n', "")

    if 'neodash-runtime = { path = "../neodash-runtime" }' not in text:
        marker = 'neodash-platform = { path = "../neodash-platform" }\n'
        if marker not in text:
            raise SystemExit("Could not find neodash-platform dependency in neodash-app")
        text = text.replace(
            marker,
            marker + 'neodash-runtime = { path = "../neodash-runtime" }\n',
            1,
        )

    write(path, text)


def patch_app_main() -> None:
    path = "crates/neodash-app/src/main.rs"
    text = read(path)

    if "fn attach_runtime_stream(" in text:
        # The source patch is already present. Still perform dependency/doc writes.
        return

    old_exec_import = "    use neodash_exec::run_shell_command_once;\n"
    if old_exec_import not in text:
        raise SystemExit(
            "Could not find the GTK-local neodash-exec import; "
            "the app source may have changed since this phase was built"
        )
    text = text.replace(old_exec_import, "", 1)

    old_runtime_import = "    use neodash_runtime::load_widget_from_path;\n"
    new_runtime_import = (
        "    use neodash_runtime::{\n"
        "        load_widget_from_path, spawn_widget_runtime, RuntimeEvent, WidgetRuntimeHandle,\n"
        "    };\n"
    )
    if old_runtime_import not in text:
        raise SystemExit("Could not find the existing neodash-runtime import")
    text = text.replace(old_runtime_import, new_runtime_import, 1)

    # Replace the GTK-owned first execution and refresh timeout with the shared
    # worker. The GTK timer below only drains already-produced events; it does not
    # decide when commands execute.
    local_loop_start = text.find("        let label = Rc::new(label);")
    local_loop_end_marker = "    }\n\n    /// Apply desktop-widget behavior"
    if local_loop_start == -1:
        raise SystemExit("Could not find the GTK-local refresh loop start")
    local_loop_end = text.find(local_loop_end_marker, local_loop_start)
    if local_loop_end == -1:
        raise SystemExit("Could not find the GTK widget-window function boundary")

    text = (
        text[:local_loop_start]
        + "        attach_runtime_stream(&window, &label, widget.as_ref().clone());\n"
        + text[local_loop_end:]
    )

    old_helper_start = text.find(
        "    /// Run one command frame and update the visible label."
    )
    old_helper_end_marker = "    /// Install minimal CSS generated from `StyleConfig`."
    old_helper_end = text.find(old_helper_end_marker, old_helper_start)
    if old_helper_start == -1 or old_helper_end == -1:
        raise SystemExit("Could not find the old GTK command-execution helper block")

    new_helpers = r'''    /// Attach one renderer-neutral runtime stream to a GTK label.
    ///
    /// `neodash-runtime` owns command execution, normalization, refresh timing,
    /// and cancellation. GTK only drains the event receiver on its main loop and
    /// translates frames into label updates.
    fn attach_runtime_stream(
        window: &gtk::ApplicationWindow,
        label: &gtk::Label,
        widget: WidgetConfig,
    ) {
        let widget_id = widget.id.0.clone();
        let (handle, events) = match spawn_widget_runtime(widget) {
            Ok(runtime) => runtime,
            Err(error) => {
                let message = format!("NeoDash runtime startup error:\n{error:#}");
                label.set_text(&message);
                tracing::error!(%widget_id, error = %error, "failed to start GTK widget runtime");
                return;
            }
        };

        let runtime = Rc::new(RefCell::new(Some(handle)));
        let weak_label = label.downgrade();
        let runtime_for_poll = Rc::clone(&runtime);

        // This is an event-delivery poll, not the widget refresh schedule. The
        // worker in neodash-runtime sleeps for source.interval_ms and executes the
        // command. GTK merely keeps UI delivery responsive.
        glib::timeout_add_local(Duration::from_millis(16), move || {
            let Some(label) = weak_label.upgrade() else {
                stop_runtime_in_background(&runtime_for_poll);
                return glib::ControlFlow::Break;
            };

            loop {
                match events.try_recv() {
                    Ok(RuntimeEvent::Started { widget_id }) => {
                        tracing::info!(%widget_id, "GTK widget runtime started");
                    }
                    Ok(RuntimeEvent::Frame(frame)) => {
                        if label.text().as_str() != frame.text.as_str() {
                            label.set_text(&frame.text);
                        }
                    }
                    Ok(RuntimeEvent::Error { widget_id, message }) => {
                        tracing::warn!(%widget_id, %message, "GTK widget runtime error");
                        label.set_text(&format!("NeoDash runtime error:\n{message}"));
                    }
                    Ok(RuntimeEvent::Stopped { widget_id }) => {
                        tracing::info!(%widget_id, "GTK widget runtime stopped");
                        stop_runtime_in_background(&runtime_for_poll);
                        return glib::ControlFlow::Break;
                    }
                    Err(std::sync::mpsc::TryRecvError::Empty) => break,
                    Err(std::sync::mpsc::TryRecvError::Disconnected) => {
                        stop_runtime_in_background(&runtime_for_poll);
                        return glib::ControlFlow::Break;
                    }
                }
            }

            glib::ControlFlow::Continue
        });

        let runtime_for_close = Rc::clone(&runtime);
        window.connect_close_request(move |_| {
            stop_runtime_in_background(&runtime_for_close);
            glib::Propagation::Proceed
        });
    }

    /// Stop and join a widget worker without blocking the GTK main loop.
    fn stop_runtime_in_background(
        runtime: &Rc<RefCell<Option<WidgetRuntimeHandle>>>,
    ) {
        let Some(handle) = runtime.borrow_mut().take() else {
            return;
        };

        let _ = std::thread::Builder::new()
            .name("neodash-gtk-runtime-stop".to_string())
            .spawn(move || {
                if let Err(error) = handle.stop() {
                    tracing::warn!(error = %error, "failed to stop GTK widget runtime cleanly");
                }
            });
    }

'''
    text = text[:old_helper_start] + new_helpers + text[old_helper_end:]

    forbidden = ("run_shell_command_once", "refresh_label_once", "push_newline_if_needed")
    leftovers = [marker for marker in forbidden if marker in text]
    if leftovers:
        raise SystemExit(
            "GTK-local execution code remained after patching: " + ", ".join(leftovers)
        )

    write(path, text)


def patch_runtime_document() -> None:
    path = "docs/RUNTIME_EVENT_STREAM.md"
    text = read(path)
    marker = "## GTK adapter status"
    if marker not in text:
        text = text.rstrip() + r'''

## GTK adapter status

The GTK frontend now consumes `RuntimeEvent` values from `neodash-runtime`.
GTK no longer calls `run_shell_command_once`, formats command warnings, or uses
`source.interval_ms` to schedule executions. Its short GLib timer only drains
frames already produced by the runtime worker and applies them on the GTK main
thread.

The next frontend phase gives the native libcosmic host the same runtime adapter.
''' + "\n"
    write(path, text)


def write_validation_script() -> None:
    write(
        "scripts/check_gtk_runtime_adapter.sh",
        r'''#!/usr/bin/env bash
set -euo pipefail

cargo fmt --all -- --check
cargo check -p neodash-runtime
cargo test -p neodash-runtime
cargo clippy -p neodash-runtime -- -D warnings
cargo check -p neodash-app --features gui
cargo clippy -p neodash-app --features gui -- -D warnings
cargo check -p neodash-app --features gui,x11-desktop
cargo clippy -p neodash-app --features gui,x11-desktop -- -D warnings

if grep -q 'run_shell_command_once' crates/neodash-app/src/main.rs; then
    printf 'error: GTK still executes commands directly\n' >&2
    exit 1
fi

if grep -q 'refresh_label_once' crates/neodash-app/src/main.rs; then
    printf 'error: GTK-local refresh loop still exists\n' >&2
    exit 1
fi

if grep -q 'neodash-exec' crates/neodash-app/Cargo.toml; then
    printf 'error: neodash-app still depends directly on neodash-exec\n' >&2
    exit 1
fi
''',
    )
    (ROOT / "scripts/check_gtk_runtime_adapter.sh").chmod(0o755)


def write_phase_document() -> None:
    write(
        "docs/GTK_RUNTIME_ADAPTER.md",
        r'''# GTK runtime adapter

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
''',
    )


def patch_readme() -> None:
    path = "README.md"
    text = read(path)
    bullet = "- GTK widget windows consume the shared daemon/runtime event stream\n"
    if bullet not in text:
        marker = "- Headless runtime crate for one-shot and watched shell widgets\n"
        if marker in text:
            text = text.replace(marker, marker + bullet, 1)
    write(path, text)


def main() -> None:
    require_runtime_phase()
    patch_app_cargo()
    patch_app_main()
    patch_runtime_document()
    write_validation_script()
    write_phase_document()
    patch_readme()
    print("NeoDash GTK runtime-adapter phase applied.")


if __name__ == "__main__":
    main()
