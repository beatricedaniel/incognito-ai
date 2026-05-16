.PHONY: eval

eval:
	uv run pytest -m eval --tb=short -q
	@test -f tests/evaluation/eval_results.json && echo "\nResults: tests/evaluation/eval_results.json" || true
