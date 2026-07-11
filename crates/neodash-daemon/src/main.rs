// SPDX-License-Identifier: MPL-2.0

use neodash_platform::detect_backend_from_env;

fn main() -> anyhow::Result<()> {
    tracing_subscriber::fmt().with_env_filter("info").init();

    let backend = detect_backend_from_env();
    tracing::info!(?backend, "NeoDash daemon starting");

    println!("neodashd skeleton is alive");
    println!("backend guess: {:?} - {}", backend.kind, backend.reason);
    println!("next step: load enabled widgets and spawn desktop surfaces");

    Ok(())
}
