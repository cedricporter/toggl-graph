all: venv

venv: .env/bin/activate

.env/bin/activate: requirements.txt
	test -d .env || virtualenv .env
	. .env/bin/activate; pip install -Ur requirements.txt
	touch .env/bin/activate

devbuild: venv
	. .env/bin/activate; python setup.py install

test: devbuild
	. .env/bin/activate; python test/runtests.py

clean:
	rm .env -rf
