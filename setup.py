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
    description="A Python library for phonetic environment analysis",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/shameedjob/phonenv",
    project_urls={
        "Documentation": "https://github.com/shameedjob/phonenv#readme",
        "Source": "https://github.com/shameedjob/phonenv",
        "Issues": "https://github.com/shameedjob/phonenv/issues",
    },
    license="MIT",
    license_files=["LICENSE", "LICENSE.txt", "LICENSE.md"],
    keywords=[
        "phonetics",
        "phonology",
        "IPA",
        "unicode",
        "linguistics",
        "text-processing",
    ],
    packages=find_packages(include=["phonenv", "phonenv.*"], exclude=("tests", "tests.*")),
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
        # Add newer versions here only when you test them
    ],
    python_requires=">=3.7",
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
            "mypy>=0.910",
        ],
    },
    entry_points={
        "console_scripts": [
            # Ensure phonenv/cli.py:main exists or point to your actual entry function.
            "phonenv=phonenv.cli:main",
        ],
    },
    include_package_data=True,
    package_data={
        # Attach data explicitly to the package to avoid implicit top-level globs.
        "phonenv": ["data/*.txt"],
    },
    zip_safe=False,
    platforms=["any"],
)