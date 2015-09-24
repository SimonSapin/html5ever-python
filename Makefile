VENV = ~/.virtualenvs/html5ever

test:
	@${VENV}/bin/python setup.py -q develop
	@${VENV}/bin/py.test -q

bench:
	@${VENV}/bin/python benchmarks/run.py | tee benchmarks/results-cpython3
	@${VENV}-py2/bin/python benchmarks/run.py | tee benchmarks/results-cpython2
	@${VENV}-pypy/bin/python benchmarks/run.py | tee benchmarks/results-pypy
