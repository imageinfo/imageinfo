#[allow(dead_code)]
mod support;
use imageinfo::{
    privacy::{
        self, RemovalLimits, RemovalRefusal,
        provenance::{ProvenanceRequest, Reason},
    },
    xmp,
};

fn packet(owner: bool, properties: &str, namespace: &str) -> Vec<u8> {
    format!(
        "<r:RDF xmlns:r='{}'><r:Description xmlns:a='{}' xmlns:p='{namespace}' {}>{properties}</r:Description></r:RDF>",
        xmp::RDF,
        privacy::OWNER_NAMESPACE,
        if owner { "a:OwnerName='invented'" } else { "" },
    ).into_bytes()
}

fn remove<'a>(
    source: &'a [u8],
    request: ProvenanceRequest<'_>,
) -> Result<privacy::OwnerRemoval<'a>, RemovalRefusal> {
    privacy::remove_owner_name(
        "authored-sidecar",
        source,
        xmp::Limits::default(),
        RemovalLimits::default(),
        request,
    )
}

#[test]
fn actual_boundary_preserves_duplicate_empty_and_uninterpretable_properties() {
    for owner in [false, true] {
        for values in [
            "<p:Signature/>",
            "<p:Signature>0</p:Signature><p:Signature>not-a-signature</p:Signature>",
        ] {
            let source = packet(owner, values, "http://www.w3.org/2000/09/xmldsig#");
            let retained = source.clone();
            let Err(RemovalRefusal::Provenance(refusal)) =
                remove(&source, ProvenanceRequest::SidecarOnly)
            else {
                panic!("must refuse before derivative, including no-op new output")
            };
            assert_eq!(refusal.reason, Reason::PacketConstraint);
            assert!(!refusal.requested_change_performed());
            assert_eq!(
                refusal.packet_indicators.len(),
                if values.contains("not-a-signature") {
                    2
                } else {
                    1
                }
            );
            for (property, range) in refusal.packet_indicators.iter().zip(&refusal.packet_ranges) {
                assert_eq!(
                    property.name.namespace,
                    "http://www.w3.org/2000/09/xmldsig#"
                );
                let range = range.as_ref().unwrap();
                assert!(source[range.clone()].starts_with(b"<p:Signature"));
            }
            assert_eq!(source, retained);
        }
    }
}

#[test]
fn coupling_declarations_refuse_and_case_distinct_unknown_names_do_not_certify_absence() {
    for namespace in [
        "http://www.w3.org/2000/09/xmldsig#",
        "http://ns.adobe.com/xap/1.0/mm/",
        "http://ns.adobe.com/xap/1.0/",
        "http://ns.adobe.com/xmp/note/",
        "http://ns.adobe.com/photoshop/1.0/",
    ] {
        assert!(matches!(
            remove(
                &packet(false, "", namespace),
                ProvenanceRequest::SidecarOnly
            ),
            Err(RemovalRefusal::Provenance(_))
        ));
    }
    let source = packet(
        true,
        "<p:Signature>uninterpreted</p:Signature>",
        "urn:authored:unknown",
    );
    let derivative = remove(&source, ProvenanceRequest::SidecarOnly).unwrap();
    assert!(derivative.removed.is_some());
    assert!(
        std::str::from_utf8(&derivative.bytes)
            .unwrap()
            .contains("uninterpreted")
    );
}

#[test]
fn malformed_scope_and_unsupported_invalidation_never_construct_candidates() {
    for request in [ProvenanceRequest::Invalidate, ProvenanceRequest::Force] {
        for owner in [false, true] {
            let source = packet(owner, "", "urn:authored:unknown");
            let Err(RemovalRefusal::Provenance(result)) = remove(&source, request) else {
                panic!("unsupported request")
            };
            assert_eq!(result.reason, Reason::UnsupportedInvalidation);
        }
    }
    for source in [b"<broken".as_slice(), b"<!DOCTYPE x><x/>".as_slice()] {
        assert!(matches!(
            remove(source, ProvenanceRequest::SidecarOnly),
            Err(RemovalRefusal::Packet(_))
        ));
    }
    let source = packet(true, "", "urn:authored:unknown");
    let Err(RemovalRefusal::Provenance(result)) = remove(
        &source,
        ProvenanceRequest::Preserve {
            native_source: Some(b"malformed-native"),
        },
    ) else {
        panic!("native inspection refusal")
    };
    assert_eq!(result.reason, Reason::NativeInspection);
    assert!(result.native_error.is_some());
}

