from pathlib import Path

ROOT = Path.cwd()


def read(path: str) -> str:
    return (ROOT / path).read_text()


def write(path: str, text: str) -> None:
    full = ROOT / path
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(text)


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise SystemExit(f"Could not find expected block while patching {label}:\n{old[:1000]}")
    return text.replace(old, new, 1)


def ensure_contains(path: str, needle: str, append_text: str) -> None:
    full = ROOT / path
    if not full.exists():
        write(path, append_text)
        return
    text = full.read_text()
    if needle not in text:
        full.write_text(text.rstrip() + "\n\n" + append_text.lstrip())


def patch_core() -> None:
    write(
        "crates/neodash-core/src/profile.rs",
        '''// SPDX-License-Identifier: MPL-2.0

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

        assert_eq!(resolved, PathBuf::from("examples/profiles/../widgets/date.toml"));
    }

    #[test]
    fn keeps_absolute_profile_paths_unchanged() {
        let base = Path::new("examples/profiles");
        let absolute = Path::new("/tmp/neodash/widget.toml");

        assert_eq!(resolve_profile_path(base, absolute), absolute);
    }
}
''',
    )

    lib = read("crates/neodash-core/src/lib.rs")
    if "pub mod profile;" not in lib:
        lib = lib.replace("pub mod model;\n", "pub mod model;\npub mod profile;\n", 1)
    if "pub use profile::*;" not in lib:
        lib = lib.replace("pub use model::*;\n", "pub use model::*;\npub use profile::*;\n", 1)
    write("crates/neodash-core/src/lib.rs", lib)


def patch_app_cargo() -> None:
    path = "crates/neodash-app/Cargo.toml"
    text = read(path)
    text = text.replace("serde.workspace = true\n", "")
    text = text.replace("toml.workspace = true\n", "")
    write(path, text)


