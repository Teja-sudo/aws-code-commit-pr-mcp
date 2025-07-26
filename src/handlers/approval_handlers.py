"""
Pull Request approval management handlers
"""

import asyncio
import logging
from typing import List
from botocore.exceptions import ClientError
import mcp.types as types

logger = logging.getLogger(__name__)


async def get_pr_approvals(pr_manager, args: dict) -> List[types.TextContent]:
    """Get comprehensive approval information including states and override status"""
    try:
        pull_request_id = args["pull_request_id"]
        include_override = args.get("include_override", True)
        
        kwargs = {"pullRequestId": pull_request_id}
        if "revision_id" in args:
            kwargs["revisionId"] = args["revision_id"]

        response = pr_manager.retry_with_backoff(
            pr_manager.codecommit_client.get_pull_request_approval_states, **kwargs
        )

        approvals = response.get("approvals", [])

        result = f"""🎯 PR Approval Information - {pull_request_id}:

📊 Approval Summary:
   Total Reviewers: {len(approvals)}
   Approvals Received: {len([a for a in approvals if a.get('approvalState') == 'APPROVE'])}
   Revoked Approvals: {len([a for a in approvals if a.get('approvalState') == 'REVOKE'])}
   Pending Reviews: {len([a for a in approvals if a.get('approvalState') not in ['APPROVE', 'REVOKE']])}

"""

        if not approvals:
            result += """ℹ️  No approval states found.

This could mean:
• No reviewers have been assigned
• No approval rules are configured
• PR doesn't require approvals
• You might not have permission to view approval states

💡 Next Steps:
• Check if approval rules exist for this repository
• Verify reviewer assignments
• Review repository approval configuration"""
        else:
            result += "👥 Reviewer Details:\n"
            for i, approval in enumerate(approvals, 1):
                state = approval.get("approvalState", "PENDING")
                user_arn = approval.get("userArn", "Unknown")
                user_name = (
                    user_arn.split("/")[-1] if user_arn != "Unknown" else "Unknown"
                )

                state_icon = {"APPROVE": "✅", "REVOKE": "❌", "PENDING": "⏳"}.get(
                    state, "❓"
                )

                result += f"""
   {i:2d}. {state_icon} {user_name}
       State: {state}
       ARN: {user_arn}"""

        # Add override status if requested
        if include_override:
            try:
                override_kwargs = {"pullRequestId": pull_request_id}
                if "revision_id" in args:
                    override_kwargs["revisionId"] = args["revision_id"]

                override_response = pr_manager.retry_with_backoff(
                    pr_manager.codecommit_client.get_pull_request_override_state, **override_kwargs
                )

                is_overridden = override_response.get("overridden", False)
                overrider_arn = override_response.get("overrider")

                result += f"\n🔓 Override Status:\n"
                
                if is_overridden:
                    overrider_name = overrider_arn.split("/")[-1] if overrider_arn else "Unknown"
                    result += f"""   Status: OVERRIDDEN ⚠️
   Overridden By: {overrider_name}
   Impact: All approval requirements bypassed"""
                else:
                    result += f"""   Status: NOT OVERRIDDEN ✅
   Normal approval rules apply"""
                    
            except Exception as e:
                result += f"\n⚠️  Could not retrieve override status: {str(e)}"

        result += f"""

💡 Available Actions:
• manage_pr_approval(action="approve/revoke/override/revoke_override") - Manage approvals
"""

        return [types.TextContent(type="text", text=result)]

    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        error_msg = e.response["Error"]["Message"]

        if error_code == "PullRequestDoesNotExistException":
            return [
                types.TextContent(
                    type="text",
                    text=f"❌ Pull Request {args['pull_request_id']} not found.\n"
                    f"🔧 Please verify the PR ID and your access permissions.",
                )
            ]

        return [
            types.TextContent(
                type="text", text=f"❌ AWS Error ({error_code}): {error_msg}"
            )
        ]


