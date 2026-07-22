// SPDX-License-Identifier: MPL-2.0

//! Headless widget runtime for NeoDash.
//!
//! This crate is deliberately boring and deliberately useful.  The CLI, daemon,
//! and future GTK app all need the same core behavior:
//!
//! 1. Load a widget config.
//! 2. Validate that the widget type can run in the current runtime path.
//! 3. Execute the widget source once, or repeatedly on its configured interval.
//! 4. Send the resulting text somewhere.
//!
//! For this first runtime iteration, "somewhere" is the terminal.  Later, the
//! GTK renderer should get a sibling API that returns frames/events instead of
//! printing.  Keeping this loop out of `neodash-cli` is important because the CLI
//! should be a front-end, not the place where app behavior accidentally lives.

use anyhow::Context;
use neodash_core::{load_widget_from_toml_str, SourceConfig, WidgetConfig, WidgetType};
use neodash_exec::{run_shell_command_once, CommandOutput};
use std::{
    fs,
    io::{self, Write},
    path::Path,
    thread,
    time::Duration,
};

/// Describes whether a runtime should execute a source once or keep refreshing.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum RefreshMode {
    /// Execute one frame and return.
    Once,

    /// Execute forever, sleeping `source.interval_ms` between frames.
    ///
    /// This intentionally relies on the user pressing Ctrl+C for now.  A future
    /// daemon runtime should use a cancellation token or channel instead.
    Watch,
}

/// Options for the terminal-backed runtime path.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct TerminalRunOptions {
    /// Whether to run once or continuously refresh.
    pub refresh_mode: RefreshMode,

    /// Clear the terminal before each watched frame.
    ///
    /// This makes the CLI feel closer to a single live widget surface, while the
    /// default append behavior remains nicer for smoke tests and logs.
    pub clear_between_frames: bool,
}

impl TerminalRunOptions {
    /// Build options for one-shot execution.
    pub fn once() -> Self {
        Self {
            refresh_mode: RefreshMode::Once,
            clear_between_frames: false,
        }
    }

    /// Build options for watched execution.
    pub fn watch() -> Self {
        Self {
            refresh_mode: RefreshMode::Watch,
            clear_between_frames: false,
        }
    }

    /// Return a copy of the options with terminal clearing toggled.
    pub fn with_clear_between_frames(mut self, enabled: bool) -> Self {
        self.clear_between_frames = enabled;
        self
    }
}

/// Load a widget TOML file from disk.
///
/// This is intentionally placed in the runtime crate rather than the core config
/// module because `neodash-core` should only know how to parse strings.  File IO
/// belongs at the runtime/app boundary.
pub fn load_widget_from_path(path: impl AsRef<Path>) -> anyhow::Result<WidgetConfig> {
    let path = path.as_ref();
    let text = fs::read_to_string(path)
        .with_context(|| format!("failed to read widget config at {}", path.display()))?;

    load_widget_from_toml_str(&text)
        .with_context(|| format!("failed to parse widget config at {}", path.display()))
}

/// Run a widget loaded from a TOML file and print frames to the terminal.
pub fn run_widget_path_to_terminal(
    path: impl AsRef<Path>,
    options: TerminalRunOptions,
) -> anyhow::Result<()> {
    let widget = load_widget_from_path(path)?;
    run_widget_to_terminal(&widget, options)
}

/// Run a parsed widget config and print frames to the terminal.
pub fn run_widget_to_terminal(
    widget: &WidgetConfig,
    options: TerminalRunOptions,
) -> anyhow::Result<()> {
    validate_terminal_widget(widget)?;
    run_source_to_terminal(&widget.source, options)
}

