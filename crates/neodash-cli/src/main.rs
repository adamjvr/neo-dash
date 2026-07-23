// SPDX-License-Identifier: MPL-2.0

use clap::{Parser, Subcommand};
use neodash_core::{
    collect_profile_widget_paths, load_profile_from_path, validate_profile, LoadedProfile,
    ProfileValidationReport, ProfileValidationSeverity, SourceConfig, WidgetConfig, WidgetId,
    WidgetType,
};
use neodash_platform::detect_backend_from_env;
use neodash_runtime::{
    run_source_to_terminal, run_widget_path_to_terminal, RefreshMode, TerminalRunOptions,
};
use std::path::PathBuf;

#[derive(Debug, Parser)]
#[command(name = "neodash")]
#[command(about = "NeoDash command line tool")]
struct Cli {
    #[command(subcommand)]
    command: Commands,
}

#[derive(Debug, Subcommand)]
enum Commands {
    /// Run an ad-hoc shell command through the NeoDash source runtime.
    Run {
        /// Command to run through the selected shell.
        #[arg(long)]
        command: String,

        /// Refresh interval in milliseconds when --watch is enabled.
        #[arg(long, default_value_t = 1000)]
        interval: u64,

        /// Shell executable.
        #[arg(long, default_value = "/bin/bash")]
        shell: String,

        /// Keep running the command on the configured interval until interrupted.
        #[arg(long, default_value_t = false)]
        watch: bool,

        /// Clear the terminal before each watched frame.
        #[arg(long, default_value_t = false)]
        clear: bool,
    },

    /// Run a shell widget from a NeoDash TOML config file.
    RunWidget {
        /// Path to a widget TOML file, for example examples/widgets/date.toml.
        path: PathBuf,

        /// Run the widget once instead of refreshing forever.
        #[arg(long, default_value_t = false)]
        once: bool,

        /// Clear the terminal before each watched frame.
        #[arg(long, default_value_t = false)]
        clear: bool,
    },

    /// Inspect a NeoDash profile and print the resolved widget paths.
    ProfileInfo {
        /// Path to a profile TOML file, for example examples/profiles/default.toml.
        path: PathBuf,
    },

    /// Validate a NeoDash profile and every widget file it references.
    ProfileCheck {
        /// Path to a profile TOML file, for example examples/profiles/default.toml.
        path: PathBuf,
    },

    /// Print the backend NeoDash would probably use in this session.
    Backend,

    /// Print an example widget TOML config.
    ExampleWidget,
}

fn print_profile_validation_report(loaded: &LoadedProfile, report: &ProfileValidationReport) {
    println!("Profile file: {}", loaded.path.display());
    println!(
        "Profile id: {}",
        loaded.profile.id.as_deref().unwrap_or("<unnamed>")
    );
    println!(
        "Profile name: {}",
        loaded.profile.name.as_deref().unwrap_or("<unnamed>")
    );
    println!("Widget files: {}", report.widget_paths.len());
    println!(
        "Issues: {} error(s), {} warning(s)",
        report.error_count(),
        report.warning_count()
    );

    if report.issues.is_empty() {
        println!("Profile OK");
        return;
    }

    for issue in &report.issues {
        let severity = match issue.severity {
            ProfileValidationSeverity::Warning => "warning",
            ProfileValidationSeverity::Error => "error",
        };

        match (&issue.path, &issue.widget_id) {
            (Some(path), Some(widget_id)) => {
                println!(
                    "  {severity}: {} [{}]: {}",
                    path.display(),
                    widget_id,
                    issue.message
                );
            }
            (Some(path), None) => {
                println!("  {severity}: {}: {}", path.display(), issue.message);
            }
            (None, Some(widget_id)) => {
                println!("  {severity}: [{widget_id}]: {}", issue.message);
            }
            (None, None) => {
                println!("  {severity}: {}", issue.message);
            }
        }
    }
}

fn main() -> anyhow::Result<()> {
    tracing_subscriber::fmt().with_env_filter("warn").init();

    let cli = Cli::parse();

    match cli.command {
        Commands::Run {
            command,
            interval,
            shell,
            watch,
            clear,
        } => {
            let source = SourceConfig {
                command: Some(command),
                shell: Some(shell),
                interval_ms: interval,
                ..SourceConfig::default()
            };

            let refresh_mode = if watch {
                RefreshMode::Watch
            } else {
                RefreshMode::Once
            };

            let options = TerminalRunOptions {
                refresh_mode,
                clear_between_frames: clear,
            };

            run_source_to_terminal(&source, options)?;
        }
        Commands::RunWidget { path, once, clear } => {
            let refresh_mode = if once {
                RefreshMode::Once
            } else {
                RefreshMode::Watch
            };

            let options = TerminalRunOptions {
                refresh_mode,
                clear_between_frames: clear,
            };

            run_widget_path_to_terminal(path, options)?;
        }
        Commands::ProfileInfo { path } => {
            let loaded = load_profile_from_path(&path)?;
            let widget_paths = collect_profile_widget_paths(&loaded)?;

            println!("Profile file: {}", loaded.path.display());
            println!(
                "Profile id: {}",
                loaded.profile.id.as_deref().unwrap_or("<unnamed>")
            );
            println!(
                "Profile name: {}",
                loaded.profile.name.as_deref().unwrap_or("<unnamed>")
            );
            println!(
                "Desktop hints: {}",
                loaded
                    .profile
                    .desktop_hints
                    .map(|value| value.to_string())
                    .unwrap_or_else(|| "not set".to_string())
            );
            println!("Widget files: {}", widget_paths.len());

            for path in widget_paths {
                println!("  {}", path.display());
            }
        }
        Commands::ProfileCheck { path } => {
            let loaded = load_profile_from_path(&path)?;
            let report = validate_profile(&loaded)?;

            print_profile_validation_report(&loaded, &report);

            if report.has_errors() {
                anyhow::bail!(
                    "profile validation failed with {} error(s) and {} warning(s)",
                    report.error_count(),
                    report.warning_count()
                );
            }
        }
        Commands::Backend => {
            let backend = detect_backend_from_env();
            println!("{:?}: {}", backend.kind, backend.reason);
        }
        Commands::ExampleWidget => {
            let widget = WidgetConfig {
                id: WidgetId("date-clock".to_string()),
                name: "Date Clock".to_string(),
                widget_type: WidgetType::Shell,
                enabled: true,
                source: SourceConfig {
                    command: Some("date '+%Y-%m-%d %H:%M:%S'".to_string()),
                    shell: Some("/bin/bash".to_string()),
                    interval_ms: 1_000,
                    timeout_ms: 800,
                    show_stderr: false,
                    parse_ansi: true,
                    ..SourceConfig::default()
                },
                geometry: Default::default(),
                style: Default::default(),
            };

            println!("{}", neodash_core::save_widget_to_toml_string(&widget)?);
        }
    }

    Ok(())
}
