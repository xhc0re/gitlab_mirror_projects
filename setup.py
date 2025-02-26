from setuptools import find_packages, setup

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="gitlab-mirror",
    version="1.0.0",
    author="Your Name",
    author_email="your.email@example.com",
    description="Tool for mirroring GitLab projects between instances",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/gitlab-mirror",
    packages=find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.7",
    install_requires=[
        "python-gitlab>=5.3,<6.0",
        "python-dotenv>=1.0,<2.0",
        "cryptography>=44.0,<45.0",
        "pydantic>=2.0.0,<3.0.0",
        "pandas>=2.0.0,<3.0.0",
        "setuptools>=75.8,<76.0",
    ],
    extras_require={
        "dev": [
            "black>=23.3.0",
            "isort>=5.12.0",
            "flake8>=6.0.0",
            "mypy>=1.3.0",
            "pre-commit>=3.3.2",
            "pytest>=7.3.1",
            "pytest-cov>=4.1.0",
            "bandit>=1.7.5",
            "sphinx>=6.2.1",
            "sphinx-rtd-theme>=1.2.2",
        ],
    },
    entry_points={
        "console_scripts": [
            "gitlab-mirror=gitlab_mirror.cli.main:main",
            "gitlab-mirror-verify=gitlab_mirror.cli.commands.verify_command:main",
            "gitlab-mirror-update=gitlab_mirror.cli.commands.update_command:main",
            "gitlab-mirror-trigger=gitlab_mirror.cli.commands.trigger_command:main",
            "gitlab-mirror-remove=gitlab_mirror.cli.commands.remove_command:main",
            "gitlab-mirror-batch-remove=gitlab_mirror.cli.commands.batch_remove_command:main",
        ],
    },
)
