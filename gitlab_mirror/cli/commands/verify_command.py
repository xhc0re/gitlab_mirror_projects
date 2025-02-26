"""
Command-line implementation for verifying push mirrors.

This module provides the CLI command for verifying that all projects
from a CSV file have been properly mirrored between GitLab instances.
It checks for missing projects, missing mirrors, and failed mirrors,
and generates reports for troubleshooting.
"""

import sys
import argparse
import logging
import traceback

from pathlib import Path
from dotenv import load_dotenv

from pydantic import SecretStr
from gitlab_mirror.core.config import GitLabConfig, MirrorConfig, get_env_variable
from gitlab_mirror.core.exceptions import ConfigError, MirrorError
from gitlab_mirror.core.mirror import MirrorService
from gitlab_mirror.utils.verify import MirrorVerifier

logger = logging.getLogger(__name__)

def setup_logging(level=logging.INFO):
    """Configure logging for the application."""
    logging.basicConfig(
        format="%(asctime)s [%(levelname)s] %(message)s",
        level=level,
    )

def main():
    """Main entry point for the verify command."""
    # Setup logging
    setup_logging()
    
    # Load environment variables
    load_dotenv()
    
    # Parse command line arguments with enhanced help
    parser = argparse.ArgumentParser(
        description="Verify GitLab projects have been properly mirrored between instances",
        epilog="""
Examples:
    gitlab-mirror-verify
    gitlab-mirror-verify --projects-file=custom-projects.csv
    gitlab-mirror-verify --debug

Output files:
    01-missing-in-target.csv  Projects missing in target GitLab instance
    02-missing-mirrors.csv    Projects without push mirrors configured
    03-failed-mirrors.csv     Projects with failed mirrors (e.g. auth errors)
    00-fix.csv                Combined list of all projects that need fixing

The generated 00-fix.csv can be used with gitlab-mirror to fix the issues:
    gitlab-mirror --projects-file=00-fix.csv
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
    connection_group.add_argument(
        "--target-url",
        help="Target GitLab URL (default: from TARGET_GITLAB_URL env var)",
        default=get_env_variable("TARGET_GITLAB_URL")
    )
    connection_group.add_argument(
        "--target-token",
        help="Target GitLab token (default: from TARGET_GITLAB_TOKEN env var)",
        default=get_env_variable("TARGET_GITLAB_TOKEN")
    )
    
    # Group input arguments
    input_group = parser.add_argument_group('Input')
    input_group.add_argument(
        "--projects-file",
        help="CSV file with project mappings (default: from PROJECTS_FILE env var)",
        default=get_env_variable("PROJECTS_FILE", "projects.csv")
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
        parser.error(f"Missing required arguments: {', '.join(missing)}")
    
    try:
        config = MirrorConfig(
            source=GitLabConfig(url=args.source_url, token=SecretStr(args.source_token)),
            target=GitLabConfig(url=args.target_url, token=SecretStr(args.target_token)),
            projects_file=Path(args.projects_file),
        )
        
        service = MirrorService(config)
        
        # Load project mappings
        project_mappings = service.load_project_mappings()
        
        print(f"Loaded {len(project_mappings)} project mappings from {args.projects_file}")
        print("Starting verification process - this may take some time...")
        
        # Create verifier
        verifier = MirrorVerifier(config.source, config.target, project_mappings)
        
        # Run verification
        verifier.verify_all_projects()
        
        # Print report
        verifier.print_report()
        
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
