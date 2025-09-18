#!/usr/bin/env python3
"""Setup script for Phonenv."""

from pathlib import Path
from setuptools import setup, find_packages

# Read README for long description
README_PATH = Path(__file__).parent / "README.md"
long_description = README_PATH.read_text(encoding="utf-8") if README_PATH.exists() else ""

setup(
    name="phonenv",
    version="0.1.0",
    author="shameedjob",
    description="A Python library for phonetic environment analysis",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/shameedjob/phonenv",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Science/Research",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
        "Topic :: Text Processing :: Linguistic",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
    python_requires=">=3.7",
    install_requires=[
        "regex>=2021.0",  # For Unicode-aware pattern matching and grapheme clusters
    ],
    extras_require={
        "enhanced": [
            "panphon>=0.20",  # For professional IPA segmentation and feature analysis
            "rich>=10.0",     # For enhanced terminal output
        ],
        "dev": [
            "pytest>=6.0",
            "black>=21.0",
            "flake8>=3.9",
            "mypy>=0.910",
        ],
    },
    entry_points={
        "console_scripts": [
            "phonenv=phonenv_cl:main",
        ],
    },
    include_package_data=True,
    package_data={
        "": ["data/*.txt"],
    },
)