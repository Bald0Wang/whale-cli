.PHONY: install web test doctor run-web release

install:
	python -m pip install -e ".[dev]"

web:
	./scripts/build_web.sh

test:
	python -m pytest
	npm --prefix webui run build

doctor:
	whale-doctor --web

run-web: web
	whale-web

release:
	./scripts/release_check.sh
