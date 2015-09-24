import os.path
from ._ffi import ffi

capi = ffi.dlopen(os.path.join(os.path.dirname(__file__), 'libhtml5ever_capi.so'))


def parse(bytes):
    parser = Parser()
    parser.feed(bytes)
    return parser.end()


class Parser(object):
    def __init__(self, tree_builder=None):
        self.tree_builder = tree_builder or DefaultTreeBuilder()
        self._keep_alive_handles = []
        self._template_contents_keep_alive_handles = {}
        self._document = self.tree_builder.new_document()
        self._ptr = ffi.gc(
            check_null(capi.new_parser(
                CALLBACKS, self._keep_alive(self), self._keep_alive(self._document))),
            lambda ptr: check_int(capi.destroy_parser(ptr)))

    def feed(self, bytes_chunk):
        data = ffi.new('char[]', bytes_chunk)
        slice_ = ffi.new('BytesSlice*', (data, len(bytes_chunk)))
        check_int(capi.feed_parser(self._ptr, slice_[0]))

    def end(self):
        check_int(capi.end_parser(self._ptr))
        self._keep_alive_handles = None
        self._template_contents_keep_alive_handles = None
        self._ptr = None
        return self._document

    def _keep_alive(self, obj):
        '''
        Keep the given object alive at least as long as the parser,
        and return a handle that can go through C / Rust as a `void *` pointer.

        For nodes, we could use a reference counting scheme here with the `clone_node_ref`
        and `destroy_node_ref` callbacks, but that would only help with nodes
        created by the parser that don't end up in the tree (to free them early),
        which is probably rare if it happens at all.
        '''
        handle = ffi.new_handle(obj)
        self._keep_alive_handles.append(handle)
        return handle


class Node(object):
    '''Abstract base class for all nodes in the tree.'''
    def __init__(self):
        self.parent = None
        self.children = []


class Document(Node):
    '''A document node, the root of the tree.'''


class DocumentFragment(Node):
    '''A document fragement node.'''


HTML_NAMESPACE = b'http://www.w3.org/1999/xhtml'
MATHML_NAMESPACE = b'http://www.w3.org/1998/Math/MathML'
SVG_NAMESPACE = b'http://www.w3.org/2000/svg'
XLINK_NAMESPACE = b'http://www.w3.org/1999/xlink'
XML_NAMESPACE = b'http://www.w3.org/XML/1998/namespace'
XMLNS_NAMESPACE = b'http://www.w3.org/2000/xmlns/'


class Element(Node):
    '''An element node.'''
    def __init__(self, namespace_url, local_name):
        self.parent = None
        self.children = []
        self.name = (namespace_url, local_name)
        self.attributes = {}
        self.template_contents = None


class Text(Node):
    '''A text node.'''
    def __init__(self, data):
        self.parent = None
        self.data = data


class Comment(Node):
    '''A comment node.'''
    def __init__(self, data):
        self.parent = None
        self.data = data


class Doctype(Node):
    '''A doctype node.'''
    def __init__(self, name, public_id, system_id):
        self.parent = None
        self.name = name
        self.public_id = public_id
        self.system_id = system_id


class DefaultTreeBuilder(object):
    def new_document(self):
        return Document()

    def new_element(self, namespace_url, local_name):
        return Element(namespace_url, local_name)

    def element_add_template_contents(self, element):
        element.template_contents = DocumentFragment()
        return element.template_contents

    def element_add_attribute_if_missing(self, element, namespace_url, local_name, value):
        element.attributes.setdefault((namespace_url, local_name), value)

    def new_comment(self, data):
        return Comment(data)

    def append_doctype_to_document(self, document, name, public_id, system_id):
        document.children.append(Doctype(name, public_id, system_id))

    def append_node(self, parent, new_child):
        parent.children.append(new_child)
        new_child.parent = parent

    def append_text(self, parent, data):
        if parent.children and isinstance(parent.children[-1], Text):
            parent.children[-1].data += data
        else:
            child = Text(data)
            child.parent = parent
            parent.children.append(child)

    def insert_node_before_sibling(self, sibling, new_sibling):
        parent = sibling.parent
        if parent is None:
            return False
        position = parent.children.index(sibling)
        parent.children.insert(position, new_sibling)
        return True

    def insert_text_before_sibling(self, sibling, data):
        parent = sibling.parent
        if parent is None:
            return False
        position = parent.children.index(sibling)
        if position > 0 and isinstance(parent.children[position - 1], Text):
            parent.children[position - 1].data += data
        else:
            child = Text(data)
            child.parent = parent
            parent.children.insert(position, child)
        return True

    def reparent_children(self, parent, new_parent):
        for child in parent.children:
            child.parent = new_parent
        new_parent.children.extend(parent.children)
        parent.children = []

    def remove_from_parent(self, node):
        if node.parent is not None:
            node.parent.children.remove(node)
            node.parent = None


def str_from_slice(slice_):
    return ffi.buffer(slice_.ptr, slice_.len)[:]


