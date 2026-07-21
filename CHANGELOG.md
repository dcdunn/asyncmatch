# Changelog

All notable changes to this project will be documented in this file.

The format is based on Keep a Changelog.

## [0.1.0] - 2026-07-21

### Added
- Added Python packaging metadata in pyproject.toml so the project can be installed with pip.
- Added project URLs and runtime dependency metadata.
- Added installation instructions in README.md for installing from GitHub (branch, tag, and commit), plus editable local install.

### Changed
- Lowered minimum supported Python version from 3.10 to 3.9.
- Replaced Python 3.10 union type syntax with Python 3.9-compatible typing.Union in asyncmatch/assert_eventually.py.

### Fixed
- Ignored setuptools egg-info directories in .gitignore.
