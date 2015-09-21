VENV = ~/.virtualenvs/html5ever

test:
	@${VENV}/bin/python setup.py -q develop
	@${VENV}/bin/py.test -q
