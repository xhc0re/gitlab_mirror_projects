# GitLab Mirror Tool - Complete Installation and Configuration Guide

## 1. Overview

GitLab Mirror Tool is a Python utility for efficiently copying (mirroring) projects between GitLab instances. The tool supports:
- Mirroring projects with preserved original group structure
- Mirroring projects to a new group structure
- Verifying mirror status and generating reports
- Triggering synchronization of existing mirrors
- Updating mirrors with new credentials or URLs
- Removing mirrors individually or in batch mode

## 2. System Requirements

- Python 3.7 or newer
- Git
- Two GitLab instances (source and target)
- Access tokens for both GitLab instances

## 3. Installation

### 3.1. Cloning the Repository

```bash
git clone <REPOSITORY_URL> gitlab-mirror
cd gitlab-mirror
```

### 3.2. Creating a Virtual Environment

```bash
python -m venv .venv
```

### 3.3. Activating the Virtual Environment

On Linux/macOS:
```bash
source .venv/bin/activate
```

On Windows (CMD):
```bash
.venv\Scripts\activate
```

On Windows (PowerShell):
```bash
.venv\Scripts\Activate.ps1
```

### 3.4. Installing Dependencies

```bash
# Install production dependencies
pip install -r requirements.txt

# For development, install development dependencies
pip install -r requirements-dev.txt
```

### 3.5. Development Mode Installation

```bash
pip install -e .
```

## 4. Configuration

### 4.1. Automatic Configuration

Use the included setup script:

```bash
python setup_env.py
```

The script will guide you through the configuration process and create necessary files.

### 4.2. Manual Configuration

1. Create a `.env` file in the project's root directory:

```
SOURCE_GITLAB_URL="https://gitlab.source.com"
SOURCE_GITLAB_TOKEN="your_source_token"
TARGET_GITLAB_URL="https://gitlab.target.com"
TARGET_GITLAB_TOKEN="your_target_token"
PROJECTS_FILE="projects.csv"
ASSIGN_USERS_TO_GROUPS=true
```

2. Create a `projects.csv` file with project mappings:

```csv
group1/project1,newgroup1
group2/subgroup1/project2,
group3/project3,othergroup
```

Format explanation:
- First column: Source project path in source GitLab
- Second column: Target group in target GitLab:
  - If provided, the project will be placed in this group
  - If empty, the original group structure will be preserved

## 5. Usage

### 5.1. Mirroring Projects

```bash
gitlab-mirror
```

Or with explicit parameters:

```bash
gitlab-mirror --source-url=https://gitlab.source.com --source-token=token --target-url=https://gitlab.target.com --target-token=token --projects-file=projects.csv
```

### 5.2. Verifying Mirror Status

```bash
gitlab-mirror-verify --projects-file=projects.csv
```

This command verifies that all projects are properly mirrored and generates reports:
- `01-missing-in-target.csv` - Projects missing in target instance
- `02-missing-mirrors.csv` - Projects without configured mirrors
- `03-failed-mirrors.csv` - Projects with failed mirrors
- `00-fix.csv` - Combined list of all projects needing repair

### 5.3. Triggering Mirror Synchronization

```bash
gitlab-mirror-trigger --projects-file=projects.csv
```

Triggers sync for existing mirrors of projects in the CSV file.

### 5.4. Updating Existing Mirrors

```bash
gitlab-mirror-update --pattern="old-domain" --update-failed
```

Updates mirrors matching the pattern or with authentication errors.

### 5.5. Removing Mirrors

```bash
gitlab-mirror-remove --pattern="test" --dry-run
```

Removes mirrors matching the specified pattern.

### 5.6. Batch Removing Mirrors

```bash
gitlab-mirror-batch-remove --csv-file=projects.csv
```

Removes mirrors for all projects listed in the specified CSV file.

### 5.7. Backward Compatibility

For compatibility with older versions:

```bash
python main.py
```

## 6. Development Tools

The project includes several development tools to ensure code quality:

### 6.1. Code Formatting and Linting

- **Black**: Code formatter
  ```bash
  black gitlab_mirror
  ```

- **isort**: Import sorter
  ```bash
  isort gitlab_mirror
  ```