async def manage_pr_approval(pr_manager, args: dict) -> List[types.TextContent]:
    """Unified approval management with automatic race condition handling"""
    
    pull_request_id = args["pull_request_id"]
    action = args["action"].lower()
    MAX_RETRIES = 3
    
    for retry_count in range(MAX_RETRIES):
        try:
            # Get fresh revision ID on retries to handle race conditions
            if retry_count > 0:
                logger.info(f"Retry {retry_count} for PR {pull_request_id} approval action: {action}")
                
                # Get latest revision ID
                pr_response = pr_manager.retry_with_backoff(
                    pr_manager.codecommit_client.get_pull_request,
                    pullRequestId=pull_request_id,
                )
                
                latest_revision = pr_response["pullRequest"]["revisionId"]
                
                if latest_revision != args["revision_id"]:
                    logger.info(f"PR {pull_request_id} updated: {args['revision_id']} -> {latest_revision}")
                    revision_id = latest_revision
                else:
                    revision_id = args["revision_id"]
            else:
                revision_id = args["revision_id"]
            
            if action in ["approve", "revoke"]:
                # Handle standard approval actions
                approval_state = "APPROVE" if action == "approve" else "REVOKE"
                
                response = pr_manager.retry_with_backoff(
                    pr_manager.codecommit_client.update_pull_request_approval_state,
                    pullRequestId=pull_request_id,
                    revisionId=revision_id,
                    approvalState=approval_state,
                )

                approval_icon = "✅" if action == "approve" else "❌"
                action_past = "approved" if action == "approve" else "revoked approval for"

                result = f"""✅ Approval Action Completed:

🆔 PR ID: {pull_request_id}
{approval_icon} Action: {approval_state}
🔄 Revision: {revision_id}

🎯 You have {action_past} this pull request!

💡 Next Steps:
• Use get_pr_approvals to check overall approval status
• Review any remaining approval requirements"""

            elif action in ["override", "revoke_override"]:
                # Handle override actions
                override_status = "OVERRIDE" if action == "override" else "REVOKE"
                
                response = pr_manager.retry_with_backoff(
                    pr_manager.codecommit_client.override_pull_request_approval_rules,
                    pullRequestId=pull_request_id,
                    revisionId=revision_id,
                    overrideStatus=override_status,
                )

                override_icon = "🔓" if action == "override" else "🔒"
                action_past = "overridden" if action == "override" else "revoked override for"

                result = f"""✅ Override Action Completed:

🆔 PR ID: {pull_request_id}
{override_icon} Action: {override_status}
🔄 Revision: {revision_id}

🎯 Approval rules have been {action_past}!

💡 Impact:"""

                if action == "override":
                    result += """
• All approval rule requirements are now bypassed
• PR can be merged without meeting normal approval criteria
• This action is logged and auditable"""
                else:
                    result += """
• Normal approval rules are now restored
• PR must meet all configured approval requirements
• Previous override has been revoked"""

            else:
                return [types.TextContent(
                    type="text",
                    text=f"❌ Invalid action: {action}\n"
                    f"🔧 Valid actions: approve, revoke, override, revoke_override"
                )]

            result += f"""

💡 Recommended Next Steps:
• Use get_pr_approvals to verify the changes
• Check if any additional approvals are needed
• Consider the security implications of overrides"""

            return [types.TextContent(type="text", text=result)]

        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            error_msg = e.response["Error"]["Message"]

            # Handle race conditions with automatic retry
            if error_code in ["InvalidRevisionIdException", "RevisionNotCurrentException"]:
                if retry_count < MAX_RETRIES - 1:
                    logger.warning(f"Race condition detected for PR {pull_request_id} (attempt {retry_count + 1}): {error_code}")
                    await asyncio.sleep(0.5 * (retry_count + 1))  # Exponential backoff
                    continue  # Retry with fresh revision ID
                else:
                    # Final attempt failed - fall through to error handling
                    troubleshooting = f"""

🔧 Race Condition - Failed after {MAX_RETRIES} attempts:
• PR was updated {retry_count + 1} times during approval attempt
• Someone else is actively modifying this PR
• Try again in a few moments when the PR is stable
• Use get_pr_info to get the latest revision ID"""
                    
                    return [
                        types.TextContent(
                            type="text",
                            text=f"❌ AWS Error ({error_code}): {error_msg}{troubleshooting}",
                        )
                    ]
            
            # Regular error handling for non-race-condition errors
            troubleshooting = ""
            if error_code == "InsufficientPermissionsException":
                troubleshooting = """

🔧 Troubleshooting - Insufficient Permissions:
• You need appropriate permissions for this action
• Override actions require admin permissions
• Check your repository access level"""

            return [
                types.TextContent(
                    type="text",
                    text=f"❌ AWS Error ({error_code}): {error_msg}{troubleshooting}",
                )
            ]

        except Exception as e:
            return [
                types.TextContent(
                    type="text", 
                    text=f"❌ Error managing approval: {str(e)}"
                )
            ]
    
    # This should never be reached due to the return statements above
    return [
        types.TextContent(
            type="text",
            text=f"❌ Unexpected error: Max retries exceeded without proper error handling"
        )
    ]


