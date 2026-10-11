use super::{Error, Limits, Result};
use std::io::{Read, Seek, SeekFrom};

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Range {
    pub offset: u64,
    pub length: u64,
}

impl Range {
    pub fn checked(offset: u64, length: u64, end: u64) -> Result<Self> {
        if offset.checked_add(length).is_none_or(|value| value > end) {
            return Err(Error::invalid("Byte range exceeds its address space"));
        }
        Ok(Self { offset, length })
    }
    pub fn end(self) -> u64 {
        self.offset + self.length
    }
}

pub struct Source<R> {
    pub reader: R,
    pub length: u64,
    pub bytes_read: u64,
    pub limits: Limits,
}

impl<R: Read + Seek> Source<R> {
    pub fn new(mut reader: R, limits: Limits) -> Result<Self> {
        let length = reader.seek(SeekFrom::End(0))?;
        Ok(Self {
            reader,
            length,
            bytes_read: 0,
            limits,
        })
    }
    pub fn read(&mut self, range: Range) -> Result<Vec<u8>> {
        Range::checked(range.offset, range.length, self.length)?;
        let next = self
            .bytes_read
            .checked_add(range.length)
            .ok_or_else(|| Error::limit("Metadata read budget overflow"))?;
        if next > self.limits.metadata_bytes || range.length > self.limits.block_bytes {
            return Err(Error::limit("Metadata byte budget exceeded"));
        }
        let count = usize::try_from(range.length)
            .map_err(|_| Error::limit("Block cannot fit this platform"))?;
        let mut data = Vec::new();
        data.try_reserve_exact(count)
            .map_err(|_| Error::limit("Cannot reserve bounded metadata buffer"))?;
        data.resize(count, 0);
        self.reader.seek(SeekFrom::Start(range.offset))?;
        self.reader.read_exact(&mut data)?;
        self.bytes_read = next;
        Ok(data)
    }
    pub fn bytes<const N: usize>(&mut self, offset: u64) -> Result<[u8; N]> {
        let data = self.read(Range::checked(offset, N as u64, self.length)?)?;
        data.try_into()
            .map_err(|_| Error::invalid("Short fixed-width field"))
    }
}

pub fn slice(data: &[u8], offset: usize, count: usize) -> Result<&[u8]> {
    let end = offset
        .checked_add(count)
        .ok_or_else(|| Error::invalid("Field size overflow"))?;
    data.get(offset..end)
        .ok_or_else(|| Error::invalid("Truncated field"))
}
pub fn be32(data: &[u8], offset: usize) -> Result<u32> {
    Ok(u32::from_be_bytes(
        slice(data, offset, 4)?
            .try_into()
            .map_err(|_| Error::invalid("Short integer"))?,
    ))
}
pub fn be64(data: &[u8], offset: usize) -> Result<u64> {
    Ok(u64::from_be_bytes(
        slice(data, offset, 8)?
            .try_into()
            .map_err(|_| Error::invalid("Short integer"))?,
    ))
}
pub fn le16(data: &[u8], offset: usize) -> Result<u16> {
    Ok(u16::from_le_bytes(
        slice(data, offset, 2)?
            .try_into()
            .map_err(|_| Error::invalid("Short integer"))?,
    ))
}
pub fn le32(data: &[u8], offset: usize) -> Result<u32> {
    Ok(u32::from_le_bytes(
        slice(data, offset, 4)?
            .try_into()
            .map_err(|_| Error::invalid("Short integer"))?,
    ))
}
