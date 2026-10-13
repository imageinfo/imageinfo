use std::{
    error::Error,
    os::windows::ffi::OsStrExt,
    path::{Component, Path, Prefix},
};
type Result<T> = std::result::Result<T, Box<dyn Error>>;
pub fn marker_path(path: &Path) -> Result<()> {
    let spelling: Vec<u16> = path.as_os_str().encode_wide().collect();
    if !path.is_absolute()
        || spelling.len() > 200
        || spelling.contains(&0)
        || spelling
            .split(|v| *v == 47 || *v == 92)
            .any(|p| p == [46] || p == [46, 46])
    {
        return Err("MARKER_PATH_UNVERIFIED".into());
    }
    for part in path.components() {
        match part {
            Component::Prefix(p) if matches!(p.kind(), Prefix::Disk(_)) => {}
            Component::RootDir => {}
            Component::Normal(name)
                if !name
                    .encode_wide()
                    .any(|u| u < 32 || [58, 42, 63, 34, 60, 62, 124].contains(&u))
                    && !matches!(name.encode_wide().last(), Some(32 | 46)) =>
            {
                let stem = name
                    .to_string_lossy()
                    .split('.')
                    .next()
                    .unwrap_or("")
                    .to_ascii_uppercase();
                if matches!(stem.as_str(), "CON" | "PRN" | "AUX" | "NUL")
                    || (stem.len() == 4
                        && (stem.starts_with("COM") || stem.starts_with("LPT"))
                        && matches!(stem.as_bytes()[3], b'1'..=b'9'))
                {
                    return Err("MARKER_PATH_UNVERIFIED".into());
                }
            }
            _ => return Err("MARKER_PATH_UNVERIFIED".into()),
        }
    }
    if path
        .file_name()
        .is_none_or(|v| !v.to_string_lossy().ends_with(".marker"))
    {
        return Err("MARKER_PATH_UNVERIFIED".into());
    }
    Ok(())
}
