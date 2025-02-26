"""
Command-line implementation for triggering mirror synchronization.

This module provides the CLI command for triggering push mirror synchronization
for existing projects. It allows batch processing of projects and controls the
synchronization rate to avoid overloading the GitLab server.
"""

import sys
import argparse
import logging
import traceback
from dotenv import load_dotenv

from gitlab_mirror.core.config import get_env_variable
from gitlab_mirror.core.exceptions import ConfigError, MirrorError
from gitlab_mirror.utils.trigger import process_file  # Import from existing trigger.py

logger = logging.getLogger(__name__)

def setup_logging(level=logging.INFO):
    """Configure logging for the application."""
    logging.basicConfig(
        format="%(asctime)s [%(levelname)s] %(message)s",
        level=level,
    )

def main():
    """Main entry point for the trigger command."""
    # Setup logging
    setup_logging()
    
    # Load environment variables
    load_dotenv()
    
    # Parse command line arguments with enhanced help
    parser = argparse.ArgumentParser(
        description="Trigger synchronization for existing GitLab push mirrors",
        epilog="""
Examples:
    gitlab-mirror-trigger --projects-file=projects.csv
    gitlab-mirror-trigger --projects-file=fix-list.csv --batch-size=10 --delay=1.5
    gitlab-mirror-trigger --projects-file=00-fix.csv --debug

File format:
    The projects file can be either:
    - A CSV file with project paths in the first column
    - A plain text file with one project path per line
    
    Project paths should be full paths including groups (e.g., "group/project")

Notes:
    - This command only triggers synchronization for existing mirrors
    - It does not create new mirrors
    - Failed sync attempts are logged to 04-trigger-failed.csv
    - Rate limiting is controlled with --batch-size and --delay options
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    # Group connection arguments
    connection_group = parser.add_argument_group('GitLab Connection')
    connection_group.add_argument(
        "--source-url",
        help="Source GitLab URL (default: from SOURCE_GITLAB_URL env var)",
        default=get_env_variable("SOURCE_GITLAB_URL")
    )
    connection_group.add_argument(
        "--source-token",
        help="Source GitLab token (default: from SOURCE_GITLAB_TOKEN env var)",
        default=get_env_variable("SOURCE_GITLAB_TOKEN")
    )
    
    # Group input arguments
    input_group = parser.add_argument_group('Input')
    input_group.add_argument(
        "--projects-file",
        help="File with project paths to trigger (CSV or plain text)",
        required=True
    )
    
    # Group behavior arguments
    behavior_group = parser.add_argument_group('Behavior')
    behavior_group.add_argument(
        "--batch-size",
        help="Number of projects to process in one batch (default: 5)",
        type=int,
        default=5
    )
    behavior_group.add_argument(
        "--delay",
        help="Delay between projects in seconds (default: 2.0)",
        type=float,
        default=2.0
    )
    
    # Debug options
    debug_group = parser.add_argument_group('Debug Options')
    debug_group.add_argument(
        "--debug",
        help="Enable debug logging",
        action="store_true"
    )
    
    args = parser.parse_args()
    
    # Enable debug logging if requested
    if args.debug:
        setup_logging(logging.DEBUG)
    
    try:
        # Process the file using the existing function from trigger.py
        process_file(
            file_path=args.projects_file,
            batch_size=args.batch_size,
            delay_between_projects=args.delay
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
