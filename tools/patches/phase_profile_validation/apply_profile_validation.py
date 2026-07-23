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
        raise SystemExit(f"Could not find expected block while patching {label}:\n{old[:900]}")
    return text.replace(old, new, 1)

def insert_before_once(text: str, marker: str, addition: str, label: str) -> str:
    if addition.strip() in text:
        return text
    if marker not in text:
        raise SystemExit(f"Could not find marker while patching {label}:\n{marker[:500]}")
    return text.replace(marker, addition + marker, 1)

def patch_core_profile() -> None:
    write('crates/neodash-core/src/profile.rs', r'''// SPDX-License-Identifier: MPL-2.0

//! Shared profile model, profile path resolution, and profile validation.
//!
//! Profiles describe which widget files make up a dashboard. Keep this model in
//! `neodash-core` so the CLI, daemon, GTK app, and future editor all agree on
//! the same profile format, relative-path behavior, and validation rules.

use crate::{config::load_widget_from_toml_str, model::WidgetType};
use serde::{Deserialize, Serialize};
use std::{
    collections::HashMap,
    fs,
    path::{Path, PathBuf},
};

/// A NeoDash dashboard profile.
#[derive(Debug, Clone, Default, PartialEq, Eq, Serialize, Deserialize)]
pub struct ProfileConfig {
    /// Stable profile identifier, such as `default`.
    pub id: Option<String>,

    /// Human-readable profile name.
    pub name: Option<String>,

    /// Explicit widget TOML file paths.
    #[serde(default)]
    pub widgets: Vec<PathBuf>,

    /// Direct child directories containing widget TOML files.
    #[serde(default)]
    pub widget_dirs: Vec<PathBuf>,

    /// Optional default desktop-hints behavior for graphical launches.
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

/// Severity for a profile validation issue.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum ProfileValidationSeverity {
    Warning,
    Error,
}

impl ProfileValidationSeverity {
    pub fn as_str(self) -> &'static str {
        match self {
            Self::Warning => "warning",
            Self::Error => "error",
        }
    }
}

/// One validation issue found while checking a profile and its widgets.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct ProfileValidationIssue {
    pub severity: ProfileValidationSeverity,
    pub message: String,
    #[serde(default)]
    pub path: Option<PathBuf>,
    #[serde(default)]
    pub widget_id: Option<String>,
}

impl ProfileValidationIssue {
    pub fn warning(message: impl Into<String>) -> Self {
        Self {
            severity: ProfileValidationSeverity::Warning,
            message: message.into(),
            path: None,
            widget_id: None,
        }
    }

    pub fn error(message: impl Into<String>) -> Self {
        Self {
            severity: ProfileValidationSeverity::Error,
            message: message.into(),
            path: None,
            widget_id: None,
        }
    }

    pub fn with_path(mut self, path: impl Into<PathBuf>) -> Self {
        self.path = Some(path.into());
        self
    }

    pub fn with_widget_id(mut self, widget_id: impl Into<String>) -> Self {
        self.widget_id = Some(widget_id.into());
        self
    }
}

/// Result of validating a loaded profile.
#[derive(Debug, Clone, Default, PartialEq, Eq)]
pub struct ProfileValidationReport {
    pub widget_paths: Vec<PathBuf>,
    pub issues: Vec<ProfileValidationIssue>,
}

impl ProfileValidationReport {
    pub fn has_errors(&self) -> bool {
        self.issues
            .iter()
            .any(|issue| issue.severity == ProfileValidationSeverity::Error)
    }

    pub fn error_count(&self) -> usize {
        self.issues
            .iter()
            .filter(|issue| issue.severity == ProfileValidationSeverity::Error)
            .count()
    }

    pub fn warning_count(&self) -> usize {
        self.issues
            .iter()
            .filter(|issue| issue.severity == ProfileValidationSeverity::Warning)
            .count()
    }
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
pub fn resolve_profile_path(base_dir: &Path, path: &Path) -> PathBuf {
    if path.is_absolute() {
        path.to_path_buf()
    } else {
        base_dir.join(path)
    }
}

/// Collect all widget TOML files referenced by a loaded profile.
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

/// Validate a loaded profile and the widget files it references.
pub fn validate_profile(profile: &LoadedProfile) -> anyhow::Result<ProfileValidationReport> {
    let mut report = ProfileValidationReport::default();
    let mut seen_widget_ids: HashMap<String, PathBuf> = HashMap::new();

    for widget in &profile.profile.widgets {
        report
            .widget_paths
            .push(resolve_profile_path(&profile.base_dir, widget));
    }

    for dir in &profile.profile.widget_dirs {
        let dir = resolve_profile_path(&profile.base_dir, dir);

        if !dir.exists() {
            report.issues.push(
                ProfileValidationIssue::error("widget directory does not exist").with_path(dir),
            );
            continue;
        }

        if !dir.is_dir() {
            report.issues.push(
                ProfileValidationIssue::error("widget directory path is not a directory")
                    .with_path(dir),
            );
            continue;
        }

        match discover_widget_paths(&dir) {
            Ok(mut paths) => report.widget_paths.append(&mut paths),
            Err(error) => report.issues.push(
                ProfileValidationIssue::error(format!("failed to read widget directory: {error}"))
                    .with_path(dir),
            ),
        }
    }

    if report.widget_paths.is_empty() {
        report.issues.push(ProfileValidationIssue::error(
            "profile does not reference any widget files",
        ));
    }

    for path in report.widget_paths.clone() {
        validate_widget_path(&path, &mut seen_widget_ids, &mut report);
    }

    Ok(report)
}

fn validate_widget_path(
    path: &Path,
    seen_widget_ids: &mut HashMap<String, PathBuf>,
    report: &mut ProfileValidationReport,
) {
    if !path.exists() {
        report.issues.push(
            ProfileValidationIssue::error("widget file does not exist").with_path(path),
        );
        return;
    }

    if !path.is_file() {
        report.issues.push(
            ProfileValidationIssue::error("widget path is not a file").with_path(path),
        );
        return;
    }

    let text = match fs::read_to_string(path) {
        Ok(text) => text,
        Err(error) => {
            report.issues.push(
                ProfileValidationIssue::error(format!("failed to read widget file: {error}"))
                    .with_path(path),
            );
            return;
        }
    };

    let widget = match load_widget_from_toml_str(&text) {
        Ok(widget) => widget,
        Err(error) => {
            report.issues.push(
                ProfileValidationIssue::error(format!("failed to parse widget TOML: {error}"))
                    .with_path(path),
            );
            return;
        }
    };

    let widget_id = widget.id.0.clone();

    if let Some(first_path) = seen_widget_ids.insert(widget_id.clone(), path.to_path_buf()) {
        report.issues.push(
            ProfileValidationIssue::error(format!(
                "duplicate widget id also used by {}",
                first_path.display()
            ))
            .with_path(path)
            .with_widget_id(widget_id.clone()),
        );
    }

    if !widget.enabled {
        report.issues.push(
            ProfileValidationIssue::warning("widget is disabled and will not be launched")
                .with_path(path)
                .with_widget_id(widget_id.clone()),
        );
    }

    if widget.enabled && widget.widget_type != WidgetType::Shell {
        report.issues.push(
            ProfileValidationIssue::error(format!(
                "enabled widget type {:?} is not supported by the current profile runtime",
                widget.widget_type
            ))
            .with_path(path)
            .with_widget_id(widget_id.clone()),
        );
    }

    if widget.widget_type == WidgetType::Shell
        && widget
            .source
            .command
            .as_deref()
            .is_none_or(|command| command.trim().is_empty())
    {
        report.issues.push(
            ProfileValidationIssue::error("shell widget is missing a non-empty source.command")
                .with_path(path)
                .with_widget_id(widget_id.clone()),
        );
    }

    if widget.geometry.width <= 0 || widget.geometry.height <= 0 {
        report.issues.push(
            ProfileValidationIssue::error("widget geometry width and height must be positive")
                .with_path(path)
                .with_widget_id(widget_id.clone()),
        );
    }

    if widget.source.interval_ms == 0 {
        report.issues.push(
            ProfileValidationIssue::warning("widget interval_ms is 0; runtime will clamp it")
                .with_path(path)
                .with_widget_id(widget_id),
        );
    }
}

/// Discover direct-child TOML files in a widget directory.
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
    use std::time::{SystemTime, UNIX_EPOCH};

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

    #[test]
    fn validation_reports_duplicate_widget_ids() {
        let temp = make_temp_dir("duplicate-widget-ids");
        let widgets = temp.join("widgets");
        fs::create_dir_all(&widgets).expect("temp widgets dir should be created");

        fs::write(widgets.join("one.toml"), widget_toml("duplicate-id"))
            .expect("first widget should write");
        fs::write(widgets.join("two.toml"), widget_toml("duplicate-id"))
            .expect("second widget should write");
        fs::write(
            temp.join("profile.toml"),
            r#"
id = "test"
widget_dirs = ["widgets"]
"#,
        )
        .expect("profile should write");

        let loaded = load_profile_from_path(temp.join("profile.toml")).expect("profile should load");
        let report = validate_profile(&loaded).expect("validation should run");

        assert!(report.has_errors());
        assert!(report
            .issues
            .iter()
            .any(|issue| issue.message.contains("duplicate widget id")));

        let _ = fs::remove_dir_all(temp);
    }

    #[test]
    fn validation_reports_missing_widget_file() {
        let temp = make_temp_dir("missing-widget-file");
        fs::create_dir_all(&temp).expect("temp dir should be created");
        fs::write(
            temp.join("profile.toml"),
            r#"
id = "test"
widgets = ["missing.toml"]
"#,
        )
        .expect("profile should write");

        let loaded = load_profile_from_path(temp.join("profile.toml")).expect("profile should load");
        let report = validate_profile(&loaded).expect("validation should run");

        assert!(report.has_errors());
        assert!(report
            .issues
            .iter()
            .any(|issue| issue.message.contains("does not exist")));

        let _ = fs::remove_dir_all(temp);
    }

    fn widget_toml(id: &str) -> String {
        format!(
            r#"
id = "{id}"
name = "Test Widget"
type = "shell"
enabled = true

[source]
command = "date"
"#
        )
    }

    fn make_temp_dir(name: &str) -> PathBuf {
        let millis = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .expect("clock should work")
            .as_millis();
        std::env::temp_dir().join(format!("neodash-{name}-{}-{millis}", std::process::id()))
    }
}
''')

