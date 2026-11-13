use super::{
    CompileError, CompiledFilter, DeclarationError, ExactNumber, ExpressionError, FIELD_BYTES,
    Registry, Scalar, ScalarType, XmpDefinition, expression,
};
use serde::Deserialize;
use serde_json::value::RawValue;
use std::collections::{BTreeMap, BTreeSet};

const REQUEST_BYTES: usize = 65_536;
const DECLARATION_LIMIT: usize = 64;

#[derive(Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
struct Request<'a> {
    version: String,
    registry_revision: String,
    expression: String,
    #[serde(borrow)]
    aliases: Vec<&'a RawValue>,
    #[serde(borrow)]
    parameters: Vec<&'a RawValue>,
    #[serde(borrow)]
    definitions: Vec<&'a RawValue>,
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Alias {
    name: String,
    selector: String,
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Parameter<'a> {
    name: String,
    #[serde(rename = "type")]
    scalar_type: String,
    #[serde(borrow)]
    value: &'a RawValue,
}

#[derive(Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
struct Definition {
    name: String,
    namespace: String,
    local_name: String,
    #[serde(rename = "type")]
    scalar_type: String,
    provenance: String,
    revision: String,
}

pub(super) fn compile(input: &[u8], registry: &Registry) -> Result<CompiledFilter, CompileError> {
    if input.len() > REQUEST_BYTES {
        return Err(CompileError::RequestBytes);
    }
    let input = std::str::from_utf8(input).map_err(|_| CompileError::Utf8)?;
    if input.starts_with('\u{feff}') {
        return Err(CompileError::Bom);
    }
    let request: Request<'_> = object(input)?;
    if request.version != "pure-data-v1" {
        return Err(CompileError::Version);
    }
    if request.registry_revision != registry.revision() {
        return Err(CompileError::RegistryMismatch);
    }

    let groups = [
        ("aliases", request.aliases.len()),
        ("parameters", request.parameters.len()),
        ("definitions", request.definitions.len()),
    ];
    for (group, count) in groups {
        if count > DECLARATION_LIMIT {
            return Err(CompileError::DeclarationCount { group });
        }
    }
    let mut names = BTreeSet::new();
    let mut aliases = BTreeMap::new();
    for (index, raw) in request.aliases.into_iter().enumerate() {
        let error = |kind| declaration_error("aliases", index, kind);
        let alias: Alias = object(raw.get()).map_err(|_| error(DeclarationError::InvalidShape))?;
        reserve_name(registry, &mut names, &alias.name).map_err(error)?;
        if !registry.0.selectors.contains(&alias.selector) {
            return Err(error(DeclarationError::InvalidSelector));
        }
        aliases.insert(alias.name, alias.selector);
    }
    let mut parameters = BTreeMap::new();
    for (index, raw) in request.parameters.into_iter().enumerate() {
        let error = |kind| declaration_error("parameters", index, kind);
        let parameter: Parameter<'_> =
            object(raw.get()).map_err(|_| error(DeclarationError::InvalidShape))?;
        reserve_name(registry, &mut names, &parameter.name).map_err(error)?;
        let value =
            scalar(parameter.value.get()).map_err(|_| error(DeclarationError::InvalidScalar))?;
        let kind = scalar_type(&parameter.scalar_type)
            .ok_or_else(|| error(DeclarationError::InvalidShape))?;
        if !matches_type(&value, kind) {
            return Err(error(DeclarationError::TypeMismatch));
        }
        parameters.insert(parameter.name, value);
    }
    let mut expanded_names = BTreeSet::new();
    let mut definitions = Vec::with_capacity(request.definitions.len());
    for (index, raw) in request.definitions.into_iter().enumerate() {
        let error = |kind| declaration_error("definitions", index, kind);
        let definition: Definition =
            object(raw.get()).map_err(|_| error(DeclarationError::InvalidShape))?;
        reserve_name(registry, &mut names, &definition.name).map_err(error)?;
        if !valid_namespace(&definition.namespace)
            || !valid_name(&definition.local_name)
            || !bounded_nonempty(&definition.provenance)
            || !valid_revision(&definition.revision)
        {
            return Err(error(DeclarationError::InvalidDefinition));
        }
        let kind = scalar_type(&definition.scalar_type)
            .ok_or_else(|| error(DeclarationError::InvalidShape))?;
        let expanded = (definition.namespace.clone(), definition.local_name.clone());
        if registry.0.builtin_expanded_names.contains(&expanded) || !expanded_names.insert(expanded)
        {
            return Err(error(DeclarationError::ExpandedNameCollision));
        }
        definitions.push(XmpDefinition {
            name: definition.name,
            namespace: definition.namespace,
            local_name: definition.local_name,
            scalar_type: kind,
            provenance: definition.provenance,
            revision: definition.revision,
        });
    }
    let expression = expression::parse(
        &request.expression,
        &registry.0.selectors,
        &aliases,
        &parameters,
    )?;
    Ok(CompiledFilter {
        registry: registry.clone(),
        definitions,
        expression,
    })
}

