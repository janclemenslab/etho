## Ethodrome documentation

The docs are published at [https://janclemenslab.org/etho]().

Requires:

- `mamba install sphinx furo sphinx-inline-tabs sphinx-copybuttonmam ghp-import myst-nb sphinx-panels -c conda-forge`  # need the latest version for proper light/dark mode
- `pip install sphinxcontrib-images`

### Build
Build the docs via `make clean html`. A fully-rendered HTML version will be built in `docs/_build/html/`.

### Publish
Publish the book by running `make clean html push`. This will build the book and push the build static html files to the [https://github.com/janclemenslab/etho/tree/gh-pages]() and make it accessible via [https://janclemenslab.org/etho]().
