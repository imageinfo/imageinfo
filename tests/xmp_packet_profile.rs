use imageinfo::xmp::*;

fn packet(body: &str) -> String {
    format!(
        "<r:RDF xmlns:r='{RDF}'><r:Description r:about='' xmlns:p='urn:unknown/' xmlns:q='urn:unknown/'>{body}</r:Description></r:RDF>"
    )
}

fn read(xml: &str) -> Result<Packet<'_>, Refusal> {
    inspect(xml.as_bytes(), Limits::default())
}

#[test]
fn aliases_duplicates_unknown_uri_and_empty_are_exact() {
    let xml = packet(
        "<p:Date>2026</p:Date><q:Date>2026</q:Date><p:Date xmlns:p='urn:unknown'>other</p:Date><p:Empty/>",
    );
    let result = read(&xml).unwrap();
    assert_eq!(result.source(), xml);
    assert_eq!(
        result.properties(),
        vec![
            Property {
                ordinal: 0,
                name: ExpandedName {
                    namespace: "urn:unknown/".into(),
                    local: "Date".into()
                },
                form: Form::Element,
                value: Value::Text("2026".into())
            },
            Property {
                ordinal: 1,
                name: ExpandedName {
                    namespace: "urn:unknown/".into(),
                    local: "Date".into()
                },
                form: Form::Element,
                value: Value::Text("2026".into())
            },
            Property {
                ordinal: 2,
                name: ExpandedName {
                    namespace: "urn:unknown".into(),
                    local: "Date".into()
                },
                form: Form::Element,
                value: Value::Text("other".into())
            },
            Property {
                ordinal: 3,
                name: ExpandedName {
                    namespace: "urn:unknown/".into(),
                    local: "Empty".into()
                },
                form: Form::Element,
                value: Value::Text("".into())
            },
        ]
    );
}

#[test]
fn attribute_form_precedes_child_occurrences() {
    let xml = format!(
        "<r:RDF xmlns:r='{RDF}' xmlns:p='urn:unknown/'><r:Description p:Date='2026' r:about=''><p:Date>2027</p:Date></r:Description></r:RDF>"
    );
    let result = read(&xml).unwrap();
    assert_eq!(result.properties()[0].form, Form::Attribute);
    assert_eq!(result.properties()[1].form, Form::Element);
    assert_eq!(result.properties()[0].name, result.properties()[1].name);
    assert_eq!(result.properties()[0].value, Value::Text("2026".into()));
    assert_eq!(result.properties()[1].value, Value::Text("2027".into()));
}

#[test]
fn sequence_bag_and_language_alt_retain_membership() {
    for (tag, kind) in [("Seq", Container::Sequence), ("Bag", Container::Bag)] {
        let xml = packet(&format!(
            "<p:Items><r:{tag}><r:li>B</r:li><r:li>A</r:li><r:li>A</r:li></r:{tag}></p:Items>"
        ));
        assert_eq!(
            read(&xml).unwrap().properties()[0].value,
            Value::List(
                kind,
                vec![
                    Member {
                        position: 1,
                        language: None,
                        text: "B".into()
                    },
                    Member {
                        position: 2,
                        language: None,
                        text: "A".into()
                    },
                    Member {
                        position: 3,
                        language: None,
                        text: "A".into()
                    },
                ]
            )
        );
    }
    let xml = packet(
        "<p:Title><r:Alt><r:li xml:lang='x-default'>A</r:li><r:li xml:lang='EN-us'>B</r:li></r:Alt></p:Title>",
    );
    assert_eq!(
        read(&xml).unwrap().properties()[0].value,
        Value::List(
            Container::LanguageAlternative,
            vec![
                Member {
                    position: 1,
                    language: Some(Language {
                        spelling: "x-default".into(),
                        key: "x-default".into()
                    }),
                    text: "A".into()
                },
                Member {
                    position: 2,
                    language: Some(Language {
                        spelling: "EN-us".into(),
                        key: "en-us".into()
                    }),
                    text: "B".into()
                },
            ]
        )
    );
}

#[test]
fn duplicate_language_and_outside_language_subset_refuse() {
    for (body, expected) in [
        (
            "<r:li xml:lang='en-US'>A</r:li><r:li xml:lang='EN-us'>B</r:li>",
            Refusal::DuplicateLanguage,
        ),
        ("<r:li xml:lang='zh-Hant'>A</r:li>", Refusal::Language),
        (
            "<r:li xml:lang='en'>A</r:li><r:li xml:lang='x-default'>B</r:li>",
            Refusal::Language,
        ),
        ("<r:li xml:lang=''>A</r:li>", Refusal::Language),
        ("<r:li>A</r:li>", Refusal::Qualifier),
    ] {
        assert_eq!(
            read(&packet(&format!("<p:T><r:Alt>{body}</r:Alt></p:T>"))),
            Err(expected)
        );
    }
}