def patch_cli() -> None:
    path = 'crates/neodash-cli/src/main.rs'
    text = read(path)

    if 'ProfileCheck' in text and 'validate_profile' in text:
        print('CLI profile-check support already appears to be applied.')
        write(path, text)
        return

    text = replace_once(text, '''use neodash_core::{
    collect_profile_widget_paths, load_profile_from_path, SourceConfig, WidgetConfig, WidgetId,
    WidgetType,
};
''', '''use neodash_core::{
    collect_profile_widget_paths, load_profile_from_path, validate_profile, LoadedProfile,
    ProfileValidationReport, ProfileValidationSeverity, SourceConfig, WidgetConfig, WidgetId,
    WidgetType,
};
''', 'CLI imports')

    text = replace_once(text, '''    /// Inspect a NeoDash profile and print the resolved widget paths.
    ProfileInfo {
        /// Path to a profile TOML file, for example examples/profiles/default.toml.
        path: PathBuf,
    },

    /// Print the backend NeoDash would probably use in this session.
''', '''    /// Inspect a NeoDash profile and print the resolved widget paths.
    ProfileInfo {
        /// Path to a profile TOML file, for example examples/profiles/default.toml.
        path: PathBuf,
    },

    /// Validate a NeoDash profile and every widget file it references.
    ProfileCheck {
        /// Path to a profile TOML file, for example examples/profiles/default.toml.
        path: PathBuf,
    },

    /// Print the backend NeoDash would probably use in this session.
''', 'CLI Commands enum')

    text = replace_once(text, '''        Commands::ProfileInfo { path } => {
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
''', '''        Commands::ProfileInfo { path } => {
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
        Commands::ProfileCheck { path } => {
            let loaded = load_profile_from_path(&path)?;
            let report = validate_profile(&loaded)?;

            print_profile_validation_report(&loaded, &report);

            if report.has_errors() {
                anyhow::bail!(
                    "profile validation failed with {} error(s) and {} warning(s)",
                    report.error_count(),
                    report.warning_count()
                );
            }
        }
        Commands::Backend => {
''', 'CLI ProfileInfo match arm')

    helper = r'''
fn print_profile_validation_report(loaded: &LoadedProfile, report: &ProfileValidationReport) {
    println!("Profile file: {}", loaded.path.display());
    println!(
        "Profile id: {}",
        loaded.profile.id.as_deref().unwrap_or("<unnamed>")
    );
    println!(
        "Profile name: {}",
        loaded.profile.name.as_deref().unwrap_or("<unnamed>")
    );
    println!("Widget files: {}", report.widget_paths.len());
    println!(
        "Issues: {} error(s), {} warning(s)",
        report.error_count(),
        report.warning_count()
    );

    if report.issues.is_empty() {
        println!("Profile OK");
        return;
    }

    for issue in &report.issues {
        let severity = match issue.severity {
            ProfileValidationSeverity::Warning => "warning",
            ProfileValidationSeverity::Error => "error",
        };

        match (&issue.path, &issue.widget_id) {
            (Some(path), Some(widget_id)) => {
                println!(
                    "  {severity}: {} [{}]: {}",
                    path.display(),
                    widget_id,
                    issue.message
                );
            }
            (Some(path), None) => {
                println!("  {severity}: {}: {}", path.display(), issue.message);
            }
            (None, Some(widget_id)) => {
                println!("  {severity}: [{widget_id}]: {}", issue.message);
            }
            (None, None) => {
                println!("  {severity}: {}", issue.message);
            }
        }
    }
}

'''
    text = insert_before_once(text, 'fn main() -> anyhow::Result<()> {', helper, 'CLI validation helper')
    write(path, text)

