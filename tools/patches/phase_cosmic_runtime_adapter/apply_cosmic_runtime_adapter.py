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
        raise SystemExit(
            "The runtime event-stream phase must be applied first; missing: "
            + ", ".join(missing)
        )


def patch_cosmic_cargo() -> None:
    path = "crates/neodash-cosmic/Cargo.toml"
    text = read(path)

    dependencies = (
        'clap.workspace = true\n',
        'neodash-core = { path = "../neodash-core" }\n',
        'neodash-runtime = { path = "../neodash-runtime" }\n',
    )

    marker = 'anyhow.workspace = true\n'
    if marker not in text:
        raise SystemExit("Could not find anyhow dependency in neodash-cosmic")

    insertion = "".join(line for line in dependencies if line not in text)
    if insertion:
        text = text.replace(marker, marker + insertion, 1)

    if 'neodash-exec = { path = "../neodash-exec" }' in text:
        raise SystemExit("neodash-cosmic must not depend directly on neodash-exec")

    write(path, text)


def patch_cosmic_main() -> None:
    path = "crates/neodash-cosmic/src/main.rs"
    current = read(path)

    if "struct WidgetSession" in current and "Message::PollRuntime" in current:
        return

    required = (
        "Native COSMIC frontend scaffold",
        "pub struct NeoDashCosmicApp",
        "cosmic::app::run::<NeoDashCosmicApp>",
    )
    missing = [marker for marker in required if marker not in current]
    if missing:
        raise SystemExit(
            "The COSMIC scaffold has changed since this phase was built; missing: "
            + ", ".join(missing)
        )

    replacement = r'''// SPDX-License-Identifier: MPL-2.0

#[cfg(all(feature = "cosmic-winit", feature = "cosmic-wayland"))]
compile_error!("enable exactly one of cosmic-winit or cosmic-wayland");

#[cfg(not(any(feature = "cosmic-winit", feature = "cosmic-wayland")))]
fn main() -> anyhow::Result<()> {
    let backend = neodash_platform::detect_backend_from_env();

    println!("NeoDash native COSMIC host");
    println!(
        "detected: {:?} / {:?} / {:?}",
        backend.desktop_family, backend.display_protocol, backend.kind
    );
    println!("reason: {}", backend.reason);
    println!();
    println!("This binary was built without libcosmic support.");
    println!();
    println!("Run the frontend on the current X11/non-COSMIC desktop:");
    println!(
        "  cargo run -p neodash-cosmic --features cosmic-winit -- --profile default"
    );
    println!();
    println!("Compile the native COSMIC Wayland target:");
    println!("  cargo check -p neodash-cosmic --features cosmic-wayland");

    Ok(())
}

#[cfg(any(feature = "cosmic-winit", feature = "cosmic-wayland"))]
fn main() -> anyhow::Result<()> {
    cosmic_host::run()
}

#[cfg(any(feature = "cosmic-winit", feature = "cosmic-wayland"))]
mod cosmic_host {
    use clap::Parser;
    use cosmic::iced::{Length, Subscription};
    use cosmic::prelude::*;
    use cosmic::widget;
    use neodash_core::{
        collect_profile_widget_paths, discover_widget_paths, load_profile_from_path,
        resolve_profile_selector, validate_profile, WidgetConfig,
    };
    use neodash_platform::{detect_backend_from_env, BackendInfo};
    use neodash_runtime::{
        load_widget_from_path, spawn_widget_runtime, RuntimeEvent, WidgetRuntimeHandle,
    };
    use std::path::PathBuf;
    use std::sync::mpsc::{Receiver, TryRecvError};
    use std::time::Duration;

    #[derive(Debug, Parser)]
    #[command(name = "neodash-cosmic")]
    #[command(about = "NeoDash native COSMIC dashboard host")]
    struct Cli {
        /// Widget TOML file to load. May be repeated.
        #[arg(long = "widget", value_name = "FILE")]
        widgets: Vec<PathBuf>,

        /// Directory containing direct-child widget TOML files. May be repeated.
        #[arg(long = "widgets-dir", value_name = "DIR")]
        widget_dirs: Vec<PathBuf>,

        /// Dashboard profile path or bare profile name.
        #[arg(long, value_name = "PROFILE")]
        profile: Option<PathBuf>,
    }

    struct Startup {
        platform: BackendInfo,
        widgets: Vec<WidgetConfig>,
    }

    pub fn run() -> anyhow::Result<()> {
        let cli = Cli::parse();
        let widgets = load_requested_widgets(&cli)?;
        let startup = Startup {
            platform: detect_backend_from_env(),
            widgets,
        };

        cosmic::app::run::<NeoDashCosmicApp>(cosmic::app::Settings::default(), startup)
            .map_err(|error| anyhow::anyhow!("COSMIC application error: {error}"))
    }

    fn load_requested_widgets(cli: &Cli) -> anyhow::Result<Vec<WidgetConfig>> {
        let mut paths = Vec::new();

        // Preserve the convenient no-argument launch used during scaffold work by
        // treating it as `--profile default` once a user config has been created.
        let profile_selector = if cli.profile.is_none()
            && cli.widgets.is_empty()
            && cli.widget_dirs.is_empty()
        {
            Some(PathBuf::from("default"))
        } else {
            cli.profile.clone()
        };

        if let Some(selector) = profile_selector {
            let profile_path = resolve_profile_selector(selector)?;
            let loaded = load_profile_from_path(&profile_path)?;
            let report = validate_profile(&loaded)?;

            anyhow::ensure!(
                !report.has_errors(),
                "profile {} failed validation with {} error(s) and {} warning(s)",
                loaded.path.display(),
                report.error_count(),
                report.warning_count()
            );

            paths.extend(collect_profile_widget_paths(&loaded)?);
        }

        paths.extend(cli.widgets.iter().cloned());
        for directory in &cli.widget_dirs {
            paths.extend(discover_widget_paths(directory)?);
        }

        anyhow::ensure!(
            !paths.is_empty(),
            "no widgets requested; pass --profile, --widget, or --widgets-dir"
        );

        let mut widgets = Vec::with_capacity(paths.len());
        for path in paths {
            let widget = load_widget_from_path(&path).map_err(|error| {
                anyhow::anyhow!("failed to load widget {}: {error:#}", path.display())
            })?;
            widgets.push(widget);
        }

        Ok(widgets)
    }

    #[derive(Clone, Debug)]
    enum Message {
        PollRuntime,
    }

    struct NeoDashCosmicApp {
        core: cosmic::Core,
        platform: BackendInfo,
        sessions: Vec<WidgetSession>,
    }

    struct WidgetSession {
        widget_id: String,
        widget_name: String,
        handle: Option<WidgetRuntimeHandle>,
        events: Option<Receiver<RuntimeEvent>>,
        latest_text: String,
        status: String,
        frame_count: u64,
    }

    impl WidgetSession {
        fn start(widget: WidgetConfig) -> Self {
            let widget_id = widget.id.0.clone();
            let widget_name = widget.name.clone();

            match spawn_widget_runtime(widget) {
                Ok((handle, events)) => Self {
                    widget_id,
                    widget_name,
                    handle: Some(handle),
                    events: Some(events),
                    latest_text: "NeoDash loading...".to_string(),
                    status: "runtime starting".to_string(),
                    frame_count: 0,
                },
                Err(error) => Self {
                    widget_id,
                    widget_name,
                    handle: None,
                    events: None,
                    latest_text: format!("NeoDash runtime startup error:\n{error:#}"),
                    status: "runtime failed to start".to_string(),
                    frame_count: 0,
                },
            }
        }

        fn poll(&mut self) {
            loop {
                let event = match self.events.as_ref() {
                    Some(events) => events.try_recv(),
                    None => return,
                };

                match event {
                    Ok(RuntimeEvent::Started { .. }) => {
                        self.status = "runtime active".to_string();
                    }
                    Ok(RuntimeEvent::Frame(frame)) => {
                        self.frame_count += 1;
                        self.latest_text = frame.text;
                        self.status = match (frame.timed_out, frame.status_code) {
                            (true, _) => "last command timed out".to_string(),
                            (false, Some(code)) if code != 0 => {
                                format!("last command exited with status {code}")
                            }
                            _ => "runtime active".to_string(),
                        };
                    }
                    Ok(RuntimeEvent::Error { message, .. }) => {
                        self.latest_text = format!("NeoDash runtime error:\n{message}");
                        self.status = "runtime error".to_string();
                    }
                    Ok(RuntimeEvent::Stopped { .. }) => {
                        self.status = "runtime stopped".to_string();
                        self.events = None;
                        drop(self.handle.take());
                        return;
                    }
                    Err(TryRecvError::Empty) => return,
                    Err(TryRecvError::Disconnected) => {
                        self.status = "runtime channel disconnected".to_string();
                        self.events = None;
                        drop(self.handle.take());
                        return;
                    }
                }
            }
        }
    }

    impl cosmic::Application for NeoDashCosmicApp {
        type Executor = cosmic::executor::Default;
        type Flags = Startup;
        type Message = Message;

        const APP_ID: &'static str = "io.github.adamjvr.NeoDash.Cosmic";

        fn core(&self) -> &cosmic::Core {
            &self.core
        }

        fn core_mut(&mut self) -> &mut cosmic::Core {
            &mut self.core
        }

        fn init(
            core: cosmic::Core,
            startup: Self::Flags,
        ) -> (Self, Task<cosmic::Action<Self::Message>>) {
            let sessions = startup
                .widgets
                .into_iter()
                .map(WidgetSession::start)
                .collect();

            (
                Self {
                    core,
                    platform: startup.platform,
                    sessions,
                },
                Task::none(),
            )
        }

        fn subscription(&self) -> Subscription<Self::Message> {
            // This timer only delivers events to the COSMIC UI. Command execution
            // and source.interval_ms scheduling remain inside neodash-runtime.
            cosmic::iced::time::every(Duration::from_millis(32))
                .map(|_| Message::PollRuntime)
        }

        fn update(&mut self, message: Self::Message) -> Task<cosmic::Action<Self::Message>> {
            match message {
                Message::PollRuntime => {
                    for session in &mut self.sessions {
                        session.poll();
                    }
                }
            }

            Task::none()
        }

        fn view(&self) -> Element<'_, Self::Message> {
            let spacing = cosmic::theme::spacing().space_m;
            let mut widget_list = widget::column::with_capacity(self.sessions.len())
                .spacing(spacing)
                .width(Length::Fill);

            for session in &self.sessions {
                let session_content = widget::column::with_capacity(4)
                    .push(widget::text::title3(format!(
                        "{} ({})",
                        session.widget_name, session.widget_id
                    )))
                    .push(widget::text::body(session.latest_text.as_str()))
                    .push(widget::text::body(format!(
                        "{} · {} frame(s)",
                        session.status, session.frame_count
                    )))
                    .spacing(cosmic::theme::spacing().space_s)
                    .width(Length::Fill);

                widget_list = widget_list.push(
                    widget::container(session_content)
                        .padding(spacing)
                        .width(Length::Fill),
                );
            }

            let content = widget::column::with_capacity(6)
                .push(widget::text::title1("NeoDash"))
                .push(widget::text::title3("Native COSMIC runtime host"))
                .push(widget::text::body(format!(
                    "Desktop: {:?}",
                    self.platform.desktop_family
                )))
                .push(widget::text::body(format!(
                    "Display: {:?}",
                    self.platform.display_protocol
                )))
                .push(widget::text::body(format!(
                    "Integration backend: {:?}",
                    self.platform.kind
                )))
                .push(widget_list)
                .spacing(spacing)
                .width(Length::Fill);

            widget::container(content)
                .padding(spacing)
                .width(Length::Fill)
                .height(Length::Fill)
                .into()
        }
    }
}
'''

    write(path, replacement)


