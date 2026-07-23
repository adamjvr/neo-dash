from __future__ import annotations

from pathlib import Path

ROOT = Path.cwd()


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def write(path: str, text: str) -> None:
    full = ROOT / path
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(text, encoding="utf-8")


def insert_once(text: str, marker: str, addition: str, label: str) -> str:
    if addition.strip() in text:
        return text
    if marker not in text:
        raise SystemExit(f"Could not find expected marker while patching {label}: {marker!r}")
    return text.replace(marker, addition + marker, 1)


def patch_workspace() -> None:
    path = "Cargo.toml"
    text = read(path)
    member = '    "crates/neodash-cosmic",\n'
    if '"crates/neodash-cosmic"' not in text:
        marker = '    "crates/neodash-app",\n'
        if marker not in text:
            raise SystemExit("Could not find neodash-app workspace member in Cargo.toml")
        text = text.replace(marker, marker + member, 1)
    write(path, text)


def patch_platform() -> None:
    write(
        "crates/neodash-platform/src/lib.rs",
        r'''// SPDX-License-Identifier: MPL-2.0

//! Platform and frontend detection for NeoDash.
//!
//! NeoDash supports two independently-developed native frontend families:
//!
//! - GTK4 for Pop!_OS 22.04, GNOME, generic Wayland, and X11 desktops.
//! - libcosmic for COSMIC as a first-class desktop target.
//!
//! The frontend toolkit and compositor integration backend are intentionally
//! separate concepts. A libcosmic application can be exercised through its
//! winit/X11 path while developing outside a COSMIC session, while the true
//! COSMIC desktop-surface behavior still requires COSMIC Wayland testing.

use neodash_core::GeometryConfig;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum FrontendKind {
    Gtk,
    Cosmic,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum DisplayProtocol {
    Wayland,
    X11,
    Headless,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum DesktopFamily {
    Cosmic,
    Gnome,
    Other,
    Unknown,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum BackendKind {
    /// Native libcosmic frontend running against a COSMIC Wayland session.
    CosmicNative,
    /// GTK4 surface using the layer-shell protocol where supported.
    WaylandLayerShell,
    /// GTK4/X11 desktop-style window with EWMH hints.
    X11DesktopWindow,
    /// GNOME Wayland cannot generally provide layer-shell desktop surfaces.
    GnomeWaylandFallback,
    Unknown,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct SurfaceCapabilities {
    pub exact_positioning: bool,
    pub desktop_layer: bool,
    pub below_windows: bool,
    pub sticky_workspaces: bool,
    pub click_through: bool,
    pub transparent_surface: bool,
    pub native_theme: bool,
}

impl BackendKind {
    pub const fn capabilities(self) -> SurfaceCapabilities {
        match self {
            Self::CosmicNative => SurfaceCapabilities {
                exact_positioning: true,
                desktop_layer: true,
                below_windows: true,
                sticky_workspaces: true,
                click_through: true,
                transparent_surface: true,
                native_theme: true,
            },
            Self::WaylandLayerShell => SurfaceCapabilities {
                exact_positioning: true,
                desktop_layer: true,
                below_windows: true,
                sticky_workspaces: true,
                click_through: true,
                transparent_surface: true,
                native_theme: false,
            },
            Self::X11DesktopWindow => SurfaceCapabilities {
                exact_positioning: true,
                desktop_layer: false,
                below_windows: true,
                sticky_workspaces: true,
                click_through: true,
                transparent_surface: true,
                native_theme: false,
            },
            Self::GnomeWaylandFallback => SurfaceCapabilities {
                exact_positioning: false,
                desktop_layer: false,
                below_windows: false,
                sticky_workspaces: false,
                click_through: false,
                transparent_surface: true,
                native_theme: false,
            },
            Self::Unknown => SurfaceCapabilities {
                exact_positioning: false,
                desktop_layer: false,
                below_windows: false,
                sticky_workspaces: false,
                click_through: false,
                transparent_surface: false,
                native_theme: false,
            },
        }
    }
}

#[derive(Debug, Clone)]
pub struct BackendInfo {
    pub kind: BackendKind,
    pub recommended_frontend: FrontendKind,
    pub desktop_family: DesktopFamily,
    pub display_protocol: DisplayProtocol,
    pub reason: String,
}

/// Pick the best frontend/backend pair using process environment detection.
pub fn detect_backend_from_env() -> BackendInfo {
    detect_backend_with(|name| std::env::var(name).ok())
}

/// Environment-reader seam used by tests and future launch-policy code.
pub fn detect_backend_with<F>(get: F) -> BackendInfo
where
    F: Fn(&str) -> Option<String>,
{
    let wayland = get("WAYLAND_DISPLAY").is_some()
        || get("XDG_SESSION_TYPE")
            .is_some_and(|value| value.eq_ignore_ascii_case("wayland"));
    let x11 = get("DISPLAY").is_some()
        || get("XDG_SESSION_TYPE")
            .is_some_and(|value| value.eq_ignore_ascii_case("x11"));

    let desktop = [
        get("XDG_CURRENT_DESKTOP"),
        get("XDG_SESSION_DESKTOP"),
        get("DESKTOP_SESSION"),
    ]
    .into_iter()
    .flatten()
    .collect::<Vec<_>>()
    .join(":")
    .to_lowercase();

    let desktop_family = if desktop.contains("cosmic") {
        DesktopFamily::Cosmic
    } else if desktop.contains("gnome") || desktop.contains("pop") {
        DesktopFamily::Gnome
    } else if desktop.is_empty() {
        DesktopFamily::Unknown
    } else {
        DesktopFamily::Other
    };

    if wayland && desktop_family == DesktopFamily::Cosmic {
        return BackendInfo {
            kind: BackendKind::CosmicNative,
            recommended_frontend: FrontendKind::Cosmic,
            desktop_family,
            display_protocol: DisplayProtocol::Wayland,
            reason: "COSMIC Wayland detected; use the native libcosmic host".into(),
        };
    }

    if wayland && desktop_family == DesktopFamily::Gnome {
        return BackendInfo {
            kind: BackendKind::GnomeWaylandFallback,
            recommended_frontend: FrontendKind::Gtk,
            desktop_family,
            display_protocol: DisplayProtocol::Wayland,
            reason: "GNOME Wayland detected; use the GTK degraded backend until the shell bridge exists"
                .into(),
        };
    }

    if wayland {
        return BackendInfo {
            kind: BackendKind::WaylandLayerShell,
            recommended_frontend: FrontendKind::Gtk,
            desktop_family,
            display_protocol: DisplayProtocol::Wayland,
            reason: "Wayland detected outside COSMIC/GNOME; try the GTK layer-shell backend".into(),
        };
    }

    if x11 {
        return BackendInfo {
            kind: BackendKind::X11DesktopWindow,
            recommended_frontend: FrontendKind::Gtk,
            desktop_family,
            display_protocol: DisplayProtocol::X11,
            reason: "X11 detected; use the GTK/X11 desktop-window backend".into(),
        };
    }

    BackendInfo {
        kind: BackendKind::Unknown,
        recommended_frontend: FrontendKind::Gtk,
        desktop_family,
        display_protocol: DisplayProtocol::Headless,
        reason: "No supported display environment detected".into(),
    }
}

pub trait DesktopSurface {
    fn apply_geometry(&self, geometry: &GeometryConfig) -> anyhow::Result<()>;
    fn set_click_through(&self, enabled: bool) -> anyhow::Result<()>;
    fn show(&self) -> anyhow::Result<()>;
    fn hide(&self) -> anyhow::Result<()>;
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::collections::HashMap;

    fn detect(values: &[(&str, &str)]) -> BackendInfo {
        let values = values
            .iter()
            .map(|(key, value)| ((*key).to_string(), (*value).to_string()))
            .collect::<HashMap<_, _>>();
        detect_backend_with(|name| values.get(name).cloned())
    }

    #[test]
    fn cosmic_wayland_selects_native_cosmic_frontend() {
        let info = detect(&[
            ("WAYLAND_DISPLAY", "wayland-1"),
            ("XDG_CURRENT_DESKTOP", "COSMIC"),
        ]);
        assert_eq!(info.kind, BackendKind::CosmicNative);
        assert_eq!(info.recommended_frontend, FrontendKind::Cosmic);
        assert_eq!(info.display_protocol, DisplayProtocol::Wayland);
    }

    #[test]
    fn gnome_wayland_selects_gtk_fallback() {
        let info = detect(&[
            ("WAYLAND_DISPLAY", "wayland-0"),
            ("XDG_CURRENT_DESKTOP", "pop:GNOME"),
        ]);
        assert_eq!(info.kind, BackendKind::GnomeWaylandFallback);
        assert_eq!(info.recommended_frontend, FrontendKind::Gtk);
    }

    #[test]
    fn generic_wayland_selects_layer_shell() {
        let info = detect(&[
            ("WAYLAND_DISPLAY", "wayland-0"),
            ("XDG_CURRENT_DESKTOP", "sway"),
        ]);
        assert_eq!(info.kind, BackendKind::WaylandLayerShell);
    }

    #[test]
    fn x11_selects_x11_desktop_window() {
        let info = detect(&[
            ("DISPLAY", ":0"),
            ("XDG_CURRENT_DESKTOP", "GNOME"),
        ]);
        assert_eq!(info.kind, BackendKind::X11DesktopWindow);
        assert_eq!(info.display_protocol, DisplayProtocol::X11);
    }

    #[test]
    fn missing_display_is_headless() {
        let info = detect(&[]);
        assert_eq!(info.kind, BackendKind::Unknown);
        assert_eq!(info.display_protocol, DisplayProtocol::Headless);
    }
}
''',
    )


