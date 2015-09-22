import os.path
import pprint
from html5ever import *


def test_tree_construction(test):
    document = parse(test[b'data'].rstrip(b'\n'))
    serialized = ''.join(serialize(document)).rstrip('\n')
    expected = test[b'document'].rstrip(b'\n').decode('utf8')
    if serialized != expected:
        pprint.pprint(test)
        print(serialized)
        print(expected)
        assert serialized == expected


def pytest_generate_tests(metafunc):
    tests = []
    ids = []
    base = os.path.join(os.path.dirname(__file__), 'html5lib-tests', 'tree-construction')
    for name in os.listdir(base):
        if name.endswith('.dat'):
            with open(os.path.join(base, name), 'rb') as fd:
                for i, test in enumerate(parse_tests(fd)):
                    tests.append(test)
                    ids.append('%s-%s' % (name, i))
    metafunc.parametrize('test', tests, ids=ids)


def parse_tests(fd):
    assert next(iter(fd)).rstrip() == b'#data'
    key = b'data'
    value = b''
    test = {}
    for line in fd:
        if line.startswith(b'#'):
            assert key not in test
            test[key] = value
            value = b''
            key = line.rstrip()[1:]
            if key == b'data':
                assert test
                yield test
                test = {}
        else:
            value += line
    assert test
    assert key not in test
    test[key] = value
    yield test


def serialize(node, indent=1):
    if isinstance(node, Document):
        for child in node.children:
            yield from serialize(child, indent)
        return

    yield '|'
    yield ' ' * indent

    if isinstance(node, Doctype):
        yield '<!DOCTYPE '
        yield node.name
        if node.public_id or node.system_id:
            yield ' "%s" "%s"' % (node.public_id, node.system_id)
        yield '>\n'

    elif isinstance(node, Text):
        yield '"'
        yield node.data
        yield '"\n'

    elif isinstance(node, Comment):
        yield '<!-- '
        yield node.data
        yield ' -->\n'

    else:
        assert isinstance(node, Element)
        yield '<'
        namespace_url, local_name = node.name
        if namespace_url == SVG_NAMESPACE:
            yield 'svg '
        elif namespace_url == MATHML_NAMESPACE:
            yield 'math '
        else:
            assert namespace_url == HTML_NAMESPACE
        yield local_name
        yield '>\n'

        for (namespace_url, local_name), value in sorted(node.attributes.items()):
            yield '|'
            yield ' ' * (indent + 2)
            if namespace_url == XLINK_NAMESPACE:
                yield 'xlink '
            elif namespace_url == XML_NAMESPACE:
                yield 'xml '
            elif namespace_url == XMLNS_NAMESPACE:
                yield 'xmlns '
            else:
                assert not namespace_url
            yield '%s="%s"\n' % (local_name, value)

    for child in node.children:
        yield from serialize(child, indent + 2)

    if isinstance(node, Element) and node.template_contents:
        yield '|'
        yield ' ' * (indent + 2)
        yield 'content\n'
        for child in node.template_contents.children:
            yield from serialize(child, indent + 4)
