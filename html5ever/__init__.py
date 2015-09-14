import os.path
from ._ffi import ffi

capi = ffi.dlopen(os.path.join(os.path.dirname(__file__), 'libhtml5ever_capi.so'))


CALLBACKS = capi.declare_callbacks(ffi.NULL, ffi.NULL, ffi.NULL, ffi.NULL)


class Parser(object):
    def __init__(self):
        self._keep_alive_handles = []
        self.document = Document()
        self._ptr = capi.new_parser(
            CALLBACKS, self._keep_alive(self), self._keep_alive(self.document))

    def __del__(self):
        # Do this here rather than through ffi.gc:
        # by the time ffi.gc would trigger, self.refcounts might have been removed already.
        capi.destroy_parser(self._ptr)

    def _keep_alive(self, obj):
        '''
        Keep the given object alive at least as long as the parser,
        and return a handle that can go through C / Rust as a `void *` pointer.

        For nodes, we could use a reference counting scheme here with the `clone_node_ref`
        and `destroy_node_ref` callbacks, but that would only help with nodes
        created by the parser that don’t end up in the tree (to free them early),
        which is probably rare if it happens at all.
        '''
        handle = ffi.new_handle(obj)
        self._keep_alive_handles.append(handle)
        return handle


class Node(object):
    """Abstract base class for all nodes in the tree."""


class Document(Node):
    """A document node, the root of the tree."""
