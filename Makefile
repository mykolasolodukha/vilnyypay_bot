.PHONY: env
env:
	poetry install

.PHONY: style
style:
	poetry run black .
	poetry run isort .
	poetry run pylint .
	poetry run pydocstyle .

.PHONY: run
run:
	poetry run python ./main.py
