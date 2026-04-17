.PHONY: up smoke compile test

up:
	./scripts/dev_up.sh

smoke:
	./scripts/dev_smoke.sh

compile:
	python -m compileall app tests run.py

test:
	pytest -q
