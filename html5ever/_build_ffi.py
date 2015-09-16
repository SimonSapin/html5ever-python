from cffi import FFI

ffi = FFI()
ffi.set_source('html5ever._ffi', None)
ffi.cdef('''

    typedef ... Callbacks;
    typedef ... ParserUserData;
    typedef ... Node;
    typedef ... QualifiedName;
    typedef ... Parser;

    typedef struct {
        uint8_t* ptr;
        uintptr_t len;
    } BytesSlice;

    typedef BytesSlice Utf8Slice;

    Callbacks* declare_callbacks(
        Node* (*clone_node_ref)(ParserUserData*, Node*),
        int (*destroy_node_ref)(ParserUserData*, Node*),
        int (*same_node)(ParserUserData*, Node*, Node*),
        int (*parse_error)(ParserUserData*, Utf8Slice),

        Node* (*create_element)(ParserUserData*, QualifiedName*, Utf8Slice, Utf8Slice),
        QualifiedName* (*element_name)(ParserUserData*, Node*),
        Node* (*get_template_contents)(ParserUserData*, Node*),
        int (*add_attribute_if_missing)(ParserUserData*, Node*, Utf8Slice, Utf8Slice, Utf8Slice),
        Node* (*create_comment)(ParserUserData*, Utf8Slice),
        int (*append_doctype_to_document)(ParserUserData*, Utf8Slice, Utf8Slice, Utf8Slice),

        int (*append_node)(ParserUserData*, Node*, Node*),
        int (*append_text)(ParserUserData*, Node*, Utf8Slice),
        int (*insert_node_before_sibling)(ParserUserData*, Node*, Node*),
        int (*insert_text_before_sibling)(ParserUserData*, Node*, Utf8Slice),
        int (*reparent_children)(ParserUserData*, Node*, Node*),
        int (*remove_from_parent)(ParserUserData*, Node*)
    );

    Parser* new_parser(Callbacks*, ParserUserData*, Node*);
    int destroy_parser(Parser*);
    int feed_parser(Parser*, BytesSlice);
    int destroy_qualified_name(QualifiedName*);

''')

if __name__ == '__main__':
    ffi.compile()