async def update_pull_request_approval_state(
    pr_manager, args: dict
) -> List[types.TextContent]:
    """Update approval state for a pull request"""
    try:
        response = pr_manager.retry_with_backoff(
            pr_manager.codecommit_client.update_pull_request_approval_state,
            pullRequestId=args["pull_request_id"],
            revisionId=args["revision_id"],
            approvalState=args["approval_state"],
        )

        approval_icon = "✅" if args["approval_state"] == "APPROVE" else "❌"
        action = (
            "approved"
            if args["approval_state"] == "APPROVE"
            else "revoked approval for"
        )

        result = f"""✅ Approval State Updated:

🆔 PR ID: {args['pull_request_id']}
{approval_icon} Action: {args['approval_state']}
🔄 Revision: {args['revision_id']}

🎯 You have {action} this pull request!

💡 Next Steps:
• Check overall approval status with get_pull_request_approval_states
• Review any remaining approval requirements
• Monitor for additional reviews or changes"""

        return [types.TextContent(type="text", text=result)]

    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        error_msg = e.response["Error"]["Message"]

        troubleshooting = ""
        if error_code == "InvalidRevisionIdException":
            troubleshooting = """
🔧 Troubleshooting - Invalid Revision:
• The revision ID might be outdated
• PR may have been updated since you last checked
• Get the latest revision with get_pull_request
"""
        elif error_code == "RevisionNotCurrentException":
            troubleshooting = """
🔧 Troubleshooting - Revision Not Current:
• PR has been updated since this revision
• Get the latest revision ID and try again
• Use get_pull_request to get current revision
"""

        return [
            types.TextContent(
                type="text",
                text=f"❌ AWS Error ({error_code}): {error_msg}{troubleshooting}",
            )
        ]


async def override_pull_request_approval_rules(
    pr_manager, args: dict
) -> List[types.TextContent]:
    """Override approval rules for a pull request"""
    try:
        response = pr_manager.retry_with_backoff(
            pr_manager.codecommit_client.override_pull_request_approval_rules,
            pullRequestId=args["pull_request_id"],
            revisionId=args["revision_id"],
            overrideStatus=args["override_status"],
        )

        override_icon = "🔓" if args["override_status"] == "OVERRIDE" else "🔒"
        action = (
            "overridden"
            if args["override_status"] == "OVERRIDE"
            else "revoked override for"
        )

        result = f"""✅ Approval Rules Override Updated:

🆔 PR ID: {args['pull_request_id']}
{override_icon} Action: {args['override_status']}
🔄 Revision: {args['revision_id']}

🎯 Approval rules have been {action}!

💡 Impact:
"""

        if args["override_status"] == "OVERRIDE":
            result += """• All approval rule requirements are now bypassed
• PR can be merged without meeting normal approval criteria
• This action is logged and auditable"""
        else:
            result += """• Normal approval rules are now restored
• PR must meet all configured approval requirements
• Previous override has been revoked"""

        result += """

💡 Next Steps:
• Check override status with get_pull_request_override_state
• Review approval requirements if override was revoked
• Consider the security implications of overrides"""

        return [types.TextContent(type="text", text=result)]

    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        error_msg = e.response["Error"]["Message"]

        if error_code == "InsufficientPermissionsException":
            return [
                types.TextContent(
                    type="text",
                    text=f"❌ Insufficient Permissions: {error_msg}\n"
                    f"🔧 You need admin permissions to override approval rules.",
                )
            ]

        return [
            types.TextContent(
                type="text", text=f"❌ AWS Error ({error_code}): {error_msg}"
            )
        ]


async def get_pull_request_override_state(
    pr_manager, args: dict
) -> List[types.TextContent]:
    """Get override state for pull request approval rules"""
    try:
        kwargs = {"pullRequestId": args["pull_request_id"]}
        if "revision_id" in args:
            kwargs["revisionId"] = args["revision_id"]

        response = pr_manager.retry_with_backoff(
            pr_manager.codecommit_client.get_pull_request_override_state, **kwargs
        )

        is_overridden = response.get("overridden", False)
        overrider_arn = response.get("overrider")

        result = f"""🔍 Override State for Pull Request {args['pull_request_id']}:

"""

        if is_overridden:
            overrider_name = (
                overrider_arn.split("/")[-1] if overrider_arn else "Unknown"
            )
            result += f"""🔓 Status: OVERRIDDEN

👤 Override Details:
   Overridden By: {overrider_name}
   Overrider ARN: {overrider_arn}

⚠️  Impact:
• All approval rule requirements are bypassed
• PR can be merged without normal approvals
• This override is logged and auditable

💡 Actions Available:
• Revoke override with override_pull_request_approval_rules
• Proceed with merge if appropriate
• Review security implications"""
        else:
            result += f"""🔒 Status: NOT OVERRIDDEN

✅ Normal approval rules are in effect:
• All configured approval requirements must be met
• Standard review process applies
• No bypass of approval rules

💡 Actions Available:
• Check approval states with get_pull_request_approval_states
• Override rules if you have admin permissions
• Follow normal approval workflow"""

        return [types.TextContent(type="text", text=result)]

    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        error_msg = e.response["Error"]["Message"]

        return [
            types.TextContent(
                type="text", text=f"❌ AWS Error ({error_code}): {error_msg}"
            )
        ]
