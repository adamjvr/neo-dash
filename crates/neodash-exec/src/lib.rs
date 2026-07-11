// SPDX-License-Identifier: MPL-2.0

//! Command execution for NeoDash.
//!
//! This crate owns the dangerous part: running user commands. Keep the safety
//! rules here instead of scattering process-spawning all over the app.

use neodash_core::SourceConfig;
use std::process::{Command, Stdio};
use std::time::{Duration, Instant};

#[derive(Debug, Clone)]
pub struct CommandOutput {
    pub stdout: String,
    pub stderr: String,
    pub status_code: Option<i32>,
    pub elapsed: Duration,
    pub timed_out: bool,
}

/// Run a shell command once.
///
/// This v0 skeleton is intentionally simple. The next version should replace
/// this with a proper timeout-killing implementation, probably using async
/// process handling. Right now we measure elapsed time and report if the command
/// exceeded the configured timeout, but we do not kill it mid-flight.
pub fn run_shell_command_once(source: &SourceConfig) -> anyhow::Result<CommandOutput> {
    let command = source
        .command
        .as_deref()
        .ok_or_else(|| anyhow::anyhow!("shell widget is missing source.command"))?;

    let shell = source.shell.as_deref().unwrap_or("/bin/sh");
    let started = Instant::now();

    let output = Command::new(shell)
        .arg("-lc")
        .arg(command)
        .stdin(Stdio::null())
        .output()?;

    let elapsed = started.elapsed();
    let timeout = Duration::from_millis(source.timeout_ms);

    Ok(CommandOutput {
        stdout: String::from_utf8_lossy(&output.stdout).to_string(),
        stderr: String::from_utf8_lossy(&output.stderr).to_string(),
        status_code: output.status.code(),
        elapsed,
        timed_out: elapsed > timeout,
    })
}
