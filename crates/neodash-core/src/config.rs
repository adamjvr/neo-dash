// SPDX-License-Identifier: MPL-2.0

use crate::model::WidgetConfig;

/// Parse a widget TOML file into the shared data model.
pub fn load_widget_from_toml_str(input: &str) -> anyhow::Result<WidgetConfig> {
    let widget: WidgetConfig = toml::from_str(input)?;
    Ok(widget)
}

/// Serialize a widget back to TOML.
///
/// This is important because the GUI editor should not mangle the user's config
/// into some unreadable blob. The app should be a good citizen.
pub fn save_widget_to_toml_string(widget: &WidgetConfig) -> anyhow::Result<String> {
    let text = toml::to_string_pretty(widget)?;
    Ok(text)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::{Anchor, DesktopLayer, WidgetType};

    #[test]
    fn parses_basic_shell_widget_with_partial_source_defaults() {
        let raw = r#"
id = "date-clock"
name = "Date Clock"
type = "shell"

[source]
command = "date"
"#;

        let widget = load_widget_from_toml_str(raw).expect("widget should parse");
        assert_eq!(widget.name, "Date Clock");
        assert_eq!(widget.widget_type, WidgetType::Shell);
        assert_eq!(widget.source.command.as_deref(), Some("date"));
        assert_eq!(widget.source.shell.as_deref(), Some("/bin/sh"));
        assert_eq!(widget.source.interval_ms, 1_000);
        assert_eq!(widget.source.timeout_ms, 2_000);
        assert!(widget.source.parse_ansi);
    }

    #[test]
    fn parses_partial_geometry_and_style_defaults() {
        let raw = r##"
id = "status"
name = "Status"
type = "text"

[geometry]
x = 256
y = 128

[style]
foreground = "#ffffff"
"##;

        let widget = load_widget_from_toml_str(raw).expect("widget should parse");
        assert_eq!(widget.geometry.monitor, "primary");
        assert_eq!(widget.geometry.x, 256);
        assert_eq!(widget.geometry.y, 128);
        assert_eq!(widget.geometry.width, 400);
        assert_eq!(widget.geometry.height, 120);
        assert_eq!(widget.geometry.anchor, Anchor::TopLeft);
        assert_eq!(widget.geometry.layer, DesktopLayer::Background);
        assert!(widget.geometry.click_through);
        assert_eq!(widget.style.font_family, "monospace");
        assert_eq!(widget.style.foreground, "#ffffff");
        assert_eq!(widget.style.background, "#00000088");
    }

    #[test]
    fn round_trips_widget_toml() {
        let raw = r#"
id = "date-clock"
name = "Date Clock"
type = "shell"

[source]
command = "date '+%Y-%m-%d %H:%M:%S'"
interval_ms = 1000
"#;

        let widget = load_widget_from_toml_str(raw).expect("widget should parse");
        let saved = save_widget_to_toml_string(&widget).expect("widget should serialize");
        let reparsed = load_widget_from_toml_str(&saved).expect("saved widget should reparse");
        assert_eq!(reparsed.id.0, "date-clock");
        assert_eq!(
            reparsed.source.command.as_deref(),
            Some("date '+%Y-%m-%d %H:%M:%S'")
        );
    }
}
