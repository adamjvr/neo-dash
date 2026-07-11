// SPDX-License-Identifier: MPL-2.0

use neodash_platform::detect_backend_from_env;

fn main() -> anyhow::Result<()> {
    tracing_subscriber::fmt().with_env_filter("info").init();

    let backend = detect_backend_from_env();

    println!("NeoDash GTK app skeleton");
    println!("backend guess: {:?} - {}", backend.kind, backend.reason);
    println!();
    println!("Next implementation step:");
    println!("  1. create gtk::Application");
    println!("  2. create undecorated ApplicationWindow");
    println!("  3. if Wayland layer-shell is available, init layer shell for the window");
    println!("  4. render one Label using command output");

    Ok(())
}

/*
Rough GTK4/layer-shell sketch for the next commit. This is left commented until
we wire exact API calls and compile on a machine with Rust + GTK dev packages.

use gtk::prelude::*;
use gtk4_layer_shell as layer_shell;

fn build_window(app: &gtk::Application) {
    let window = gtk::ApplicationWindow::builder()
        .application(app)
        .title("NeoDash Widget")
        .decorated(false)
        .default_width(420)
        .default_height(80)
        .build();

    layer_shell::init_for_window(&window);
    layer_shell::set_layer(&window, layer_shell::Layer::Background);
    layer_shell::set_anchor(&window, layer_shell::Edge::Top, true);
    layer_shell::set_anchor(&window, layer_shell::Edge::Left, true);
    layer_shell::set_margin(&window, layer_shell::Edge::Top, 40);
    layer_shell::set_margin(&window, layer_shell::Edge::Left, 40);

    let label = gtk::Label::new(Some("NeoDash"));
    window.set_child(Some(&label));
    window.present();
}
*/
