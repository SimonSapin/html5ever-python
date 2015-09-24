import hashlib
import html5ever.elementtree
import html5lib
import lxml.html
import os.path
import re
import subprocess
import sys
import timeit
try:
    from urllib.request import urlopen  # Python 3.x
except ImportError:
    from urllib import urlopen


def run(url, quick=False):
    html = urlopen(url).read()
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    print('Python {}'.format(sys.version.replace('\n', ' ')))
    if not quick:
        print('rustc {}'.format(rustc_version()))
        print('html5ever {}'.format(html5ever_version(root)))
        print('lxml {}'.format(lxml.etree.LXML_VERSION))
        print('libxml {}'.format(lxml.etree.LIBXML_COMPILED_VERSION))
        print('htmllib {}'.format(html5lib.__version__))
        print('')
        print('HTML source SHA1: {}'.format(hashlib.sha1(html).hexdigest()))
        print('Best time of 3, parsing {:,} bytes of HTML:'.format(len(html)))
        print('')
        bench_rust(root, html)
        bench('lxml.html', lambda: lxml.html.fromstring(html))
    bench('html5ever-python', lambda: html5ever.parse(html))
    bench('html5ever-python to ElementTree',
          lambda: html5ever.parse(html, tree_builder=html5ever.elementtree.TreeBuilder))
    if not quick:
        bench('html5lib to ElementTree', lambda: html5lib.parse(html))
        bench('html5lib to lxml', lambda: html5lib.parse(html, treebuilder='lxml'))


def rustc_version():
    stdout, stderr = subprocess.Popen(['rustc', '--version'], stdout=subprocess.PIPE).communicate()
    return stdout.strip()


def html5ever_version(root):
    with open(os.path.join(root, 'rust-glue', 'Cargo.lock'), 'rb') as fd:
        return re.search(b'html5ever ([\d.]+)', fd.read()).group(1).decode('utf8')


def bench_rust(root, html):
    subprocess.check_call([
        'cargo', 'test', '--no-run', '--release', '--manifest-path',
        os.path.join(root, 'rust-glue', 'Cargo.toml'),
    ])
    subprocess.Popen(
        [os.path.join(root, 'rust-glue', 'target', 'release', 'examples', 'time_parse_stdin')],
        stdin=subprocess.PIPE,
    ).communicate(html)


def bench(name, func):
    print('{}: {:.3f} seconds'.format(name, min(timeit.repeat(func, number=1, repeat=3))))


if __name__ == '__main__':
    quick = '--quick' in sys.argv
    if quick:
        sys.argv.remove('--quick')
    if len(sys.argv) > 1:
        url = sys.argv[1]
    else:
        url = 'https://raw.githubusercontent.com/whatwg/html/d8717d8831c276ca65d2d44bbf2ce4ce673997b9/source'
    run(url, quick)
