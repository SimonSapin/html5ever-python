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
    println!("{}.{:09}", d.as_secs(), d.subsec_nanos());
}
