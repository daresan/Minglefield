//! Generate a minimal development-only Windows icon before Tauri's resource build.
//! Replace with reviewed branded assets before distributing installer packages.
use std::{fs, path::PathBuf};

fn write_development_icon() -> std::io::Result<()> {
    let dir = PathBuf::from(std::env::var("CARGO_MANIFEST_DIR").expect("Cargo manifest dir"));
    let path = dir.join("icons").join("icon.ico");
    if path.exists() {
        return Ok(());
    }
    fs::create_dir_all(path.parent().expect("icon directory"))?;

    // ICO containing a 16x16 32-bit BGRA DIB plus a 1-bit transparency mask.
    const SIDE: usize = 16;
    const PIXELS: usize = SIDE * SIDE * 4;
    const MASK: usize = SIDE * 4; // 1bpp rows padded to 4 bytes
    let image_bytes = 40 + PIXELS + MASK;
    let mut ico = Vec::with_capacity(22 + image_bytes);
    ico.extend_from_slice(&[0, 0, 1, 0, 1, 0]); // ICO header, one image
    ico.extend_from_slice(&[SIDE as u8, SIDE as u8, 0, 0]);
    ico.extend_from_slice(&1u16.to_le_bytes());
    ico.extend_from_slice(&32u16.to_le_bytes());
    ico.extend_from_slice(&(image_bytes as u32).to_le_bytes());
    ico.extend_from_slice(&22u32.to_le_bytes());
    ico.extend_from_slice(&40u32.to_le_bytes()); // BITMAPINFOHEADER size
    ico.extend_from_slice(&(SIDE as i32).to_le_bytes()); // width
    ico.extend_from_slice(&((SIDE * 2) as i32).to_le_bytes()); // XOR + AND height
    ico.extend_from_slice(&1u16.to_le_bytes()); // planes
    ico.extend_from_slice(&32u16.to_le_bytes()); // bits per pixel
    ico.extend_from_slice(&0u32.to_le_bytes()); // BI_RGB
    ico.extend_from_slice(&(PIXELS as u32).to_le_bytes());
    ico.extend_from_slice(&0i32.to_le_bytes()); // x pixels per meter
    ico.extend_from_slice(&0i32.to_le_bytes()); // y pixels per meter
    ico.extend_from_slice(&0u32.to_le_bytes()); // colors used
    ico.extend_from_slice(&0u32.to_le_bytes()); // important colors
    for y in 0..SIDE {
        for x in 0..SIDE {
            let accent = (x + y) % 4 == 0;
            // Blue, green, red, alpha: teal checker over dark blue.
            ico.extend_from_slice(if accent {
                &[150, 204, 91, 255]
            } else {
                &[47, 31, 20, 255]
            });
        }
    }
    ico.resize(22 + image_bytes, 0); // opaque AND mask
    fs::write(path, ico)
}

fn main() {
    if cfg!(target_os = "windows") {
        write_development_icon().expect("failed to create development icon");
    }
    tauri_build::build()
}
