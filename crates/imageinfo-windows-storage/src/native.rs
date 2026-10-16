//! Isolated SDK boundary; see ../SDK-REVIEW.md. Only OS-returned handles and allocations enter ownership.
use std::{
    ffi::c_void,
    fs::File,
    io,
    mem::{offset_of, size_of},
    os::windows::{
        ffi::OsStrExt,
        io::{AsRawHandle, FromRawHandle, OwnedHandle},
    },
    path::Path,
    ptr,
};
use windows_sys::Wdk::{
    Foundation::OBJECT_ATTRIBUTES,
    Storage::FileSystem::{
        FILE_CREATE, FILE_DIRECTORY_FILE, FILE_OPEN_REPARSE_POINT, FILE_SYNCHRONOUS_IO_NONALERT,
        NtCreateFile,
    },
};
use windows_sys::Win32::{
    Foundation::*,
    Security::{Authorization::*, *},
    Storage::FileSystem::*,
    System::{IO::IO_STATUS_BLOCK, Threading::*},
};

struct LocalMemory(*mut c_void);
impl Drop for LocalMemory {
    fn drop(&mut self) {
        // SAFETY: allocations come only from documented LocalFree-compatible APIs.
        unsafe {
            LocalFree(self.0);
        }
    }
}
fn wide(path: &Path) -> io::Result<Vec<u16>> {
    let mut v: Vec<_> = path.as_os_str().encode_wide().collect();
    if v.is_empty() || v.len() > 240 || v.contains(&0) {
        return Err(io::Error::new(
            io::ErrorKind::Unsupported,
            "WIDE_NAME_UNVERIFIED",
        ));
    }
    v.push(0);
    Ok(v)
}
fn sddl(descriptor: *mut c_void) -> io::Result<String> {
    let mut text = ptr::null_mut();
    let mut count = 0;
    // SAFETY: caller retains the OS-owned descriptor throughout this synchronous
    // conversion. Output variables are live; returned text is separately owned.
    if unsafe {
        ConvertSecurityDescriptorToStringSecurityDescriptorW(
            descriptor,
            1,
            OWNER_SECURITY_INFORMATION | DACL_SECURITY_INFORMATION,
            &mut text,
            &mut count,
        )
    } == 0
    {
        return Err(io::Error::last_os_error());
    }
    let _allocation = LocalMemory(text.cast());
    if text.is_null() || count == 0 || count > 32768 {
        return Err(io::Error::other("SECURITY_TEXT_BOUND"));
    }
    // SAFETY: successful API reports allocated UTF-16 count, including NUL.
    let units = unsafe { std::slice::from_raw_parts(text, count as usize) };
    let end = units
        .iter()
        .position(|u| *u == 0)
        .ok_or_else(|| io::Error::other("SECURITY_TEXT_TERMINATOR"))?;
    String::from_utf16(&units[..end]).map_err(|_| io::Error::other("SECURITY_TEXT_ENCODING"))
}
fn current_sid() -> io::Result<String> {
    let mut raw = ptr::null_mut();
    // SAFETY: borrowed current-process pseudo-handle is never closed here.
    if unsafe { OpenProcessToken(GetCurrentProcess(), TOKEN_QUERY, &mut raw) } == 0 {
        return Err(io::Error::last_os_error());
    }
    // SAFETY: successful token query transfers one real owned handle.
    let token = unsafe { OwnedHandle::from_raw_handle(raw) };
    let mut size = 0;
    // SAFETY: NULL/zero is the documented sizing query, not a readable buffer.
    let first = unsafe {
        GetTokenInformation(
            token.as_raw_handle(),
            TokenUser,
            ptr::null_mut(),
            0,
            &mut size,
        )
    };
    if first != 0
        || io::Error::last_os_error().raw_os_error() != Some(ERROR_INSUFFICIENT_BUFFER as i32)
        || size < size_of::<TOKEN_USER>() as u32
        || size > 65536
    {
        return Err(io::Error::other("TOKEN_SIZE_UNVERIFIED"));
    }
    let capacity = size;
    let mut buffer = vec![0usize; (size as usize).div_ceil(size_of::<usize>())];
    // SAFETY: aligned initialized storage has the measured capacity; API receives
    // that capacity and the same query-only token handle, with live output length.
    if unsafe {
        GetTokenInformation(
            token.as_raw_handle(),
            TokenUser,
            buffer.as_mut_ptr().cast(),
            capacity,
            &mut size,
        )
    } == 0
    {
        return Err(io::Error::last_os_error());
    }
    if size > capacity || size < size_of::<TOKEN_USER>() as u32 {
        return Err(io::Error::other("TOKEN_SIZE_CHANGED"));
    }
    // SAFETY: success initialized an aligned TOKEN_USER within the checked length.
    let sid = unsafe { (*buffer.as_ptr().cast::<TOKEN_USER>()).User.Sid };
    let start = buffer.as_ptr() as usize;
    if (sid as usize) < start || (sid as usize) >= start + size as usize {
        return Err(io::Error::other("TOKEN_SID_BOUND"));
    }
    let mut text = ptr::null_mut();
    // SAFETY: TokenUser supplies a valid SID retained in this live buffer. The
    // converter returns a separately allocated, terminated string.
    if unsafe { ConvertSidToStringSidW(sid, &mut text) } == 0 {
        return Err(io::Error::last_os_error());
    }
    let _text = LocalMemory(text.cast());
    let mut units = Vec::new();
    if text.is_null() {
        return Err(io::Error::other("TOKEN_TEXT_NULL"));
    }
    for i in 0..192 {
        // SAFETY: successful API guarantees a terminated SID string. Reads stop
        // at its terminator, never at unused allocation bytes; SID text is bounded.
        let unit = unsafe { *text.add(i) };
        if unit == 0 {
            return String::from_utf16(&units).map_err(|_| io::Error::other("TOKEN_ENCODING"));
        }
        units.push(unit);
    }
    Err(io::Error::other("TOKEN_TEXT_BOUND"))
}
pub struct PrivateSecurity {
    allocation: LocalMemory,
    canonical: String,
}
impl PrivateSecurity {
    pub fn current() -> io::Result<Self> {
        let sid = current_sid()?;
        let text: Vec<u16> = format!("O:{sid}D:P(A;;FA;;;{sid})")
            .encode_utf16()
            .chain(Some(0))
            .collect();
        let mut descriptor = ptr::null_mut();
        // SAFETY: internally generated terminated SDDL; returned descriptor is
        // owned until all creation/check operations finish, then LocalFree releases it.
        if unsafe {
            ConvertStringSecurityDescriptorToSecurityDescriptorW(
                text.as_ptr(),
                1,
                &mut descriptor,
                ptr::null_mut(),
            )
        } == 0
        {
            return Err(io::Error::last_os_error());
        }
        let allocation = LocalMemory(descriptor);
        let canonical = sddl(descriptor)?;
        Ok(Self {
            allocation,
            canonical,
        })
    }
    pub fn check(&self, file: &File) -> io::Result<()> {
        let mut descriptor = ptr::null_mut();
        // SAFETY: live handle includes READ_CONTROL. GetSecurityInfo returns an
        // owned copy; no pointers into a concurrently mutable descriptor escape.
        let code = unsafe {
            GetSecurityInfo(
                file.as_raw_handle(),
                SE_FILE_OBJECT,
                OWNER_SECURITY_INFORMATION | DACL_SECURITY_INFORMATION,
                ptr::null_mut(),
                ptr::null_mut(),
                ptr::null_mut(),
                ptr::null_mut(),
                &mut descriptor,
            )
        };
        if code != 0 {
            return Err(io::Error::from_raw_os_error(code as i32));
        }
        let _copy = LocalMemory(descriptor);
        if sddl(descriptor)? != self.canonical {
            return Err(io::Error::other("PRIVATE_OWNER_OR_DACL_CHANGED"));
        }
        Ok(())
    }
    pub fn create_directory(&self, parent: &File, name: &Path) -> io::Result<File> {
        let mut name = wide(name)?;
        if name[..name.len() - 1]
            .iter()
            .any(|u| [b'\\' as u16, b'/' as u16, b':' as u16].contains(u))
        {
            return Err(io::Error::new(
                io::ErrorKind::Unsupported,
                "DIRECTORY_LEAF_REQUIRED",
            ));
        }
        let mut string = UNICODE_STRING {
            Length: ((name.len() - 1) * 2) as u16,
            MaximumLength: (name.len() * 2) as u16,
            Buffer: name.as_mut_ptr(),
        };
        let attributes = OBJECT_ATTRIBUTES {
            Length: size_of::<OBJECT_ATTRIBUTES>() as u32,
            RootDirectory: parent.as_raw_handle(),
            ObjectName: &mut string,
            Attributes: 0x40,
            SecurityDescriptor: self.allocation.0.cast(),
            SecurityQualityOfService: ptr::null_mut(),
        };
        let mut handle = ptr::null_mut();
        let mut status_block = IO_STATUS_BLOCK::default();
        // SAFETY: checked single leaf, live parent, terminated Unicode name, SD
        // and outputs all survive this synchronous create. FILE_CREATE refuses an
        // existing leaf and returns its actual owned handle, closing create/open
        // races. SYNCHRONIZE matches SYNCHRONOUS_IO_NONALERT; no privilege changes.
        let status = unsafe {
            NtCreateFile(
                &mut handle,
                GENERIC_READ | GENERIC_WRITE | READ_CONTROL | 0x100000,
                &attributes,
                &mut status_block,
                ptr::null(),
                FILE_ATTRIBUTE_DIRECTORY,
                FILE_SHARE_READ | FILE_SHARE_WRITE,
                FILE_CREATE,
                FILE_DIRECTORY_FILE | FILE_SYNCHRONOUS_IO_NONALERT | FILE_OPEN_REPARSE_POINT,
                ptr::null(),
                0,
            )
        };
        // Unexpected pending must not return/drop an OS-owned stack output. This
        // synchronous-only constructor aborts rather than release pending storage.
        if status == 0x103 {
            std::process::abort();
        }
        if status != 0 {
            return Err(io::Error::from_raw_os_error(
                unsafe { RtlNtStatusToDosError(status) } as i32,
            ));
        }
        // SAFETY: successful exclusive create returns a real owned directory handle.
        let file = unsafe { File::from_raw_handle(handle) };
        self.check(&file)?;
        Ok(file)
    }
    pub fn create_file(&self, path: &Path) -> io::Result<File> {
        let name = wide(path)?;
        let attributes = SECURITY_ATTRIBUTES {
            nLength: size_of::<SECURITY_ATTRIBUTES>() as u32,
            lpSecurityDescriptor: self.allocation.0,
            bInheritHandle: 0,
        };
        // SAFETY: bounded terminated path, live descriptor and noninherited
        // outputs. Exclusive creation never replaces an existing object. The
        // actual returned handle has data/name guards effective at creation.
        let handle = unsafe {
            CreateFileW(
                name.as_ptr(),
                GENERIC_READ | GENERIC_WRITE | DELETE | READ_CONTROL,
                FILE_SHARE_READ,
                &attributes,
                CREATE_NEW,
                FILE_FLAG_OPEN_REPARSE_POINT,
                ptr::null_mut(),
            )
        };
        if handle == INVALID_HANDLE_VALUE {
            return Err(io::Error::last_os_error());
        }
        // SAFETY: successful exclusive creation transfers exactly one handle.
        let file = unsafe { File::from_raw_handle(handle) };
        self.check(&file)?;
        Ok(file)
    }
}
pub fn security(file: &File) -> io::Result<String> {
    let mut descriptor = ptr::null_mut();
    // SAFETY: live READ_CONTROL file and owned OS descriptor output; borrowed
    // file stays open and returned descriptor is released by LocalMemory.
    let code = unsafe {
        GetSecurityInfo(
            file.as_raw_handle(),
            SE_FILE_OBJECT,
            OWNER_SECURITY_INFORMATION | DACL_SECURITY_INFORMATION,
            ptr::null_mut(),
            ptr::null_mut(),
            ptr::null_mut(),
            ptr::null_mut(),
            &mut descriptor,
        )
    };
    if code != 0 {
        return Err(io::Error::from_raw_os_error(code as i32));
    }
    let _owned = LocalMemory(descriptor);
    sddl(descriptor)
}
pub fn check_streams(file: &File) -> io::Result<()> {
    check_streams_kind(file, false)
}
pub fn check_directory_streams(file: &File) -> io::Result<()> {
    check_streams_kind(file, true)
}
fn check_streams_kind(file: &File, directory: bool) -> io::Result<()> {
    let mut buffer = vec![0usize; 65536 / size_of::<usize>()];
    // SAFETY: aligned 64 KiB output and live handle. Larger/unavailable stream
    // inventories refuse this marker profile instead of parsing partial results.
    if unsafe {
        GetFileInformationByHandleEx(
            file.as_raw_handle(),
            FileStreamInfo,
            buffer.as_mut_ptr().cast(),
            65536,
        )
    } == 0
    {
        let error = io::Error::last_os_error();
        if directory && error.raw_os_error() == Some(ERROR_HANDLE_EOF as i32) {
            return Ok(());
        }
        return Err(error);
    }
    // SAFETY: success initialized the SDK header inside the aligned output.
    let info = unsafe { &*buffer.as_ptr().cast::<FILE_STREAM_INFO>() };
    if info.NextEntryOffset != 0 || info.StreamNameLength != 14 {
        return Err(io::Error::new(
            io::ErrorKind::Unsupported,
            "NONDEFAULT_STREAM",
        ));
    }
    // SAFETY: the checked 14-byte name follows the header within the 64 KiB buffer.
    let name =
        unsafe { std::slice::from_raw_parts(ptr::addr_of!(info.StreamName).cast::<u16>(), 7) };
    if name != "::$DATA".encode_utf16().collect::<Vec<_>>() {
        return Err(io::Error::new(
            io::ErrorKind::Unsupported,
            "NONDEFAULT_STREAM",
        ));
    }
    Ok(())
}
pub fn filesystem(file: &File) -> io::Result<String> {
    let mut name = [0u16; 32];
    // SAFETY: live directory handle and fixed writable output. Optional outputs
    // are NULL. The filesystem name belongs to this bound volume, not a guessed drive.
    if unsafe {
        GetVolumeInformationByHandleW(
            file.as_raw_handle(),
            ptr::null_mut(),
            0,
            ptr::null_mut(),
            ptr::null_mut(),
            ptr::null_mut(),
            name.as_mut_ptr(),
            name.len() as u32,
        )
    } == 0
    {
        return Err(io::Error::last_os_error());
    }
    let end = name
        .iter()
        .position(|u| *u == 0)
        .ok_or_else(|| io::Error::other("FILESYSTEM_NAME_BOUND"))?;
    String::from_utf16(&name[..end]).map_err(|_| io::Error::other("FILESYSTEM_NAME_ENCODING"))
}
pub fn check_case(file: &File) -> io::Result<()> {
    let mut info = FILE_CASE_SENSITIVE_INFO::default();
    // SAFETY: live directory handle and correctly sized initialized SDK output;
    // unsupported query/flags refuse rather than assuming insensitive lookup.
    if unsafe {
        GetFileInformationByHandleEx(
            file.as_raw_handle(),
            FileCaseSensitiveInfo,
            (&mut info as *mut FILE_CASE_SENSITIVE_INFO).cast(),
            size_of::<FILE_CASE_SENSITIVE_INFO>() as u32,
        )
    } == 0
    {
        return Err(io::Error::last_os_error());
    }
    if info.Flags != 0 {
        return Err(io::Error::new(
            io::ErrorKind::Unsupported,
            "CASE_SENSITIVE_DIRECTORY_UNSUPPORTED",
        ));
    }
    Ok(())
}
pub fn check_local_ntfs(file: &File, path: &Path) -> io::Result<()> {
    let drive = path
        .components()
        .next()
        .ok_or_else(|| io::Error::other("DRIVE_REQUIRED"))?;
    let mut name = drive.as_os_str().encode_wide().collect::<Vec<_>>();
    name.extend([b'\\' as u16, 0]);
    // SAFETY: checked ordinary drive prefix becomes a terminated drive-root path.
    // No device or volume handle is opened. The DOS mapping is an explicit scope
    // premise; privileged mount remapping is outside this primitive boundary.
    if unsafe { GetDriveTypeW(name.as_ptr()) } != 3 || filesystem(file)? != "NTFS" {
        return Err(io::Error::new(
            io::ErrorKind::Unsupported,
            "LOCAL_FIXED_NTFS_REQUIRED",
        ));
    }
    Ok(())
}
pub fn rename(file: &File, destination: &Path) -> io::Result<()> {
    let name = wide(destination)?;
    let length = (name.len() - 1) * 2;
    let bytes = (offset_of!(FILE_RENAME_INFO, FileName) + name.len() * 2)
        .max(size_of::<FILE_RENAME_INFO>());
    // Byte Vec alignment is insufficient for the SDK header. Native-word storage
    // supplies aligned zeroed padding and bounded space for the UTF-16 tail.
    let mut buffer = vec![0usize; bytes.div_ceil(size_of::<usize>())];
    let info = buffer.as_mut_ptr().cast::<FILE_RENAME_INFO>();
    // SAFETY: pinned SDK layout, aligned initialized storage and bounded tail.
    // Handles survive the synchronous call; Flags=0 forbids replacement. The
    // operation renames the held file, never reopens a mutable candidate pathname.
    let success = unsafe {
        (*info).Anonymous.Flags = 0;
        (*info).RootDirectory = ptr::null_mut();
        (*info).FileNameLength = length as u32;
        ptr::copy_nonoverlapping(
            name.as_ptr(),
            ptr::addr_of_mut!((*info).FileName).cast::<u16>(),
            name.len(),
        );
        SetFileInformationByHandle(
            file.as_raw_handle(),
            FileRenameInfo,
            buffer.as_ptr().cast(),
            bytes as u32,
        )
    };
    if success == 0 {
        return Err(io::Error::last_os_error());
    }
    Ok(())
}

