"""
Command-line implementation for removing push mirrors.

This module provides the CLI command for removing GitLab push mirrors
based on specified criteria such as URL pattern matching or failure status.
"""

import argparse
import logging
import sys
import traceback

from dotenv import load_dotenv

from gitlab_mirror.core.config import get_env_variable
from gitlab_mirror.core.exceptions import ConfigError, MirrorError
from gitlab_mirror.utils.remove import remove_mirrors

logger = logging.getLogger(__name__)


def setup_logging(level=logging.INFO):
    """Configure logging for the application."""
    logging.basicConfig(
        format="%(asctime)s [%(levelname)s] %(message)s",
        level=level,
    )


def main():
    """Main entry point for the remove command."""
    # Setup logging
    setup_logging()

    # Load environment variables
    load_dotenv()

    # Parse command line arguments with enhanced help
    parser = argparse.ArgumentParser(
        description="Remove push mirrors from GitLab projects based on specified criteria.",
        epilog="""
Examples:
    gitlab-mirror-remove --pattern="old-domain.com"
    gitlab-mirror-remove --remove-failed
    gitlab-mirror-remove --pattern="test" --dry-run

Environment Variables:
    SOURCE_GITLAB_URL      GitLab URL to connect to
    SOURCE_GITLAB_TOKEN    GitLab API token
    MIRROR_PATTERN         Default regex pattern for matching mirror URLs
    REMOVE_FAILED_MIRRORS  Whether to remove failed mirrors (true/false)

Warning:
    Removing mirrors is irreversible. Use --dry-run to preview changes.
    The --all flag will remove ALL mirrors from ALL projects - use with caution!
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # Group connection arguments
    connection_group = parser.add_argument_group("GitLab Connection")
    connection_group.add_argument(
        "--gitlab-url",
        help="GitLab URL (default: from SOURCE_GITLAB_URL env var)",
        default=get_env_variable("SOURCE_GITLAB_URL"),
    )
    connection_group.add_argument(
        "--token",
        help="GitLab token (default: from SOURCE_GITLAB_TOKEN env var)",
        default=get_env_variable("SOURCE_GITLAB_TOKEN"),
    )

    # Group selection criteria
    selection_group = parser.add_argument_group("Selection Criteria (at least one required)")
    selection_group.add_argument(
        "--pattern",
        help="Regex pattern to match mirror URLs (default: from MIRROR_PATTERN env var)",
        default=get_env_variable("MIRROR_PATTERN", required=False),
    )
    selection_group.add_argument(
        "--remove-failed",
        help="Remove mirrors with errors (default: from REMOVE_FAILED_MIRRORS env var)",
        action="store_true",
        default=get_env_variable("REMOVE_FAILED_MIRRORS", required=False) == "true",
    )
    selection_group.add_argument(
        "--all",
        help="WARNING: Remove ALL mirrors from ALL projects",
        action="store_true",
        default=False,
    )

    # Group behavior options
    behavior_group = parser.add_argument_group("Behavior")
    behavior_group.add_argument(
        "--dry-run",
        help="Only show what would be removed, don't actually remove",
        action="store_true",
        default=False,
    )

    # Debug options
    debug_group = parser.add_argument_group("Debug Options")
    debug_group.add_argument("--debug", help="Enable debug logging", action="store_true")

    args = parser.parse_args()

    # Enable debug logging if requested
    if args.debug:
        setup_logging(logging.DEBUG)

    pattern = args.pattern
    if pattern and not pattern.startswith("^") and not pattern.endswith("$"):
        # If pattern is plain text, escape dots for regex
        pattern = pattern.replace(".", "\\.")

    # Check for required arguments
    missing = []
    if not args.gitlab_url:
        missing.append("gitlab-url")
    if not args.token:
        missing.append("token")

    # Check to see if at least one mirrored selection condition is given
    if not args.pattern and not args.remove_failed and not args.all:
        logger.error(
            "No selection criteria provided. Please specify at least one of: --pattern, --remove-failed, or --all"
        )
        logger.error("You can also set MIRROR_PATTERN or REMOVE_FAILED_MIRRORS in your .env file")
        sys.exit(1)

    if missing:
        parser.error(f"Missing required arguments: {', '.join(missing)}")

    try:
        if args.dry_run:
            print(
                "DRY RUN MODE: No mirrors will be removed. Run without --dry-run to remove mirrors."
            )

            if args.all:
                print("Would remove ALL mirrors from ALL projects")
            else:
                if args.pattern:
                    print(f"Would remove mirrors matching pattern: '{args.pattern}'")
                if args.remove_failed:
                    print("Would remove failed mirrors")

            # Call the function in dry-run mode to display statistics
            result = remove_mirrors(
                gitlab_url=args.gitlab_url,
                private_token=args.token,
                pattern=args.pattern,
                remove_failed=args.remove_failed,
                remove_all=args.all,
                dry_run=True,
            )

            print(
                f"\nWould remove approximately {result['would_remove']} mirrors from {result['matching_projects']} projects"
            )
            sys.exit(0)

        # Print information about what will be done
        if args.all:
            print("WARNING: You are about to remove ALL mirrors from ALL projects!")
            confirmation = input(
                "Are you ABSOLUTELY sure? This cannot be undone. Type 'YES' (all capitals) to confirm: "
            )
            if confirmation != "YES":
                print("Operation cancelled.")
                sys.exit(0)
        else:
            action_description = []
            if args.pattern:
                action_description.append(f"mirrors matching pattern '{args.pattern}'")
            if args.remove_failed:
                action_description.append("failed mirrors")

            print(f"Removing {' and '.join(action_description)} from {args.gitlab_url}")
            confirmation = input(
                "Are you sure you want to remove these mirrors? This cannot be undone. (yes/no): "
            )
            if confirmation.lower() not in ["yes", "y"]:
                print("Operation cancelled.")
                sys.exit(0)

        # Run the remove operation
        result = remove_mirrors(
            gitlab_url=args.gitlab_url,
            private_token=args.token,
            pattern=args.pattern,
            remove_failed=args.remove_failed,
            remove_all=args.all,
        )

        # Print summary
        print("\n===== MIRROR REMOVAL SUMMARY =====")
        print(f"Total projects processed: {result['processed_projects']}")
        print(f"Projects with mirrors: {result['projects_with_mirrors']}")
        print(f"Mirrors removed: {result['mirrors_removed']}")
        print(f"Errors encountered: {result['errors']}")

        if result["failed_projects"]:
            print("\nFailed projects:")
            for project in result["failed_projects"][:5]:
                print(f"  - {project['project']}: {project['error']}")
            if len(result["failed_projects"]) > 5:
                print(f"  ... and {len(result['failed_projects']) - 5} more")

    except ConfigError as e:
        logger.error("Configuration error: %s", e)
        sys.exit(1)
    except MirrorError as e:
        logger.error("Mirror operation failed: %s", e)
        sys.exit(2)
    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.error("Unexpected error: %s", e)
        traceback.print_exc()
        sys.exit(3)


if __name__ == "__main__":
    main()
