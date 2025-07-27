"""
Pull Request management handlers
"""

import logging
import re
from typing import List
from botocore.exceptions import ClientError
import mcp.types as types
from ..utils.helpers import (
    get_changes_with_enhanced_pagination,
    get_comprehensive_file_discovery,
    stream_analyze_huge_pr,
    detect_encoding,
    is_binary_file,
)
from ..utils.constants import MAX_FILE_SIZE_FOR_DIFF

logger = logging.getLogger(__name__)


async def create_pull_request(pr_manager, args: dict) -> List[types.TextContent]:
    """Create a new pull request with enhanced error handling"""
    try:
        kwargs = {
            "title": args["title"],
            "targets": [
                {
                    "repositoryName": args["repository_name"],
                    "sourceReference": args["source_commit"],
                    "destinationReference": args["destination_commit"],
                }
            ],
        }

        if "description" in args:
            kwargs["description"] = args["description"]
        if "client_request_token" in args:
            kwargs["clientRequestToken"] = args["client_request_token"]

        response = pr_manager.retry_with_backoff(
            pr_manager.codecommit_client.create_pull_request, **kwargs
        )

        pr_info = response["pullRequest"]
        target = pr_info["pullRequestTargets"][0]

        result = f"""✅ Pull Request Created:

🆔 Information:
   PR ID: {pr_info['pullRequestId']}
   Title: {pr_info['title']}
   Repository: {target['repositoryName']}
   Status: {pr_info['pullRequestStatus']}

🔀 Branches:
   Source: {target['sourceReference']} → {target['destinationReference']}
   Source Commit: {target['sourceCommit']}
   Destination Commit: {target['destinationCommit']}

📅 Created: {pr_info['creationDate'].strftime('%Y-%m-%d %H:%M:%S UTC')}
👤 Author: {pr_info.get('authorArn', 'Unknown').split('/')[-1] if pr_info.get('authorArn') else 'Unknown'}
"""

        return [types.TextContent(type="text", text=result)]

    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        error_msg = e.response["Error"]["Message"]

        troubleshooting = ""
        if error_code == "ReferenceDoesNotExistException":
            troubleshooting = """
🔧 Troubleshooting - Reference Not Found:
• Verify source and destination branch/commit exist
• Check branch names are correct (case-sensitive)
• Ensure you have access to both references
• Try: aws codecommit get-branch --repository-name REPO --branch-name BRANCH
"""

        return [
            types.TextContent(
                type="text",
                text=f"❌ AWS Error ({error_code}): {error_msg}{troubleshooting}",
            )
        ]


