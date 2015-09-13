from cffi import FFI

ffi = FFI()
ffi.set_source('html5ever._ffi', None)
ffi.cdef('''
    uint8_t is_ascii_lowercase(uint8_t c);
''')

if __name__ == '__main__':
    ffi.compile()
