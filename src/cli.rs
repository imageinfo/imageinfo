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
}

#[derive(Debug, PartialEq, Eq)]
pub enum Invocation {
    Help(String),
    Version(OutputFormat),
    Read(ReadRequest),
}

#[derive(Debug, PartialEq, Eq)]
pub struct UsageError {
    pub code: &'static str,
    pub message: String,
    /// Available only after the complete argument grammar parsed successfully.
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
        .after_help("This foundation provides help and version reporting. Media reading is not implemented yet.")
        .subcommand(help_command())
        .subcommand(common(Command::new("version").about("Show version and current implementation scope")))
        .subcommand(
            common(Command::new("metadata").about("Inspect camera RAW metadata"))
                .subcommand(help_command())
                .subcommand(
                    common(Command::new("read").about("Read metadata (not implemented yet)"))
                        .subcommand(help_command())
                        .subcommand_precedence_over_arg(true)
                        .arg(Arg::new("tag").long("tag").action(ArgAction::Append).help("Select a tag; repeat to select several"))
                        .arg(Arg::new("values").long("values").value_parser(["raw", "normalized", "display", "all"]).help("Select the metadata value view"))
                        .arg(Arg::new("inputs").value_name("INPUT").num_args(0..).value_parser(OsStringValueParser::new()).help("Literal input paths; use -- before paths named help or starting with -"))
                        .after_help("Unavailable in this build. Inputs are not opened. Use imageinfo metadata read help for this contract."),
                ),
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
    let tree = command();
    let matches = tree
        .clone()
        .try_get_matches_from(args)
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
            // A failed parser has not established a validated output selection. Do
            // not guess it by rescanning argv with another tokenizer.
            output: OutputFormat::Text,
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
                OutputFormat::Text,
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
    if path.is_empty() || path == ["metadata"] {
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
    let tags = current
        .get_many::<String>("tag")
        .map(|items| items.cloned().collect())
        .unwrap_or_default();
    let values = match current.get_one::<String>("values").map(String::as_str) {
        Some("raw") => ValueView::Raw,
        Some("display") => ValueView::Display,
        Some("all") => ValueView::All,
        _ => ValueView::Normalized,
    };
    Ok(Invocation::Read(ReadRequest {
        inputs,
        tags,
        values,
        output,
    }))
}

fn scalar_values<'a>(scopes: &[&'a ArgMatches], name: &str) -> Vec<&'a str> {
    scopes
        .iter()
        .filter_map(|scope| scope.get_one::<String>(name).map(String::as_str))
        .collect()
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
