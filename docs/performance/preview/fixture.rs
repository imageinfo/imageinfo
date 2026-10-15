//! Authored structural bytes, not decodable camera images. Setup is never timed.
#[allow(dead_code)]
#[path = "../../../tests/support/mod.rs"]
mod support;

fn payload(size: usize, marker: u8) -> Vec<u8> {
    let mut bytes = vec![marker; size];
    bytes[..2].copy_from_slice(&[0xff, 0xd8]);
    bytes[size - 5..size - 3].copy_from_slice(&[0xff, 0xd9]);
    bytes[size - 3..].fill(0);
    bytes
}

fn main() {
    let root =
        std::path::PathBuf::from(std::env::args_os().nth(1).expect("fresh fixture directory"));
    std::fs::create_dir(&root).unwrap();
    let data = support::fixture_with_previews(
        "Firmware Version authored",
        payload(4096, 0x41),
        payload(65536, 0x42),
        payload(1048583, 0x43),
    );
    for (name, bytes) in [
        ("source.cr3", data.bytes),
        ("ThumbnailImage.bin", data.thumbnail),
        ("PreviewImage.bin", data.preview),
        ("JpgFromRaw.bin", data.jpeg),
    ] {
        std::fs::write(root.join(name), bytes).unwrap();
    }
}