fn native() -> Vec<u8> {
    support::fixture_with_previews(
        "Firmware Version 2.2.1",
        vec![255, 216, 255, 217],
        vec![255, 216, 255, 217],
        vec![255, 216, 255, 217],
    )
    .bytes
}

// Compact the authored required arrays while retaining their exact selected
// values. Additional TIFF entries fit inside the original payload extent, so
// container lengths and all later track/preview offsets stay unchanged.
fn add_native_indicators(raw: &mut [u8], values: &[u32]) {
    let kind = raw.windows(4).position(|w| w == b"CMT3").unwrap();
    let base = kind + 4;
    let payload_len = u32::from_be_bytes(raw[kind - 4..kind].try_into().unwrap()) as usize - 8;
    let mut settings = vec![0u8; 8];
    settings[..2].copy_from_slice(&8u16.to_le_bytes());
    settings[6..8].copy_from_slice(&4u16.to_le_bytes());
    let mut lighting = vec![0u8; 48];
    lighting[..4].copy_from_slice(&48u32.to_le_bytes());
    let mut fields = vec![
        (1, 3, settings),
        (7, 2, b"Firmware Version 2.2.1\0".to_vec()),
        (16, 4, 0x80000421u32.to_le_bytes().to_vec()),
        (0x4018, 4, lighting),
    ];
    fields.extend(
        values
            .iter()
            .map(|value| (0x83, 4, value.to_le_bytes().to_vec())),
    );
    let mut payload = support::tiff(fields);
    assert!(payload.len() <= payload_len);
    payload.resize(payload_len, 0);
    raw[base..base + payload_len].copy_from_slice(&payload);
}

#[test]
fn exact_native_indicator_gate_retains_every_occurrence_without_following_values() {
    for value in [0u32, u32::MAX] {
        let mut raw = native();
        add_native_indicators(&mut raw, &[value, value]);
        for owner in [false, true] {
            let source = packet(owner, "", "urn:authored:unknown");
            let Err(RemovalRefusal::Provenance(refusal)) = remove(
                &source,
                ProvenanceRequest::Preserve {
                    native_source: Some(&raw),
                },
            ) else {
                panic!("known native indicator")
            };
            assert_eq!(refusal.reason, Reason::KnownIndicator);
            assert_eq!(
                refusal
                    .native_indicators
                    .iter()
                    .filter(|p| p.code == "CANON_ORIGINAL_DECISION_INDICATOR")
                    .count(),
                2
            );
            assert_ne!(
                refusal.native_indicators[0].range,
                refusal.native_indicators[1].range
            );
        }
    }
}

#[test]
fn no_match_with_incomplete_native_dependency_scope_still_refuses() {
    let raw = native();
    let source = packet(true, "", "urn:authored:unknown");
    let Err(RemovalRefusal::Provenance(refusal)) = remove(
        &source,
        ProvenanceRequest::Preserve {
            native_source: Some(&raw),
        },
    ) else {
        panic!("opaque dependencies remain")
    };
    assert!(refusal.native_indicators.is_empty());
    assert!(
        refusal
            .native_refusals
            .iter()
            .any(|p| p.code == "OPAQUE_DEPENDENCY_UNPROVEN")
    );
}

#[test]
fn same_numeric_tag_in_cmt2_does_not_impersonate_canon_cmt3_identity() {
    let mut raw = native();
    let base = raw.windows(4).position(|w| w == b"CMT2").unwrap() + 4;
    let count = u16::from_le_bytes(raw[base + 8..base + 10].try_into().unwrap()) as usize;
    let at = (0..count)
        .map(|i| base + 10 + i * 12)
        .find(|&at| u16::from_le_bytes(raw[at..at + 2].try_into().unwrap()) == 0x9011)
        .unwrap();
    raw[at..at + 2].copy_from_slice(&0x83u16.to_le_bytes());
    let source = packet(true, "", "urn:authored:unknown");
    let Err(RemovalRefusal::Provenance(refusal)) = remove(
        &source,
        ProvenanceRequest::Preserve {
            native_source: Some(&raw),
        },
    ) else {
        panic!("independent opaque-dependency gate")
    };
    assert!(
        refusal
            .native_indicators
            .iter()
            .all(|p| p.code != "CANON_ORIGINAL_DECISION_INDICATOR")
    );
    assert!(!refusal.native_refusals.is_empty());
}

