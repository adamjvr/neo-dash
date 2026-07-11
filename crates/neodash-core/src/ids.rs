// SPDX-License-Identifier: MPL-2.0

use serde::{Deserialize, Serialize};
use std::fmt::{Display, Formatter};

/// A stable widget identifier.
///
/// This is intentionally just a string wrapper. Human-readable IDs are nicer in
/// config files than random UUIDs, and for a desktop widget tool that is a good
/// tradeoff. We can still add UUID helpers later if needed.
#[derive(Debug, Clone, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(transparent)]
pub struct WidgetId(pub String);

impl Display for WidgetId {
    fn fmt(&self, f: &mut Formatter<'_>) -> std::fmt::Result {
        write!(f, "{}", self.0)
    }
}

/// A stable profile/layout identifier.
#[derive(Debug, Clone, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(transparent)]
pub struct ProfileId(pub String);

impl Display for ProfileId {
    fn fmt(&self, f: &mut Formatter<'_>) -> std::fmt::Result {
        write!(f, "{}", self.0)
    }
}
