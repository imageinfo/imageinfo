use std::{fs::File, io, mem::size_of, os::windows::io::AsRawHandle};
use windows_sys::Win32::Storage::FileSystem::{
    FILE_DISPOSITION_INFO, FileDispositionInfo, SetFileInformationByHandle,
};

pub fn mark_owned_file(file: &File) -> io::Result<()> {
    let disposition = FILE_DISPOSITION_INFO { DeleteFile: true };
    // SAFETY: caller retains a proven exclusively created owned marker, validates
    // live guards and calls only before publication. Restart reuse additionally
    // requires trusted caller identities and confirmed stop before publication;
    // editable transaction records alone never select this object for deletion.
    // The OS requires DELETE access
    // (missing access must fail; there is no pathname fallback). Exact
    // SDK layout/size and borrowed handle survive this synchronous call. This
    // sets disposition on that object, never a path from a record or enumeration.
    if unsafe {
        SetFileInformationByHandle(
            file.as_raw_handle(),
            FileDispositionInfo,
            std::ptr::from_ref(&disposition).cast(),
            size_of::<FILE_DISPOSITION_INFO>() as u32,
        )
    } == 0
    {
        return Err(io::Error::last_os_error());
    }
    Ok(())
}