def patch_app() -> None:
    path = 'crates/neodash-app/src/main.rs'
    text = read(path)

    if 'validate_loaded_profile' in text:
        print('App profile validation support already appears to be applied.')
        write(path, text)
        return

    text = replace_once(text, '''    use neodash_core::{
        collect_profile_widget_paths, discover_widget_paths, load_profile_from_path,
        GeometryConfig, LoadedProfile, WidgetConfig, WidgetType,
    };
''', '''    use neodash_core::{
        collect_profile_widget_paths, discover_widget_paths, load_profile_from_path, validate_profile,
        GeometryConfig, LoadedProfile, ProfileValidationSeverity, WidgetConfig, WidgetType,
    };
''', 'app imports')

    text = replace_once(text, '''        let profile_desktop_hints = loaded_profile
            .as_ref()
            .and_then(|loaded| loaded.profile.desktop_hints)
            .unwrap_or(false);
''', '''        if let Some(loaded) = loaded_profile.as_ref() {
            validate_loaded_profile(loaded)?;
        }

        let profile_desktop_hints = loaded_profile
            .as_ref()
            .and_then(|loaded| loaded.profile.desktop_hints)
            .unwrap_or(false);
''', 'app run validation call')

    helper = r'''    /// Validate a loaded profile before the GTK app opens windows.
    fn validate_loaded_profile(loaded: &LoadedProfile) -> anyhow::Result<()> {
        let report = validate_profile(loaded)?;

        for issue in &report.issues {
            let path = issue
                .path
                .as_ref()
                .map(|path| path.display().to_string())
                .unwrap_or_else(|| "<profile>".to_string());
            let widget_id = issue.widget_id.as_deref().unwrap_or("<none>");

            match issue.severity {
                ProfileValidationSeverity::Warning => tracing::warn!(
                    path = %path,
                    widget_id = widget_id,
                    message = %issue.message,
                    "profile validation warning"
                ),
                ProfileValidationSeverity::Error => tracing::error!(
                    path = %path,
                    widget_id = widget_id,
                    message = %issue.message,
                    "profile validation error"
                ),
            }
        }

        anyhow::ensure!(
            !report.has_errors(),
            "profile {} failed validation with {} error(s) and {} warning(s)",
            loaded.path.display(),
            report.error_count(),
            report.warning_count()
        );

        Ok(())
    }

'''
    text = insert_before_once(text, '    /// Collect widget paths from an optional profile plus explicit CLI arguments.', helper, 'app validation helper')
    write(path, text)

