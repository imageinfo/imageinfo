//! Bounded UTF-8 XML/XMP packet inspection. No file I/O or serialization.
//!
//! See `docs/sidecars/packet-profile.md` for the exact accepted lexical profile.
//! Inspection preserves unknown identities; it does not authorize an edit.
use roxmltree::{Document, Node, ParsingOptions};
use std::collections::HashSet;

pub const RDF: &str = "http://www.w3.org/1999/02/22-rdf-syntax-ns#";
pub const XML: &str = "http://www.w3.org/XML/1998/namespace";
pub const META: &str = "adobe:ns:meta/";

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ExpandedName {
    pub namespace: String,
    pub local: String,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Form {
    Attribute,
    Element,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Property {
    /// Zero-based traversal ordinal, scoped to this packet, not stable across edits.
    pub ordinal: usize,
    pub name: ExpandedName,
    pub form: Form,
    pub value: Value,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Container {
    Sequence,
    Bag,
    LanguageAlternative,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Language {
    pub spelling: String,
    pub key: String,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Member {
    /// One-based serialized membership occurrence; bag order is observation only.
    pub position: usize,
    pub language: Option<Language>,
    pub text: String,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Value {
    Text(String),
    List(Container, Vec<Member>),
}

#[derive(Debug, PartialEq, Eq)]
pub struct Packet<'a> {
    /// Source retained for unknown spelling/lexical data; no serialization promise.
    source: &'a str,
    properties: Vec<Property>,
    deletion_ranges: Vec<Option<std::ops::Range<usize>>>,
    property_ranges: Vec<std::ops::Range<usize>>,
    packet_mode: PacketMode,
    /// Concrete indicators only; absence is not an authenticity certificate.
    couplings: Vec<Coupling>,
}

#[derive(Debug, Clone, Copy)]
pub struct Limits {
    pub bytes: usize,
    pub nodes: u32,
    pub depth: usize,
    pub attributes_per_element: usize,
    pub namespace_declarations_per_element: usize,
    pub properties: usize,
    pub members_per_list: usize,
    pub text_bytes: usize,
}

impl Default for Limits {
    fn default() -> Self {
        Self {
            bytes: 65_536,
            nodes: 2_048,
            depth: 16,
            attributes_per_element: 32,
            namespace_declarations_per_element: 32,
            properties: 128,
            members_per_list: 128,
            text_bytes: 8_192,
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Refusal {
    Bytes,
    Utf8,
    Doctype,
    Xml,
    Nodes,
    Depth,
    Attributes,
    NamespaceDeclarations,
    Properties,
    Members,
    Text,
    Shape,
    Namespace,
    Qualifier,
    Language,
    DuplicateLanguage,
    Declaration,
    PacketInstruction,
    Name,
    Reference,
    Coupling,
    ReadOnlyPacket,
}

fn expanded(namespace: Option<&str>, local: &str) -> Result<ExpandedName, Refusal> {
    let namespace = namespace.ok_or(Refusal::Namespace)?;
    if namespace == RDF || namespace == XML || namespace == META {
        return Err(Refusal::Namespace);
    }
    Ok(ExpandedName {
        namespace: namespace.to_owned(),
        local: local.to_owned(),
    })
}

fn elements<'a, 'i>(node: Node<'a, 'i>) -> Result<Vec<Node<'a, 'i>>, Refusal> {
    if node.children().any(|n| {
        n.is_text()
            && !n
                .text()
                .unwrap_or("")
                .trim_matches([' ', '\t', '\r', '\n'])
                .is_empty()
    }) {
        return Err(Refusal::Shape);
    }
    Ok(node.children().filter(Node::is_element).collect())
}

fn text(node: Node<'_, '_>, limit: usize) -> Result<String, Refusal> {
    if node.children().any(|n| n.is_element()) {
        return Err(Refusal::Shape);
    }
    let mut result = String::new();
    for child in node.children().filter(Node::is_text) {
        let value = child.text().unwrap_or("");
        if value.len() > limit.saturating_sub(result.len()) {
            return Err(Refusal::Text);
        }
        result.push_str(value);
    }
    Ok(result)
}

fn language(value: &str) -> Result<Language, Refusal> {
    let key = value.to_ascii_lowercase();
    // A deliberately small language subset avoids pretending to validate BCP 47.
    let parts: Vec<_> = value.split('-').collect();
    let letters = |s: &str| s.bytes().all(|b| b.is_ascii_alphabetic());
    let valid = key == "x-default"
        || ((2..=3).contains(&parts[0].len())
            && letters(parts[0])
            && (parts.len() == 1
                || (parts.len() == 2
                    && ((parts[1].len() == 2 && letters(parts[1]))
                        || (parts[1].len() == 3
                            && parts[1].bytes().all(|b| b.is_ascii_digit()))))));
    if !valid {
        return Err(Refusal::Language);
    }
    Ok(Language {
        spelling: value.to_owned(),
        key,
    })
}

fn value(node: Node<'_, '_>, limits: Limits) -> Result<Value, Refusal> {
    if node.attributes().len() != 0 {
        return Err(Refusal::Qualifier);
    }
    let children: Vec<_> = node.children().filter(Node::is_element).collect();
    if children.is_empty() {
        return Ok(Value::Text(text(node, limits.text_bytes)?));
    }
    let children = elements(node)?;
    if children.len() != 1 {
        return Err(Refusal::Shape);
    }
    let list = children[0];
    let kind = match (list.tag_name().namespace(), list.tag_name().name()) {
        (Some(RDF), "Seq") => Container::Sequence,
        (Some(RDF), "Bag") => Container::Bag,
        (Some(RDF), "Alt") => Container::LanguageAlternative,
        _ => return Err(Refusal::Shape),
    };
    if list.attributes().len() != 0 {
        return Err(Refusal::Qualifier);
    }
    let mut members = Vec::new();
    let mut languages = HashSet::new();
    for item in elements(list)? {
        if members.len() == limits.members_per_list {
            return Err(Refusal::Members);
        }
        if !item.has_tag_name((RDF, "li")) {
            return Err(Refusal::Shape);
        }
        let language = if kind == Container::LanguageAlternative {
            if item.attributes().len() != 1 {
                return Err(Refusal::Qualifier);
            }
            let lang = language(item.attribute((XML, "lang")).ok_or(Refusal::Language)?)?;
            if lang.key == "x-default" && !members.is_empty() {
                return Err(Refusal::Language);
            }
            if !languages.insert(lang.key.clone()) {
                return Err(Refusal::DuplicateLanguage);
            }
            Some(lang)
        } else {
            if item.attributes().len() != 0 {
                return Err(Refusal::Qualifier);
            }
            None
        };
        members.push(Member {
            position: members.len() + 1,
            language,
            text: text(item, limits.text_bytes)?,
        });
    }
    Ok(Value::List(kind, members))
}

pub fn inspect(bytes: &[u8], limits: Limits) -> Result<Packet<'_>, Refusal> {
    if bytes.len() > limits.bytes {
        return Err(Refusal::Bytes);
    }
    let source = std::str::from_utf8(bytes).map_err(|_| Refusal::Utf8)?;
    let doc = Document::parse_with_options(
        source,
        ParsingOptions {
            allow_dtd: false,
            nodes_limit: limits.nodes,
            entity_resolver: None,
        },
    )
    .map_err(|e| match e {
        roxmltree::Error::DtdDetected => Refusal::Doctype,
        roxmltree::Error::NodesLimitReached => Refusal::Nodes,
        _ => Refusal::Xml,
    })?;
    declaration(source)?;
    lexical_checks(source, limits)?;
    let packet_mode = packet_instructions(&doc, source)?;
    let mut couplings = Vec::new();
    for node in doc.descendants().filter(Node::is_element) {
        for namespace in node.namespaces() {
            if let Some(indicator) = coupling(namespace.uri())
                && !couplings.contains(&indicator)
            {
                couplings.push(indicator);
            }
        }
        if node.ancestors().filter(Node::is_element).count() > limits.depth {
            return Err(Refusal::Depth);
        }
        if node.attributes().len() > limits.attributes_per_element {
            return Err(Refusal::Attributes);
        }
    }
    let mut rdf = doc.root_element();
    if rdf.has_tag_name((META, "xmpmeta")) {
        if rdf
            .attributes()
            .any(|a| a.namespace() != Some(META) || a.name() != "xmptk")
        {
            return Err(Refusal::Qualifier);
        }
        let children = elements(rdf)?;
        if children.len() != 1 {
            return Err(Refusal::Shape);
        }
        rdf = children[0];
    }
    if !rdf.has_tag_name((RDF, "RDF")) || rdf.attributes().len() != 0 {
        return Err(Refusal::Shape);
    }
    let descriptions = elements(rdf)?;
    if descriptions.len() != 1 || !descriptions[0].has_tag_name((RDF, "Description")) {
        return Err(Refusal::Shape);
    }
    let description = descriptions[0];
    let mut properties = Vec::new();
    let mut deletion_ranges = Vec::new();
    let mut property_ranges = Vec::new();
    for attr in description.attributes() {
        if attr.namespace() == Some(RDF) && attr.name() == "about" && attr.value().is_empty() {
            continue;
        }
        if properties.len() == limits.properties {
            return Err(Refusal::Properties);
        }
        if attr.value().len() > limits.text_bytes {
            return Err(Refusal::Text);
        }
        property_ranges.push(attr.range());
        deletion_ranges.push(Some(attr.range()));
        properties.push(Property {
            ordinal: properties.len(),
            name: expanded(attr.namespace(), attr.name())?,
            form: Form::Attribute,
            value: Value::Text(attr.value().to_owned()),
        });
    }
    for child in elements(description)? {
        if properties.len() == limits.properties {
            return Err(Refusal::Properties);
        }
        let deletable = child.attributes().len() == 0
            && child.children().all(|n| n.is_text())
            && !local_namespace_declaration(&source[child.range()]);
        property_ranges.push(child.range());
        deletion_ranges.push(deletable.then(|| child.range()));
        properties.push(Property {
            ordinal: properties.len(),
            name: expanded(child.tag_name().namespace(), child.tag_name().name())?,
            form: Form::Element,
            value: value(child, limits)?,
        });
    }
    Ok(Packet {
        source,
        properties,
        deletion_ranges,
        property_ranges,
        packet_mode,
        couplings,
    })
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum PacketMode {
    Bare,
    Writable,
    ReadOnly,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Coupling {
    XmlSignature,
    XmpMediaManagement,
    XmpBasic,
    ExtendedXmp,
    Photoshop,
}

fn coupling(uri: &str) -> Option<Coupling> {
    match uri {
        "http://www.w3.org/2000/09/xmldsig#" => Some(Coupling::XmlSignature),
        "http://ns.adobe.com/xap/1.0/mm/" => Some(Coupling::XmpMediaManagement),
        "http://ns.adobe.com/xap/1.0/" => Some(Coupling::XmpBasic),
        "http://ns.adobe.com/xmp/note/" => Some(Coupling::ExtendedXmp),
        "http://ns.adobe.com/photoshop/1.0/" => Some(Coupling::Photoshop),
        _ => None,
    }
}

impl Packet<'_> {
    pub(crate) fn property_range(&self, ordinal: usize) -> Option<std::ops::Range<usize>> {
        self.property_ranges.get(ordinal).cloned()
    }

    /// Parser-bound whole-property range, only for supported deletion shapes.
    pub(crate) fn deletion_range(&self, ordinal: usize) -> Option<std::ops::Range<usize>> {
        self.deletion_ranges.get(ordinal).cloned().flatten()
    }

    pub fn source(&self) -> &str {
        self.source
    }
    pub fn properties(&self) -> &[Property] {
        &self.properties
    }
    pub fn packet_mode(&self) -> PacketMode {
        self.packet_mode
    }
    pub fn couplings(&self) -> &[Coupling] {
        &self.couplings
    }

    /// Refuse concrete unresolved coupling and read-only packet instructions.
    /// Success checks only this packet profile; source-specific dependency review,
    /// intent, native source binding and publication admission remain separate.
    pub fn check_edit_constraints(&self) -> Result<(), Refusal> {
        if !self.couplings.is_empty() {
            return Err(Refusal::Coupling);
        }
        if self.packet_mode == PacketMode::ReadOnly {
            return Err(Refusal::ReadOnlyPacket);
        }
        Ok(())
    }
}

fn declaration(source: &str) -> Result<(), Refusal> {
    let source = source.strip_prefix('\u{feff}').unwrap_or(source);
    if source.starts_with("<?xml")
        && source
            .as_bytes()
            .get(5)
            .is_some_and(u8::is_ascii_whitespace)
        && !source.starts_with("<?xml ")
    {
        return Err(Refusal::Declaration);
    }
    if !source.starts_with("<?xml ") {
        // The component rejects misplaced declarations and reserved PI targets.
        return Ok(());
    }
    let end = source.find("?>").ok_or(Refusal::Declaration)?;
    let body = &source[6..end];
    // Deliberately finite declaration syntax, not another XML declaration parser.
    let fields: Vec<_> = body.split(' ').collect();
    let matches = |field: &str, name: &str, values: &[&str]| {
        values.iter().any(|value| {
            field == format!("{name}=\"{value}\"") || field == format!("{name}='{value}'")
        })
    };
    if fields.is_empty() || !matches(fields[0], "version", &["1.0"]) {
        return Err(Refusal::Declaration);
    }
    let mut rest = &fields[1..];
    if rest
        .first()
        .is_some_and(|s| matches(s, "encoding", &["UTF-8"]))
    {
        rest = &rest[1..];
    }
    if rest
        .first()
        .is_some_and(|s| matches(s, "standalone", &["yes", "no"]))
    {
        rest = &rest[1..];
    }
    if !rest.is_empty() {
        return Err(Refusal::Declaration);
    }
    Ok(())
}

fn packet_instructions(doc: &Document<'_>, source: &str) -> Result<PacketMode, Refusal> {
    let instructions: Vec<_> = doc.descendants().filter(Node::is_pi).collect();
    if instructions.is_empty() {
        return Ok(PacketMode::Bare);
    }
    if instructions.len() != 2 {
        return Err(Refusal::PacketInstruction);
    }
    let root = doc.root_element().range();
    let begin = instructions[0];
    let end = instructions[1];
    if begin.range().end > root.start || end.range().start < root.end {
        return Err(Refusal::PacketInstruction);
    }
    let raw_begin = &source[begin.range()];
    let valid_begin = ['\'', '"'].iter().any(|quote| {
        ["", "\u{feff}"].iter().any(|marker| {
            ['\'', '"'].iter().any(|id_quote| {
                raw_begin == format!(
                    "<?xpacket begin={quote}{marker}{quote} id={id_quote}W5M0MpCehiHzreSzNTczkc9d{id_quote}?>"
                )
            })
        })
    });
    if !valid_begin {
        return Err(Refusal::PacketInstruction);
    }
    match &source[end.range()] {
        "<?xpacket end='w'?>" | "<?xpacket end=\"w\"?>" => Ok(PacketMode::Writable),
        "<?xpacket end='r'?>" | "<?xpacket end=\"r\"?>" => Ok(PacketMode::ReadOnly),
        _ => Err(Refusal::PacketInstruction),
    }
}

fn ascii_qname(name: &str) -> Result<(), Refusal> {
    let mut count = 0;
    for part in name.split(':') {
        count += 1;
        let mut bytes = part.bytes();
        if !bytes
            .next()
            .is_some_and(|b| b.is_ascii_alphabetic() || b == b'_')
            || !bytes.all(|b| b.is_ascii_alphanumeric() || b"_.-".contains(&b))
        {
            return Err(Refusal::Name);
        }
    }
    if count > 2 {
        return Err(Refusal::Name);
    }
    Ok(())
}

fn references(value: &str) -> Result<(), Refusal> {
    for rest in value.split("&#").skip(1) {
        let digits = rest.split_once(';').ok_or(Refusal::Reference)?.0;
        let (digits, radix) = digits.strip_prefix('x').map_or((digits, 10), |s| (s, 16));
        let code = u32::from_str_radix(digits, radix).map_err(|_| Refusal::Reference)?;
        if !matches!(code, 0x9 | 0xa | 0xd | 0x20..=0xd7ff | 0xe000..=0xfffd | 0x10000..=0x10ffff) {
            return Err(Refusal::Reference);
        }
    }
    Ok(())
}

fn lexical_checks(mut source: &str, limits: Limits) -> Result<(), Refusal> {
    // This runs only after bounded component parsing. It supplements two measured
    // tokenizer gaps (QName starts and invalid numeric Unicode scalar replacement),
    // reserved xmlns declarations and XML-1.0 prefixed namespace undeclaration.
    // It is not a second XML parser: syntax/nesting/entities/namespaces remain the
    // component's responsibility. Inert lexical regions are skipped verbatim.
    while !source.is_empty() {
        let inert = [("<!--", "-->"), ("<![CDATA[", "]]>"), ("<?", "?>")]
            .into_iter()
            .find(|(open, _)| source.starts_with(open));
        if let Some((open, close)) = inert {
            let end =
                source[open.len()..].find(close).ok_or(Refusal::Xml)? + open.len() + close.len();
            source = &source[end..];
        } else if let Some(mut tag) = source.strip_prefix('<') {
            if let Some(close) = tag.strip_prefix('/') {
                tag = close;
            }
            let end = tag
                .find(|c: char| c.is_ascii_whitespace() || c == '/' || c == '>')
                .ok_or(Refusal::Xml)?;
            ascii_qname(&tag[..end])?;
            tag = &tag[end..];
            let mut namespace_declarations = 0;
            loop {
                tag = tag.trim_start_matches([' ', '\t', '\r', '\n']);
                if let Some(rest) = tag.strip_prefix('>') {
                    source = rest;
                    break;
                }
                if let Some(rest) = tag.strip_prefix("/>") {
                    source = rest;
                    break;
                }
                let end = tag
                    .find(|c: char| c.is_ascii_whitespace() || c == '=')
                    .ok_or(Refusal::Xml)?;
                let attribute_name = &tag[..end];
                ascii_qname(attribute_name)?;
                if attribute_name == "xmlns" || attribute_name.starts_with("xmlns:") {
                    namespace_declarations += 1;
                    if namespace_declarations > limits.namespace_declarations_per_element {
                        return Err(Refusal::NamespaceDeclarations);
                    }
                }
                if attribute_name == "xmlns:xmlns" {
                    return Err(Refusal::Namespace);
                }
                tag = tag[end..].trim_start_matches([' ', '\t', '\r', '\n']);
                tag = tag
                    .strip_prefix('=')
                    .ok_or(Refusal::Xml)?
                    .trim_start_matches([' ', '\t', '\r', '\n']);
                let quote = tag.chars().next().ok_or(Refusal::Xml)?;
                if quote != '\'' && quote != '"' {
                    return Err(Refusal::Xml);
                }
                tag = &tag[1..];
                let end = tag.find(quote).ok_or(Refusal::Xml)?;
                if attribute_name.starts_with("xmlns:") && end == 0 {
                    return Err(Refusal::Namespace);
                }
                references(&tag[..end])?;
                tag = &tag[end + 1..];
            }
        } else {
            let end = source.find('<').unwrap_or(source.len());
            references(&source[..end])?;
            source = &source[end..];
        }
    }
    Ok(())
}

// Inspect only the already parsed element's start tag. Preserve all namespace
// declaration bytes by refusing deletion of an element that declares one locally.
fn local_namespace_declaration(mut source: &str) -> bool {
    source = &source[1..];
    let end = source
        .find(|c: char| c.is_ascii_whitespace() || c == '/' || c == '>')
        .unwrap_or(source.len());
    source = &source[end..];
    loop {
        source = source.trim_start_matches([' ', '\t', '\r', '\n']);
        if source.starts_with('>') || source.starts_with("/>") {
            return false;
        }
        let Some(end) = source.find(|c: char| c.is_ascii_whitespace() || c == '=') else {
            return true;
        };
        let name = &source[..end];
        if name == "xmlns" || name.starts_with("xmlns:") {
            return true;
        }
        source = source[end..].trim_start_matches([' ', '\t', '\r', '\n']);
        let Some(rest) = source.strip_prefix('=') else {
            return true;
        };
        source = rest.trim_start_matches([' ', '\t', '\r', '\n']);
        let Some(quote) = source.chars().next() else {
            return true;
        };
        source = &source[quote.len_utf8()..];
        let Some(end) = source.find(quote) else {
            return true;
        };
        source = &source[end + quote.len_utf8()..];
    }
}
