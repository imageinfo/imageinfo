//! Shared command and result boundaries for the first imageinfo executable.
//!
//! Media parsing is introduced separately. Help and version reporting use only
//! built-in definitions; neither operation reads input files or configuration.

pub mod cli;
pub mod output;

/// The current capability inventory revision. It is not a runtime support claim.
pub const CAPABILITY_DATA_REVISION: &str = "2026-10-10.9";

/// Version reported by both the library boundary and the executable.
pub const VERSION: &str = env!("CARGO_PKG_VERSION");