def patch_app_main() -> None:
    path = "crates/neodash-app/src/main.rs"
    text = read(path)

    text = text.replace("    use serde::Deserialize;\n", "")

    text = text.replace(
        "    use neodash_core::{GeometryConfig, WidgetConfig, WidgetType};\n",
        "    use neodash_core::{\n        collect_profile_widget_paths, discover_widget_paths, load_profile_from_path,\n        GeometryConfig, LoadedProfile, WidgetConfig, WidgetType,\n    };\n",
        1,
    )

    text = text.replace(
        "    use std::{\n        cell::RefCell,\n        fs,\n        path::{Path, PathBuf},\n        rc::Rc,\n        time::Duration,\n    };\n",
        "    use std::{cell::RefCell, path::PathBuf, rc::Rc, time::Duration};\n",
        1,
    )

    text = text.replace("Some(profile_path) => Some(load_profile(profile_path)?),", "Some(profile_path) => Some(load_profile_from_path(profile_path)?),", 1)

    local_profile_block = '''    #[derive(Debug, Deserialize)]
    struct ProfileConfig {
        id: Option<String>,
        name: Option<String>,
        #[serde(default)]
        widgets: Vec<PathBuf>,
        #[serde(default)]
        widget_dirs: Vec<PathBuf>,
        #[serde(default)]
        desktop_hints: Option<bool>,
    }

    #[derive(Debug)]
    struct LoadedProfile {
        base_dir: PathBuf,
        profile: ProfileConfig,
    }

    fn load_profile(path: &Path) -> anyhow::Result<LoadedProfile> {
        let profile_text = fs::read_to_string(path)
            .with_context(|| format!("failed to read profile {}", path.display()))?;
        let profile: ProfileConfig = toml::from_str(&profile_text)
            .with_context(|| format!("failed to parse profile {}", path.display()))?;
        let base_dir = path
            .parent()
            .unwrap_or_else(|| Path::new("."))
            .to_path_buf();

        tracing::info!(
            path = %path.display(),
            profile_id = profile.id.as_deref().unwrap_or("<unnamed>"),
            profile_name = profile.name.as_deref().unwrap_or("<unnamed>"),
            widget_count = profile.widgets.len(),
            widget_dir_count = profile.widget_dirs.len(),
            desktop_hints = profile.desktop_hints.unwrap_or(false),
            "loaded NeoDash profile"
        );

        Ok(LoadedProfile { base_dir, profile })
    }

    fn resolve_profile_path(base_dir: &Path, path: &Path) -> PathBuf {
        if path.is_absolute() {
            path.to_path_buf()
        } else {
            base_dir.join(path)
        }
    }

'''
    if local_profile_block in text:
        text = text.replace(local_profile_block, "", 1)
    else:
        print("warning: local profile block was not found; it may already be removed")

    old_collect = '''    /// Collect widget paths from an optional profile plus explicit CLI arguments.
    ///
    /// Loading order: profile widgets, profile widget_dirs, explicit --widget,
    /// then explicit --widgets-dir.
    fn collect_widget_paths(
        cli: &Cli,
        loaded_profile: Option<&LoadedProfile>,
    ) -> anyhow::Result<Vec<PathBuf>> {
        let mut paths = Vec::new();

        if let Some(loaded) = loaded_profile {
            for widget in &loaded.profile.widgets {
                paths.push(resolve_profile_path(&loaded.base_dir, widget));
            }
            for dir in &loaded.profile.widget_dirs {
                let dir = resolve_profile_path(&loaded.base_dir, dir);
                paths.extend(discover_widget_paths(&dir)?);
            }
        }

        paths.extend(cli.widgets.iter().cloned());
        for dir in &cli.widget_dirs {
            paths.extend(discover_widget_paths(dir)?);
        }

        anyhow::ensure!(
            !paths.is_empty(),
            "no widgets requested; pass --profile FILE, --widget FILE, or --widgets-dir DIR"
        );

        Ok(paths)
    }

    /// Discover direct-child TOML files in a widget directory.
    ///
    /// This intentionally does not recurse. Recursive loading should wait until
    /// NeoDash has a profile and widget-pack layout so nested folders have a
    /// defined meaning.
    fn discover_widget_paths(dir: &Path) -> anyhow::Result<Vec<PathBuf>> {
        let mut paths = Vec::new();

        for entry in fs::read_dir(dir)
            .with_context(|| format!("failed to read widget directory {}", dir.display()))?
        {
            let entry =
                entry.with_context(|| format!("failed to read entry in {}", dir.display()))?;
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
'''
    new_collect = '''    /// Collect widget paths from an optional profile plus explicit CLI arguments.
    ///
    /// Loading order: profile widgets, profile widget_dirs, explicit --widget,
    /// then explicit --widgets-dir.
    fn collect_widget_paths(
        cli: &Cli,
        loaded_profile: Option<&LoadedProfile>,
    ) -> anyhow::Result<Vec<PathBuf>> {
        let mut paths = Vec::new();

        if let Some(loaded) = loaded_profile {
            paths.extend(collect_profile_widget_paths(loaded)?);
        }

        paths.extend(cli.widgets.iter().cloned());
        for dir in &cli.widget_dirs {
            paths.extend(discover_widget_paths(dir)?);
        }

        anyhow::ensure!(
            !paths.is_empty(),
            "no widgets requested; pass --profile FILE, --widget FILE, or --widgets-dir DIR"
        );

        Ok(paths)
    }
'''
    text = replace_once(text, old_collect, new_collect, "app collect_widget_paths")

    if '"loaded NeoDash profile through shared profile model"' not in text:
        text = text.replace(
            '''        let loaded_profile = match cli.profile.as_ref() {
            Some(profile_path) => Some(load_profile_from_path(profile_path)?),
            None => None,
        };
''',
            '''        let loaded_profile = match cli.profile.as_ref() {
            Some(profile_path) => {
                let loaded = load_profile_from_path(profile_path)?;
                tracing::info!(
                    path = %loaded.path.display(),
                    profile_id = loaded.profile.id.as_deref().unwrap_or("<unnamed>"),
                    profile_name = loaded.profile.name.as_deref().unwrap_or("<unnamed>"),
                    widget_count = loaded.profile.widgets.len(),
                    widget_dir_count = loaded.profile.widget_dirs.len(),
                    desktop_hints = loaded.profile.desktop_hints.unwrap_or(false),
                    "loaded NeoDash profile through shared profile model"
                );
                Some(loaded)
            }
            None => None,
        };
''',
            1,
        )

    write(path, text)


def patch_cli() -> None:
    path = "crates/neodash-cli/src/main.rs"
    text = read(path)

    text = text.replace(
        "use neodash_core::{SourceConfig, WidgetConfig, WidgetId, WidgetType};",
        "use neodash_core::{\n    collect_profile_widget_paths, load_profile_from_path, SourceConfig, WidgetConfig, WidgetId,\n    WidgetType,\n};",
        1,
    )

    if "ProfileInfo" not in text:
        text = text.replace(
            '''    /// Print the backend NeoDash would probably use in this session.
    Backend,
''',
            '''    /// Inspect a NeoDash profile and print the resolved widget paths.
    ProfileInfo {
        /// Path to a profile TOML file, for example examples/profiles/default.toml.
        path: PathBuf,
    },

    /// Print the backend NeoDash would probably use in this session.
    Backend,
''',
            1,
        )

        text = text.replace(
            '''        Commands::Backend => {
            let backend = detect_backend_from_env();
            println!("{:?}: {}", backend.kind, backend.reason);
        }
''',
            '''        Commands::ProfileInfo { path } => {
            let loaded = load_profile_from_path(&path)?;
            let widget_paths = collect_profile_widget_paths(&loaded)?;

            println!("Profile file: {}", loaded.path.display());
            println!(
                "Profile id: {}",
                loaded.profile.id.as_deref().unwrap_or("<unnamed>")
            );
            println!(
                "Profile name: {}",
                loaded.profile.name.as_deref().unwrap_or("<unnamed>")
            );
            println!(
                "Desktop hints: {}",
                loaded
                    .profile
                    .desktop_hints
                    .map(|value| value.to_string())
                    .unwrap_or_else(|| "not set".to_string())
            );
            println!("Widget files: {}", widget_paths.len());

            for path in widget_paths {
                println!("  {}", path.display());
            }
        }
        Commands::Backend => {
            let backend = detect_backend_from_env();
            println!("{:?}: {}", backend.kind, backend.reason);
        }
''',
            1,
        )

    write(path, text)


