// SPDX-License-Identifier: MPL-2.0

// NeoDash currently supports two app builds:
//
// 1. The default build, with no GUI feature enabled.
//    This keeps CI, headless systems, and distro build sanity checks simple.
//
// 2. The `gui` feature build.
//    This enables the GTK4 widget preview window.
//
// Optional desktop-integration features are intentionally separate:
//
// - `x11-desktop` adds X11/EWMH window-manager hints.
// - `layer-shell` is reserved for future Wayland layer-shell behavior.
// - `adwaita` is reserved for the future editor/control app.
//
// The important architectural choice here is that the default app target does
// not drag GTK/X11/Wayland desktop integration into the entire workspace.

#[cfg(not(feature = "gui"))]
fn main() -> anyhow::Result<()> {
    use clap::Parser;
    use neodash_platform::detect_backend_from_env;
    use std::path::PathBuf;

    #[derive(Debug, Parser)]
    #[command(name = "neodash-app")]
    #[command(about = "NeoDash graphical app skeleton")]
    struct Cli {
        /// Widget TOML file to preview once GUI support is enabled.
        #[arg(long = "widget", value_name = "FILE")]
        widgets: Vec<PathBuf>,

        /// Directory of widget TOML files to preview once GUI support is enabled.
        #[arg(long = "widgets-dir", value_name = "DIR")]
        widget_dirs: Vec<PathBuf>,
    }

    tracing_subscriber::fmt().with_env_filter("info").init();

    let cli = Cli::parse();
    let backend = detect_backend_from_env();

    println!("NeoDash GTK app skeleton");
    println!("backend guess: {:?} - {}", backend.kind, backend.reason);

    for widget in cli.widgets {
        println!("requested widget: {}", widget.display());
    }

    for dir in cli.widget_dirs {
        println!("requested widget directory: {}", dir.display());
    }

    println!();
    println!("This binary was built without GUI support.");
    println!();
    println!("Run:");
    println!("  cargo run -p neodash-app --features gui -- --widget examples/widgets/date.toml");
    println!("  cargo run -p neodash-app --features gui,x11-desktop -- --widgets-dir examples/widgets --desktop-hints");
    println!();

    Ok(())
}

#[cfg(feature = "gui")]
fn main() -> anyhow::Result<()> {
    gui::run()
}

#[cfg(feature = "gui")]
mod gui {
    use anyhow::Context;
    use clap::Parser;
    use gtk::glib;
    use gtk::prelude::*;
    use neodash_core::{
        collect_profile_widget_paths, discover_widget_paths, load_profile_from_path,
        resolve_profile_selector, validate_profile, GeometryConfig, LoadedProfile,
        ProfileValidationSeverity, WidgetConfig, WidgetType,
    };
    use neodash_exec::run_shell_command_once;
    use neodash_platform::detect_backend_from_env;
    use neodash_runtime::load_widget_from_path;
    use std::{cell::RefCell, path::PathBuf, rc::Rc, time::Duration};

    /// Command line arguments for the graphical NeoDash widget preview.
    ///
    /// This is still not the full visual editor.
    ///
    /// The preview app is the bridge between the proven headless runtime and the
    /// future desktop-widget surface. It loads one widget TOML file, renders the
    /// shell output in a native GTK4 window, and refreshes on the widget's
    /// configured interval.
    #[derive(Debug, Parser)]
    #[command(name = "neodash-app")]
    #[command(about = "NeoDash graphical widget preview")]
    struct Cli {
        /// Widget TOML file to preview.
        ///
        /// May be repeated:
        ///
        ///   --widget examples/widgets/date.toml --widget examples/widgets/uptime.toml
        #[arg(long = "widget", value_name = "FILE")]
        widgets: Vec<PathBuf>,

        /// Directory containing widget TOML files to preview.
        ///
        /// NeoDash loads direct child files ending in `.toml`, sorted by path for
        /// deterministic startup behavior. It does not recurse yet.
        #[arg(long = "widgets-dir", value_name = "DIR")]
        widget_dirs: Vec<PathBuf>,

        /// Profile TOML file describing a dashboard.
        ///
        /// Relative widget paths and widget directories inside the profile are
        /// resolved relative to the profile file's parent directory.
        #[arg(long = "profile", value_name = "FILE")]
        profile: Option<PathBuf>,

        /// Show normal window-manager decorations.
        #[arg(long, default_value_t = false)]
        decorated: bool,

