from cffi import FFI

ffi = FFI()
ffi.set_source('html5ever._ffi', None)
ffi.cdef('''

    typedef ... Callbacks;
    typedef ... ParserUserData;
    typedef ... Node;
    typedef ... Parser;

    typedef struct {
        uint8_t* ptr;
        uintptr_t len;
    } BytesSlice;

    typedef BytesSlice Utf8Slice;

    Callbacks* declare_callbacks(
        Node* (*clone_node_ref)(ParserUserData*, Node*),
        void (*destroy_node_ref)(ParserUserData*, Node*),
        int (*same_node)(ParserUserData*, Node*, Node*),
        void (*parse_error)(ParserUserData*, Utf8Slice),
    );

    Parser* new_parser(Callbacks*, ParserUserData*, Node*);
    void destroy_parser(Parser*);
    void feed_parser(Parser*, BytesSlice);

''')

if __name__ == '__main__':
    ffi.compile()
