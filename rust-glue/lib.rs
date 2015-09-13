extern crate html5ever;

#[no_mangle]
pub fn is_ascii_lowercase(c: u8) -> u8 {
    (b'a' <= c && c <= b'z') as u8
}
