"""
Setup script for KiCad LCSC Manager Plugin
"""
from setuptools import setup, find_packages
from pathlib import Path

# Read README
readme_file = Path(__file__).parent / "README.md"
long_description = readme_file.read_text(encoding="utf-8") if readme_file.exists() else ""

# Read requirements
requirements_file = Path(__file__).parent / "requirements.txt"
requirements = []
if requirements_file.exists():
    requirements = requirements_file.read_text().strip().split('\n')

setup(
    name="kicad-lcsc-manager",
    version="0.1.0",
    author="Your Name",
    author_email="your.email@example.com",
    description="KiCad plugin for importing components from LCSC/EasyEDA and JLCPCB",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/kicad-lcsc-manager",
    packages=find_packages(where="plugins"),
    package_dir={"": "plugins"},
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Topic :: Scientific/Engineering :: Electronic Design Automation (EDA)",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
    python_requires=">=3.8",
    install_requires=requirements,
    include_package_data=True,
    package_data={
        "lcsc_manager": [
            "resources/*",
        ],
    },
    entry_points={
        "console_scripts": [
            "lcsc-manager=lcsc_manager.cli:main",
        ],
    },
    keywords="kicad pcb eda lcsc jlcpcb easyeda electronics",
    project_urls={
        "Bug Reports": "https://github.com/yourusername/kicad-lcsc-manager/issues",
        "Source": "https://github.com/yourusername/kicad-lcsc-manager",
    },
)
