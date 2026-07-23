from __future__ import annotations
from pathlib import Path
import sys

ROOT = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path.cwd().resolve()


def read(path: str) -> str:
    p = ROOT / path
    if not p.exists():
        raise SystemExit(f"Required file is missing: {path}")
    return p.read_text(encoding="utf-8")


def write(path: str, text: str) -> None:
    p = ROOT / path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def patch_runtime() -> None:
    path = "crates/neodash-runtime/src/lib.rs"
    text = read(path)
    marker = "#[cfg(test)]\nmod tests {"
    if "pub enum RuntimeEvent" in text:
        return
    if marker not in text:
        raise SystemExit("Could not find neodash-runtime test module marker")
    addition = r'''
/// One renderer-neutral frame produced by a widget source.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct RuntimeFrame {
    pub widget_id: String,
    pub text: String,
    pub status_code: Option<i32>,
    pub timed_out: bool,
}

/// Events emitted by a long-running widget worker.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum RuntimeEvent {
    Started { widget_id: String },
    Frame(RuntimeFrame),
    Error { widget_id: String, message: String },
    Stopped { widget_id: String },
}

/// Handle used by daemon/frontends to stop one widget worker cleanly.
pub struct WidgetRuntimeHandle {
    stop_tx: std::sync::mpsc::Sender<()>,
    join: Option<std::thread::JoinHandle<()>>,
}

impl WidgetRuntimeHandle {
    pub fn stop(mut self) -> anyhow::Result<()> {
        let _ = self.stop_tx.send(());
        if let Some(join) = self.join.take() {
            join.join().map_err(|_| anyhow::anyhow!("widget runtime thread panicked"))?;
        }
        Ok(())
    }
}

impl Drop for WidgetRuntimeHandle {
    fn drop(&mut self) {
        let _ = self.stop_tx.send(());
        if let Some(join) = self.join.take() {
            let _ = join.join();
        }
    }
}

/// Execute one renderer-neutral frame for a shell widget.
pub fn execute_widget_frame(widget: &WidgetConfig) -> anyhow::Result<RuntimeFrame> {
    validate_runtime_widget(widget)?;
    let output = run_shell_command_once(&widget.source)?;
    let mut text = output.stdout;

    if widget.source.show_stderr && !output.stderr.is_empty() {
        if !text.ends_with('\n') && !text.is_empty() {
            text.push('\n');
        }
        text.push_str(&output.stderr);
    }

    if output.timed_out {
        if !text.ends_with('\n') && !text.is_empty() {
            text.push('\n');
        }
        text.push_str(&format!(
            "neodash: warning: command exceeded timeout after {:?}",
            output.elapsed
        ));
    }

    if let Some(code) = output.status_code.filter(|code| *code != 0) {
        if !text.ends_with('\n') && !text.is_empty() {
            text.push('\n');
        }
        text.push_str(&format!("neodash: warning: command exited with status code {code}"));
    }

    if text.trim().is_empty() {
        text = "NeoDash command produced no output".to_string();
    }

    Ok(RuntimeFrame {
        widget_id: widget.id.0.clone(),
        text,
        status_code: output.status_code,
        timed_out: output.timed_out,
    })
}

/// Spawn a cancellable worker which owns refresh timing and emits events.
pub fn spawn_widget_runtime(
    widget: WidgetConfig,
) -> anyhow::Result<(WidgetRuntimeHandle, std::sync::mpsc::Receiver<RuntimeEvent>)> {
    validate_runtime_widget(&widget)?;

    let (event_tx, event_rx) = std::sync::mpsc::channel();
    let (stop_tx, stop_rx) = std::sync::mpsc::channel();
    let widget_id = widget.id.0.clone();

    let join = std::thread::Builder::new()
        .name(format!("neodash-widget-{widget_id}"))
        .spawn(move || {
            let _ = event_tx.send(RuntimeEvent::Started {
                widget_id: widget_id.clone(),
            });

            loop {
                match execute_widget_frame(&widget) {
                    Ok(frame) => {
                        if event_tx.send(RuntimeEvent::Frame(frame)).is_err() {
                            break;
                        }
                    }
                    Err(error) => {
                        if event_tx
                            .send(RuntimeEvent::Error {
                                widget_id: widget_id.clone(),
                                message: format!("{error:#}"),
                            })
                            .is_err()
                        {
                            break;
                        }
                    }
                }

                let interval = Duration::from_millis(widget.source.interval_ms.max(1));
                match stop_rx.recv_timeout(interval) {
                    Ok(()) | Err(std::sync::mpsc::RecvTimeoutError::Disconnected) => break,
                    Err(std::sync::mpsc::RecvTimeoutError::Timeout) => {}
                }
            }

            let _ = event_tx.send(RuntimeEvent::Stopped { widget_id });
        })?;

    Ok((
        WidgetRuntimeHandle {
            stop_tx,
            join: Some(join),
        },
        event_rx,
    ))
}

fn validate_runtime_widget(widget: &WidgetConfig) -> anyhow::Result<()> {
    anyhow::ensure!(widget.enabled, "widget '{}' is disabled", widget.name);
    anyhow::ensure!(
        widget.widget_type == WidgetType::Shell,
        "runtime event stream currently supports only shell widgets; '{}' is {:?}",
        widget.name,
        widget.widget_type
    );
    anyhow::ensure!(
        widget.source.command.as_deref().is_some_and(|value| !value.trim().is_empty()),
        "shell widget '{}' is missing a non-empty [source].command",
        widget.name
    );
    Ok(())
}

'''
    text = text.replace(marker, addition + marker, 1)
    write(path, text)