def create_cosmic_crate() -> None:
    write(
        "crates/neodash-cosmic/Cargo.toml",
        r'''[package]
name = "neodash-cosmic"
version = "0.0.1"
edition = "2024"
rust-version = "1.93"
license.workspace = true
authors.workspace = true
repository.workspace = true

[[bin]]
name = "neodash-cosmic"
path = "src/main.rs"

[features]
default = []
# Development mode: run the libcosmic frontend through winit/X11 on the
# currently-installed non-COSMIC desktop.
cosmic-winit = ["dep:cosmic", "cosmic/winit", "cosmic/x11", "cosmic/tokio"]
# Native target mode: compile the frontend with COSMIC/Wayland support.
cosmic-wayland = ["dep:cosmic", "cosmic/wayland", "cosmic/tokio"]

[dependencies]
anyhow.workspace = true
neodash-platform = { path = "../neodash-platform" }
cosmic = { package = "libcosmic", git = "https://github.com/pop-os/libcosmic.git", optional = true, default-features = false }
''',
    )

    write(
        "crates/neodash-cosmic/src/main.rs",
        r'''// SPDX-License-Identifier: MPL-2.0

#[cfg(all(feature = "cosmic-winit", feature = "cosmic-wayland"))]
compile_error!("enable exactly one of cosmic-winit or cosmic-wayland");

#[cfg(not(any(feature = "cosmic-winit", feature = "cosmic-wayland")))]
fn main() -> anyhow::Result<()> {
    let backend = neodash_platform::detect_backend_from_env();

    println!("NeoDash native COSMIC host scaffold");
    println!(
        "detected: {:?} / {:?} / {:?}",
        backend.desktop_family, backend.display_protocol, backend.kind
    );
    println!("reason: {}", backend.reason);
    println!();
    println!("This binary was built without libcosmic support.");
    println!();
    println!("Run the frontend on the current X11/non-COSMIC desktop:");
    println!("  cargo run -p neodash-cosmic --features cosmic-winit");
    println!();
    println!("Compile the native COSMIC Wayland target:");
    println!("  cargo check -p neodash-cosmic --features cosmic-wayland");

    Ok(())
}

#[cfg(any(feature = "cosmic-winit", feature = "cosmic-wayland"))]
fn main() -> cosmic::iced::Result {
    cosmic_host::run()
}

#[cfg(any(feature = "cosmic-winit", feature = "cosmic-wayland"))]
mod cosmic_host {
    use cosmic::iced::Length;
    use cosmic::prelude::*;
    use cosmic::widget;
    use neodash_platform::{BackendInfo, detect_backend_from_env};

    pub fn run() -> cosmic::iced::Result {
        cosmic::app::run::<NeoDashCosmicApp>(cosmic::app::Settings::default(), ())
    }

    #[derive(Debug, Clone)]
    pub enum Message {
        Noop,
    }

    pub struct NeoDashCosmicApp {
        core: cosmic::Core,
        platform: BackendInfo,
    }

    impl cosmic::Application for NeoDashCosmicApp {
        type Executor = cosmic::executor::Default;
        type Flags = ();
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
            _flags: Self::Flags,
        ) -> (Self, Task<cosmic::Action<Self::Message>>) {
            (
                Self {
                    core,
                    platform: detect_backend_from_env(),
                },
                Task::none(),
            )
        }

        fn view(&self) -> Element<'_, Self::Message> {
            let spacing = cosmic::theme::spacing().space_m;
            let content = widget::column::with_capacity(5)
                .push(widget::text::title1("NeoDash"))
                .push(widget::text::title3("Native COSMIC frontend scaffold"))
                .push(widget::text::body(format!(
                    "Desktop: {:?}",
                    self.platform.desktop_family
                )))
                .push(widget::text::body(format!(
                    "Display: {:?}",
                    self.platform.display_protocol
                )))
                .push(widget::text::body(format!(
                    "Integration backend: {:?}",
                    self.platform.kind
                )))
                .spacing(spacing);

            widget::container(content)
                .padding(spacing)
                .width(Length::Fill)
                .height(Length::Fill)
                .into()
        }

        fn update(&mut self, _message: Self::Message) -> Task<cosmic::Action<Self::Message>> {
            Task::none()
        }
    }
}
''',
    )


