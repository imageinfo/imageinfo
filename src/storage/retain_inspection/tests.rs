use super::*;

fn expected() -> Expectation {
    let artifact = |file_index, marker| ArtifactObservation {
        identity: Identity {
            volume_serial: 14,
            file_index,
        },
        snapshot: Snapshot {
            size: 42,
            links: 1,
            attributes: 32,
            creation_time: 50,
            last_write_time: 51,
            owner_dacl: "O:SYD:P(A;;FA;;;SY)".into(),
        },
        sha256: [marker; 32],
    };
    Expectation {
        schema: SCHEMA.into(),
        old: artifact(26, 3),
        candidate: artifact(40, 8),
    }
}

#[test]
fn fixed_expectation_accepts_objects_and_rejects_truncation_and_trailing_data() {
    let expectation = expected();
    let encoded = serde_json::to_vec(&expectation).unwrap();
    assert_eq!(parse_expectation(&encoded), Ok(expectation));
    for end in 0..encoded.len() {
        assert_eq!(
            parse_expectation(&encoded[..end]),
            Err(Refusal::MalformedExpectation)
        );
    }
    let mut trailing = encoded;
    trailing.extend_from_slice(b"{}");
    assert_eq!(
        parse_expectation(&trailing),
        Err(Refusal::MalformedExpectation)
    );
}

#[test]
fn malformed_unknown_duplicate_and_positional_fields_refuse() {
    let encoded = serde_json::to_string(&expected()).unwrap();
    for invalid in [
        encoded.replace(SCHEMA, "imageinfo.retain-inspection.v2"),
        encoded.replacen("\"old\":", "\"path\":\"elsewhere\",\"old\":", 1),
        encoded.replacen("\"size\":42", "\"size\":42,\"size\":42", 1),
        encoded.replacen("\"fileIndex\":26", "\"fileIndex\":26,\"unknown\":null", 1),
        encoded.replacen("{\"volumeSerial\":14,\"fileIndex\":26}", "[14,26]", 1),
        encoded.replacen("\"size\":42", "\"size\":[[[42]]]", 1),
        encoded.replacen("\"sha256\":[3,", "\"sha256\":[300,", 1),
        encoded.replacen("\"sha256\":[3,", "\"sha256\":[", 1),
        encoded.replacen("\"sha256\":[3,", "\"sha256\":[3,3,", 1),
        encoded.replacen("\"old\":", &format!("\"schema\":\"{SCHEMA}\",\"old\":"), 1),
        format!(
            "[\"{SCHEMA}\",{},{}]",
            serde_json::to_string(&expected().old).unwrap(),
            serde_json::to_string(&expected().candidate).unwrap()
        ),
    ] {
        assert_eq!(
            parse_expectation(invalid.as_bytes()),
            Err(Refusal::MalformedExpectation)
        );
    }
}

#[test]
fn bounds_and_identity_role_conflicts_refuse() {
    let expectation = expected();
    let mut encoded = serde_json::to_vec(&expectation).unwrap();
    encoded.resize(super::super::MAX_RECORD_BYTES as usize, b' ');
    assert_eq!(parse_expectation(&encoded), Ok(expectation));
    encoded.push(b' ');
    assert_eq!(parse_expectation(&encoded), Err(Refusal::ExpectationBound));

    let mut expectation = expected();
    let parse = |value: &Expectation| parse_expectation(&serde_json::to_vec(value).unwrap());
    expectation.old.snapshot.size = MAX_ARTIFACT_BYTES;
    assert!(parse(&expectation).is_ok());
    expectation.old.snapshot.size += 1;
    assert_eq!(parse(&expectation), Err(Refusal::ExpectationBound));
    expectation.old.snapshot.size = 42;
    expectation.old.snapshot.owner_dacl = "a".repeat(MAX_OWNER_DACL_BYTES + 1);
    assert_eq!(parse(&expectation), Err(Refusal::ExpectationBound));
    expectation.old = expectation.candidate.clone();
    assert_eq!(parse(&expectation), Err(Refusal::ContradictoryExpectation));
    expectation.old.identity.volume_serial += 1;
    assert_eq!(parse(&expectation), Err(Refusal::ContradictoryExpectation));
}

#[test]
fn names_refuse_traversal_aliases_devices_and_overlong_spelling() {
    assert!(validate_slots(["target.bin", "Retained.bin", "staging.bin"]).is_ok());
    let oversized = "s".repeat(101);
    for leaf in [
        "",
        ".",
        "..",
        "x/../target",
        "x\\target",
        "x:stream",
        "s\u{7f}",
        "s\u{fe}",
        "s.",
        "s ",
        "CONIN$.bin",
        "con.txt",
        "con .txt",
        "com5.bin",
        "TARGEt.Bin",
        &oversized,
    ] {
        assert_eq!(
            validate_slots(["target.bin", "retained.bin", leaf]),
            Err(Refusal::InvalidSlots)
        );
    }
}

#[test]
fn role_association_checks_physical_identity_before_hash_or_properties() {
    let expected = expected();
    let mut actual = expected.old.clone();
    actual.identity = expected.candidate.identity;
    assert_eq!(
        associate(&actual, &expected),
        Association::Mismatch {
            role: Role::Candidate,
            snapshot_matches: true,
            sha256_matches: false,
        }
    );
    actual.identity.file_index += 1;
    assert_eq!(
        associate(&actual, &expected),
        Association::Foreign {
            same_bytes_as_old: true,
            same_bytes_as_candidate: false,
        }
    );
    assert_eq!(
        disposition(&[
            SlotObservation::Missing,
            SlotObservation::Unavailable(Issue::Inaccessible),
            SlotObservation::Missing
        ]),
        Disposition::IncompleteOrUncertain
    );
}

#[cfg(not(windows))]
#[test]
fn unsupported_platform_refuses_without_opening_root() {
    assert_eq!(
        inspect(
            Path::new("deliberately-missing"),
            ["target", "retained", "staging"],
            &serde_json::to_vec(&expected()).unwrap()
        ),
        Err(Refusal::UnsupportedPlatform)
    );
}