#[cfg(test)]
mod adversarial_tests {
    use super::*;
    use crate::GuardedSource;
    use std::{
        fs::{self, OpenOptions},
        os::windows::fs::OpenOptionsExt,
    };

    // Test-only actor deliberately asks for replacement/POSIX semantics. These
    // flags are never accepted or generated by the production rename helper.
    fn posix_replace(file: &File, destination: &Path) -> io::Result<()> {
        let name = wide(destination)?;
        let bytes = (offset_of!(FILE_RENAME_INFO, FileName) + name.len() * 2)
            .max(size_of::<FILE_RENAME_INFO>());
        let mut buffer = vec![0usize; bytes.div_ceil(size_of::<usize>())];
        let info = buffer.as_mut_ptr().cast::<FILE_RENAME_INFO>();
        // SAFETY: same aligned bounded held-object SDK buffer as rename(); only
        // this authored adversary selects extended replacement flags/class.
        let success = unsafe {
            (*info).Anonymous.Flags =
                windows_sys::Wdk::Storage::FileSystem::FILE_RENAME_REPLACE_IF_EXISTS
                    | windows_sys::Wdk::Storage::FileSystem::FILE_RENAME_POSIX_SEMANTICS;
            (*info).RootDirectory = ptr::null_mut();
            (*info).FileNameLength = ((name.len() - 1) * 2) as u32;
            ptr::copy_nonoverlapping(
                name.as_ptr(),
                ptr::addr_of_mut!((*info).FileName).cast::<u16>(),
                name.len(),
            );
            SetFileInformationByHandle(
                file.as_raw_handle(),
                FileRenameInfoEx,
                buffer.as_ptr().cast(),
                bytes as u32,
            )
        };
        if success == 0 {
            return Err(io::Error::last_os_error());
        }
        Ok(())
    }

