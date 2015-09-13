from html5ever import libc

def test_islower():
    assert libc.islower(ord('a'))
    assert not libc.islower(ord('A'))
    assert not libc.islower(ord('-'))
