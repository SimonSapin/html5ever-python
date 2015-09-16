#![feature(catch_panic)]

extern crate html5ever;
extern crate string_cache;
extern crate tendril;

use html5ever::tokenizer::{Tokenizer, Attribute};
use html5ever::tree_builder::{TreeBuilder, TreeSink, QuirksMode, NodeOrText};
use std::borrow::Cow;
use std::slice;
use std::mem;
use std::os::raw::{c_void, c_int};
use std::thread::catch_panic;
use string_cache::QualName;
use tendril::StrTendril;

/// When given as a function parameter, only valid for the duration of the call.
#[repr(C)]
#[derive(Copy, Clone)]
#[allow(raw_pointer_derive)]
pub struct BytesSlice {
    ptr: *const u8,
    len: usize,
}

impl BytesSlice {
    fn from_slice(slice: &[u8]) -> BytesSlice {
        BytesSlice {
            ptr: slice.as_ptr(),
            len: slice.len()
        }
    }

    unsafe fn as_slice(&self) -> &[u8] {
        slice::from_raw_parts(self.ptr, self.len)
    }
}

/// When given as a function parameter, only valid for the duration of the call.
#[repr(C)]
#[derive(Copy, Clone)]
pub struct Utf8Slice(BytesSlice);

impl Utf8Slice {
    fn from_str(s: &str) -> Utf8Slice {
        Utf8Slice(BytesSlice::from_slice(s.as_bytes()))
    }
}


pub type OpaqueParserUserData = c_void;
pub type OpaqueNode = c_void;

struct NodeHandle {
    ptr: *const OpaqueNode,
    parser_user_data: *const OpaqueParserUserData,
    callbacks: &'static Callbacks,
}

macro_rules! call {
    ($self_: expr, $callback: ident ( $( $arg: expr ),* )) => {
        ($self_.callbacks.$callback)($self_.parser_user_data, $( $arg ),* )
    };
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

struct ParserMutPtr(*mut Parser);

// FIXME: These make catch_panic happy, but they are total lies as far as I know.
unsafe impl Send for BytesSlice {}
unsafe impl Send for ParserMutPtr {}
unsafe impl Send for Parser {}

impl CallbackTreeSink {
    fn new_handle(&self, ptr: *const OpaqueNode) -> NodeHandle {
        NodeHandle {
            ptr: ptr,
            parser_user_data: self.parser_user_data,
            callbacks: self.callbacks,
        }
    }

    fn add_attributes_if_missing(&self, element: *const OpaqueNode, attributes: Vec<Attribute>) {
        for attribute in attributes {
            call!(self, add_attribute_if_missing(
                element,
                Utf8Slice::from_str(&attribute.name.ns.0),
                Utf8Slice::from_str(&attribute.name.local),
                Utf8Slice::from_str(&attribute.value)));
        }
    }
}

impl TreeSink for CallbackTreeSink {
    type Handle = NodeHandle;

    fn parse_error(&mut self, msg: Cow<'static, str>) {
        call_if_some!(self, parse_error(Utf8Slice::from_str(&msg)))
    }

    fn get_document(&mut self) -> NodeHandle {
        self.document.clone()
    }

    fn get_template_contents(&self, target: NodeHandle) -> NodeHandle {
        self.new_handle(call!(self, get_template_contents(target.ptr)))
    }

    fn set_quirks_mode(&mut self, mode: QuirksMode) {
        self.quirks_mode = mode
    }

    fn same_node(&self, x: NodeHandle, y: NodeHandle) -> bool {
        call_if_some!(self, same_node(x.ptr, y.ptr) else (x.ptr == y.ptr) as c_int) != 0
    }

    fn elem_name(&self, target: NodeHandle) -> QualName {
        let ptr = call!(self, element_name(target.ptr));
        unsafe {
            (*ptr).clone()
         }
    }

    fn create_element(&mut self, name: QualName, attrs: Vec<Attribute>) -> NodeHandle {
        let namespace_url = Utf8Slice::from_str(&name.ns.0);
        let local_name = Utf8Slice::from_str(&name.local);
        let element = call!(self, create_element(Box::new(name), namespace_url, local_name));
        self.add_attributes_if_missing(element, attrs);
        self.new_handle(element)
    }

    fn create_comment(&mut self, text: StrTendril) -> NodeHandle {
        self.new_handle(call!(self, create_comment(Utf8Slice::from_str(&text))))
    }

    fn append(&mut self, parent: NodeHandle, child: NodeOrText<NodeHandle>) {
        match child {
            NodeOrText::AppendNode(node) => {
                call!(self, append_node(parent.ptr, node.ptr))
            }
            NodeOrText::AppendText(ref text) => {
                call!(self, append_text(parent.ptr, Utf8Slice::from_str(text)))
            }
        }
    }

    fn append_before_sibling(&mut self, sibling: NodeHandle, child: NodeOrText<NodeHandle>)
                             -> Result<(), NodeOrText<NodeHandle>> {
        let result = match child {
            NodeOrText::AppendNode(ref node) => {
                call!(self, insert_node_before_sibling(sibling.ptr, node.ptr))
            }
            NodeOrText::AppendText(ref text) => {
                call!(self, insert_text_before_sibling(sibling.ptr, Utf8Slice::from_str(text)))
            }
        };
        if result == 0 {
            Ok(())
        } else {
            Err(child)
        }
    }

    fn append_doctype_to_document(&mut self,
                                  name: StrTendril,
                                  public_id: StrTendril,
                                  system_id: StrTendril) {
        call!(self, append_doctype_to_document(
            Utf8Slice::from_str(&name),
            Utf8Slice::from_str(&public_id),
            Utf8Slice::from_str(&system_id)))
    }

    fn add_attrs_if_missing(&mut self, target: NodeHandle, attrs: Vec<Attribute>) {
        self.add_attributes_if_missing(target.ptr, attrs)
    }

    fn remove_from_parent(&mut self, target: NodeHandle) {
        call!(self, remove_from_parent(target.ptr))
    }

    fn reparent_children(&mut self, node: NodeHandle, new_parent: NodeHandle) {
        call!(self, reparent_children(node.ptr, new_parent.ptr))
    }

    fn mark_script_already_started(&mut self, _target: NodeHandle) {}
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
        pub unsafe extern "C" fn declare_callbacks($( $name: $ty ),+)
                                                   -> Option<&'static Callbacks> {
            catch_panic_opt(move || {
                &*Box::into_raw(Box::new(Callbacks {
                    $( $name: $name, )+
                }))
            })
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
        Utf8Slice)>

    /// Create an element node with the given namespace URL and local name.
    /// The qualified name (namespace URL plus local name) is also given in
    /// its Rust representation, to be returned in the `element_name` callback.
    ///
    /// If the element in `template` element in the HTML namespace,
    /// an associated document fragment node should be created for the template contents.
    callback create_element: extern "C" fn(*const OpaqueParserUserData,
        Box<QualName>, Utf8Slice, Utf8Slice) -> *const OpaqueNode

    /// Return the Rust representation of the qualified name of the given element,
    /// as was given by the `create_element` callback.
    callback element_name: extern "C" fn(*const OpaqueParserUserData,
        *const OpaqueNode) -> *const QualName

    /// Return a reference to the document fragment node for the template contents.
    ///
    /// This is only ever called for `template` elements in the HTML namespace.
    callback get_template_contents: extern "C" fn(*const OpaqueParserUserData,
        *const OpaqueNode) -> *const OpaqueNode

    /// Add the attribute (given as namespace URL, local name, and value)
    /// to the given element node if the element doesn’t already have
    /// an attribute with that name in that namespace.
    callback add_attribute_if_missing: extern "C" fn(*const OpaqueParserUserData,
        *const OpaqueNode, Utf8Slice, Utf8Slice, Utf8Slice)

    /// Create a comment node.
    callback create_comment: extern "C" fn(*const OpaqueParserUserData,
        Utf8Slice) -> *const OpaqueNode

    /// Create a doctype node and append it to the document.
    callback append_doctype_to_document: extern "C" fn(*const OpaqueParserUserData,
        Utf8Slice, Utf8Slice, Utf8Slice)

    callback append_node: extern "C" fn(*const OpaqueParserUserData,
        *const OpaqueNode, *const OpaqueNode)

    callback append_text: extern "C" fn(*const OpaqueParserUserData,
        *const OpaqueNode, Utf8Slice)

    /// If `sibling` has a parent, insert the given node just before it and return 0.
    /// Otherwise, do nothing and return a non-zero value.
    callback insert_node_before_sibling: extern "C" fn(*const OpaqueParserUserData,
        *const OpaqueNode, *const OpaqueNode) -> c_int

    /// If `sibling` has a parent, insert the given text just before it and return 0.
    /// Otherwise, do nothing and return a non-zero value.
    callback insert_text_before_sibling: extern "C" fn(*const OpaqueParserUserData,
        *const OpaqueNode, Utf8Slice) -> c_int

    callback reparent_children: extern "C" fn(*const OpaqueParserUserData,
        *const OpaqueNode, *const OpaqueNode)

    callback remove_from_parent: extern "C" fn(*const OpaqueParserUserData,
        *const OpaqueNode)
}

