"""
Command-line interface for GitLab mirroring tool.
"""

import argparse
import logging
import os

from dotenv import load_dotenv

from gitlab_mirror.cli.commands.mirror_command import mirror_command


def setup_logging(level=logging.INFO):
    """Configure logging for the application."""
    logging.basicConfig(
        format="%(asctime)s [%(levelname)s] %(message)s",
        level=level,
    )


def main():
    """Main entry point for the CLI tool."""
    # Setup logging
    setup_logging()

    # Load environment variables
    load_dotenv()

    # Parse command line arguments
    parser = argparse.ArgumentParser(description="GitLab Project Mirroring Tool")

    parser.add_argument(
        "--source-url", help="Source GitLab URL", default=os.environ.get("SOURCE_GITLAB_URL", "")
    )
    parser.add_argument(
        "--source-token",
        help="Source GitLab token",
        default=os.environ.get("SOURCE_GITLAB_TOKEN", ""),
    )
    parser.add_argument(
        "--target-url", help="Target GitLab URL", default=os.environ.get("TARGET_GITLAB_URL", "")
    )
    parser.add_argument(
        "--target-token",
        help="Target GitLab token",
        default=os.environ.get("TARGET_GITLAB_TOKEN", ""),
    )
    parser.add_argument(
        "--projects-file",
        help="CSV file with project mappings",
        default=os.environ.get("PROJECTS_FILE", "projects.csv"),
    )
    parser.add_argument(
        "--assign-users",
        help="Assign users from source to target groups",
        action="store_true",
        default=os.environ.get("ASSIGN_USERS_TO_GROUPS", "false").lower() in ("true", "1", "yes"),
    )
    parser.add_argument("--debug", help="Enable debug logging", action="store_true")
    parser.add_argument(
        "--shallow",
        action="store_true",
        help="Perform shallow clone (no history) for faster migration",
    )

    args = parser.parse_args()

    # Enable debug logging if requested
    if args.debug:
        setup_logging(logging.DEBUG)

    # Check for required arguments
    missing = []
    if not args.source_url:
        missing.append("source-url")
    if not args.source_token:
        missing.append("source-token")
    if not args.target_url:
        missing.append("target-url")
    if not args.target_token:
        missing.append("target-token")

    if missing:
        parser.error("Missing required arguments: %s" % ", ".join(missing))

    # Run the mirror command
    mirror_command(
        source_url=args.source_url,
        source_token=args.source_token,
        target_url=args.target_url,
        target_token=args.target_token,
        projects_file=args.projects_file,
        assign_users=args.assign_users,
    )


if __name__ == "__main__":
    main()
