# Makefile for doc_processor common tasks

.PHONY: setup test lint clean run

setup:
	python -m venv venv
	venv/bin/pip install -r requirements.txt

run:
	venv/bin/python -m doc_processor.app

test:
	venv/bin/pytest tests/

lint:
	venv/bin/flake8 .

clean:
	rm -rf __pycache__ venv *.pyc */__pycache__ */*.pyc
