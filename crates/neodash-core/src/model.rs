// SPDX-License-Identifier: MPL-2.0

use crate::ids::WidgetId;
use serde::{Deserialize, Serialize};

/// Top-level widget config.
///
/// This is the file format users should be able to understand and edit by hand.
/// The GUI editor should write the same structure instead of hiding everything
/// in a private database.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct WidgetConfig {
    pub id: WidgetId,
    pub name: String,

    #[serde(rename = "type")]
    pub widget_type: WidgetType,

    #[serde(default = "default_true")]
    pub enabled: bool,

    #[serde(default)]
    pub source: SourceConfig,

    #[serde(default)]
    pub geometry: GeometryConfig,

    #[serde(default)]
    pub style: StyleConfig,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum WidgetType {
    Shell,
    Log,
    Image,
    Web,
    Text,
}

/// The unified source config.
///
/// For v0.1 this is mostly shell-command data. Later we can split this into
/// tagged enum variants if the config starts getting too chunky.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SourceConfig {
    #[serde(default)]
    pub command: Option<String>,

    #[serde(default = "default_shell")]
    pub shell: Option<String>,

    #[serde(default)]
    pub file_path: Option<String>,

    #[serde(default)]
    pub url: Option<String>,

    #[serde(default = "default_interval_ms")]
    pub interval_ms: u64,

    #[serde(default = "default_timeout_ms")]
    pub timeout_ms: u64,

    #[serde(default)]
    pub show_stderr: bool,

    #[serde(default = "default_true")]
    pub parse_ansi: bool,
}

impl Default for SourceConfig {
    fn default() -> Self {
        Self {
            command: None,
            shell: default_shell(),
            file_path: None,
            url: None,
            interval_ms: default_interval_ms(),
            timeout_ms: default_timeout_ms(),
            show_stderr: false,
            parse_ansi: true,
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GeometryConfig {
    #[serde(default = "default_monitor")]
    pub monitor: String,

    #[serde(default = "default_x")]
    pub x: i32,

    #[serde(default = "default_y")]
    pub y: i32,

    #[serde(default = "default_width")]
    pub width: i32,

    #[serde(default = "default_height")]
    pub height: i32,

    #[serde(default)]
    pub anchor: Anchor,

    #[serde(default)]
    pub layer: DesktopLayer,

    #[serde(default = "default_true")]
    pub click_through: bool,
}

impl Default for GeometryConfig {
    fn default() -> Self {
        Self {
            monitor: default_monitor(),
            x: default_x(),
            y: default_y(),
            width: default_width(),
            height: default_height(),
            anchor: Anchor::default(),
            layer: DesktopLayer::default(),
            click_through: true,
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize, Default)]
#[serde(rename_all = "kebab-case")]
pub enum Anchor {
    #[default]
    TopLeft,
    TopRight,
    BottomLeft,
    BottomRight,
    Center,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize, Default)]
#[serde(rename_all = "kebab-case")]
pub enum DesktopLayer {
    #[default]
    Background,
    Bottom,
    Top,
    Overlay,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct StyleConfig {
    #[serde(default = "default_font_family")]
    pub font_family: String,

    #[serde(default = "default_font_size")]
    pub font_size: u32,

    #[serde(default = "default_foreground")]
    pub foreground: String,

    #[serde(default = "default_background")]
    pub background: String,

    #[serde(default = "default_opacity")]
    pub opacity: f32,

    #[serde(default = "default_padding")]
    pub padding: u32,

    #[serde(default)]
    pub border_radius: u32,
}

impl Default for StyleConfig {
    fn default() -> Self {
        Self {
            font_family: default_font_family(),
            font_size: default_font_size(),
            foreground: default_foreground(),
            background: default_background(),
            opacity: default_opacity(),
            padding: default_padding(),
            border_radius: 0,
        }
    }
}

fn default_true() -> bool {
    true
}

fn default_shell() -> Option<String> {
    Some("/bin/sh".to_string())
}

fn default_interval_ms() -> u64 {
    1_000
}

fn default_timeout_ms() -> u64 {
    2_000
}

fn default_monitor() -> String {
    "primary".to_string()
}

fn default_x() -> i32 {
    40
}

fn default_y() -> i32 {
    40
}

fn default_width() -> i32 {
    400
}

fn default_height() -> i32 {
    120
}

fn default_font_family() -> String {
    "monospace".to_string()
}

fn default_font_size() -> u32 {
    14
}

fn default_foreground() -> String {
    "#eeeeee".to_string()
}

fn default_background() -> String {
    "#00000088".to_string()
}

fn default_opacity() -> f32 {
    1.0
}

fn default_padding() -> u32 {
    8
}
