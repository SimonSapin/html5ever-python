import gc
from html5ever import Parser, parse

def test_parser_gc():
    deleted = [False]
    class RecordDel(object):
        def __del__(self):
            deleted[0] = True

    parser = Parser()
    parser.document.record_del = RecordDel()
    assert not deleted[0]

    del parser
    gc.collect()
    assert deleted[0]

def test_feed():
    Parser().feed(b'a<a>')

def test_parse():
    parse(b'a<a>')
