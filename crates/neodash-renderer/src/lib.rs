// SPDX-License-Identifier: MPL-2.0

//! Renderer abstraction.
//!
//! This crate should eventually know how to convert source output into a visual
//! model. Actual GTK widgets live in neodash-app, not here.

use neodash_core::WidgetType;

#[derive(Debug, Clone)]
pub enum RenderPayload {
    PlainText(String),
    TerminalText(String),
    ImagePath(String),
    Html(String),
    Empty,
}

pub fn default_payload_for_type(widget_type: WidgetType) -> RenderPayload {
    match widget_type {
        WidgetType::Shell | WidgetType::Log | WidgetType::Text => {
            RenderPayload::PlainText(String::new())
        }
        WidgetType::Image => RenderPayload::ImagePath(String::new()),
        WidgetType::Web => RenderPayload::Html(String::new()),
    }
}
