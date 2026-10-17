//! Bounded data-only translation for the twelve frozen MIG forms.
//! This module has no filesystem, process, environment or native-read boundary.
use serde::{
    Deserialize, Deserializer, Serialize,
    de::{self, SeqAccess, Visitor},
};
use serde_json::{Value, json};
use std::{
    fmt,
    io::{self, Read, Write},
};

pub const MAX_DOCUMENT_BYTES: usize = 131_072;
const MAX_REPORT_BYTES: usize = 1_048_576;

#[derive(Deserialize, Serialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
struct Invocation {
    schema_version: u32,
    kind: String,
    id: String,
    path_style: String,
    working_directory: String,
    #[serde(deserialize_with = "arguments")]
    arguments: Vec<String>,
}

fn arguments<'de, D: Deserializer<'de>>(decoder: D) -> Result<Vec<String>, D::Error> {
    struct Arguments;
    impl<'de> Visitor<'de> for Arguments {
        type Value = Vec<String>;
        fn expecting(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
            f.write_str("1..128 bounded argument strings")
        }
        fn visit_seq<A: SeqAccess<'de>>(self, mut seq: A) -> Result<Self::Value, A::Error> {
            let mut values = Vec::new();
            let mut total = 0;
            while let Some(value) = seq.next_element::<String>()? {
                total += value.len();
                if values.len() == 128 || !bounded(&value, 32768) || total > 65536 {
                    return Err(de::Error::custom("argument bounds"));
                }
                values.push(value);
            }
            if values.is_empty() {
                return Err(de::Error::custom("empty arguments"));
            }
            Ok(values)
        }
    }
    decoder.deserialize_seq(Arguments)
}

fn bounded(value: &str, maximum: usize) -> bool {
    !value.is_empty() && value.len() <= maximum && !value.contains('\0')
}

fn absolute_directory(style: &str, cwd: &str) -> bool {
    match style {
        "posix" => cwd.starts_with('/') && !cwd.starts_with("//"),
        "windows" => {
            let bytes = cwd.as_bytes();
            if bytes.len() >= 3 && bytes[0].is_ascii_alphabetic() && &bytes[1..3] == b":\\" {
                return true;
            }
            if let Some(unc) = cwd.strip_prefix("\\\\") {
                let mut components = unc.split('\\');
                return [components.next(), components.next()]
                    .iter()
                    .all(|part| part.is_some_and(|p| !p.is_empty() && !p.contains('/')));
            }
            false
        }
        _ => false,
    }
}

fn decode(bytes: &[u8]) -> Result<Invocation, &'static str> {
    if bytes.len() > MAX_DOCUMENT_BYTES {
        return Err("Invocation exceeds document byte limit.");
    }
    let text = std::str::from_utf8(bytes).map_err(|_| "Invocation is not valid UTF-8.")?;
    if text.starts_with('\u{feff}') {
        return Err("UTF-8 BOM is not permitted.");
    }
    let (mut depth, mut quoted, mut escaped) = (0usize, false, false);
    for ch in text.chars() {
        if quoted {
            if escaped {
                escaped = false;
            } else if ch == '\\' {
                escaped = true;
            } else if ch == '"' {
                quoted = false;
            }
        } else if ch == '"' {
            quoted = true;
        } else if ch == '[' || ch == '{' {
            depth += 1;
            if depth > 8 {
                return Err("Invocation exceeds container depth limit.");
            }
        } else if ch == ']' || ch == '}' {
            depth = depth.saturating_sub(1);
        }
    }
    let invocation: Invocation = serde_json::from_slice(bytes)
        .map_err(|_| "Invocation JSON shape, members, strings or argument bounds are invalid.")?;
    if invocation.schema_version != 1
        || invocation.kind != "legacy-invocation"
        || !bounded(&invocation.id, 128)
        || !bounded(&invocation.working_directory, 32768)
        || !absolute_directory(&invocation.path_style, &invocation.working_directory)
        || !invocation.arguments[0].starts_with('-')
    {
        return Err(
            "Invocation version, kind, ID, absolute directory or token-array contract is invalid.",
        );
    }
    Ok(invocation)
}

