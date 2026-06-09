# Documentation
- User-facing installation and run docs should target Windows acquisition rigs.
  macOS and Linux are fine for building docs and running development checks
  that do not require hardware SDKs.

- _Install_ etho with the `dev` and `doc` extras in the conda environment:
  ```bash
  conda create -n etho -c conda-forge -y python=3.14 uv pip git
  conda activate etho
  uv pip install -e ".[dev,doc]"
  ```

- _Build_ the docs via `make clean html`. A fully-rendered HTML version will be built in `docs/_build/html/`.

- _Publish_ the book by running `make clean html push`. This will build the book, push the static HTML files to [gh-pages](https://github.com/janclemenslab/etho/tree/gh-pages), and make it accessible at [janclemenslab.org/etho](https://janclemenslab.org/etho/).
