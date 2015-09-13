#![feature(box_raw)]

extern crate html5ever;
extern crate string_cache;
extern crate tendril;

use html5ever::tokenizer::{Tokenizer, Attribute};
use html5ever::tree_builder::{TreeBuilder, TreeSink, QuirksMode, NodeOrText};
use std::borrow::Cow;
use std::slice;
use std::mem;
use std::os::raw::{c_void, c_int};
use string_cache::QualName;
use tendril::StrTendril;

pub type OpaqueParserUserData = c_void;
pub type OpaqueNode = c_void;

struct NodeHandle {
    ptr: *const OpaqueNode,
    parser_user_data: *const OpaqueParserUserData,
    callbacks: &'static Callbacks,
}

macro_rules! call_if_some {
    ($self_: expr, $opt_callback: ident ( $( $arg: expr ),* )) => {
        call_if_some!($self_, $opt_callback( $( $arg ),* ) else ())
    };
    ($self_: expr, $opt_callback: ident ( $( $arg: expr ),* ) else $default: expr) => {
        if let Some(callback) = $self_.callbacks.$opt_callback {
            callback($self_.parser_user_data, $( $arg ),* )
        } else {
            $default
        }
    };
}

impl Clone for NodeHandle {
    fn clone(&self) -> NodeHandle {
        NodeHandle {
            ptr: call_if_some!(self, clone_node_ref(self.ptr) else self.ptr),
            parser_user_data: self.parser_user_data,
            callbacks: self.callbacks,
        }
    }
}

impl Drop for NodeHandle {
    fn drop(&mut self) {
        call_if_some!(self, destroy_node_ref(self.ptr))
    }
}

struct CallbackTreeSink {
    parser_user_data: *const c_void,
    callbacks: &'static Callbacks,
    document: NodeHandle,
    quirks_mode: QuirksMode,
}

pub struct Parser {
    opt_tokenizer: Option<Tokenizer<TreeBuilder<NodeHandle, CallbackTreeSink>>>
}

impl CallbackTreeSink {
    fn new_handle(&self, ptr: *const OpaqueNode) -> NodeHandle {
        NodeHandle {
            ptr: ptr,
            parser_user_data: self.parser_user_data,
            callbacks: self.callbacks,
        }
    }
}

impl TreeSink for CallbackTreeSink {
    type Handle = NodeHandle;

    fn parse_error(&mut self, msg: Cow<'static, str>) {
        call_if_some!(self, parse_error(&msg.as_bytes()[0], msg.len()))
    }

    fn get_document(&mut self) -> NodeHandle {
        self.document.clone()
    }

    fn get_template_contents(&self, target: NodeHandle) -> NodeHandle {
        unimplemented!()
    }

    fn set_quirks_mode(&mut self, mode: QuirksMode) {
        self.quirks_mode = mode
    }

    fn same_node(&self, x: NodeHandle, y: NodeHandle) -> bool {
        call_if_some!(self, same_node(x.ptr, y.ptr) else (x.ptr == y.ptr) as c_int) != 0
    }

    fn elem_name(&self, target: NodeHandle) -> QualName {
        unimplemented!()
    }

    fn create_element(&mut self, name: QualName, attrs: Vec<Attribute>) -> NodeHandle {
        unimplemented!()
    }

    fn create_comment(&mut self, text: StrTendril) -> NodeHandle {
        unimplemented!()
    }

    fn append(&mut self, parent: NodeHandle, child: NodeOrText<NodeHandle>) {
        unimplemented!()
    }

    fn append_before_sibling(&mut self, sibling: NodeHandle, child: NodeOrText<NodeHandle>)
                             -> Result<(), NodeOrText<NodeHandle>> {
        unimplemented!()
    }

    fn append_doctype_to_document(&mut self,
                                  name: StrTendril,
                                  public_id: StrTendril,
                                  system_id: StrTendril) {
        unimplemented!()
    }

    fn add_attrs_if_missing(&mut self, target: NodeHandle, attrs: Vec<Attribute>) {
        unimplemented!()
    }