async def get_pr_info(pr_manager, args: dict) -> List[types.TextContent]:
    """Get comprehensive PR information including optional metadata analysis"""
    try:
        pull_request_id = str(args["pull_request_id"]).strip()
        include_metadata = args.get("include_metadata", False)

        if not pull_request_id:
            return [
                types.TextContent(
                    type="text", text="❌ Error: pull_request_id cannot be empty"
                )
            ]

        response = pr_manager.retry_with_backoff(
            pr_manager.codecommit_client.get_pull_request,
            pullRequestId=pull_request_id,
        )

        pr = response["pullRequest"]
        target = pr["pullRequestTargets"][0]
        repository_name = target["repositoryName"]
        source_commit = target["sourceCommit"]
        destination_commit = target["destinationCommit"]

        # Extract additional target details
        merge_base = target.get("mergeBase", "Not available")
        merge_metadata = target.get("mergeMetadata", {})
        merge_option = merge_metadata.get("mergeOption", "Not specified")
        merge_commit_id = merge_metadata.get("mergeCommitId", "Not available")
        merged_by = merge_metadata.get("mergedBy", "Not merged")

        # Format author information
        author_arn = pr.get("authorArn", "Unknown")
        author_name = (
            author_arn.split("/")[-1] if author_arn != "Unknown" else "Unknown"
        )

        # Client request token
        client_token = pr.get("clientRequestToken", "Not specified")

        result = f"""📋 Pull Request Complete Details:

🆔 Basic Information:
   PR ID: {pr['pullRequestId']}
   Title: {pr['title']}
   Status: {pr['pullRequestStatus']}
   Repository: {repository_name}
   Client Token: {client_token}
   
📝 Description:
{pr.get('description', 'No description provided')}

👤 Author Information:
   Author: {author_name}
   Author ARN: {author_arn}
   Created: {pr['creationDate'].strftime('%Y-%m-%d %H:%M:%S UTC')}
   Last Updated: {pr['lastActivityDate'].strftime('%Y-%m-%d %H:%M:%S UTC')}

🔀 Branch & Merge Details:
   Source Branch: {target['sourceReference']}
   Destination Branch: {target['destinationReference']}
   Source Commit: {source_commit}
   Destination Commit: {destination_commit}
   Merge Base: {merge_base}
   Merge Option: {merge_option}
   Merge Commit ID: {merge_commit_id}
   Merged By: {merged_by}

💬 Commit IDs for Comments:
   Before Commit: {destination_commit}
   After Commit: {source_commit}

🔄 Revision ID for Approvals:
   Revision ID: {pr['revisionId']}"""

        # Add approval rules information if available
        approval_rules = pr.get("approvalRules", [])
        if approval_rules:
            result += f"\n\n📋 Approval Rules ({len(approval_rules)} rules):\n"
            for i, rule in enumerate(approval_rules, 1):
                rule_name = rule.get("approvalRuleName", f"Rule {i}")
                rule_id = rule.get("approvalRuleId", "No ID")
                rule_content = rule.get("approvalRuleContent", "No content available")

                result += f"\n   {i}. {rule_name}\n"
                result += f"      Rule ID: {rule_id}\n"
                result += f"      Content: {rule_content[:200]}{'...' if len(rule_content) > 200 else ''}\n"
        else:
            result += f"\n\n📋 Approval Rules: None configured"

        # Add multiple targets support (if PR has multiple targets)
        all_targets = pr.get("pullRequestTargets", [])
        if len(all_targets) > 1:
            result += f"\n\n🎯 Multiple Targets ({len(all_targets)} total):\n"
            for i, t in enumerate(all_targets, 1):
                result += f"\n   Target {i}:\n"
                result += f"      Repository: {t.get('repositoryName', 'Unknown')}\n"
                result += f"      Source: {t.get('sourceReference', 'Unknown')} → {t.get('destinationReference', 'Unknown')}\n"
                result += f"      Commits: {t.get('sourceCommit', 'Unknown')[:12]}... {t.get('destinationCommit', 'Unknown')[:12]}...\n"

        # Add metadata analysis if requested
        if include_metadata:
            result += f"\n\n📊 PR Metadata Analysis:\n"

            try:
                # Count total files WITHOUT loading content
                total_files = 0
                total_pages = 0
                file_summary = {"A": 0, "M": 0, "D": 0}
                next_token = None

                # Quick scan to get metadata only
                while True:
                    kwargs = {
                        "repositoryName": repository_name,
                        "beforeCommitSpecifier": destination_commit,
                        "afterCommitSpecifier": source_commit,
                        "MaxResults": 100,  # AWS max per page
                    }

                    if next_token:
                        kwargs["nextToken"] = next_token

                    diff_response = pr_manager.retry_with_backoff(
                        pr_manager.codecommit_client.get_differences, **kwargs
                    )

                    differences = diff_response.get("differences", [])
                    page_files = len(differences)
                    total_files += page_files
                    total_pages += 1

                    # Count by change type
                    for diff in differences:
                        change_type = diff.get("changeType", "")
                        if change_type in file_summary:
                            file_summary[change_type] += 1

                    next_token = diff_response.get("nextToken")
                    if not next_token:
                        break

                    # Safety break for extreme cases
                    if total_pages > 1000:  # 100,000 files max
                        logger.warning(
                            f"PR {pull_request_id} has extremely large number of pages, limiting metadata scan"
                        )
                        break

                result += f"""
🎯 File Analysis:
   Total Files: {total_files:,}
   Total Pages: {total_pages:,} (100 files per page)
   
📈 Change Distribution:
   📄 Added: {file_summary['A']:,} files
   ✏️  Modified: {file_summary['M']:,} files
   🗑️  Deleted: {file_summary['D']:,} files

🔄 Review Strategy:
   Recommended: {"Smart pagination required" if total_files > 100 else "Standard review workflow"}
   Next Steps: {"Use pr_page for file-by-file analysis" if total_files > 50 else "Use pr_page or direct file access"}
   
💡 Navigation:
   • pr_page(pull_request_id="{pull_request_id}", page=1) - Start file review
   • pr_file_chunk(file_path="path", start_line=1) - Get file content"""

            except Exception as e:
                result += f"\n⚠️  Metadata analysis failed: {str(e)}"

        else:
            result += f"""

🔍 Available Analysis Tools:
   • get_pr_info(pull_request_id="{pull_request_id}", include_metadata=true) - Get full metadata
   • pr_page - Navigate files page by page
   • pr_file_diff - Review diff of file content in chunks
   • pr_file_chunk - Review file content in chunks
   • pr_comments - See discussions
   • pr_events - View activity timeline
   • pr_approvals - Check approval status"""

        return [types.TextContent(type="text", text=result)]

    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        error_msg = e.response["Error"]["Message"]

        if error_code == "PullRequestDoesNotExistException":
            return [
                types.TextContent(
                    type="text",
                    text=f"❌ Pull Request {args['pull_request_id']} not found.\n"
                    f"🔧 Please verify:\n"
                    f"• PR ID is correct\n"
                    f"• You have access to the repository\n"
                    f"• PR exists and hasn't been deleted",
                )
            ]

        return [
            types.TextContent(
                type="text", text=f"❌ AWS Error ({error_code}): {error_msg}"
            )
        ]


