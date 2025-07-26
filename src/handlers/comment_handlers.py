"""
Pull Request comment management handlers
"""

import logging
from typing import List
from botocore.exceptions import ClientError
import mcp.types as types

logger = logging.getLogger(__name__)


async def post_comment_for_pull_request(
    pr_manager, args: dict
) -> List[types.TextContent]:
    """Post a comment on a pull request with enhanced validation"""
    try:
        kwargs = {
            "pullRequestId": args["pull_request_id"],
            "repositoryName": args["repository_name"],
            "beforeCommitId": args["before_commit_id"],
            "afterCommitId": args["after_commit_id"],
            "content": args["content"],
        }

        if "location" in args:
            kwargs["location"] = args["location"]
        if "client_request_token" in args:
            kwargs["clientRequestToken"] = args["client_request_token"]

        response = pr_manager.retry_with_backoff(
            pr_manager.codecommit_client.post_comment_for_pull_request, **kwargs
        )

        comment = response.get("comment", {})
        is_inline = "location" in args

        result = f"""✅ Comment Posted:

💬 Details:
   Comment ID: {comment.get('commentId', 'Unknown')}
   PR ID: {args['pull_request_id']}
   Type: {'Inline' if is_inline else 'General'}
   
📝 Content:
{args['content']}

"""

        if is_inline:
            location = args["location"]
            result += f"""📍 Location:
   File: {location.get('filePath', 'Unknown')}
   Position: {location.get('filePosition', 'Unknown')}
   Version: {location.get('relativeFileVersion', 'Unknown')}

"""

        result += f"""⏰ Posted: {comment.get('creationDate', 'Unknown')}
👤 Author: {comment.get('authorArn', 'Unknown').split('/')[-1] if comment.get('authorArn') else 'Unknown'}"""

        return [types.TextContent(type="text", text=result)]

    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        error_msg = e.response["Error"]["Message"]

        troubleshooting = ""
        if error_code == "InvalidLocationException":
            troubleshooting = """
🔧 Troubleshooting - Invalid Location:
• Check that the file path exists in the PR
• Verify the file position is within file bounds
• Ensure the relative_file_version is correct (BEFORE/AFTER)
"""
        elif error_code == "CommentContentRequiredException":
            troubleshooting = """
🔧 Troubleshooting - Content Required:
• Comment content cannot be empty
• Provide meaningful comment text
"""

        return [
            types.TextContent(
                type="text",
                text=f"❌ AWS Error ({error_code}): {error_msg}{troubleshooting}",
            )
        ]


async def get_comments_for_pull_request(
    pr_manager, args: dict
) -> List[types.TextContent]:
    """Get all comments for a pull request with enhanced pagination support"""
    try:
        kwargs = {
            "pullRequestId": args["pull_request_id"],
            "maxResults": args.get("max_results", 100),
        }

        # Optional filters
        if "repository_name" in args:
            kwargs["repositoryName"] = args["repository_name"]
        if "before_commit_id" in args:
            kwargs["beforeCommitId"] = args["before_commit_id"]
        if "after_commit_id" in args:
            kwargs["afterCommitId"] = args["after_commit_id"]
        if (
            "next_token" in args
            and args["next_token"] not in pr_manager.processed_tokens
        ):
            kwargs["nextToken"] = args["next_token"]
            pr_manager.processed_tokens.add(args["next_token"])

        response = pr_manager.retry_with_backoff(
            pr_manager.codecommit_client.get_comments_for_pull_request, **kwargs
        )

        comments = response.get("commentsForPullRequestData", [])
        next_token = response.get("nextToken")

        result = f"""💬 PR {args['pull_request_id']} Comments:

📊 Summary:
   Total: {len(comments)}
   Pagination: {'More available' if next_token else 'Complete'}

"""

        if not comments:
            result += """ℹ️  No comments found.

Possible reasons:
• No comments posted yet
• Filtered by criteria
• Access permissions

💡 Try removing filters or check PR activity."""
        else:
            result += "📝 Comment Details:\n"

            general_comments = []
            inline_comments = []

            # Categorize comments
            for comment_data in comments:
                if comment_data.get("location"):
                    inline_comments.append(comment_data)
                else:
                    general_comments.append(comment_data)

            # Show general comments first
            if general_comments:
                result += f"\n💬 General Comments ({len(general_comments)}):\n"
                for i, comment_data in enumerate(general_comments, 1):
                    comment = comment_data.get("comment", {})
                    author = (
                        comment.get("authorArn", "Unknown").split("/")[-1]
                        if comment.get("authorArn")
                        else "Unknown"
                    )
                    content = comment.get("content", "No content")
                    created = comment.get("creationDate", "Unknown")

                    result += f"""
   {i:2d}. 👤 {author} ({created})
       💬 {content[:100]}{"..." if len(content) > 100 else ""}
"""

            # Show inline comments
            if inline_comments:
                result += f"\n📍 Inline Comments ({len(inline_comments)}):\n"
                for i, comment_data in enumerate(inline_comments, 1):
                    comment = comment_data.get("comment", {})
                    location = comment_data.get("location", {})
                    author = (
                        comment.get("authorArn", "Unknown").split("/")[-1]
                        if comment.get("authorArn")
                        else "Unknown"
                    )
                    content = comment.get("content", "No content")
                    created = comment.get("creationDate", "Unknown")
                    file_path = location.get("filePath", "Unknown")

                    result += f"""
   {i:2d}. 👤 {author} ({created})
       📁 File: {file_path}
       💬 {content[:100]}{"..." if len(content) > 100 else ""}
"""

        if next_token:
            result += f"\n\n📄 More available. Use next_token: {next_token}"

        return [types.TextContent(type="text", text=result)]

    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        error_msg = e.response["Error"]["Message"]

        return [
            types.TextContent(
                type="text", text=f"❌ AWS Error ({error_code}): {error_msg}"
            )
        ]


