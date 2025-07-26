"""
AWS Client Management for CodeCommit PR operations
"""

import os
import time
import logging
import boto3
from botocore.exceptions import ClientError, NoCredentialsError

from .utils.constants import MAX_RETRIES, RETRY_DELAY

logger = logging.getLogger(__name__)


class CodeCommitPRManager:
    """Enhanced main class for AWS CodeCommit pull request operations with profile support"""

    def __init__(self):
        self.session = None
        self.codecommit_client = None
        self.current_profile = None
        self.current_region = None
        self.processed_tokens = set()  # Track processed pagination tokens
        self._initialized = False

    def ensure_initialized(self):
        """Ensure AWS session is initialized (lazy initialization)"""
        if not self._initialized:
            self.initialize_aws_session()
            self._initialized = True

    def initialize_aws_session(self):
        """Initialize AWS session with proper credential handling and profile support"""
        try:
            # Check for profile in environment variables
            profile_name = os.getenv("AWS_PROFILE")
            region_name = os.getenv("AWS_DEFAULT_REGION", "us-east-1")

            # Initialize session with profile if specified
            if profile_name:
                self.session = boto3.Session(
                    profile_name=profile_name, region_name=region_name
                )
                logger.info(f"Using AWS profile: {profile_name}")
            else:
                self.session = boto3.Session(region_name=region_name)

            self.current_profile = profile_name
            self.current_region = region_name
            self.codecommit_client = self.session.client("codecommit")

            # Test credentials with retry logic
            self._test_credentials_with_retry()

        except NoCredentialsError:
            logger.warning("AWS credentials not found. Tools will not work.")
        except Exception as e:
            logger.error(f"Error initializing AWS session: {e}")

    def _test_credentials_with_retry(self):
        """Test AWS credentials with retry logic"""
        for attempt in range(MAX_RETRIES):
            try:
                sts_client = self.session.client("sts")
                identity = sts_client.get_caller_identity()
                logger.info(
                    f"AWS Session initialized for account: {identity.get('Account')} "
                    f"in region: {self.current_region}"
                )
                return
            except Exception as e:
                if attempt < MAX_RETRIES - 1:
                    logger.warning(
                        f"Credential test attempt {attempt + 1} failed: {e}. Retrying..."
                    )
                    time.sleep(RETRY_DELAY * (2**attempt))
                else:
                    logger.error(f"All credential test attempts failed: {e}")
                    raise

    def switch_profile(self, profile_name: str, region: str = None):
        """Switch to a different AWS profile with validation"""
        try:
            if region is None:
                region = self.current_region or "us-east-1"

            # Create new session
            new_session = boto3.Session(profile_name=profile_name, region_name=region)
            new_client = new_session.client("codecommit")

            # Test new credentials
            sts_client = new_session.client("sts")
            identity = sts_client.get_caller_identity()

            # If successful, update current session
            self.session = new_session
            self.codecommit_client = new_client
            self.current_profile = profile_name
            self.current_region = region
            self.processed_tokens.clear()  # Clear token cache

            logger.info(
                f"Switched to profile: {profile_name}, account: {identity.get('Account')}, "
                f"region: {region}"
            )
            return True

        except Exception as e:
            logger.error(f"Error switching to profile {profile_name}: {e}")
            return False

    def get_client(self, region: str = None):
        """Get CodeCommit client for specific region"""
        self.ensure_initialized()
        if region and region != self.current_region:
            if self.current_profile:
                return self.session.client("codecommit", region_name=region)
            else:
                temp_session = boto3.Session(region_name=region)
                return temp_session.client("codecommit")
        return self.codecommit_client

    def get_current_profile_info(self):
        """Get information about current AWS profile and session"""
        self.ensure_initialized()
        try:
            sts_client = self.session.client("sts")
            identity = sts_client.get_caller_identity()
            return {
                "profile": self.current_profile or "default",
                "region": self.current_region,
                "account": identity.get("Account"),
                "user_arn": identity.get("Arn"),
                "user_id": identity.get("UserId"),
            }
        except Exception as e:
            logger.error(f"Error getting profile info: {e}")
            return None

    def refresh_credentials(self):
        """Force refresh of AWS credentials and session"""
        try:
            logger.info("Refreshing AWS credentials...")
            # Clear current session
            self.session = None
            self.codecommit_client = None
            self._initialized = False

            # Re-initialize with fresh credentials
            self.ensure_initialized()
            return True
        except Exception as e:
            logger.error(f"Error refreshing credentials: {e}")
            return False

    def retry_with_backoff(self, func, *args, **kwargs):
        """Execute function with exponential backoff retry and credential refresh"""
        self.ensure_initialized()
        for attempt in range(MAX_RETRIES):
            try:
                return func(*args, **kwargs)
            except ClientError as e:
                error_code = e.response["Error"]["Code"]

                # Handle credential-related errors by refreshing
                if error_code in [
                    "ExpiredToken",
                    "InvalidToken",
                    "TokenRefreshRequired",
                    "UnauthorizedOperation",
                    "AccessDenied",
                ]:
                    if attempt == 0:  # Only try refresh once per retry sequence
                        logger.warning(
                            f"Credential error detected ({error_code}), attempting refresh..."
                        )
                        if self.refresh_credentials():
                            logger.info(
                                "Credentials refreshed successfully, retrying..."
                            )
                            continue
                        else:
                            logger.error("Failed to refresh credentials")
                            raise

                if (
                    error_code
                    in ["Throttling", "ThrottlingException", "RequestTimeout"]
                    and attempt < MAX_RETRIES - 1
                ):
                    delay = RETRY_DELAY * (2**attempt)
                    logger.warning(
                        f"AWS API throttled, retrying in {delay}s (attempt {attempt + 1})"
                    )
                    time.sleep(delay)
                else:
                    raise
            except Exception as e:
                # Check if it's a credential-related exception
                error_str = str(e).lower()
                if any(
                    keyword in error_str
                    for keyword in ["credential", "token", "expired", "unauthorized"]
                ):
                    if attempt == 0:  # Only try refresh once per retry sequence
                        logger.warning(f"Potential credential error detected: {e}")
                        if self.refresh_credentials():
                            logger.info(
                                "Credentials refreshed successfully, retrying..."
                            )
                            continue
                        else:
                            logger.error("Failed to refresh credentials")
                            raise

                if attempt < MAX_RETRIES - 1:
                    delay = RETRY_DELAY * (2**attempt)
                    logger.warning(
                        f"Request failed, retrying in {delay}s (attempt {attempt + 1}): {e}"
                    )
                    time.sleep(delay)
                else:
                    raise