    #[test]
    fn posix_replacement_refuses_read_only_source_hold() {
        let base = std::env::current_dir()
            .unwrap()
            .join(".local")
            .join("native-166")
            .join(format!("{}-posix", std::process::id()));
        fs::create_dir_all(&base).unwrap();
        let source = base.join("source.bin");
        let foreign = base.join("foreign.bin");
        fs::write(&source, b"original source").unwrap();
        fs::write(&foreign, b"foreign replacement").unwrap();
        let mut held = GuardedSource::open(&source, 1024).unwrap();
        let actor = OpenOptions::new()
            .access_mode(GENERIC_READ | DELETE)
            .share_mode(7)
            .open(&foreign)
            .unwrap();
        let result = posix_replace(&actor, &source);
        let result_note = match &result {
            Ok(()) => "replacement-succeeded".to_owned(),
            Err(e) => format!("replacement-refused:{:?}", e.raw_os_error()),
        };
        fs::write(base.join("actor-result.txt"), &result_note).unwrap();
        assert_eq!(
            result.unwrap_err().raw_os_error(),
            Some(ERROR_SHARING_VIOLATION as i32)
        );
        held.check().unwrap();
        assert_eq!(fs::read(&source).unwrap(), b"original source");
    }

    #[test]
    fn posix_replacement_refuses_delete_capable_existing_source_hold() {
        let base = std::env::current_dir()
            .unwrap()
            .join(".local")
            .join("native-166")
            .join(format!("{}-posix-delete", std::process::id()));
        fs::create_dir_all(&base).unwrap();
        let source = base.join("source.bin");
        let foreign = base.join("foreign.bin");
        fs::write(&source, b"original source").unwrap();
        fs::write(&foreign, b"foreign replacement").unwrap();
        let held = OpenOptions::new()
            .access_mode(GENERIC_READ | DELETE | READ_CONTROL)
            .share_mode(FILE_SHARE_READ)
            .custom_flags(FILE_FLAG_OPEN_REPARSE_POINT)
            .open(&source)
            .unwrap();
        let actor = OpenOptions::new()
            .access_mode(GENERIC_READ | DELETE)
            .share_mode(7)
            .open(&foreign)
            .unwrap();
        let error = posix_replace(&actor, &source).unwrap_err();
        assert_eq!(error.raw_os_error(), Some(ERROR_SHARING_VIOLATION as i32));
        crate::windows::check_binding(&source, &held).unwrap();
        fs::write(
            base.join("actor-result.txt"),
            "replacement-refused:Some(32)\n",
        )
        .unwrap();
        assert_eq!(fs::read(source).unwrap(), b"original source");
        assert_eq!(fs::read(foreign).unwrap(), b"foreign replacement");
    }

