use imageinfo_privacy_coverage_research::{MAX_RAW_BYTES, inspect};
use std::{ffi::OsStr, fs::File, io::Read, path::Path, process::ExitCode};

fn read(path: &OsStr, limit: usize) -> Result<Vec<u8>, &'static str> {
    let file = File::open(Path::new(path)).map_err(|_| "INPUT_IO")?;
    if !file.metadata().map_err(|_| "INPUT_IO")?.is_file() {
        return Err("INPUT_NOT_FILE");
    }
    let mut bytes = Vec::new();
    file.take(limit as u64 + 1)
        .read_to_end(&mut bytes)
        .map_err(|_| "INPUT_IO")?;
    if bytes.len() > limit {
        return Err("INPUT_LIMIT");
    }
    Ok(bytes)
}
fn run() -> Result<(), &'static str> {
    let args: Vec<_> = std::env::args_os().skip(1).collect();
    let (raw_path, sidecar_path) = match args.as_slice() {
        [raw] => (raw.as_os_str(), None),
        [raw, flag, sidecar] if flag == OsStr::new("--sidecar") => {
            (raw.as_os_str(), Some(sidecar.as_os_str()))
        }
        _ => return Err("USAGE: imageinfo-privacy-coverage-research RAW [--sidecar XMP]"),
    };
    let raw = read(raw_path, MAX_RAW_BYTES)?;
    let sidecar = sidecar_path.map(|path| read(path, 65_536)).transpose()?;
    let report = inspect(&raw, sidecar.as_deref()).map_err(|_| "COVERAGE_REFUSED")?;
    serde_json::to_writer_pretty(std::io::stdout().lock(), &report).map_err(|_| "REPORT_IO")?;
    Ok(())
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
