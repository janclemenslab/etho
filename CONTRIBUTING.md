# Contributing

Thank you for your interest in contributing to `etho`.

## Platform scope

`etho` is tested as runtime software for Windows acquisition rigs. The hardware
stack depends on vendor SDKs, which may also work on macOS or Linux but have
not been tested with `etho`. Development, unit tests, and documentation work can
be done on Windows, macOS, or Linux when hardware SDKs are not required. Keep
user-facing installation and run instructions Windows-focused; use
cross-platform commands only for contributor workflows.

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
conda create -n etho -c conda-forge -y python=3.14 uv pip git
conda activate etho
uv pip install -e ".[dev,doc]"
```

Use Python 3.14 by default. Use Python 3.10 instead when reproducing behavior
for hardware SDKs that only provide Python 3.10 bindings.

## Running tests

Run the test suite locally before submitting changes:

```bash
python -m pytest
```

Use the same activated environment where you installed the editable package. Continuous integration (CI) tests are automatically run on all pull requests and must pass before merging.
