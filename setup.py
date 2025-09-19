#!/usr/bin/env python3
"""Setup script for Phonenv."""

from pathlib import Path
from setuptools import setup, find_packages

ROOT = Path(__file__).parent
README_PATH = ROOT / "README.md"

try:
    long_description = README_PATH.read_text(encoding="utf-8")
except Exception:
    long_description = ""

setup(
    name="phonenv",
    version="2.0.0",
    author="shameedjob",
    description="A robust Python library for phonetic environment analysis with comprehensive validation and multiple output formats",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/shameedjob/phonenv",
    project_urls={
        "Documentation": "https://github.com/shameedjob/phonenv#readme",
        "Source": "https://github.com/shameedjob/phonenv",
        "Issues": "https://github.com/shameedjob/phonenv/issues",
    },
    license="MIT",
    license_files=["LICENSE"],
    keywords=[
        "phonetics",
        "phonology",
        "IPA",
        "unicode",
        "linguistics",
        "text-processing",
        "segmentation",
        "transcription",
        "validation",
        "environment-analysis",
    ],
    py_modules=["analysis", "cli", "data", "phonenv_io", "validate", "utils"],
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Science/Research",
        "Intended Audience :: Education",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
        "Topic :: Text Processing :: Linguistic",
        "Topic :: Text Processing :: General",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.8",
    install_requires=[
        "regex>=2021.0",  # Unicode-aware regex/grapheme clustering
    ],
    extras_require={
        "enhanced": [
            "panphon>=0.20",  # IPA segmentation and feature analysis
            "rich>=10.0",     # Enhanced terminal output
        ],
        "dev": [
            "pytest>=6.0",
            "black>=21.0",
            "flake8>=3.9",
            "mypy>=1.0",
        ],
        "test": [
            "pytest>=6.0",
            "pytest-cov>=2.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "phonenv=cli:main",
        ],
    },
    include_package_data=True,
    data_files=[
        ("phonenv_data", ["data/dataset.txt", "data/targets.txt"]),
    ],
    zip_safe=False,
    platforms=["any"],
)