def create_check_script() -> None:
    write(
        "scripts/check_frontends.sh",
        r'''#!/usr/bin/env bash
set -euo pipefail

# Checks both NeoDash frontend families without requiring the current login
# session to be COSMIC.

cargo check -p neodash-app --features gui
cargo check -p neodash-app --features gui,x11-desktop
cargo check -p neodash-cosmic
cargo check -p neodash-cosmic --features cosmic-winit
cargo check -p neodash-cosmic --features cosmic-wayland
''',
    )
    (ROOT / "scripts/check_frontends.sh").chmod(0o755)


def patch_ci() -> None:
    path = ".github/workflows/ci.yml"
    if not (ROOT / path).exists():
        return

    text = read(path)
    if "name: COSMIC frontend checks" in text:
        return

    text += r'''

  cosmic-frontends:
    name: COSMIC frontend checks
    runs-on: ubuntu-24.04
    steps:
      - uses: actions/checkout@v4
      - uses: dtolnay/rust-toolchain@stable
      - name: Install libcosmic build dependencies
        run: |
          sudo apt-get update
          sudo apt-get install -y \
            cmake \
            libexpat1-dev \
            libfontconfig-dev \
            libfreetype-dev \
            libwayland-dev \
            libxkbcommon-dev \
            pkg-config
      - name: Check libcosmic winit development host
        run: cargo check -p neodash-cosmic --features cosmic-winit
      - name: Check native COSMIC Wayland host
        run: cargo check -p neodash-cosmic --features cosmic-wayland
'''
    write(path, text)


