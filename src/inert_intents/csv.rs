use super::{DecodeError, Edit, ErrorKind, ErrorLocation, Identity, MAX_EDITS, WireValue};

const HEADER: [&str; 10] = [
    "sourceKey",
    "snapshotId",
    "occurrenceId",
    "namespace",
    "nativeId",
    "valueKind",
    "decimal",
    "numerator",
    "denominator",
    "text",
];

pub(super) fn decode(text: &str) -> Result<Vec<Edit>, DecodeError> {
    let (header, mut remainder) = record(text).map_err(|kind| DecodeError {
        location: ErrorLocation::Input,
        kind,
    })?;
    if header != HEADER {
        return Err(DecodeError {
            location: ErrorLocation::Input,
            kind: ErrorKind::CsvHeader,
        });
    }

    let mut edits = Vec::new();
    while !remainder.is_empty() {
        if edits.len() == MAX_EDITS {
            return Err(DecodeError {
                location: ErrorLocation::Input,
                kind: ErrorKind::EditCount,
            });
        }
        let error = |kind| DecodeError {
            location: ErrorLocation::Row(edits.len() + 1),
            kind,
        };
        let (cells, rest) = record(remainder).map_err(error)?;
        edits.push(edit(cells).map_err(error)?);
        remainder = rest;
    }
    Ok(edits)
}

fn record(mut input: &str) -> Result<([String; 10], &str), ErrorKind> {
    let mut cells = std::array::from_fn(|_| String::new());
    for (index, cell) in cells.iter_mut().enumerate() {
        let (value, remainder) = field(input)?;
        *cell = value;
        let last = index + 1 == HEADER.len();
        match remainder.as_bytes() {
            [b',', ..] if !last => input = &remainder[1..],
            [b'\r', b'\n', ..] if last => return Ok((cells, &remainder[2..])),
            [b',', ..] | [b'\r', b'\n', ..] => return Err(ErrorKind::CsvWidth),
            _ => return Err(ErrorKind::CsvRecordEnding),
        }
    }
    unreachable!("the final field always ends the record or refuses")
}

fn field(input: &str) -> Result<(String, &str), ErrorKind> {
    if let Some(quoted) = input.strip_prefix('"') {
        let mut bytes = quoted.bytes().enumerate().peekable();
        while let Some((index, byte)) = bytes.next() {
            if byte == b'"' {
                if bytes.next_if(|&(_, next)| next == b'"').is_some() {
                    continue;
                }
                let remainder = &quoted[index + 1..];
                if !matches!(remainder.as_bytes(), [] | [b',' | b'\r' | b'\n', ..]) {
                    return Err(ErrorKind::CsvAfterQuote);
                }
                return Ok((quoted[..index].replace("\"\"", "\""), remainder));
            }
        }
        return Err(ErrorKind::CsvQuote);
    }
    let end = input
        .bytes()
        .position(|byte| matches!(byte, b',' | b'\r' | b'\n' | b'"'))
        .unwrap_or(input.len());
    let (value, remainder) = input.split_at(end);
    if remainder.starts_with('"') {
        return Err(ErrorKind::CsvQuote);
    }
    Ok((value.to_owned(), remainder))
}

fn edit(cells: [String; 10]) -> Result<Edit, ErrorKind> {
    let [
        source_key,
        snapshot_id,
        occurrence_id,
        namespace,
        native_id,
        kind,
        decimal,
        numerator,
        denominator,
        text,
    ] = cells;
    let value = match kind.as_str() {
        "integer" if numerator.is_empty() && denominator.is_empty() && text.is_empty() => {
            WireValue::Integer { decimal }
        }
        "rational" if decimal.is_empty() && text.is_empty() => WireValue::Rational {
            numerator,
            denominator,
        },
        "string" if decimal.is_empty() && numerator.is_empty() && denominator.is_empty() => {
            WireValue::String { text }
        }
        "integer" | "rational" | "string" => return Err(ErrorKind::CsvUnusedCell),
        _ => return Err(ErrorKind::ValueKind),
    };
    Ok(Edit {
        identity: Identity {
            source_key,
            snapshot_id,
            occurrence_id,
            namespace,
            native_id,
        },
        value,
    })
}
