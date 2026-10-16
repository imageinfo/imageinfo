//! Shared command and result boundaries for the first imageinfo executable.
//!
//! Media parsing is introduced separately. Help and version reporting use only
//! built-in definitions; neither operation reads input files or configuration.

pub mod cli;
pub mod output;
pub mod pairing;
pub mod plan;
pub mod preview;
pub mod read_request;
pub mod read_session;
pub mod reader;
pub mod source_binding;
pub mod xmp;

/// The current capability inventory revision. It is not a runtime support claim.
pub const CAPABILITY_DATA_REVISION: &str = "2026-10-12.1";

/// Version reported by both the library boundary and the executable.
pub const VERSION: &str = env!("CARGO_PKG_VERSION");