        /// Allow the preview window to be resized by the window manager.
        #[arg(long, default_value_t = false)]
        resizable: bool,

        /// Disable Escape-to-close.
        #[arg(long, default_value_t = false)]
        no_escape_close: bool,

        /// Draw a visible border around the widget frame.
        #[arg(long, default_value_t = false)]
        debug_frame: bool,

        /// Apply desktop-widget window hints when the active backend supports it.
        ///
        /// On X11, this tries to set EWMH hints for:
        ///
        /// - skip taskbar
        /// - skip pager
        /// - sticky/all workspaces
        /// - below normal windows
        ///
        /// This flag is opt-in for now because desktop-window behavior can make
        /// a preview harder to find while we are still developing the renderer.
        #[arg(long, default_value_t = false)]
        desktop_hints: bool,
    }

    #[derive(Debug, Clone, Copy)]
    struct PreviewOptions {
        decorated: bool,
        resizable: bool,
        close_on_escape: bool,
        debug_frame: bool,
        desktop_hints: bool,
    }

    pub fn run() -> anyhow::Result<()> {
        tracing_subscriber::fmt().with_env_filter("info").init();

        let cli = Cli::parse();

        let loaded_profile = match cli.profile.as_ref() {
            Some(profile_path) => {
                let resolved_profile_path = resolve_profile_selector(profile_path)?;
                let loaded = load_profile_from_path(&resolved_profile_path)?;
                tracing::info!(
                    path = %loaded.path.display(),
                    profile_id = loaded.profile.id.as_deref().unwrap_or("<unnamed>"),
                    profile_name = loaded.profile.name.as_deref().unwrap_or("<unnamed>"),
                    widget_count = loaded.profile.widgets.len(),
                    widget_dir_count = loaded.profile.widget_dirs.len(),
                    desktop_hints = loaded.profile.desktop_hints.unwrap_or(false),
                    "loaded NeoDash profile through shared profile model"
                );
                Some(loaded)
            }
            None => None,
        };

        if let Some(loaded) = loaded_profile.as_ref() {
            validate_loaded_profile(loaded)?;
        }

        let profile_desktop_hints = loaded_profile
            .as_ref()
            .and_then(|loaded| loaded.profile.desktop_hints)
            .unwrap_or(false);

        let options = PreviewOptions {
            decorated: cli.decorated,
            resizable: cli.resizable,
            close_on_escape: !cli.no_escape_close,
            debug_frame: cli.debug_frame,
            desktop_hints: cli.desktop_hints || profile_desktop_hints,
        };

        let widget_paths = collect_widget_paths(&cli, loaded_profile.as_ref())?;
        let mut widgets = Vec::new();

        for widget_path in &widget_paths {
            let widget = load_widget_from_path(widget_path)
                .with_context(|| format!("failed to load widget {}", widget_path.display()))?;

            validate_preview_widget(&widget)
                .with_context(|| format!("widget {} is not previewable", widget_path.display()))?;

            tracing::info!(
                path = %widget_path.display(),
                widget_id = %widget.id.0,
                widget_name = %widget.name,
                "loaded NeoDash preview widget"
            );

            widgets.push(Rc::new(widget));
        }

        let widgets = Rc::new(widgets);

        tracing::info!(
            widget_count = widgets.len(),
            desktop_hints = options.desktop_hints,
            "loaded NeoDash preview widget set"
        );

        let app = gtk::Application::builder()
            .application_id("io.github.adamjvr.NeoDash")
            .build();

        app.connect_activate(move |app| {
            for widget in widgets.iter() {
                build_widget_window(app, Rc::clone(widget), options);
            }
        });

        // GTK/GApplication also tries to parse process arguments when `run()` is
        // called. Clap already parsed NeoDash-specific arguments above, so the
        // real argv would make GTK complain about options like `--widget`.
        app.run_with_args::<&str>(&["neodash-app"]);

        Ok(())
    }

