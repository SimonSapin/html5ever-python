#![feature(duration_span)]
extern crate html5ever;
extern crate tendril;

use html5ever::{parse, one_input};
use html5ever::rcdom::RcDom;
use tendril::StrTendril;
use std::io::{stdin, Read};
use std::time::Duration;

fn main() {
    let mut data = Vec::new();
    stdin().read_to_end(&mut data).unwrap();
    let d = (0..3).map(|_| Duration::span(|| {
        let data = StrTendril::from_slice(&String::from_utf8_lossy(&data));
        let _dom: RcDom = parse(one_input(data), Default::default());
    })).min().unwrap();
    const NANOS_PER_MILI: u32 = 1_000_000;
    println!("html5ever to Rust RcDom: {}.{:03} seconds", d.as_secs(), d.subsec_nanos() / NANOS_PER_MILI);
}
