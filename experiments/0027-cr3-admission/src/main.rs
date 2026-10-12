//! Read-only qualification entry point, not a product mutation command.
use imageinfo::reader::{
    Range,
    admission::{self, DateTime},
};
use std::{
    error::Error,
    fs::{self, OpenOptions},
    path::Path,
};
type Result<T> = std::result::Result<T, Box<dyn Error>>;
fn main() {
    if let Err(error) = run() {
        eprintln!(
            "{}",
            serde_json::json!({"issue":error.to_string().chars().filter(|c| !c.is_control()).take(256).collect::<String>(),"productionMutationAllowed":false,"artifactsCreated":false})
        );
        std::process::exit(2);
    }
}
fn run() -> Result<()> {
    let args: Vec<_> = std::env::args_os().skip(1).collect();
    if args.len() == 1 && (args[0] == "--help" || args[0] == "help") {
        println!(
            "Read-only CR3 admission research\n\nUsage: imageinfo-cr3-admission-probe inspect SOURCE \"YYYY:MM:DD HH:MM:SS\" [EXPECTED_OFFSET]\nNo writes, signature verification or production capability are enabled."
        );
        return Ok(());
    }
    if !(3..=4).contains(&args.len()) || args[0] != "inspect" {
        return Err("Expected inspect SOURCE DATE [EXPECTED_OFFSET]".into());
    }
    let date = DateTime::parse(args[2].to_str().ok_or("Date must be ASCII")?)?;
    let expected = args
        .get(3)
        .map(|v| -> Result<Range> {
            Ok(Range {
                offset: v.to_str().ok_or("Invalid offset")?.parse()?,
                length: 20,
            })
        })
        .transpose()?;
    let path = Path::new(&args[1]);
    if !fs::symlink_metadata(path)?.is_file() {
        return Err("Direct regular source required".into());
    }
    let mut options = OpenOptions::new();
    options.read(true);
    #[cfg(windows)]
    {
        use std::os::windows::fs::OpenOptionsExt;
        options.share_mode(1);
    }
    let mut source = options.open(path)?;
    let before = source.metadata()?;
    let result = admission::inspect(&mut source, date, expected)?;
    let after = source.metadata()?;
    if before.len() != after.len() || before.modified().ok() != after.modified().ok() {
        return Err("Source changed while inspected".into());
    }
    let findings = |items: &[admission::Finding]| {
        items.iter().map(|f| serde_json::json!({"code":f.code,"range":f.range.map(|r|serde_json::json!({"offset":r.offset,"length":r.length}))})).collect::<Vec<_>>()
    };
    println!(
        "{}",
        serde_json::json!({
            "schemaVersion":1,"admissionRevision":admission::REVISION,"catalogRevision":admission::CATALOG_REVISION,
            "operation":"replace-existing-CMT2-DateTimeOriginal-ASCII20","field":result.field.map(|r|serde_json::json!({"offset":r.offset,"length":r.length})),
            "fieldShapeVerified":result.field_shape_verified,"expectedOccurrenceMatches":result.expected_occurrence_matches,
            "valueAlreadyMatches":result.value_already_matches,"knownStructures":findings(&result.known_structures),"refusals":findings(&result.refusals),
            "opaqueDependencyRegions":result.opaque_dependency_regions,"jpegMarkersExamined":result.jpeg_markers_examined,"bytesExamined":result.bytes_examined,
            "knownCatalogObservation":if result.known_structures.is_empty(){"no-match-in-inspected-locations"}else{"indicator-present"},
            "generalAuthenticityAbsenceEstablished":false,"cryptographicValidationPerformed":false,
            "productionMutationAllowed":result.production_mutation_allowed(),"artifactsCreated":false,
            "preservedIndependentFields":["OffsetTimeOriginal","SubSecTimeOriginal","DateTimeDigitized","container/timed date copies"],
            "remainingGates":["opaque structural/checksum dependencies","storage profile","production preview/apply integration"]
        })
    );
    Ok(())
}
