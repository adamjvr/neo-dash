// SPDX-License-Identifier: MPL-2.0

//! User config directory discovery and selector resolution.
//!
//! NeoDash started with repository-local example files. This module begins the
//! move toward a normal installed application layout under the user's XDG config
//! directory while keeping path behavior deterministic and testable.

use std::{
    env,
    path::{Path, PathBuf},
};

/// Resolved NeoDash user config directories.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct NeoDashConfigPaths {
    /// Root config directory, normally `~/.config/neodash`.
    pub config_dir: PathBuf,

    /// Profile TOML directory, normally `~/.config/neodash/profiles`.
    pub profiles_dir: PathBuf,

    /// Widget TOML directory, normally `~/.config/neodash/widgets`.
    pub widgets_dir: PathBuf,

    /// Theme TOML directory, normally `~/.config/neodash/themes`.
    pub themes_dir: PathBuf,
}

/// Resolve the NeoDash user config root.
///
/// Resolution order:
///
/// 1. `NEODASH_CONFIG_DIR` if set and non-empty.
/// 2. `$XDG_CONFIG_HOME/neodash` if `XDG_CONFIG_HOME` is set and non-empty.
/// 3. `$HOME/.config/neodash`.
pub fn neodash_config_dir() -> anyhow::Result<PathBuf> {
    if let Some(path) = non_empty_env_path("NEODASH_CONFIG_DIR") {
        return Ok(path);
    }

    if let Some(xdg_config_home) = non_empty_env_path("XDG_CONFIG_HOME") {
        return Ok(xdg_config_home.join("neodash"));
    }

    let home = non_empty_env_path("HOME")
        .ok_or_else(|| anyhow::anyhow!("HOME is not set; cannot resolve NeoDash config dir"))?;

    Ok(home.join(".config").join("neodash"))
}

/// Resolve the standard NeoDash user config directories.
pub fn neodash_config_paths() -> anyhow::Result<NeoDashConfigPaths> {
    let config_dir = neodash_config_dir()?;

    Ok(config_paths_from_root(config_dir))
}

/// Build the config path set from an already-resolved root.
///
/// This is useful for tests and for callers that intentionally use a custom
/// config root.
pub fn config_paths_from_root(config_dir: PathBuf) -> NeoDashConfigPaths {
    NeoDashConfigPaths {
        profiles_dir: config_dir.join("profiles"),
        widgets_dir: config_dir.join("widgets"),
        themes_dir: config_dir.join("themes"),
        config_dir,
    }
}

/// Resolve a user-supplied profile selector.
///
/// If the selector looks like a path, it is returned as a path:
///
/// - absolute paths
/// - relative paths containing a directory component
/// - paths with a file extension, such as `default.toml`
///
/// If the selector is a bare name like `default`, it resolves to:
///
/// ```text
/// <config-dir>/profiles/default.toml
/// ```
pub fn resolve_profile_selector(selector: impl AsRef<Path>) -> anyhow::Result<PathBuf> {
    let paths = neodash_config_paths()?;
    resolve_profile_selector_with_config_dir(selector, &paths.config_dir)
}

/// Resolve a profile selector against an explicit config root.
pub fn resolve_profile_selector_with_config_dir(
    selector: impl AsRef<Path>,
    config_dir: impl AsRef<Path>,
) -> anyhow::Result<PathBuf> {
    let selector = selector.as_ref();

    anyhow::ensure!(
        !selector.as_os_str().is_empty(),
        "profile selector cannot be empty"
    );

    if selector.is_absolute() || selector.components().count() > 1 || selector.extension().is_some()
    {
        return Ok(selector.to_path_buf());
    }

    let name = selector
        .file_name()
        .and_then(|name| name.to_str())
        .ok_or_else(|| anyhow::anyhow!("profile selector is not valid UTF-8"))?;

    Ok(config_dir
        .as_ref()
        .join("profiles")
        .join(format!("{name}.toml")))
}

fn non_empty_env_path(name: &str) -> Option<PathBuf> {
    let value = env::var_os(name)?;

    if value.is_empty() {
        None
    } else {
        Some(PathBuf::from(value))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn bare_profile_name_resolves_into_config_profiles_dir() {
        let resolved = resolve_profile_selector_with_config_dir("default", "/tmp/neodash")
            .expect("selector should resolve");

        assert_eq!(
            resolved,
            PathBuf::from("/tmp/neodash/profiles/default.toml")
        );
    }

    #[test]
    fn explicit_relative_profile_path_stays_relative() {
        let resolved =
            resolve_profile_selector_with_config_dir("examples/profiles/default.toml", "/tmp/x")
                .expect("selector should resolve");

        assert_eq!(resolved, PathBuf::from("examples/profiles/default.toml"));
    }

    #[test]
    fn relative_toml_filename_stays_relative() {
        let resolved = resolve_profile_selector_with_config_dir("default.toml", "/tmp/x")
            .expect("selector should resolve");

        assert_eq!(resolved, PathBuf::from("default.toml"));
    }

    #[test]
    fn absolute_profile_path_stays_absolute() {
        let resolved = resolve_profile_selector_with_config_dir("/tmp/default.toml", "/tmp/x")
            .expect("selector should resolve");

        assert_eq!(resolved, PathBuf::from("/tmp/default.toml"));
    }
}