async def list_pull_requests(pr_manager, args: dict) -> List[types.TextContent]:
    """List pull requests with enhanced pagination and details"""
    try:
        kwargs = {
            "repositoryName": args["repository_name"],
            "maxResults": args.get("max_results", 50),
        }

        if "author_arn" in args:
            kwargs["authorArn"] = args["author_arn"]
        if "pr_status" in args:
            kwargs["pullRequestStatus"] = args["pr_status"]
        if (
            "next_token" in args
            and args["next_token"] not in pr_manager.processed_tokens
        ):
            kwargs["nextToken"] = args["next_token"]
            pr_manager.processed_tokens.add(args["next_token"])

        response = pr_manager.retry_with_backoff(
            pr_manager.codecommit_client.list_pull_requests, **kwargs
        )

        prs = response.get("pullRequestIds", [])
        next_token = response.get("nextToken")

        if not prs:
            result = f"📋 No pull requests found in {args['repository_name']}"
            if "pr_status" in args:
                result += f" with status: {args['pr_status']}"
            if "author_arn" in args:
                result += f" by author: {args['author_arn'].split('/')[-1]}"
            return [types.TextContent(type="text", text=result)]

        result = f"""📋 PRs in {args['repository_name']}:

🔍 Filters:
   Status: {args.get('pr_status', 'All')}
   Author: {args.get('author_arn', 'All').split('/')[-1] if args.get('author_arn') else 'All'}
   Max: {args.get('max_results', 50)}

📄 Found {len(prs)} PR(s):
"""

        # Get detailed info for each PR
        for i, pr_id in enumerate(prs, 1):
            try:
                pr_response = pr_manager.retry_with_backoff(
                    pr_manager.codecommit_client.get_pull_request, pullRequestId=pr_id
                )
                pr = pr_response["pullRequest"]
                target = pr["pullRequestTargets"][0]

                # Enhanced status indicators
                status_icon = "🟢" if pr["pullRequestStatus"] == "OPEN" else "🔴"
                merge_status = ""
                if pr["pullRequestStatus"] == "CLOSED":
                    merge_metadata = target.get("mergeMetadata", {})
                    if merge_metadata.get("isMerged"):
                        merge_status = " (Merged)"
                    else:
                        merge_status = " (Closed without merge)"

                result += f"""
   {i:2d}. {status_icon} PR #{pr['pullRequestId']}{merge_status}
       📝 {pr['title']}
       🔀 {target['sourceReference']} → {target['destinationReference']}
       👤 {pr.get('authorArn', 'Unknown').split('/')[-1] if pr.get('authorArn') else 'Unknown'}
       📅 {pr['creationDate'].strftime('%Y-%m-%d %H:%M')}
"""

            except Exception as e:
                result += (
                    f"\n   {i:2d}. ❌ PR #{pr_id} - Error loading details: {str(e)}"
                )

        if next_token:
            result += f"\n\n📄 More results available. Use next_token: {next_token}"

        return [types.TextContent(type="text", text=result)]

    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        error_msg = e.response["Error"]["Message"]

        if error_code == "RepositoryDoesNotExistException":
            return [
                types.TextContent(
                    type="text",
                    text=f"❌ Repository {args['repository_name']} not found.\n"
                    f"🔧 Please verify:\n"
                    f"• Repository name is correct\n"
                    f"• You have access to the repository\n"
                    f"• Repository exists in current region: {pr_manager.current_region}",
                )
            ]

        return [
            types.TextContent(
                type="text", text=f"❌ AWS Error ({error_code}): {error_msg}"
            )
        ]