fn empty_report() -> Value {
    json!({"schemaVersion":1,"kind":"legacy-translation-report","profile":"mig-001-012-inert-v1",
        "request":null,"status":"malformed","exitStatus":2,"accounting":[],"findings":[],
        "differences":[],"questions":[],"prerequisites":[],
        "suggestion":{"state":"withheld","executable":null,"arguments":null,"workingDirectory":null,"operation":null,"authority":"none-report-only"},
        "effects":{"mediaOpened":false,"referencedFilesOpened":false,"commandsExecuted":false,"authorizationGranted":false}})
}

fn malformed(reason: &str) -> Value {
    let mut report = empty_report();
    report["findings"] =
        json!([{"id":"F1","code":"MALFORMED_INVOCATION","tokenIndices":[],"message":reason}]);
    report
}

fn accounting(args: &[String]) -> Value {
    let read = args.len() == 3 && args[0] == "-n" && args[1] == "-ISO";
    let mut after_terminator = false;
    let mut previous_option = false;
    Value::Array(args.iter().enumerate().map(|(index, token)| {
        let separate = index > 0 && previous_option && !after_terminator && ["-tagsFromFile","-stay_open","-@","-config","-if"].contains(&args[index-1].as_str());
        let role = if (read && index == 2) || after_terminator { "operand" }
            else if separate { "option-value" } else if token == "--" { "terminator" }
            else if token == "-unknown" { "unknown" } else if token.starts_with('-') { "option" } else { "operand" };
        previous_option = role == "option";
        if role == "terminator" { after_terminator = true; }
        let cut = if role == "option" { token.find('=').map(|offset|offset+1).or_else(|| (token == "-G1").then_some(2)) } else { None };
        let parts = if let Some(cut) = cut {
            let scalar_cut = token[..cut].chars().count();
            json!([{"start":0,"end":scalar_cut,"kind":"syntax","text":&token[..cut]},
                {"start":scalar_cut,"end":token.chars().count(),"kind":"value","text":&token[cut..]}])
        } else {
            json!([{"start":0,"end":token.chars().count(),"kind":if separate {"value"} else if role == "option" || role == "terminator" {"syntax"} else {"literal"},"text":token}])
        };
        json!({"index":index,"token":token,"role":role,"valueOwner":if cut.is_some(){Some(index)}else if separate{Some(index-1)}else{None},"parts":parts,"findingIds":["F1"]})
    }).collect())
}

