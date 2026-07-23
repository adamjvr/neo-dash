// SPDX-License-Identifier: MPL-2.0

//! Toolkit-independent planning data for one libcosmic widget window.
//!
//! This module deliberately converts NeoDash's signed, hand-editable geometry
//! into values safe to pass to a window toolkit. It does not claim to implement
//! monitor selection, anchor semantics, desktop layers, or click-through; those
//! require compositor-specific integration in the following phase.

use neodash_core::WidgetConfig;

#[derive(Debug, Clone, PartialEq, Eq)]
pub(crate) struct WidgetSurfacePlan {
    pub(crate) widget_id: String,
    pub(crate) widget_name: String,
    pub(crate) x: i32,
    pub(crate) y: i32,
    pub(crate) width: u32,
    pub(crate) height: u32,
    pub(crate) padding: u16,
}

impl WidgetSurfacePlan {
    pub(crate) fn from_widget(widget: &WidgetConfig) -> Self {
        Self {
            widget_id: widget.id.0.clone(),
            widget_name: widget.name.clone(),
            x: widget.geometry.x,
            y: widget.geometry.y,
            width: positive_dimension(widget.geometry.width),
            height: positive_dimension(widget.geometry.height),
            padding: u16::try_from(widget.style.padding).unwrap_or(u16::MAX),
        }
    }
}

fn positive_dimension(value: i32) -> u32 {
    u32::try_from(value).unwrap_or(1).max(1)
}

#[cfg(test)]
mod tests {
    use super::*;
    use neodash_core::{SourceConfig, WidgetConfig, WidgetId, WidgetType};

    fn widget() -> WidgetConfig {
        WidgetConfig {
            id: WidgetId("clock".to_string()),
            name: "Clock".to_string(),
            widget_type: WidgetType::Shell,
            enabled: true,
            source: SourceConfig::default(),
            geometry: Default::default(),
            style: Default::default(),
        }
    }

    #[test]
    fn keeps_configured_position_and_size() {
        let mut widget = widget();
        widget.geometry.x = 120;
        widget.geometry.y = 240;
        widget.geometry.width = 640;
        widget.geometry.height = 180;

        let plan = WidgetSurfacePlan::from_widget(&widget);

        assert_eq!((plan.x, plan.y), (120, 240));
        assert_eq!((plan.width, plan.height), (640, 180));
    }

    #[test]
    fn clamps_invalid_dimensions_before_toolkit_use() {
        let mut widget = widget();
        widget.geometry.width = 0;
        widget.geometry.height = -50;

        let plan = WidgetSurfacePlan::from_widget(&widget);

        assert_eq!((plan.width, plan.height), (1, 1));
    }

    #[test]
    fn caps_padding_at_the_toolkit_limit() {
        let mut widget = widget();
        widget.style.padding = u32::MAX;

        let plan = WidgetSurfacePlan::from_widget(&widget);

        assert_eq!(plan.padding, u16::MAX);
    }
}