#[test]
fn unsupported_unknown_shapes_are_never_silently_discarded() {
    for (body, expected) in [
        ("<p:T p:qualifier='x'>A</p:T>", Refusal::Qualifier),
        (
            "<p:T r:resource='https://example.invalid/a'/>",
            Refusal::Qualifier,
        ),
        (
            "<p:T r:parseType='Resource'><p:N>A</p:N></p:T>",
            Refusal::Qualifier,
        ),
        ("<p:T><p:N>A</p:N></p:T>", Refusal::Shape),
        ("<p:T>mixed<r:Bag/></p:T>", Refusal::Shape),
        ("<T/>", Refusal::Namespace),
        ("<r:type>A</r:type>", Refusal::Namespace),
        ("<p:T xml:lang='en'>A</p:T>", Refusal::Qualifier),
        (
            "<p:T><r:Seq><r:li p:qualifier='x'>A</r:li></r:Seq></p:T>",
            Refusal::Qualifier,
        ),
    ] {
        assert_eq!(read(&packet(body)), Err(expected), "{body}");
    }
}

#[test]
fn entities_encoding_and_doctype_vectors() {
    assert_eq!(
        read(&packet(
            "<p:T>&amp;&#x41;<![CDATA[B]]><!-- split -->C</p:T>"
        ))
        .unwrap()
        .properties()[0]
            .value,
        Value::Text("&ABC".into())
    );
    assert_eq!(inspect(&[0xff], Limits::default()), Err(Refusal::Utf8));
    assert_eq!(read(&packet("<p:T>&unknown;</p:T>")), Err(Refusal::Xml));
    for declaration in [
        "<!DOCTYPE r:RDF>",
        "<!DOCTYPE r:RDF []>",
        "<!DOCTYPE r:RDF SYSTEM 'https://example.invalid/external.dtd'>",
        "<!DOCTYPE r:RDF [<!ENTITY a 'expansion'>]>",
    ] {
        assert_eq!(
            read(&format!("{declaration}{}", packet(""))),
            Err(Refusal::Doctype)
        );
    }
    assert!(read(&format!("<!-- <!DOCTYPE -->{}", packet(""))).is_ok());
    assert_eq!(
        read(&packet("<p:T><![CDATA[<!DOCTYPE]]></p:T>"))
            .unwrap()
            .properties()[0]
            .value,
        Value::Text("<!DOCTYPE".into())
    );
}

#[test]
fn exact_limits_and_one_over_each_bound() {
    let xml = packet("<p:T>A</p:T>");
    let defaults = Limits::default();
    assert!(
        inspect(
            xml.as_bytes(),
            Limits {
                bytes: xml.len(),
                ..defaults
            }
        )
        .is_ok()
    );
    assert_eq!(
        inspect(
            xml.as_bytes(),
            Limits {
                bytes: xml.len() - 1,
                ..defaults
            }
        ),
        Err(Refusal::Bytes)
    );
    let nodes = roxmltree::Document::parse(&xml)
        .unwrap()
        .descendants()
        .count() as u32;
    assert!(inspect(xml.as_bytes(), Limits { nodes, ..defaults }).is_ok());
    assert_eq!(
        inspect(
            xml.as_bytes(),
            Limits {
                nodes: nodes - 1,
                ..defaults
            }
        ),
        Err(Refusal::Nodes)
    );
    for (limits, expected) in [
        (
            Limits {
                depth: 2,
                ..defaults
            },
            Refusal::Depth,
        ),
        (
            Limits {
                attributes_per_element: 0,
                ..defaults
            },
            Refusal::Attributes,
        ),
        (
            Limits {
                properties: 0,
                ..defaults
            },
            Refusal::Properties,
        ),
        (
            Limits {
                text_bytes: 0,
                ..defaults
            },
            Refusal::Text,
        ),
    ] {
        assert_eq!(inspect(xml.as_bytes(), limits), Err(expected));
    }
    assert!(
        inspect(
            xml.as_bytes(),
            Limits {
                depth: 3,
                attributes_per_element: 1,
                properties: 1,
                text_bytes: 1,
                ..defaults
            }
        )
        .is_ok()
    );
    let list = packet("<p:T><r:Bag><r:li>A</r:li></r:Bag></p:T>");
    assert!(
        inspect(
            list.as_bytes(),
            Limits {
                members_per_list: 1,
                ..defaults
            }
        )
        .is_ok()
    );
    assert_eq!(
        inspect(
            list.as_bytes(),
            Limits {
                members_per_list: 0,
                ..defaults
            }
        ),
        Err(Refusal::Members)
    );
}

