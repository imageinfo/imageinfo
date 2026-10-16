use imageinfo::{
    privacy::{self, RemovalLimits, RemovalRefusal, provenance::ProvenanceRequest},
    xmp,
};
use std::borrow::Cow;
fn packet(attrs: &str, children: &str) -> String {
    format!(
        "<r:RDF xmlns:r='{}' xmlns:o='{}' xmlns:u='urn:unknown'><r:Description r:about='' {}>{}</r:Description></r:RDF>",
        xmp::RDF,
        privacy::OWNER_NAMESPACE,
        attrs,
        children
    )
}
fn remove(bytes: &[u8]) -> Result<privacy::OwnerRemoval<'_>, RemovalRefusal> {
    privacy::remove_owner_name(
        "authored-sidecar",
        bytes,
        xmp::Limits::default(),
        RemovalLimits::default(),
        ProvenanceRequest::default(),
    )
}
#[test]
fn attribute_exact_range_preserves_separators_entities_and_unknowns() {
    let target = "o:OwnerName = \"Invented &amp; owner\"";
    let original = packet(
        &format!("u:first='&amp;'  {target}\n u:last='tail'"),
        "<!--protected--><u:keep><![CDATA[a<b]]></u:keep>",
    );
    let out = remove(original.as_bytes()).unwrap();
    assert_eq!(out.bytes.as_ref(), original.replace(target, "").as_bytes());
    let found = out.removed.unwrap();
    assert_eq!(found.document_id, "authored-sidecar");
    assert_eq!(found.property.ordinal, 1);
    assert_eq!(&original[found.deletion_range], target);
}
#[test]
fn simple_empty_and_cdata_elements_remove_whole_property() {
    for target in [
        "<o:OwnerName>invented</o:OwnerName>",
        "<o:OwnerName/>",
        "<o:OwnerName></o:OwnerName>",
        "<o:OwnerName><![CDATA[<&]]></o:OwnerName>",
    ] {
        let original = packet("u:keep='a'", &format!("\n{target}\n<u:keep>z</u:keep>"));
        let out = remove(original.as_bytes()).unwrap();
        assert_eq!(out.bytes.as_ref(), original.replace(target, "").as_bytes());
        assert!(out.removed.is_some());
    }
}
#[test]
fn absent_borrows_and_lookalikes_are_retained() {
    let original = packet(
        "u:OwnerName='retained' o:ownerName='case'",
        "<u:OwnerName>same local</u:OwnerName>",
    );
    let out = remove(original.as_bytes()).unwrap();
    assert!(matches!(out.bytes, Cow::Borrowed(_)));
    assert_eq!(out.bytes.as_ptr(), original.as_ptr());
    assert!(out.removed.is_none());
}
#[test]
fn aliases_select_uri_and_rebinding_retains_lookalike() {
    let target = "<o:OwnerName>target</o:OwnerName>";
    let original = packet(
        "",
        &format!("{target}<o:OwnerName xmlns:o='urn:other'>keep</o:OwnerName>"),
    );
    let out = remove(original.as_bytes()).unwrap();
    assert_eq!(out.bytes.as_ref(), original.replace(target, "").as_bytes());
}
#[test]
fn duplicates_refuse_including_attribute_element_and_aliases() {
    for original in [
        packet("o:OwnerName='a'", "<o:OwnerName>a</o:OwnerName>"),
        packet("", "<o:OwnerName/><o:OwnerName/>"),
        packet(
            "xmlns:alias='http://ns.adobe.com/exif/1.0/aux/' o:OwnerName='a' alias:OwnerName='a'",
            "",
        ),
    ] {
        assert!(remove(original.as_bytes()).is_err());
    }
}
#[test]
fn unsupported_or_qualified_targets_never_become_absent() {
    for target in [
        "<o:OwnerName xml:lang='en'>name</o:OwnerName>",
        "<o:OwnerName><r:Seq><r:li>name</r:li></r:Seq></o:OwnerName>",
        "<o:OwnerName><u:nested/></o:OwnerName>",
        "<o:OwnerName><!--retained?-->name</o:OwnerName>",
        "<o:OwnerName xmlns:local='urn:keep'>name</o:OwnerName>",
    ] {
        assert!(remove(packet("", target).as_bytes()).is_err(), "{target}");
    }
}
#[test]
fn malformed_profile_and_limits_refuse() {
    let original = packet("o:OwnerName='name'", "");
    let base = xmp::Limits::default();
    for limits in [
        xmp::Limits {
            bytes: original.len() - 1,
            ..base
        },
        xmp::Limits {
            properties: 0,
            ..base
        },
        xmp::Limits {
            text_bytes: 3,
            ..base
        },
        xmp::Limits { nodes: 1, ..base },
    ] {
        assert!(
            privacy::remove_owner_name(
                "a",
                original.as_bytes(),
                limits,
                RemovalLimits::default(),
                ProvenanceRequest::default()
            )
            .is_err()
        );
    }
    assert!(
        privacy::remove_owner_name(
            "a",
            original.as_bytes(),
            base,
            RemovalLimits {
                output_bytes: 1,
                ..RemovalLimits::default()
            },
            ProvenanceRequest::default()
        )
        .is_err()
    );
    for bad in [b"<!DOCTYPE x><x/>".as_slice(), b"<bad".as_slice(), &[255]] {
        assert!(remove(bad).is_err());
    }
}
#[test]
fn provenance_gate_applies_before_absent_new_output() {
    let original = packet(
        "xmlns:mm='http://ns.adobe.com/xap/1.0/mm/'",
        "<mm:DocumentID>authored-id</mm:DocumentID>",
    );
    assert!(matches!(
        remove(original.as_bytes()),
        Err(RemovalRefusal::Provenance(_))
    ));
    let clean = packet("", "");
    assert!(
        privacy::remove_owner_name(
            "a",
            clean.as_bytes(),
            xmp::Limits::default(),
            RemovalLimits::default(),
            ProvenanceRequest::Force
        )
        .is_err()
    );
}
#[test]
fn writable_packet_instructions_bom_are_exact() {
    let xml = packet("o:OwnerName='authored'", "<u:keep>unchanged</u:keep>");
    let original = format!(
        "\u{feff}<?xml version='1.0' encoding='UTF-8'?><?xpacket begin='' id='W5M0MpCehiHzreSzNTczkc9d'?>{xml}   <?xpacket end='w'?>"
    );
    let out = remove(original.as_bytes()).unwrap();
    assert_eq!(
        out.bytes.as_ref(),
        original.replace("o:OwnerName='authored'", "").as_bytes()
    );
    assert!(remove(original.replace("end='w'", "end='r'").as_bytes()).is_err());
}
#[test]
fn absent_output_bound_and_document_id_bound_are_enforced() {
    let original = packet("", "");
    assert!(matches!(
        privacy::remove_owner_name(
            "a",
            original.as_bytes(),
            xmp::Limits::default(),
            RemovalLimits {
                output_bytes: original.len() - 1,
                ..RemovalLimits::default()
            },
            ProvenanceRequest::default()
        ),
        Err(RemovalRefusal::OutputLimit)
    ));
    for id in ["", "abc"] {
        assert!(matches!(
            privacy::remove_owner_name(
                id,
                original.as_bytes(),
                xmp::Limits::default(),
                RemovalLimits {
                    document_id_bytes: 2,
                    ..RemovalLimits::default()
                },
                ProvenanceRequest::default()
            ),
            Err(RemovalRefusal::DocumentId)
        ));
    }
}
#[test]
fn multibyte_offsets_and_self_closing_description_remain_valid() {
    let original = format!(
        "<r:RDF xmlns:r='{}' xmlns:o='{}' xmlns:u='urn:u'><r:Description u:before='\u{e9}\u{2603}' o:OwnerName='invented' u:after='\u{4fdd}\u{7559}'/></r:RDF>",
        xmp::RDF,
        privacy::OWNER_NAMESPACE
    );
    let out = remove(original.as_bytes()).unwrap();
    assert_eq!(
        out.bytes.as_ref(),
        original.replace("o:OwnerName='invented'", "").as_bytes()
    );
    assert_eq!(
        &original[out.removed.unwrap().deletion_range],
        "o:OwnerName='invented'"
    );
}

#[test]
fn unknown_lists_and_repeated_sibling_order_survive_exactly() {
    let target = "<o:OwnerName>invented</o:OwnerName>";
    let original = packet(
        "",
        &format!(
            "<u:repeat>one</u:repeat>{target}<u:repeat>two</u:repeat><u:list><r:Seq><r:li>z</r:li><r:li>a</r:li></r:Seq></u:list>"
        ),
    );
    let out = remove(original.as_bytes()).unwrap();
    let expected = original.replace(target, "");
    assert_eq!(out.bytes.as_ref(), expected.as_bytes());
    let observed = xmp::inspect(&out.bytes, xmp::Limits::default()).unwrap();
    assert_eq!(observed.properties().len(), 3);
    assert_eq!(
        observed.properties()[0].value,
        xmp::Value::Text("one".into())
    );
    assert_eq!(
        observed.properties()[1].value,
        xmp::Value::Text("two".into())
    );
}
