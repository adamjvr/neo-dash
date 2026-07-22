// SPDX-License-Identifier: MPL-2.0

//! Shared profile model and profile path resolution.
//!
//! Profiles describe which widget files make up a dashboard. Keep this model in
//! `neodash-core` so the CLI, daemon, GTK app, and future editor all agree on
//! the same profile format and relative-path behavior.

use serde::{Deserialize, Serialize};
use std::{
    fs,
    path::{Path, PathBuf},
};

/// A NeoDash dashboard profile.
///
/// This first shared profile model is intentionally small. It captures the
/// pieces the app already needs:
///
/// - explicit widget TOML files
/// - direct-child widget TOML directories
/// - optional default desktop-hints behavior
///
/// Themes, per-widget overrides, monitor rules, and profile inheritance should
/// be added after the basic runtime path is stable.
#[derive(Debug, Clone, Default, PartialEq, Eq, Serialize, Deserialize)]
pub struct ProfileConfig {
    /// Stable profile identifier, such as `default`.
    pub id: Option<String>,

    /// Human-readable profile name.
    pub name: Option<String>,

    /// Explicit widget TOML file paths.
    ///
    /// Relative paths are resolved relative to the profile file's parent
    /// directory by `collect_profile_widget_paths`.
    #[serde(default)]
    pub widgets: Vec<PathBuf>,

    /// Direct child directories containing widget TOML files.
    ///
    /// Directory loading is intentionally non-recursive for now. Recursive
    /// loading should wait until widget-pack layout rules are defined.
    #[serde(default)]
    pub widget_dirs: Vec<PathBuf>,

    /// Optional default desktop-hints behavior for graphical launches.
    ///
    /// The CLI or app may still override this. The profile only provides the
    /// user's preferred default for this dashboard.
    #[serde(default)]
    pub desktop_hints: Option<bool>,
}

/// A profile plus the filesystem context needed to resolve relative paths.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct LoadedProfile {
    /// Path to the profile TOML file that was loaded.
    pub path: PathBuf,

    /// Directory used as the base for relative paths inside the profile.
    pub base_dir: PathBuf,

    /// Parsed profile data.
    pub profile: ProfileConfig,
}

/// Parse a profile TOML string without filesystem context.
pub fn load_profile_from_toml_str(input: &str) -> anyhow::Result<ProfileConfig> {
    let profile: ProfileConfig = toml::from_str(input)?;
    Ok(profile)
}

/// Load a profile TOML file and remember its relative-path base directory.
pub fn load_profile_from_path(path: impl AsRef<Path>) -> anyhow::Result<LoadedProfile> {
    let path = path.as_ref();
    let text = fs::read_to_string(path)?;
    let profile = load_profile_from_toml_str(&text)?;
    let base_dir = path
        .parent()
        .unwrap_or_else(|| Path::new("."))
        .to_path_buf();

    Ok(LoadedProfile {
        path: path.to_path_buf(),
        base_dir,
        profile,
    })
}

/// Resolve a profile-relative path.
///
/// Absolute paths are returned unchanged. Relative paths are joined to the
/// profile file's parent directory. This function intentionally does not
/// canonicalize paths because users may point at files that do not exist yet
/// while editing a profile.
pub fn resolve_profile_path(base_dir: &Path, path: &Path) -> PathBuf {
    if path.is_absolute() {
        path.to_path_buf()
    } else {
        base_dir.join(path)
    }
}

/// Collect all widget TOML files referenced by a loaded profile.
///
/// Loading order:
///
/// 1. Explicit `widgets`, in profile order.
/// 2. Direct child TOML files from each `widget_dirs` entry, sorted per
///    directory for deterministic startup behavior.
pub fn collect_profile_widget_paths(profile: &LoadedProfile) -> anyhow::Result<Vec<PathBuf>> {
    let mut paths = Vec::new();

    for widget in &profile.profile.widgets {
        paths.push(resolve_profile_path(&profile.base_dir, widget));
    }

    for dir in &profile.profile.widget_dirs {
        let dir = resolve_profile_path(&profile.base_dir, dir);
        paths.extend(discover_widget_paths(&dir)?);
    }

    Ok(paths)
}

/// Discover direct-child TOML files in a widget directory.
///
/// This is shared so the app, CLI, and future daemon apply the same directory
/// loading rule.
pub fn discover_widget_paths(dir: &Path) -> anyhow::Result<Vec<PathBuf>> {
    let mut paths = Vec::new();

    for entry in fs::read_dir(dir)? {
        let entry = entry?;
        let path = entry.path();

        if !path.is_file() {
            continue;
        }

        let is_toml = path
            .extension()
            .and_then(|extension| extension.to_str())
            .is_some_and(|extension| extension.eq_ignore_ascii_case("toml"));

        if is_toml {
            paths.push(path);
        }
    }

    paths.sort();

    Ok(paths)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_profile_with_defaults() {
        let profile = load_profile_from_toml_str(
            r#"
id = "default"
name = "Default Dashboard"

widgets = ["../widgets/date.toml"]
widget_dirs = ["../widgets"]
desktop_hints = true
"#,
        )
        .expect("profile should parse");

        assert_eq!(profile.id.as_deref(), Some("default"));
        assert_eq!(profile.name.as_deref(), Some("Default Dashboard"));
        assert_eq!(profile.widgets, vec![PathBuf::from("../widgets/date.toml")]);
        assert_eq!(profile.widget_dirs, vec![PathBuf::from("../widgets")]);
        assert_eq!(profile.desktop_hints, Some(true));
    }

    #[test]
    fn profile_defaults_to_empty_widget_lists() {
        let profile = load_profile_from_toml_str(
            r#"
id = "empty"
"#,
        )
        .expect("profile should parse");

        assert_eq!(profile.id.as_deref(), Some("empty"));
        assert!(profile.widgets.is_empty());
        assert!(profile.widget_dirs.is_empty());
        assert_eq!(profile.desktop_hints, None);
    }

    #[test]
    fn resolves_relative_profile_paths_without_canonicalizing() {
        let base = Path::new("examples/profiles");
        let resolved = resolve_profile_path(base, Path::new("../widgets/date.toml"));

        assert_eq!(
            resolved,
            PathBuf::from("examples/profiles/../widgets/date.toml")
        );
    }

    #[test]
    fn keeps_absolute_profile_paths_unchanged() {
        let base = Path::new("examples/profiles");
        let absolute = Path::new("/tmp/neodash/widget.toml");

        assert_eq!(resolve_profile_path(base, absolute), absolute);
    }
}