#[test]
fn malformed_xml_and_multiple_subjects_refuse() {
    assert_eq!(read(&packet("<p:T>")), Err(Refusal::Xml));
    let duplicate_attributes = format!(
        "<r:RDF xmlns:r='{RDF}' xmlns:p='urn:x' xmlns:q='urn:x'><r:Description p:A='1' q:A='2'/></r:RDF>"
    );
    assert_eq!(read(&duplicate_attributes), Err(Refusal::Xml));
    for body in [
        "<r:Description/><r:Description/>",
        "<r:Description r:about='external'/>",
        "<r:Description xml:lang='en'/>",
    ] {
        assert!(read(&format!("<r:RDF xmlns:r='{RDF}'>{body}</r:RDF>")).is_err());
    }
}

#[test]
fn optional_wrapper_and_processing_instructions_keep_source() {
    let xml = format!(
        "<?xpacket begin='' id='W5M0MpCehiHzreSzNTczkc9d'?><x:xmpmeta xmlns:x='{META}' x:xmptk='authored'>{}</x:xmpmeta><?xpacket end='w'?>",
        packet("<p:T>value</p:T>")
    );
    assert_eq!(read(&xml).unwrap().source(), xml);
}

#[test]
fn supported_declarations_bom_and_packet_envelopes_are_exact() {
    for bom in ["", "\u{feff}"] {
        for declaration in [
            "",
            "<?xml version='1.0'?>",
            "<?xml version=\"1.0\" encoding='UTF-8'?>",
            "<?xml version='1.0' standalone='no'?>",
            "<?xml version='1.0' encoding=\"UTF-8\" standalone='yes'?>",
        ] {
            for mode in ["", "w", "r"] {
                let body = packet("<p:T>&#x1F600;</p:T>");
                let xml = if mode.is_empty() {
                    format!("{bom}{declaration}{body}")
                } else {
                    format!(
                        "{bom}{declaration}<?xpacket begin='\u{feff}' id=\"W5M0MpCehiHzreSzNTczkc9d\"?>{body} \r\n<?xpacket end='{mode}'?>"
                    )
                };
                let result = read(&xml).unwrap();
                assert_eq!(result.source().as_bytes(), xml.as_bytes());
                assert_eq!(
                    result.packet_mode(),
                    match mode {
                        "w" => PacketMode::Writable,
                        "r" => PacketMode::ReadOnly,
                        _ => PacketMode::Bare,
                    }
                );
                assert_eq!(
                    result.check_edit_constraints(),
                    if mode == "r" {
                        Err(Refusal::ReadOnlyPacket)
                    } else {
                        Ok(())
                    }
                );
            }
        }
    }
}

#[test]
fn unsupported_or_contradictory_declarations_refuse() {
    for declaration in [
        "<?xml version='1.1'?>",
        "<?xml version='anything'?>",
        "<?xml version='1.0' encoding='UTF-16'?>",
        "<?xml version='1.0' encoding='utf-8'?>",
        "<?xml version='1.0' standalone='maybe'?>",
        "<?xml encoding='UTF-8' version='1.0'?>",
        "<?xml\tversion='1.0'?>",
        "<?xml version = '1.0'?>",
        "<?xml version='1.0' ?>",
        "<?xml version='1.0' version='1.0'?>",
        "<?xml?>",
    ] {
        assert!(
            read(&format!("{declaration}{}", packet(""))).is_err(),
            "{declaration}"
        );
    }
    for bytes in [&b"\xff\xfe<\0r\0"[..], &b"\xef\xbb\xbf\xef\xbb\xbf<r/>"[..]] {
        assert!(inspect(bytes, Limits::default()).is_err());
    }
}

#[test]
fn packet_instructions_must_be_paired_and_outside_the_root() {
    let begin = "<?xpacket begin='' id='W5M0MpCehiHzreSzNTczkc9d'?>";
    for xml in [
        format!("{begin}{}", packet("")),
        format!("{}<?xpacket end='w'?>", packet("")),
        format!("{begin}{}<?xpacket end='x'?>", packet("")),
        format!(
            "{begin}{}<?xpacket end='w'?>",
            packet("<?xpacket end='r'?>")
        ),
        format!("<?other inert?>{}", packet("")),
        format!(
            "<?xpacket begin='' id='wrong'?>{}<?xpacket end='w'?>",
            packet("")
        ),
    ] {
        assert_eq!(read(&xml), Err(Refusal::PacketInstruction));
    }
}

