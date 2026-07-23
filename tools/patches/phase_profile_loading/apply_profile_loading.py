
from pathlib import Path
import re

ROOT = Path.cwd()

def replace_once(text, old, new, label):
    if old not in text:
        raise SystemExit(f"missing patch target: {label}")
    return text.replace(old, new, 1)

def write(path, text):
    p = ROOT / path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)

cargo_path = ROOT / "crates/neodash-app/Cargo.toml"
cargo = cargo_path.read_text()
if "serde.workspace = true" not in cargo:
    cargo = cargo.replace("clap.workspace = true\n", "clap.workspace = true\nserde.workspace = true\n", 1)
if "toml.workspace = true" not in cargo:
    cargo = cargo.replace("tracing.workspace = true\n", "toml.workspace = true\ntracing.workspace = true\n", 1)
cargo_path.write_text(cargo)

main_path = ROOT / "crates/neodash-app/src/main.rs"
text = main_path.read_text()

if "--profile" not in text or "ProfileConfig" not in text:
    text = replace_once(
        text,
        '    use neodash_runtime::load_widget_from_path;\n    use std::{\n',
        '    use neodash_runtime::load_widget_from_path;\n    use serde::Deserialize;\n    use std::{\n',
        "serde import",
    )

    text = replace_once(
        text,
        '''        #[arg(long = "widgets-dir", value_name = "DIR")]
        widget_dirs: Vec<PathBuf>,

        /// Show normal window-manager decorations.
''',
        '''        #[arg(long = "widgets-dir", value_name = "DIR")]
        widget_dirs: Vec<PathBuf>,

        /// Profile TOML file describing a dashboard.
        ///
        /// Relative widget paths and widget directories inside the profile are
        /// resolved relative to the profile file's parent directory.
        #[arg(long = "profile", value_name = "FILE")]
        profile: Option<PathBuf>,

        /// Show normal window-manager decorations.
''',
        "profile cli option",
    )

    text = replace_once(
        text,
        '''        let cli = Cli::parse();

        let options = PreviewOptions {
''',
        '''        let cli = Cli::parse();

        let loaded_profile = match cli.profile.as_ref() {
            Some(profile_path) => Some(load_profile(profile_path)?),
            None => None,
        };

        let profile_desktop_hints = loaded_profile
            .as_ref()
            .and_then(|loaded| loaded.profile.desktop_hints)
            .unwrap_or(false);

        let options = PreviewOptions {
''',
        "profile load block",
    )

    text = replace_once(
        text,
        "            desktop_hints: cli.desktop_hints,\n",
        "            desktop_hints: cli.desktop_hints || profile_desktop_hints,\n",
        "profile desktop hints",
    )

    text = replace_once(
        text,
        "        let widget_paths = collect_widget_paths(&cli)?;\n",
        "        let widget_paths = collect_widget_paths(&cli, loaded_profile.as_ref())?;\n",
        "collect call",
    )

    profile_code = '''    #[derive(Debug, Deserialize)]
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
        let base_dir = path.parent().unwrap_or_else(|| Path::new(".")).to_path_buf();

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
        if path.is_absolute() { path.to_path_buf() } else { base_dir.join(path) }
    }

'''
    marker = "    /// Collect widget paths from explicit `--widget` arguments and direct child\n"
    if marker not in text:
        raise SystemExit("missing collect_widget_paths marker")
    text = text.replace(marker, profile_code + marker, 1)

    pattern = r'    /// Collect widget paths from explicit `--widget` arguments and direct child\n.*?    fn collect_widget_paths\(cli: &Cli\) -> anyhow::Result<Vec<PathBuf>> \{.*?    \}\n\n    /// Discover direct-child TOML files in a widget directory\.'
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

    /// Discover direct-child TOML files in a widget directory.'''
    text, n = re.subn(pattern, new_collect, text, flags=re.S)
    if n != 1:
        raise SystemExit(f"collect_widget_paths replacement count was {n}")

    main_path.write_text(text)
else:
    print("Profile loading support already appears to be present.")

write("examples/profiles/default.toml", '''id = "default"
name = "Default NeoDash Example Dashboard"

# Relative paths are resolved from this profile file's parent directory.
widget_dirs = ["../widgets"]

desktop_hints = true
''')

write("docs/PROFILE_LOADING.md", '''# Profile loading

NeoDash can launch a dashboard from a profile TOML file.

```bash
cargo run -p neodash-app --features gui,x11-desktop -- \\
  --profile examples/profiles/default.toml \\
  --debug-frame
```

The current implementation is intentionally app-local. The next cleanup is to
move the profile model and path resolution into `neodash-core` so the CLI,
daemon, and GTK app share one parser.

## Format

```toml
id = "default"
name = "Default NeoDash Example Dashboard"
widget_dirs = ["../widgets"]
widgets = []
desktop_hints = true
```

Relative paths are resolved from the profile file's parent directory. The
example profile lives in `examples/profiles`, so `../widgets` points at
`examples/widgets`.

## Current limitations

- No recursive widget directory loading.
- No duplicate widget ID validation yet.
- No themes or per-widget overrides yet.
- No daemon-owned profile state yet.
''')

for doc in ["README.md", "docs/NEXT_STEPS.md", "docs/ROADMAP.md"]:
    p = ROOT / doc
    if not p.exists():
        continue
    t = p.read_text()
    if doc == "README.md" and "## Profile loading" not in t:
        block = '''
## Profile loading

NeoDash can now launch a dashboard from a profile file:

```bash
cargo run -p neodash-app --features gui,x11-desktop -- \\
  --profile examples/profiles/default.toml \\
  --debug-frame
```

See `docs/PROFILE_LOADING.md` for the current profile format and limitations.
'''
        marker = "## Widget file model\n"
        t = t.replace(marker, block + "\n" + marker, 1) if marker in t else t + block
    elif doc == "docs/NEXT_STEPS.md" and "promote profile loading" not in t:
        t += "\n\n## Current implementation target: promote profile loading\n\nProfile loading now exists in the GTK app. Next, move `ProfileConfig` into `neodash-core`, add parsing tests, add duplicate widget ID validation, and define the `~/.config/neodash` layout.\n"
    elif doc == "docs/ROADMAP.md":
        t = t.replace("## Phase 5: profile and config directory runtime\n\nStatus: planned.", "## Phase 5: profile and config directory runtime\n\nStatus: started.")
        if "Initial `--profile` support in `neodash-app`." not in t:
            t += "\n\n## Phase 5 update: profile loading started\n\n- Initial `--profile` support in `neodash-app`.\n- Example profile at `examples/profiles/default.toml`.\n- Relative path resolution for profile widget paths and directories.\n"
    p.write_text(t)

print("Applied NeoDash profile loading phase.")