fn translate(invocation: Invocation) -> Value {
    // An immutable compile-time table, extracted from #0129's twelve reports.
    // Runtime input can never select a file, a module, an executable or a template.
    let templates: Vec<Value> =
        serde_json::from_str(include_str!("inert_translation_templates.json"))
            .expect("compiled finite report table");
    let args = &invocation.arguments;
    let accounts = accounting(args);
    let matched = templates
        .iter()
        .cloned()
        .enumerate()
        .find(|(case, report)| {
            let pattern = report["request"]["arguments"]
                .as_array()
                .expect("compiled arguments");
            if pattern.len() != args.len() {
                return false;
            }
            pattern
                .iter()
                .zip(args)
                .enumerate()
                .all(|(index, (expected, actual))| {
                    // Only literal operands vary. Separate opaque values and attached
                    // option values retain their exact frozen spelling in this profile.
                    let operand = report["accounting"][index]["role"] == "operand";
                    (operand && (*case == 0 || !actual.starts_with('-')))
                        || expected.as_str() == Some(actual)
                })
        });
    let mut report = if let Some((_, report)) = matched {
        report
    } else {
        let mut report = empty_report();
        let known = [
            "-n",
            "-ISO",
            "-XMP-xmp:Label=",
            "-XMP-xmp:Label=Reviewed",
            "-Subject+=travel",
            "-DateTimeOriginal+=1",
            "-tagsFromFile",
            "-all:all",
            "-json=edits.json",
            "-r",
            "-j",
            "-G1",
            "-overwrite_original",
            "-stay_open",
            "-@",
            "-config",
            "-if",
            "-all=",
            "--",
        ];
        let unsupported_feature = args.iter().any(|a| {
            a.starts_with('-') && !["-n", "-ISO", "-r", "-j", "-G1", "--"].contains(&a.as_str())
        });
        let duplicate = args
            .iter()
            .enumerate()
            .any(|(index, a)| a.starts_with('-') && a != "--" && args[..index].contains(a));
        let unknown = args.iter().enumerate().any(|(index, a)| {
            (accounts[index]["role"] == "option" || accounts[index]["role"] == "unknown")
                && !known.contains(&a.as_str())
        });
        let code = if unknown {
            "UNKNOWN_TOKEN"
        } else if duplicate {
            "DUPLICATE_OPTION"
        } else {
            "ORDER_OUTSIDE_FINITE_PROFILE"
        };
        report["status"] = json!(if duplicate && !unsupported_feature {
            "needs-input"
        } else {
            "unsupported"
        });
        report["exitStatus"] = json!(1);
        report["findings"] = json!([{"id":"F1","code":code,"tokenIndices":(0..args.len()).collect::<Vec<_>>(),"message":"Invocation is outside the twelve frozen forms; no option is dropped, reordered or executed."}]);
        report["prerequisites"] = json!([{"code":code,"requirement":"Resolve duplicate/unknown tokens or supply an independently qualified finite mapping; referenced files remain unopened.","owner":"#0130; LG-001"}]);
        // Preserve known missing operations even when an interaction or an
        // unknown token prevents selecting a complete frozen form.
        for template in templates.iter().skip(1) {
            let options = template["request"]["arguments"]
                .as_array()
                .expect("compiled options");
            if options.iter().any(|option| {
                option.as_str().is_some_and(|option| {
                    option.starts_with('-') && option != "-" && args.iter().any(|arg| arg == option)
                })
            }) {
                for prerequisite in template["prerequisites"]
                    .as_array()
                    .expect("compiled prerequisites")
                {
                    if !report["prerequisites"]
                        .as_array()
                        .expect("prerequisites")
                        .contains(prerequisite)
                    {
                        report["prerequisites"]
                            .as_array_mut()
                            .expect("prerequisites")
                            .push(prerequisite.clone());
                    }
                }
            }
        }
        report
    };
    // All entries reference F1, which in every frozen report covers every token.
    report["accounting"] = accounts;
    if report["suggestion"]["state"] == "usable" {
        report["suggestion"]["arguments"][7] = json!(args[2]);
        report["suggestion"]["workingDirectory"] = json!(invocation.working_directory);
    }
    report["request"] = serde_json::to_value(invocation).expect("bounded invocation serialization");
    report
}

/// Translate a bounded document without opening any path carried in the data.
/// Malformed data produces a complete status-2 report, never prefix translation.
pub fn document(bytes: &[u8]) -> Value {
    match decode(bytes) {
        Ok(invocation) => translate(invocation),
        Err(reason) => malformed(reason),
    }
}