def patch_daemon_cargo() -> None:
    path = "crates/neodash-daemon/Cargo.toml"
    text = read(path)

    dependency_header = "[dependencies]\n"
    if dependency_header not in text:
        raise SystemExit("Could not find daemon [dependencies] section")

    additions = []
    if "clap.workspace" not in text:
        additions.append("clap.workspace = true")
    if "neodash-runtime" not in text:
        additions.append('neodash-runtime = { path = "../neodash-runtime" }')

    if additions:
        block = "".join(f"{line}\n" for line in additions)
        text = text.replace(dependency_header, dependency_header + block, 1)

    write(path, text)


def patch_daemon_main() -> None:
    write("crates/neodash-daemon/src/main.rs", r'''// SPDX-License-Identifier: MPL-2.0

use clap::Parser;
use neodash_platform::detect_backend_from_env;
use neodash_runtime::{load_widget_from_path, spawn_widget_runtime, RuntimeEvent};
use std::path::PathBuf;

#[derive(Debug, Parser)]
#[command(name = "neodashd")]
#[command(about = "NeoDash background runtime daemon")]
struct Cli {
    /// Run one widget through the daemon-owned event stream.
    #[arg(long, value_name = "FILE")]
    widget: Option<PathBuf>,

    /// Stop after receiving this many frames; zero means run until Ctrl+C.
    #[arg(long, default_value_t = 0)]
    frames: usize,
}

fn main() -> anyhow::Result<()> {
    tracing_subscriber::fmt().with_env_filter("info").init();
    let cli = Cli::parse();
    let backend = detect_backend_from_env();
    tracing::info!(?backend, "NeoDash daemon starting");

    let Some(path) = cli.widget else {
        println!("neodashd runtime event-stream phase is alive");
        println!("backend guess: {:?} - {}", backend.kind, backend.reason);
        println!("run: cargo run -p neodash-daemon -- --widget examples/widgets/date.toml --frames 3");
        return Ok(());
    };

    let widget = load_widget_from_path(&path)?;
    let (handle, events) = spawn_widget_runtime(widget)?;
    let mut frame_count = 0usize;

    for event in events {
        match event {
            RuntimeEvent::Started { widget_id } => {
                tracing::info!(%widget_id, "widget runtime started");
            }
            RuntimeEvent::Frame(frame) => {
                frame_count += 1;
                println!("--- {} frame {} ---", frame.widget_id, frame_count);
                println!("{}", frame.text);
                if cli.frames > 0 && frame_count >= cli.frames {
                    break;
                }
            }
            RuntimeEvent::Error { widget_id, message } => {
                tracing::warn!(%widget_id, %message, "widget runtime error");
            }
            RuntimeEvent::Stopped { widget_id } => {
                tracing::info!(%widget_id, "widget runtime stopped");
                break;
            }
        }
    }

    handle.stop()?;
    Ok(())
}
''')


def write_docs() -> None:
    write("docs/RUNTIME_EVENT_STREAM.md", r'''# Runtime event stream phase

This phase introduces the toolkit-neutral execution boundary that both GTK and
libcosmic will consume.

`neodash-runtime` now owns:

- validation of executable widget sources
- one-frame command execution
- output/error normalization
- refresh intervals
- worker cancellation
- renderer-neutral runtime events

The daemon can exercise the same stream without opening either GUI:

```bash
cargo run -p neodash-daemon -- \
  --widget examples/widgets/date.toml \
  --frames 3
```

The next phase replaces the GTK-local timeout loop with this event receiver and
then gives the COSMIC host the same adapter. No GTK or libcosmic type is allowed
inside `neodash-runtime`.
''')

    write("scripts/check_runtime_stream.sh", r'''#!/usr/bin/env bash
set -euo pipefail

cargo fmt --all -- --check
cargo check -p neodash-runtime
cargo test -p neodash-runtime
cargo clippy -p neodash-runtime -- -D warnings
cargo check -p neodash-daemon
cargo clippy -p neodash-daemon -- -D warnings
''')
    (ROOT / "scripts/check_runtime_stream.sh").chmod(0o755)


def main() -> None:
    patch_runtime()
    patch_daemon_cargo()
    patch_daemon_main()
    write_docs()
    print("NeoDash runtime event-stream phase applied.")


if __name__ == "__main__":
    main()
