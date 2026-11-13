//! Authored consumers of the pure filter API over production CR3 reads.
#[allow(dead_code)]
mod support;

use imageinfo::pure_filter::{
    CompileError, CompiledFilter, DeclarationError, ExpressionError, IssueKind, Registry, Truth,
    compile,
};
use imageinfo::reader::{self, Limits};
use serde_json::{Value, json};
use std::{fs, io::Cursor};

fn envelope(registry: &Registry, expression: &str) -> Value {
    json!({
        "version": "pure-data-v1",
        "registryRevision": registry.revision(),
        "expression": expression,
        "aliases": [{ "name": "capture_iso", "selector": "EXIF:ISO" }],
        "parameters": [],
        "definitions": [],
    })
}

fn request(expression: &str) -> CompiledFilter {
    let registry = Registry::native();
    compile(
        &serde_json::to_vec(&envelope(&registry, expression)).unwrap(),
        &registry,
    )
    .unwrap()
}

#[test]
fn observed_native_exists_selects_after_replacement_and_deletion() {
    let filter = request(
        r#"exists(alias("capture_iso")) and exists("canon:ctmd:ISO") and exists("EXIF:ExifImageWidth")"#,
    );
    let dir = support::TempDir::new();
    let path = dir.path.join("authored.cr3");
    fs::write(&path, support::fixture().bytes).unwrap();
    let retained = reader::read_file(&path, Limits::default()).unwrap();
    let bytes_read = retained.bytes_read;
    let selected = reader::select(&retained, &[]).unwrap();
    let before = retained.snapshot("authored", "authored.cr3", &selected, false);

    fs::write(&path, b"replacement bytes after extraction").unwrap();
    assert!(reader::read_file(&path, Limits::default()).is_err());
    let after_replacement = filter.evaluate_metadata(&retained);
    assert_eq!(after_replacement.truth, Truth::True);
    assert!(after_replacement.issues.is_empty());

    fs::remove_file(&path).unwrap();
    assert_eq!(
        reader::read_file(&path, Limits::default())
            .unwrap_err()
            .code,
        "INPUT_IO"
    );
    let after_deletion = filter.evaluate_metadata(&retained);
    assert_eq!(after_deletion.truth, Truth::True);
    assert!(after_deletion.issues.is_empty());
    assert_eq!(retained.bytes_read, bytes_read);
    assert_eq!(
        retained.snapshot("authored", "authored.cr3", &selected, false),
        before
    );
    assert_eq!(before["coverage"][0]["state"], "partial");
    assert!(fs::read_dir(&dir.path).unwrap().next().is_none());
}

#[test]
fn native_partial_scope_never_establishes_absence_or_value_uniqueness() {
    let retained = reader::read(Cursor::new(support::fixture().bytes), Limits::default()).unwrap();
    let observed_absent = request(r#"absent("EXIF:ISO")"#).evaluate_metadata(&retained);
    assert_eq!(observed_absent.truth, Truth::False);
    assert!(observed_absent.issues.is_empty());

    for (expression, selector) in [
        (r#"exists("Canon:ISO")"#, "Canon:ISO"),
        (r#"absent("Canon:ISO")"#, "Canon:ISO"),
        (r#"exists("Binary:ISO")"#, "Binary:ISO"),
        (r#"value("EXIF:ISO", "raw") >= 400"#, "EXIF:ISO"),
        (r#"value("EXIF:ISO", "normalized") >= 400"#, "EXIF:ISO"),
    ] {
        let result = request(expression).evaluate_metadata(&retained);
        assert_eq!(result.truth, Truth::Unknown, "{expression}");
        assert_eq!(result.issues.len(), 1, "{expression}");
        assert_eq!(result.issues[0].kind, IssueKind::IncompleteCoverage);
        assert_eq!(result.issues[0].selector.as_deref(), Some(selector));
    }
}

#[test]
fn native_short_circuit_skips_unobserved_branches() {
    let retained = reader::read(Cursor::new(support::fixture().bytes), Limits::default()).unwrap();
    let skipped =
        request(r#"exists("EXIF:ISO") or exists("Canon:ISO")"#).evaluate_metadata(&retained);
    assert_eq!(skipped.truth, Truth::True);
    assert!(skipped.issues.is_empty());

    let visited =
        request(r#"exists("Canon:ISO") or exists("EXIF:ISO")"#).evaluate_metadata(&retained);
    assert_eq!(visited.truth, Truth::True);
    assert_eq!(visited.issues.len(), 1);
    assert_eq!(visited.issues[0].kind, IssueKind::IncompleteCoverage);
    assert_eq!(visited.issues[0].selector.as_deref(), Some("Canon:ISO"));
}

#[test]
fn native_metadata_requires_its_authoritative_registry_even_with_the_same_revision() {
    let retained = reader::read(Cursor::new(support::fixture().bytes), Limits::default()).unwrap();
    for revision in ["different-registry", reader::READER_REVISION] {
        let registry = Registry::new(
            revision,
            ["EXIF:ISO"],
            [] as [&str; 0],
            [] as [(&str, &str); 0],
        )
        .unwrap();
        let mut input = envelope(&registry, r#"exists("EXIF:ISO")"#);
        input["aliases"][0]["name"] = json!("ExifImageWidth");
        let filter = compile(&serde_json::to_vec(&input).unwrap(), &registry).unwrap();
        let result = filter.evaluate_metadata(&retained);
        assert_eq!(result.truth, Truth::Unknown);
        assert_eq!(result.issues.len(), 1);
        assert_eq!(result.issues[0].kind, IssueKind::RegistryMismatch);
    }
}

#[test]
fn native_preflight_refuses_builtin_names_and_expanded_definitions() {
    let registry = Registry::native();
    assert_eq!(registry.revision(), reader::READER_REVISION);
    let mut input = envelope(&registry, r#"exists("EXIF:ISO")"#);
    for name in ["ISO", "ExifImageWidth", "ExifImageHeight"] {
        input["aliases"][0]["name"] = json!(name);
        assert!(matches!(
            compile(&serde_json::to_vec(&input).unwrap(), &registry),
            Err(CompileError::Declaration {
                kind: DeclarationError::NameCollision,
                ..
            })
        ));
    }

    let mut input = envelope(&registry, r#"exists("EXIF:ISO")"#);
    input["definitions"] = json!([{
        "name": "AuthoredIso",
        "namespace": "http://ns.adobe.com/exif/1.0/",
        "localName": "ISOSpeedRatings",
        "type": "integer",
        "provenance": "authored registry collision test",
        "revision": "v1",
    }]);
    assert!(matches!(
        compile(&serde_json::to_vec(&input).unwrap(), &registry),
        Err(CompileError::Declaration {
            kind: DeclarationError::ExpandedNameCollision,
            ..
        })
    ));
}

#[test]
fn native_preflight_refuses_unsupported_selector_in_a_skipped_branch() {
    let registry = Registry::native();
    let input = envelope(&registry, r#"exists("EXIF:ISO") or exists("xmp:Rating")"#);
    assert!(matches!(
        compile(&serde_json::to_vec(&input).unwrap(), &registry),
        Err(CompileError::Expression {
            kind: ExpressionError::UnknownSelector,
            ..
        })
    ));
}
