use imageinfo::{
    VERSION,
    cli::{self, Invocation, OutputFormat},
    output::{ErrorEnvelope, VersionInfo},
};
use std::{
    io::{self, Write},
    process::ExitCode,
    time::{SystemTime, UNIX_EPOCH},
};

fn main() -> ExitCode {
    let mut stdout = io::stdout().lock();
    let mut stderr = io::stderr().lock();
    let status = match cli::parse(std::env::args_os()) {
        Ok(Invocation::Help(help)) => write_result(&mut stdout, help.as_bytes()),
        Ok(Invocation::Version(format)) => match format {
            OutputFormat::Text => write_result(
                &mut stdout,
                format!("imageinfo {VERSION}\nMedia reading is not implemented yet.\n").as_bytes(),
            ),
            OutputFormat::Json => write_json(&mut stdout, &VersionInfo::default()),
        },
        Ok(Invocation::Read(request)) => report_error(
            &mut stdout,
            &mut stderr,
            request.output,
            Some("metadata read"),
            "CAPABILITY_UNSUPPORTED",
            "Media reading is not implemented in this foundation. No input was opened.".into(),
            1,
        ),
        Err(error) => report_error(
            &mut stdout,
            &mut stderr,
            error.output,
            None,
            error.code,
            error.message,
            2,
        ),
    };
    match status {
        Ok(code) => ExitCode::from(code),
        Err(error) => {
            let _ = writeln!(
                stderr,
                "OUTPUT_INCOMPLETE: Could not finish output ({:?}).",
                error.kind()
            );
            ExitCode::from(1)
        }
    }
}

fn write_result(writer: &mut impl Write, bytes: &[u8]) -> io::Result<u8> {
    writer.write_all(bytes)?;
    writer.flush()?;
    Ok(0)
}

fn write_json(writer: &mut impl Write, record: &impl serde::Serialize) -> io::Result<u8> {
    serde_json::to_writer(&mut *writer, record).map_err(|error| {
        io::Error::new(
            error.io_error_kind().unwrap_or(io::ErrorKind::InvalidData),
            error,
        )
    })?;
    writer.write_all(b"\n")?;
    writer.flush()?;
    Ok(0)
}

fn report_error(
    stdout: &mut impl Write,
    stderr: &mut impl Write,
    format: OutputFormat,
    operation: Option<&'static str>,
    code: &'static str,
    message: String,
    status: u8,
) -> io::Result<u8> {
    let safe_message = escape_controls(&message);
    if format == OutputFormat::Json {
        let timestamp = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap_or_default()
            .as_nanos();
        let request_id = format!("req-{}-{timestamp}", std::process::id());
        write_json(
            stdout,
            &ErrorEnvelope::new(request_id, operation, code, safe_message.clone(), status),
        )?;
    }
    writeln!(stderr, "{code}: {safe_message}")?;
    Ok(status)
}

// User-controlled option text must not become terminal control sequences. Help
// and diagnostics are always plain text, including when --color always is given.
fn escape_controls(text: &str) -> String {
    const MAX_BYTES: usize = 4096;
    let mut output = String::with_capacity(text.len().min(MAX_BYTES));
    for ch in text.chars() {
        let rendered = if ch.is_control() && ch != '\n' && ch != '\t' {
            ch.escape_default().to_string()
        } else {
            ch.to_string()
        };
        if output.len() + rendered.len() > MAX_BYTES - 3 {
            output.push_str("...");
            break;
        }
        output.push_str(&rendered);
    }
    output
}

#[cfg(test)]
mod tests {
    use super::*;
    struct FailingWriter;
    impl Write for FailingWriter {
        fn write(&mut self, _: &[u8]) -> io::Result<usize> {
            Err(io::ErrorKind::BrokenPipe.into())
        }
        fn flush(&mut self) -> io::Result<()> {
            Ok(())
        }
    }

    #[test]
    fn text_and_json_output_propagate_transport_failure() {
        assert_eq!(
            write_result(&mut FailingWriter, b"help")
                .unwrap_err()
                .kind(),
            io::ErrorKind::BrokenPipe
        );
        assert_eq!(
            write_json(&mut FailingWriter, &VersionInfo::default())
                .unwrap_err()
                .kind(),
            io::ErrorKind::BrokenPipe
        );
    }
}
