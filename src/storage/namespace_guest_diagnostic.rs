//! Explicit #0219 disposable-guest entry, retaining the raw #0218 observer.
//! Environment choices are current-parent assertions, not authenticated custody
//! or proof of a guest/NTFS/nonboot disk. The separately reviewed bootstrap must
//! observe that actual disk correlation before the parent launches this entry.

use super::namespace_diagnostic::{authored_marker_fixture, run_authored_observer};
use std::io;
use std::os::windows::fs::MetadataExt;
use std::path::{Path, PathBuf};

const APPROVAL: &str = "explicit-parent-disposable-guest-v1";
const MARKER: &[u8] = b"imageinfo-0219-disposable-authored-only-v1\n";

fn token(value: &str) -> bool {
    !value.is_empty()
        && value.len() <= 64
        && value
            .bytes()
            .all(|b| b.is_ascii_alphanumeric() || matches!(b, b'_' | b'-'))
}

fn drive(value: &str) -> bool {
    let b = value.as_bytes();
    b.len() == 2 && b[0].is_ascii_uppercase() && b[1] == b':'
}

fn device_component(value: &str) -> bool {
    let upper = value.to_ascii_uppercase();
    matches!(upper.as_str(), "CON" | "PRN" | "AUX" | "NUL" | "CLOCK$")
        || ((upper.starts_with("COM") || upper.starts_with("LPT"))
            && upper.len() == 4
            && upper.as_bytes()[3].is_ascii_digit())
}

/// Pure lexical admission. Exact canonical path/ancestor checks follow before
/// any marker/source access. This intentionally admits only narrow ASCII paths.
fn selection(
    root: &str,
    selected: &str,
    system: &str,
    approval: &str,
    unit: &str,
) -> io::Result<()> {
    if approval != APPROVAL
        || !token(unit)
        || !drive(selected)
        || !drive(&system.to_ascii_uppercase())
        || selected.eq_ignore_ascii_case(system)
        || root.len() > 240
        || !root.starts_with(&format!("{selected}\\"))
    {
        return Err(io::Error::other(
            "GUEST_EXPLICIT_NON_SYSTEM_SELECTION_REQUIRED",
        ));
    }
    let relative = &root[3..];
    if relative
        .split('\\')
        .any(|part| !token(part) || device_component(part))
    {
        return Err(io::Error::other("GUEST_EXACT_CASE_PATH_REQUIRED"));
    }
    Ok(())
}

fn exact_canonical(requested: &Path, actual: &Path) -> bool {
    actual.to_str().and_then(|s| s.strip_prefix("\\\\?\\")) == requested.to_str()
}

fn guest_fixture(path: &Path, selected: &str) -> io::Result<()> {
    // Inspect each lexical ancestor and its canonical result. A reparse point,
    // SUBST-style alias or different path spelling is refused. These are
    // boundary observations; this does not promise continuing path exclusion.
    let mut current = PathBuf::from(format!("{selected}\\"));
    let inspect = |candidate: &Path| -> io::Result<()> {
        let meta = std::fs::symlink_metadata(candidate)?;
        if !meta.is_dir()
            || meta.file_attributes() & 0x400 != 0
            || !exact_canonical(candidate, &std::fs::canonicalize(candidate)?)
        {
            return Err(io::Error::other("GUEST_ALIAS_OR_REPARSE_REFUSED"));
        }
        Ok(())
    };
    inspect(&current)?;
    for part in path.to_str().expect("validated ASCII path")[3..].split('\\') {
        current.push(part);
        inspect(&current)?;
    }
    authored_marker_fixture(path, "fixture219.marker", MARKER)
}

#[test]
#[ignore = "requires exact independently reviewed #0219 disposable-guest plan and owning parent"]
fn guest_namespace_diagnostic_worker() {
    let root = std::env::var("IMAGEINFO_219_ROOT").expect("explicit case root required");
    let unit = std::env::var("IMAGEINFO_219_UNIT").expect("explicit attempt identity required");
    let selected =
        std::env::var("IMAGEINFO_219_GUEST_DRIVE").expect("explicit guest drive required");
    let system = std::env::var("SystemDrive").expect("actual system drive environment required");
    let approval =
        std::env::var("IMAGEINFO_219_GUEST_APPROVAL").expect("explicit parent choice required");
    selection(&root, &selected, &system, &approval, &unit)
        .expect("exact current-parent selection required");
    let path = Path::new(&root);
    guest_fixture(path, &selected).expect("exact fresh guest authored fixture required");
    run_authored_observer(
        path,
        unit,
        "219-authored-namespace-guest-diagnostic",
        "219-authored-v1",
    );
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn selected_case_is_narrow_and_parent_explicit() {
        assert!(
            selection(
                "E:\\case-219\\persistent-write-error",
                "E:",
                "C:",
                APPROVAL,
                "try_1"
            )
            .is_ok()
        );
        for (root, selected, system, approval, unit) in [
            ("E:\\case", "E:", "E:", APPROVAL, "try1"),
            ("E:\\case", "E:", "e:", APPROVAL, "try1"),
            ("E:\\case", "E:", "", APPROVAL, "try1"),
            ("E:\\case", "E:", "C:", "", "try1"),
            ("E:\\case", "E:", "C:", APPROVAL, "../try1"),
            ("E:\\case", "e:", "C:", APPROVAL, "try1"),
            ("F:\\case", "E:", "C:", APPROVAL, "try1"),
        ] {
            assert!(selection(root, selected, system, approval, unit).is_err());
        }
    }

    #[test]
    fn roots_and_lexical_aliases_are_refused_before_io() {
        for root in [
            "E:\\",
            "E:case",
            "E:/case",
            "\\\\server\\share",
            "\\\\?\\E:\\case",
            "E:\\case\\..\\other",
            "E:\\case\\.",
            "E:\\case\\",
            "E:\\case ",
            "E:\\case.",
            "E:\\case:stream",
            "E:\\NUL",
            "E:\\com1",
            "E:\\LPT9",
            "E:\\café",
        ] {
            assert!(
                selection(root, "E:", "C:", APPROVAL, "try1").is_err(),
                "{root}"
            );
        }
    }

    #[test]
    fn canonical_spelling_must_match_exact_selected_name() {
        assert!(exact_canonical(
            Path::new("E:\\case"),
            Path::new("\\\\?\\E:\\case")
        ));
        for actual in [
            "\\\\?\\C:\\case",
            "\\\\?\\E:\\Case",
            "\\\\?\\E:\\different",
            "\\\\?\\UNC\\host\\case",
            "E:\\case",
        ] {
            assert!(!exact_canonical(Path::new("E:\\case"), Path::new(actual)));
        }
    }
}
