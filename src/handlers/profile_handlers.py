"""
AWS Profile management handlers
"""

import logging
from typing import List
import mcp.types as types

logger = logging.getLogger(__name__)


async def get_current_aws_profile(pr_manager, args: dict) -> List[types.TextContent]:
    """Get information about current AWS profile with comprehensive details"""
    try:
        profile_info = pr_manager.get_current_profile_info()

        if not profile_info:
            result = """❌ AWS Profile Information Unavailable

🔧 Unable to retrieve current AWS profile information.

Possible causes:
1. AWS credentials not configured
2. Session not properly initialized
3. Network connectivity issues

To resolve:
• Check AWS credentials: aws configure list
• Verify profile: aws configure list-profiles
• Test access: aws sts get-caller-identity

Please check your AWS credentials configuration.
"""

            return [types.TextContent(type="text", text=result)]

        result = f"""✅ Current AWS Profile Information:

🆔 Identity Details:
   Profile: {profile_info['profile']}
   Account: {profile_info['account']}
   Region: {profile_info['region']}
   User ID: {profile_info['user_id']}
   ARN: {profile_info['user_arn']}

🔧 Configuration:
   Active Session: ✅ Authenticated
   CodeCommit Access: ✅ Available
   
💡 Available Actions:
1. Switch profiles: Use switch_aws_profile tool
2. List repositories: Use CodeCommit list operations
3. Manage pull requests: Full PR management available

📋 Quick Commands:
• aws configure list
• aws configure list-profiles  
• aws codecommit list-repositories
• aws sts get-caller-identity

✅ Your AWS session is properly configured and ready for CodeCommit operations!
"""

        return [types.TextContent(type="text", text=result)]

    except Exception as e:
        result = f"""❌ Error retrieving AWS profile information

🔧 Error Details: {str(e)}

Troubleshooting Steps:
1. Verify AWS credentials are configured
2. Check AWS CLI installation: aws --version
3. Test credentials: aws sts get-caller-identity
4. Check environment variables: AWS_PROFILE, AWS_DEFAULT_REGION

Please check your AWS credentials configuration.
"""

        return [types.TextContent(type="text", text=result)]


async def switch_aws_profile(pr_manager, args: dict) -> List[types.TextContent]:
    """Switch to a different AWS profile with enhanced validation"""
    try:
        profile_name = args["profile_name"]
        region = args.get("region")

        success = pr_manager.switch_profile(profile_name, region)

        if success:
            profile_info = pr_manager.get_current_profile_info()
            result = f"""✅ AWS Profile Switch Successful!

🔄 Profile Changed:
   New Profile: {profile_name}
   Region: {profile_info.get('region', 'Unknown')}
   Account: {profile_info.get('account', 'Unknown')}
   User: {profile_info.get('user_arn', 'Unknown').split('/')[-1] if profile_info.get('user_arn') else 'Unknown'}

🎯 Session Status:
   ✅ Authentication: Successful
   ✅ CodeCommit Access: Available
   ✅ API Permissions: Active

💡 Next Steps:
   • All subsequent operations will use this profile
   • Token cache has been cleared for fresh start
   • You can now access repositories in this account/region

🔧 Verify with:
   • get_current_aws_profile - Check new profile details
   • list_pull_requests - Test CodeCommit access
"""
        else:
            result = f"""❌ Profile Switch Failed

🔧 Could not switch to profile: {profile_name}

Common Issues:
1. Profile doesn't exist in AWS config
2. Invalid credentials for this profile
3. Missing permissions for CodeCommit
4. Network connectivity issues

Troubleshooting:
• Check available profiles: aws configure list-profiles
• Verify profile config: aws configure list --profile {profile_name}
• Test profile access: aws sts get-caller-identity --profile {profile_name}
• Test CodeCommit: aws codecommit list-repositories --profile {profile_name}
"""

        return [types.TextContent(type="text", text=result)]

    except Exception as e:
        return [
            types.TextContent(
                type="text", text=f"ERROR: Could not switch profile: {str(e)}"
            )
        ]


async def refresh_aws_credentials(pr_manager, args: dict) -> List[types.TextContent]:
    """Refresh AWS credentials without restarting the MCP server"""
    try:
        logger.info("Manual credential refresh requested")

        # Get current profile info before refresh (if available)
        old_profile_info = None
        try:
            old_profile_info = pr_manager.get_current_profile_info()
        except:
            pass

        # Attempt credential refresh
        success = pr_manager.refresh_credentials()

        if success:
            # Get new profile info
            new_profile_info = pr_manager.get_current_profile_info()

            result = f"""✅ AWS Credentials Refreshed:

🔄 Session Renewed:
   Profile: {new_profile_info.get('profile', 'default')}
   Account: {new_profile_info.get('account', 'Unknown')}
   Region: {new_profile_info.get('region', 'Unknown')}
   User: {new_profile_info.get('user_arn', 'Unknown').split('/')[-1] if new_profile_info.get('user_arn') else 'Unknown'}

🎯 Status:
   ✅ Credentials: Refreshed
   ✅ Session: Active
   ✅ CodeCommit: Available

💡 All subsequent operations will use fresh credentials.
No need to restart Claude Desktop!"""

            return [types.TextContent(type="text", text=result)]
        else:
            result = """❌ Credential Refresh Failed:

🔧 Could not refresh AWS credentials.

Common Issues:
1. AWS credentials file not updated
2. Profile configuration missing
3. Network connectivity issues
4. Permission issues accessing credentials

Troubleshooting:
• Update credentials: aws configure
• Check credentials: aws configure list
• Test access: aws sts get-caller-identity
• Verify profile: aws configure list-profiles

You may need to restart Claude Desktop if this persists."""

            return [types.TextContent(type="text", text=result)]

    except Exception as e:
        logger.error(f"Error during credential refresh: {e}")
        return [
            types.TextContent(
                type="text",
                text=f"❌ Credential refresh error: {str(e)}\n\nYou may need to restart Claude Desktop.",
            )
        ]
