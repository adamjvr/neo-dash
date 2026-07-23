// SPDX-License-Identifier: MPL-2.0

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
        println!(
            "run: cargo run -p neodash-daemon -- --widget examples/widgets/date.toml --frames 3"
        );
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
