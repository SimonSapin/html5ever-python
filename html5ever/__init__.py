import os.path
from ._ffi import ffi

html5ever_capi = ffi.dlopen(os.path.join(os.path.dirname(__file__), 'libhtml5ever_capi.so'))
