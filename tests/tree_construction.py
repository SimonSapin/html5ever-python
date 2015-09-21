import os.path
from html5ever import parse


def test_tree_construction(test):
    document = parse(test[b'data'])


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
    yield test
