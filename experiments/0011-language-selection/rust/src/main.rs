//! Disposable #0011 feasibility probe. Not an imageinfo parser or CLI.
#![forbid(unsafe_code)]
use clap::{Arg, ArgAction, Command, builder::OsStringValueParser};
use serde::{Deserialize, Serialize};
use std::{
    ffi::OsString,
    fs::File,
    io::{self, Cursor, Read, Seek, SeekFrom},
};

fn command(policy: bool) -> Command {
    fn options(c: Command, policy: bool) -> Command {
        let mut c = c
            .disable_help_subcommand(true)
            .disable_help_flag(policy)
            // Keep scope matches separate so duplicate scalar options cannot be lost
            // when clap propagates global values between parent and child commands.
            .arg(
                Arg::new("output")
                    .long("output")
                    .value_parser(["json", "text"]),
            )
            .arg(Arg::new("tag").long("tag").action(ArgAction::Append));
        if policy {
            // Ordinary Help actions terminate parsing early. The accepted contract requires
            // malformed options to win over help regardless of their position.
            c = c.arg(Arg::new("help").long("help").action(ArgAction::SetTrue));
        }
        c
    }
    options(Command::new("probe"), policy).subcommand(
        options(
            Command::new("metadata").about("Metadata operations"),
            policy,
        )
        .subcommand(
            options(Command::new("read").about("Read metadata"), policy).arg(
                Arg::new("inputs")
                    .num_args(0..)
                    .value_parser(OsStringValueParser::new()),
            ),
        ),
    )
}

// Only a bare command path is rewritten; option values and operands after -- stay literal.
fn normalize_help(args: &[OsString]) -> Vec<OsString> {
    let mut out = args.to_vec();
    if args.iter().any(|a| a == "--") {
        return out;
    }
    let words = &args[1..];
    let path = if words.first().is_some_and(|s| s == "help") {
        Some(&words[1..])
    } else if words.last().is_some_and(|s| s == "help") {
        Some(&words[..words.len() - 1])
    } else {
        None
    };
    if let Some(path) = path {
        let tree = command(true);
        let mut node = &tree;
        for part in path {
            let Some(next) = part.to_str().and_then(|p| node.find_subcommand(p)) else {
                return out;
            };
            node = next;
        }
        out = vec![args[0].clone()];
        out.extend_from_slice(path);
        out.push("--help".into());
    }
    out
}

fn parse(args: &[OsString]) -> Result<(bool, Vec<OsString>, String), ()> {
    let mut tree = command(true);
    let matches = tree
        .clone()
        .try_get_matches_from(normalize_help(args))
        .map_err(|_| ())?;
    let mut m = &matches;
    let mut node = &mut tree;
    let mut requested_help = false;
    let mut output_count = 0;
    loop {
        requested_help |= m.get_flag("help");
        output_count += usize::from(m.get_one::<String>("output").is_some());
        if let Some((name, child)) = m.subcommand() {
            node = node.find_subcommand_mut(name).unwrap();
            m = child;
        } else {
            break;
        }
    }
    if output_count > 1 {
        return Err(());
    }
    let help = requested_help || node.has_subcommands();
    let inputs: Vec<OsString> = m
        .try_get_many::<OsString>("inputs")
        .ok()
        .flatten()
        .map(|v| v.cloned().collect())
        .unwrap_or_default();
    if !help && inputs.is_empty() {
        return Err(());
    }
    Ok((help, inputs, node.render_help().to_string()))
}

fn scan<R: Read + Seek>(reader: &mut R, length: u64, budget: usize) -> io::Result<usize> {
    let bad = || io::Error::new(io::ErrorKind::InvalidData, "invalid or limited header");
    let mut offset = 0u64;
    let mut count = 0;
    while offset < length {
        if count == budget || length - offset < 8 {
            return Err(bad());
        }
        reader.seek(SeekFrom::Start(offset))?;
        let mut header = [0; 8];
        reader.read_exact(&mut header)?;
        let short = u32::from_be_bytes(header[..4].try_into().unwrap());
        let (size, min) = match short {
            0 => (length - offset, 8),
            1 => {
                if length - offset < 16 {
                    return Err(bad());
                }
                let mut wide = [0; 8];
                reader.read_exact(&mut wide)?;
                (u64::from_be_bytes(wide), 16)
            }
            n => (u64::from(n), 8),
        };
        if size < min || size > length - offset {
            return Err(bad());
        }
        offset = offset.checked_add(size).ok_or_else(bad)?;
        count += 1;
    }
    Ok(count)
}

#[derive(Debug, PartialEq, Serialize, Deserialize)]
struct ValueProbe {
    integer: String,
    rational: [String; 2],
    float_bits: String,
    occurrences: Vec<String>,
}

