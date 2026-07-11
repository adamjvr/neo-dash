// SPDX-License-Identifier: MPL-2.0

//! Future log tailing support.
//!
//! v0.1 shell widgets come first. This crate exists now so the architecture is
//! ready for GeekTool-style file/log widgets later.

#[derive(Debug, Clone)]
pub struct TailEvent {
    pub line: String,
}

pub fn placeholder() -> &'static str {
    "neodash-tail: log tailing is not implemented yet"
}
