# Scanned and Leaked – Hybrid URL Leak Detection System

This repository contains the hybrid leak detection framework used in the study:

**"Scanned and Leaked: Measuring Sensitive Data Exposure in Public URL Repositories."**

The system analyzes publicly accessible URLs and identifies potential exposure of sensitive information using a combination of heuristic analysis and automated artifact inspection.

---

## Overview

The detection pipeline identifies potential privacy leaks through multiple analysis stages, including:

- Lexical filtering of suspicious URL parameters
- Structural heuristic analysis
- Live URL validation
- Dynamic page rendering using Selenium
- Multi-layer HTML inspection
- OCR-based extraction from rendered content
- Artifact analysis (e.g., screenshots and documents)

These components allow the system to detect sensitive information exposed through URL parameters, rendered web content, embedded documents, and visual artifacts.

---

## Repository Structure

main.py
Core hybrid detection pipeline

scanners/
Source-specific URL collection scripts


---

## Disclaimer

This system is intended strictly for **research and defensive security analysis**.

The system analyzes only publicly accessible resources and **does not attempt authentication bypass, intrusion, or exploitation** of protected systems.

---

## License

This project is licensed under **Creative Commons Attribution–NonCommercial 4.0 (CC BY-NC 4.0)**.

See the `LICENSE` file for details.
