// SPDX-License-Identifier: MPL-2.0

//! Shared NeoDash data model.
//!
//! Keep this crate boring and dependable. Every other crate should be allowed to
//! depend on `neodash-core`, so do not pull GUI/toolkit/platform bullshit in here.

pub mod config;
pub mod ids;
pub mod model;
pub mod profile;

pub use config::{load_widget_from_toml_str, save_widget_to_toml_string};
pub use ids::{ProfileId, WidgetId};
pub use model::*;
pub use profile::*;
