//! #0022's actual OD-11 live marker sequence; ordinary owner policy throughout.
use crate::{
    inspection_record::{Info, MAX_RECORD},
    native::{self, PrivateSecurity},
    ordinary_record::{self, PersistenceMode, Record},
    restart_context::{self, Context, OwnedRecord, RecordName, Stage},
};
use imageinfo_recovery_probe::digest;
use serde_json::{Value, json};
use std::{
    error::Error,
    fs::{self, File, OpenOptions},
    io::{self, BufRead, Read, Seek, SeekFrom, Write},
    os::windows::fs::{MetadataExt, OpenOptionsExt},
    path::Path,
};
type Result<T> = std::result::Result<T, Box<dyn Error>>;
const SOURCE: &str = "source.marker";
const CANDIDATE: &str = "candidate.marker";
const OUTPUT: &str = "output.marker";
const RECORDS: [(&str, &str); 3] = [
    ("prepared.record", "prepared"),
    ("intent.record", "publication-intent"),
    ("observation.record", "recovery-required"),
];
fn info(file: &File) -> Result<Info> {
    let v = winapi_util::file::information(file)?;
    Ok(Info {
        identity: format!("{:x}:{:x}", v.volume_serial_number(), v.file_index()),
        size: v.file_size(),
        links: v.number_of_links().try_into()?,
        attributes: v.file_attributes().try_into()?,
        creation_time: file.metadata()?.creation_time(),
        last_write_time: v.last_write_time().ok_or("MTIME_UNAVAILABLE")?,
    })
}
fn emit(mut value: Value) -> Result<()> {
    for key in [
        "committed",
        "namespaceAcknowledged",
        "productionPublicationAllowed",
        "repairAllowed",
    ] {
        value[key] = json!(false);
    }
    println!("{value}");
    io::stdout().flush()?;
    Ok(())
}
fn barrier(name: &str) -> Result<()> {
    emit(json!({"barrier":name}))?;
    let mut line = String::new();
    io::stdin().lock().take(32).read_line(&mut line)?;
    match line.as_str() {
        "continue\n" | "continue\r\n" => Ok(()),
        "cancel\n" | "cancel\r\n" => Err("CONTROL_CANCEL".into()),
        "fail\n" | "fail\r\n" => Err("INJECTED_PROTOCOL_FAILURE".into()),
        _ => Err("CONTROL_INVALID".into()),
    }
}
fn read(file: &mut File) -> Result<Vec<u8>> {
    if file.metadata()?.len() > MAX_RECORD {
        return Err("ARTIFACT_SIZE_BOUND".into());
    }
    file.seek(SeekFrom::Start(0))?;
    let mut bytes = Vec::new();
    file.take(MAX_RECORD + 1).read_to_end(&mut bytes)?;
    if bytes.len() as u64 > MAX_RECORD {
        return Err("ARTIFACT_SIZE_BOUND".into());
    }
    Ok(bytes)
}
fn binding(path: &Path, file: &File) -> Result<()> {
    let observed = OpenOptions::new()
        .access_mode(0x20080)
        .share_mode(7)
        .custom_flags(0x02200000)
        .open(path)?;
    if info(&observed)?.identity != info(file)?.identity {
        return Err("PATH_BINDING_CHANGED".into());
    }
    Ok(())
}
fn directory(root: &Path, held: &File, before: &Info, security: &PrivateSecurity) -> Result<()> {
    security.check(held)?;
    binding(root, held)?;
    let now = info(held)?;
    if now.identity != before.identity
        || now.creation_time != before.creation_time
        || now.attributes & !32 != before.attributes & !32
        || now.attributes & 0x410 != 0x10
    {
        return Err("ROOT_PROPERTIES_CHANGED".into());
    }
    Ok(())
}
struct Artifact {
    file: File,
    before: Info,
    hash: String,
    name: &'static str,
    persistence: PersistenceMode,
}
impl Artifact {
    fn create(
        root: &Path,
        name: &'static str,
        security: &PrivateSecurity,
        bytes: &[u8],
    ) -> Result<Self> {
        Self::create_with_mode(root, name, security, bytes, PersistenceMode::Buffered)
    }
    fn create_with_mode(
        root: &Path,
        name: &'static str,
        security: &PrivateSecurity,
        bytes: &[u8],
        persistence: PersistenceMode,
    ) -> Result<Self> {
        let mut file = if persistence == PersistenceMode::WriteThrough {
            security.create_write_through_file(&root.join(name))?
        } else {
            security.create_file(&root.join(name))?
        };
        crate::staging::copy_exact(
            &mut std::io::Cursor::new(bytes),
            &mut file,
            bytes.len() as u64,
        )?;
        file.sync_all()?;
        let before = info(&file)?;
        Ok(Self {
            file,
            before,
            hash: digest(bytes),
            name,
            persistence,
        })
    }
    fn check(&mut self, root: &Path, security: &PrivateSecurity) -> Result<()> {
        security.check(&self.file)?;
        native::check_streams(&self.file)?;
        binding(&root.join(self.name), &self.file)?;
        let now = info(&self.file)?;
        if now != self.before || now.links != 1 || now.attributes & 0x410 != 0 {
            return Err("FILE_PROPERTIES_CHANGED".into());
        }
        if digest(&read(&mut self.file)?) != self.hash || info(&self.file)? != now {
            return Err("FILE_CONTENT_OR_PROPERTIES_CHANGED".into());
        }
        Ok(())
    }
}
fn open_source(root: &Path, security: &PrivateSecurity) -> Result<Artifact> {
    let mut file = OpenOptions::new()
        .access_mode(0x80020000)
        .share_mode(1)
        .custom_flags(0x02200000)
        .open(root.join(SOURCE))?;
    security.check(&file)?;
    native::check_streams(&file)?;
    let before = info(&file)?;
    let bytes = read(&mut file)?;
    if bytes != vec![b'3'; 65536] || before.links != 1 || before.attributes & 0x410 != 0 {
        return Err("OWNED_MARKER_SOURCE_UNVERIFIED".into());
    }
    Ok(Artifact {
        file,
        before,
        hash: digest(&bytes),
        name: SOURCE,
        persistence: PersistenceMode::Buffered,
    })
}
fn save(
    root: &Path,
    security: &PrivateSecurity,
    name: &'static str,
    phase: &str,
    dir: &Info,
    source: &Artifact,
    candidate: &Artifact,
) -> Result<Artifact> {
    let record = Record {
        purpose: "imageinfo-od11-marker-v1".into(),
        phase: phase.into(),
        target: OUTPUT.into(),
        expected_absence: true,
        observation_only: true,
        committed: false,
        namespace_acknowledged: false,
        root: dir.clone(),
        source: source.before.clone(),
        candidate: candidate.before.clone(),
        sha256: source.hash.clone(),
        persistence_mode: candidate.persistence,
    };
    let wire = ordinary_record::encode(&record)?;
    if wire.len() > MAX_RECORD as usize {
        return Err("RECORD_SIZE_BOUND".into());
    }
    Artifact::create_with_mode(root, name, security, &wire, candidate.persistence)
}
fn export_context(stage: Stage, dir: &Info, source: &Artifact, owned: &[Artifact]) -> Result<()> {
    export_held_context(stage, dir, source, &owned[0], &owned[1..])
}
fn export_held_context(
    stage: Stage,
    dir: &Info,
    source: &Artifact,
    candidate: &Artifact,
    records: &[Artifact],
) -> Result<()> {
    let names = [
        RecordName::Prepared,
        RecordName::Intent,
        RecordName::Observation,
    ];
    let context = Context {
        purpose: "imageinfo-od11-caller-context-v1".into(),
        stage,
        stopped_before_publication: false,
        root: dir.clone(),
        source: source.before.clone(),
        candidate: candidate.before.clone(),
        sha256: source.hash.clone(),
        persistence_mode: candidate.persistence,
        records: records
            .iter()
            .zip(names)
            .map(|(a, name)| OwnedRecord {
                name,
                info: a.before.clone(),
                sha256: a.hash.clone(),
            })
            .collect(),
    };
    // The supervisor retains this outside the editable transaction. A later
    // record or checksum cannot recreate the caller's authorization/history.
    emit(json!({"callerContext":context,"observationOnly":true}))
}
fn prepare(root: &Path) -> Result<()> {
    let ancestors = crate::windows::ancestors(root.parent().ok_or("PARENT_REQUIRED")?)?;
    let parent = ancestors.last().ok_or("PARENT_REQUIRED")?;
    if native::filesystem(parent)? != "NTFS" {
        return Err("FILESYSTEM_UNVERIFIED".into());
    }
    let security = PrivateSecurity::current()?;
    let dir = security.create_directory(
        parent,
        Path::new(root.file_name().ok_or("ROOT_LEAF_REQUIRED")?),
    )?;
    let _source = Artifact::create(root, SOURCE, &security, &vec![b'3'; 65536])?;
    dir.sync_all()?;
    emit(json!({"outcome":"owned-source-prepared","rootRetained":true}))
}
fn retained_work(root: &Path) -> bool {
    fs::read_dir(root)
        .map(|entries| {
            for entry in entries {
                match entry {
                    Ok(entry) if entry.file_name() == SOURCE => {}
                    _ => return true,
                }
            }
            false
        })
        .unwrap_or(true)
}
fn live(
    root: &Path,
    source_fault: &str,
    persistence: PersistenceMode,
    checkpoints: bool,
) -> Result<()> {
    crate::staging::check_budget(&[65536, MAX_RECORD, MAX_RECORD, MAX_RECORD], 262144)?;
    let _ancestors = crate::windows::ancestors(root.parent().ok_or("PARENT_REQUIRED")?)?;
    let security = PrivateSecurity::current()?;
    let dir = OpenOptions::new()
        .access_mode(0xc0020000)
        .share_mode(3)
        .custom_flags(0x02200000)
        .open(root)?;
    let dir_before = info(&dir)?;
    if native::filesystem(&dir)? != "NTFS" {
        return Err("FILESYSTEM_UNVERIFIED".into());
    }
    directory(root, &dir, &dir_before, &security)?;
    let entries: Vec<_> = fs::read_dir(root)?
        .take(3)
        .map(|v| v.map(|e| e.file_name()))
        .collect::<std::io::Result<_>>()?;
    if entries.len() != 1 || entries[0] != SOURCE {
        return Err("INITIAL_ARTIFACTS_UNEXPECTED".into());
    }
    let mut source = open_source(root, &security)?;
    let mut owned: Vec<Artifact> = Vec::new();
    let mut attempted = false;
    let mut published = false;
    let mut installed_check_passed = false;
    let mut installed_file_flushed = false;
    let mut parent_flushed = false;
    let mut observation_file_flushed = false;
    let mut observation_parent_flushed = false;
    let result = (|| -> Result<()> {
        if checkpoints {
            emit(json!({"persistenceMode":persistence,"observationOnly":true}))?;
        }
        source.check(root, &security)?;
        barrier("source-guarded")?;
        source.file.seek(SeekFrom::Start(0))?;
        let mut candidate = if persistence == PersistenceMode::WriteThrough {
            security.create_write_through_file(&root.join(CANDIDATE))?
        } else {
            security.create_file(&root.join(CANDIDATE))?
        };
        // Labeled producer-stream injections exercise a failure after exclusive
        // file creation but before an Artifact can be returned/tracked.
        match source_fault {
            "short" => crate::staging::copy_exact(
                &mut Read::by_ref(&mut source.file).take(65535),
                &mut candidate,
                65536,
            )?,
            "long" => crate::staging::copy_exact(
                &mut Read::by_ref(&mut source.file).chain(&b"x"[..]),
                &mut candidate,
                65536,
            )?,
            _ => crate::staging::copy_exact(&mut source.file, &mut candidate, 65536)?,
        }
        candidate.sync_all()?;
        owned.push(Artifact {
            before: info(&candidate)?,
            file: candidate,
            hash: source.hash.clone(),
            name: CANDIDATE,
            persistence,
        });
        owned[0].check(root, &security)?;
        source.check(root, &security)?;
        dir.sync_all()?;
        barrier("candidate-flushed")?;
        for (name, phase) in RECORDS.iter().take(2) {
            let record = save(
                root,
                &security,
                name,
                phase,
                &dir_before,
                &source,
                &owned[0],
            )?;
            owned.push(record);
            dir.sync_all()?;
            barrier(if *phase == "prepared" {
                "prepared-record-flushed"
            } else {
                "intent-record-flushed"
            })?;
        }
        barrier("before-property-check")?;
        directory(root, &dir, &dir_before, &security)?;
        source.check(root, &security)?;
        for artifact in &mut owned {
            artifact.check(root, &security)?;
        }
        emit(json!({"boundary":"before-publication","propertiesMatch":true}))?;
        // Property observations are checkpoints under OD-11. Continuous byte/name
        // holds remain; no snapshot/hash is advertised as full property exclusion.
        if checkpoints {
            export_context(Stage::BeforePublication, &dir_before, &source, &owned)?;
        }
        barrier("before-namespace-call")?;
        attempted = true;
        native::rename(&owned[0].file, &dir, &root.join(OUTPUT), false)?;
        published = true;
        owned[0].name = OUTPUT;
        barrier("published")?;
        if persistence == PersistenceMode::FlushAfterRename {
            // Flush the held installed object before taking its property
            // observation. API success alone remains a distinct earlier cell.
            owned[0].file.sync_all()?;
            installed_file_flushed = true;
            if checkpoints {
                barrier("installed-file-flushed")?;
            }
        }
        directory(root, &dir, &dir_before, &security)?;
        source.check(root, &security)?;
        for artifact in &mut owned {
            artifact.check(root, &security)?;
        }
        emit(json!({"boundary":"installed-output","propertiesMatch":true}))?;
        installed_check_passed = true;
        if !installed_file_flushed {
            owned[0].file.sync_all()?;
            installed_file_flushed = true;
            if checkpoints {
                barrier("installed-file-flushed")?;
            }
        }
        dir.sync_all()?;
        parent_flushed = true;
        if checkpoints {
            export_context(Stage::AfterPublication, &dir_before, &source, &owned)?;
            barrier("parent-flushed")?;
        }
        let observation = save(
            root,
            &security,
            RECORDS[2].0,
            RECORDS[2].1,
            &dir_before,
            &source,
            &owned[0],
        )?;
        owned.push(observation);
        observation_file_flushed = true;
        if checkpoints {
            barrier("observation-file-flushed")?;
        }
        dir.sync_all()?;
        observation_parent_flushed = true;
        if checkpoints {
            export_context(Stage::AfterPublication, &dir_before, &source, &owned)?;
            barrier("observation-parent-flushed")?;
        }
        barrier("observed-record-flushed")?;
        directory(root, &dir, &dir_before, &security)?;
        source.check(root, &security)?;
        for artifact in &mut owned {
            artifact.check(root, &security)?;
        }
        Ok(())
    })();
    let error = result.err().map(|e| e.to_string());
    let cancel = error.as_deref() == Some("CONTROL_CANCEL");
    let mut removed = 0;
    let mut cleanup_pending = retained_work(root);
    if cancel
        && !attempted
        && directory(root, &dir, &dir_before, &security).is_ok()
        && owned.iter_mut().all(|v| v.check(root, &security).is_ok())
    {
        while let Some(artifact) = owned.pop() {
            if crate::disposition::mark_owned_file(&artifact.file).is_err() {
                break;
            }
            drop(artifact.file);
            removed += 1;
        }
        cleanup_pending = retained_work(root);
    }
    let outcome = if attempted {
        "recovery-required"
    } else if cancel {
        "cancelled-before-publication"
    } else if error.is_some() {
        "conflict-or-failed-before-publication"
    } else {
        "recovery-required"
    };
    emit(
        json!({"outcome":outcome,"diagnostic":error.map(|v|v.chars().filter(|c|!c.is_control()).take(128).collect::<String>()),"publicationAttempted":attempted,"publicationCallSucceeded":published,"installedCheckPassed":installed_check_passed,"installedFileFlushSucceeded":installed_file_flushed,"parentFlushSucceeded":parent_flushed,"observationFileFlushSucceeded":observation_file_flushed,"observationParentFlushSucceeded":observation_parent_flushed,"persistenceMode":persistence,"ownedHandlesRemoved":removed,"cleanupPending":cleanup_pending,"sourceRetained":true,"rootRetained":true}),
    )
}
fn inspect(root: &Path) -> Result<()> {
    let report = (|| -> Result<Value> {
        let _held = crate::windows::ancestors(root.parent().ok_or("PARENT_REQUIRED")?)?;
        let security = PrivateSecurity::current()?;
        let directory = OpenOptions::new()
            .access_mode(0x20080)
            .share_mode(3)
            .custom_flags(0x02200000)
            .open(root)?;
        security.check(&directory)?;
        let root_info = info(&directory)?;
        if root_info.attributes & 0x410 != 0x10 || native::filesystem(&directory)? != "NTFS" {
            return Err("ROOT_TYPE_OR_FILESYSTEM".into());
        }
        let names: Vec<_> = fs::read_dir(root)?
            .take(8)
            .map(|v| v.map(|e| e.file_name()))
            .collect::<std::io::Result<_>>()?;
        for name in &names {
            if ![
                SOURCE,
                CANDIDATE,
                OUTPUT,
                RECORDS[0].0,
                RECORDS[1].0,
                RECORDS[2].0,
            ]
            .iter()
            .any(|v| name == v)
            {
                return Err("UNEXPECTED_ARTIFACT".into());
            }
        }
        let has = |name: &str| names.iter().any(|v| v == name);
        let mut held = Vec::new();
        let mut records = Vec::new();
        for (name, phase) in RECORDS {
            if has(name) {
                let mut file = OpenOptions::new()
                    .access_mode(0x80020000)
                    .share_mode(1)
                    .custom_flags(0x02200000)
                    .open(root.join(name))?;
                security.check(&file)?;
                native::check_streams(&file)?;
                let before = info(&file)?;
                if before.links != 1 || before.attributes & 0x410 != 0 {
                    return Err("RECORD_TYPE_OR_LINKS".into());
                }
                let record = ordinary_record::decode(&read(&mut file)?, phase)?;
                if before != info(&file)?
                    || record.root.identity != root_info.identity
                    || record.root.creation_time != root_info.creation_time
                {
                    return Err("RECORD_ROOT_CHANGED".into());
                }
                if let Some(previous) = records.first() {
                    let previous: &Record = previous;
                    if previous.source != record.source
                        || previous.candidate != record.candidate
                        || previous.sha256 != record.sha256
                        || previous.persistence_mode != record.persistence_mode
                    {
                        return Err("RECORDS_DISAGREE".into());
                    }
                }
                records.push(record);
                held.push(file);
            }
        }
        if has(RECORDS[1].0) && !has(RECORDS[0].0) || has(RECORDS[2].0) && !has(RECORDS[1].0) {
            return Err("RECORD_SEQUENCE_INVALID".into());
        }
        let mut matched = Vec::new();
        for name in [SOURCE, CANDIDATE, OUTPUT] {
            if has(name) {
                let mut file = OpenOptions::new()
                    .access_mode(0x80020000)
                    .share_mode(1)
                    .custom_flags(0x02200000)
                    .open(root.join(name))?;
                security.check(&file)?;
                native::check_streams(&file)?;
                let before = info(&file)?;
                if before.attributes & 0x410 != 0 || before.links != 1 {
                    return Err("ARTIFACT_TYPE_OR_LINKS".into());
                }
                let hash = digest(&read(&mut file)?);
                let same = records.first().is_some_and(|r| {
                    before
                        == if name == SOURCE {
                            r.source.clone()
                        } else {
                            r.candidate.clone()
                        }
                        && hash == r.sha256
                });
                if info(&file)? != before {
                    return Err("ARTIFACT_CHANGED".into());
                }
                matched.push((name, same));
                held.push(file);
            }
        }
        let matches = |name: &str| matched.iter().any(|(n, m)| *n == name && *m);
        let outcome = if records.is_empty() {
            "unattributed-artifacts"
        } else if !matches(SOURCE) {
            "source-conflict"
        } else if has(CANDIDATE) && has(OUTPUT) {
            "candidate-and-output-conflict"
        } else if has(OUTPUT) {
            if matches(OUTPUT) && has(RECORDS[1].0) {
                "matching-output-recovery-required"
            } else {
                "output-conflict"
            }
        } else if has(CANDIDATE) && matches(CANDIDATE) {
            "candidate-retained-output-absent"
        } else {
            "candidate-missing-or-conflicting"
        };
        security.check(&directory)?;
        for file in &held {
            security.check(file)?;
            native::check_streams(file)?;
        }
        Ok(
            json!({"outcome":outcome,"recordCount":records.len(),"outputPresent":has(OUTPUT),"observationOnly":true,"persistenceMode":records.first().map(|r|r.persistence_mode)}),
        )
    })();
    emit(report.unwrap_or_else(|e|json!({"outcome":"uninspectable","diagnostic":e.to_string().chars().filter(|c|!c.is_control()).take(128).collect::<String>(),"observationOnly":true})))
}
fn check_restart_layout(root: &Path, candidate: &str, owned: &[Artifact]) -> Result<()> {
    let entries: Vec<_> = fs::read_dir(root)?
        .take(8)
        .map(|v| v.map(|e| e.file_name()))
        .collect::<io::Result<_>>()?;
    if entries.len() != owned.len() + 2
        || entries
            .iter()
            .any(|n| n != SOURCE && n != candidate && !owned.iter().any(|a| n == a.name))
    {
        return Err("RESTART_NAMESPACE_CONFLICT".into());
    }
    Ok(())
}
fn open_expected(
    root: &Path,
    name: &'static str,
    expected: &Info,
    hash: &str,
    mode: PersistenceMode,
    access: u32,
    security: &PrivateSecurity,
) -> Result<Artifact> {
    let file = OpenOptions::new()
        .access_mode(access)
        .share_mode(1)
        .custom_flags(
            0x02200000
                | if mode == PersistenceMode::WriteThrough {
                    0x80000000
                } else {
                    0
                },
        )
        .open(root.join(name))?;
    let mut artifact = Artifact {
        file,
        before: expected.clone(),
        hash: hash.into(),
        name,
        persistence: mode,
    };
    artifact.check(root, security)?;
    Ok(artifact)
}
fn restart(root: &Path, prune: bool) -> Result<()> {
    let mut line = Vec::new();
    io::stdin()
        .lock()
        .take(MAX_RECORD + 1)
        .read_until(b'\n', &mut line)?;
    let context = match restart_context::decode(&line) {
        Ok(c) => c,
        Err(e) => {
            return emit(
                json!({"outcome":"restart-refused-before-effects","diagnostic":e,"effectsAttempted":false,"ownedHandlesRemoved":0}),
            );
        }
    };
    if prune != (context.stage == Stage::BeforePublication) {
        return emit(
            json!({"outcome":"restart-refused-before-effects","diagnostic":"CALLER_STAGE_DISALLOWS_ACTION","effectsAttempted":false,"ownedHandlesRemoved":0}),
        );
    }
    let mut effects = false;
    if prune && !context.stopped_before_publication {
        return emit(
            json!({"outcome":"restart-refused-before-effects","diagnostic":"CALLER_STOP_CONFIRMATION_REQUIRED","effectsAttempted":false,"ownedHandlesRemoved":0}),
        );
    }
    let mut removed = 0;
    let mut recorded = false;
    let mut already_present = false;
    let result = (|| -> Result<()> {
        crate::staging::check_budget(&[65536, MAX_RECORD, MAX_RECORD, MAX_RECORD], 262144)?;
        let _ancestors = crate::windows::ancestors(root.parent().ok_or("PARENT_REQUIRED")?)?;
        let security = PrivateSecurity::current()?;
        let dir = OpenOptions::new()
            .access_mode(0xc0020000)
            .share_mode(3)
            .custom_flags(0x02200000)
            .open(root)?;
        if native::filesystem(&dir)? != "NTFS" {
            return Err("FILESYSTEM_UNVERIFIED".into());
        }
        directory(root, &dir, &context.root, &security)?;
        let mut source = open_expected(
            root,
            SOURCE,
            &context.source,
            &context.sha256,
            PersistenceMode::Buffered,
            0x80020000,
            &security,
        )?;
        if read(&mut source.file)? != vec![b'3'; 65536] {
            return Err("OWNED_MARKER_SOURCE_UNVERIFIED".into());
        }
        let candidate_name = if prune { CANDIDATE } else { OUTPUT };
        let mut candidate = open_expected(
            root,
            candidate_name,
            &context.candidate,
            &context.sha256,
            context.persistence_mode,
            0xc0030000,
            &security,
        )?;
        let mut records = Vec::new();
        for expected in &context.records {
            let mut artifact = open_expected(
                root,
                expected.name.leaf(),
                &expected.info,
                &expected.sha256,
                context.persistence_mode,
                0x80030000,
                &security,
            )?;
            let record =
                ordinary_record::decode(&read(&mut artifact.file)?, expected.name.phase())?;
            if record.root != context.root
                || record.source != context.source
                || record.candidate != context.candidate
                || record.sha256 != context.sha256
                || record.persistence_mode != context.persistence_mode
            {
                return Err("RESTART_RECORD_CONTEXT_DISAGREES".into());
            }
            records.push(artifact);
        }
        check_restart_layout(root, candidate_name, &records)?;
        emit(
            json!({"restartAction":if prune { "prune-unpublished" } else { "record-output-observation" },"callerStage":context.stage}),
        )?;
        barrier("restart-guarded")?;
        directory(root, &dir, &context.root, &security)?;
        source.check(root, &security)?;
        candidate.check(root, &security)?;
        for r in &mut records {
            r.check(root, &security)?;
        }
        check_restart_layout(root, candidate_name, &records)?;
        if prune {
            // These exact objects were created exclusively by the prior worker,
            // and the caller retained its before-publication context. Reopened
            // handles, not editable records or pathname patterns, select deletion.
            while let Some(mut artifact) = records.pop() {
                emit(json!({"ownedLeaf":artifact.name}))?;
                barrier("restart-before-remove")?;
                directory(root, &dir, &context.root, &security)?;
                source.check(root, &security)?;
                candidate.check(root, &security)?;
                artifact.check(root, &security)?;
                for r in &mut records {
                    r.check(root, &security)?;
                }
                let mut remaining_names: Vec<_> = records.iter().map(|r| r.name).collect();
                remaining_names.push(artifact.name);
                let entries: Vec<_> = fs::read_dir(root)?
                    .take(8)
                    .map(|v| v.map(|e| e.file_name()))
                    .collect::<io::Result<_>>()?;
                if entries.len() != remaining_names.len() + 2
                    || entries.iter().any(|n| {
                        n != SOURCE && n != CANDIDATE && !remaining_names.iter().any(|s| n == s)
                    })
                {
                    return Err("RESTART_NAMESPACE_CONFLICT".into());
                }
                effects = true;
                crate::disposition::mark_owned_file(&artifact.file)?;
                drop(artifact);
                removed += 1;
                barrier("restart-file-removed")?;
            }
            barrier("restart-before-remove")?;
            directory(root, &dir, &context.root, &security)?;
            source.check(root, &security)?;
            candidate.check(root, &security)?;
            check_restart_layout(root, CANDIDATE, &[])?;
            effects = true;
            crate::disposition::mark_owned_file(&candidate.file)?;
            drop(candidate);
            removed += 1;
            barrier("restart-file-removed")?;
            source.check(root, &security)?;
        } else {
            already_present = context.records.len() == 3;
            if !already_present {
                barrier("restart-before-record")?;
                directory(root, &dir, &context.root, &security)?;
                source.check(root, &security)?;
                candidate.check(root, &security)?;
                for r in &mut records {
                    r.check(root, &security)?;
                }
                check_restart_layout(root, OUTPUT, &records)?;
                candidate.file.sync_all()?;
                dir.sync_all()?;
                effects = true;
                let record = save(
                    root,
                    &security,
                    RECORDS[2].0,
                    RECORDS[2].1,
                    &context.root,
                    &source,
                    &candidate,
                )?;
                recorded = true;
                records.push(record);
                export_held_context(
                    Stage::AfterPublication,
                    &context.root,
                    &source,
                    &candidate,
                    &records,
                )?;
                barrier("restart-record-file-flushed")?;
                dir.sync_all()?;
                barrier("restart-record-parent-flushed")?;
                directory(root, &dir, &context.root, &security)?;
                source.check(root, &security)?;
                candidate.check(root, &security)?;
                for r in &mut records {
                    r.check(root, &security)?;
                }
                check_restart_layout(root, OUTPUT, &records)?;
            }
        }
        Ok(())
    })();
    let diagnostic = result.err().map(|e| {
        e.to_string()
            .chars()
            .filter(|c| !c.is_control())
            .take(128)
            .collect::<String>()
    });
    let outcome = if diagnostic.is_some() {
        if effects {
            "restart-partial-or-uncertain"
        } else {
            "restart-refused-before-effects"
        }
    } else if prune {
        "owned-unpublished-handles-pruned"
    } else if already_present {
        "output-observation-already-present"
    } else {
        "output-observation-recorded-recovery-required"
    };
    emit(
        json!({"outcome":outcome,"diagnostic":diagnostic,"effectsAttempted":effects,"ownedHandlesRemoved":removed,"observationRecordCreated":recorded,"cleanupPending":if prune { retained_work(root) } else { effects && !recorded },"retainedWork":retained_work(root),"sourceRetained":true,"rootRetained":true,"markerResearchOnly":true}),
    )
}
pub fn run(root: &Path, mode: &str) -> Result<()> {
    match mode {
        "-prepare" => prepare(root),
        "" => live(root, "", PersistenceMode::Buffered, false),
        "-short-source" => live(root, "short", PersistenceMode::Buffered, false),
        "-long-source" => live(root, "long", PersistenceMode::Buffered, false),
        "-persistence-buffered" => live(root, "", PersistenceMode::Buffered, true),
        "-flush-after-rename" => live(root, "", PersistenceMode::FlushAfterRename, true),
        "-write-through" => live(root, "", PersistenceMode::WriteThrough, true),
        "-inspect" => inspect(root),
        "-restart-observe" => restart(root, false),
        "-restart-prune" => restart(root, true),
        "-admit" | "-finalize" | "-prune" => emit(
            json!({"outcome":"refused-before-effects","workerArtifacts":0,"missingCells":["qualified-windows-namespace-receipt-crash-persistence","safe-restart-finalization-prune"]}),
        ),
        _ => Err("ORDINARY_MODE_UNVERIFIED".into()),
    }
}
