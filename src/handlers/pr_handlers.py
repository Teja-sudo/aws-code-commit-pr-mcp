"""
Pull Request management handlers
"""

import logging
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
            return [types.TextContent(
                type="text", 
                text="❌ Error: pull_request_id cannot be empty"
            )]

        response = pr_manager.retry_with_backoff(
            pr_manager.codecommit_client.get_pull_request,
            pullRequestId=pull_request_id,
        )

        pr = response["pullRequest"]
        target = pr["pullRequestTargets"][0]
        repository_name = target["repositoryName"]
        source_commit = target["sourceCommit"]
        destination_commit = target["destinationCommit"]

        result = f"""📋 Pull Request Details:

🆔 Basic Information:
   PR ID: {pr['pullRequestId']}
   Title: {pr['title']}
   Status: {pr['pullRequestStatus']}
   Repository: {repository_name}
   
📝 Description:
{pr.get('description', 'No description provided')}

👤 Author Information:
   Author ARN: {pr.get('authorArn', 'Unknown')}
   Created: {pr['creationDate'].strftime('%Y-%m-%d %H:%M:%S UTC')}
   Last Updated: {pr['lastActivityDate'].strftime('%Y-%m-%d %H:%M:%S UTC')}

🔀 Branch Details:
   Source: {target['sourceReference']} ({source_commit})
   Destination: {target['destinationReference']} ({destination_commit})
   Merge Option: {target.get('mergeMetadata', {}).get('mergeOption', 'Not specified')}

💬 Commit IDs for Comments:
   Before Commit: {destination_commit}
   After Commit: {source_commit}"""

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
                        logger.warning(f"PR {pull_request_id} has extremely large number of pages, limiting metadata scan")
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


async def get_pull_request_changes_bulletproof(
    pr_manager, args: dict
) -> List[types.TextContent]:
    """Enhanced PR changes analysis with bulletproof edge case handling"""
    try:
        pull_request_id = args["pull_request_id"]
        include_diff = args.get("include_diff", True)
        max_files = args.get("max_files", 100000)
        file_filter = args.get("file_path_filter")
        deep_analysis = args.get("deep_analysis", True)
        stream_processing = args.get("stream_processing", True)

        # Get PR details with retry logic
        pr_response = pr_manager.retry_with_backoff(
            pr_manager.codecommit_client.get_pull_request,
            pullRequestId=pull_request_id,
        )

        pr = pr_response["pullRequest"]
        target = pr["pullRequestTargets"][0]
        repository_name = target["repositoryName"]
        source_commit = target["sourceCommit"]
        destination_commit = target["destinationCommit"]
        pr_status = pr["pullRequestStatus"]

        result = f"""🔍 Enhanced Pull Request Analysis:

🆔 PR Information:
   PR ID: {pull_request_id}
   Status: {pr_status}
   Repository: {repository_name}
   Source: {source_commit} → Destination: {destination_commit}

⚙️  Analysis Configuration:
   Include Diff: {include_diff}
   Max Files: {max_files:,}
   File Filter: {file_filter or 'None'}
   Deep Analysis: {deep_analysis}
   Stream Processing: {stream_processing}

🔍 Starting comprehensive analysis...

"""

        # Use destination commit as base for comparison
        # Note: AWS CodeCommit doesn't have a direct merge base API
        before_commit = destination_commit
        after_commit = source_commit
        result += f"✅ Using destination commit as base: {before_commit}\n\n"

        # Enhanced pagination with bulletproof token handling
        all_differences = await get_changes_with_enhanced_pagination(
            pr_manager,
            repository_name,
            before_commit,
            after_commit,
            max_files,
            file_filter,
            stream_processing,
        )

        total_files = len(all_differences)

        if total_files == 0:
            result += """📄 No file changes detected.

This could mean:
• PR has no actual file modifications
• All changes are in ignored/filtered paths
• PR might be closed/merged without changes
• Access permissions might be limiting visibility

✅ Analysis complete - No changes found."""
            return [types.TextContent(type="text", text=result)]

        # For huge PRs, use streaming analysis
        if total_files > 100 or stream_processing:
            result += await stream_analyze_huge_pr(all_differences)
        else:
            # Regular analysis for smaller PRs
            result += f"📊 Found {total_files} file changes:\n\n"

            for i, diff in enumerate(all_differences, 1):
                change_type = diff.get("changeType", "")
                change_icon = {"A": "📄", "M": "✏️", "D": "🗑️"}.get(change_type, "❓")

                if change_type == "A":
                    blob = diff.get("afterBlob", {})
                elif change_type == "D":
                    blob = diff.get("beforeBlob", {})
                else:
                    blob = diff.get("afterBlob", {}) or diff.get("beforeBlob", {})

                file_path = blob.get("path", "Unknown")
                file_size = blob.get("size", 0)

                result += (
                    f"   {i:3d}. {change_icon} {file_path} ({file_size:,} bytes)\n"
                )

        # Enhanced file discovery if enabled
        if deep_analysis and total_files > 0:
            try:
                discovered_files = await get_comprehensive_file_discovery(
                    pr_manager, pull_request_id, repository_name, pr
                )
                if discovered_files:
                    result += f"\n🔍 Deep Analysis: Found {len(discovered_files)} additional file references\n"
            except Exception as e:
                logger.warning(f"Deep analysis failed: {str(e)}")

        result += f"""

✅ Analysis Complete!

📊 Summary:
   • Files: {total_files:,}
   • Stream: {'On' if stream_processing else 'Off'}
   • Deep: {'On' if deep_analysis else 'Off'}
   • Filter: {'Yes' if file_filter else 'No'}
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
                    f"🔧 Please verify the PR ID is correct and you have access to the repository.",
                )
            ]

        return [
            types.TextContent(
                type="text", text=f"❌ AWS Error ({error_code}): {error_msg}"
            )
        ]

    except Exception as e:
        logger.error(
            f"Unexpected error in get_pull_request_changes_bulletproof: {str(e)}"
        )
        return [
            types.TextContent(
                type="text",
                text=f"💥 Unexpected Error: {str(e)}\n\nThis indicates a serious issue. Please contact support with this error message.",
            )
        ]


async def get_pull_request_file_paths(
    pr_manager, args: dict
) -> List[types.TextContent]:
    """Get all file paths associated with a pull request with filtering options"""
    try:
        import re

        pull_request_id = args["pull_request_id"]
        change_types = args.get("change_types", ["A", "M", "D"])
        file_extension_filter = args.get("file_extension_filter")
        path_pattern = args.get("path_pattern")

        # Get PR details
        pr_response = pr_manager.retry_with_backoff(
            pr_manager.codecommit_client.get_pull_request,
            pullRequestId=pull_request_id,
        )

        pr = pr_response["pullRequest"]
        target = pr["pullRequestTargets"][0]
        repository_name = target["repositoryName"]
        source_commit = target["sourceCommit"]
        destination_commit = target["destinationCommit"]
        pr_status = pr["pullRequestStatus"]

        # Use destination commit as base for comparison
        # Note: AWS CodeCommit doesn't have a direct merge base API
        before_commit = destination_commit
        after_commit = source_commit

        # Get all differences
        all_differences = []
        next_token = None

        while True:
            kwargs = {
                "repositoryName": repository_name,
                "beforeCommitSpecifier": before_commit,
                "afterCommitSpecifier": after_commit,
                "MaxResults": 100,
            }

            if next_token:
                kwargs["nextToken"] = next_token

            diff_response = pr_manager.retry_with_backoff(
                pr_manager.codecommit_client.get_differences, **kwargs
            )

            differences = diff_response.get("differences", [])
            all_differences.extend(differences)

            next_token = diff_response.get("nextToken")
            if not next_token:
                break

        # Process and filter file paths
        file_paths = {"A": [], "M": [], "D": []}

        for diff in all_differences:
            change_type = diff.get("changeType", "")

            # Skip if change type not in filter
            if change_type not in change_types:
                continue

            file_path = None

            # Get file path based on change type
            if change_type == "A":  # Added
                file_path = diff.get("afterBlob", {}).get("path")
            elif change_type == "M":  # Modified
                file_path = diff.get("afterBlob", {}).get("path") or diff.get(
                    "beforeBlob", {}
                ).get("path")
            elif change_type == "D":  # Deleted
                file_path = diff.get("beforeBlob", {}).get("path")

            if not file_path:
                continue

            # Apply file extension filter if specified
            if file_extension_filter:
                if not file_path.endswith(file_extension_filter):
                    continue

            # Apply path pattern filter if specified
            if path_pattern:
                try:
                    if not re.search(path_pattern, file_path):
                        continue
                except re.error:
                    # If regex is invalid, treat as literal string match
                    if path_pattern not in file_path:
                        continue

            file_paths[change_type].append(file_path)

        # Sort all file paths
        for change_type in file_paths:
            file_paths[change_type].sort()

        # Generate summary
        total_files = sum(len(paths) for paths in file_paths.values())

        result = f"""📁 File Paths for Pull Request {pull_request_id}:

