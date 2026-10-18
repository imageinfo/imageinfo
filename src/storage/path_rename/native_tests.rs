//! Retained authored markers only. Parent runs these native cells serially.
//! Actor processes own separate handles; no source handle is reopened by the plan.
use super::{PreparedRename, RenameObservation, RenamePlan, RenameState, StopReason};
use imageinfo_windows_storage::{FileSnapshot, GuardedSource, PrivateRoot};
use sha2::{Digest, Sha256};
use std::{
    fs::{self, File, FileTimes, OpenOptions},
    io::Write,
    os::windows::fs::OpenOptionsExt,
    path::{Path, PathBuf},
    process::{Child, Command, Stdio},
    thread,
    time::{Duration, Instant, SystemTime, UNIX_EPOCH},
};

const MARKER: &[u8] = b"authored 0201 original marker; never camera data\n";
const FOREIGN: &[u8] = b"independent 0201 foreign winner\n";
const OLD: &str = "Source.bin";
const NEW: &str = "SOURCE.BIN";
const TEMP: &str = "explicit-temporary.bin";

fn snapshot(path: &Path) -> FileSnapshot {
    GuardedSource::open(path, 4096).unwrap().snapshot().clone()
}

fn facts(snapshot: &FileSnapshot) -> serde_json::Value {
    serde_json::json!({
        "volume": snapshot.volume_serial_number, "identity": snapshot.file_index,
        "size": snapshot.size, "links": snapshot.links, "attributes": snapshot.attributes,
        "creation": snapshot.creation_time, "last_write": snapshot.last_write_time,
        "owner_dacl": snapshot.owner_dacl,
    })
}

struct Fixture {
    root: PathBuf,
    baseline: FileSnapshot,
}

impl Fixture {
    fn new(label: &str) -> Self {
        let base = std::env::var_os("IMAGEINFO_RENAME_201_EVIDENCE_ROOT")
            .map(PathBuf::from)
            .unwrap_or_else(|| {
                std::env::current_dir()
                    .unwrap()
                    .join(".local")
                    .join("native-201")
            });
        fs::create_dir_all(&base).unwrap();
        let nonce = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_nanos();
        let root = base.join(format!("{label}-{}-{nonce}", std::process::id()));
        let private = PrivateRoot::create(&root).unwrap();
        drop(private.create_artifact(OLD, MARKER, 4096).unwrap());
        drop(private);
        let baseline = snapshot(&root.join(OLD));
        fs::write(root.join("baseline.private.json"), serde_json::to_vec_pretty(&serde_json::json!({
            "source": OLD, "marker_sha256": format!("{:x}", Sha256::digest(MARKER)),
            "properties": facts(&baseline),
            "property_scope": "volume/file identity, bytes/size, link count, attributes, creation/last-write, owner/DACL; stream set checked by SDK",
        })).unwrap()).unwrap();
        Self { root, baseline }
    }

    fn plan(&self, case_only: bool) -> RenamePlan {
        RenamePlan::new(
            &self.root.join(OLD),
            &self.root.join(if case_only { NEW } else { "ordinary.bin" }),
            case_only.then(|| self.root.join(TEMP)).as_deref(),
        )
        .unwrap()
    }

    fn prepare(&self, case_only: bool) -> PreparedRename {
        PreparedRename::open(self.plan(case_only), &self.baseline).unwrap()
    }

    fn observation(&self, label: &str, observation: &RenameObservation) {
        fs::write(
            self.root.join(format!("{label}.private.txt")),
            format!("{observation:#?}\n"),
        )
        .unwrap();
    }

