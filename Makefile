.PHONY: check generate test clean

check:
	python3 -m netforge examples/lab.toml --check

generate:
	python3 -m netforge examples/lab.toml --output generated --clean

test:
	python3 -m unittest discover -s tests -v

clean:
	rm -rf generated build dist *.egg-info netforge_iac.egg-info