🆔 PR Information:
   Repository: {repository_name}
   Status: {pr_status}
   Source: {source_commit}
   Base: {before_commit}

🔍 Filters Applied:
   Change Types: {', '.join(change_types)}
   Extension Filter: {file_extension_filter or 'None'}
   Path Pattern: {path_pattern or 'None'}

📊 Summary:
   Total Files: {total_files}
   Added: {len(file_paths['A'])}
   Modified: {len(file_paths['M'])}
   Deleted: {len(file_paths['D'])}

"""

        # Add file listings by category
        if file_paths["A"] and "A" in change_types:
            result += f"📄 ADDED FILES ({len(file_paths['A'])}):\n"
            for i, path in enumerate(file_paths["A"], 1):
                result += f"   {i:3d}. {path}\n"
            result += "\n"

        if file_paths["M"] and "M" in change_types:
            result += f"✏️  MODIFIED FILES ({len(file_paths['M'])}):\n"
            for i, path in enumerate(file_paths["M"], 1):
                result += f"   {i:3d}. {path}\n"
            result += "\n"

        if file_paths["D"] and "D" in change_types:
            result += f"🗑️  DELETED FILES ({len(file_paths['D'])}):\n"
            for i, path in enumerate(file_paths["D"], 1):
                result += f"   {i:3d}. {path}\n"
            result += "\n"

        if total_files == 0:
            result += "ℹ️  No files match the specified filters.\n"
        else:
            result += f"✅ Retrieved {total_files} file paths successfully!\n\n"
            result += "💡 Use get_pull_request_file_content to get the actual content of specific files."

        return [types.TextContent(type="text", text=result)]

    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        error_msg = e.response["Error"]["Message"]

        if error_code == "PullRequestDoesNotExistException":
            return [
                types.TextContent(
                    type="text",
                    text=f"❌ Pull Request {args['pull_request_id']} not found.\n"
                    f"🔧 Please verify the PR ID is correct and you have access to the repository.",
                )
            ]

        return [
            types.TextContent(
                type="text", text=f"❌ AWS Error ({error_code}): {error_msg}"
            )
        ]

    except Exception as e:
        logger.error(f"Error in get_pull_request_file_paths: {str(e)}")
        return [
            types.TextContent(
                type="text", text=f"❌ Error retrieving file paths: {str(e)}"
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