    /// Validate a loaded profile before the GTK app opens windows.
    fn validate_loaded_profile(loaded: &LoadedProfile) -> anyhow::Result<()> {
        let report = validate_profile(loaded)?;

        for issue in &report.issues {
            let path = issue
                .path
                .as_ref()
                .map(|path| path.display().to_string())
                .unwrap_or_else(|| "<profile>".to_string());
            let widget_id = issue.widget_id.as_deref().unwrap_or("<none>");

            match issue.severity {
                ProfileValidationSeverity::Warning => tracing::warn!(
                    path = %path,
                    widget_id = widget_id,
                    message = %issue.message,
                    "profile validation warning"
                ),
                ProfileValidationSeverity::Error => tracing::error!(
                    path = %path,
                    widget_id = widget_id,
                    message = %issue.message,
                    "profile validation error"
                ),
            }
        }

        anyhow::ensure!(
            !report.has_errors(),
            "profile {} failed validation with {} error(s) and {} warning(s)",
            loaded.path.display(),
            report.error_count(),
            report.warning_count()
        );

        Ok(())
    }

    /// Collect widget paths from an optional profile plus explicit CLI arguments.
    ///
    /// Loading order: profile widgets, profile widget_dirs, explicit --widget,
    /// then explicit --widgets-dir.
    fn collect_widget_paths(
        cli: &Cli,
        loaded_profile: Option<&LoadedProfile>,
    ) -> anyhow::Result<Vec<PathBuf>> {
        let mut paths = Vec::new();

        if let Some(loaded) = loaded_profile {
            paths.extend(collect_profile_widget_paths(loaded)?);
        }

        paths.extend(cli.widgets.iter().cloned());
        for dir in &cli.widget_dirs {
            paths.extend(discover_widget_paths(dir)?);
        }

        anyhow::ensure!(
            !paths.is_empty(),
            "no widgets requested; pass --profile FILE, --widget FILE, or --widgets-dir DIR"
        );

        Ok(paths)
    }

    /// Reject unsupported widget types before GTK opens a window.
    fn validate_preview_widget(widget: &WidgetConfig) -> anyhow::Result<()> {
        anyhow::ensure!(
            widget.enabled,
            "widget '{}' is disabled; refusing to preview it",
            widget.name
        );

        anyhow::ensure!(
            widget.widget_type == WidgetType::Shell,
            "neodash-app preview currently supports only shell widgets; '{}' is {:?}",
            widget.name,
            widget.widget_type
        );

        anyhow::ensure!(
            widget
                .source
                .command
                .as_deref()
                .is_some_and(|command| !command.trim().is_empty()),
            "shell widget '{}' is missing a non-empty [source].command",
            widget.name
        );

        Ok(())
    }

    /// Build the current NeoDash GTK preview window.
    ///
    /// This is still deliberately plain GTK4.
    ///
    /// We use `geometry.width` and `geometry.height` here. Exact X/Y placement
    /// is still a backend problem:
    ///
    /// - X11: X11/EWMH/native placement path
    /// - Wayland: layer-shell path
    ///
    /// This iteration adds optional X11 desktop-style window-manager hints, but
    /// not forced coordinate placement yet.
    fn build_widget_window(
        app: &gtk::Application,
        widget: Rc<WidgetConfig>,
        options: PreviewOptions,
    ) {
        let backend = detect_backend_from_env();
        let window_title = format!(
            "NeoDash Preview - {} [{}:{}]",
            widget.name,
            widget.id.0,
            std::process::id()
        );

        tracing::info!(
            ?backend.kind,
            reason = %backend.reason,
            widget_id = %widget.id.0,
            widget_name = %widget.name,
            decorated = options.decorated,
            resizable = options.resizable,
            close_on_escape = options.close_on_escape,
            debug_frame = options.debug_frame,
            desktop_hints = options.desktop_hints,
            "opening NeoDash widget preview"
        );

        let label = gtk::Label::new(Some("NeoDash loading..."));
        label.set_xalign(0.0);
        label.set_yalign(0.0);
        label.set_wrap(true);
        label.set_selectable(true);
        label.add_css_class("neodash-widget-label");

        let frame = gtk::Box::new(gtk::Orientation::Vertical, 0);
        frame.add_css_class("neodash-widget-frame");

        if options.debug_frame {
            frame.add_css_class("neodash-debug-frame");
        }

        frame.set_margin_top(widget.style.padding as i32);
        frame.set_margin_bottom(widget.style.padding as i32);
        frame.set_margin_start(widget.style.padding as i32);
        frame.set_margin_end(widget.style.padding as i32);
        frame.append(&label);

        let window = gtk::ApplicationWindow::builder()
            .application(app)
            .title(&window_title)
            .default_width(widget.geometry.width)
            .default_height(widget.geometry.height)
            .decorated(options.decorated)
            .resizable(options.resizable)
            .child(&frame)
            .build();

        if options.close_on_escape {
            install_escape_to_close(&window);
        }

        install_widget_css(&widget);

        window.present();

        schedule_desktop_hints(options.desktop_hints, window_title, widget.geometry.clone());

        let label = Rc::new(label);
        let last_output = Rc::new(RefCell::new(String::new()));

        refresh_label_once(
            Rc::clone(&widget),
            Rc::clone(&label),
            Rc::clone(&last_output),
        );

        let interval_ms = widget.source.interval_ms.max(1);

        glib::timeout_add_local(Duration::from_millis(interval_ms), move || {
            refresh_label_once(
                Rc::clone(&widget),
                Rc::clone(&label),
                Rc::clone(&last_output),
            );
            glib::ControlFlow::Continue
        });
    }

