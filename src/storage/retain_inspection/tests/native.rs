use super::*;
use imageinfo_windows_storage::{ExistingRoot, FileSnapshot, GuardedSource, PrivateRoot};
use std::{
    collections::BTreeMap,
    fs::{self, FileTimes, OpenOptions},
    io,
    os::windows::fs::{MetadataExt, OpenOptionsExt},
    path::PathBuf,
    process::Command,
    time::{Duration, SystemTime, UNIX_EPOCH},
};

const LEAVES: [&str; 3] = ["target.bin", "retained.bin", "staging.bin"];
const OLD: &[u8] = b"authored marker old\n";
const CANDIDATE: &[u8] = b"authored marker new\n";
const EXTRA: &str = "known-marker";

struct Fixture {
    evidence: PathBuf,
    root: PathBuf,
    expected: Expectation,
}

fn base() -> &'static Path {
    static BASE: std::sync::OnceLock<PathBuf> = std::sync::OnceLock::new();
    BASE.get_or_init(|| {
        let parent = std::env::var_os("IMAGEINFO_RETAIN_INSPECTION_EVIDENCE_ROOT")
            .map(PathBuf::from)
            .unwrap_or_else(|| {
                std::env::current_dir()
                    .unwrap()
                    .join(".local")
                    .join("retain-inspection")
            });
        fs::create_dir_all(&parent).unwrap();
        let session = parent.join(format!(
            "run-{}-{}",
            std::process::id(),
            SystemTime::now()
                .duration_since(UNIX_EPOCH)
                .unwrap()
                .as_nanos()
        ));
        fs::create_dir(&session).unwrap();
        session
    })
}

fn marker(path: &Path) -> ArtifactObservation {
    let held = GuardedSource::open(path, MAX_ARTIFACT_BYTES).unwrap();
    ArtifactObservation::observed(held.snapshot(), &fs::read(path).unwrap())
}

impl Fixture {
    fn new(label: &str, old: Option<usize>, candidate: Option<usize>) -> Self {
        let evidence = base().join(label);
        fs::create_dir(&evidence).unwrap();
        let root = evidence.join("root");
        drop(PrivateRoot::create(&root).unwrap());
        let original = |slot: Option<usize>, elsewhere, bytes| {
            let path = match slot {
                Some(index) => root.join(LEAVES[index]),
                None => evidence.join(elsewhere),
            };
            fs::write(&path, bytes).unwrap();
            marker(&path)
        };
        let expected = Expectation {
            schema: SCHEMA.into(),
            old: original(old, "old-elsewhere.bin", OLD),
            candidate: original(candidate, "candidate-elsewhere.bin", CANDIDATE),
        };
        Self {
            evidence,
            root,
            expected,
        }
    }

    fn path(&self, slot: usize) -> PathBuf {
        self.root.join(LEAVES[slot])
    }

    fn inspect(&self) -> Report {
        inspect(
            &self.root,
            LEAVES,
            &serde_json::to_vec(&self.expected).unwrap(),
        )
        .unwrap()
    }

    fn audit<T: serde::Serialize>(&self, report: impl FnOnce() -> T) -> T {
        self.audit_as("observation.private.json", report)
    }

    fn audit_as<T: serde::Serialize>(&self, file: &str, report: impl FnOnce() -> T) -> T {
        let before = self.inventory();
        let report = report();
        let after = self.inventory();
        let record = serde_json::json!({
            "expectation": self.expected,
            "report": report,
            "before": before.record(),
            "after": after.record(),
        });
        fs::write(
            self.evidence.join(file),
            serde_json::to_vec_pretty(&record).unwrap(),
        )
        .unwrap();
        assert_eq!(before, after);
        report
    }

