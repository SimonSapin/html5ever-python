from html5ever import html5ever_capi

def test_is_ascii_lowercase():
    assert html5ever_capi.is_ascii_lowercase(ord('a'))
    assert not html5ever_capi.is_ascii_lowercase(ord('A'))
    assert not html5ever_capi.is_ascii_lowercase(ord('-'))
