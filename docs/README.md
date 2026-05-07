# Documentation
- _Install_ etho with the `doc` extra: `uv pip install etho[doc]`.
- _Build_ the docs via `make clean html`. A fully-rendered HTML version will be built in `docs/_build/html/`.
- _Publish_ the book by running `make clean html push`. This will build the book, push the static HTML files to [gh-pages](https://github.com/janclemenslab/etho/tree/gh-pages), and make it accessible at [janclemenslab.org/etho](https://janclemenslab.org/etho/).
