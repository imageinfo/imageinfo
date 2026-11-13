use super::{CompiledFilter, Coverage, Evaluation, Occurrence, Registry, SelectorObservation};
use crate::{privacy, reader};
use std::sync::Arc;

impl Registry {
    /// Returns the fixed registry required by `CompiledFilter::evaluate_metadata`.
    /// It admits the reader's existing selector spellings and reserves built-in
    /// declaration identities before any native observation is evaluated.
    pub fn native() -> Self {
        let reader_names = reader::NAMES
            .iter()
            .copied()
            .chain(["ExifImageWidth", "ExifImageHeight"]);
        let selectors = reader_names.clone().flat_map(|name| {
            [
                "",
                "EXIF:",
                "exif:",
                "Canon:",
                "canon:",
                "CTMD:",
                "canon:ctmd:",
                "Binary:",
                "canon:binary:",
            ]
            .map(|prefix| format!("{prefix}{name}"))
        });
        let mut registry = Registry::new(
            reader::READER_REVISION,
            selectors,
            reader_names.chain(["ISOSpeedRatings", privacy::OWNER_LOCAL]),
            [
                ("http://ns.adobe.com/exif/1.0/", "ISOSpeedRatings"),
                ("http://ns.adobe.com/exif/1.0/", "DateTimeOriginal"),
                (privacy::OWNER_NAMESPACE, privacy::OWNER_LOCAL),
            ],
        )
        .expect("static native registry identities are valid and unique");
        Arc::get_mut(&mut registry.0)
            .expect("new native registry has one owner")
            .native = true;
        registry
    }
}

impl CompiledFilter {
    /// Evaluates retained native metadata using a request compiled with `Registry::native()`.
    /// The native reader reports partial coverage. Observed occurrences can establish
    /// presence, while unobserved scopes and value comparisons remain unknown.
    pub fn evaluate_metadata(&self, metadata: &reader::Metadata) -> Evaluation {
        if !self.registry.0.native || self.registry_revision() != reader::READER_REVISION {
            return Evaluation::registry_mismatch();
        }

        // With incomplete coverage the evaluator only needs evidence of presence.
        // Scalar views would be usable only after proving singleton completeness.
        let present = SelectorObservation {
            coverage: Coverage::Incomplete,
            occurrences: vec![Occurrence {
                raw: None,
                normalized: None,
            }],
        };
        self.evaluate_with(|selector| {
            let (namespace, name) = reader::selector(selector).ok()?;
            metadata
                .occurrences
                .iter()
                .any(|occurrence| {
                    occurrence.name == name && namespace.is_none_or(|ns| occurrence.namespace == ns)
                })
                .then_some(&present)
        })
    }
}