    fn inventory(&self) -> Inventory {
        let held = ExistingRoot::open(&self.root).unwrap();
        let directories = [held.snapshot().clone(), held.parent_snapshot().clone()];
        let mut entries = BTreeMap::new();
        for entry in fs::read_dir(&self.root).unwrap() {
            let entry = entry.unwrap();
            let path = entry.path();
            let metadata = fs::symlink_metadata(&path).unwrap();
            let reparse = metadata.file_attributes() & 0x400 != 0;
            let regular = metadata.is_file() && !reparse;
            let identity = if reparse {
                const FILE_READ_ATTRIBUTES: u32 = 0x80;
                const OPEN_REPARSE_DIRECTORY: u32 = 0x0220_0000;
                let result = OpenOptions::new()
                    .access_mode(FILE_READ_ATTRIBUTES)
                    .share_mode(7)
                    .custom_flags(OPEN_REPARSE_DIRECTORY)
                    .open(&path)
                    .and_then(same_file::Handle::from_file);
                assert!(result.is_ok(), "authored reparse identity query failed");
                Some(readable(result))
            } else {
                regular.then(|| readable(same_file::Handle::from_path(&path)))
            };
            let bytes = regular.then(|| readable(fs::read(&path)));
            let snapshot = regular.then(|| {
                readable(
                    GuardedSource::open(&path, MAX_ARTIFACT_BYTES).map(|g| g.snapshot().clone()),
                )
            });
            let readable_refusal = matches!(bytes, Some(Ok(_))) && matches!(snapshot, Some(Err(_)));
            let independent_properties = readable_refusal.then(|| independent_properties(&path));
            let mut alternate = path.as_os_str().to_owned();
            alternate.push(format!(":{EXTRA}"));
            let alternate = regular.then(|| readable(fs::read(alternate)));
            let link_target = reparse.then(|| readable(fs::read_link(path)));
            entries.insert(
                entry.file_name(),
                Entry {
                    identity,
                    bytes,
                    snapshot,
                    independent_properties,
                    alternate,
                    link_target,
                    metadata: [
                        metadata.len(),
                        u64::from(metadata.file_attributes()),
                        metadata.creation_time(),
                        metadata.last_write_time(),
                    ],
                },
            );
        }
        Inventory {
            directories,
            entries,
        }
    }
}

type Available<T> = Result<T, (io::ErrorKind, Option<i32>)>;

fn readable<T>(result: io::Result<T>) -> Available<T> {
    result.map_err(|error| (error.kind(), error.raw_os_error()))
}

#[derive(Debug, Eq, PartialEq)]
struct IndependentProperties {
    owner_dacl: String,
    hard_links: Vec<Vec<u8>>,
}

fn independent_properties(path: &Path) -> IndependentProperties {
    // The SDK's supported-property snapshot is intentionally unavailable on
    // these readable refusals. Query the authored artifact through separate
    // read-only Windows commands and compare the ACL and complete hard-link
    // listing across inspection, without modifying the fixture for access.
    let security = Command::new("powershell.exe")
        .args([
            "-NoLogo",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            "$ErrorActionPreference = 'Stop'; [IO.File]::GetAccessControl($env:IMAGEINFO_INSPECTION_AUDIT_FILE).Sddl",
        ])
        .env("IMAGEINFO_INSPECTION_AUDIT_FILE", path)
        .output()
        .unwrap();
    assert!(
        security.status.success(),
        "authored ACL query failed: {}",
        String::from_utf8_lossy(&security.stderr)
    );
    let owner_dacl = String::from_utf8(security.stdout)
        .unwrap()
        .trim()
        .to_owned();
    assert!(owner_dacl.starts_with("O:") && owner_dacl.contains("D:"));
    let links = Command::new("fsutil.exe")
        .args(["hardlink", "list"])
        .arg(path)
        .output()
        .unwrap();
    assert!(links.status.success(), "authored hard-link query failed");
    let mut hard_links: Vec<_> = links
        .stdout
        .split(|&byte| byte == b'\n')
        .filter(|line| !line.is_empty())
        .map(|line| line.strip_suffix(b"\r").unwrap_or(line).to_vec())
        .collect();
    hard_links.sort();
    assert!(!hard_links.is_empty() && hard_links.iter().all(|link| link.starts_with(b"\\")));
    IndependentProperties {
        owner_dacl,
        hard_links,
    }
}

