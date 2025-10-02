#!/usr/bin/env python3
"""Setup script for Phonenv."""

from pathlib import Path
from setuptools import setup

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
    maintainer="jhnwnstd",
    description=(
        "Phonetic environment analysis with Unicode-correct IPA processing, "
        "automatic normalization, and validation — originally by shameedjob; "
        "major contributions by jhnwnstd."
    ),
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
        "linguistics",
        "transcription",
        "environment-analysis",
    ],
    py_modules=[
        "analyze",
        "data",
        "main",
        "normalize",
        "phonenv_io",
        "utils",
        "validate",
    ],
    classifiers=[
        "Intended Audience :: Science/Research",
        "Intended Audience :: Education",
        "Topic :: Text Processing :: Linguistic",
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
        "regex>=2021.0",
    ],
    extras_require={
        "enhanced": [
            "panphon>=0.20",
            "rich>=10.0",
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
            "phonenv=main:main",
        ],
    },
    include_package_data=True,
    data_files=[
        ("phonenv_data", ["data/dataset.txt", "data/targets.txt"]),
    ],
    zip_safe=False,
    platforms=["any"],
)