    /// A separate enumeration and fresh guarded observation after operation drop.
    /// Exact spellings matter: Path::exists aliases OLD and NEW on this volume.
    fn audit(&self, expected: &[(&str, &FileSnapshot, &[u8])], label: &str) {
        let mut all_names: Vec<String> = fs::read_dir(&self.root)
            .unwrap()
            .map(|e| e.unwrap().file_name().into_string().unwrap())
            .collect();
        all_names.sort();
        let names: Vec<String> = all_names
            .iter()
            .filter(|name| [OLD, NEW, TEMP, "ordinary.bin"].contains(&name.as_str()))
            .cloned()
            .collect();
        let mut wanted: Vec<String> = expected.iter().map(|(name, _, _)| (*name).into()).collect();
        wanted.sort();
        assert_eq!(names, wanted, "exact planned namespace map");
        let entries = expected
            .iter()
            .map(|(name, properties, bytes)| {
                let path = self.root.join(name);
                let observed = snapshot(&path);
                let actual = fs::read(&path).unwrap();
                assert_eq!(
                    &observed, *properties,
                    "identity and every inventoried property: {name}"
                );
                assert_eq!(actual, *bytes, "default-stream bytes: {name}");
                serde_json::json!({"name": name, "properties": facts(&observed),
                "sha256": format!("{:x}", Sha256::digest(&actual))})
            })
            .collect::<Vec<_>>();
        fs::write(self.root.join("independent-map-audit.private.json"), serde_json::to_vec_pretty(
            &serde_json::json!({"cell": label, "exact_names": names, "all_directory_names": all_names, "entries": entries,
                "audit": "fresh enumeration + GuardedSource snapshot + separate fs::read after plan drop",
                "limits": "no durability, receipt, restart custody, pair/cycle or production admission"})).unwrap()).unwrap();
    }
}

fn wait_for(path: &Path) {
    let start = Instant::now();
    while !path.exists() {
        assert!(
            start.elapsed() < Duration::from_secs(25),
            "actor handshake timeout: {}",
            path.display()
        );
        thread::sleep(Duration::from_millis(10));
    }
}

/// A child test process supplies an actor independent of the guarded caller.
struct Actor {
    child: Child,
    prefix: PathBuf,
}
impl Actor {
    fn start(fixture: &Fixture, mode: &str, target: &str) -> Self {
        let prefix = fixture.root.join(format!("actor-{mode}"));
        let log = File::create(prefix.with_extension("log.private.txt")).unwrap();
        let child = Command::new(std::env::current_exe().unwrap())
            .args([
                "--exact",
                "storage::path_rename::native_tests::native_actor_helper",
                "--ignored",
                "--nocapture",
            ])
            .env("IMAGEINFO_201_ACTOR_MODE", mode)
            .env("IMAGEINFO_201_ACTOR_TARGET", fixture.root.join(target))
            .env("IMAGEINFO_201_ACTOR_PREFIX", &prefix)
            .stdout(Stdio::from(log.try_clone().unwrap()))
            .stderr(Stdio::from(log))
            .spawn()
            .unwrap();
        let actor = Self { child, prefix };
        wait_for(&actor.prefix.with_extension("ready"));
        actor
    }
    fn act(&self) -> String {
        fs::write(self.prefix.with_extension("go"), b"go").unwrap();
        wait_for(&self.prefix.with_extension("done"));
        fs::read_to_string(self.prefix.with_extension("done")).unwrap()
    }
}
impl Drop for Actor {
    fn drop(&mut self) {
        let _ = fs::write(self.prefix.with_extension("release"), b"release");
        let _ = self.child.wait();
    }
}

