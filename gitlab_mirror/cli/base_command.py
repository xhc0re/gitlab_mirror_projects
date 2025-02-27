"""
Base command utilities for standardizing CLI interfaces.
"""

import argparse
import logging
import sys
import traceback
from typing import Any, Callable, List, Optional

from dotenv import load_dotenv

from gitlab_mirror.core.config import get_env_variable
from gitlab_mirror.core.exceptions import ConfigError, MirrorError


def setup_logging(level: int = logging.INFO) -> None:
    """
    Configure logging for the application with a standardized format.

    Args:
        level: Logging level (default: INFO)
    """
    logging.basicConfig(
        format="%(asctime)s [%(levelname)s] %(message)s",
        level=level,
    )


class BaseCommand:
    """Base class for standardizing command-line interfaces."""

    def __init__(
        self,
        description: str,
        epilog: Optional[str] = None,
        formatter_class: Any = argparse.RawDescriptionHelpFormatter,
    ):
        """
        Initialize the base command.

        Args:
            description: Command description for help text
            epilog: Optional epilog text for help output
            formatter_class: Argument parser formatter class
        """
        # Setup logging
        setup_logging()

        # Load environment variables
        load_dotenv()

        # Create parser
        self.parser = argparse.ArgumentParser(
            description=description, epilog=epilog, formatter_class=formatter_class
        )

        # Add common argument groups
        self.connection_group = self.parser.add_argument_group("GitLab Connection")
        self.behavior_group = self.parser.add_argument_group("Behavior")
        self.debug_group = self.parser.add_argument_group("Debug Options")

        # Add standard arguments
        self._add_standard_arguments()

    def _add_standard_arguments(self) -> None:
        """Add standard arguments that apply to most commands."""
        self.connection_group.add_argument(
            "--source-url",
            help="Source GitLab URL (default: from SOURCE_GITLAB_URL env var)",
            default=get_env_variable("SOURCE_GITLAB_URL"),
        )
        self.connection_group.add_argument(
            "--source-token",
            help="Source GitLab token (default: from SOURCE_GITLAB_TOKEN env var)",
            default=get_env_variable("SOURCE_GITLAB_TOKEN"),
        )

        self.debug_group.add_argument("--debug", help="Enable debug logging", action="store_true")

    def add_target_connection_args(self) -> None:
        """Add target connection arguments for commands that need them."""
        self.connection_group.add_argument(
            "--target-url",
            help="Target GitLab URL (default: from TARGET_GITLAB_URL env var)",
            default=get_env_variable("TARGET_GITLAB_URL"),
        )
        self.connection_group.add_argument(
            "--target-token",
            help="Target GitLab token (default: from TARGET_GITLAB_TOKEN env var)",
            default=get_env_variable("TARGET_GITLAB_TOKEN"),
        )

    def add_projects_file_arg(self, required: bool = False) -> None:
        """
        Add projects file argument to the parser.

        Args:
            required: Whether the argument is required
        """
        self.parser.add_argument(
            "--projects-file",
            help="CSV file with project mappings (default: from PROJECTS_FILE env var)",
            ddefault=get_env_variable("PROJECTS_FILE", required=False) or "projects.csv",
            required=required,
        )

    def add_dry_run_arg(self) -> None:
        """Add dry run argument to the parser."""
        self.behavior_group.add_argument(
            "--dry-run",
            help="Only show what would be done, don't actually make changes",
            action="store_true",
            default=False,
        )

    def parse_args(self) -> argparse.Namespace:
        """
        Parse command line arguments.

        Returns:
            Parsed command line arguments
        """
        args = self.parser.parse_args()

        # Enable debug logging if requested
        if args.debug:
            setup_logging(logging.DEBUG)

        return args

    def verify_required_args(self, args: argparse.Namespace, required_args: List[str]) -> None:
        """
        Verify required arguments are present.

        Args:
            args: Parsed command line arguments
            required_args: List of required argument names

        Raises:
            SystemExit: If any required arguments are missing
        """
        missing = []
        for arg_name in required_args:
            if not getattr(args, arg_name.replace("-", "_")):
                missing.append(arg_name)

        if missing:
            self.parser.error(f"Missing required arguments: {', '.join(missing)}")
            sys.exit(1)

    def run_command(self, command_func: Callable, *args, **kwargs) -> None:
        """
        Run the command function with standardized error handling.

        Args:
            command_func: Function to run
            *args: Positional arguments for the command function
            **kwargs: Keyword arguments for the command function
        """
        try:
            command_func(*args, **kwargs)
        except ConfigError as e:
            logging.error("Configuration error: %s", e)
            sys.exit(1)
        except MirrorError as e:
            logging.error("Mirror operation failed: %s", e)
            sys.exit(2)
        except Exception as e:
            logging.error("Unexpected error: %s", e)
            traceback.print_exc()
            sys.exit(3)
