# Silent Spill – Heuristic URL Leak Detection System

This repository contains the heuristic-based detection pipeline used in the paper:

"The Silent Spill: Measuring Sensitive Data Leaks Across Public URL Repositories"

## Overview

This system detects potential sensitive data exposure in publicly accessible URLs using:

- Lexical URL filtering
- Structural heuristics
- Dynamic rendering (Selenium)
- OCR-based extraction
- Multi-layer HTML inspection

## Structure

- main.py – Core heuristic detection pipeline
- scanners/ – Source-specific collection scripts


## Disclaimer

This system is intended for research and defensive security analysis only.
It does not attempt authentication bypass or active exploitation.

## License

See LICENSE file.