@ffi.callback('Node*(ParserUserData*, Utf8Slice, Utf8Slice)')
def create_element(parser, namespace_url, local_name):
    parser = ffi.from_handle(ffi.cast('void*', parser))
    namespace_url = str_from_slice(namespace_url)
    local_name = str_from_slice(local_name)
    element = parser.tree_builder.new_element(namespace_url, local_name)
    if local_name == b'template' and namespace_url == HTML_NAMESPACE:
        parser._template_contents_keep_alive_handles[element] = \
            ffi.new_handle(parser.tree_builder.element_add_template_contents(element))
    return parser._keep_alive(element)


@ffi.callback('Node*(ParserUserData*, Node*)')
def get_template_contents(parser, element):
    parser = ffi.from_handle(ffi.cast('void*', parser))
    element = ffi.from_handle(ffi.cast('void*', element))
    return parser._template_contents_keep_alive_handles[element]


@ffi.callback('int(ParserUserData*, Node*, Utf8Slice, Utf8Slice, Utf8Slice)', error=-1)
def add_attribute_if_missing(parser, element, namespace_url, local_name, value):
    parser = ffi.from_handle(ffi.cast('void*', parser))
    element = ffi.from_handle(ffi.cast('void*', element))
    parser.tree_builder.element_add_attribute_if_missing(
        element,
        str_from_slice(namespace_url),
        str_from_slice(local_name),
        str_from_slice(value))
    return 0


@ffi.callback('Node*(ParserUserData*, Utf8Slice)')
def create_comment(parser, data):
    parser = ffi.from_handle(ffi.cast('void*', parser))
    return parser._keep_alive(parser.tree_builder.new_comment(str_from_slice(data)))


@ffi.callback('int(ParserUserData*, uintptr_t, Utf8Slice, Utf8Slice, Utf8Slice)', error=-1)
def append_doctype_to_document(parser, _dummy, name, public_id, system_id):
    parser = ffi.from_handle(ffi.cast('void*', parser))
    parser.tree_builder.append_doctype_to_document(
        parser._document,
        str_from_slice(name),
        str_from_slice(public_id),
        str_from_slice(system_id))
    return 0


@ffi.callback('int(ParserUserData*, Node*, Node*)', error=-1)
def append_node(parser, parent, child):
    parser = ffi.from_handle(ffi.cast('void*', parser))
    parent = ffi.from_handle(ffi.cast('void*', parent))
    child = ffi.from_handle(ffi.cast('void*', child))
    parser.tree_builder.append_node(parent, child)
    return 0


@ffi.callback('int(ParserUserData*, Node*, Utf8Slice)', error=-1)
def append_text(parser, parent, data):
    parser = ffi.from_handle(ffi.cast('void*', parser))
    parent = ffi.from_handle(ffi.cast('void*', parent))
    parser.tree_builder.append_text(parent, str_from_slice(data))
    return 0


@ffi.callback('int(ParserUserData*, Node*, Node*)', error=-1)
def insert_node_before_sibling(parser, sibling, new_sibling):
    parser = ffi.from_handle(ffi.cast('void*', parser))
    sibling = ffi.from_handle(ffi.cast('void*', sibling))
    new_sibling = ffi.from_handle(ffi.cast('void*', new_sibling))
    return parser.tree_builder.insert_node_before_sibling(sibling, new_sibling)


@ffi.callback('int(ParserUserData*, Node*, Utf8Slice)', error=-1)
def insert_text_before_sibling(parser, sibling, data):
    parser = ffi.from_handle(ffi.cast('void*', parser))
    sibling = ffi.from_handle(ffi.cast('void*', sibling))
    return parser.tree_builder.insert_text_before_sibling(sibling, str_from_slice(data))


@ffi.callback('int(ParserUserData*, Node*, Node*)', error=-1)
def reparent_children(parser, parent, new_parent):
    parser = ffi.from_handle(ffi.cast('void*', parser))
    parent = ffi.from_handle(ffi.cast('void*', parent))
    new_parent = ffi.from_handle(ffi.cast('void*', new_parent))
    parser.tree_builder.reparent_children(parent, new_parent)
    return 0


@ffi.callback('int(ParserUserData*, Node*)', error=-1)
def remove_from_parent(parser, node):
    parser = ffi.from_handle(ffi.cast('void*', parser))
    node = ffi.from_handle(ffi.cast('void*', node))
    parser.tree_builder.remove_from_parent(node)
    return 0


def check_null(pointer):
    if pointer == ffi.NULL:
        raise RustPanic()
    else:
        return pointer


def check_int(value):
    if value < 0:
        raise RustPanic()
    else:
        return value


class RustPanic(Exception):
    '''Some Rust code panicked. This is a bug.'''


CALLBACKS = check_null(capi.declare_callbacks(
    ffi.NULL, ffi.NULL, ffi.NULL, ffi.NULL,
    create_element, get_template_contents, add_attribute_if_missing,
    create_comment, append_doctype_to_document,
    append_node, append_text, insert_node_before_sibling, insert_text_before_sibling,
    reparent_children, remove_from_parent))
