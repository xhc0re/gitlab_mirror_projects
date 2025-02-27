"""
Command-line implementation for removing push mirrors from a CSV file.

This module provides the CLI command for removing GitLab push mirrors
for projects specified in a CSV file.
"""

import argparse
import logging
import sys
import traceback

from dotenv import load_dotenv

from gitlab_mirror.core.config import get_env_variable
from gitlab_mirror.core.exceptions import ConfigError, MirrorError
from gitlab_mirror.utils.batch_remove import remove_mirrors_from_csv

logger = logging.getLogger(__name__)


def setup_logging(level=logging.INFO):
    """Configure logging for the application."""
    logging.basicConfig(
        format="%(asctime)s [%(levelname)s] %(message)s",
        level=level,
    )


def main():
    """Main entry point for the batch remove command."""
    # Setup logging
    setup_logging()

    # Load environment variables
    load_dotenv()

    # Create a more descriptive argument parser with examples and formatting


parser = argparse.ArgumentParser(
    description="Remove push mirrors for projects specified in a CSV file.",
    epilog="""
Examples:
    gitlab-mirror-batch-remove --csv-file=projects.csv
    gitlab-mirror-batch-remove --csv-file=projects.csv --dry-run
    gitlab-mirror-batch-remove --gitlab-url=https://gitlab.source.com --token=glpat-xyz123

Input file formats:
    The command supports several input formats:
    - CSV with headers: source_path,target_group
    - CSV without headers: first column contains project paths
    - Plain text: one project path per line

    Project paths should include the full path with namespace (e.g., "group/project")

Environment Variables:
    SOURCE_GITLAB_URL      GitLab URL to connect to (if --gitlab-url not specified)
    SOURCE_GITLAB_TOKEN    GitLab API token (if --token not specified)
    PROJECTS_FILE          Default CSV file path (if --csv-file not specified)

Output Files:
    batch-remove-failed.csv    List of projects where mirror removal failed

Use Cases:
    - Remove mirrors from a specific set of projects during migration
    - Clean up mirrors for decommissioned projects
    - Remove mirrors in a controlled batch process rather than by pattern
    - Execute mirror removal actions from verification outputs

Related Commands:
    gitlab-mirror-remove       Remove mirrors by pattern or status
    gitlab-mirror-verify       Generate lists of projects needing attention
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

# Group input arguments
input_group = parser.add_argument_group("Input")
input_group.add_argument(
    "--csv-file",
    help="CSV file with project paths (default: from PROJECTS_FILE env var)",
    default=get_env_variable("PROJECTS_FILE", required=False) or "projects.csv",
)

# Group behavior arguments
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

# Check for required arguments
missing = []
if not args.gitlab_url:
    missing.append("gitlab-url")
if not args.token:
    missing.append("token")
if not args.csv_file:
    missing.append("csv-file")

if missing:
    parser.error(f"Missing required arguments: {', '.join(missing)}")

try:
    # Call the utility function
    result = remove_mirrors_from_csv(
        gitlab_url=args.gitlab_url,
        private_token=args.token,
        csv_file=args.csv_file,
        dry_run=args.dry_run,
    )

    # Print summary
    print("\n===== BATCH MIRROR REMOVAL SUMMARY =====")
    print(f"Total projects in CSV: {result['total_projects_in_csv']}")
    print(f"Projects processed: {result['processed_projects']}")
    print(f"Projects skipped (not found): {result['skipped_projects']}")

    if args.dry_run:
        print(f"Mirrors that would be removed: {result['would_remove']}")
    else:
        print(f"Mirrors removed: {result['mirrors_removed']}")

    if result["failed_projects"]:
        print("\nFailed operations:")
        for project in result["failed_projects"][:5]:
            print(f" - {project['project']}: {project['error']}")
        if len(result["failed_projects"]) > 5:
            print(f"  ... and {len(result['failed_projects']) - 5} more")

        # Export failed projects to CSV
        with open("batch-remove-failed.csv", "w", encoding="utf-8") as f:
            f.write("project,error\n")
            for failed in result["failed_projects"]:
                SANITIZED_ERROR = str(failed["error"]).replace(",", ";")
                f.write(f"{failed['project']}, {SANITIZED_ERROR}\n")
        print(
            f"Exported {len(result['failed_projects'])} failed projects to batch-remove-failed.csv"
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
