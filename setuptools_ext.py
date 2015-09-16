import os.path
import shutil
import subprocess
import sys
from distutils import log

try:
    basestring
except NameError:
    # Python 3.x
    basestring = str


if sys.platform == 'win32':
    DYNAMIC_LIB_SUFFIX = '.dll'
elif sys.platform == 'darwin':
    DYNAMIC_LIB_SUFFIX = '.dylib'
else:
    DYNAMIC_LIB_SUFFIX = '.so'


def rust_crates(dist, attr, value):
    assert attr == 'rust_crates'
    if isinstance(value, basestring):
        value = [value]

    release = False

    for crate, destination in value:
        args = ['cargo', 'build', '--manifest-path', os.path.join(crate, 'Cargo.toml')]
        if release:
            args.append('--release')
        log.info(' '.join(args))
        subprocess.check_call(args)

        target = os.path.join(crate, 'target', 'release' if release else 'debug')
        libs = [name for name in os.listdir(target) if name.endswith(DYNAMIC_LIB_SUFFIX)]
        assert libs
        for lib in libs:
            shutil.copy(os.path.join(target, lib), os.path.join(destination, lib))

    # Tell bdist_wheel to include the CPU architecture in the wheel file name.
    # FIXME: Can we do that but *not* include the Python version/implementation?
    dist.is_pure = lambda: False
