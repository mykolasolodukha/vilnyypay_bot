.PHONY: env
env:
	poetry install

.PHONY: style
style:
	poetry run black .
	poetry run isort .
	poetry run pylint .
	poetry run pydocstyle .

.PHONY: extract-locales
extract-locales:
	poetry run pybabel extract --input-dirs . --output ./locales/messages.pot

.PHONY: compile-locales
compile-locales:
	poetry run pybabel compile --directory ./locales

.PHONY: run
run:
	poetry run python ./main.py
