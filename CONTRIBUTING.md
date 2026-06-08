# Contributing

Thank you for your interest in contributing to `etho`.

## Reporting issues

Please use the GitHub issue tracker to report bugs, request features, or ask questions. When possible, include:

- a minimal reproducible example
- operating system and Python version
- output of `etho version`
- relevant log output or error messages

## Development setup

Clone the repository and install the package in editable mode:

```bash

git clone https://github.com/janclemenslab/etho.git
cd etho
uv venv --python 3.14
source .venv\Scripts\activate
uv pip install -e ".[dev,doc]"
```

## Running tests

Run the test suite locally before submitting changes with `pytest`. Continuous integration (CI) tests are automatically run on all pull requests and must pass before merging.
