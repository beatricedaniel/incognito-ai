.PHONY: eval

eval:
	uv run pytest -m eval --tb=short -q
