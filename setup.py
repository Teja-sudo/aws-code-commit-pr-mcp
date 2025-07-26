#!/usr/bin/env python3
"""
Setup script for AWS PR Review MCP Server
"""

from setuptools import setup, find_packages
import os

# Read the README file
def read_readme():
    with open("README.md", "r", encoding="utf-8") as fh:
        return fh.read()

# Read requirements
def read_requirements():
    with open("requirements.txt", "r", encoding="utf-8") as fh:
        return [line.strip() for line in fh if line.strip() and not line.startswith("#")]

setup(
    name="aws-pr-mcp",
    version="1.0.0",
    author="Enterprise Security Team",
    author_email="security@company.com",
    description="A comprehensive MCP server for AWS PR reviews with security analysis and compliance checking",
    long_description=read_readme(),
    long_description_content_type="text/markdown",
    url="https://github.com/company/aws-pr-mcp",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "Intended Audience :: System Administrators",
        "Topic :: Software Development :: Quality Assurance",
        "Topic :: Security",
        "Topic :: System :: Systems Administration",
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
    install_requires=read_requirements(),
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-asyncio>=0.21.0",
            "pytest-cov>=4.0.0",
            "black>=23.0.0",
            "flake8>=6.0.0",
            "mypy>=1.0.0",
            "isort>=5.12.0",
        ],
        "security": [
            "bandit>=1.7.0",
            "safety>=2.0.0",
        ],
        "analysis": [
            "pandas>=2.0.0",
            "numpy>=1.24.0",
        ],
        "git": [
            "GitPython>=3.1.0",
        ],
        "terraform": [
            "python-hcl2>=4.0.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "aws-pr-mcp=server:main",
        ],
    },
    keywords=[
        "aws",
        "security",
        "compliance",
        "mcp",
        "claude",
        "pull-request",
        "review",
        "infrastructure",
        "cloud",
        "devops",
        "boto3",
    ],
    project_urls={
        "Bug Reports": "https://github.com/company/aws-pr-mcp/issues",
        "Documentation": "https://github.com/company/aws-pr-mcp/wiki",
        "Source": "https://github.com/company/aws-pr-mcp",
    },
    include_package_data=True,
    package_data={
        "": ["*.md", "*.txt", "*.yml", "*.yaml", "*.json"],
    },
    zip_safe=False,
)