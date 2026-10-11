use super::{Metadata, Occurrence, READER_REVISION, Range, Value};
use serde_json::{Value as Json, json};

fn range_resource(id: &str, range: Range, media: Option<&str>) -> Json {
    json!({"id":id,"byteLength":range.length.to_string(),"mediaType":media,"sha256":null,"content":{"kind":"source-ranges","ranges":[{"space":"source","ref":"src-raw","offset":range.offset.to_string(),"length":range.length.to_string()}]}})
}
fn native_value(value: &Value) -> Json {
    match value {
        Value::Integer(n) => json!({"kind":"integer","decimal":n.to_string()}),
        Value::Rational(n, d) => {
            json!({"kind":"rational","numerator":n.to_string(),"denominator":d.to_string()})
        }
        Value::Text(s) => json!({"kind":"string","text":s}),
        Value::Binary(_) => json!(null),
    }
}

impl Metadata {
    /// Serialize at the external boundary; native offsets/integers stay numeric.
    pub fn snapshot(
        &self,
        id: &str,
        display_path: &str,
        selected: &[usize],
        include_display: bool,
    ) -> Json {
        let mut resources = Vec::new();
        let mut occurrences = Vec::new();
        let mut issues = Vec::new();
        for &index in selected {
            let occurrence = &self.occurrences[index];
            let occurrence_id = format!("occ-{index}");
            let resource_id = if matches!(occurrence.value, Value::Binary(_)) {
                let preview = self
                    .previews
                    .iter()
                    .position(|p| p.range == occurrence.range)
                    .expect("Reader-produced binary occurrence has its resource");
                format!("preview-{preview}")
            } else {
                let id = format!("value-{index}");
                resources.push(range_resource(&id, occurrence.range, None));
                id
            };
            let invalid = matches!(occurrence.value, Value::Rational(_, 0));
            let issue_id = format!("invalid-{index}");
            if invalid {
                issues.push(json!({"id":issue_id,"code":"ZERO_DENOMINATOR","severity":"error","message":"Stored rational has a zero denominator","occurrenceRefs":[occurrence_id],"documentRefs":["doc-raw"]}));
            }
            let raw = json!({"state":"present","value":if matches!(occurrence.value,Value::Binary(_)){json!({"kind":"binary","resourceRef":resource_id})}else{native_value(&occurrence.value)}});
            let normalized = if invalid {
                json!({"state":"invalid","code":"ZERO_DENOMINATOR","detail":"Cannot interpret a zero-denominator rational"})
            } else {
                raw.clone()
            };
            let display = if include_display && !invalid {
                json!({"state":"present","text":occurrence.value.display(occurrence.name),"locale":"en","timeZone":null,"formatterRef":"native-r5-display-v1"})
            } else {
                json!({"state":"unavailable","reason":if invalid{"Invalid stored rational"}else{"Not requested"}})
            };
            let unit = match occurrence.name {
                "ExposureTime" => Some("seconds"),
                "FNumber" => Some("f-number"),
                "FocalLength" => Some("mm"),
                "ImageWidth" | "ImageHeight" | "PixelXDimension" | "PixelYDimension" => {
                    Some("pixels")
                }
                _ => None,
            };
            occurrences.push(json!({"id":occurrence_id,"documentRef":"doc-raw","tag":{"namespace":occurrence.namespace,"nativeId":occurrence.native_id,"name":occurrence.name,"definitionRef":format!("{READER_REVISION}:{}:{}",occurrence.namespace,occurrence.native_id)},"groups":[{"axis":"metadata-family","label":occurrence.namespace}],"path":occurrence.path,"ordinal":index,"origin":{"kind":"stored","resourceRef":resource_id,"encoding":occurrence.encoding,"byteOrder":occurrence.order},"values":{"raw":raw,"normalized":normalized,"normalization":{"ruleRef":"identity-exact-stored-value","reversibility":if invalid{"not-applicable"}else{"exact"},"assumptions":[],"dependencies":[],"unit":unit},"display":display},"capabilityRefs":[],"issueRefs":if invalid{vec![issue_id]}else{Vec::<String>::new()}}));
        }
        for (index, preview) in self.previews.iter().enumerate() {
            resources.push(range_resource(
                &format!("preview-{index}"),
                preview.range,
                Some("image/jpeg"),
            ));
        }
        for (index, (range, _)) in self.opaque.iter().enumerate() {
            resources.push(range_resource(
                &format!("opaque-{index}"),
                *range,
                Some("application/octet-stream"),
            ));
        }
        let coverage = vec![
            json!({"id":"coverage-raw","documentRef":"doc-raw","namespace":"*","pathPrefix":[],"state":"partial","reason":"Only the declared R5 read slice is decoded; other fields, embedded metadata and opaque regions are not interpreted. Full-source/resource hashes are not computed by this bounded read."}),
        ];
        json!({"$schema":"https://github.com/imageinfo/imageinfo/raw/main/docs/metadata-model/metadata-contract.schema.json","schemaVersion":1,"kind":"metadata-snapshot","id":id,"basis":"observed","producer":{"modelRevision":"2026-10-10.1","readerRevision":READER_REVISION,"registryRevision":READER_REVISION},"sources":[{"id":"src-raw","role":"raw","displayPath":display_path,"byteLength":self.length.to_string(),"identity":{"kind":"unavailable","reason":"Bounded metadata reading does not hash the complete source; this snapshot cannot authorize mutations."}}],"documents":[{"id":"doc-raw","sourceRef":"src-raw","kind":"raw","format":"CR3","parentDocumentRef":null,"resourceRef":null,"path":[]}],"resources":resources,"occurrences":occurrences,"associations":[],"coverage":coverage,"selections":[],"issues":issues})
    }
}

