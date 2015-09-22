import os.path
import pprint
import pytest
from html5ever import *


def test_tree_construction(test):
    document = parse(test[b'data'])
    serialized = ''.join(serialize(document))[:-1]  # Drop the trailing newline
    expected = test[b'document'].decode('utf8')
    if serialized != expected:
        pprint.pprint(test)
        print(serialized)
        print(expected)
        assert serialized == expected


def pytest_generate_tests(metafunc):
    # https://github.com/servo/html5ever/blob/v0.2.4/data/test/ignore
    ignore = set('''
        ruby.dat-0
        ruby.dat-1
        ruby.dat-10
        ruby.dat-12
        ruby.dat-13
        ruby.dat-15
        ruby.dat-17
        ruby.dat-2
        ruby.dat-20
        ruby.dat-3
        ruby.dat-5
        ruby.dat-7
        tests19.dat-18
        tests19.dat-21
        tests20.dat-34
        tests20.dat-35
        tests20.dat-36
        tests20.dat-37
    '''.split())
    tests = []
    ids = []
    base = os.path.join(os.path.dirname(__file__), 'html5lib-tests', 'tree-construction')
    for name in os.listdir(base):
        if name.endswith('.dat'):
            with open(os.path.join(base, name), 'rb') as fd:
                for i, test in enumerate(parse_tests(fd)):
                    id_ = '%s-%s' % (name, i)
                    ids.append(id_)
                    if b'document-fragment' in test or b'script-off' in test or id_ in ignore:
                        test = pytest.mark.xfail(test)
                    tests.append(test)
    metafunc.parametrize('test', tests, ids=ids)


def parse_tests(fd):
    key = None
    lines = []
    test = {}
    for line in fd:
        line = line.rstrip(b'\n')
        if line.startswith(b'#'):
            if line == b'#data' and lines and not lines[-1]:
                lines.pop()  # Drop the empty line separating tests
            if key:
                assert key not in test
                test[key] = b'\n'.join(lines)
            lines = []
            key = line.rstrip()[1:]
            if key == b'data' and test:
                yield test
                test = {}
        else:
            lines.append(line)
    if key:
        assert key not in test
        test[key] = b'\n'.join(lines)
    if test:
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
