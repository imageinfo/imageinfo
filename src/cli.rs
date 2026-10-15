//! Command definitions and validation shared by help and command dispatch.

use std::{ffi::OsString, path::PathBuf};

use clap::{Arg, ArgAction, ArgMatches, Command, builder::OsStringValueParser, error::ErrorKind};

#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub enum OutputFormat {
    #[default]
    Text,
    Json,
}

#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub enum ValueView {
    #[default]
    Normalized,
    Raw,
    Display,
    All,
}

#[derive(Debug, PartialEq, Eq)]
pub struct ReadRequest {
    pub inputs: Vec<PathBuf>,
    pub tags: Vec<String>,
    pub values: ValueView,
    pub output: OutputFormat,
    pub limits: crate::reader::Limits,
}

#[derive(Debug, PartialEq, Eq)]
pub struct ExtractRequest {
    pub input: PathBuf,
    pub destination: PathBuf,
    pub tag: String,
    pub output: OutputFormat,
    pub dry_run: bool,
    pub limits: crate::reader::Limits,
}

#[derive(Debug, PartialEq, Eq)]
pub struct DatePreviewRequest {
    pub input: PathBuf,
    pub value: String,
    pub offset: Option<u64>,
    pub output: OutputFormat,
}

#[derive(Debug, PartialEq, Eq)]
pub struct PairRequest {
    pub raw: PathBuf,
    pub sidecar: Option<PathBuf>,
    pub output: OutputFormat,
}

#[derive(Debug, PartialEq, Eq)]
pub enum Invocation {
    Help(String),
    Version(OutputFormat),
    Read(ReadRequest),
    BinaryList(ReadRequest),
    Extract(ExtractRequest),
    DatePreview(DatePreviewRequest),
    Pair(PairRequest),
}

#[derive(Debug, PartialEq, Eq)]
pub struct UsageError {
    pub code: &'static str,
    pub message: String,
    /// An unambiguous result selector, including for whole-request syntax errors.
    pub output: OutputFormat,
}

impl std::fmt::Display for UsageError {
    fn fmt(&self, formatter: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(formatter, "{}: {}", self.code, self.message)
    }
}

impl std::error::Error for UsageError {}

/// Build the command tree used for parsing, help and future menu introspection.
pub fn command() -> Command {
    common(Command::new("imageinfo").about("Camera RAW metadata tooling"))
        .after_help("Reads a declared Canon EOS R5 full RAW metadata/preview subset, describes a read-only date intent, and associates explicit existing RAW/sidecar paths. Other cameras, variants, XMP content operations and metadata writes are not supported yet.")
        .subcommand(help_command())
        .subcommand(common(Command::new("version").about("Show version and current implementation scope")))
        .subcommand(
            common(Command::new("metadata").about("Inspect camera RAW metadata"))
                .subcommand(help_command())
                .subcommand(
                    input_options(common(Command::new("read").about("Read the declared R5 metadata subset")))
                        .subcommand(help_command())
                        .subcommand_precedence_over_arg(true)
                        .arg(Arg::new("tag").long("tag").action(ArgAction::Append).help("Select a tag; repeat to select several"))
                        .arg(Arg::new("values").long("values").value_parser(["raw", "normalized", "display", "all"]).help("Select the metadata value view"))
                        .arg(Arg::new("inputs").value_name("INPUT").num_args(0..).value_parser(OsStringValueParser::new()).help("Literal input paths; use -- before paths named help or starting with -"))
                        .after_help("Coverage is partial and explicit. Source bytes are never modified; --tag selects every matching implemented occurrence."),
                ),
        )
        .subcommand(common(Command::new("binary").about("List or extract stored R5 previews"))
            .subcommand(help_command())
            .subcommand(input_options(common(Command::new("list").about("List stored preview resources"))).subcommand(help_command()).subcommand_precedence_over_arg(true).arg(input_argument()))
            .subcommand(input_options(common(Command::new("extract").about("Copy one stored preview to a new destination"))).subcommand(help_command()).subcommand_precedence_over_arg(true).arg(input_argument())
                .arg(Arg::new("tag").long("tag").value_parser(["ThumbnailImage","PreviewImage","JpgFromRaw"]).help("Exactly one named preview"))
                .arg(Arg::new("output-file").long("output-file").value_parser(OsStringValueParser::new()).help("New output path; existing destinations are refused"))
                .arg(Arg::new("dry-run").long("dry-run").action(ArgAction::SetTrue).help("Validate and report extraction without creating an output"))))
        .subcommand(common(Command::new("preview").about("Describe read-only metadata intents"))
            .subcommand(help_command())
            .subcommand(common(Command::new("date-time-original").about("Inspect one existing CMT2 DateTimeOriginal ASCII20 intent"))
                .subcommand(help_command()).subcommand_precedence_over_arg(true)
                .arg(input_argument())
                .arg(Arg::new("value").long("value").help("Exact YYYY:MM:DD HH:MM:SS Gregorian date"))
                .arg(Arg::new("offset").long("offset").value_parser(clap::value_parser!(u64)).help("Assert the existing unique 20-byte allocation's source offset"))
                .after_help("Reports hypothetical changed/preserved bytes and actual admission refusals. Creates no output; never authorizes application or a production storage profile.")))
        .subcommand(common(Command::new("sidecar").about("Inspect explicit RAW/sidecar associations"))
            .subcommand(help_command())
            .subcommand(common(Command::new("pair").about("Associate two explicit existing files without modifying either"))
                .subcommand(help_command()).subcommand_precedence_over_arg(true)
                .arg(input_argument())
                .arg(Arg::new("sidecar").long("sidecar").value_parser(OsStringValueParser::new()).help("Explicit existing sidecar path; no basename selection"))
                .after_help("Missing sidecars, aliases and ambiguous names are refused. Contents are not interpreted. No sidecar is created or synchronized.")))
}

