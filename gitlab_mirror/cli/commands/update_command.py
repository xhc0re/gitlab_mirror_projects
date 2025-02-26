"""
Command-line implementation for updating push mirrors.

This module provides the CLI command for updating GitLab push mirrors
to fix authentication issues, update tokens, or change domain URLs.
It can help migrate mirrors to a new domain or fix broken mirrors.
"""

import argparse
import logging
import sys
import traceback

from dotenv import load_dotenv

from gitlab_mirror.core.config import get_env_variable
from gitlab_mirror.core.exceptions import ConfigError, MirrorError
from gitlab_mirror.utils.update import update_mirrors

logger = logging.getLogger(__name__)


def setup_logging(level=logging.INFO):
    """Configure logging for the application."""
    logging.basicConfig(
        format="%(asctime)s [%(levelname)s] %(message)s",
        level=level,
    )


def main():
    """Main entry point for the update command."""
    # Setup logging
    setup_logging()

    # Load environment variables
    load_dotenv()

    # Parse command line arguments with enhanced help
    parser = argparse.ArgumentParser(
        description="Update or fix GitLab push mirrors with new authentication or URLs",
        epilog="""
Examples:
  gitlab-mirror-update --pattern="gitlab.old.com"
  gitlab-mirror-update --old-domain="gitlab.old.com" --new-domain="gitlab.new.com"
  gitlab-mirror-update --update-failed --dry-run

Use cases:
  - Update mirror authentication after token rotation
  - Migrate mirrors to a new GitLab domain
  - Fix broken mirrors with authentication errors
  - Perform domain migration for GitLab instances

Notes:
  - Mirrors with update failures will be removed if they cannot be fixed
  - Failed updates are logged to 05-update-failed-projects.csv
  - Use --dry-run to preview changes before applying them
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # Group connection arguments
    connection_group = parser.add_argument_group("GitLab Connection")
    connection_group.add_argument(
        "--source-url",
        help="Source GitLab URL (default: from SOURCE_GITLAB_URL env var)",
        default=get_env_variable("SOURCE_GITLAB_URL"),
    )
    connection_group.add_argument(
        "--source-token",
        help="Source GitLab token (default: from SOURCE_GITLAB_TOKEN env var)",
        default=get_env_variable("SOURCE_GITLAB_TOKEN"),
    )
    connection_group.add_argument(
        "--target-token",
        help="Target GitLab token (default: from TARGET_GITLAB_TOKEN env var)",
        default=get_env_variable("TARGET_GITLAB_TOKEN"),
    )

    # Group selection criteria
    selection_group = parser.add_argument_group("Selection Criteria")
    selection_group.add_argument(
        "--pattern", help="Regex pattern to match mirror URLs", default=None
    )
    selection_group.add_argument(
        "--update-failed",
        help="Update mirrors with authentication errors (default: true)",
        action="store_true",
        dest="update_failed",
    )
    selection_group.add_argument(
        "--no-update-failed",
        help="Don't update mirrors with authentication errors",
        action="store_false",
        dest="update_failed",
    )
    parser.set_defaults(update_failed=True)

    # Group update options
    update_group = parser.add_argument_group("Update Options")
    update_group.add_argument(
        "--old-domain", help="Old domain to replace in mirror URLs", default=None
    )
    update_group.add_argument(
        "--new-domain",
        help="New domain to use in mirror URLs (required if --old-domain is specified)",
        default=None,
    )

    # Group behavior arguments
    behavior_group = parser.add_argument_group("Behavior")
    behavior_group.add_argument(
        "--dry-run", help="Test without making changes", action="store_true", default=False
    )

    # Debug options
    debug_group = parser.add_argument_group("Debug Options")
    debug_group.add_argument("--debug", help="Enable debug logging", action="store_true")

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
    if not args.target_token:
        missing.append("target-token")

    # Check that new-domain is provided if old-domain is specified
    if args.old_domain and not args.new_domain:
        parser.error("--new-domain is required when --old-domain is specified")

    if missing:
        parser.error(f"Missing required arguments: {', '.join(missing)}")

    try:
        # Run the update operation using the existing function from update.py
        update_mirrors(
            gitlab_url=args.source_url,
            private_token=args.source_token,
            new_mirror_token=args.target_token,
            pattern=args.pattern,
            update_failed=args.update_failed,
            old_domain=args.old_domain,
            new_domain=args.new_domain,
            dry_run=args.dry_run,
        )

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