def patch_docs() -> None:
    write(
        "docs/PROFILE_MODEL.md",
        '''# Shared profile model

NeoDash profile parsing now lives in `neodash-core`.

This matters because profiles are not only a GTK app feature. The CLI, daemon,
editor, and any future import/export tooling all need to agree on the same
profile format and path resolution rules.

## Current profile format

```toml
id = "default"
name = "Default NeoDash Example Dashboard"

widget_dirs = ["../widgets"]
widgets = []
desktop_hints = true
```

## Shared core API

The shared model currently exposes:

```text
ProfileConfig
LoadedProfile
load_profile_from_toml_str
load_profile_from_path
resolve_profile_path
collect_profile_widget_paths
discover_widget_paths
```

## Path resolution rule

Relative paths inside a profile are resolved relative to the profile file's
parent directory.

Example:

```text
examples/
  profiles/
    default.toml
  widgets/
    date.toml
    uptime.toml
```

Inside `examples/profiles/default.toml`, this points at `examples/widgets`:

```toml
widget_dirs = ["../widgets"]
```

The resolver intentionally does not canonicalize paths. This keeps editing
friendly because a profile can refer to files that do not exist yet.

## CLI inspection

Use this command to inspect a profile without opening GTK windows:

```bash
cargo run -p neodash-cli -- profile-info examples/profiles/default.toml
```

The command prints the profile id, name, desktop-hints setting, and resolved
widget files.

## Current limitations

- No duplicate widget ID validation yet.
- No profile inheritance yet.
- No theme/default loading yet.
- No per-widget override layer yet.
- No user config discovery yet.
- The daemon does not own profile state yet.

## Next step

The next phase should add a user config layout and a command that can resolve:

```text
~/.config/neodash/profiles/default.toml
```

from a simple profile name like:

```bash
neodash profile-info default
```
''',
    )

    ensure_contains(
        "docs/PROFILE_LOADING.md",
        "## Shared core model",
        '''## Shared core model

Profile parsing and path resolution now live in `neodash-core`. The GTK app uses
that shared model, and the CLI can inspect profiles with:

```bash
cargo run -p neodash-cli -- profile-info examples/profiles/default.toml
```

See `docs/PROFILE_MODEL.md` for the shared model details.
''',
    )

    ensure_contains(
        "README.md",
        "cargo run -p neodash-cli -- profile-info examples/profiles/default.toml",
        '''## Profile inspection

Profiles can be inspected without opening the GTK app:

```bash
cargo run -p neodash-cli -- profile-info examples/profiles/default.toml
```

Profile parsing and profile-relative path resolution are shared through
`neodash-core`; see `docs/PROFILE_MODEL.md` for details.
''',
    )

    ensure_contains(
        "docs/NEXT_STEPS.md",
        "## Current implementation target: user config discovery",
        '''## Current implementation target: user config discovery

Profile parsing is now shared through `neodash-core`. The next runtime milestone
is user config discovery.

Target layout:

```text
~/.config/neodash/
  profiles/
    default.toml
  widgets/
    date.toml
    uptime.toml
  themes/
    default.toml
```

Target commands:

```bash
neodash profile-info default
neodash-app --profile default
```

Implementation notes:

- Use the `directories` crate already present in workspace dependencies.
- Keep explicit file paths working.
- Add a resolver that treats bare names as profile IDs under the config dir.
- Add tests before moving more runtime ownership into the daemon.
''',
    )

    ensure_contains(
        "docs/ROADMAP.md",
        "- Shared profile model in `neodash-core`.",
        '''## Phase update: shared profile model

Status: complete.

Delivered:

- Shared profile model in `neodash-core`.
- Shared profile path resolution.
- Shared widget directory discovery.
- CLI profile inspection command.
- GTK app now uses the shared profile loader.
- Documentation for the profile model.

Next:

- User config directory discovery.
- Profile lookup by name.
- Duplicate widget ID validation.
- Daemon-owned profile state.
''',
    )


def main() -> None:
    patch_core()
    patch_app_cargo()
    patch_app_main()
    patch_cli()
    patch_docs()
    print("Applied shared profile model phase.")


if __name__ == "__main__":
    main()