def patch_runtime_document() -> None:
    path = "docs/RUNTIME_EVENT_STREAM.md"
    text = read(path)
    marker = "## COSMIC adapter status"
    if marker not in text:
        text = text.rstrip() + r'''

## COSMIC adapter status

The native libcosmic frontend now consumes the same `RuntimeEvent` stream as the
GTK frontend. It supports profile, explicit widget-file, and widget-directory
loading. Its short iced subscription only drains already-produced events; command
execution, output normalization, refresh intervals, and cancellation remain in
`neodash-runtime`.

The adapter is exercised locally with `cosmic-winit` and compiled continuously
with `cosmic-wayland`. Desktop-layer surfaces under `cosmic-comp` remain a later
platform-integration phase.
''' + "\n"
    write(path, text)


def patch_dual_frontend_document() -> None:
    path = "docs/DUAL_FRONTEND_DEVELOPMENT.md"
    text = read(path)
    marker = "## Shared runtime parity"
    if marker not in text:
        text = text.rstrip() + r'''

## Shared runtime parity

Both graphical hosts now consume `neodash-runtime` events:

- GTK drains events on the GLib main loop.
- libcosmic drains events through an iced subscription.
- neither frontend executes shell commands directly.
- each widget keeps its independent runtime-owned refresh interval.

Local COSMIC runtime test:

```bash
cargo run -p neodash-cosmic --features cosmic-winit -- --profile default
```

Native target compile test:

```bash
cargo check -p neodash-cosmic --features cosmic-wayland
```
''' + "\n"
    write(path, text)