    /// Apply desktop-widget behavior after GTK has had a moment to realize/map
    /// the native window.
    ///
    /// GTK exposes a high-level cross-platform window API. The X11 desktop hints
    /// and X/Y placement are lower-level X11/EWMH operations on the native X11
    /// window.
    ///
    /// For this development pass, we find the X11 window by its unique title
    /// after presentation. That is still a temporary seam, but now the backend
    /// operation has enough data to apply the widget's configured geometry too.
    ///
    /// Future cleanup target:
    ///
    /// - split X11 behavior out of `neodash-app`
    /// - expose a real platform surface API from `neodash-platform`
    /// - pass a native window handle instead of title-searching
    fn schedule_desktop_hints(enabled: bool, window_title: String, geometry: GeometryConfig) {
        if !enabled {
            return;
        }

        #[cfg(feature = "x11-desktop")]
        {
            glib::timeout_add_local(Duration::from_millis(250), move || {
                match x11_desktop::apply_desktop_widget_behavior(&window_title, &geometry) {
                    Ok(()) => {
                        tracing::info!(
                            window_title = %window_title,
                            x = geometry.x,
                            y = geometry.y,
                            width = geometry.width,
                            height = geometry.height,
                            "applied X11 desktop-widget hints and geometry"
                        );
                    }
                    Err(error) => {
                        tracing::warn!(
                            window_title = %window_title,
                            error = %error,
                            "failed to apply X11 desktop-widget behavior"
                        );
                    }
                }

                glib::ControlFlow::Break
            });
        }

        #[cfg(not(feature = "x11-desktop"))]
        {
            let _ = window_title;
            let _ = geometry;

            tracing::warn!(
                "desktop hints requested, but neodash-app was built without the x11-desktop feature"
            );
        }
    }

    /// Add Escape-to-close support to the preview window.
    fn install_escape_to_close(window: &gtk::ApplicationWindow) {
        let controller = gtk::EventControllerKey::new();
        let weak_window = window.downgrade();

        controller.connect_key_pressed(move |_, key, _, _| {
            if key == gtk::gdk::Key::Escape {
                if let Some(window) = weak_window.upgrade() {
                    window.close();
                }

                glib::Propagation::Stop
            } else {
                glib::Propagation::Proceed
            }
        });

        window.add_controller(controller);
    }

    /// Run one command frame and update the visible label.
    fn refresh_label_once(
        widget: Rc<WidgetConfig>,
        label: Rc<gtk::Label>,
        last_output: Rc<RefCell<String>>,
    ) {
        let text = match run_shell_command_once(&widget.source) {
            Ok(output) => {
                let mut text = output.stdout;

                if widget.source.show_stderr && !output.stderr.is_empty() {
                    push_newline_if_needed(&mut text);
                    text.push_str(&output.stderr);
                }

                if output.timed_out {
                    push_newline_if_needed(&mut text);
                    text.push_str(&format!(
                        "neodash: warning: command exceeded timeout after {:?}",
                        output.elapsed
                    ));
                }

                if let Some(code) = output.status_code {
                    if code != 0 {
                        push_newline_if_needed(&mut text);
                        text.push_str(&format!(
                            "neodash: warning: command exited with status code {code}"
                        ));
                    }
                }

                if text.trim().is_empty() {
                    "NeoDash command produced no output".to_string()
                } else {
                    text
                }
            }
            Err(error) => format!("NeoDash command error:\n{error:#}"),
        };

        let mut previous = last_output.borrow_mut();

        if *previous != text {
            label.set_text(&text);
            *previous = text;
        }
    }

    fn push_newline_if_needed(text: &mut String) {
        if !text.ends_with('\n') {
            text.push('\n');
        }
    }