#[derive(Debug, Eq, PartialEq)]
struct Entry {
    identity: Option<Available<same_file::Handle>>,
    bytes: Option<Available<Vec<u8>>>,
    snapshot: Option<Available<FileSnapshot>>,
    independent_properties: Option<IndependentProperties>,
    alternate: Option<Available<Vec<u8>>>,
    link_target: Option<Available<PathBuf>>,
    metadata: [u64; 4],
}

#[derive(Debug, Eq, PartialEq)]
struct Inventory {
    directories: [FileSnapshot; 2],
    entries: BTreeMap<OsString, Entry>,
}

impl Inventory {
    fn record(&self) -> serde_json::Value {
        // The live equality check above compares independently opened physical
        // handles. Debug preserves the independently queried handle identities,
        // declared properties, available streams and bounded authored bytes.
        serde_json::json!(format!("{self:#?}"))
    }
}

fn assert_slot(
    report: &Report,
    slot: usize,
    association: Association,
    expected: &ArtifactObservation,
) {
    assert_eq!(
        report.slots[slot],
        SlotObservation::Present {
            artifact: expected.clone(),
            association
        }
    );
}

#[test]
fn exact_prefixes_and_unexpected_name_preserve_native_fixtures() {
    for (label, old, candidate, missing, layout) in [
        ("before", 0, 2, 1, Disposition::OldNotMoved),
        ("between", 1, 2, 0, Disposition::OldRetainedCandidateStaged),
        ("installed", 1, 0, 2, Disposition::InstalledLayoutObserved),
    ] {
        let f = Fixture::new(label, Some(old), Some(candidate));
        let unexpected = ["extra-a", "extra-b", "extra-c", "extra-d"];
        for name in unexpected {
            fs::write(f.root.join(name), b"unselected marker").unwrap();
        }
        let report = f.audit(|| f.inspect());
        assert_eq!(report.disposition, layout);
        assert_eq!(report.slots[missing], SlotObservation::Missing);
        assert_eq!(
            report.unexpected_entries,
            Some(unexpected.map(OsString::from).to_vec())
        );
        assert_slot(&report, old, Association::Match(Role::Old), &f.expected.old);
        assert_slot(
            &report,
            candidate,
            Association::Match(Role::Candidate),
            &f.expected.candidate,
        );
    }
}

#[test]
fn later_foreign_target_is_never_associated_from_bytes() {
    for (label, bytes, same) in [
        ("foreign", b"authored foreign\n".as_slice(), false),
        ("same-byte-foreign", CANDIDATE, true),
    ] {
        let f = Fixture::new(label, Some(1), Some(2));
        fs::write(f.path(0), bytes).unwrap();
        let actual = marker(&f.path(0));
        let report = f.audit(|| f.inspect());
        assert_eq!(report.disposition, Disposition::ForeignCurrentTarget);
        assert_slot(
            &report,
            0,
            Association::Foreign {
                same_bytes_as_old: false,
                same_bytes_as_candidate: same,
            },
            &actual,
        );
        assert_slot(&report, 1, Association::Match(Role::Old), &f.expected.old);
        assert_slot(
            &report,
            2,
            Association::Match(Role::Candidate),
            &f.expected.candidate,
        );
    }
}

#[test]
fn proven_foreign_target_survives_missing_staging_but_staging_conflicts_remain_uncertain() {
    for (label, staging) in [
        ("foreign-missing-staging", None),
        ("foreign-contradictory-staging", Some(false)),
        ("foreign-inaccessible-staging", Some(true)),
    ] {
        let f = Fixture::new(label, Some(1), staging.map(|_| 2));
        fs::write(f.path(0), OLD).unwrap();
        let target = marker(&f.path(0));
        let _lock = match staging {
            Some(false) => {
                fs::write(f.path(2), OLD).unwrap();
                None
            }
            Some(true) => Some(
                OpenOptions::new()
                    .read(true)
                    .share_mode(0)
                    .open(f.path(2))
                    .unwrap(),
            ),
            None => None,
        };
        let report = f.audit(|| f.inspect());
        assert_slot(
            &report,
            0,
            Association::Foreign {
                same_bytes_as_old: true,
                same_bytes_as_candidate: false,
            },
            &target,
        );
        assert_slot(&report, 1, Association::Match(Role::Old), &f.expected.old);
        match staging {
            None => {
                assert_eq!(report.disposition, Disposition::ForeignCurrentTarget);
                assert_eq!(report.slots[2], SlotObservation::Missing);
            }
            Some(false) => {
                assert_eq!(report.disposition, Disposition::IncompleteOrUncertain);
                assert!(matches!(
                    report.slots[2],
                    SlotObservation::Present {
                        association: Association::Mismatch {
                            role: Role::Candidate,
                            sha256_matches: false,
                            ..
                        },
                        ..
                    }
                ));
            }
            Some(true) => {
                assert_eq!(report.disposition, Disposition::IncompleteOrUncertain);
                assert_eq!(
                    report.slots[2],
                    SlotObservation::Unavailable(Issue::Inaccessible)
                );
            }
        }
    }
}