#[test]
fn reached_indicator_survives_a_later_real_jpeg_inspection_error() {
    let mut raw = support::fixture_with_previews(
        "Firmware Version 2.2.1",
        vec![255, 216, 255, 235, 0, 1, 255, 217],
        vec![255, 216, 255, 217],
        vec![255, 216, 255, 217],
    )
    .bytes;
    add_native_indicators(&mut raw, &[0]);
    let source = packet(true, "", "urn:authored:unknown");
    let Err(RemovalRefusal::Provenance(refusal)) = remove(
        &source,
        ProvenanceRequest::Preserve {
            native_source: Some(&raw),
        },
    ) else {
        panic!("partial inspection refuses")
    };
    assert_eq!(refusal.reason, Reason::KnownIndicator);
    assert_eq!(refusal.native_indicators.len(), 1);
    assert_eq!(
        refusal.native_indicators[0].code,
        "CANON_ORIGINAL_DECISION_INDICATOR"
    );
    assert!(refusal.native_error.is_some());
    assert!(!refusal.requested_change_performed());
}

#[test]
fn completed_app11_indicator_survives_later_errors_or_discard_without_duplication() {
    let mut description = vec![
        0x63, 0x32, 0x70, 0x61, 0, 0x11, 0, 0x10, 0x80, 0, 0, 0xaa, 0, 0x38, 0x9b, 0x71, 3,
    ];
    description.extend_from_slice(b"c2pa\0");
    let data = support::atom(b"jumb", support::atom(b"jumd", description));
    for mode in 0..4 {
        let mut body = data.clone();
        if mode == 1 {
            // The first complete box is reached before this malformed tail.
            body.extend_from_slice(b"bad");
        }
        let payload = [b"JP\0\x01\0\0\0\x01".to_vec(), body].concat();
        let segment = [
            vec![255, 235],
            ((payload.len() + 2) as u16).to_be_bytes().to_vec(),
            payload,
        ]
        .concat();
        let tail = match mode {
            0 => vec![255, 224, 0, 1, 255, 217],
            1 => vec![255, 217],
            2 => [
                vec![255, 235, 0, 18],
                b"JP\0\x01\0\0\0\x02".to_vec(),
                b"mismatch".to_vec(),
                vec![255, 217],
            ]
            .concat(),
            3 => [[255, 1].repeat(4096), vec![255, 217]].concat(),
            _ => unreachable!(),
        };
        let jpeg = [vec![255, 216], segment, tail].concat();
        let raw = support::fixture_with_previews(
            "Firmware Version 2.2.1",
            jpeg,
            vec![255, 216, 255, 217],
            vec![255, 216, 255, 217],
        )
        .bytes;
        let source = packet(true, "", "urn:authored:unknown");
        let Err(RemovalRefusal::Provenance(refusal)) = remove(
            &source,
            ProvenanceRequest::Preserve {
                native_source: Some(&raw),
            },
        ) else {
            panic!("complete earlier indicator must remain visible")
        };
        assert_eq!(refusal.reason, Reason::KnownIndicator, "mode {mode}");
        assert_eq!(refusal.native_indicators.len(), 1, "mode {mode}");
        assert_eq!(refusal.native_indicators[0].code, "C2PA_JPEG_JUMBF");
        if mode == 2 {
            assert!(refusal.native_error.is_none());
            assert!(
                refusal
                    .native_refusals
                    .iter()
                    .any(|f| f.code == "APP11_SEQUENCE_UNVERIFIED")
            );
        } else {
            assert_eq!(
                refusal.native_error.as_ref().unwrap().code,
                if mode == 3 {
                    "LIMIT_EXCEEDED"
                } else {
                    "INVALID_STRUCTURE"
                }
            );
        }
        assert!(!refusal.requested_change_performed());
    }
}
