from pathlib import Path

ROOT = Path.cwd()


def read(path: str) -> str:
    return (ROOT / path).read_text()


def write(path: str, text: str) -> None:
    full = ROOT / path
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(text)


def insert_before_once(text: str, marker: str, addition: str, label: str) -> str:
    if addition.strip() in text:
        return text
    if marker not in text:
        raise SystemExit(f"Could not find marker while patching {label}:\n{marker[:500]}")
    return text.replace(marker, addition + marker, 1)


def patch_core_config_paths() -> None:
    write(
        "crates/neodash-core/src/config_paths.rs",
'''// SPDX-License-Identifier: MPL-2.0

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

        assert_eq!(resolved, PathBuf::from("/tmp/neodash/profiles/default.toml"));
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
''')

    lib_path = "crates/neodash-core/src/lib.rs"
    text = read(lib_path)

    if "pub mod config_paths;" not in text:
        text = text.replace("pub mod config;\n", "pub mod config;\npub mod config_paths;\n", 1)

    if "pub use config_paths::*;" not in text:
        text = text.replace(
            "pub use config::{load_widget_from_toml_str, save_widget_to_toml_string};\n",
            "pub use config::{load_widget_from_toml_str, save_widget_to_toml_string};\npub use config_paths::*;\n",
            1,
        )

    write(lib_path, text)


def patch_cli() -> None:
    path = "crates/neodash-cli/src/main.rs"
    text = read(path)

    if "ConfigInit" in text and "init_user_config" in text:
        print("CLI config-directory support already appears to be applied.")
        return

    if "use neodash_core::{" in text:
        if "neodash_config_paths" not in text:
            text = text.replace(
                "use neodash_core::{\n",
                "use neodash_core::{\n    neodash_config_paths, resolve_profile_selector,\n",
                1,
            )
    else:
        raise SystemExit("Could not find neodash_core import block in CLI main.rs")

    text = text.replace(
        "use std::path::PathBuf;",
        "use std::{\n    fs,\n    path::{Path, PathBuf},\n};",
        1,
    )

    if "    ConfigDir," not in text:
        marker = '''    /// Print the backend NeoDash would probably use in this session.
    Backend,
'''
        addition = '''    /// Print the resolved NeoDash user config directories.
    ConfigDir,

    /// Install the example dashboard into the NeoDash user config directory.
    ConfigInit {
        /// Overwrite existing profile and widget files.
        #[arg(long, default_value_t = false)]
        force: bool,
    },

'''
        text = insert_before_once(text, marker, addition, "CLI config subcommands")

    text = text.replace(
        "let loaded = load_profile_from_path(&path)?;",
        "let profile_path = resolve_profile_selector(&path)?;\n            let loaded = load_profile_from_path(&profile_path)?;",
    )
    text = text.replace(
        "let loaded = load_profile_from_path(path)?;",
        "let profile_path = resolve_profile_selector(&path)?;\n            let loaded = load_profile_from_path(&profile_path)?;",
    )

    if "Commands::ConfigDir" not in text:
        marker = '''        Commands::Backend => {
            let backend = detect_backend_from_env();
            println!("{:?}: {}", backend.kind, backend.reason);
        }
'''
        addition = '''        Commands::ConfigDir => {
            let paths = neodash_config_paths()?;

            println!("Config dir: {}", paths.config_dir.display());
            println!("Profiles dir: {}", paths.profiles_dir.display());
            println!("Widgets dir: {}", paths.widgets_dir.display());
            println!("Themes dir: {}", paths.themes_dir.display());
        }
        Commands::ConfigInit { force } => {
            init_user_config(force)?;
        }
'''
        text = insert_before_once(text, marker, addition, "CLI config match arms")

    helper_code = r'''
const DEFAULT_PROFILE_TOML: &str = r#"
id = "default"
name = "Default NeoDash Dashboard"

widget_dirs = ["../widgets"]
desktop_hints = true
"#;

const DEFAULT_DATE_WIDGET_TOML: &str = r#"
id = "date-clock"
name = "Date Clock"
type = "shell"
enabled = true

[source]
command = "date '+%Y-%m-%d %H:%M:%S'"
shell = "/bin/bash"
interval_ms = 1000
timeout_ms = 800
show_stderr = false
parse_ansi = true

[geometry]
monitor = "primary"
x = 40
y = 40
width = 400
height = 120
anchor = "top-left"
layer = "background"
click_through = true

[style]
font_family = "monospace"
font_size = 18
foreground = "#eeeeee"
background = "#00000088"
opacity = 1.0
padding = 8
border_radius = 0
"#;

const DEFAULT_UPTIME_WIDGET_TOML: &str = r#"
id = "uptime-status"
name = "Uptime Status"
type = "shell"
enabled = true

[source]
command = "uptime"
shell = "/bin/bash"
interval_ms = 5000
timeout_ms = 1200
show_stderr = false
parse_ansi = true

[geometry]
monitor = "primary"
x = 40
y = 190
width = 620
height = 100
anchor = "top-left"
layer = "background"
click_through = true

[style]
font_family = "monospace"
font_size = 13
foreground = "#eeeeee"
background = "#00000088"
opacity = 1.0
padding = 8
border_radius = 0
"#;

/// Install a starter NeoDash dashboard into the user's config directory.
fn init_user_config(force: bool) -> anyhow::Result<()> {
    let paths = neodash_config_paths()?;

    fs::create_dir_all(&paths.profiles_dir)?;
    fs::create_dir_all(&paths.widgets_dir)?;
    fs::create_dir_all(&paths.themes_dir)?;

    write_config_file(
        &paths.profiles_dir.join("default.toml"),
        DEFAULT_PROFILE_TOML.trim_start(),
        force,
    )?;
    write_config_file(
        &paths.widgets_dir.join("date.toml"),
        DEFAULT_DATE_WIDGET_TOML.trim_start(),
        force,
    )?;
    write_config_file(
        &paths.widgets_dir.join("uptime.toml"),
        DEFAULT_UPTIME_WIDGET_TOML.trim_start(),
        force,
    )?;

    println!("NeoDash config initialized:");
    println!("  {}", paths.config_dir.display());
    println!();
    println!("Try:");
    println!("  cargo run -p neodash-cli -- profile-info default");
    println!("  cargo run -p neodash-cli -- profile-check default");
    println!("  cargo run -p neodash-app --features gui,x11-desktop -- --profile default --debug-frame");

    Ok(())
}

fn write_config_file(path: &Path, contents: &str, force: bool) -> anyhow::Result<()> {
    if path.exists() && !force {
        println!("kept existing: {}", path.display());
        return Ok(());
    }

    fs::write(path, contents)?;
    println!("wrote: {}", path.display());

    Ok(())
}

'''
    text = insert_before_once(text, "fn main() -> anyhow::Result<()> {\n", helper_code, "CLI helper functions")

    write(path, text)