#[test]
fn component_name_and_numeric_scalar_gaps_are_refused() {
    for body in [
        "<p:1bad/>",
        "<1:T xmlns:1='urn:x'/>",
        "<p:T p:1bad='x'/>",
        "<p:T xmlns:1='urn:x'/>",
        "<p:é/>",
        "<p:T>&#xD800;</p:T>",
        "<p:T>&#1114112;</p:T>",
        "<p:T>&#0;</p:T>",
        "<p:T>&#xFFFFFFF;</p:T>",
        "<p:T p:A='&#xD800;'/>",
        "<p:T>&#x;</p:T>",
        "<p:T>&#-1;</p:T>",
        "<p:T>&missing;</p:T>",
    ] {
        assert!(read(&packet(body)).is_err(), "{body}");
    }
    assert!(
        read(&packet(
            "<p:T><![CDATA[&#xD800; <1bad/>]]><!-- &#1114112; --></p:T>"
        ))
        .is_ok()
    );
    assert!(read(&packet("\u{a0}<p:T/>")).is_err());
}

#[test]
fn declared_couplings_refuse_edits_without_claiming_authenticity() {
    for (uri, indicator) in [
        ("http://www.w3.org/2000/09/xmldsig#", Coupling::XmlSignature),
        (
            "http://ns.adobe.com/xap/1.0/mm/",
            Coupling::XmpMediaManagement,
        ),
        ("http://ns.adobe.com/xap/1.0/", Coupling::XmpBasic),
        ("http://ns.adobe.com/xmp/note/", Coupling::ExtendedXmp),
        ("http://ns.adobe.com/photoshop/1.0/", Coupling::Photoshop),
    ] {
        let xml = packet(&format!("<p:T xmlns:declared='{uri}'>retained</p:T>"));
        let result = read(&xml).unwrap();
        assert_eq!(result.couplings(), &[indicator]);
        assert_eq!(result.check_edit_constraints(), Err(Refusal::Coupling));
        assert_eq!(result.source(), xml);
    }
    let xml = packet("<p:T>unknown retained</p:T>");
    let result = read(&xml).unwrap();
    assert!(result.couplings().is_empty());
    assert_eq!(result.check_edit_constraints(), Ok(()));
}

#[test]
fn namespace_declaration_contradictions_and_component_gaps_refuse() {
    for declaration in [
        "xmlns:xmlns='urn:wrong'",
        "xmlns:z=''",
        "xmlns:xml='urn:wrong'",
        "xmlns='http://www.w3.org/2000/xmlns/'",
        "xmlns='http://www.w3.org/XML/1998/namespace'",
        "xmlns:z='http://www.w3.org/2000/xmlns/'",
        "xmlns:z='http://www.w3.org/XML/1998/namespace'",
        "xmlns:xml=''",
    ] {
        let xml = packet(&format!("<p:T {declaration}>value</p:T>"));
        assert!(read(&xml).is_err(), "{declaration}");
    }
    let xml = packet("<p:T xmlns=''>accepted prefixed property</p:T>");
    assert!(read(&xml).is_ok());
}

#[test]
fn input_default_limit_is_enforced_without_changing_source() {
    let xml = packet("<p:T/>");
    let padded = format!("{}{}", xml, " ".repeat(65_536 - xml.len()));
    assert!(read(&padded).is_ok());
    assert_eq!(read(&format!("{padded} ")), Err(Refusal::Bytes));
}

#[test]
fn namespace_declaration_limit_counts_local_spellings_including_redundancy() {
    let xml = packet("<p:T xmlns:a='urn:a' xmlns:b='urn:b'>value</p:T>");
    let defaults = Limits::default();
    assert!(
        inspect(
            xml.as_bytes(),
            Limits {
                namespace_declarations_per_element: 2,
                ..defaults
            }
        )
        .is_ok()
    );
    assert_eq!(
        inspect(
            xml.as_bytes(),
            Limits {
                namespace_declarations_per_element: 1,
                ..defaults
            }
        ),
        Err(Refusal::NamespaceDeclarations)
    );
    let repeated =
        packet("<p:T xmlns:p='urn:unknown/' xmlns:a='urn:a' xmlns:b='urn:b'>value</p:T>");
    assert_eq!(
        inspect(
            repeated.as_bytes(),
            Limits {
                namespace_declarations_per_element: 2,
                ..defaults
            }
        ),
        Err(Refusal::NamespaceDeclarations)
    );
}
