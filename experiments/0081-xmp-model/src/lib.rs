//! Authored, bounded read-only XMP subset for #0081; no production parser or writer.
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
    pub source: &'a str,
    pub properties: Vec<Property>,
}

#[derive(Debug, Clone, Copy)]
pub struct Limits {
    pub bytes: usize,
    pub nodes: u32,
    pub depth: usize,
    pub attributes_per_element: usize,
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
    Properties,
    Members,
    Text,
    Shape,
    Namespace,
    Qualifier,
    Language,
    DuplicateLanguage,
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
    if node
        .children()
        .any(|n| n.is_text() && !n.text().unwrap_or("").trim().is_empty())
    {
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
    for node in doc.descendants().filter(Node::is_element) {
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
        properties.push(Property {
            ordinal: properties.len(),
            name: expanded(child.tag_name().namespace(), child.tag_name().name())?,
            form: Form::Element,
            value: value(child, limits)?,
        });
    }
    Ok(Packet { source, properties })
}
