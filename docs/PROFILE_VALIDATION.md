# Profile validation

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
cargo run -p neodash-app --features gui,x11-desktop -- \
  --profile examples/profiles/default.toml \
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