#[test]
#[ignore = "child-process actor helper; only launched by a native 0201 cell"]
fn native_actor_helper() {
    let mode = std::env::var("IMAGEINFO_201_ACTOR_MODE").unwrap();
    let target = PathBuf::from(std::env::var_os("IMAGEINFO_201_ACTOR_TARGET").unwrap());
    let prefix = PathBuf::from(std::env::var_os("IMAGEINFO_201_ACTOR_PREFIX").unwrap());
    let held = match mode.as_str() {
        "writer" => Some(
            OpenOptions::new()
                .write(true)
                .share_mode(7)
                .open(&target)
                .unwrap(),
        ),
        "property" => Some(
            OpenOptions::new()
                .access_mode(0x100)
                .share_mode(7)
                .open(&target)
                .unwrap(),
        ),
        _ => None,
    };
    fs::write(prefix.with_extension("ready"), b"ready").unwrap();
    if mode != "writer" {
        wait_for(&prefix.with_extension("go"));
        let result = match mode.as_str() {
            "collision" => OpenOptions::new()
                .write(true)
                .create_new(true)
                .open(&target)
                .and_then(|mut file| file.write_all(FOREIGN)),
            "parent" => fs::rename(&target, target.with_extension("actor-moved")),
            "property" => held.as_ref().unwrap().set_times(
                FileTimes::new().set_modified(UNIX_EPOCH + Duration::from_secs(1_500_000_000)),
            ),
            _ => panic!("unknown actor mode"),
        };
        fs::write(
            prefix.with_extension("done"),
            if result.is_ok() { "ok" } else { "refused" },
        )
        .unwrap();
    }
    wait_for(&prefix.with_extension("release"));
    drop(held);
}

#[test]
fn native_01_ordinary_success() {
    let f = Fixture::new("01-ordinary");
    let mut operation = f.prepare(false);
    let result = operation.advance(false);
    f.observation("result", &result);
    assert_eq!(result.state, RenameState::Finished);
    assert_eq!(result.completed_steps, 1);
    drop(operation);
    f.audit(&[("ordinary.bin", &f.baseline, MARKER)], "ordinary success");
}

#[test]
fn native_02_case_only_success() {
    let f = Fixture::new("02-case-only");
    let mut operation = f.prepare(true);
    let first = operation.advance(false);
    f.observation("first", &first);
    assert_eq!(first.state, RenameState::AtTemporary);
    assert_eq!(first.completed_steps, 1);
    let result = operation.advance(false);
    f.observation("result", &result);
    assert_eq!(result.state, RenameState::Finished);
    assert_eq!(result.completed_steps, 2);
    drop(operation);
    f.audit(&[(NEW, &f.baseline, MARKER)], "case-only success");
}

#[test]
fn native_03_initial_temporary_collision() {
    let f = Fixture::new("03-initial-temp");
    let actor = Actor::start(&f, "collision", TEMP);
    assert_eq!(actor.act(), "ok");
    drop(actor);
    let foreign = snapshot(&f.root.join(TEMP));
    assert!(PreparedRename::open(f.plan(true), &f.baseline).is_err());
    f.audit(
        &[(OLD, &f.baseline, MARKER), (TEMP, &foreign, FOREIGN)],
        "initial temporary collision; no call",
    );
}

#[test]
fn native_04_late_temporary_collision() {
    let f = Fixture::new("04-late-temp");
    let mut operation = f.prepare(true);
    let actor = Actor::start(&f, "collision", TEMP);
    assert_eq!(actor.act(), "ok");
    drop(actor);
    let foreign = snapshot(&f.root.join(TEMP));
    let result = operation.advance(false);
    f.observation("result", &result);
    assert_eq!(result.state, RenameState::Stopped);
    assert_eq!(result.reason, Some(StopReason::NameMapChanged));
    assert_eq!(result.completed_steps, 0);
    drop(operation);
    f.audit(
        &[(OLD, &f.baseline, MARKER), (TEMP, &foreign, FOREIGN)],
        "late temporary collision",
    );
}

#[test]
fn native_05_final_foreign_winner() {
    let f = Fixture::new("05-final-winner");
    let mut operation = f.prepare(true);
    assert_eq!(operation.advance(false).state, RenameState::AtTemporary);
    let actor = Actor::start(&f, "collision", NEW);
    assert_eq!(actor.act(), "ok");
    drop(actor);
    let foreign = snapshot(&f.root.join(NEW));
    let result = operation.advance(false);
    f.observation("result", &result);
    assert_eq!(result.state, RenameState::Stopped);
    assert_eq!(result.reason, Some(StopReason::NameMapChanged));
    assert_eq!(result.completed_steps, 1);
    assert_eq!(operation.advance(false), result);
    drop(operation);
    f.audit(
        &[(TEMP, &f.baseline, MARKER), (NEW, &foreign, FOREIGN)],
        "final foreign winner; original retained at temporary",
    );
}