#[no_mangle]
pub extern "C" fn new_parser(callbacks: &'static Callbacks,
                             data: *const OpaqueParserUserData,
                             document: *const OpaqueNode)
                             -> Option<Box<Parser>> {
    struct TotallyNotSendProbably(*const OpaqueParserUserData, *const OpaqueNode);
    unsafe impl Send for TotallyNotSendProbably {}  // ???
    let send = TotallyNotSendProbably(data, document);
    catch_panic_opt(move || {
        let data = send.0;
        let document = send.1;
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
    })
}

#[no_mangle]
pub unsafe extern "C" fn feed_parser(parser: &mut Parser, chunk: BytesSlice) -> c_int {
    let parser = ParserMutPtr(parser);
    catch_panic_int(move || {
        let parser = &mut *parser.0;
        let tokenizer = unwrap_or_return!(parser.opt_tokenizer.as_mut());
        // FIXME: Support UTF-8 byte sequences split across chunk boundary
        // FIXME: Go through the data once here instead of twice.
        let string = String::from_utf8_lossy(chunk.as_slice());
        tokenizer.feed((&*string).into())
    })
}

#[no_mangle]
pub unsafe extern "C" fn end_parser(parser: &mut Parser) -> c_int {
    let parser = ParserMutPtr(parser);
    catch_panic_int(move || {
        let parser = &mut *parser.0;
        let mut tokenizer = unwrap_or_return!(parser.opt_tokenizer.take());
        tokenizer.end();
    })
}

#[no_mangle]
pub extern "C" fn destroy_parser(mut parser: Box<Parser>) -> c_int {
    catch_panic_int(move || {
        // Leave `None` behind to protect against double drop.
        mem::drop(parser.opt_tokenizer.take())
    })
}

#[no_mangle]
pub extern "C" fn destroy_qualified_name(name: Box<QualName>) -> c_int {
    catch_panic_int(|| {
        mem::drop(name)
    })
}

fn catch_panic_opt<R, F: FnOnce() -> R + Send + 'static>(f: F) -> Option<R> {
    catch_panic(f).ok()
}

fn catch_panic_int<F: FnOnce() + Send + 'static>(f: F) -> c_int {
    match catch_panic(f) {
        Ok(()) => 0,
        Err(_) => -1,
    }
}
