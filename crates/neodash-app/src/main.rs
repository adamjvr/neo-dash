// SPDX-License-Identifier: MPL-2.0

// NeoDash currently supports two app builds:
//
// 1. The default build, with no GUI feature enabled.
//    This keeps CI, headless systems, and distro build sanity checks simple.
//
// 2. The `gui` feature build.
//    This enables the first real GTK4 widget preview window.
//
// The important architectural choice here is that the default app target does
// not drag GTK into the entire workspace. NeoDash's core model, command runtime,
// CLI, daemon, and tests should stay buildable without desktop libraries.

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
        #[arg(long)]
        widget: Option<PathBuf>,
    }

    tracing_subscriber::fmt().with_env_filter("info").init();

    let cli = Cli::parse();
    let backend = detect_backend_from_env();

    println!("NeoDash GTK app skeleton");
    println!("backend guess: {:?} - {}", backend.kind, backend.reason);

    if let Some(widget) = cli.widget {
        println!("requested widget: {}", widget.display());
    }

    println!();
    println!("This binary was built without GUI support.");
    println!();
    println!("Run:");
    println!("  cargo run -p neodash-app --features gui -- --widget examples/widgets/date.toml");

    Ok(())
}

#[cfg(feature = "gui")]
fn main() -> anyhow::Result<()> {
    gui::run()
}

#[cfg(feature = "gui")]
mod gui {
    use clap::Parser;
    use gtk::glib;
    use gtk::prelude::*;
    use neodash_core::{WidgetConfig, WidgetType};
    use neodash_exec::run_shell_command_once;
    use neodash_platform::detect_backend_from_env;
    use neodash_runtime::load_widget_from_path;
    use std::{cell::RefCell, path::PathBuf, rc::Rc, time::Duration};

    /// Command line arguments for the first graphical NeoDash preview.
    ///
    /// This is intentionally not the full visual editor yet.
    ///
    /// The first GUI milestone is:
    ///
    /// - load one widget TOML file
    /// - run its shell command repeatedly
    /// - display the output in a native GTK label
    /// - use the geometry/style values that already exist in the config model
    ///
    /// Once this works, the next layer can make the window behave like a true
    /// desktop widget on X11 and Wayland.
    #[derive(Debug, Parser)]
    #[command(name = "neodash-app")]
    #[command(about = "NeoDash graphical widget preview")]
    struct Cli {
        /// Widget TOML file to preview.
        #[arg(long)]
        widget: PathBuf,
    }

    pub fn run() -> anyhow::Result<()> {
        tracing_subscriber::fmt().with_env_filter("info").init();

        let cli = Cli::parse();
        let widget = load_widget_from_path(&cli.widget)?;

        validate_preview_widget(&widget)?;

        let app = gtk::Application::builder()
            .application_id("io.github.adamjvr.NeoDash")
            .build();

        let widget = Rc::new(widget);

        app.connect_activate(move |app| {
            build_widget_window(app, Rc::clone(&widget));
        });

        // GTK/GApplication also tries to parse process arguments when `run()`
        // is called. We already parsed NeoDash-specific arguments with Clap
        // above, so passing the real argv through again makes GTK complain about
        // options like `--widget`.
        //
        // Use a sanitized argv containing only the program name. This keeps
        // Clap in charge of NeoDash CLI options and GTK in charge of the app
        // lifecycle.
        app.run_with_args::<&str>(&["neodash-app"]);

        Ok(())
    }

    /// Reject unsupported widget types before GTK opens a window.
    ///
    /// This keeps the preview honest. A blank window is worse than a clear error.
    /// The only renderer implemented in this file is shell-command text output.
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

    /// Build the first real NeoDash window.
    ///
    /// This is deliberately plain GTK4.
    ///
    /// It does not use layer-shell yet.
    /// It does not try to become a desktop-pinned window yet.
    /// It does not use libadwaita yet.
    ///
    /// That restraint matters: we are proving the renderer first. Once a normal
    /// native GTK window can show a live widget, we can wrap that window with
    /// backend-specific X11 or Wayland behavior.
    fn build_widget_window(app: &gtk::Application, widget: Rc<WidgetConfig>) {
        let backend = detect_backend_from_env();

        tracing::info!(
            ?backend.kind,
            reason = %backend.reason,
            widget_id = %widget.id.0,
            widget_name = %widget.name,
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
        frame.set_margin_top(widget.style.padding as i32);
        frame.set_margin_bottom(widget.style.padding as i32);
        frame.set_margin_start(widget.style.padding as i32);
        frame.set_margin_end(widget.style.padding as i32);
        frame.append(&label);

        let window = gtk::ApplicationWindow::builder()
            .application(app)
            .title(&widget.name)
            .default_width(widget.geometry.width)
            .default_height(widget.geometry.height)
            .decorated(false)
            .child(&frame)
            .build();

        install_widget_css(&widget);

        // Since this first preview window is undecorated, the easiest close path
        // during development is Ctrl+C in the terminal that launched it.
        window.present();

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

    /// Run one command frame and update the visible label.
    ///
    /// The label is updated only when the rendered text changes. That is not
    /// necessary for a one-label preview, but it is the right instinct for a
    /// dashboard system where many widgets may refresh independently.
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
    ///
    /// GTK CSS does not reliably accept every CSS color syntax that browsers do,
    /// so `css_color` converts NeoDash's default #RRGGBBAA color into rgba().
    /// That keeps the default widget background from becoming a GTK warning.
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
    ///
    /// Supported direct forms:
    ///
    /// - #RRGGBB
    /// - #RRGGBBAA
    ///
    /// Anything else is returned unchanged so advanced users can still pass
    /// normal GTK CSS color names or rgba() values later.
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
}