#[test]
fn native_06_preopened_writer() {
    let f = Fixture::new("06-preopened-writer");
    let actor = Actor::start(&f, "writer", OLD);
    assert!(PreparedRename::open(f.plan(true), &f.baseline).is_err());
    drop(actor);
    f.audit(
        &[(OLD, &f.baseline, MARKER)],
        "external preopened writer; no call",
    );
}

#[test]
fn native_07_parent_move() {
    let f = Fixture::new("07-parent-move");
    let mut operation = f.prepare(true);
    assert_eq!(operation.advance(false).state, RenameState::AtTemporary);
    let actor = Actor::start(&f, "parent", "");
    assert_eq!(actor.act(), "refused");
    drop(actor);
    let result = operation.advance(false);
    f.observation("result", &result);
    assert_eq!(result.state, RenameState::Finished);
    drop(operation);
    f.audit(
        &[(NEW, &f.baseline, MARKER)],
        "external parent move refused while same handle retained",
    );
}

#[test]
fn native_08_property_change() {
    let f = Fixture::new("08-property-change");
    let actor = Actor::start(&f, "property", OLD);
    let mut operation = f.prepare(true);
    assert_eq!(operation.advance(false).state, RenameState::AtTemporary);
    assert_eq!(actor.act(), "ok");
    let result = operation.advance(false);
    f.observation("result", &result);
    assert_eq!(result.state, RenameState::Stopped);
    assert_eq!(result.reason, Some(StopReason::CheckpointFailed));
    assert_eq!(result.completed_steps, 1);
    assert_eq!(operation.advance(false), result);
    drop(operation);
    drop(actor);
    let changed = snapshot(&f.root.join(TEMP));
    let mut expected = f.baseline.clone();
    assert_ne!(changed.last_write_time, expected.last_write_time);
    // Exact FILETIME corresponding to the actor's fixed UTC Unix timestamp.
    expected.last_write_time = 131_444_736_000_000_000;
    assert_eq!(changed, expected);
    f.audit(
        &[(TEMP, &expected, MARKER)],
        "external preopened property edit retained; no restoration",
    );
}

#[test]
fn native_09_cancellation_between_moves() {
    let f = Fixture::new("09-cancel");
    let mut operation = f.prepare(true);
    assert_eq!(operation.advance(false).state, RenameState::AtTemporary);
    let result = operation.advance(true);
    f.observation("result", &result);
    assert_eq!(result.state, RenameState::Stopped);
    assert_eq!(result.reason, Some(StopReason::Cancelled));
    assert_eq!(result.completed_steps, 1);
    assert_eq!(operation.advance(false), result);
    drop(operation);
    f.audit(
        &[(TEMP, &f.baseline, MARKER)],
        "cancel between moves; original temporary name retained",
    );
}

#[test]
fn native_10_unknown_response_between_moves() {
    let f = Fixture::new("10-unknown-response");
    let mut operation = f.prepare(true);
    // The actual first SDK move occurs, then its response is lost before the
    // planner classifies it or advances its confirmed prefix. This tests the
    // unknown-result branch; it is an injected caller/SDK boundary loss, not an
    // assertion that the Windows syscall itself returned an ambiguous error.
    operation.lose_next_response();
    let result = operation.advance(false);
    f.observation("result", &result);
    assert_eq!(result.state, RenameState::RecoveryRequired);
    assert_eq!(result.reason, Some(StopReason::UnknownResult));
    assert_eq!(result.completed_steps, 0);
    assert_eq!(operation.advance(false), result);
    drop(operation);
    f.audit(
        &[(TEMP, &f.baseline, MARKER)],
        "injected SDK response loss before planner classification; unknown history terminal; no replay",
    );
}
