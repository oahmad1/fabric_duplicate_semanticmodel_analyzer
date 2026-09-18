# Contributing

Thanks for helping improve the Fabric Duplicate Semantic Model Analyzer.

## Local setup

This project intentionally has no runtime Python package dependencies for offline comparison and tests.

```powershell
python --version
python -m unittest discover -s tests
```

## Development workflow

1. Create or update synthetic metadata in `samples\`.
2. Update scanner behavior in `tools\semantic_model_duplicate_finder.py`.
3. Add or update tests in `tests\`.
4. Regenerate expected outputs in `results\` when report formats change.
5. Update `README.md`, `TESTING_GUIDE.md`, and `TEST_RESULTS.md` when user-facing behavior changes.

## Regenerate dummy results

```powershell
python .\tools\semantic_model_duplicate_finder.py compare --input .\samples\dummy_semantic_models.json --format md --output .\results\dummy-test-results.md
python .\tools\semantic_model_duplicate_finder.py compare --input .\samples\dummy_semantic_models.json --format csv --output .\results\dummy-test-results.csv
python .\tools\semantic_model_duplicate_finder.py compare --input .\samples\dummy_semantic_models.json --format json --output .\results\dummy-test-results.json
python .\tools\semantic_model_duplicate_finder.py compare --input .\samples\dummy_semantic_models.json --format html --output .\results\dummy-test-results.html
```

## Pull request checklist

- Tests pass with `python -m unittest discover -s tests`.
- Public docs do not contain local machine paths, secrets, tokens, or customer data.
- New report fields are documented.
- Synthetic samples remain fictional.

