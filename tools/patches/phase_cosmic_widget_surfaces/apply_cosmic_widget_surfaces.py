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


def require_previous_phases() -> None:
    runtime = read("crates/neodash-runtime/src/lib.rs")
    cosmic_main = read("crates/neodash-cosmic/src/main.rs")

    runtime_markers = (
        "pub enum RuntimeEvent",
        "pub struct WidgetRuntimeHandle",
        "pub fn spawn_widget_runtime",
    )
    missing_runtime = [marker for marker in runtime_markers if marker not in runtime]
    if missing_runtime:
        raise SystemExit(
            "The runtime event-stream phase must be applied first; missing: "
            + ", ".join(missing_runtime)
        )

    if "struct WidgetSurface" in cosmic_main and "fn view_window" in cosmic_main:
        return

    adapter_markers = (
        "struct WidgetSession",
        "Message::PollRuntime",
        "Native COSMIC runtime host",
    )
    missing_adapter = [marker for marker in adapter_markers if marker not in cosmic_main]
    if missing_adapter:
        raise SystemExit(
            "The COSMIC runtime-adapter phase must be applied first; missing: "
            + ", ".join(missing_adapter)
        )


def patch_cosmic_features() -> None:
    path = "crates/neodash-cosmic/Cargo.toml"
    text = read(path)

    for feature_name in ("cosmic-winit", "cosmic-wayland"):
        lines = text.splitlines()
        for index, line in enumerate(lines):
            if line.startswith(f"{feature_name} = ["):
                if '"cosmic/multi-window"' not in line:
                    lines[index] = line[:-1] + ', "cosmic/multi-window"]'
                break
        else:
            raise SystemExit(f"Could not find {feature_name} feature in {path}")
        text = "\n".join(lines) + "\n"

    write(path, text)


def patch_cosmic_sources() -> None:
    current = read("crates/neodash-cosmic/src/main.rs")
    if "struct WidgetSurface" not in current or "fn view_window" not in current:
        write("crates/neodash-cosmic/src/main.rs", MAIN_RS)

    write("crates/neodash-cosmic/src/surface_plan.rs", SURFACE_PLAN_RS)


def append_docs() -> None:
    runtime_path = "docs/RUNTIME_EVENT_STREAM.md"
    runtime = read(runtime_path)
    marker = "## Independent COSMIC widget surfaces"
    if marker not in runtime:
        runtime = runtime.rstrip() + r'''

## Independent COSMIC widget surfaces

The libcosmic host now creates one independent window per widget. Every window
owns only presentation state while its `WidgetRuntimeHandle` continues to own
command execution, refresh timing, cancellation, and renderer-neutral events.
Closing one window drops only that widget session; closing the final widget exits
the iced daemon.
''' + "\n"
        write(runtime_path, runtime)

    dual_path = "docs/DUAL_FRONTEND_DEVELOPMENT.md"
    dual = read(dual_path)
    marker = "## COSMIC independent-window phase"
    if marker not in dual:
        dual = dual.rstrip() + r'''

## COSMIC independent-window phase

The native host no longer combines all widgets into a diagnostic dashboard.
Each widget receives its own libcosmic window and configured size. Under the
`cosmic-winit` X11 development path, NeoDash also requests the configured `x/y`
position. Ordinary Wayland toplevels do not support reliable absolute placement,
so monitor, anchor, layer, and click-through behavior remains assigned to the
following native COSMIC layer-surface phase.

Use layout mode while developing outside COSMIC:

```bash
cargo run -p neodash-cosmic --features cosmic-winit -- \
  --profile default \
  --layout-mode \
  --debug-frame
```
''' + "\n"
        write(dual_path, dual)