def write_docs() -> None:
    write('docs/PROFILE_VALIDATION.md', '''# Profile validation

NeoDash now has shared profile validation in `neodash-core`.

The point of this phase is simple: the CLI, GTK app, and future daemon should
all agree on whether a profile is valid before any dashboard windows are opened
or any long-running runtime process is started.

## Commands

Inspect a profile and print its resolved widget paths:

```bash
cargo run -p neodash-cli -- profile-info examples/profiles/default.toml
```

Validate a profile and the widget files it references:

```bash
cargo run -p neodash-cli -- profile-check examples/profiles/default.toml
```

Launch the GTK profile preview:

```bash
cargo run -p neodash-app --features gui,x11-desktop -- \\
  --profile examples/profiles/default.toml \\
  --debug-frame
```

The GTK app now runs the same profile validation before opening windows. If the
profile has errors, the app logs the validation errors and exits instead of
opening a partial dashboard.

## What is validated

Current validation checks:

- profile references at least one widget file,
- explicit widget files exist,
- widget directories exist,
- widget directory paths are directories,
- widget files can be read,
- widget TOML parses into `WidgetConfig`,
- widget IDs are unique within the loaded profile,
- disabled widgets are reported as warnings,
- enabled non-shell widgets are rejected by the current runtime,
- shell widgets have a non-empty `source.command`,
- widget width and height are positive,
- `interval_ms = 0` is reported as a warning.

## Why non-shell widgets are currently errors

NeoDash's data model already includes planned widget types such as log, image,
web, and text widgets. The current graphical runtime only supports shell widgets.

For now, an enabled non-shell widget is a validation error because the current
runtime cannot launch it honestly. Later, when each renderer exists, validation
should become renderer-aware instead of shell-only.

## Validation severities

Validation issues are either warnings or errors.

Warnings mean NeoDash can continue, but the profile probably needs attention.
For example, a disabled widget is a warning because the dashboard can still run.

Errors mean the profile should not launch. Missing widget files, duplicate widget
IDs, unparsable TOML, and unsupported enabled widget types are errors.

## Next work

Validation should grow with the runtime:

- duplicate profile IDs when profile collections exist,
- per-renderer validation when log/image/web/text renderers land,
- theme/default validation,
- monitor and geometry validation,
- config directory validation,
- machine-readable JSON validation output,
- daemon-side validation before profile activation.
''')

    for path in ['docs/PROFILE_MODEL.md', 'README.md', 'docs/ROADMAP.md', 'docs/NEXT_STEPS.md']:
        full = ROOT / path
        if not full.exists():
            continue
        text = full.read_text()
        if path == 'docs/PROFILE_MODEL.md' and '## Validation' not in text:
            text += '''\n\n## Validation\n\nProfile validation now lives in `neodash-core` alongside the shared profile model. Use:\n\n```bash\ncargo run -p neodash-cli -- profile-check examples/profiles/default.toml\n```\n\nSee `docs/PROFILE_VALIDATION.md` for details.\n'''
        elif path == 'README.md' and 'profile-check' not in text:
            text += '''\n\n## Profile validation\n\nValidate a profile before launching it:\n\n```bash\ncargo run -p neodash-cli -- profile-check examples/profiles/default.toml\n```\n\nThe GTK app also validates profile launches before opening windows.\n'''
        elif path == 'docs/ROADMAP.md' and 'Profile validation is now shared through `neodash-core`.' not in text:
            text += '''\n\n## Current validation status\n\nProfile validation is now shared through `neodash-core`. The CLI exposes it via:\n\n```bash\ncargo run -p neodash-cli -- profile-check examples/profiles/default.toml\n```\n\nThe GTK app uses the same validation before launching a profile.\n'''
        elif path == 'docs/NEXT_STEPS.md' and '## Current implementation target: daemon-owned profile runtime' not in text:
            text += '''\n\n## Current implementation target: daemon-owned profile runtime\n\nProfile parsing and validation are now shared in `neodash-core`. The next major phase is to make the daemon own a loaded, validated profile instead of keeping all runtime state inside `neodash-app`.\n\nPre-daemon checks:\n\n```bash\ncargo run -p neodash-cli -- profile-check examples/profiles/default.toml\ncargo run -p neodash-app --features gui,x11-desktop -- --profile examples/profiles/default.toml --debug-frame\n```\n'''
        full.write_text(text)

def main() -> None:
    patch_core_profile()
    patch_cli()
    patch_app()
    write_docs()

if __name__ == '__main__':
    main()
