// SPDX-License-Identifier: MPL-2.0

use clap::{Parser, Subcommand};
use neodash_core::{SourceConfig, WidgetConfig, WidgetId, WidgetType};
use neodash_exec::run_shell_command_once;
use neodash_platform::detect_backend_from_env;

#[derive(Debug, Parser)]
#[command(name = "neodash")]
#[command(about = "NeoDash command line tool")]
struct Cli {
    #[command(subcommand)]
    command: Commands,
}

#[derive(Debug, Subcommand)]
enum Commands {
    /// Run a command once through the NeoDash shell source path.
    Run {
        /// Command to run through the selected shell.
        #[arg(long)]
        command: String,

        /// Refresh interval in milliseconds. This skeleton prints once for now.
        #[arg(long, default_value_t = 1000)]
        interval: u64,

        /// Shell executable.
        #[arg(long, default_value = "/bin/bash")]
        shell: String,
    },

    /// Print the backend NeoDash would probably use in this session.
    Backend,

    /// Print an example widget TOML config.
    ExampleWidget,
}

fn main() -> anyhow::Result<()> {
    tracing_subscriber::fmt().with_env_filter("warn").init();

    let cli = Cli::parse();

    match cli.command {
        Commands::Run {
            command,
            interval,
            shell,
        } => {
            let source = SourceConfig {
                command: Some(command),
                shell: Some(shell),
                interval_ms: interval,
                ..SourceConfig::default()
            };

            let output = run_shell_command_once(&source)?;
            print!("{}", output.stdout);

            if source.show_stderr && !output.stderr.is_empty() {
                eprint!("{}", output.stderr);
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
