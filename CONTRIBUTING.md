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
```

Activate the virtual environment on linux or macOS:

```bash
source .venv/bin/activate
```

On Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

On Windows `cmd.exe`:

```bat
.venv\Scripts\activate.bat
```

Then install the package:

```bash
uv pip install -e ".[dev,doc]"
```

## Running tests

Run the test suite locally before submitting changes:

```bash
python -m pytest
```

Use the same activated environment where you installed the editable package. Continuous integration (CI) tests are automatically run on all pull requests and must pass before merging.