fn input_argument() -> Arg {
    Arg::new("inputs")
        .value_name("INPUT")
        .num_args(0..)
        .value_parser(OsStringValueParser::new())
}
fn input_options(command: Command) -> Command {
    command
        .arg(
            Arg::new("max-bytes")
                .long("max-bytes")
                .value_parser(clap::value_parser!(u64).range(1..=268435456))
                .help("Metadata read byte budget (default 8388608)"),
        )
        .arg(
            Arg::new("max-preview-bytes")
                .long("max-preview-bytes")
                .value_parser(clap::value_parser!(u64).range(1..=1073741824))
                .help("Maximum one-preview size (default 67108864)"),
        )
}

fn common(command: Command) -> Command {
    command
        // Built-in Help actions stop before later syntax errors. Help is a normal
        // flag so CW-002 can validate the whole invocation before dispatch.
        .disable_help_flag(true)
        .disable_help_subcommand(true)
        .disable_version_flag(true)
        .term_width(80)
        .arg(
            Arg::new("help")
                .long("help")
                .action(ArgAction::SetTrue)
                .help("Show help for this command"),
        )
        .arg(
            Arg::new("version-flag")
                .long("version")
                .action(ArgAction::SetTrue)
                .help("Show version after validating arguments"),
        )
        // Do not use clap's global propagation: it can replace a parent's scalar
        // match with a child's value. Retain each scope to detect duplicates.
        .arg(
            Arg::new("output")
                .long("output")
                .value_parser(["text", "json"])
                .help("Result format (help always uses plain text)"),
        )
        .arg(
            Arg::new("color")
                .long("color")
                .value_parser(["auto", "always", "never"])
                .help("Presentation preference; foundation output is plain text"),
        )
        .arg(
            Arg::new("no-interactive")
                .long("no-interactive")
                .action(ArgAction::SetTrue)
                .help("Keep this invocation noninteractive"),
        )
        .arg(
            Arg::new("interactive")
                .long("interactive")
                .action(ArgAction::SetTrue)
                .help("Request guided mode (not implemented yet)"),
        )
}

fn help_command() -> Command {
    common(Command::new("help").about("Show contextual help without opening inputs"))
        .arg(Arg::new("command-path").num_args(0..).value_name("COMMAND"))
}

