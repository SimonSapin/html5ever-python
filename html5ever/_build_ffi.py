from cffi import FFI

ffi = FFI()
ffi.set_source("html5ever._ffi", None)
ffi.cdef("""
    int islower (int c);
""")

if __name__ == "__main__":
    ffi.compile()
