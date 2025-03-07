"""
Module for handling large repository mirroring exceeding the 2 GB push limit.

This module provides functionality to split large repositories into smaller
chunks for pushing to remote GitLab instances, working around the 2 GB
push limit imposed by GitLab.

This module respects the configuration from .env and integrates with the
existing configuration system.
"""

import logging
import os
import shutil
import subprocess
import time
from typing import List, Optional, Tuple, Union

from gitlab_mirror.core.config import get_env_variable

# Configure logging
logger = logging.getLogger(__name__)


def get_repository_size(gitlab_client, project_id: Union[int, str]) -> Optional[float]:
    """
    Get repository size in MB using multiple fallback methods.

    Args:
        gitlab_client: GitLab client instance
        project_id_or_path: Project ID or path

    Returns:
        Repository size in MB, or None if size couldn't be determined
    """
    try:
        response = gitlab_client.http_get(f"/projects/{project_id}?statistics=true")

        if isinstance(response, dict) and "statistics" in response:
            stats = response["statistics"]
            if "repository_size" in stats:
                # GitLab returns size in bytes, convert to MB
                return stats["repository_size"] / (1024.0 * 1024.0)
    except Exception as e:
        logger.debug("Method 3 failed: %s", e)

    # If we reach here, all methods failed
    return None


def is_large_repository(
    gitlab_client, project_id: Union[int, str], threshold_mb: int = 1800
) -> bool:
    """
    Check if a repository exceeds the size threshold for normal mirroring.

    Args:
        gitlab_client: GitLab client instance
        project_id: Project ID or path to check
        threshold_mb: Size threshold in MB (default: 1800)

    Returns:
        True if repository size exceeds threshold, False otherwise
    """
    try:
        size_mb = get_repository_size(gitlab_client, project_id)

        if size_mb is not None:
            logger.info("Repository size of project %s: %.2f MB", project_id, size_mb)
            return size_mb > threshold_mb

        # If we couldn't determine the size, log a warning
        logger.warning(
            "Could not determine repository size for project %s, assuming not large", project_id
        )

        # Check if environment variable is set to force large repo handling
        force_large = get_env_variable("FORCE_LARGE_REPO_HANDLING", required=False)
        if force_large and force_large.lower() in ("true", "yes", "1"):
            logger.info(
                "FORCE_LARGE_REPO_HANDLING is enabled. Treating repository %s as large.", project_id
            )
            return True

        return False

    except Exception as e:
        logger.warning(
            "Error checking repository size for project %s, assuming not large: %s", project_id, e
        )
        return False