#[test]
fn missing_and_swapped_expectations_are_incomplete() {
    for (label, old, candidate, missing) in [
        ("old-missing", None, Some(2), 1),
        ("candidate-missing", Some(1), None, 2),
    ] {
        let f = Fixture::new(label, old, candidate);
        let report = f.audit(|| f.inspect());
        assert_eq!(report.disposition, Disposition::IncompleteOrUncertain);
        assert_eq!(report.slots[missing], SlotObservation::Missing);
    }
    let mut f = Fixture::new("swapped", Some(0), Some(2));
    std::mem::swap(&mut f.expected.old, &mut f.expected.candidate);
    let report = f.audit(|| f.inspect());
    assert_eq!(report.disposition, Disposition::IncompleteOrUncertain);
    assert_slot(
        &report,
        0,
        Association::Match(Role::Candidate),
        &f.expected.candidate,
    );
    let mut f = Fixture::new("duplicated", Some(0), Some(2));
    f.expected.old = f.expected.candidate.clone();
    let result = f
        .audit(|| inspect(&f.root, LEAVES, &serde_json::to_vec(&f.expected).unwrap()).unwrap_err());
    assert_eq!(result, Refusal::ContradictoryExpectation);
}

#[test]
fn unsupported_stream_link_reparse_case_and_property_are_explicit() {
    let f = Fixture::new("stream", Some(0), Some(2));
    let mut stream = f.path(2).into_os_string();
    stream.push(format!(":{EXTRA}"));
    fs::write(stream, b"authored extra stream").unwrap();
    assert_unsupported(&f, 2);

    let f = Fixture::new("link", Some(0), Some(2));
    fs::hard_link(f.path(2), f.root.join("candidate-link.bin")).unwrap();
    let before = f.inventory();
    assert_eq!(
        before.entries[&OsString::from("candidate-link.bin")].identity,
        before.entries[&OsString::from(LEAVES[2])].identity
    );
    assert_eq!(
        before.entries[&OsString::from(LEAVES[2])]
            .independent_properties
            .as_ref()
            .unwrap()
            .hard_links
            .len(),
        2
    );
    assert_unsupported(&f, 2);

    let f = Fixture::new("case", Some(0), None);
    fs::write(f.root.join("Staging.bin"), CANDIDATE).unwrap();
    assert_unsupported(&f, 2);

    let f = Fixture::new("reparse", Some(0), None);
    let decoy = f.evidence.join("junction-target");
    fs::create_dir(&decoy).unwrap();
    fs::write(decoy.join("marker.bin"), CANDIDATE).unwrap();
    let status = Command::new("cmd.exe")
        .args(["/d", "/c", "mklink", "/J"])
        .arg(f.path(2))
        .arg(decoy)
        .output()
        .unwrap();
    assert!(
        status.status.success(),
        "authored junction fixture could not be created"
    );
    assert_unsupported(&f, 2);

    let f = Fixture::new("hidden", Some(0), Some(2));
    assert!(
        Command::new("attrib.exe")
            .arg("+H")
            .arg(f.path(2))
            .output()
            .unwrap()
            .status
            .success()
    );
    assert_unsupported(&f, 2);
}

fn assert_unsupported(f: &Fixture, slot: usize) {
    let report = f.audit(|| f.inspect());
    assert_eq!(report.disposition, Disposition::IncompleteOrUncertain);
    assert_eq!(
        report.slots[slot],
        SlotObservation::Unavailable(Issue::Unsupported)
    );
}

