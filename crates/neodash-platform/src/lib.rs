// SPDX-License-Identifier: MPL-2.0

//! Platform backend abstraction.
//!
//! NeoDash must not pretend Linux desktop behavior is one thing. It is not.
//! We need clean backend seams for Wayland layer-shell, X11 fallback, and GNOME
//! Wayland weirdness.

use neodash_core::GeometryConfig;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum BackendKind {
    WaylandLayerShell,
    X11DesktopWindow,
    GnomeWaylandFallback,
    Unknown,
}

#[derive(Debug, Clone)]
pub struct BackendInfo {
    pub kind: BackendKind,
    pub reason: String,
}

/// Pick the best backend using environment detection.
///
/// This is deliberately conservative. Real layer-shell availability should be
/// probed inside the GUI crate when GTK/GDK is alive.
pub fn detect_backend_from_env() -> BackendInfo {
    let wayland = std::env::var_os("WAYLAND_DISPLAY").is_some();
    let x11 = std::env::var_os("DISPLAY").is_some();
    let desktop = std::env::var("XDG_CURRENT_DESKTOP")
        .unwrap_or_default()
        .to_lowercase();

    if wayland && desktop.contains("gnome") {
        return BackendInfo {
            kind: BackendKind::GnomeWaylandFallback,
            reason: "GNOME Wayland detected; layer-shell is not generally available there".into(),
        };
    }

    if wayland && desktop.contains("cosmic") {
        return BackendInfo {
            kind: BackendKind::WaylandLayerShell,
            reason: "COSMIC Wayland detected; try layer-shell backend first".into(),
        };
    }

    if wayland {
        return BackendInfo {
            kind: BackendKind::WaylandLayerShell,
            reason: "WAYLAND_DISPLAY is set; try layer-shell backend first".into(),
        };
    }

    if x11 {
        return BackendInfo {
            kind: BackendKind::X11DesktopWindow,
            reason: "DISPLAY is set and Wayland was not detected; use X11 fallback".into(),
        };
    }

    BackendInfo {
        kind: BackendKind::Unknown,
        reason: "No supported display environment detected".into(),
    }
}

pub trait DesktopSurface {
    fn apply_geometry(&self, geometry: &GeometryConfig) -> anyhow::Result<()>;
    fn set_click_through(&self, enabled: bool) -> anyhow::Result<()>;
    fn show(&self) -> anyhow::Result<()>;
    fn hide(&self) -> anyhow::Result<()>;
}