fn main() {
    let cases: &[(&[&str], bool)] = &[
        (&["probe"], true),
        (&["probe", "metadata"], true),
        (&["probe", "help"], true),
        (&["probe", "metadata", "help"], true),
        (&["probe", "metadata", "--help"], true),
        (&["probe", "help", "metadata", "read"], true),
        (&["probe", "metadata", "read", "help"], true),
        (&["probe", "metadata", "read", "--help"], true),
        (&["probe", "metadata", "read"], false),
        (&["probe", "metadata", "read", "--help", "--bogus"], false),
        (&["probe", "metadata", "read", "--bogus", "--help"], false),
        (
            &["probe", "metadata", "read", "--output", "bad", "--help"],
            false,
        ),
        (
            &[
                "probe", "metadata", "read", "--output", "json", "--output", "json", "x",
            ],
            false,
        ),
        (
            &[
                "probe", "--output", "json", "metadata", "read", "--output", "text", "x",
            ],
            false,
        ),
        (
            &[
                "probe", "metadata", "read", "--tag", "ISO", "--tag", "Model", "x",
            ],
            true,
        ),
        (
            &["probe", "--output", "json", "metadata", "read", "x"],
            true,
        ),
        (&["probe", "metadata", "read", "--output=json", "x"], true),
        (&["probe", "metadata", "read", "--", "help"], true),
        (&["probe", "metadata", "read", "--", "-photo.cr3"], true),
        (&["probe", "metadata", "read", "--", "写真 🦆.cr3"], true),
        (&["probe", "metadata", "read", "--out", "json", "x"], false),
    ];
    let mut failures = Vec::new();
    for (index, (argv, expected)) in cases.iter().enumerate() {
        let args: Vec<OsString> = argv.iter().map(OsString::from).collect();
        if parse(&args).is_ok() != *expected {
            failures.push(index + 1);
        }
    }
    let argv = |a: &[&str]| a.iter().map(OsString::from).collect::<Vec<_>>();
    assert_eq!(
        parse(&argv(&["probe", "metadata", "read", "--", "help"]))
            .unwrap()
            .1,
        vec![OsString::from("help")]
    );
    let h1 = parse(&argv(&["probe", "metadata", "read", "help"])).unwrap();
    let h2 = parse(&argv(&["probe", "metadata", "read", "--help"])).unwrap();
    assert!(h1.0 && h2.0 && h1.2 == h2.2 && !h1.2.contains('\u{1b}'));
    let stock =
        command(false).try_get_matches_from(["probe", "metadata", "read", "--help", "--bogus"]);
    let stock_help_short_circuits =
        stock.is_err_and(|e| e.kind() == clap::error::ErrorKind::DisplayHelp);
    let v = ValueProbe {
        integer: u64::MAX.to_string(),
        rational: ["1".into(), "0".into()],
        float_bits: "8000000000000000".into(),
        occurrences: vec!["ISO".into(), "ISO".into()],
    };
    assert_eq!(
        serde_json::from_str::<ValueProbe>(&serde_json::to_string(&v).unwrap()).unwrap(),
        v
    );
    let malformed: Vec<Vec<u8>> = vec![
        vec![0; 7],
        vec![0, 0, 0, 4, b'f', b'r', b'e', b'e'],
        vec![0, 0, 0, 20, b'f', b'r', b'e', b'e'],
        [
            vec![0, 0, 0, 1, b'f', b'r', b'e', b'e'],
            u64::MAX.to_be_bytes().to_vec(),
        ]
        .concat(),
    ];
    for data in &malformed {
        assert!(scan(&mut Cursor::new(data), data.len() as u64, 32).is_err());
    }
    let valid = vec![0, 0, 0, 8, b'f', b'r', b'e', b'e'];
    assert_eq!(scan(&mut Cursor::new(&valid), 8, 1).unwrap(), 1);
    assert!(scan(&mut Cursor::new(&valid), 8, 0).is_err());
    let mut lengths = Vec::new();
    for path in std::env::args_os().skip(1) {
        let mut f = File::open(path).unwrap();
        let n = f.metadata().unwrap().len();
        lengths.push(scan(&mut f, n, 4096).unwrap());
    }
    println!(
        "{}",
        serde_json::json!({"cli_cases":cases.len(),"cli_failed_cases":failures,"help_equivalence_and_literal_operand_checks":true,"stock_help_short_circuits":stock_help_short_circuits,"exact_wire_roundtrip":true,"header_cases":6,"private_inputs":lengths.len(),"private_top_level_box_counts":lengths,"production_capabilities":0})
    );
    assert!(failures.is_empty(), "policy probe failures");
}