#[test]
fn inaccessible_and_conflicting_read_are_distinct_from_absence() {
    let f = Fixture::new("inaccessible", Some(0), Some(2));
    let locked = OpenOptions::new()
        .read(true)
        .share_mode(0)
        .open(f.path(2))
        .unwrap();
    let report = f.audit(|| f.inspect());
    assert_eq!(report.disposition, Disposition::IncompleteOrUncertain);
    assert_eq!(
        report.slots[2],
        SlotObservation::Unavailable(Issue::Inaccessible)
    );
    drop(locked);

    let f = Fixture::new("binding-conflict", Some(0), Some(2));
    let inspector = native::Inspection::collect(&f.root, LEAVES).unwrap();
    fs::write(f.path(1), OLD).unwrap();
    let report = f.audit(|| inspector.finish(&f.expected));
    assert_eq!(report.disposition, Disposition::IncompleteOrUncertain);
    assert_eq!(
        report.slots[1],
        SlotObservation::Unavailable(Issue::Conflict)
    );
    assert_eq!(report.root_issue, Some(Issue::Conflict));
    assert_eq!(report.unexpected_entries, None);

    let f = Fixture::new("read-conflict", Some(0), Some(2));
    let inspector = native::Inspection::collect(&f.root, LEAVES).unwrap();
    set_write_time(&f.path(2));
    let report = f.audit(|| inspector.finish(&f.expected));
    assert_eq!(report.disposition, Disposition::IncompleteOrUncertain);
    assert_eq!(
        report.slots[2],
        SlotObservation::Unavailable(Issue::Conflict)
    );
    assert_eq!(report.root_issue, None);
    assert_slot(&report, 0, Association::Match(Role::Old), &f.expected.old);
}

fn set_write_time(path: &Path) {
    OpenOptions::new()
        .access_mode(0x100)
        .share_mode(7)
        .open(path)
        .unwrap()
        .set_times(FileTimes::new().set_modified(UNIX_EPOCH + Duration::from_secs(1_000_000_000)))
        .unwrap();
}

#[test]
fn actual_changed_bytes_and_properties_remain_visible_as_mismatches() {
    let f = Fixture::new("changed-bytes", Some(0), Some(2));
    fs::write(f.path(2), OLD).unwrap();
    let actual = marker(&f.path(2));
    let report = f.audit(|| f.inspect());
    assert_eq!(report.disposition, Disposition::IncompleteOrUncertain);
    assert_slot(
        &report,
        2,
        Association::Mismatch {
            role: Role::Candidate,
            snapshot_matches: actual.snapshot == f.expected.candidate.snapshot,
            sha256_matches: false,
        },
        &actual,
    );

    let f = Fixture::new("changed-property", Some(0), Some(2));
    set_write_time(&f.path(2));
    let actual = marker(&f.path(2));
    let report = f.audit(|| f.inspect());
    assert_eq!(report.disposition, Disposition::IncompleteOrUncertain);
    assert_slot(
        &report,
        2,
        Association::Mismatch {
            role: Role::Candidate,
            snapshot_matches: false,
            sha256_matches: true,
        },
        &actual,
    );
}

#[test]
fn actual_listing_accepts_4096_entries_and_refuses_the_next() {
    let f = Fixture::new("root-entry-bound", Some(0), Some(2));
    for index in 2..MAX_ROOT_ENTRIES {
        fs::create_dir(f.root.join(format!("extra-{index:04}"))).unwrap();
    }
    let report = f.audit(|| f.inspect());
    assert_eq!(report.disposition, Disposition::OldNotMoved);
    assert_eq!(
        report.unexpected_entries.unwrap().len(),
        MAX_ROOT_ENTRIES - 2
    );

    fs::create_dir(f.root.join("extra-overflow")).unwrap();
    let result = f.audit_as("overflow.private.json", || {
        inspect(&f.root, LEAVES, &serde_json::to_vec(&f.expected).unwrap()).unwrap_err()
    });
    assert_eq!(result, Refusal::Root(Issue::EntryBound));
}