    /// Install minimal CSS generated from `StyleConfig`.
    fn install_widget_css(widget: &WidgetConfig) {
        let background = css_color(&widget.style.background);
        let foreground = css_color(&widget.style.foreground);
        let font_family = widget.style.font_family.replace('"', "\\\"");

        let css = format!(
            r#"
            .neodash-widget-frame {{
                background: {};
                opacity: {};
                border-radius: {}px;
            }}

            .neodash-debug-frame {{
                border: 1px solid rgba(255, 255, 255, 0.65);
            }}

            .neodash-widget-label {{
                color: {};
                font-family: "{}";
                font-size: {}px;
            }}
            "#,
            background,
            widget.style.opacity,
            widget.style.border_radius,
            foreground,
            font_family,
            widget.style.font_size,
        );

        let provider = gtk::CssProvider::new();
        provider.load_from_data(&css);

        if let Some(display) = gtk::gdk::Display::default() {
            gtk::style_context_add_provider_for_display(
                &display,
                &provider,
                gtk::STYLE_PROVIDER_PRIORITY_APPLICATION,
            );
        }
    }

    /// Convert simple NeoDash color strings into GTK-friendly CSS colors.
    fn css_color(input: &str) -> String {
        let trimmed = input.trim();

        if let Some(hex) = trimmed.strip_prefix('#') {
            if hex.len() == 6 {
                return trimmed.to_string();
            }

            if hex.len() == 8 {
                let red = u8::from_str_radix(&hex[0..2], 16);
                let green = u8::from_str_radix(&hex[2..4], 16);
                let blue = u8::from_str_radix(&hex[4..6], 16);
                let alpha = u8::from_str_radix(&hex[6..8], 16);

                if let (Ok(red), Ok(green), Ok(blue), Ok(alpha)) = (red, green, blue, alpha) {
                    let alpha = alpha as f32 / 255.0;
                    return format!("rgba({red}, {green}, {blue}, {alpha:.3})");
                }
            }
        }

        trimmed.to_string()
    }

    #[cfg(feature = "x11-desktop")]
    mod x11_desktop {
        use neodash_core::GeometryConfig;
        use x11rb::{
            connection::Connection,
            protocol::xproto::{
                Atom, AtomEnum, ConfigureWindowAux, ConnectionExt, PropMode, Window,
            },
            rust_connection::RustConnection,
            wrapper::ConnectionExt as _,
        };

        /// X11 atoms used by the temporary X11 preview backend.
        ///
        /// These are mostly EWMH window-manager properties. Window managers are
        /// allowed to interpret some of them differently, so NeoDash treats this
        /// as a best-effort desktop-widget behavior pass rather than a hard
        /// guarantee.
        struct X11Atoms {
            net_wm_name: Atom,
            utf8_string: Atom,
            net_wm_state: Atom,
            net_wm_state_skip_taskbar: Atom,
            net_wm_state_skip_pager: Atom,
            net_wm_state_sticky: Atom,
            net_wm_state_below: Atom,
            net_wm_desktop: Atom,
        }

        impl X11Atoms {
            fn new<C: Connection>(connection: &C) -> anyhow::Result<Self> {
                Ok(Self {
                    net_wm_name: intern_atom(connection, b"_NET_WM_NAME")?,
                    utf8_string: intern_atom(connection, b"UTF8_STRING")?,
                    net_wm_state: intern_atom(connection, b"_NET_WM_STATE")?,
                    net_wm_state_skip_taskbar: intern_atom(
                        connection,
                        b"_NET_WM_STATE_SKIP_TASKBAR",
                    )?,
                    net_wm_state_skip_pager: intern_atom(connection, b"_NET_WM_STATE_SKIP_PAGER")?,
                    net_wm_state_sticky: intern_atom(connection, b"_NET_WM_STATE_STICKY")?,
                    net_wm_state_below: intern_atom(connection, b"_NET_WM_STATE_BELOW")?,
                    net_wm_desktop: intern_atom(connection, b"_NET_WM_DESKTOP")?,
                })
            }
        }

