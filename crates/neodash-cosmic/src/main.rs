// SPDX-License-Identifier: MPL-2.0

#[cfg(any(test, feature = "cosmic-winit", feature = "cosmic-wayland"))]
mod surface_plan;

#[cfg(all(feature = "cosmic-winit", feature = "cosmic-wayland"))]
compile_error!("enable exactly one of cosmic-winit or cosmic-wayland");

#[cfg(not(any(feature = "cosmic-winit", feature = "cosmic-wayland")))]
fn main() -> anyhow::Result<()> {
    let backend = neodash_platform::detect_backend_from_env();

    println!("NeoDash native COSMIC widget-surface host");
    println!(
        "detected: {:?} / {:?} / {:?}",
        backend.desktop_family, backend.display_protocol, backend.kind
    );
    println!("reason: {}", backend.reason);
    println!();
    println!("This binary was built without libcosmic support.");
    println!();
    println!("Run independent widget windows on the current desktop:");
    println!(
        "  cargo run -p neodash-cosmic --features cosmic-winit -- --profile default --layout-mode --debug-frame"
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
    use crate::surface_plan::WidgetSurfacePlan;
    use clap::Parser;
    use cosmic::iced::{Length, Point, Size, Subscription, event, window};
    use cosmic::prelude::*;
    use cosmic::widget::{self, header_bar};
    use neodash_core::{
        WidgetConfig, collect_profile_widget_paths, discover_widget_paths, load_profile_from_path,
        resolve_profile_selector, validate_profile,
    };
    use neodash_platform::{BackendInfo, DisplayProtocol, detect_backend_from_env};
    use neodash_runtime::{
        RuntimeEvent, WidgetRuntimeHandle, load_widget_from_path, spawn_widget_runtime,
    };
    use std::collections::HashMap;
    use std::path::PathBuf;
    use std::sync::mpsc::{Receiver, TryRecvError};
    use std::time::Duration;

    #[derive(Debug, Parser)]
    #[command(name = "neodash-cosmic")]
    #[command(about = "NeoDash native COSMIC widget-surface host")]
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

        /// Add COSMIC header bars and allow resizing for layout/debug work.
        #[arg(long)]
        layout_mode: bool,

        /// Show widget identity, runtime status, and frame count inside each window.
        #[arg(long)]
        debug_frame: bool,
    }

    struct Startup {
        platform: BackendInfo,
        widgets: Vec<WidgetConfig>,
        layout_mode: bool,
        debug_frame: bool,
    }

    pub fn run() -> anyhow::Result<()> {
        let cli = Cli::parse();
        let widgets = load_requested_widgets(&cli)?;
        let startup = Startup {
            platform: detect_backend_from_env(),
            widgets,
            layout_mode: cli.layout_mode,
            debug_frame: cli.debug_frame,
        };

        // NeoDash owns only widget windows in this phase. There is deliberately no
        // extra dashboard/controller window hiding behind them.
        let settings = cosmic::app::Settings::default()
            .no_main_window(true)
            .exit_on_close(false)
            .client_decorations(false)
            .transparent(true);

        cosmic::app::run::<NeoDashCosmicApp>(settings, startup)
            .map_err(|error| anyhow::anyhow!("COSMIC application error: {error}"))
    }

    fn load_requested_widgets(cli: &Cli) -> anyhow::Result<Vec<WidgetConfig>> {
        let mut paths = Vec::new();

        let profile_selector =
            if cli.profile.is_none() && cli.widgets.is_empty() && cli.widget_dirs.is_empty() {
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

        paths
            .into_iter()
            .map(|path| {
                load_widget_from_path(&path).map_err(|error| {
                    anyhow::anyhow!("failed to load widget {}: {error:#}", path.display())
                })
            })
            .collect()
    }

    #[derive(Clone, Debug)]
    enum Message {
        PollRuntime,
        CloseWindow(window::Id),
        WindowOpened(window::Id, Option<Point>),
        WindowClosed(window::Id),
    }

    struct NeoDashCosmicApp {
        core: cosmic::Core,
        platform: BackendInfo,
        surfaces: HashMap<window::Id, WidgetSurface>,
    }

    struct WidgetSurface {
        plan: WidgetSurfacePlan,
        handle: Option<WidgetRuntimeHandle>,
        events: Option<Receiver<RuntimeEvent>>,
        latest_text: String,
        status: String,
        frame_count: u64,
        layout_mode: bool,
        debug_frame: bool,
    }

    impl WidgetSurface {
        fn start(widget: WidgetConfig, layout_mode: bool, debug_frame: bool) -> Self {
            let plan = WidgetSurfacePlan::from_widget(&widget);

            match spawn_widget_runtime(widget) {
                Ok((handle, events)) => Self {
                    plan,
                    handle: Some(handle),
                    events: Some(events),
                    latest_text: "NeoDash loading...".to_string(),
                    status: "runtime starting".to_string(),
                    frame_count: 0,
                    layout_mode,
                    debug_frame,
                },
                Err(error) => Self {
                    plan,
                    handle: None,
                    events: None,
                    latest_text: format!("NeoDash runtime startup error:\n{error:#}"),
                    status: "runtime failed to start".to_string(),
                    frame_count: 0,
                    layout_mode,
                    debug_frame,
                },
            }
        }

        fn window_settings(&self, platform: &BackendInfo) -> window::Settings {
            let position = if platform.display_protocol == DisplayProtocol::X11 {
                window::Position::Specific(Point::new(self.plan.x as f32, self.plan.y as f32))
            } else {
                // Ordinary Wayland toplevels cannot request reliable absolute
                // placement. COSMIC layer-surface positioning is the next phase.
                window::Position::Default
            };

            window::Settings {
                size: Size::new(self.plan.width as f32, self.plan.height as f32),
                position,
                resizable: self.layout_mode,
                decorations: false,
                transparent: true,
                exit_on_close_request: false,
                ..Default::default()
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
            let mut surfaces = HashMap::with_capacity(startup.widgets.len());
            let mut open_tasks = Vec::with_capacity(startup.widgets.len());

            for widget in startup.widgets {
                let surface =
                    WidgetSurface::start(widget, startup.layout_mode, startup.debug_frame);
                let settings = surface.window_settings(&startup.platform);
                let (id, open_task) = window::open(settings);

                surfaces.insert(id, surface);
                open_tasks.push(
                    open_task.map(|opened_id| {
                        cosmic::Action::App(Message::WindowOpened(opened_id, None))
                    }),
                );
            }

            (
                Self {
                    core,
                    platform: startup.platform,
                    surfaces,
                },
                Task::batch(open_tasks),
            )
        }

        fn subscription(&self) -> Subscription<Self::Message> {
            let runtime_poll =
                cosmic::iced::time::every(Duration::from_millis(32)).map(|_| Message::PollRuntime);

            let window_events = event::listen_with(|event, _, id| {
                if let cosmic::iced::Event::Window(window_event) = event {
                    match window_event {
                        window::Event::CloseRequested => Some(Message::CloseWindow(id)),
                        window::Event::Opened { position, .. } => {
                            Some(Message::WindowOpened(id, position))
                        }
                        window::Event::Closed => Some(Message::WindowClosed(id)),
                        _ => None,
                    }
                } else {
                    None
                }
            });

            Subscription::batch([runtime_poll, window_events])
        }

        fn update(&mut self, message: Self::Message) -> Task<cosmic::Action<Self::Message>> {
            match message {
                Message::PollRuntime => {
                    for surface in self.surfaces.values_mut() {
                        surface.poll();
                    }
                    Task::none()
                }
                Message::CloseWindow(id) => window::close(id),
                Message::WindowOpened(id, _reported_position) => {
                    let Some(surface) = self.surfaces.get(&id) else {
                        return Task::none();
                    };

                    let title = surface.plan.widget_name.clone();
                    let target_position = Point::new(surface.plan.x as f32, surface.plan.y as f32);
                    let mut tasks = vec![self.set_window_title(title, id)];

                    // Winit/X11 supports explicit placement. Ordinary Wayland
                    // toplevels do not; native COSMIC placement follows with the
                    // layer-surface integration phase.
                    if self.platform.display_protocol == DisplayProtocol::X11 {
                        tasks.push(window::move_to(id, target_position));
                    }

                    Task::batch(tasks)
                }
                Message::WindowClosed(id) => {
                    self.surfaces.remove(&id);
                    if self.surfaces.is_empty() {
                        cosmic::iced::exit()
                    } else {
                        Task::none()
                    }
                }
            }
        }

        fn view(&self) -> Element<'_, Self::Message> {
            // Settings::no_main_window(true) means this fallback is not normally
            // displayed, but Application still requires a main view method.
            widget::text::body("NeoDash widget surfaces are active").into()
        }

        fn view_window(&self, id: window::Id) -> Element<'_, Self::Message> {
            let Some(surface) = self.surfaces.get(&id) else {
                return widget::text::body("NeoDash widget surface is closing").into();
            };

            let spacing = cosmic::theme::spacing().space_s;
            let mut content = widget::column::with_capacity(3)
                .push(widget::text::body(surface.latest_text.as_str()))
                .spacing(spacing)
                .width(Length::Fill);

            if surface.debug_frame {
                content = content
                    .push(widget::text::body(format!(
                        "{} ({})",
                        surface.plan.widget_name, surface.plan.widget_id
                    )))
                    .push(widget::text::body(format!(
                        "{} · {} frame(s)",
                        surface.status, surface.frame_count
                    )));
            }

            let window_content = widget::container(content)
                .padding(surface.plan.padding)
                .width(Length::Fill)
                .height(Length::Fill)
                .class(cosmic::style::Container::Background);

            if surface.layout_mode {
                let focused = self.core().focused_window() == Some(id);
                widget::column![header_bar().focused(focused), window_content].into()
            } else {
                window_content.into()
            }
        }
    }
}