def write_phase_files() -> None:
    write(
        "docs/COSMIC_WIDGET_SURFACES.md",
        r'''# COSMIC widget surfaces

NeoDash's libcosmic host now runs without an extra controller/dashboard window.
It opens one native window for every loaded widget and maps each window ID to one
runtime session.

## Implemented

- one independent libcosmic window per widget
- configured widget width and height
- configured `x/y` requests under the X11 `cosmic-winit` development path
- independent close lifecycle for each widget
- application exit when the final widget closes
- `--layout-mode` header bars and resizing
- `--debug-frame` identity, state, and frame counters
- shared `neodash-runtime` execution and refresh ownership

## Deliberately deferred

Ordinary Wayland toplevel windows cannot provide NeoDash's final desktop-widget
semantics. The following native COSMIC integration phase must implement:

- monitor selection
- anchor-relative placement
- background/bottom/top/overlay layer mapping
- compositor-level click-through input regions
- sticky workspace behavior
- exact COSMIC Wayland positioning

The current phase does not pretend those capabilities are already active.

## Local test

```bash
cargo run -p neodash-cosmic --features cosmic-winit -- \
  --widget examples/widgets/date.toml \
  --widget examples/widgets/uptime.toml \
  --layout-mode \
  --debug-frame
```

Two independent windows should open. Closing one must leave the other running.
Closing the final window must terminate `neodash-cosmic`.
''',
    )

    write(
        "scripts/check_cosmic_widget_surfaces.sh",
        r'''#!/usr/bin/env bash
set -euo pipefail

cargo fmt --all -- --check
cargo test -p neodash-cosmic
cargo check -p neodash-runtime
cargo test -p neodash-runtime
cargo clippy -p neodash-runtime -- -D warnings
cargo check -p neodash-cosmic
cargo clippy -p neodash-cosmic -- -D warnings
cargo check -p neodash-cosmic --features cosmic-winit
cargo clippy -p neodash-cosmic --features cosmic-winit -- -D warnings
cargo check -p neodash-cosmic --features cosmic-wayland
cargo clippy -p neodash-cosmic --features cosmic-wayland -- -D warnings

for marker in \
    'cosmic/multi-window' \
    'no_main_window(true)' \
    'window::open' \
    'fn view_window' \
    'Message::WindowClosed' \
    'cosmic::iced::exit()'; do
    if ! grep -q "$marker" crates/neodash-cosmic/Cargo.toml crates/neodash-cosmic/src/main.rs; then
        printf 'error: COSMIC widget-surface marker missing: %s\n' "$marker" >&2
        exit 1
    fi
done

if grep -q 'Native COSMIC runtime host")' crates/neodash-cosmic/src/main.rs; then
    printf 'error: the old combined COSMIC dashboard view is still present\n' >&2
    exit 1
fi

if grep -q 'run_shell_command_once' crates/neodash-cosmic/src/main.rs; then
    printf 'error: COSMIC widget surfaces execute commands directly\n' >&2
    exit 1
fi
''',
    )

    write(
        "NEODASH_COSMIC_WIDGET_SURFACES_PATCH.md",
        r'''# NeoDash — COSMIC Independent Widget Surfaces

## Goal

Replace the combined COSMIC diagnostic dashboard with one libcosmic window per
widget while preserving the shared runtime boundary.

## Added

- libcosmic multi-window support in both build modes
- no-main-window daemon startup
- one `WidgetSurface` per `window::Id`
- configured window size
- best-effort configured X11 position
- independent window close lifecycle
- clean exit after the final widget closes
- COSMIC layout/debug modes
- pure surface-plan tests
- architecture guards and documentation

## Important boundary

This phase uses ordinary windows. Native COSMIC layer-shell semantics are the
next phase because desktop layers, anchors, monitor selection, click-through, and
exact Wayland placement require compositor-specific surfaces.

## Suggested commit

```text
feat(cosmic): open independent widget surfaces

- replace the combined COSMIC dashboard with one window per widget
- apply configured size and X11 development-position requests
- add independent widget-window lifecycle handling
- add layout and debug modes for surface development
- prepare native COSMIC layer-surface integration
```
''',
    )


def make_executable(path: str) -> None:
    target = ROOT / path
    target.chmod(target.stat().st_mode | 0o111)