    fn remove_from_parent(&mut self, target: NodeHandle) {
        unimplemented!()
    }

    fn reparent_children(&mut self, node: NodeHandle, new_parent: NodeHandle) {
        unimplemented!()
    }

    fn mark_script_already_started(&mut self, target: NodeHandle) {
        unimplemented!()
    }
}

macro_rules! unwrap_or_return {
    ($e: expr) => {
        match $e {
            Some(value) => value,
            None => return  // FIXME: signal error somehow
        }
    }
}

// FIXME: catch panics

macro_rules! declare_with_callbacks {
    ($( $( #[$attr:meta] )* callback $name: ident: $ty: ty )+) => {
        pub struct Callbacks {
            $( $( #[$attr] )* $name: $ty, )+
        }

        /// Return a heap-allocated stuct that lives forever,
        /// containing the given function pointers.
        ///
        /// This leaks memory, but you normally only need one of these per program.
        #[no_mangle]
        pub unsafe extern "C" fn declare_callbacks($( $name: $ty ),+) -> &'static Callbacks {
            &*Box::into_raw(Box::new(Callbacks {
                $( $name: $name, )+
            }))
        }

    }
}

declare_with_callbacks! {
    /// Create and return a new reference to the given node.
    /// The returned pointer may be the same as the given one.
    /// If this callback is not provided, the same pointer is always used
    callback clone_node_ref:  Option<extern "C" fn(*const OpaqueParserUserData,
        *const OpaqueNode) -> *const OpaqueNode>

    /// Destroy a new reference to the given node.
    /// When all references are gone, the node itself can be destroyed.
    /// If this callback is not provided, references are leaked.
    callback destroy_node_ref: Option<extern "C" fn(*const OpaqueParserUserData,
        *const OpaqueNode)>

    /// Return a non-zero value if the two given references are for the same node.
    /// If this callback is not provided, pointer equality is used.
    callback same_node: Option<extern "C" fn(*const OpaqueParserUserData,
        *const OpaqueNode, *const OpaqueNode) -> c_int>

    /// Log an author conformance error.
    /// The pointer is guaranteed to point to the given size of well-formed UTF-8 bytes.
    /// The pointer can not be used after the end of this call.
    /// If this callback is not provided, author conformance errors are ignored.
    callback parse_error: Option<extern "C" fn(*const OpaqueParserUserData,
        &u8, usize)>
}

#[no_mangle]
pub extern "C" fn new_parser(callbacks: &'static Callbacks,
                             data: *const c_void,
                             document: *const OpaqueNode)
                             -> Box<Parser> {
    let sink = CallbackTreeSink {
        parser_user_data: data,
        callbacks: callbacks,
        document: NodeHandle {
            ptr: document,
            parser_user_data: data,
            callbacks: callbacks,
        },
        quirks_mode: QuirksMode::NoQuirks,
    };
    let tree_builder = TreeBuilder::new(sink, Default::default());
    let tokenizer = Tokenizer::new(tree_builder, Default::default());
    Box::new(Parser {
        opt_tokenizer: Some(tokenizer)
    })
}

#[no_mangle]
pub unsafe extern "C" fn feed_parser(parser: &mut Parser, chunk_ptr: *const u8, chunk_length: usize) {
    let tokenizer = unwrap_or_return!(parser.opt_tokenizer.as_mut());
    // FIXME: Support UTF-8 byte sequences split across chunk boundary
    // FIXME: Go through the data once here instead of twice.
    let string = String::from_utf8_lossy(slice::from_raw_parts(chunk_ptr, chunk_length));
    tokenizer.feed((&*string).into())
}

#[no_mangle]
pub unsafe extern "C" fn end_parser(parser: &mut Parser) {
    let mut tokenizer = unwrap_or_return!(parser.opt_tokenizer.take());
    tokenizer.end();
}

#[no_mangle]
pub extern "C" fn destroy_parser(mut parser: Box<Parser>) {
    // Leave `None` behind to protect against double drop.
    mem::drop(parser.opt_tokenizer.take())
}
