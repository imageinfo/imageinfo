//! Reviewed #0084 preservation through the adopted production packet profile.
use super::mapping::{
    ConflictPolicy, Decision, OriginalSnapshot, TARGET_LOCAL, TARGET_NAMESPACE, compare,
};
use crate::xmp::{Limits, RDF, Value, inspect};
use roxmltree::{Document, Node, ParsingOptions};
use std::borrow::Cow;
use std::ops::Range;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Kind {
    NoOp,
    Derivative,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Change {
    /// Whole replaced lexical date value, not a list of minimal differing bytes.
    pub original: Range<usize>,
    pub derivative: Range<usize>,
}

#[derive(Debug, PartialEq, Eq)]
pub struct Prepared<'a> {
    pub bytes: Cow<'a, [u8]>,
    pub kind: Kind,
    pub changed: Option<Change>,
    pub production_mutation_allowed: bool,
    pub facts: Facts,
}

#[derive(Debug, PartialEq, Eq)]
pub struct Facts {
    pub mapping: &'static str,
    pub target_ordinal: usize,
    pub previous: String,
    pub mapped: String,
    pub losses: Vec<super::mapping::Loss>,
    pub acknowledged: Vec<super::mapping::Loss>,
    pub conflict_policy: &'static str,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Refusal {
    Inspect(crate::xmp::Refusal),
    Mapping(super::mapping::Refusal),
    Decision(Decision),
    LexicalTarget,
    Span,
    DerivativeLimit,
    Verification,
}

fn target_span(source: &str, previous: &str) -> Result<Range<usize>, Refusal> {
    // The first bounded inspection already established the finite document shape.
    // Positions are enabled only here to bind the lexical complement; #0081's
    // semantic model deliberately carries no per-property byte offsets.
    let doc = Document::parse_with_options(
        source,
        ParsingOptions {
            allow_dtd: false,
            nodes_limit: Limits::default().nodes,
            entity_resolver: None,
        },
    )
    .map_err(|_| Refusal::Verification)?;
    let description = doc
        .descendants()
        .find(|n| n.has_tag_name((RDF, "Description")))
        .ok_or(Refusal::Span)?;
    let mut spans = Vec::new();
    for attr in description.attributes() {
        if attr.namespace() == Some(TARGET_NAMESPACE) && attr.name() == TARGET_LOCAL {
            spans.push(attr.range_value());
        }
    }
    for child in description.children().filter(Node::is_element) {
        if !child.has_tag_name((TARGET_NAMESPACE, TARGET_LOCAL)) {
            continue;
        }
        // A plain sole text child can be replaced without serializing XML. CDATA,
        // references and comment/PI-separated text have lexical structure which
        // this small mechanism deliberately refuses to rewrite.
        let children: Vec<_> = child.children().collect();
        if children.len() != 1 || !children[0].is_text() {
            return Err(Refusal::LexicalTarget);
        }
        spans.push(children[0].range());
    }
    if spans.len() != 1 {
        return Err(Refusal::Span);
    }
    let span = spans.pop().ok_or(Refusal::Span)?;
    if source.get(span.clone()) != Some(previous) {
        return Err(Refusal::LexicalTarget);
    }
    Ok(span)
}

/// Recompute mapping/conflicts against immutable original input, then either
/// borrow the entire unchanged input or return a separately owned byte vector.
/// Typed snapshots are untrusted observations; this function grants no filesystem
/// identity, preservation admission beyond its measured bytes, or mutation right.
pub fn prepare<'a>(
    input: &'a [u8],
    original: &OriginalSnapshot<'_>,
    selected_target_ordinal: usize,
    policy: ConflictPolicy<'_>,
) -> Result<Prepared<'a>, Refusal> {
    let limits = Limits::default();
    let before = inspect(input, limits).map_err(Refusal::Inspect)?;
    before.check_edit_constraints().map_err(Refusal::Inspect)?;
    let comparison =
        compare(original, &before, selected_target_ordinal, policy).map_err(Refusal::Mapping)?;
    let facts = Facts {
        mapping: comparison.mapping,
        target_ordinal: comparison.target_ordinal,
        previous: comparison.previous.clone(),
        mapped: comparison.mapped.clone(),
        losses: comparison.destination_losses.clone(),
        conflict_policy: match policy {
            ConflictPolicy::Refuse => "refuse",
            ConflictPolicy::KeepDestination => "keep-destination",
            ConflictPolicy::ReplaceSelected { .. } => "replace-selected",
        },
        acknowledged: match policy {
            ConflictPolicy::ReplaceSelected { acknowledged } => acknowledged.to_vec(),
            _ => vec![],
        },
    };
    match comparison.decision {
        Decision::NoOp => {
            return Ok(Prepared {
                bytes: Cow::Borrowed(input),
                kind: Kind::NoOp,
                changed: None,
                production_mutation_allowed: false,
                facts,
            });
        }
        Decision::ReplaceIntentOnly => {}
        other => return Err(Refusal::Decision(other)),
    }
    let span = target_span(before.source(), &comparison.previous)?;
    // #0083 produces only this bounded ASCII date alphabet; checking it here
    // prevents a future mapping change from accidentally becoming an XML escape
    // policy or introducing markup into the direct lexical replacement.
    if comparison.mapped.is_empty()
        || comparison.mapped.len() > 35
        || !comparison
            .mapped
            .bytes()
            .all(|b| b.is_ascii_digit() || b"-:T.+".contains(&b))
    {
        return Err(Refusal::Verification);
    }
    let output_length = input
        .len()
        .checked_sub(span.len())
        .and_then(|n| n.checked_add(comparison.mapped.len()))
        .filter(|&n| n <= limits.bytes)
        .ok_or(Refusal::DerivativeLimit)?;
    let end = span
        .start
        .checked_add(comparison.mapped.len())
        .ok_or(Refusal::Span)?;
    let mut output = Vec::with_capacity(output_length);
    output.extend_from_slice(input.get(..span.start).ok_or(Refusal::Span)?);
    output.extend_from_slice(comparison.mapped.as_bytes());
    output.extend_from_slice(input.get(span.end..).ok_or(Refusal::Span)?);
    if output.len() != output_length
        || output[..span.start] != input[..span.start]
        || output[end..] != input[span.end..]
    {
        return Err(Refusal::Verification);
    }
    let after = inspect(&output, limits).map_err(|_| Refusal::Verification)?;
    let mut expected = before.properties().to_vec();
    let selected = expected
        .iter_mut()
        .find(|p| p.ordinal == selected_target_ordinal)
        .ok_or(Refusal::Verification)?;
    selected.value = Value::Text(comparison.mapped);
    if after.properties() != expected {
        return Err(Refusal::Verification);
    }
    Ok(Prepared {
        bytes: Cow::Owned(output),
        kind: Kind::Derivative,
        changed: Some(Change {
            original: span.clone(),
            derivative: span.start..end,
        }),
        production_mutation_allowed: false,
        facts,
    })
}
