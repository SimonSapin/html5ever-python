from setuptools import setup

setup(
    name='html5ever',
    url='https://github.com/SimonSapin/html5ever-python',
    license='MIT / Apache-2.0',
    packages=['html5ever'],
    setup_requires=["cffi>=1.0.0"],
    install_requires=["cffi>=1.0.0"],
    cffi_modules=["html5ever/_build_ffi.py:ffi"],
)