- **Flake8**: Code linter
  ```bash
  flake8 gitlab_mirror
  ```

- **mypy**: Type checker
  ```bash
  mypy gitlab_mirror
  ```

- **Bandit**: Security scanner
  ```bash
  bandit -r gitlab_mirror
  ```

### 6.2. Pre-commit Hooks

Pre-commit hooks automatically check code quality before commits:

```bash
# Install pre-commit hooks
pre-commit install

# Manually run all hooks
pre-commit run --all-files
```

### 6.3. Testing

```bash
# Run all tests
pytest

# Run tests with coverage report
pytest --cov=gitlab_mirror

# Generate HTML coverage report
pytest --cov=gitlab_mirror --cov-report=html
```

### 6.4. Documentation

The project uses Sphinx for documentation:

```bash
# Build documentation
cd docs
make html

# View documentation
open _build/html/index.html  # On macOS
```

## 7. Shell Completion

### 7.1. Zsh Completion

Zsh completion support is provided for all commands:

1. Copy completion file to a directory in your `$fpath`:
   ```bash
   cp zsh_completions/_gitlab-mirror ~/.zsh/completions/
   ```

2. Add the directory to your `$fpath` in `.zshrc` if not already done:
   ```bash
   fpath=(~/.zsh/completions $fpath)
   ```

3. Reload Zsh or run:
   ```bash
   autoload -U compinit && compinit
   ```

## 8. Project Structure

```
gitlab-mirror/
├── setup.py                           # Package configuration
├── requirements.txt                   # Production dependencies
├── requirements-dev.txt               # Development dependencies
├── pyproject.toml                     # Tool configurations
├── setup.cfg                          # Linter configurations
├── .pre-commit-config.yaml            # Pre-commit hook settings
├── .env.example                       # Example configuration
├── .github/workflows/                 # CI/CD workflows
├── docs/                              # Documentation
├── setup_env.py                       # Configuration script
├── projects.csv                       # Project mappings
├── gitlab_mirror/                     # Main package
│   ├── __init__.py
│   ├── core/                          # Core modules
│   │   ├── __init__.py
│   │   ├── config.py                  # Configuration
│   │   ├── mirror.py                  # Mirror logic
│   │   └── exceptions.py              # Exception definitions
│   ├── utils/                         # Utility modules
│   │   ├── __init__.py
│   │   ├── verify.py                  # Verification
│   │   ├── trigger.py                 # Mirror triggering
│   │   ├── update.py                  # Mirror updates
│   │   ├── remove.py                  # Mirror removal
│   │   └── batch_remove.py            # Batch removal
│   └── cli/                           # CLI interface
│       ├── __init__.py
│       ├── base_command.py            # Common CLI functionality
│       ├── main.py                    # Main entry point
│       └── commands/                  # Command implementations
│           ├── __init__.py
│           ├── mirror_command.py      # Mirror command
│           ├── verify_command.py      # Verify command
│           ├── trigger_command.py     # Trigger command
│           ├── update_command.py      # Update command
│           ├── remove_command.py      # Remove command
│           └── batch_remove_command.py# Batch remove command
└── tests/                             # Tests
    ├── __init__.py
    └── test_imports.py                # Import tests
```

## 9. Troubleshooting

### GitLab Connection Issues
- Verify GitLab URLs are correct
- Ensure tokens have sufficient permissions (API, read_repository, write_repository)

### Mirroring Problems
- Use `gitlab-mirror-verify` to diagnose issues
- Check source GitLab logs for push mirror errors

### Import Problems
- Run `python -m tests.test_imports` to verify imports
- Ensure all dependencies are installed

### Development Tool Issues
- Verify that `pre-commit` is installed and hooks are set up
- Ensure Python version is compatible (Python 3.7+)

## 10. Contributing

### 10.1. Development Workflow

1. Fork the repository
2. Create a feature branch
3. Run tests and linters
4. Submit a pull request

### 10.2. Coding Standards

- Follow Google Python Style Guide
- Document all functions, classes, and modules
- Add tests for new functionality
- Use type annotations where feasible

### 10.3. Commit Message Format

```
component: Brief description

Longer explanation if needed.
```

## 11. Support and Resources

- Report issues via the repository's issue tracker
- For questions, contact the project maintainers