    #[test]
    fn candidate_owner_dacl_actor_is_detected_without_source_acl_changes() {
        let base = std::env::current_dir()
            .unwrap()
            .join(".local")
            .join("native-166")
            .join(format!("{}-dacl", std::process::id()));
        fs::create_dir_all(&base).unwrap();
        let root = crate::PrivateRoot::create(&base.join("transaction")).unwrap();
        let mut candidate = root
            .create_artifact("candidate.bin", b"authored candidate", 1024)
            .unwrap();
        let actor = OpenOptions::new()
            .access_mode(WRITE_DAC | READ_CONTROL)
            .share_mode(7)
            .open(root.path().join("candidate.bin"))
            .unwrap();
        let sid = current_sid().unwrap();
        let text = format!("O:{sid}D:P(A;OICI;FA;;;{sid})")
            .encode_utf16()
            .chain(Some(0))
            .collect::<Vec<_>>();
        let mut descriptor = ptr::null_mut();
        // SAFETY: test-only internally generated terminated owner-only SDDL;
        // returned descriptor remains live until LocalMemory releases it.
        assert_ne!(
            unsafe {
                ConvertStringSecurityDescriptorToSecurityDescriptorW(
                    text.as_ptr(),
                    1,
                    &mut descriptor,
                    ptr::null_mut(),
                )
            },
            0
        );
        let allocation = LocalMemory(descriptor);
        let mut present = 0;
        let mut defaulted = 0;
        let mut acl = ptr::null_mut();
        // SAFETY: live OS-created descriptor; ACL is borrowed only while owner lives.
        assert_ne!(
            unsafe {
                GetSecurityDescriptorDacl(allocation.0, &mut present, &mut acl, &mut defaulted)
            },
            0
        );
        assert_ne!(present, 0);
        assert!(!acl.is_null());
        // SAFETY: test-owned fresh candidate only, retained WRITE_DAC handle,
        // live owner-only ACL. No source, privilege or token is modified.
        assert_eq!(
            unsafe {
                SetSecurityInfo(
                    actor.as_raw_handle(),
                    SE_FILE_OBJECT,
                    DACL_SECURITY_INFORMATION | PROTECTED_DACL_SECURITY_INFORMATION,
                    ptr::null_mut(),
                    ptr::null_mut(),
                    acl,
                    ptr::null_mut(),
                )
            },
            0
        );
        assert!(candidate.check(&root).is_err());
        drop(actor);
        drop(candidate);
        drop(root);
        assert_eq!(
            fs::read(base.join("transaction/candidate.bin")).unwrap(),
            b"authored candidate"
        );
    }
}