        /// Apply the current X11 desktop-widget behavior.
        ///
        /// This does two things:
        ///
        /// 1. Applies EWMH hints:
        ///    - skip taskbar
        ///    - skip pager
        ///    - sticky/all workspaces
        ///    - below normal windows
        ///
        /// 2. Applies configured geometry:
        ///    - x
        ///    - y
        ///    - width
        ///    - height
        ///
        /// The title-search lookup is temporary. It works well enough for this
        /// preview, but the final backend should use a real native window handle.
        pub fn apply_desktop_widget_behavior(
            window_title: &str,
            geometry: &GeometryConfig,
        ) -> anyhow::Result<()> {
            let (connection, screen_number) = RustConnection::connect(None)?;
            let screen = &connection.setup().roots[screen_number];
            let root = screen.root;
            let atoms = X11Atoms::new(&connection)?;

            let window = find_window_by_title(&connection, root, &atoms, window_title)?
                .ok_or_else(|| {
                    anyhow::anyhow!("could not find X11 window titled {window_title:?}")
                })?;

            apply_state_hints(&connection, window, &atoms)?;
            apply_geometry(&connection, window, geometry)?;

            connection.flush()?;

            Ok(())
        }

        /// Apply EWMH state properties that make the window behave more like a
        /// desktop widget than a normal application window.
        fn apply_state_hints<C: Connection>(
            connection: &C,
            window: Window,
            atoms: &X11Atoms,
        ) -> anyhow::Result<()> {
            let states = [
                atoms.net_wm_state_skip_taskbar,
                atoms.net_wm_state_skip_pager,
                atoms.net_wm_state_sticky,
                atoms.net_wm_state_below,
            ];

            connection.change_property32(
                PropMode::REPLACE,
                window,
                atoms.net_wm_state,
                AtomEnum::ATOM,
                &states,
            )?;

            // 0xFFFFFFFF means "all desktops" in EWMH.
            connection.change_property32(
                PropMode::REPLACE,
                window,
                atoms.net_wm_desktop,
                AtomEnum::CARDINAL,
                &[u32::MAX],
            )?;

            Ok(())
        }

        /// Apply the geometry from the widget TOML file to the X11 window.
        ///
        /// GTK4 no longer exposes simple global-coordinate window positioning.
        /// On X11, however, a backend can still request placement through the X
        /// server. Window managers may adjust the final position, but this gives
        /// NeoDash the correct direction for X11 desktop widgets.
        fn apply_geometry<C: Connection>(
            connection: &C,
            window: Window,
            geometry: &GeometryConfig,
        ) -> anyhow::Result<()> {
            let width = geometry.width.max(1) as u32;
            let height = geometry.height.max(1) as u32;

            connection.configure_window(
                window,
                &ConfigureWindowAux::new()
                    .x(geometry.x)
                    .y(geometry.y)
                    .width(width)
                    .height(height),
            )?;

            Ok(())
        }

        fn intern_atom<C: Connection>(connection: &C, name: &[u8]) -> anyhow::Result<Atom> {
            Ok(connection.intern_atom(false, name)?.reply()?.atom)
        }

        fn find_window_by_title<C: Connection>(
            connection: &C,
            root: Window,
            atoms: &X11Atoms,
            title: &str,
        ) -> anyhow::Result<Option<Window>> {
            let mut stack = vec![root];

            while let Some(window) = stack.pop() {
                if window_has_title(connection, window, atoms, title).unwrap_or(false) {
                    return Ok(Some(window));
                }

                let tree = match connection.query_tree(window) {
                    Ok(cookie) => match cookie.reply() {
                        Ok(tree) => tree,
                        Err(_) => continue,
                    },
                    Err(_) => continue,
                };

                stack.extend(tree.children);
            }

            Ok(None)
        }

        fn window_has_title<C: Connection>(
            connection: &C,
            window: Window,
            atoms: &X11Atoms,
            title: &str,
        ) -> anyhow::Result<bool> {
            if property_contains_text(
                connection,
                window,
                atoms.net_wm_name,
                atoms.utf8_string,
                title,
            )? {
                return Ok(true);
            }

            property_contains_text(
                connection,
                window,
                AtomEnum::WM_NAME.into(),
                AtomEnum::STRING.into(),
                title,
            )
        }

        fn property_contains_text<C: Connection>(
            connection: &C,
            window: Window,
            property: Atom,
            property_type: Atom,
            text: &str,
        ) -> anyhow::Result<bool> {
            let reply = connection
                .get_property(false, window, property, property_type, 0, 1024)?
                .reply()?;

            if reply.value.is_empty() {
                return Ok(false);
            }

            let value = String::from_utf8_lossy(&reply.value);

            Ok(value.contains(text))
        }
    }
}