pub const NAMES: &[&str] = &[
    "ThumbnailImage",
    "PreviewImage",
    "JpgFromRaw",
    "Make",
    "Model",
    "ImageWidth",
    "ImageHeight",
    "ExposureTime",
    "FNumber",
    "ISO",
    "FocalLength",
    "DateTimeOriginal",
    "OffsetTimeOriginal",
    "SubSecTimeOriginal",
    "PixelXDimension",
    "PixelYDimension",
    "CanonFirmwareVersion",
    "CanonModelID",
    "Quality",
    "DualPixelRaw",
];

pub fn select(metadata: &Metadata, tags: &[String]) -> super::Result<Vec<usize>> {
    let specs: Vec<_> = tags
        .iter()
        .map(|tag| selector(tag))
        .collect::<super::Result<_>>()?;
    Ok(metadata
        .occurrences
        .iter()
        .enumerate()
        .filter(|(_, occ)| {
            specs.is_empty()
                || specs.iter().any(|(namespace, name)| {
                    occ.name == *name && namespace.is_none_or(|ns| occ.namespace == ns)
                })
        })
        .map(|(i, _)| i)
        .collect())
}

pub fn selector(tag: &str) -> super::Result<(Option<&'static str>, &'static str)> {
    let (prefix, name) = tag
        .rsplit_once(':')
        .map_or((None, tag), |(prefix, name)| (Some(prefix), name));
    let name = match name {
        "ExifImageWidth" => "PixelXDimension",
        "ExifImageHeight" => "PixelYDimension",
        name => name,
    };
    let canonical = NAMES
        .iter()
        .find(|&&known| known == name)
        .copied()
        .ok_or_else(|| super::Error {
            code: "TAG_UNSUPPORTED",
            message: "Tag is outside the declared read slice; see docs/reader/README.md".into(),
        })?;
    let namespace = match prefix {
        None => None,
        Some("EXIF" | "exif") => Some("exif"),
        Some("Canon" | "canon") => Some("canon"),
        Some("CTMD" | "canon:ctmd") => Some("canon:ctmd"),
        Some("Binary" | "canon:binary") => Some("canon:binary"),
        _ => return Err(super::Error::unsupported("Unknown tag namespace")),
    };
    Ok((namespace, canonical))
}

pub fn text_value(occurrence: &Occurrence) -> String {
    occurrence.value.display(occurrence.name)
}