/// Read at most the frozen byte limit plus one sentinel byte. Input/output I/O
/// errors remain transport failures; no complete report or status is claimed.
pub fn run(input: &mut impl Read, output: &mut impl Write) -> io::Result<u8> {
    let mut bytes = Vec::with_capacity(MAX_DOCUMENT_BYTES + 1);
    input
        .take((MAX_DOCUMENT_BYTES + 1) as u64)
        .read_to_end(&mut bytes)?;
    let report = document(&bytes);
    let status = report["exitStatus"].as_u64().expect("fixed report status") as u8;
    let mut encoded = serde_json::to_vec(&report).map_err(io::Error::other)?;
    if encoded.len() + 1 > MAX_REPORT_BYTES {
        return Err(io::Error::other("translation report byte limit"));
    }
    encoded.push(b'\n');
    output.write_all(&encoded)?;
    output.flush()?;
    Ok(status)
}
#[cfg(test)]
mod tests {
    use super::*;
    fn base() -> Value {
        json!({"schemaVersion":1,"kind":"legacy-invocation","id":"test","pathStyle":"posix","workingDirectory":"/missing","arguments":["-n","-ISO","missing.cr3"]})
    }
    fn report(value: &Value) -> Value {
        document(&serde_json::to_vec(value).unwrap())
    }
    #[test]
    fn frozen_twelve_reports_match_the_independent_specification() {
        let vectors: Value = serde_json::from_str(include_str!(
            "../docs/legacy-compatibility/inert-translation/vectors.v1.json"
        ))
        .unwrap();
        for case in vectors["reports"].as_array().unwrap().iter().take(12) {
            assert_eq!(
                report(&case["report"]["request"]),
                case["report"],
                "{}",
                case["id"]
            );
        }
    }
    #[test]
    fn malformed_preflight_never_echoes_or_accounts_a_prefix() {
        let mut cases = vec![
            vec![0xff],
            b"\xef\xbb\xbf{}".to_vec(),
            b"{}{}".to_vec(),
            b"[]".to_vec(),
            b"{\"id\":\"x\",\"id\":\"x\"}".to_vec(),
            b"[[[[[[[[[0]]]]]]]]]".to_vec(),
            vec![b' '; MAX_DOCUMENT_BYTES + 1],
            b"{\"id\":\"\\ud800\"}".to_vec(),
        ];
        for (key, value) in [
            ("extra", json!(1)),
            ("schemaVersion", json!(true)),
            ("schemaVersion", json!(2)),
            ("kind", json!("other")),
            ("id", json!("x".repeat(129))),
            ("id", json!("é".repeat(65))),
            ("workingDirectory", json!(".")),
            ("workingDirectory", json!("C:\\mismatch")),
            ("arguments", json!([])),
            ("arguments", json!([null])),
            ("arguments", json!([""])),
            ("arguments", json!(["exiftool", "-n"])),
            ("arguments", json!(["-n\0"])),
            ("arguments", json!([format!("-{}", "x".repeat(32768))])),
            ("arguments", json!(vec!["-n"; 129])),
            (
                "arguments",
                json!([
                    format!("-{}", "x".repeat(32767)),
                    "x".repeat(32768),
                    "x".to_string()
                ]),
            ),
        ] {
            let mut value_base = base();
            value_base[key] = value;
            cases.push(serde_json::to_vec(&value_base).unwrap());
        }
        for bytes in cases {
            let result = document(&bytes);
            assert_eq!(result["exitStatus"], 2);
            assert!(result["request"].is_null());
            assert_eq!(result["accounting"], json!([]));
            assert_eq!(result["suggestion"]["state"], "withheld");
        }
        for cwd in [
            "C:relative",
            "\\relative",
            "\\\\server",
            "\\\\server\\",
            "//server/share",
        ] {
            let mut value = base();
            value["pathStyle"] = json!("windows");
            value["workingDirectory"] = json!(cwd);
            assert_eq!(report(&value)["exitStatus"], 2);
        }
        // A duplicate in a fully otherwise valid object must fail, including a same-value duplicate.
        let bytes = serde_json::to_string(&base())
            .unwrap()
            .replacen('{', "{\"id\":\"test\",", 1);
        assert_eq!(document(bytes.as_bytes())["exitStatus"], 2);
    }
    #[test]
    fn exact_boundaries_unicode_literals_and_directories_remain_data() {
        for cwd in ["C:\\missing", "\\\\server\\share", "\\\\server\\share\\raw"] {
            let mut value = base();
            value["pathStyle"] = json!("windows");
            value["workingDirectory"] = json!(cwd);
            assert_eq!(report(&value)["exitStatus"], 0);
        }
        for operand in ["-photo.cr3", "$HOME/*.cr3", "$(literal);literal", "é📷.cr3"] {
            let mut value = base();
            value["arguments"][2] = json!(operand);
            let result = report(&value);
            assert_eq!(result["suggestion"]["arguments"][7], operand);
            assert_eq!(
                result["accounting"][2]["parts"][0]["end"],
                operand.chars().count()
            );
        }
        let mut value = base();
        value["id"] = json!("é".repeat(64));
        value["workingDirectory"] = json!(format!("/{}", "x".repeat(32767)));
        assert_eq!(report(&value)["exitStatus"], 0);
        let mut value = base();
        value["arguments"] = json!([format!("-{}", "x".repeat(32767)), "x".repeat(32768)]);
        assert_eq!(report(&value)["exitStatus"], 1);
        let mut value = base();
        value["arguments"] = json!(vec!["-n"; 128]);
        assert_eq!(report(&value)["exitStatus"], 1);
        let mut bytes = serde_json::to_vec(&base()).unwrap();
        bytes.resize(MAX_DOCUMENT_BYTES, b' ');
        assert_eq!(document(&bytes)["exitStatus"], 0);
    }
    #[test]
    fn unknown_order_and_duplicate_never_form_usable_suggestions() {
        for (args, status, code) in [
            (vec!["-unknown", "missing"], "unsupported", "UNKNOWN_TOKEN"),
            (
                vec!["-n", "-n", "-ISO", "missing"],
                "needs-input",
                "DUPLICATE_OPTION",
            ),
            (
                vec!["-ISO", "-n", "missing"],
                "unsupported",
                "ORDER_OUTSIDE_FINITE_PROFILE",
            ),
            (
                vec!["-n", "-ISO", "--", "-missing"],
                "unsupported",
                "ORDER_OUTSIDE_FINITE_PROFILE",
            ),
            (
                vec!["-all=", "-all=", "missing"],
                "unsupported",
                "DUPLICATE_OPTION",
            ),
        ] {
            let mut value = base();
            value["arguments"] = json!(args);
            let result = report(&value);
            assert_eq!(result["status"], status);
            assert_eq!(result["findings"][0]["code"], code);
            assert_eq!(result["suggestion"]["state"], "withheld");
        }
    }
    #[test]
    fn unqualified_terminators_and_option_like_values_do_not_forge_value_owners() {
        for args in [
            vec!["-n", "--", "-config", "opaque"],
            vec!["-config", "-if", "opaque"],
        ] {
            let mut value = base();
            value["arguments"] = json!(args);
            let result = report(&value);
            assert_eq!(result["suggestion"]["state"], "withheld");
            for account in result["accounting"].as_array().unwrap() {
                if let Some(owner) = account["valueOwner"].as_u64() {
                    assert_eq!(result["accounting"][owner as usize]["role"], "option");
                }
            }
        }
    }

    struct Fails;
    impl Read for Fails {
        fn read(&mut self, _: &mut [u8]) -> io::Result<usize> {
            Err(io::ErrorKind::Other.into())
        }
    }
    impl Write for Fails {
        fn write(&mut self, _: &[u8]) -> io::Result<usize> {
            Err(io::ErrorKind::BrokenPipe.into())
        }
        fn flush(&mut self) -> io::Result<()> {
            Err(io::ErrorKind::BrokenPipe.into())
        }
    }
    #[test]
    fn actual_io_failures_and_bounded_input_have_explicit_outcomes() {
        let mut output = Vec::new();
        assert!(run(&mut Fails, &mut output).is_err());
        assert!(output.is_empty());
        assert_eq!(
            run(
                &mut serde_json::to_vec(&base()).unwrap().as_slice(),
                &mut Fails
            )
            .unwrap_err()
            .kind(),
            io::ErrorKind::BrokenPipe
        );
        let bytes = vec![b' '; MAX_DOCUMENT_BYTES + 100];
        let mut input = bytes.as_slice();
        assert_eq!(run(&mut input, &mut Vec::new()).unwrap(), 2);
        assert_eq!(input.len(), 99);
    }
}