async def describe_pull_request_events(
    pr_manager, args: dict
) -> List[types.TextContent]:
    """Get events for a pull request with enhanced pagination support"""
    try:
        kwargs = {
            "pullRequestId": args["pull_request_id"],
            "maxResults": args.get("max_results", 100),
        }

        # Optional filters
        if "pull_request_event_type" in args:
            kwargs["pullRequestEventType"] = args["pull_request_event_type"]
        if "actor_arn" in args:
            kwargs["actorArn"] = args["actor_arn"]
        if (
            "next_token" in args
            and args["next_token"] not in pr_manager.processed_tokens
        ):
            kwargs["nextToken"] = args["next_token"]
            pr_manager.processed_tokens.add(args["next_token"])

        response = pr_manager.retry_with_backoff(
            pr_manager.codecommit_client.describe_pull_request_events, **kwargs
        )

        events = response.get("pullRequestEvents", [])
        next_token = response.get("nextToken")

        result = f"""📅 PR {args['pull_request_id']} Events:

📊 Summary:
   Total: {len(events)}
   Filters: {'Yes' if any(k in args for k in ['pull_request_event_type', 'actor_arn']) else 'No'}
   Pagination: {'More available' if next_token else 'Complete'}

"""

        if not events:
            result += """ℹ️  No events found.

Possible reasons:
• New PR with minimal activity
• Filtered by criteria
• Access permissions

💡 Try removing filters or check basic PR info."""
        else:
            result += "📋 Event Timeline (most recent first):\n"

            # Group events by type for better organization
            event_types = {}
            for event in events:
                event_type = event.get("pullRequestEventType", "UNKNOWN")
                if event_type not in event_types:
                    event_types[event_type] = []
                event_types[event_type].append(event)

            result += f"\n📈 Event Types Found: {', '.join(event_types.keys())}\n"

            # Show events chronologically
            for i, event in enumerate(events, 1):
                event_type = event.get("pullRequestEventType", "UNKNOWN")
                event_date = event.get("eventDate", "Unknown")
                actor_arn = event.get("actorArn", "Unknown")
                actor_name = (
                    actor_arn.split("/")[-1] if actor_arn != "Unknown" else "Unknown"
                )

                # Event type specific icons
                event_icons = {
                    "PULL_REQUEST_CREATED": "🆕",
                    "PULL_REQUEST_SOURCE_REFERENCE_UPDATED": "🔄",
                    "PULL_REQUEST_STATUS_CHANGED": "📊",
                    "PULL_REQUEST_MERGE_STATUS_CHANGED": "🔀",
                    "APPROVAL_RULE_CREATED": "📋",
                    "APPROVAL_RULE_UPDATED": "✏️",
                    "APPROVAL_RULE_DELETED": "🗑️",
                    "APPROVAL_RULE_OVERRIDDEN": "🔓",
                    "APPROVAL_STATE_CHANGED": "✅",
                }

                icon = event_icons.get(event_type, "📌")

                result += f"""
   {i:2d}. {icon} {event_type}
       👤 Actor: {actor_name}
       ⏰ Date: {event_date}"""

                # Add specific event details
                if event_type == "PULL_REQUEST_STATUS_CHANGED":
                    status_metadata = event.get(
                        "pullRequestStatusChangedEventMetadata", {}
                    )
                    if status_metadata:
                        result += f"\n       📊 Status: {status_metadata.get('pullRequestStatus', 'Unknown')}"

                elif event_type == "APPROVAL_STATE_CHANGED":
                    approval_metadata = event.get(
                        "approvalStateChangedEventMetadata", {}
                    )
                    if approval_metadata:
                        result += f"\n       ✅ State: {approval_metadata.get('approvalStatus', 'Unknown')}"

        if next_token:
            result += f"\n\n📄 More available. Use next_token: {next_token}"

        result += f"""

💡 Event Types:
• Created: PR initiation
• Status: PR lifecycle
• Approval: Review progress
• Merge: Completion status"""

        return [types.TextContent(type="text", text=result)]

    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        error_msg = e.response["Error"]["Message"]

        return [
            types.TextContent(
                type="text", text=f"❌ AWS Error ({error_code}): {error_msg}"
            )
        ]
