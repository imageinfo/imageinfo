//! Recording source shared by independent native reader boundary qualifications.
#![allow(dead_code)]
use std::{
    cell::RefCell,
    io::{self, Cursor, Read, Seek, SeekFrom},
    rc::Rc,
};
#[derive(Clone, Debug, PartialEq, Eq, serde::Serialize)]
pub struct Request {
    pub offset: u64,
    pub requested: usize,
    pub returned: usize,
}
pub type Trace = Rc<RefCell<Vec<Request>>>;
pub struct RecordingSource<'a> {
    cursor: Cursor<&'a [u8]>,
    pub trace: Trace,
}
impl<'a> RecordingSource<'a> {
    pub fn new(bytes: &'a [u8]) -> (Self, Trace) {
        let trace = Rc::new(RefCell::new(Vec::new()));
        (
            Self {
                cursor: Cursor::new(bytes),
                trace: trace.clone(),
            },
            trace,
        )
    }
}
impl Read for RecordingSource<'_> {
    fn read(&mut self, buffer: &mut [u8]) -> io::Result<usize> {
        let offset = self.cursor.position();
        let returned = self.cursor.read(buffer)?;
        self.trace.borrow_mut().push(Request {
            offset,
            requested: buffer.len(),
            returned,
        });
        Ok(returned)
    }
}
impl Seek for RecordingSource<'_> {
    fn seek(&mut self, from: SeekFrom) -> io::Result<u64> {
        self.cursor.seek(from)
    }
}