fn object<'de, T: Deserialize<'de>>(text: &'de str) -> Result<T, CompileError> {
    // Serde's struct decoder also accepts positional arrays. The v1 shape is
    // strictly an object, and RawValue retains that distinction for declarations.
    if !text
        .trim_start_matches([' ', '\t', '\r', '\n'])
        .starts_with('{')
    {
        return Err(CompileError::Json { line: 1, column: 1 });
    }
    serde_json::from_str(text).map_err(|error| CompileError::Json {
        line: error.line(),
        column: error.column(),
    })
}

fn declaration_error(group: &'static str, index: usize, kind: DeclarationError) -> CompileError {
    CompileError::Declaration { group, index, kind }
}

fn reserve_name(
    registry: &Registry,
    names: &mut BTreeSet<String>,
    name: &str,
) -> Result<(), DeclarationError> {
    if !valid_name(name) {
        return Err(DeclarationError::InvalidName);
    }
    if registry.0.builtin_names.contains(name) || !names.insert(name.to_owned()) {
        return Err(DeclarationError::NameCollision);
    }
    Ok(())
}

fn scalar_type(value: &str) -> Option<ScalarType> {
    match value {
        "string" => Some(ScalarType::String),
        "number" => Some(ScalarType::Number),
        "integer" => Some(ScalarType::Integer),
        "boolean" => Some(ScalarType::Boolean),
        "null" => Some(ScalarType::Null),
        _ => None,
    }
}

fn valid_name(value: &str) -> bool {
    value.len() <= 64
        && value
            .as_bytes()
            .first()
            .is_some_and(u8::is_ascii_alphabetic)
        && value
            .bytes()
            .all(|byte| byte.is_ascii_alphanumeric() || byte == b'_')
}

pub(super) fn valid_revision(value: &str) -> bool {
    value.len() <= 64
        && value
            .as_bytes()
            .first()
            .is_some_and(u8::is_ascii_alphanumeric)
        && value
            .bytes()
            .all(|byte| byte.is_ascii_alphanumeric() || b"_.-".contains(&byte))
}

pub(super) fn bounded_nonempty(value: &str) -> bool {
    !value.is_empty() && value.len() <= FIELD_BYTES
}

pub(super) fn valid_namespace(value: &str) -> bool {
    if !bounded_nonempty(value) {
        return false;
    }
    let Some((scheme, suffix)) = value.split_once(':') else {
        return false;
    };
    if !scheme
        .as_bytes()
        .first()
        .is_some_and(u8::is_ascii_alphabetic)
        || !scheme
            .bytes()
            .all(|byte| byte.is_ascii_alphanumeric() || b"+.-".contains(&byte))
        || suffix.is_empty()
    {
        return false;
    }
    let mut bytes = suffix.bytes();
    while let Some(byte) = bytes.next() {
        if byte == b'%' {
            if !(0..2).all(|_| bytes.next().is_some_and(|digit| digit.is_ascii_hexdigit())) {
                return false;
            }
        } else if !(byte.is_ascii_alphanumeric() || b"._~:/?#[]@!$&'()*+,;=-".contains(&byte)) {
            return false;
        }
    }
    true
}

pub(super) fn scalar(token: &str) -> Result<Scalar, ExpressionError> {
    match token {
        "true" => Ok(Scalar::Boolean(true)),
        "false" => Ok(Scalar::Boolean(false)),
        "null" => Ok(Scalar::Null),
        string if string.starts_with('"') => string_value(string).map(Scalar::String),
        number => ExactNumber::from_json_number(number)
            .map(Scalar::Number)
            .ok_or(ExpressionError::Number),
    }
}

pub(super) fn string_value(token: &str) -> Result<String, ExpressionError> {
    let value: String = serde_json::from_str(token).map_err(|_| ExpressionError::String)?;
    if value.len() > FIELD_BYTES {
        return Err(ExpressionError::String);
    }
    Ok(value)
}

fn matches_type(scalar: &Scalar, kind: ScalarType) -> bool {
    match (scalar, kind) {
        (Scalar::Number(number), ScalarType::Integer) => number.is_integer_literal(),
        (Scalar::String(_), ScalarType::String)
        | (Scalar::Number(_), ScalarType::Number)
        | (Scalar::Boolean(_), ScalarType::Boolean)
        | (Scalar::Null, ScalarType::Null) => true,
        _ => false,
    }
}
