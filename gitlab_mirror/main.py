"""
Main entry point for the GitLab mirroring tool.
Provides backward compatibility with the old interface.
"""

import sys
from gitlab_mirror.cli.main import main

if __name__ == "__main__":
    sys.exit(main())