def write_validation_script() -> None:
    write(
        "scripts/check_cosmic_runtime_adapter.sh",
        r'''#!/usr/bin/env bash
set -euo pipefail

cargo fmt --all -- --check
cargo check -p neodash-runtime
cargo test -p neodash-runtime
cargo clippy -p neodash-runtime -- -D warnings
cargo check -p neodash-cosmic
cargo clippy -p neodash-cosmic -- -D warnings
cargo check -p neodash-cosmic --features cosmic-winit
cargo clippy -p neodash-cosmic --features cosmic-winit -- -D warnings
cargo check -p neodash-cosmic --features cosmic-wayland
cargo clippy -p neodash-cosmic --features cosmic-wayland -- -D warnings

if grep -q 'run_shell_command_once' crates/neodash-cosmic/src/main.rs; then
    printf 'error: COSMIC still executes commands directly\n' >&2
    exit 1
fi

if grep -q 'neodash-exec' crates/neodash-cosmic/Cargo.toml; then
    printf 'error: neodash-cosmic depends directly on neodash-exec\n' >&2
    exit 1
fi

for marker in 'spawn_widget_runtime' 'RuntimeEvent' 'Message::PollRuntime'; do
    if ! grep -q "$marker" crates/neodash-cosmic/src/main.rs; then
        printf 'error: COSMIC runtime adapter marker missing: %s\n' "$marker" >&2
        exit 1
    fi
done
''',
    )