MAIN_RS = '// SPDX-License-Identifier: MPL-2.0\n\n#[cfg(any(test, feature = "cosmic-winit", feature = "cosmic-wayland"))]\nmod surface_plan;\n\n#[cfg(all(feature = "cosmic-winit", feature = "cosmic-wayland"))]\ncompile_error!("enable exactly one of cosmic-winit or cosmic-wayland");\n\n#[cfg(not(any(feature = "cosmic-winit", feature = "cosmic-wayland")))]\nfn main() -> anyhow::Result<()> {\n    let backend = neodash_platform::detect_backend_from_env();\n\n    println!("NeoDash native COSMIC widget-surface host");\n    println!(\n        "detected: {:?} / {:?} / {:?}",\n        backend.desktop_family, backend.display_protocol, backend.kind\n    );\n    println!("reason: {}", backend.reason);\n    println!();\n    println!("This binary was built without libcosmic support.");\n    println!();\n    println!("Run independent widget windows on the current desktop:");\n    println!(\n        "  cargo run -p neodash-cosmic --features cosmic-winit -- --profile default --layout-mode --debug-frame"\n    );\n    println!();\n    println!("Compile the native COSMIC Wayland target:");\n    println!("  cargo check -p neodash-cosmic --features cosmic-wayland");\n\n    Ok(())\n}\n\n#[cfg(any(feature = "cosmic-winit", feature = "cosmic-wayland"))]\nfn main() -> anyhow::Result<()> {\n    cosmic_host::run()\n}\n\n#[cfg(any(feature = "cosmic-winit", feature = "cosmic-wayland"))]\nmod cosmic_host {\n    use crate::surface_plan::WidgetSurfacePlan;\n    use clap::Parser;\n    use cosmic::iced::{event, window, Length, Point, Size, Subscription};\n    use cosmic::prelude::*;\n    use cosmic::widget::{self, header_bar};\n    use neodash_core::{\n        collect_profile_widget_paths, discover_widget_paths, load_profile_from_path,\n        resolve_profile_selector, validate_profile, WidgetConfig,\n    };\n    use neodash_platform::{detect_backend_from_env, BackendInfo, DisplayProtocol};\n    use neodash_runtime::{\n        load_widget_from_path, spawn_widget_runtime, RuntimeEvent, WidgetRuntimeHandle,\n    };\n    use std::collections::HashMap;\n    use std::path::PathBuf;\n    use std::sync::mpsc::{Receiver, TryRecvError};\n    use std::time::Duration;\n\n    #[derive(Debug, Parser)]\n    #[command(name = "neodash-cosmic")]\n    #[command(about = "NeoDash native COSMIC widget-surface host")]\n    struct Cli {\n        /// Widget TOML file to load. May be repeated.\n        #[arg(long = "widget", value_name = "FILE")]\n        widgets: Vec<PathBuf>,\n\n        /// Directory containing direct-child widget TOML files. May be repeated.\n        #[arg(long = "widgets-dir", value_name = "DIR")]\n        widget_dirs: Vec<PathBuf>,\n\n        /// Dashboard profile path or bare profile name.\n        #[arg(long, value_name = "PROFILE")]\n        profile: Option<PathBuf>,\n\n        /// Add COSMIC header bars and allow resizing for layout/debug work.\n        #[arg(long)]\n        layout_mode: bool,\n\n        /// Show widget identity, runtime status, and frame count inside each window.\n        #[arg(long)]\n        debug_frame: bool,\n    }\n\n    struct Startup {\n        platform: BackendInfo,\n        widgets: Vec<WidgetConfig>,\n        layout_mode: bool,\n        debug_frame: bool,\n    }\n\n    pub fn run() -> anyhow::Result<()> {\n        let cli = Cli::parse();\n        let widgets = load_requested_widgets(&cli)?;\n        let startup = Startup {\n            platform: detect_backend_from_env(),\n            widgets,\n            layout_mode: cli.layout_mode,\n            debug_frame: cli.debug_frame,\n        };\n\n        // NeoDash owns only widget windows in this phase. There is deliberately no\n        // extra dashboard/controller window hiding behind them.\n        let settings = cosmic::app::Settings::default()\n            .no_main_window(true)\n            .exit_on_close(false)\n            .client_decorations(false)\n            .transparent(true);\n\n        cosmic::app::run::<NeoDashCosmicApp>(settings, startup)\n            .map_err(|error| anyhow::anyhow!("COSMIC application error: {error}"))\n    }\n\n    fn load_requested_widgets(cli: &Cli) -> anyhow::Result<Vec<WidgetConfig>> {\n        let mut paths = Vec::new();\n\n        let profile_selector = if cli.profile.is_none()\n            && cli.widgets.is_empty()\n            && cli.widget_dirs.is_empty()\n        {\n            Some(PathBuf::from("default"))\n        } else {\n            cli.profile.clone()\n        };\n\n        if let Some(selector) = profile_selector {\n            let profile_path = resolve_profile_selector(selector)?;\n            let loaded = load_profile_from_path(&profile_path)?;\n            let report = validate_profile(&loaded)?;\n\n            anyhow::ensure!(\n                !report.has_errors(),\n                "profile {} failed validation with {} error(s) and {} warning(s)",\n                loaded.path.display(),\n                report.error_count(),\n                report.warning_count()\n            );\n\n            paths.extend(collect_profile_widget_paths(&loaded)?);\n        }\n\n        paths.extend(cli.widgets.iter().cloned());\n        for directory in &cli.widget_dirs {\n            paths.extend(discover_widget_paths(directory)?);\n        }\n\n        anyhow::ensure!(\n            !paths.is_empty(),\n            "no widgets requested; pass --profile, --widget, or --widgets-dir"\n        );\n\n        paths\n            .into_iter()\n            .map(|path| {\n                load_widget_from_path(&path).map_err(|error| {\n                    anyhow::anyhow!("failed to load widget {}: {error:#}", path.display())\n                })\n            })\n            .collect()\n    }\n\n    #[derive(Clone, Debug)]\n    enum Message {\n        PollRuntime,\n        CloseWindow(window::Id),\n        WindowOpened(window::Id, Option<Point>),\n        WindowClosed(window::Id),\n    }\n\n    struct NeoDashCosmicApp {\n        core: cosmic::Core,\n        platform: BackendInfo,\n        surfaces: HashMap<window::Id, WidgetSurface>,\n    }\n\n    struct WidgetSurface {\n        plan: WidgetSurfacePlan,\n        handle: Option<WidgetRuntimeHandle>,\n        events: Option<Receiver<RuntimeEvent>>,\n        latest_text: String,\n        status: String,\n        frame_count: u64,\n        layout_mode: bool,\n        debug_frame: bool,\n    }\n\n    impl WidgetSurface {\n        fn start(widget: WidgetConfig, layout_mode: bool, debug_frame: bool) -> Self {\n            let plan = WidgetSurfacePlan::from_widget(&widget);\n\n            match spawn_widget_runtime(widget) {\n                Ok((handle, events)) => Self {\n                    plan,\n                    handle: Some(handle),\n                    events: Some(events),\n                    latest_text: "NeoDash loading...".to_string(),\n                    status: "runtime starting".to_string(),\n                    frame_count: 0,\n                    layout_mode,\n                    debug_frame,\n                },\n                Err(error) => Self {\n                    plan,\n                    handle: None,\n                    events: None,\n                    latest_text: format!("NeoDash runtime startup error:\\n{error:#}"),\n                    status: "runtime failed to start".to_string(),\n                    frame_count: 0,\n                    layout_mode,\n                    debug_frame,\n                },\n            }\n        }\n\n        fn window_settings(&self, platform: &BackendInfo) -> window::Settings {\n            let position = if platform.display_protocol == DisplayProtocol::X11 {\n                window::Position::Specific(Point::new(self.plan.x as f32, self.plan.y as f32))\n            } else {\n                // Ordinary Wayland toplevels cannot request reliable absolute\n                // placement. COSMIC layer-surface positioning is the next phase.\n                window::Position::Default\n            };\n\n            window::Settings {\n                size: Size::new(self.plan.width as f32, self.plan.height as f32),\n                position,\n                resizable: self.layout_mode,\n                decorations: false,\n                transparent: true,\n                exit_on_close_request: false,\n                ..Default::default()\n            }\n        }\n\n        fn poll(&mut self) {\n            loop {\n                let event = match self.events.as_ref() {\n                    Some(events) => events.try_recv(),\n                    None => return,\n                };\n\n                match event {\n                    Ok(RuntimeEvent::Started { .. }) => {\n                        self.status = "runtime active".to_string();\n                    }\n                    Ok(RuntimeEvent::Frame(frame)) => {\n                        self.frame_count += 1;\n                        self.latest_text = frame.text;\n                        self.status = match (frame.timed_out, frame.status_code) {\n                            (true, _) => "last command timed out".to_string(),\n                            (false, Some(code)) if code != 0 => {\n                                format!("last command exited with status {code}")\n                            }\n                            _ => "runtime active".to_string(),\n                        };\n                    }\n                    Ok(RuntimeEvent::Error { message, .. }) => {\n                        self.latest_text = format!("NeoDash runtime error:\\n{message}");\n                        self.status = "runtime error".to_string();\n                    }\n                    Ok(RuntimeEvent::Stopped { .. }) => {\n                        self.status = "runtime stopped".to_string();\n                        self.events = None;\n                        drop(self.handle.take());\n                        return;\n                    }\n                    Err(TryRecvError::Empty) => return,\n                    Err(TryRecvError::Disconnected) => {\n                        self.status = "runtime channel disconnected".to_string();\n                        self.events = None;\n                        drop(self.handle.take());\n                        return;\n                    }\n                }\n            }\n        }\n    }\n\n    impl cosmic::Application for NeoDashCosmicApp {\n        type Executor = cosmic::executor::Default;\n        type Flags = Startup;\n        type Message = Message;\n\n        const APP_ID: &\'static str = "io.github.adamjvr.NeoDash.Cosmic";\n\n        fn core(&self) -> &cosmic::Core {\n            &self.core\n        }\n\n        fn core_mut(&mut self) -> &mut cosmic::Core {\n            &mut self.core\n        }\n\n        fn init(\n            core: cosmic::Core,\n            startup: Self::Flags,\n        ) -> (Self, Task<cosmic::Action<Self::Message>>) {\n            let mut surfaces = HashMap::with_capacity(startup.widgets.len());\n            let mut open_tasks = Vec::with_capacity(startup.widgets.len());\n\n            for widget in startup.widgets {\n                let surface = WidgetSurface::start(\n                    widget,\n                    startup.layout_mode,\n                    startup.debug_frame,\n                );\n                let settings = surface.window_settings(&startup.platform);\n                let (id, open_task) = window::open(settings);\n\n                surfaces.insert(id, surface);\n                open_tasks.push(\n                    open_task.map(|opened_id| {\n                        cosmic::Action::App(Message::WindowOpened(opened_id, None))\n                    }),\n                );\n            }\n\n            (\n                Self {\n                    core,\n                    platform: startup.platform,\n                    surfaces,\n                },\n                Task::batch(open_tasks),\n            )\n        }\n\n        fn subscription(&self) -> Subscription<Self::Message> {\n            let runtime_poll = cosmic::iced::time::every(Duration::from_millis(32))\n                .map(|_| Message::PollRuntime);\n\n            let window_events = event::listen_with(|event, _, id| {\n                if let cosmic::iced::Event::Window(window_event) = event {\n                    match window_event {\n                        window::Event::CloseRequested => Some(Message::CloseWindow(id)),\n                        window::Event::Opened { position, .. } => {\n                            Some(Message::WindowOpened(id, position))\n                        }\n                        window::Event::Closed => Some(Message::WindowClosed(id)),\n                        _ => None,\n                    }\n                } else {\n                    None\n                }\n            });\n\n            Subscription::batch([runtime_poll, window_events])\n        }\n\n        fn update(&mut self, message: Self::Message) -> Task<cosmic::Action<Self::Message>> {\n            match message {\n                Message::PollRuntime => {\n                    for surface in self.surfaces.values_mut() {\n                        surface.poll();\n                    }\n                    Task::none()\n                }\n                Message::CloseWindow(id) => window::close(id),\n                Message::WindowOpened(id, _reported_position) => {\n                    let Some(surface) = self.surfaces.get(&id) else {\n                        return Task::none();\n                    };\n\n                    let title = surface.plan.widget_name.clone();\n                    let target_position = Point::new(surface.plan.x as f32, surface.plan.y as f32);\n                    let mut tasks = vec![self.set_window_title(title, id)];\n\n                    // Winit/X11 supports explicit placement. Ordinary Wayland\n                    // toplevels do not; native COSMIC placement follows with the\n                    // layer-surface integration phase.\n                    if self.platform.display_protocol == DisplayProtocol::X11 {\n                        tasks.push(window::move_to(id, target_position));\n                    }\n\n                    Task::batch(tasks)\n                }\n                Message::WindowClosed(id) => {\n                    self.surfaces.remove(&id);\n                    if self.surfaces.is_empty() {\n                        cosmic::iced::exit()\n                    } else {\n                        Task::none()\n                    }\n                }\n            }\n        }\n\n        fn view(&self) -> Element<\'_, Self::Message> {\n            // Settings::no_main_window(true) means this fallback is not normally\n            // displayed, but Application still requires a main view method.\n            widget::text::body("NeoDash widget surfaces are active").into()\n        }\n\n        fn view_window(&self, id: window::Id) -> Element<\'_, Self::Message> {\n            let Some(surface) = self.surfaces.get(&id) else {\n                return widget::text::body("NeoDash widget surface is closing").into();\n            };\n\n            let spacing = cosmic::theme::spacing().space_s;\n            let mut content = widget::column::with_capacity(3)\n                .push(widget::text::body(surface.latest_text.as_str()))\n                .spacing(spacing)\n                .width(Length::Fill);\n\n            if surface.debug_frame {\n                content = content\n                    .push(widget::text::body(format!(\n                        "{} ({})",\n                        surface.plan.widget_name, surface.plan.widget_id\n                    )))\n                    .push(widget::text::body(format!(\n                        "{} · {} frame(s)",\n                        surface.status, surface.frame_count\n                    )));\n            }\n\n            let window_content = widget::container(content)\n                .padding(surface.plan.padding)\n                .width(Length::Fill)\n                .height(Length::Fill)\n                .class(cosmic::style::Container::Background);\n\n            if surface.layout_mode {\n                let focused = self.core().focused_window() == Some(id);\n                widget::column![header_bar().focused(focused), window_content].into()\n            } else {\n                window_content.into()\n            }\n        }\n    }\n}\n'
SURFACE_PLAN_RS = '// SPDX-License-Identifier: MPL-2.0\n\n//! Toolkit-independent planning data for one libcosmic widget window.\n//!\n//! This module deliberately converts NeoDash\'s signed, hand-editable geometry\n//! into values safe to pass to a window toolkit. It does not claim to implement\n//! monitor selection, anchor semantics, desktop layers, or click-through; those\n//! require compositor-specific integration in the following phase.\n\nuse neodash_core::WidgetConfig;\n\n#[derive(Debug, Clone, PartialEq, Eq)]\npub(crate) struct WidgetSurfacePlan {\n    pub(crate) widget_id: String,\n    pub(crate) widget_name: String,\n    pub(crate) x: i32,\n    pub(crate) y: i32,\n    pub(crate) width: u32,\n    pub(crate) height: u32,\n    pub(crate) padding: u16,\n}\n\nimpl WidgetSurfacePlan {\n    pub(crate) fn from_widget(widget: &WidgetConfig) -> Self {\n        Self {\n            widget_id: widget.id.0.clone(),\n            widget_name: widget.name.clone(),\n            x: widget.geometry.x,\n            y: widget.geometry.y,\n            width: positive_dimension(widget.geometry.width),\n            height: positive_dimension(widget.geometry.height),\n            padding: u16::try_from(widget.style.padding).unwrap_or(u16::MAX),\n        }\n    }\n}\n\nfn positive_dimension(value: i32) -> u32 {\n    u32::try_from(value).unwrap_or(1).max(1)\n}\n\n#[cfg(test)]\nmod tests {\n    use super::*;\n    use neodash_core::{SourceConfig, WidgetConfig, WidgetId, WidgetType};\n\n    fn widget() -> WidgetConfig {\n        WidgetConfig {\n            id: WidgetId("clock".to_string()),\n            name: "Clock".to_string(),\n            widget_type: WidgetType::Shell,\n            enabled: true,\n            source: SourceConfig::default(),\n            geometry: Default::default(),\n            style: Default::default(),\n        }\n    }\n\n    #[test]\n    fn keeps_configured_position_and_size() {\n        let mut widget = widget();\n        widget.geometry.x = 120;\n        widget.geometry.y = 240;\n        widget.geometry.width = 640;\n        widget.geometry.height = 180;\n\n        let plan = WidgetSurfacePlan::from_widget(&widget);\n\n        assert_eq!((plan.x, plan.y), (120, 240));\n        assert_eq!((plan.width, plan.height), (640, 180));\n    }\n\n    #[test]\n    fn clamps_invalid_dimensions_before_toolkit_use() {\n        let mut widget = widget();\n        widget.geometry.width = 0;\n        widget.geometry.height = -50;\n\n        let plan = WidgetSurfacePlan::from_widget(&widget);\n\n        assert_eq!((plan.width, plan.height), (1, 1));\n    }\n\n    #[test]\n    fn caps_padding_at_the_toolkit_limit() {\n        let mut widget = widget();\n        widget.style.padding = u32::MAX;\n\n        let plan = WidgetSurfacePlan::from_widget(&widget);\n\n        assert_eq!(plan.padding, u16::MAX);\n    }\n}\n'


def main() -> None:
    require_previous_phases()
    patch_cosmic_features()
    patch_cosmic_sources()
    append_docs()
    write_phase_files()
    make_executable("scripts/check_cosmic_widget_surfaces.sh")
    print("NeoDash COSMIC independent widget-surface phase applied.")


if __name__ == "__main__":
    main()