/// Parse argv, including argv[0], without media, environment or configuration I/O.
pub fn parse<I, T>(args: I) -> Result<Invocation, UsageError>
where
    I: IntoIterator<Item = T>,
    T: Into<OsString> + Clone,
{
    let args: Vec<OsString> = args.into_iter().map(Into::into).collect();
    let tree = command();
    let matches = tree
        .clone()
        .try_get_matches_from(&args)
        .map_err(|error| UsageError {
            code: match error.kind() {
                ErrorKind::InvalidSubcommand => "INVALID_COMMAND",
                ErrorKind::MissingRequiredArgument | ErrorKind::TooFewValues => "MISSING_ARGUMENT",
                _ => "INVALID_OPTION",
            },
            message: format!(
                "{}\nUse the command path shown in Usage followed by help.",
                error
            ),
            output: syntax_output(&args),
        })?;

    let mut scopes = vec![&matches];
    let mut path = Vec::new();
    let mut current = &matches;
    let mut help_path = None;
    while let Some((name, child)) = current.subcommand() {
        scopes.push(child);
        if name == "help" {
            let mut target = path.clone();
            if let Some(parts) = child.get_many::<String>("command-path") {
                target.extend(parts.cloned());
            }
            help_path = Some(target);
            break;
        }
        path.push(name.to_owned());
        current = child;
    }

    let output_values = scalar_values(&scopes, "output");
    let output = if output_values.len() == 1 && output_values[0] == "json" {
        OutputFormat::Json
    } else {
        OutputFormat::Text
    };
    for name in ["output", "color"] {
        if scalar_values(&scopes, name).len() > 1 {
            return Err(usage(
                "INVALID_OPTION",
                format!(
                    "--{name} may be specified only once. See {}.",
                    help_spelling(&path)
                ),
                output,
            ));
        }
    }
    let interactive = scopes.iter().any(|scope| scope.get_flag("interactive"));
    let no_interactive = scopes.iter().any(|scope| scope.get_flag("no-interactive"));
    if interactive && no_interactive {
        return Err(usage(
            "INVALID_OPTION",
            format!(
                "--interactive conflicts with --no-interactive. See {}.",
                help_spelling(&path)
            ),
            output,
        ));
    }

    let requested_help = scopes.iter().any(|scope| scope.get_flag("help"));
    if let Some(target) = help_path {
        return render_help(&tree, &target, output);
    }
    if requested_help {
        return render_help(&tree, &path, output);
    }
    if interactive {
        return Err(usage(
            "INTERACTION_UNAVAILABLE",
            "Guided mode is not implemented yet. Use contextual help and an ordinary command."
                .into(),
            output,
        ));
    }
    if scopes.iter().any(|scope| scope.get_flag("version-flag")) || path == ["version"] {
        return Ok(Invocation::Version(output));
    }
    if path.is_empty()
        || path == ["metadata"]
        || path == ["binary"]
        || path == ["preview"]
        || path == ["sidecar"]
    {
        return render_help(&tree, &path, output);
    }

    let inputs: Vec<PathBuf> = current
        .get_many::<OsString>("inputs")
        .map(|items| items.map(PathBuf::from).collect())
        .unwrap_or_default();
    if inputs.is_empty() {
        return Err(usage(
            "MISSING_ARGUMENT",
            format!(
                "At least one INPUT is required. See {}.",
                help_spelling(&path)
            ),
            output,
        ));
    }
    if inputs.iter().any(|path| path.as_os_str().is_empty()) {
        return Err(usage(
            "INVALID_INPUT",
            "Empty input paths are not allowed.".into(),
            output,
        ));
    }
    if path == ["preview", "date-time-original"] || path == ["sidecar", "pair"] {
        if inputs.len() != 1 {
            return Err(usage(
                "INVALID_INPUT",
                format!(
                    "Exactly one INPUT is required. See {}.",
                    help_spelling(&path)
                ),
                output,
            ));
        }
        if path == ["preview", "date-time-original"] {
            let value = current.get_one::<String>("value").ok_or_else(|| {
                usage(
                    "MISSING_ARGUMENT",
                    "Date preview requires --value. See imageinfo preview date-time-original help."
                        .into(),
                    output,
                )
            })?;
            crate::reader::admission::DateTime::parse(value)
                .map_err(|error| usage(error.code, error.message, output))?;
            return Ok(Invocation::DatePreview(DatePreviewRequest {
                input: inputs[0].clone(),
                value: value.clone(),
                offset: current.get_one::<u64>("offset").copied(),
                output,
            }));
        }
        let sidecar = current.get_one::<OsString>("sidecar");
        if sidecar.is_some_and(|value| value.is_empty()) {
            return Err(usage(
                "INVALID_INPUT",
                "Empty sidecar paths are not allowed.".into(),
                output,
            ));
        }
        return Ok(Invocation::Pair(PairRequest {
            raw: inputs[0].clone(),
            sidecar: sidecar.map(PathBuf::from),
            output,
        }));
    }
    let tags: Vec<String> = current
        .try_get_many::<String>("tag")
        .ok()
        .flatten()
        .map(|items| items.cloned().collect())
        .unwrap_or_default();
    let values = match current
        .try_get_one::<String>("values")
        .ok()
        .flatten()
        .map(String::as_str)
    {
        Some("raw") => ValueView::Raw,
        Some("display") => ValueView::Display,
        Some("all") => ValueView::All,
        _ => ValueView::Normalized,
    };
    let mut limits = crate::reader::Limits::default();
    if let Some(value) = current.get_one::<u64>("max-bytes") {
        limits.metadata_bytes = *value;
    }
    if let Some(value) = current.get_one::<u64>("max-preview-bytes") {
        limits.preview_bytes = *value;
    }
    if path == ["binary", "extract"] {
        if inputs.len() != 1
            || tags.len() != 1
            || current.get_one::<OsString>("output-file").is_none()
        {
            return Err(usage("MISSING_ARGUMENT","Extraction needs one INPUT, --tag and --output-file. See imageinfo binary extract help.".into(),output));
        }
        if current
            .get_one::<OsString>("output-file")
            .is_some_and(|value| value.is_empty())
        {
            return Err(usage(
                "INVALID_INPUT",
                "Empty output paths are not allowed.".into(),
                output,
            ));
        }
        return Ok(Invocation::Extract(ExtractRequest {
            input: inputs[0].clone(),
            destination: PathBuf::from(
                current
                    .get_one::<OsString>("output-file")
                    .expect("Checked required output"),
            ),
            tag: tags[0].clone(),
            output,
            dry_run: current.get_flag("dry-run"),
            limits,
        }));
    }
    let request = ReadRequest {
        inputs,
        tags,
        values,
        output,
        limits,
    };
    if path == ["binary", "list"] {
        Ok(Invocation::BinaryList(request))
    } else {
        Ok(Invocation::Read(request))
    }
}