def patch_docs() -> None:
    write(
        "docs/DUAL_FRONTEND_DEVELOPMENT.md",
        r'''# Dual frontend development

NeoDash deliberately maintains two native Linux frontend families.

```text
shared NeoDash engine
  neodash-core
  neodash-runtime
  neodash-daemon
  neodash-renderer
  neodash-platform
        |
        +-- GTK4 host
        |     Pop!_OS 22.04
        |     GNOME X11
        |     GNOME Wayland degraded mode
        |     generic layer-shell Wayland
        |
        +-- libcosmic host
              COSMIC on Pop!_OS 24.04 and later
```

COSMIC is not classified as generic Wayland. A COSMIC Wayland session selects
`BackendKind::CosmicNative` and recommends `FrontendKind::Cosmic`.

## Developing while logged into a non-COSMIC desktop

The two libcosmic build modes let both frontends advance from the current
machine:

```bash
# Existing GTK frontend: run and visually test it now.
cargo run -p neodash-app --features gui,x11-desktop -- \
  --profile default \
  --layout-mode \
  --debug-frame

# Native libcosmic UI rendered through winit/X11 for local visual iteration.
cargo run -p neodash-cosmic --features cosmic-winit

# True COSMIC/Wayland build: compile on every phase even outside COSMIC.
cargo check -p neodash-cosmic --features cosmic-wayland
```

Run the complete frontend gate with:

```bash
./scripts/check_frontends.sh
```

## What can be verified outside COSMIC

- shared profile and runtime behavior
- COSMIC application model and message flow
- libcosmic widgets, typography, spacing, and general editor layout
- compilation of the native Wayland target
- GTK/X11 desktop-window behavior
- backend-selection tests

## What still requires a COSMIC login

- compositor-specific desktop/layer placement
- exact multi-monitor anchoring under `cosmic-comp`
- click-through and input-region behavior
- workspace/sticky behavior
- native COSMIC theme/config integration in the actual session
- launch-at-login and session lifecycle integration

Those compositor checks are validation gates, not blockers for ordinary feature
development.

## Development rule

New user-facing functionality should be divided into:

1. toolkit-neutral state and behavior in shared crates;
2. a GTK presentation adapter;
3. a libcosmic presentation adapter;
4. compositor integration behind `neodash-platform` capabilities.

Do not duplicate scheduling, profile parsing, command execution, or persistence in
either frontend.
''',
    )

    readme_path = ROOT / "README.md"
    if readme_path.exists():
        text = readme_path.read_text(encoding="utf-8")
        heading = "## Dual GTK and native COSMIC frontends\n"
        if heading not in text:
            section = r'''
## Dual GTK and native COSMIC frontends

NeoDash supports two first-class native frontend families rather than treating
COSMIC as generic Wayland:

- GTK4 for Pop!_OS 22.04, GNOME, X11, and generic layer-shell desktops.
- libcosmic for COSMIC on Pop!_OS 24.04 and later.

The libcosmic frontend has a `cosmic-winit` development build that can run on a
non-COSMIC X11 desktop and a `cosmic-wayland` build that is compiled continuously
for the real COSMIC target. See `docs/DUAL_FRONTEND_DEVELOPMENT.md`.

'''
            marker = "## License\n"
            if marker in text:
                text = text.replace(marker, section + marker, 1)
            else:
                text += "\n" + section
            readme_path.write_text(text, encoding="utf-8")

    architecture_path = ROOT / "docs/ARCHITECTURE.md"
    if architecture_path.exists():
        text = architecture_path.read_text(encoding="utf-8")
        if "## Frontend split" not in text:
            text += r'''

## Frontend split

`neodash-app` is the GTK compatibility and generic-Linux host.
`neodash-cosmic` is the native libcosmic host.

Both are presentation shells around the same core/runtime/daemon state. COSMIC
Wayland selects `CosmicNative`; it is not routed through the generic layer-shell
classification. The libcosmic host may also run through `cosmic-winit` during
development on a non-COSMIC desktop, but that mode does not claim to validate
COSMIC compositor integration.
'''
            architecture_path.write_text(text, encoding="utf-8")


def main() -> None:
    patch_workspace()
    patch_platform()
    create_cosmic_crate()
    create_check_script()
    patch_ci()
    patch_docs()
    print("Dual GTK/libcosmic frontend scaffold applied.")


if __name__ == "__main__":
    main()
