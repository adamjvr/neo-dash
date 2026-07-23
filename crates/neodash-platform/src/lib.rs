// SPDX-License-Identifier: MPL-2.0

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
        || get("XDG_SESSION_TYPE").is_some_and(|value| value.eq_ignore_ascii_case("wayland"));
    let x11 = get("DISPLAY").is_some()
        || get("XDG_SESSION_TYPE").is_some_and(|value| value.eq_ignore_ascii_case("x11"));

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
            reason:
                "GNOME Wayland detected; use the GTK degraded backend until the shell bridge exists"
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
        let info = detect(&[("DISPLAY", ":0"), ("XDG_CURRENT_DESKTOP", "GNOME")]);
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