/// Run a source config and print command output to the terminal.
///
/// This function is intentionally source-oriented instead of command-string
/// oriented.  The GUI will eventually build `SourceConfig` values, not loose
/// strings, and the config file already stores source settings this way.
pub fn run_source_to_terminal(
    source: &SourceConfig,
    options: TerminalRunOptions,
) -> anyhow::Result<()> {
    match options.refresh_mode {
        RefreshMode::Once => run_one_terminal_frame(source),
        RefreshMode::Watch => loop {
            if options.clear_between_frames {
                clear_terminal()?;
            }

            run_one_terminal_frame(source)?;

            // Avoid accidental busy loops if somebody sets interval_ms = 0 in a
            // handwritten config.  One millisecond is still silly-fast, but it
            // prevents pegging a CPU core instantly.
            let sleep_ms = source.interval_ms.max(1);
            thread::sleep(Duration::from_millis(sleep_ms));
        },
    }
}

/// Validate that the current terminal runtime knows how to execute this widget.
fn validate_terminal_widget(widget: &WidgetConfig) -> anyhow::Result<()> {
    anyhow::ensure!(
        widget.enabled,
        "widget '{}' is disabled; refusing to run it from the CLI",
        widget.name
    );

    anyhow::ensure!(
        widget.widget_type == WidgetType::Shell,
        "run-widget currently supports only shell widgets; widget '{}' has type {:?}",
        widget.name,
        widget.widget_type
    );

    anyhow::ensure!(
        widget
            .source
            .command
            .as_deref()
            .is_some_and(|cmd| !cmd.trim().is_empty()),
        "shell widget '{}' is missing a non-empty [source].command",
        widget.name
    );

    Ok(())
}

/// Execute one command frame and write it to the terminal.
fn run_one_terminal_frame(source: &SourceConfig) -> anyhow::Result<()> {
    let output = run_shell_command_once(source)?;
    write_command_output(&output, source.show_stderr)
}

/// Write a command result to stdout/stderr.
///
/// A non-zero exit status is not treated as a runtime error here.  NeoDash is a
/// dashboard tool: a script may fail temporarily because Wi-Fi is down, a server
/// is asleep, or a file does not exist yet.  The runtime should keep breathing.
fn write_command_output(output: &CommandOutput, show_stderr: bool) -> anyhow::Result<()> {
    {
        let mut stdout = io::stdout().lock();
        stdout.write_all(output.stdout.as_bytes())?;
        stdout.flush()?;
    }

    {
        let mut stderr = io::stderr().lock();

        if show_stderr && !output.stderr.is_empty() {
            stderr.write_all(output.stderr.as_bytes())?;
        }

        if output.timed_out {
            writeln!(
                stderr,
                "neodash: warning: command exceeded configured timeout after {:?}",
                output.elapsed
            )?;
        }

        if let Some(code) = output.status_code {
            if code != 0 {
                writeln!(
                    stderr,
                    "neodash: warning: command exited with status code {}",
                    code
                )?;
            }
        }

        stderr.flush()?;
    }

    Ok(())
}

/// Clear the terminal and return the cursor to the top-left corner.
fn clear_terminal() -> anyhow::Result<()> {
    let mut stdout = io::stdout().lock();
    stdout.write_all(b"\x1b[2J\x1b[H")?;
    stdout.flush()?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use neodash_core::{SourceConfig, WidgetConfig, WidgetId};

    #[test]
    fn one_shot_options_do_not_clear_terminal() {
        let options = TerminalRunOptions::once();
        assert_eq!(options.refresh_mode, RefreshMode::Once);
        assert!(!options.clear_between_frames);
    }

    #[test]
    fn watch_options_can_enable_terminal_clearing() {
        let options = TerminalRunOptions::watch().with_clear_between_frames(true);
        assert_eq!(options.refresh_mode, RefreshMode::Watch);
        assert!(options.clear_between_frames);
    }

    #[test]
    fn rejects_non_shell_widgets_for_terminal_runtime() {
        let widget = WidgetConfig {
            id: WidgetId("note".to_string()),
            name: "Note".to_string(),
            widget_type: WidgetType::Text,
            enabled: true,
            source: SourceConfig::default(),
            geometry: Default::default(),
            style: Default::default(),
        };

        let error = validate_terminal_widget(&widget).expect_err("text widget should fail");
        assert!(error.to_string().contains("supports only shell widgets"));
    }
}