fn scalar_values<'a>(scopes: &[&'a ArgMatches], name: &str) -> Vec<&'a str> {
    scopes
        .iter()
        .filter_map(|scope| scope.get_one::<String>(name).map(String::as_str))
        .collect()
}

fn syntax_output(args: &[OsString]) -> OutputFormat {
    // Negotiate only the result channel; clap still validates the whole request.
    // The grammar rejects separate hyphen-leading option values, so --output is
    // an option outside `--`, never another option's data. Attached values remain
    // one argv token. Keep that invariant tested when extending the command tree.
    let mut selected = None;
    let mut args = args.iter().skip(1);
    while let Some(arg) = args.next() {
        if arg == "--" {
            break;
        }
        let value = if arg == "--output" {
            args.next().and_then(|value| value.to_str())
        } else if arg.as_encoded_bytes().starts_with(b"--output=") {
            arg.to_str()
                .and_then(|value| value.strip_prefix("--output="))
        } else {
            continue;
        };
        let format = match value {
            Some("json") => OutputFormat::Json,
            Some("text") => OutputFormat::Text,
            _ => return OutputFormat::Text,
        };
        if selected.replace(format).is_some() {
            return OutputFormat::Text;
        }
    }
    selected.unwrap_or_default()
}

fn render_help(
    tree: &Command,
    path: &[String],
    output: OutputFormat,
) -> Result<Invocation, UsageError> {
    let mut node = tree;
    let mut known_path = Vec::new();
    for component in path {
        node = node
            .find_subcommand(component)
            .filter(|node| node.get_name() != "help")
            .ok_or_else(|| {
                usage(
                    "INVALID_COMMAND",
                    format!(
                        "Unknown help component {component:?}. See {}.",
                        help_spelling(&known_path)
                    ),
                    output,
                )
            })?;
        known_path.push(component.clone());
    }
    let mut node = node.clone();
    node = node.bin_name(if path.is_empty() {
        "imageinfo".into()
    } else {
        format!("imageinfo {}", path.join(" "))
    });
    Ok(Invocation::Help(node.render_help().to_string()))
}

fn help_spelling(path: &[String]) -> String {
    if path.is_empty() {
        "imageinfo help".into()
    } else {
        format!("imageinfo {} help", path.join(" "))
    }
}

fn usage(code: &'static str, message: String, output: OutputFormat) -> UsageError {
    UsageError {
        code,
        message,
        output,
    }
}
