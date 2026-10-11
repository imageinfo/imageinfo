use super::{Error, Limits, Result, bounded::slice};
use std::collections::BTreeSet;

#[derive(Clone, Copy, Debug)]
pub enum Order {
    Little,
    Big,
}
impl Order {
    pub fn u16(self, data: &[u8], at: usize) -> Result<u16> {
        let b: [u8; 2] = slice(data, at, 2)?
            .try_into()
            .map_err(|_| Error::invalid("Short TIFF integer"))?;
        Ok(match self {
            Self::Little => u16::from_le_bytes(b),
            Self::Big => u16::from_be_bytes(b),
        })
    }
    pub fn u32(self, data: &[u8], at: usize) -> Result<u32> {
        let b: [u8; 4] = slice(data, at, 4)?
            .try_into()
            .map_err(|_| Error::invalid("Short TIFF integer"))?;
        Ok(match self {
            Self::Little => u32::from_le_bytes(b),
            Self::Big => u32::from_be_bytes(b),
        })
    }
    pub fn name(self) -> &'static str {
        match self {
            Self::Little => "little",
            Self::Big => "big",
        }
    }
}

#[derive(Debug)]
pub struct Entry {
    pub tag: u16,
    pub format: u16,
    pub count: u32,
    pub offset: usize,
    pub length: usize,
    pub ifd: usize,
    pub ordinal: usize,
}

pub fn entries(data: &[u8], limits: Limits) -> Result<(Order, Vec<Entry>)> {
    let order = match slice(data, 0, 2)? {
        b"II" => Order::Little,
        b"MM" => Order::Big,
        _ => return Err(Error::invalid("Invalid TIFF byte order")),
    };
    if order.u16(data, 2)? != 42 {
        return Err(Error::unsupported(
            "Only classic TIFF metadata is supported",
        ));
    }
    let mut pending = vec![(order.u32(data, 4)? as usize, 0usize)];
    let mut seen = BTreeSet::new();
    let mut out = Vec::new();
    while let Some((offset, depth)) = pending.pop() {
        if offset == 0 {
            continue;
        }
        if depth > limits.depth {
            return Err(Error::limit("IFD depth limit exceeded"));
        }
        if offset < 8 || !seen.insert(offset) {
            return Err(Error::invalid("Cyclic or aliased TIFF directory"));
        }
        let count = usize::from(order.u16(data, offset)?);
        if count > limits.entries
            || out
                .len()
                .checked_add(count)
                .is_none_or(|n| n > limits.entries)
        {
            return Err(Error::limit("TIFF entry limit exceeded"));
        }
        let bytes = count
            .checked_mul(12)
            .and_then(|n| n.checked_add(6))
            .ok_or_else(|| Error::invalid("IFD size overflow"))?;
        slice(data, offset, bytes)?;
        for i in 0..count {
            let at = offset + 2 + i * 12;
            let tag = order.u16(data, at)?;
            let format = order.u16(data, at + 2)?;
            let n = order.u32(data, at + 4)?;
            let width = match format {
                1 | 2 | 6 | 7 => 1,
                3 | 8 => 2,
                4 | 9 | 11 => 4,
                5 | 10 | 12 => 8,
                _ => return Err(Error::unsupported("Unknown TIFF storage type")),
            };
            let length = usize::try_from(n)
                .ok()
                .and_then(|v| v.checked_mul(width))
                .ok_or_else(|| Error::invalid("TIFF value length overflow"))?;
            let value_at = if length <= 4 {
                at + 8
            } else {
                order.u32(data, at + 8)? as usize
            };
            slice(data, value_at, length)?;
            if matches!(tag, 0x8769 | 0x8825 | 0xa005) {
                if format != 4 || n != 1 {
                    return Err(Error::invalid("Invalid TIFF directory pointer"));
                }
                pending.push((order.u32(data, value_at)? as usize, depth + 1));
            }
            out.push(Entry {
                tag,
                format,
                count: n,
                offset: value_at,
                length,
                ifd: offset,
                ordinal: i,
            });
        }
        pending.push((
            order.u32(data, offset + 2 + count * 12)? as usize,
            depth + 1,
        ));
    }
    Ok((order, out))
}

pub fn text(data: &[u8]) -> Result<String> {
    if data.is_empty() || data.last() != Some(&0) {
        return Err(Error::invalid("Selected ASCII field lacks its terminator"));
    }
    let end = data.iter().position(|b| *b == 0).unwrap_or(data.len());
    if data[end..].iter().any(|b| *b != 0) || data[..end].iter().any(|b| !(0x20..=0x7e).contains(b))
    {
        return Err(Error::unsupported(
            "Selected ASCII field has an unsupported encoding",
        ));
    }
    String::from_utf8(data[..end].to_vec()).map_err(|_| Error::invalid("Invalid ASCII text"))
}
