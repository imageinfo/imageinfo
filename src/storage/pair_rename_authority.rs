//! Current live-caller authority for one immutable explicit pair; never restart authority.
use super::{
    MAX_RECORD_BYTES,
    custody::{CustodyRefusal, ExchangeGeneration, TrustedCurrentCaller},
    pair_rename::PairNames,
    runtime::Binding,
};
use std::path::Path;

#[derive(Clone, Debug, PartialEq, Eq)]
pub(crate) struct PairBindings {
    bytes: Vec<u8>,
}
impl PairBindings {
    pub(crate) fn capture(
        operation: &str,
        names: &PairNames,
        record_root: &Path,
        originals: [Binding; 2],
        parent: Binding,
    ) -> Result<Self, CustodyRefusal> {
        if operation.is_empty()
            || operation.len() > 256
            || originals[0].identity == originals[1].identity
            || record_root.as_os_str().is_empty()
        {
            return Err(CustodyRefusal::InvalidBindings);
        }
        let bindings = [&originals[0], &originals[1], &parent];
        if bindings.iter().any(|b| {
            b.identity.is_empty()
                || b.identity.len() > 256
                || b.facts.is_empty()
                || b.facts.len() > 8192
        }) {
            return Err(CustodyRefusal::InvalidBindings);
        }
        let mut length = 128 + operation.len();
        for p in names
            .paths()
            .into_iter()
            .chain(std::iter::once(record_root))
        {
            let n = p.as_os_str().as_encoded_bytes().len();
            if n > 4096 {
                return Err(CustodyRefusal::ConstructionBound);
            }
            length += 8 + n;
        }
        for b in bindings {
            length += 16 + b.identity.len() + b.facts.len();
        }
        if length > MAX_RECORD_BYTES as usize {
            return Err(CustodyRefusal::ConstructionBound);
        }
        let mut bytes = Vec::with_capacity(length);
        let mut put = |v: &[u8]| {
            bytes.extend_from_slice(&(v.len() as u64).to_le_bytes());
            bytes.extend_from_slice(v);
        };
        put(b"explicit-raw-xmp-rename-v1");
        put(operation.as_bytes());
        for plan in names.plans() {
            put(&[u8::from(plan.temporary().is_some())]);
            for p in std::iter::once(plan.source()).chain(plan.steps()) {
                put(p.as_os_str().as_encoded_bytes());
            }
        }
        put(record_root.as_os_str().as_encoded_bytes());
        for b in bindings {
            put(&b.identity);
            put(&b.facts);
        }
        Ok(Self { bytes })
    }
    pub(crate) fn bytes(&self) -> &[u8] {
        &self.bytes
    }
    #[cfg(windows)]
    pub(crate) fn capture_snapshots(
        operation: &str,
        names: &PairNames,
        record_root: &Path,
        originals: [&imageinfo_windows_storage::FileSnapshot; 2],
        parent: &imageinfo_windows_storage::FileSnapshot,
    ) -> Result<Self, CustodyRefusal> {
        if originals.iter().any(|s| {
            s.volume_serial_number != parent.volume_serial_number
                || s.links != 1
                || s.owner_dacl.len() > 8000
        }) || parent.owner_dacl.len() > 8000
        {
            return Err(CustodyRefusal::InvalidBindings);
        }
        Self::capture(
            operation,
            names,
            record_root,
            originals.map(|s| super::windows::binding_snapshot(s, None)),
            super::windows::binding_snapshot(parent, None),
        )
    }
}
pub(crate) struct PairAuthority {
    expected: PairBindings,
    generation: ExchangeGeneration,
}
impl PairAuthority {
    pub(crate) fn authorize(
        caller: &mut TrustedCurrentCaller,
        expected: PairBindings,
    ) -> Result<Self, CustodyRefusal> {
        Ok(Self {
            expected,
            generation: caller.begin_pair_rename()?,
        })
    }
    pub(crate) fn check(&self, fresh: &PairBindings) -> Result<(), CustodyRefusal> {
        self.generation.check()?;
        if self.expected != *fresh {
            return Err(CustodyRefusal::ChangedBindings);
        }
        Ok(())
    }
}