class LargeRepoHandler:
    """Handles mirroring of large repositories that exceed the 2 GB push limit."""

    def __init__(
        self,
        source_url: str,
        source_project_path: str,
        source_token: str,
        target_url: str,
        target_project_path: str,
        target_token: str,
        chunk_size: int = 25,
        shallow: bool = False,  # Add this parameter
        keep_temp_dir: bool = True,  # Added parameter to control temp directory cleanup
    ):
        """
        Initialize the large repo handler.

        Args:
            source_url: Source GitLab instance URL (without http/https)
            source_project_path: Full path of source project with namespace
            source_token: Access token for authentication to source GitLab
            target_url: Target GitLab instance URL (without http/https)
            target_project_path: Full path of target project with namespace
            target_token: Access token for authentication to target GitLab
            chunk_size: Number of commits per chunk (default: 25)
            shallow: Whether to do a shallow clone (no history)
            keep_temp_dir: Whether to keep the temp directory after operation (default: True)
        """
        self.source_url = source_url.replace("https://", "").replace("http://", "")
        self.source_project_path = source_project_path
        self.source_token = source_token
        self.target_url = target_url.replace("https://", "").replace("http://", "")
        self.target_project_path = target_project_path
        self.target_token = target_token
        self.chunk_size = chunk_size
        self.shallow = shallow  # Store shallow option
        self.keep_temp_dir = keep_temp_dir  # Store temp dir cleanup preference
        self.temp_dir = None
        self.repo_already_cloned = False  # Flag to track if repo is already cloned
        self.git_env = os.environ.copy()
        # Add custom environment variables for Git if needed
        self.git_env["GIT_TERMINAL_PROMPT"] = "0"  # Disable Git prompts

    def __enter__(self):
        """Context manager entry point."""
        # Create temp directory in ~/tmp/ folder
        home_dir = os.path.expanduser("~")
        tmp_dir = os.path.join(home_dir, "tmp")

        # Ensure the ~/tmp directory exists
        os.makedirs(tmp_dir, exist_ok=True)

        # Create a predictable directory name based on the project path
        # This allows us to reuse the same directory for the same repository
        safe_name = self.source_project_path.replace("/", "_").replace(".", "_")
        repo_temp_dir = os.path.join(tmp_dir, f"gitlab_mirror_{safe_name}")

        if os.path.exists(repo_temp_dir) and self.keep_temp_dir:
            # If directory exists and we're keeping temp dirs, use it
            logger.info("Using existing temporary directory: %s", repo_temp_dir)
            self.temp_dir = repo_temp_dir
            self.repo_already_cloned = os.path.exists(os.path.join(repo_temp_dir, ".git"))
            if self.repo_already_cloned:
                logger.info("Found existing repository clone in temporary directory")
        else:
            # Otherwise create a new temporary directory
            if os.path.exists(repo_temp_dir):
                logger.info("Removing old temporary directory: %s", repo_temp_dir)
                shutil.rmtree(repo_temp_dir, ignore_errors=True)

            os.makedirs(repo_temp_dir, exist_ok=True)
            logger.info("Created temporary directory: %s", repo_temp_dir)
            self.temp_dir = repo_temp_dir
            self.repo_already_cloned = False

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit point to clean up resources."""
        if not self.keep_temp_dir:
            if self.temp_dir and os.path.exists(self.temp_dir):
                logger.info("Removing temporary directory: %s", self.temp_dir)
                shutil.rmtree(self.temp_dir, ignore_errors=True)
        else:
            logger.info("Keeping temporary directory: %s", self.temp_dir)

    def run_git_command(
        self, command: List[str], cwd: Optional[str] = None
    ) -> Tuple[int, str, str]:
        """
        Run a git command and return its output.

        Args:
            command: Git command as a list of strings
            cwd: Working directory for the command

        Returns:
            Tuple of (return_code, stdout, stderr)
        """
        working_dir = cwd or self.temp_dir
        logger.debug("Running git command: %s in %s", " ".join(command), working_dir)

        try:
            process = subprocess.Popen(
                command,
                cwd=working_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=self.git_env,
                universal_newlines=True,
            )
            stdout, stderr = process.communicate()
            return process.returncode, stdout, stderr
        except subprocess.SubprocessError as e:
            logger.error("Git command failed: %s", e)
            return 1, "", str(e)

    def clone_source_repo(self) -> bool:
        """
        Clone the source repository with access token authentication.
        If the repository is already cloned, update it instead.

        Returns:
            True if successful, False otherwise
        """
        # Use personal access token for authentication to source GitLab
        source_repo_url = (
            f"https://oauth2:{self.source_token}@{self.source_url}/{self.source_project_path}.git"
        )

        # Set Git config to handle large repos better
        config_cmds = [
            ["git", "config", "--global", "http.postBuffer", "1048576000"],  # 1GB buffer
            ["git", "config", "--global", "http.lowSpeedLimit", "500"],  # 500B/s minimum speed
            ["git", "config", "--global", "http.lowSpeedTime", "600"],  # 10 min timeout
            ["git", "config", "--global", "http.receivepack", "true"],
            ["git", "config", "--global", "pack.windowMemory", "100m"],  # Lower memory usage
            ["git", "config", "--global", "pack.threads", "1"],  # Single thread
        ]

        for cmd in config_cmds:
            self.run_git_command(cmd)

        if self.repo_already_cloned:
            logger.info("Repository already cloned, updating instead of re-cloning")

            # Check if 'origin' remote exists and update it if needed
            remote_check_cmd = ["git", "remote", "-v"]
            _, stdout, _ = self.run_git_command(remote_check_cmd)

            if "origin" not in stdout:
                logger.info("Adding 'origin' remote")
                add_remote_cmd = ["git", "remote", "add", "origin", source_repo_url]
                self.run_git_command(add_remote_cmd)
            else:
                logger.info("Updating 'origin' remote URL")
                update_remote_cmd = ["git", "remote", "set-url", "origin", source_repo_url]
                self.run_git_command(update_remote_cmd)

            # Fetch the latest changes
            logger.info("Fetching latest changes")
            fetch_cmd = ["git", "fetch", "--all", "--prune"]
            return_code, _, stderr = self.run_git_command(fetch_cmd)

            if return_code != 0:
                logger.error("Failed to fetch updates: %s", stderr)
                return False

            # Reset to the latest state of origin
            reset_cmd = ["git", "reset", "--hard", "origin/HEAD"]
            return_code, _, stderr = self.run_git_command(reset_cmd)

            if return_code != 0:
                # If reset to origin/HEAD fails, try to determine the default branch
                branch_cmd = ["git", "remote", "show", "origin"]
                _, branch_output, _ = self.run_git_command(branch_cmd)

                default_branch = None
                for line in branch_output.split("\n"):
                    if "HEAD branch" in line:
                        default_branch = line.split(":")[-1].strip()
                        break

                if default_branch:
                    logger.info("Resetting to default branch: %s", default_branch)
                    reset_cmd = ["git", "reset", "--hard", f"origin/{default_branch}"]
                    return_code, _, stderr = self.run_git_command(reset_cmd)

                    if return_code != 0:
                        logger.error("Failed to reset repository: %s", stderr)
                        return False
                else:
                    logger.error("Could not determine default branch and reset failed: %s", stderr)
                    return False

            logger.info("Successfully updated repository")
            return True
        else:
            # Clone with depth 1 first to get repository structure faster
            logger.info("Performing shallow clone first to get repository structure")
            shallow_clone_cmd = ["git", "clone", "--depth", "1", source_repo_url, "."]
            return_code, _, stderr = self.run_git_command(shallow_clone_cmd)

            if return_code != 0:
                logger.error("Failed to clone repository: %s", stderr)
                return False

            # Then fetch the rest if this is not a shallow migration
            if not self.shallow:
                logger.info("Fetching complete repository history")
                fetch_cmd = ["git", "fetch", "--unshallow"]
                return_code, _, stderr = self.run_git_command(fetch_cmd)

                if return_code != 0:
                    logger.error("Failed to fetch complete repository: %s", stderr)
                    return False

            logger.info("Successfully cloned source repository")
            return True

    def setup_target_remote(self) -> bool:
        """
        Set up the target repository as a remote.
        If the remote already exists, update its URL.

        Returns:
            True if successful, False otherwise
        """
        target_repo_url = (
            f"https://oauth2:{self.target_token}@{self.target_url}/{self.target_project_path}.git"
        )

        # Check if the remote already exists using simple 'git remote' command
        remote_check_cmd = ["git", "remote"]
        return_code, stdout, stderr = self.run_git_command(remote_check_cmd)

        if return_code != 0:
            logger.error("Failed to check remotes: %s", stderr)
            return False

        # Split the output into lines and clean up
        remotes = [r.strip() for r in stdout.splitlines() if r.strip()]
        logger.debug("Available remotes: %s", remotes)

        # If 'target' is in the list of remotes, update URL, otherwise add it
        if "target" in remotes:
            logger.info("Target remote exists, updating URL")
            cmd = ["git", "remote", "set-url", "target", target_repo_url]
        else:
            logger.info("Target remote does not exist, adding it")
            cmd = ["git", "remote", "add", "target", target_repo_url]

        # Run the appropriate command
        return_code, stdout, stderr = self.run_git_command(cmd)

        if return_code != 0:
            logger.error(
                "Failed to %s target remote: %s", "update" if "target" in remotes else "add", stderr
            )
            return False

        # Verify that the remote now exists and has the correct URL
        verify_cmd = ["git", "remote", "get-url", "target"]
        return_code, stdout, stderr = self.run_git_command(verify_cmd)

        if return_code != 0:
            logger.error("Failed to verify target remote: %s", stderr)
            return False

        logger.info(
            "Target remote successfully configured with URL: %s",
            target_repo_url.replace(self.target_token, "***TOKEN***"),
        )
        return True

    def find_already_pushed_commits(self) -> set:
        """
        Determine which commits have already been pushed to the target repository.
        
        Returns:
            Set of commit SHAs that exist in the target repository
        """
        logger.info("Checking for commits already pushed to target repository")
        
        # First, make sure the target remote is set up correctly
        if not self.setup_target_remote():
            logger.warning("Could not set up target remote to check for existing commits")
            return set()
        
        # Fetch from target to get its current state
        logger.info("Fetching from target repository to get current state")
        fetch_cmd = ["git", "fetch", "target", "--prune"]
        return_code, stdout, stderr = self.run_git_command(fetch_cmd)
        
        if return_code != 0:
            logger.warning("Failed to fetch from target: %s", stderr)
            return set()
        else:
            logger.info("Successfully fetched from target repository")
        
        # List remote branches to find target branches
        remote_branches_cmd = ["git", "branch", "-r"]
        return_code, stdout, stderr = self.run_git_command(remote_branches_cmd)
        
        if return_code != 0:
            logger.warning("Failed to list remote branches: %s", stderr)
            return set()
        
        # Extract only target branches
        target_branches = []
        for line in stdout.splitlines():
            branch = line.strip()
            if branch.startswith("target/"):
                target_branches.append(branch)
        
        logger.info("Found %d target branches: %s", len(target_branches), target_branches)
        
        if not target_branches:
            logger.info("No branches found on target repository")
            return set()
        
        # Get commit count using rev-list on target/master
        if "target/master" in target_branches:
            count_cmd = ["git", "rev-list", "--count", "target/master"]
            return_code, stdout, stderr = self.run_git_command(count_cmd)
            
            if return_code == 0:
                commit_count = int(stdout.strip())
                logger.info("Target repository has %d commits on master branch", commit_count)
            else:
                logger.warning("Failed to get commit count: %s", stderr)
        
        # Get all commit SHAs from target branches
        target_commits = set()
        for branch in target_branches:
            logger.info("Getting commits from branch: %s", branch)
            rev_list_cmd = ["git", "rev-list", branch]
            return_code, stdout, stderr = self.run_git_command(rev_list_cmd)
            
            if return_code != 0:
                logger.warning("Failed to get commit list for branch %s: %s", branch, stderr)
                continue
            
            # Count commits in this branch
            branch_commits = 0
            # Add all commit SHAs to our set
            for commit_sha in stdout.splitlines():
                if commit_sha.strip():
                    target_commits.add(commit_sha.strip())
                    branch_commits += 1
            
            logger.info("Added %d commits from branch %s", branch_commits, branch)
        
        logger.info("Found %d total unique commits already pushed to target repository", len(target_commits))
        
        return target_commits

    def push_in_chunks(self, step: int = 200) -> bool:
        """Push the repository in chunks to avoid the 2 GB limit."""
        # Find all milestone commits
        milestones = self.find_milestones(step)
        
        if not milestones:
            logger.error("No milestone commits found")
            return False
        
        logger.info("Found %d milestone commits", len(milestones))
        logger.debug("Milestone commits: %s", milestones[:10])  # Log first 10 for debugging
        
        # Find what branch we're working with
        branch_check_cmd = ["git", "branch"]
        _, stdout, _ = self.run_git_command(branch_check_cmd)
        available_branches = [b.strip().replace('* ', '') for b in stdout.strip().split("\n") if b.strip()]
        branch = "main"  # Default
        
        if "main" in available_branches:
            branch = "main"
        elif "master" in available_branches:
            branch = "master"
        elif available_branches:
            branch = available_branches[0]
        
        logger.info("Using branch %s for pushing", branch)
        
        # Set up target remote - this must succeed before we continue
        if not self.setup_target_remote():
            logger.error("Failed to set up target remote for pushing")
            return False
        
        # Get commits that already exist on the target
        already_pushed_commits = self.find_already_pushed_commits()
        logger.info("Found %d commits already pushed to target repository", len(already_pushed_commits))
        
        # Force re-push the latest commit to ensure we're up to date
        logger.info("Getting latest commit from source branch")
        latest_cmd = ["git", "rev-parse", "HEAD"]
        return_code, stdout, stderr = self.run_git_command(latest_cmd)
        
        if return_code == 0 and stdout.strip():
            latest_commit = stdout.strip()
            logger.info("Latest commit is %s - force pushing to target", latest_commit)
            
            # Force push the latest commit to ensure we're making progress
            push_latest_cmd = ["git", "push", "target", f"+{latest_commit}:refs/heads/{branch}"]
            return_code, stdout, stderr = self.run_git_command(push_latest_cmd)
            
            if return_code == 0:
                logger.info("Successfully force-pushed latest commit to target")
            else:
                logger.warning("Failed to force-push latest commit: %s", stderr)

        # Set Git push options to handle timeouts better
        push_config_cmds = [
            ["git", "config", "http.postBuffer", "524288000"],  # 500MB buffer
            ["git", "config", "http.lowSpeedLimit", "1000"],
            ["git", "config", "http.lowSpeedTime", "300"],
            ["git", "config", "push.default", "upstream"],
        ]
        
        for cmd in push_config_cmds:
            self.run_git_command(cmd)
        
        # Check if the latest milestone is already pushed
        if milestones and milestones[-1] in already_pushed_commits:
            logger.info("Latest milestone commit %s already exists on target. Repository is up to date.", milestones[-1])
            
            # Do a final mirror push to ensure all refs are synchronized
            logger.info("Performing final mirror push for all refs")
            mirror_cmd = ["git", "push", "target", "--mirror", "--force"]
            
            max_retries = 3
            for attempt in range(1, max_retries + 1):
                mirror_code, _, mirror_stderr = self.run_git_command(mirror_cmd)
                
                if mirror_code == 0:
                    logger.info("Successfully completed mirror push")
                    break
                elif attempt < max_retries:
                    logger.warning("Mirror push attempt %d failed. Retrying...", attempt)
                    time.sleep(5)
                else:
                    logger.warning("Final mirror push had issues after %d attempts: %s", max_retries, mirror_stderr)
            
            return True
        
        # Push each milestone that hasn't been pushed already
        success = True
        max_retries = 3
        commits_pushed = 0
        for commit_sha in milestones:
            # Skip if already pushed
            if commit_sha in already_pushed_commits:
                logger.info("Skipping milestone commit %s - already exists on target", commit_sha)
                continue
                
            logger.info("Pushing milestone commit: %s", commit_sha)
            # Use force push with the + prefix to overcome non-fast-forward errors
            push_cmd = ["git", "push", "target", f"+{commit_sha}:refs/heads/{branch}"]
            
            # Try up to 3 times
            for attempt in range(1, max_retries + 1):
                return_code, _, stderr = self.run_git_command(push_cmd)
                
                if return_code == 0:
                    logger.info("Successfully pushed milestone %s", commit_sha)
                    # Add to our set of already pushed commits
                    already_pushed_commits.add(commit_sha)
                    commits_pushed += 1
                    logger.info("Commits pushed in this session: %d", commits_pushed)
                    break
                elif attempt < max_retries:
                    logger.warning("Push attempt %d failed for %s. Retrying...", attempt, commit_sha)
                    backoff_time = 5 * (2**(attempt-1))  # 5s, 10s, 20s...
                    logger.info("Exponential backoff: Waiting %d seconds before retry", backoff_time)
                    time.sleep(backoff_time)
                else:
                    if "pack exceeds maximum allowed size" in stderr:
                        logger.warning("Pack size exceeded at commit %s, reducing step size", commit_sha)
                        # Reduce step size and try again with just this segment
                        smaller_step = max(50, step // 2)  # Even smaller steps
                        logger.info("Retrying with smaller step size: %d", smaller_step)
                        
                        # Recursively call with smaller step
                        return self.push_in_chunks(step=smaller_step)
                    else:
                        logger.error("Failed to push milestone %s after %d attempts: %s", commit_sha, max_retries, stderr)
                        success = False
        
        logger.info("Finished pushing milestones. Total commits pushed in this session: %d", commits_pushed)
        
        # After pushing all milestones, verify the number of commits on target
        after_push_commits = self.find_already_pushed_commits()
        logger.info("After pushing all milestones, found %d commits on target", len(after_push_commits))
        
        # Final mirror push for any remaining refs - also with retry
        logger.info("Performing final mirror push for all refs")
        mirror_cmd = ["git", "push", "target", "--mirror", "--force"]
        
        for attempt in range(1, max_retries + 1):
            mirror_code, _, mirror_stderr = self.run_git_command(mirror_cmd)
            
            if mirror_code == 0:
                logger.info("Successfully completed mirror push")
                break
            elif attempt < max_retries:
                logger.warning("Mirror push attempt %d failed. Retrying...", attempt)
                time.sleep(5)
            else:
                logger.warning("Final mirror push had issues after %d attempts: %s", max_retries, mirror_stderr)
                # Don't fail the whole operation for this - we already pushed the main branch
        
        # Final verification after mirror push
        final_commits = self.find_already_pushed_commits()
        logger.info("After final mirror push, found %d commits on target", len(final_commits))
        
        return success

    def find_milestones(self, step: int = 1000) -> List[str]:
        """
        Find milestone commits for incremental pushing.

        Args:
            step: Number of commits between milestones (default: 1000)

        Returns:
            List of commit SHAs to use as milestones
        """
        # First, check what branches exist in the repository
        branch_check_cmd = ["git", "branch"]
        return_code, stdout, stderr = self.run_git_command(branch_check_cmd)

        if return_code != 0:
            logger.error("Failed to list branches: %s", stderr)
            return []

        available_branches = [
            b.strip().replace("* ", "") for b in stdout.strip().split("\n") if b.strip()
        ]
        logger.info("Available branches: %s", available_branches)

        # Try to find the default branch
        default_branch = None

        # Method 1: Try HEAD reference
        head_ref_cmd = ["git", "symbolic-ref", "--short", "HEAD"]
        return_code, stdout, stderr = self.run_git_command(head_ref_cmd)
        if return_code == 0 and stdout.strip():
            default_branch = stdout.strip()
            logger.info("Found default branch from HEAD: %s", default_branch)

        # Method 2: Check for common branch names
        if not default_branch:
            for branch in ["main", "master", "develop", "dev"]:
                if branch in available_branches:
                    default_branch = branch
                    logger.info("Using common branch name: %s", default_branch)
                    break

        # Method 3: Just use the first branch in the list
        if not default_branch and available_branches:
            default_branch = available_branches[0]
            logger.info("Using first available branch: %s", default_branch)

        if not default_branch:
            logger.error("Could not determine default branch")
            return []

        # Find milestone commits
        logger.info("Finding milestone commits on branch: %s", default_branch)
        log_cmd = ["git", "log", "--oneline", "--reverse", default_branch]
        return_code, stdout, stderr = self.run_git_command(log_cmd)

        if return_code != 0:
            logger.error("Failed to get commit log: %s", stderr)
            return []

        all_commits = [line for line in stdout.strip().split("\n") if line.strip()]

        if not all_commits:
            logger.error("No commits found in branch %s", default_branch)
            return []

        logger.info("Found %d total commits", len(all_commits))

        # Create milestone list
        milestones = []
        for i, line in enumerate(all_commits):
            if i % step == 0 and line:
                commit_sha = line.split(" ")[0]
                milestones.append(commit_sha)

        logger.info("Created %d milestone commits", len(milestones))
        return milestones

    def mirror_large_repo(self, step: int = 1000) -> bool:
        """
        Execute the full mirroring process for a large repository.

        Args:
            step: Number of commits per chunk (default: 1000)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            logger.info(
                "Starting large repo mirroring: %s -> %s (chunk size: %d commits)",
                self.source_project_path,
                self.target_project_path,
                step
            )
            
            # Clone the source repository
            if not self.clone_source_repo():
                return False
                
            # Set up the target remote
            if not self.setup_target_remote():
                return False
                
            # Check how many commits are already on the target before pushing
            existing_commits = self.find_already_pushed_commits()
            logger.info("Before pushing, found %d commits already on target", len(existing_commits))
                
            # Push in chunks with the specified step size
            if not self.push_in_chunks(step=step):
                logger.warning("Chunked push had some issues, trying with smaller chunks...")
                smaller_step = max(100, step // 2)
                logger.info("Reducing chunk size to %d commits", smaller_step)
                if not self.push_in_chunks(step=smaller_step):
                    logger.error("Failed to push even with smaller chunks")
                    return False
                    
            # Check how many commits are on the target after pushing
            after_push_commits = self.find_already_pushed_commits()
            logger.info("After pushing, found %d commits on target (added %d)", 
                        len(after_push_commits), len(after_push_commits) - len(existing_commits))
            
            logger.info(
                "Successfully mirrored large repository: %s -> %s",
                self.source_project_path,
                self.target_project_path,
            )
            return True
            
        except Exception as e:
            logger.error("Unexpected error during large repo mirroring: %s", e)
            return False
    
    def mirror_repository(self) -> bool:
        """
        Mirror repository based on the shallow flag.

        Returns:
            True if successful, False otherwise
        """
        try:
            if self.shallow:
                logger.info("Using shallow clone migration approach")
                return self.mirror_shallow()
            else:
                logger.info("Using full history migration approach")
                return self.mirror_large_repo(step=self.chunk_size)
        except Exception as e:
            logger.error("Error during repository mirroring: %s", e)
            return False

    def mirror_shallow(self) -> bool:
        """
        Mirror repository using a shallow clone (no history).
        If repository is already cloned, update it instead.

        Returns:
            True if successful, False otherwise
        """
        try:
            # If repo is not already cloned, clone it
            if not self.repo_already_cloned:
                # Clone source repository with depth=1 (only latest commit)
                source_repo_url = f"https://oauth2:{self.source_token}@{self.source_url}/{self.source_project_path}.git"
                clone_cmd = ["git", "clone", "--depth", "1", source_repo_url, "."]

                logger.info("Performing shallow clone of: %s", self.source_project_path)
                return_code, _, stderr = self.run_git_command(clone_cmd)

                if return_code != 0:
                    logger.error("Failed to shallow clone source repository: %s", stderr)
                    return False
            else:
                # If already cloned, make sure it's updated
                logger.info("Repository already cloned, updating with fetch")
                fetch_cmd = ["git", "fetch", "--depth", "1"]
                return_code, _, stderr = self.run_git_command(fetch_cmd)

                if return_code != 0:
                    logger.error("Failed to update existing repository: %s", stderr)
                    return False

                # Try to reset to the most recent state
                reset_cmd = ["git", "reset", "--hard", "origin/HEAD"]
                return_code, _, stderr = self.run_git_command(reset_cmd)

                if return_code != 0:
                    logger.warning(
                        "Failed to reset to HEAD, will try to determine default branch: %s", stderr
                    )
                    branch_cmd = ["git", "remote", "show", "origin"]
                    _, branch_output, _ = self.run_git_command(branch_cmd)

                    default_branch = None
                    for line in branch_output.split("\n"):
                        if "HEAD branch" in line:
                            default_branch = line.split(":")[-1].strip()
                            break

                    if default_branch:
                        logger.info("Resetting to default branch: %s", default_branch)
                        reset_cmd = ["git", "reset", "--hard", f"origin/{default_branch}"]
                        return_code, _, stderr = self.run_git_command(reset_cmd)

                        if return_code != 0:
                            logger.error("Failed to reset repository: %s", stderr)
                            return False
                    else:
                        logger.error("Could not determine default branch")
                        return False

            # Set up target remote
            if not self.setup_target_remote():
                return False

            # Push to target
            logger.info("Pushing shallow clone to target: %s", self.target_project_path)

            # First try to push normally
            push_cmd = ["git", "push", "target", "HEAD:master"]
            return_code, _, stderr = self.run_git_command(push_cmd)

            # If normal push fails due to protected branch, try with a different branch
            if return_code != 0 and "protected branch" in stderr:
                logger.warning(
                    "Protected branch detected, pushing to migration-temp branch instead"
                )
                push_cmd = ["git", "push", "target", "HEAD:migration-temp"]
                return_code, _, stderr = self.run_git_command(push_cmd)

            if return_code != 0:
                logger.error("Failed to push shallow clone: %s", stderr)
                return False

            logger.info("Successfully migrated repository using shallow clone")
            return True

        except Exception as e:
            logger.error("Error in shallow clone migration: %s", e)
            return False


def mirror_large_repository(
    source_url: str,
    source_project_path: str,
    source_token: str,
    target_url: str,
    target_project_path: str,
    target_token: str,
    chunk_size: int = 25,
    shallow: bool = False,  # Add this parameter
    keep_temp_dir: bool = True,  # Added parameter to control temp directory cleanup
) -> bool:
    """
    Mirror a large repository from source to target GitLab instance.

    Args:
        source_url: Source GitLab instance URL
        source_project_path: Full path of source project with namespace
        source_token: Access token for authentication to source GitLab
        target_url: Target GitLab instance URL
        target_project_path: Full path of target project with namespace
        target_token: Access token for authentication to target GitLab
        chunk_size: Number of commits per chunk (default: 25)
        shallow: Whether to do a shallow clone (no history)
        keep_temp_dir: Whether to keep the temp directory after operation (default: True)

    Returns:
        True if successful, False otherwise
    """
    try:
        logger.info(
            "Mirroring repository: %s -> %s (Shallow: %s)",
            source_project_path,
            target_project_path,
            shallow,
        )

        with LargeRepoHandler(
            source_url,
            source_project_path,
            source_token,
            target_url,
            target_project_path,
            target_token,
            chunk_size=chunk_size,
            shallow=shallow,
            keep_temp_dir=keep_temp_dir,
        ) as handler:
            return handler.mirror_repository()  # Use the new method that handles branching
    except Exception as e:
        logger.error("Failed to mirror repository: %s", e)
        return False
