clean:
	rm -rf *.egg-info
	rm -rf .eggs

configure:
	pip install poetry==1.4.2

lint:
	flake8 tibanna

build:
	make configure
	poetry install

install:
	poetry install

test:
	poetry run invoke test --no-flake

retest:  # runs only failed tests from the last test run.
	pytest -vv --last-failed

update:  # updates dependencies
	poetry update

publish:
	# New Python based publish script (2023-09-20).
	poetry run publish-to-pypi

publish-for-ga:
	# Normally this is done like this:
	# -> poetry run publish-to-pypi --noconfirm
	# But this will not work in GA because this repo (tibanna) does not have dcicutils as a
	# dependency in pyproject.toml and the publish-to-pypi is defined within pyproject.toml
	# so it will not find dcicutils, even we install it explicitly here (or in the GA yml file),
	# so we just call the script manually here, just like it is defined in pyproject.toml.
	pip install dcicutils
	python -m dcicutils.scripts.publish_to_pypi --noconfirm

publish-pypi:
	scripts/publish-pypi

publish-docker:
	scripts/publish-docker

help:
	@make info

info:
	@: $(info Here are some 'make' options:)
	   $(info - Use 'make lint' to check style with flake8.)
	   $(info - Use 'make install' to install dependencies using poetry.)
	   $(info - Use 'make publish-pypi' to publish this library to Pypi)
	   $(info - Use 'make publish-docker' to build the docker image and upload it to docker hub.)
	   $(info - Use 'make retest' to run failing tests from the previous test run.)
	   $(info - Use 'make test' to run tests with the normal options we use for CI/CD like GA.)
	   $(info - Use 'make update' to update dependencies (and the lock file))