def write_phase_document() -> None:
    write(
        "NEODASH_COSMIC_RUNTIME_ADAPTER_PATCH.md",
        r'''# NeoDash — COSMIC Runtime Adapter Phase

## Goal

Connect the native libcosmic host to the same renderer-neutral runtime event
stream already used by GTK.

## Added

- `--profile`, repeated `--widget`, and repeated `--widgets-dir` loading
- one `WidgetSession` per configured widget
- runtime-owned execution and refresh timing
- iced subscription-based event delivery
- visible lifecycle/status information per widget
- local `cosmic-winit` runtime testing
- native `cosmic-wayland` compile and Clippy checks

## Apply

```bash
cd ~/GitHub/neo-dash
unzip -o ~/Downloads/neodash_phase_cosmic_runtime_adapter.zip -d .
bash tools/patches/phase_cosmic_runtime_adapter/apply.sh
```

## Validate

```bash
cargo fmt --all
./scripts/check_cosmic_runtime_adapter.sh
```

## Run locally outside COSMIC

```bash
cargo run -p neodash-cosmic --features cosmic-winit -- --profile default
```

No arguments also select the `default` profile.

## Suggested commit

```text
feat(cosmic): consume the shared widget runtime stream

- add profile-aware widget loading to the libcosmic host
- translate RuntimeEvent frames into native COSMIC views
- keep command execution and refresh scheduling in neodash-runtime
- validate both cosmic-winit and cosmic-wayland builds
- document shared GTK and COSMIC runtime parity
```
''',
    )


def main() -> None:
    require_runtime_phase()
    patch_cosmic_cargo()
    patch_cosmic_main()
    patch_runtime_document()
    patch_dual_frontend_document()
    write_validation_script()
    write_phase_document()

    validation = ROOT / "scripts/check_cosmic_runtime_adapter.sh"
    validation.chmod(validation.stat().st_mode | 0o111)

    print("NeoDash COSMIC runtime-adapter phase applied.")


if __name__ == "__main__":
    main()