# Update functions with enhanced error handling
async def update_pull_request_title(pr_manager, args: dict) -> List[types.TextContent]:
    """Update pull request title with validation"""
    try:
        response = pr_manager.retry_with_backoff(
            pr_manager.codecommit_client.update_pull_request_title,
            pullRequestId=args["pull_request_id"],
            title=args["title"],
        )
        pr = response["pullRequest"]
        result = f"""✅ Title Updated:

🆔 PR ID: {pr['pullRequestId']}
📝 Title: {pr['title']}
📅 Updated: {pr['lastActivityDate'].strftime('%Y-%m-%d %H:%M:%S UTC')}
👤 Author: {pr.get('authorArn', 'Unknown').split('/')[-1] if pr.get('authorArn') else 'Unknown'}"""
        return [types.TextContent(type="text", text=result)]
    except ClientError as e:
        return [
            types.TextContent(
                type="text",
                text=f"❌ AWS Error ({e.response['Error']['Code']}): {e.response['Error']['Message']}",
            )
        ]


async def update_pull_request_description(
    pr_manager, args: dict
) -> List[types.TextContent]:
    """Update pull request description with validation"""
    try:
        response = pr_manager.retry_with_backoff(
            pr_manager.codecommit_client.update_pull_request_description,
            pullRequestId=args["pull_request_id"],
            description=args["description"],
        )
        pr = response["pullRequest"]
        result = f"""✅ Description Updated:

🆔 PR ID: {pr['pullRequestId']}
📝 Description: 
{pr.get('description', 'No description')}

📅 Updated: {pr['lastActivityDate'].strftime('%Y-%m-%d %H:%M:%S UTC')}"""
        return [types.TextContent(type="text", text=result)]
    except ClientError as e:
        return [
            types.TextContent(
                type="text",
                text=f"❌ AWS Error ({e.response['Error']['Code']}): {e.response['Error']['Message']}",
            )
        ]


async def update_pull_request_status(pr_manager, args: dict) -> List[types.TextContent]:
    """Update pull request status with enhanced feedback"""
    try:
        response = pr_manager.retry_with_backoff(
            pr_manager.codecommit_client.update_pull_request_status,
            pullRequestId=args["pull_request_id"],
            pullRequestStatus=args["status"],
        )
        pr = response["pullRequest"]

        status_icon = "🟢" if args["status"] == "OPEN" else "🔴"
        action = "reopened" if args["status"] == "OPEN" else "closed"

        result = f"""✅ Status Updated:

🆔 PR ID: {pr['pullRequestId']}
{status_icon} Status: {args["status"]}
📅 Updated: {pr['lastActivityDate'].strftime('%Y-%m-%d %H:%M:%S UTC')}

🎯 PR {action} successfully."""

        return [types.TextContent(type="text", text=result)]
    except ClientError as e:
        return [
            types.TextContent(
                type="text",
                text=f"❌ AWS Error ({e.response['Error']['Code']}): {e.response['Error']['Message']}",
            )
        ]