def patch_app() -> None:
    path = "crates/neodash-app/src/main.rs"
    text = read(path)

    if "resolve_profile_selector" not in text:
        text = text.replace(
            "collect_profile_widget_paths, discover_widget_paths, load_profile_from_path,",
            "collect_profile_widget_paths, discover_widget_paths, load_profile_from_path,\n        resolve_profile_selector,",
            1,
        )

    text = text.replace(
        '''                let loaded = load_profile_from_path(profile_path)?;''',
        '''                let resolved_profile_path = resolve_profile_selector(profile_path)?;
                let loaded = load_profile_from_path(&resolved_profile_path)?;''',
        1,
    )

    text = text.replace(
        '''let loaded = load_profile_from_path(profile_path)?;''',
        '''let resolved_profile_path = resolve_profile_selector(profile_path)?;
                let loaded = load_profile_from_path(&resolved_profile_path)?;''',
        1,
    )

    write(path, text)


def patch_docs() -> None:
    write(
        "docs/CONFIG_DIRECTORY.md",
'''# Config directory

NeoDash can now resolve and initialize a user config directory.

The default layout is:

```text
~/.config/neodash/
  profiles/
    default.toml
  widgets/
    date.toml
    uptime.toml
  themes/
```

The config root can be overridden with:

```bash
export NEODASH_CONFIG_DIR=/path/to/neodash-config
```

If `NEODASH_CONFIG_DIR` is not set, NeoDash follows XDG-style behavior:

1. `$XDG_CONFIG_HOME/neodash`
2. `$HOME/.config/neodash`

## Inspect config paths

```bash
cargo run -p neodash-cli -- config-dir
```

## Initialize starter config

```bash
cargo run -p neodash-cli -- config-init
```

Use `--force` to overwrite existing starter files:

```bash
cargo run -p neodash-cli -- config-init --force
```

## Profile selector behavior

A profile can still be passed as an explicit path:

```bash
cargo run -p neodash-app --features gui,x11-desktop -- \\
  --profile examples/profiles/default.toml
```

A bare profile name resolves through the user config directory:

```bash
cargo run -p neodash-app --features gui,x11-desktop -- \\
  --profile default \\
  --debug-frame
```

`default` resolves to:

```text
~/.config/neodash/profiles/default.toml
```

The same selector rule applies to CLI profile commands:

```bash
cargo run -p neodash-cli -- profile-info default
cargo run -p neodash-cli -- profile-check default
```

## What this phase intentionally does not do

This phase does not add the daemon yet. It only makes local app-style config
paths real and testable.

The next runtime step is for the daemon to own profile loading and widget
processes instead of the GTK preview app owning them directly.
''')

    readme = ROOT / "README.md"
    if readme.exists():
        text = readme.read_text()
        if "## User config directory" not in text:
            section = '''
## User config directory

NeoDash can initialize and use a local config directory:

```bash
cargo run -p neodash-cli -- config-dir
cargo run -p neodash-cli -- config-init --force
cargo run -p neodash-cli -- profile-info default
cargo run -p neodash-cli -- profile-check default
cargo run -p neodash-app --features gui,x11-desktop -- --profile default --debug-frame
```

A bare profile name such as `default` resolves to
`~/.config/neodash/profiles/default.toml`, unless `NEODASH_CONFIG_DIR` points at
another config root. See `docs/CONFIG_DIRECTORY.md`.

'''
            marker = "## Profile loading\n"
            if marker in text:
                text = text.replace(marker, section + marker, 1)
            else:
                text += "\n" + section
            readme.write_text(text)

    next_steps = ROOT / "docs/NEXT_STEPS.md"
    if next_steps.exists():
        text = next_steps.read_text()
        if "## Current implementation target: daemon-owned runtime" not in text:
            text += '''

## Current implementation target: daemon-owned runtime

Config directory support is now the bridge between repo examples and a real
installed app workflow. The next major phase should move profile ownership into
`neodash-daemon`.

Current app-style flow:

```bash
cargo run -p neodash-cli -- config-init --force
cargo run -p neodash-cli -- profile-check default
cargo run -p neodash-app --features gui,x11-desktop -- --profile default --debug-frame
```

Next daemon targets:

- Define daemon command interface.
- Add `neodash daemon start`.
- Add `neodash daemon status`.
- Make the daemon load a profile by name.
- Make the daemon own refresh scheduling.
- Keep GTK as a viewer/editor instead of the sole runtime owner.
'''
            next_steps.write_text(text)

    roadmap = ROOT / "docs/ROADMAP.md"
    if roadmap.exists():
        text = roadmap.read_text()
        text = text.replace(
            "## Phase 5: profile and config directory runtime\n\nStatus: started.",
            "## Phase 5: profile and config directory runtime\n\nStatus: in progress.",
        )
        if "Config directory initialization via `config-init`." not in text:
            marker = "Started features:\n\n"
            addition = "- Config directory resolution.\n- Config directory initialization via `config-init`.\n- Bare profile-name resolution such as `--profile default`.\n"
            if marker in text:
                text = text.replace(marker, marker + addition, 1)
            else:
                text += "\n## Config directory phase\n\n- Config directory resolution.\n- Config directory initialization via `config-init`.\n- Bare profile-name resolution such as `--profile default`.\n"
            roadmap.write_text(text)


def main() -> None:
    patch_core_config_paths()
    patch_cli()
    patch_app()
    patch_docs()


if __name__ == "__main__":
    main()
