
# Javascript helper functions

Bokeh often uses `CustomJS` snippets to make the client-side behaviour
more fluid. Over time we have accumulated more and more sophisticated
uses of client-side code.

## Install nodejs dependencies needed by forest.js

To install the local dependencies simply run `npm install`, this
should create a `node_modules` directory and a `package.lock` JSON file.

```bash
# Installation instructions
npm install
```

## Build forest-min.js using npm

The `package.json` contains a command to build `forest-min.js` that
can be invoked as follows from inside this directory.

```bash
# Build /static/forest-min.js
npm run build
```

## Run all of the tests

The JS test framework is Jest, this has two useful modes. It can run all
tests to check everything works and it comes with a `--watch` facility
to rerun tests on file save

```bash
# Run test suite once
npm test
```

To watch files and re-run tests on save.

```bash
# Run test suite and watch for file changes
npm run watch
```

## Conclusions

A good starting point for a more automated client-side build

