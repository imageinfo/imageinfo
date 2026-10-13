//! Fixed-layout SDK request with stable async storage and cancellation ownership.
use std::{
    cell::UnsafeCell,
    fs::File,
    io,
    mem::size_of,
    os::windows::io::{AsRawHandle, FromRawHandle, OwnedHandle},
    ptr,
};
use windows_sys::Win32::{
    Foundation::*,
    Storage::FileSystem::ReadFile,
    System::{IO::*, Ioctl::*, Threading::*},
};

fn event() -> io::Result<OwnedHandle> {
    // SAFETY: no security/name pointers; a manual-reset unnamed event is owned.
    let raw = unsafe { CreateEventW(ptr::null(), 1, 0, ptr::null()) };
    if raw.is_null() {
        return Err(io::Error::last_os_error());
    }
    // SAFETY: successful API transfers one real handle.
    Ok(unsafe { OwnedHandle::from_raw_handle(raw) })
}
struct Request {
    input: REQUEST_OPLOCK_INPUT_BUFFER,
    output: REQUEST_OPLOCK_OUTPUT_BUFFER,
    overlapped: OVERLAPPED,
}
pub struct Oplock {
    file: File,
    event: OwnedHandle,
    // Box keeps every kernel-visible address stable across moves of the owner.
    // UnsafeCell permits foreign asynchronous writes while methods borrow the
    // owner; completion, not a Rust reference, synchronizes later output reads.
    // Private storage is not read or moved while the asynchronous request is live.
    state: Box<UnsafeCell<Request>>,
    pending: bool,
    completion: Option<serde_json::Value>,
}
impl Oplock {
    pub fn request(file: File, level: u32) -> io::Result<Self> {
        let event = event()?;
        let state = Box::new(UnsafeCell::new(Request {
            input: REQUEST_OPLOCK_INPUT_BUFFER {
                StructureVersion: REQUEST_OPLOCK_CURRENT_VERSION as u16,
                StructureLength: size_of::<REQUEST_OPLOCK_INPUT_BUFFER>() as u16,
                RequestedOplockLevel: level,
                Flags: REQUEST_OPLOCK_INPUT_FLAG_REQUEST,
            },
            output: REQUEST_OPLOCK_OUTPUT_BUFFER::default(),
            overlapped: OVERLAPPED {
                hEvent: event.as_raw_handle(),
                ..Default::default()
            },
        }));
        // SAFETY: initialized SDK layouts, exact lengths and stable boxed storage.
        // File/event live until cancellation/completion; the input is retained too.
        let success = unsafe {
            DeviceIoControl(
                file.as_raw_handle(),
                FSCTL_REQUEST_OPLOCK,
                ptr::addr_of!((*state.get()).input).cast(),
                size_of::<REQUEST_OPLOCK_INPUT_BUFFER>() as u32,
                ptr::addr_of_mut!((*state.get()).output).cast(),
                size_of::<REQUEST_OPLOCK_OUTPUT_BUFFER>() as u32,
                ptr::null_mut(),
                ptr::addr_of_mut!((*state.get()).overlapped),
            )
        };
        let error = io::Error::last_os_error();
        if success != 0 || error.raw_os_error() != Some(ERROR_IO_PENDING as i32) {
            // A granted oplock must pend; synchronous completion is not a grant.
            return Err(if success != 0 {
                io::Error::other("OPLOCK_NOT_PENDING")
            } else {
                error
            });
        }
        Ok(Self {
            file,
            event,
            state,
            pending: true,
            completion: None,
        })
    }
    pub fn observe(&mut self) -> io::Result<serde_json::Value> {
        if let Some(value) = &self.completion {
            return Ok(value.clone());
        }
        // SAFETY: live event; zero wait does not dereference request storage.
        match unsafe { WaitForSingleObject(self.event.as_raw_handle(), 0) } {
            WAIT_TIMEOUT => return Ok(serde_json::json!({"broken":false})),
            WAIT_OBJECT_0 => {}
            _ => return Err(io::Error::last_os_error()),
        }
        let mut count = 0;
        // SAFETY: exact request pointer and file, after its event signals. Only
        // successful completion permits reading the async output below.
        if unsafe {
            GetOverlappedResult(
                self.file.as_raw_handle(),
                ptr::addr_of!((*self.state.get()).overlapped),
                &mut count,
                0,
            )
        } == 0
        {
            return Err(io::Error::last_os_error());
        }
        self.pending = false;
        // SAFETY: completion above ends the kernel's access to this cell.
        let output = unsafe { (*self.state.get()).output };
        if count < size_of::<REQUEST_OPLOCK_OUTPUT_BUFFER>() as u32
            || output.StructureVersion != REQUEST_OPLOCK_CURRENT_VERSION as u16
            || output.StructureLength < size_of::<REQUEST_OPLOCK_OUTPUT_BUFFER>() as u16
        {
            return Err(io::Error::other("OPLOCK_OUTPUT_LAYOUT"));
        }
        let value = serde_json::json!({"broken":true,"originalLevel":output.OriginalOplockLevel,"newLevel":output.NewOplockLevel,"flags":output.Flags,"ackRequired":output.Flags & REQUEST_OPLOCK_OUTPUT_FLAG_ACK_REQUIRED != 0});
        self.completion = Some(value.clone());
        Ok(value)
    }
}
impl Drop for Oplock {
    fn drop(&mut self) {
        if self.pending {
            let mut count = 0;
            // SAFETY: cancel only this exact request. Even ERROR_NOT_FOUND can
            // mean racing completion; drain it before storage/handles are freed.
            // A process watchdog bounds pathological driver waits, not this API.
            unsafe {
                CancelIoEx(
                    self.file.as_raw_handle(),
                    ptr::addr_of!((*self.state.get()).overlapped),
                );
                GetOverlappedResult(
                    self.file.as_raw_handle(),
                    ptr::addr_of!((*self.state.get()).overlapped),
                    &mut count,
                    1,
                );
            }
        }
        // Dropping the file acknowledges a completed break by closing the holder.
    }
}
pub fn marker_matches(file: &File) -> io::Result<bool> {
    let event = event()?;
    let overlap = UnsafeCell::new(OVERLAPPED {
        hEvent: event.as_raw_handle(),
        ..Default::default()
    });
    let mut bytes = vec![0u8; 65537];
    let mut count = 0;
    // SAFETY: independent zero-offset read; initialized bounded buffer, separate
    // event/request. No storage can leave scope until completion is drained.
    let ok = unsafe {
        ReadFile(
            file.as_raw_handle(),
            bytes.as_mut_ptr(),
            bytes.len() as u32,
            ptr::null_mut(),
            overlap.get(),
        )
    };
    if ok == 0 && io::Error::last_os_error().raw_os_error() != Some(ERROR_IO_PENDING as i32) {
        return Err(io::Error::last_os_error());
    }
    // SAFETY: drain this read on the exact file before accessing buffer/stack.
    if unsafe { GetOverlappedResult(file.as_raw_handle(), overlap.get(), &mut count, 1) } == 0 {
        return Err(io::Error::last_os_error());
    }
    Ok(count == 65536 && bytes[..65536].iter().all(|b| *b == b'3'))
}
