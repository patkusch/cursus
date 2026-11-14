# Changelog

All notable changes to this project are listed here, newest first.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added
- A readable page report, with tests for its questions, sources, checks and table escaping.

## [0.1.0] - 2026-10-03

First version. You write a process down in plain text and get a Visio flow chart, with the sentence behind every box.

- Reading the process with a local model, and asking the author to close any gaps.
- A scoreboard that marks a model's readings against eleven reference processes, with a first run of two local models and later runs of three stronger models.
- Every generated Visio file is opened by a second program on each push, including Microsoft's free Visio Viewer, so a broken file fails the build.
- Readings that were right are no longer refused.
