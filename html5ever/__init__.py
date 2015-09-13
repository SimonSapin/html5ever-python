import os.path
from ._ffi import ffi

capi = ffi.dlopen(os.path.join(os.path.dirname(__file__), 'libhtml5ever_capi.so'))


@ffi.callback('Node* (ParserUserData*, Node*)')
def clone_node_ref(parser, node):
    ffi.from_handle(ffi.cast('void*', parser)).refcounts[node] += 1
    return node


@ffi.callback('void (ParserUserData*, Node*)')
def destroy_node_ref(parser, node):
    parser = ffi.from_handle(ffi.cast('void*', parser))
    count = parser.refcounts[node]
    if count == 1:
        del parser.refcounts[node]
    else:
        parser.refcounts[node] = count - 1


CALLBACKS = capi.declare_callbacks(clone_node_ref, destroy_node_ref, ffi.NULL, ffi.NULL)


class Parser(object):
    def __init__(self):
        self.refcounts = {}
        self.self_handle = ffi.new_handle(self)
        self.document = Document()
        self.ptr = ffi.gc(
            capi.new_parser(CALLBACKS, self.self_handle, self._new_node(self.document)),
            capi.destroy_parser)

    def _new_node(self, node):
        handle = ffi.new_handle(self.document)
        self.refcounts[handle] = 1
        return handle

    def __del__(self):
        # Trigger destroy_parser() while self.refcounts is still alive
        del self.ptr


class Node(object):
    """Abstract base class for all nodes in the tree."""


class Document(object):
    """A document node, the root of the tree."""
