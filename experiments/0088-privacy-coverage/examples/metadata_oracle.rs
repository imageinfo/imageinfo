//! Same-parser structural observations for independent private classification.
//! This does not independently parse the format or certify privacy/absence.
use imageinfo::reader::{self, Limits};
use serde_json::json;
use std::{fs::File, path::Path, process::ExitCode};

fn run() -> Result<(), &'static str> {
    let args: Vec<_> = std::env::args_os().skip(1).collect();
    let [path] = args.as_slice() else {
        return Err("USAGE: metadata_oracle RAW");
    };
    let input = File::open(path).map_err(|_| "INPUT_IO")?;
    let before = input.metadata().map_err(|_| "INPUT_IO")?;
    if !before.is_file() || before.len() > 256 * 1024 * 1024 {
        return Err("INPUT_LIMIT_OR_KIND");
    }
    drop(input);
    let metadata =
        reader::read_file(Path::new(path), Limits::default()).map_err(|_| "READER_REFUSED")?;
    let previews: Vec<_> = metadata
        .previews
        .iter()
        .map(|preview| {
            json!({"name":preview.name,"offset":preview.range.offset,
                   "length":preview.range.length,"path":preview.path})
        })
        .collect();
    let opaque: Vec<_> = metadata
        .opaque
        .iter()
        .map(|(range, path)| json!({"offset":range.offset,"length":range.length,"path":path}))
        .collect();
    serde_json::to_writer(
        std::io::stdout().lock(),
        &json!({"schemaVersion":1,"basis":"same-root-reader-independent-classification-only",
                "sourceLength":metadata.length,"declaredPreviews":previews,"opaqueRegions":opaque}),
    )
    .map_err(|_| "OUTPUT_IO")
}

fn main() -> ExitCode {
    match run() {
        Ok(()) => ExitCode::SUCCESS,
        Err(code) => {
            eprintln!("{code}");
            ExitCode::from(1)
        }
    }
}
