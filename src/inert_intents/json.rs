use std::{cell::Cell, fmt, marker::PhantomData};

use serde::{
    Deserialize, Deserializer,
    de::{self, DeserializeSeed, MapAccess, SeqAccess, Visitor, value::MapAccessDeserializer},
};

use super::{DecodeError, Edit, ErrorKind, ErrorLocation, Identity, MAX_EDITS, WireValue};

pub(super) fn decode(text: &str) -> Result<Vec<Edit>, DecodeError> {
    let location = Cell::new(ErrorLocation::Input);
    let reason = Cell::new(None);
    let mut parser = serde_json::Deserializer::from_str(text);
    let edits = parser
        .deserialize_map(Document {
            location: &location,
            reason: &reason,
        })
        .map_err(|error| DecodeError {
            location: location.get(),
            kind: reason.get().unwrap_or_else(|| {
                if error.is_data() {
                    ErrorKind::JsonShape
                } else {
                    ErrorKind::JsonSyntax
                }
            }),
        })?;
    parser.end().map_err(|_| DecodeError {
        location: ErrorLocation::Input,
        kind: ErrorKind::JsonSyntax,
    })?;
    Ok(edits)
}

struct Document<'a> {
    location: &'a Cell<ErrorLocation>,
    reason: &'a Cell<Option<ErrorKind>>,
}

#[derive(Deserialize)]
#[serde(field_identifier, rename_all = "camelCase")]
enum Field {
    SchemaVersion,
    Kind,
    Edits,
}

impl<'de> Visitor<'de> for Document<'_> {
    type Value = Vec<Edit>;

    fn expecting(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str("a scalar-v1 JSON object")
    }

    fn visit_map<M: MapAccess<'de>>(self, mut map: M) -> Result<Self::Value, M::Error> {
        let mut version = None;
        let mut kind = None;
        let mut edits = None;
        while let Some(field) = map.next_key()? {
            match field {
                Field::SchemaVersion if version.is_none() => {
                    version = Some(map.next_value::<u32>()?)
                }
                Field::Kind if kind.is_none() => kind = Some(map.next_value::<String>()?),
                Field::Edits if edits.is_none() => {
                    edits = Some(map.next_value_seed(Edits {
                        location: self.location,
                        reason: self.reason,
                    })?);
                }
                Field::SchemaVersion => return Err(de::Error::duplicate_field("schemaVersion")),
                Field::Kind => return Err(de::Error::duplicate_field("kind")),
                Field::Edits => return Err(de::Error::duplicate_field("edits")),
            }
        }
        let version = version.ok_or_else(|| de::Error::missing_field("schemaVersion"))?;
        let kind = kind.ok_or_else(|| de::Error::missing_field("kind"))?;
        if version != 1 || kind != "inert-scalar-intents" {
            self.reason.set(Some(ErrorKind::JsonProfile));
            return Err(de::Error::custom("unexpected scalar intent profile"));
        }
        edits.ok_or_else(|| de::Error::missing_field("edits"))
    }
}

struct Edits<'a> {
    location: &'a Cell<ErrorLocation>,
    reason: &'a Cell<Option<ErrorKind>>,
}

impl<'de> DeserializeSeed<'de> for Edits<'_> {
    type Value = Vec<Edit>;

    fn deserialize<D: Deserializer<'de>>(self, parser: D) -> Result<Self::Value, D::Error> {
        parser.deserialize_seq(self)
    }
}

impl<'de> Visitor<'de> for Edits<'_> {
    type Value = Vec<Edit>;

    fn expecting(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str("a scalar edit array")
    }

    fn visit_seq<S: SeqAccess<'de>>(self, mut sequence: S) -> Result<Self::Value, S::Error> {
        let mut edits = Vec::new();
        loop {
            if edits.len() == MAX_EDITS {
                self.location.set(ErrorLocation::Input);
                if sequence
                    .next_element_seed(RejectExtraEdit(self.reason))?
                    .is_none()
                {
                    return Ok(edits);
                }
                unreachable!("the extra-edit seed always refuses an element");
            }
            self.location.set(ErrorLocation::Row(edits.len() + 1));
            let Some(Object(wire)) = sequence.next_element::<Object<WireEdit>>()? else {
                self.location.set(ErrorLocation::Input);
                return Ok(edits);
            };
            if wire.operation != "set" {
                self.reason.set(Some(ErrorKind::Operation));
                return Err(de::Error::custom("unexpected edit operation"));
            }
            edits.push(Edit {
                identity: Identity {
                    source_key: wire.source_key,
                    snapshot_id: wire.snapshot_id,
                    occurrence_id: wire.occurrence_id,
                    namespace: wire.namespace,
                    native_id: wire.native_id,
                },
                value: wire.value.0,
            });
        }
    }
}

struct RejectExtraEdit<'a>(&'a Cell<Option<ErrorKind>>);

impl<'de> DeserializeSeed<'de> for RejectExtraEdit<'_> {
    type Value = std::convert::Infallible;

    fn deserialize<D: Deserializer<'de>>(self, _: D) -> Result<Self::Value, D::Error> {
        self.0.set(Some(ErrorKind::EditCount));
        Err(de::Error::custom("too many edits"))
    }
}

#[derive(Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
struct WireEdit {
    source_key: String,
    snapshot_id: String,
    occurrence_id: String,
    namespace: String,
    native_id: String,
    operation: String,
    value: Object<WireValue>,
}

// Serde derives can deserialize structs from positional sequences. Require JSON objects.
struct Object<T>(T);

impl<'de, T: Deserialize<'de>> Deserialize<'de> for Object<T> {
    fn deserialize<D: Deserializer<'de>>(parser: D) -> Result<Self, D::Error> {
        struct ObjectVisitor<T>(PhantomData<T>);

        impl<'de, T: Deserialize<'de>> Visitor<'de> for ObjectVisitor<T> {
            type Value = Object<T>;

            fn expecting(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
                f.write_str("an object")
            }

            fn visit_map<M: MapAccess<'de>>(self, map: M) -> Result<Self::Value, M::Error> {
                T::deserialize(MapAccessDeserializer::new(map)).map(Object)
            }
        }

        parser.deserialize_map(ObjectVisitor(PhantomData))
    }
}
