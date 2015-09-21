import os.path
from ._ffi import ffi

capi = ffi.dlopen(os.path.join(os.path.dirname(__file__), 'libhtml5ever_capi.so'))


def parse(bytes):
    parser = Parser()
    parser.feed(bytes)
    return parser.document


class Parser(object):
    def __init__(self):
        self._keep_alive_handles = []
        self._template_contents_keep_alive_handles = {}
        self.document = Document()
        self._ptr = check_null(capi.new_parser(
            CALLBACKS, self._keep_alive(self), self._keep_alive(self.document)))

    def __del__(self):
        # Do this here rather than through ffi.gc:
        # by the time ffi.gc would trigger, self.refcounts might have been removed already.
        check_int(capi.destroy_parser(self._ptr))

    def feed(self, bytes_chunk):
        data = ffi.new('char[]', bytes_chunk)
        slice_ = ffi.new('BytesSlice*', (data, len(bytes_chunk)))
        check_int(capi.feed_parser(self._ptr, slice_[0]))

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
    '''Abstract base class for all nodes in the tree.'''
    def __init__(self):
        self.parent = None
        self.children = []


class Document(Node):
    '''A document node, the root of the tree.'''


class DocumentFragment(Node):
    '''A document fragement node.'''


HTML_NAMESPACE = 'http://www.w3.org/1999/xhtml'


class Element(Node):
    '''An element node.'''
    def __init__(self, qualified_name, namespace_url, local_name):
        super(Element, self).__init__()
        self.qualified_name = ffi.gc(
            qualified_name,
            lambda q: check_int(capi.destroy_qualified_name(q)))
        self.name = (namespace_url, local_name)
        self.attributes = {}
        self.template_contents = None


class Text(Node):
    '''A text node.'''
    def __init__(self, data):
        super(Text, self).__init__()
        self.data = data


class Comment(Node):
    '''A comment node.'''
    def __init__(self, data):
        super(Comment, self).__init__()
        self.data = data


class Doctype(Node):
    '''A doctype node.'''
    def __init__(self, name, public_id, system_id):
        super(Doctype, self).__init__()
        self.name = name
        self.public_id = public_id
        self.system_id = system_id


def str_from_slice(slice_):
    return ffi.buffer(slice_.ptr, slice_.len)[:].decode('utf-8')


@ffi.callback('Node*(ParserUserData*, QualifiedName*, Utf8Slice, Utf8Slice)')
def create_element(parser, qualified_name, namespace_url, local_name):
    parser = ffi.from_handle(ffi.cast('void*', parser))
    element = Element(qualified_name, str_from_slice(namespace_url), str_from_slice(local_name))
    if element.name == (HTML_NAMESPACE, 'template'):
        element.template_contents = DocumentFragment()
        parser._template_contents_keep_alive_handles[element] = \
            ffi.new_handle(element.template_contents)
    return parser._keep_alive(element)


@ffi.callback('QualifiedName*(ParserUserData*, Node*)')
def element_name(_parser, element):
    element = ffi.from_handle(ffi.cast('void*', element))
    return element.qualified_name


@ffi.callback('Node*(ParserUserData*, Node*)')
def get_template_contents(parser, element):
    parser = ffi.from_handle(ffi.cast('void*', parser))
    element = ffi.from_handle(ffi.cast('void*', element))
    return parser._template_contents_keep_alive_handles[element]


@ffi.callback('int(ParserUserData*, Node*, Utf8Slice, Utf8Slice, Utf8Slice)', error=-1)
def add_attribute_if_missing(_parser, element, namespace_url, local_name, value):
    element = ffi.from_handle(ffi.cast('void*', element))
    element.attributes.setdefault(
        (str_from_slice(namespace_url), str_from_slice(local_name)),
        str_from_slice(value))
    return 0


@ffi.callback('Node*(ParserUserData*, Utf8Slice)')
def create_comment(parser, data):
    parser = ffi.from_handle(ffi.cast('void*', parser))
    return parser._keep_alive(Comment(str_from_slice(data)))


@ffi.callback('int(ParserUserData*, Utf8Slice, Utf8Slice, Utf8Slice)', error=-1)
def append_doctype_to_document(parser, name, public_id, system_id):
    parser = ffi.from_handle(ffi.cast('void*', parser))
    parser.document.children.append(Doctype(
        str_from_slice(name),
        str_from_slice(public_id),
        str_from_slice(system_id)))
    return 0


@ffi.callback('int(ParserUserData*, Node*, Node*)', error=-1)
def append_node(_parser, parent, child):
    parent = ffi.from_handle(ffi.cast('void*', parent))
    child = ffi.from_handle(ffi.cast('void*', child))
    child.parent = parent
    parent.children.append(child)
    return 0


@ffi.callback('int(ParserUserData*, Node*, Utf8Slice)', error=-1)
def append_text(_parser, parent, data):
    parent = ffi.from_handle(ffi.cast('void*', parent))
    data = str_from_slice(data)
    if parent.children and isinstance(parent.children[-1], Text):
        parent.children[-1].data += data
    else:
        child = Text(data)
        child.parent = parent
        parent.children.append(child)
    return 0


@ffi.callback('int(ParserUserData*, Node*, Node*)', error=-1)
def insert_node_before_sibling(_parser, sibling, child):
    sibling = ffi.from_handle(ffi.cast('void*', sibling))
    parent = sibling.parent
    if parent is None:
        return 0
    child = ffi.from_handle(ffi.cast('void*', child))
    position = parent.children.index(sibling)
    parent.children.insert(position, child)
    return 1


@ffi.callback('int(ParserUserData*, Node*, Utf8Slice)', error=-1)
def insert_text_before_sibling(_parser, sibling, data):
    sibling = ffi.from_handle(ffi.cast('void*', sibling))
    parent = sibling.parent
    if parent is None:
        return 0
    data = str_from_slice(data)
    position = parent.children.index(sibling)
    if position > 0 and isinstance(parent.children[position - 1], Text):
        parent.children[position - 1].data += data
    else:
        child = Text(data)
        child.parent = parent
        parent.children.insert(position, child)
    return 1


@ffi.callback('int(ParserUserData*, Node*, Node*)', error=-1)
def reparent_children(_parser, parent, new_parent):
    parent = ffi.from_handle(ffi.cast('void*', parent))
    new_parent = ffi.from_handle(ffi.cast('void*', new_parent))
    for child in parent.children:
        child.parent = new_parent
    new_parent.children.extend(parent.children)
    parent.children.clear()
    return 0


@ffi.callback('int(ParserUserData*, Node*)', error=-1)
def remove_from_parent(_parser, node):
    node = ffi.from_handle(ffi.cast('void*', node))
    if node.parent is not None:
        node.parent.children.remove(node)
        node.parent = None
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
    create_element, element_name, get_template_contents, add_attribute_if_missing,
    create_comment, append_doctype_to_document,
    append_node, append_text, insert_node_before_sibling, insert_text_before_sibling,
    reparent_children, remove_from_parent))
