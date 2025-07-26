"""
Pull Request comment management handlers
"""

import logging
from typing import List, Dict
from botocore.exceptions import ClientError
import mcp.types as types
from datetime import datetime

logger = logging.getLogger(__name__)

# Global tracker for fallback comments to enable smart aggregation
_fallback_comment_tracker: Dict[str, List[Dict]] = {}


async def post_comment_for_pull_request(
    pr_manager, args: dict
) -> List[types.TextContent]:
    """Post a comment on a pull request with enhanced validation and intelligent fallback"""
    original_location = args.get("location")
    fallback_attempted = False
    
    try:
        kwargs = {
            "pullRequestId": args["pull_request_id"],
            "repositoryName": args["repository_name"],
            "beforeCommitId": args["before_commit_id"],
            "afterCommitId": args["after_commit_id"],
            "content": args["content"],
        }

        if "location" in args:
            location = args["location"]
            
            # CRITICAL VALIDATION: Check for common inline comment failures
            file_path = location.get("filePath", "")
            file_position = location.get("filePosition", 0)
            relative_version = location.get("relativeFileVersion", "")
            
            # Log validation details
            logger.info(f"INLINE COMMENT VALIDATION:")
            logger.info(f"  - filePath: '{file_path}' (length: {len(file_path)})")
            logger.info(f"  - filePosition: {file_position} (type: {type(file_position)})")
            logger.info(f"  - relativeFileVersion: '{relative_version}' (valid: {relative_version in ['BEFORE', 'AFTER']})")
            
            # Validate required fields for inline comments
            if not file_path:
                logger.warning("INLINE COMMENT WARNING: filePath is empty!")
            if file_position <= 0:
                logger.warning(f"INLINE COMMENT WARNING: filePosition {file_position} might be invalid!")
            if relative_version not in ["BEFORE", "AFTER"]:
                logger.warning(f"INLINE COMMENT WARNING: relativeFileVersion '{relative_version}' is invalid!")
            
            # CRITICAL FIX: Ensure location uses exact AWS API field names
            # AWS CodeCommit is very strict about this - use camelCase exactly
            validated_location = {
                "filePath": str(file_path),  # Ensure string type
                "filePosition": int(file_position),  # Ensure integer type
                "relativeFileVersion": str(relative_version)  # Ensure string type
            }
            
            # CRITICAL WARNING: filePosition must be within diff context
            logger.warning("CRITICAL INLINE COMMENT REQUIREMENT:")
            logger.warning(f"  The filePosition {file_position} MUST be within the actual diff context!")
            logger.warning(f"  This means line {file_position} must have actual changes in the PR diff")
            logger.warning(f"  If line {file_position} is not changed, the comment will appear as general comment")
            logger.warning(f"  File: {file_path} - Version: {relative_version}")
            
            # VERSION MISMATCH WARNING
            if relative_version == "AFTER":
                logger.warning("VERSION MISMATCH CHECK:")
                logger.warning(f"  You're commenting on AFTER version at line {file_position}")
                logger.warning(f"  ENSURE you used pr_file_chunk(version='after') to get this line number!")
                logger.warning(f"  Using line numbers from 'before' version will cause positioning failures!")
            elif relative_version == "BEFORE":
                logger.warning("UNCOMMON USAGE WARNING:")
                logger.warning(f"  You're commenting on BEFORE version - this is rare!")
                logger.warning(f"  Most comments should use AFTER version with pr_file_chunk(version='after')")
            
            kwargs["location"] = validated_location
            logger.info(f"INLINE COMMENT FIXED - Validated location: {validated_location}")
            logger.info(f"INLINE COMMENT DEBUG - Location parameters: {location}")
            logger.info(f"INLINE COMMENT DEBUG - Full kwargs: {kwargs}")
        if "client_request_token" in args:
            kwargs["clientRequestToken"] = args["client_request_token"]

        logger.info(f"COMMENT DEBUG - Making AWS API call with kwargs: {kwargs}")
        
        # INTELLIGENT FALLBACK MECHANISM
        try:
            response = pr_manager.retry_with_backoff(
                pr_manager.codecommit_client.post_comment_for_pull_request, **kwargs
            )
            logger.info(f"COMMENT DEBUG - AWS Response: {response}")
            
            # Check if inline comment was successful by verifying the response has location
            if original_location and "location" not in response.get("comment", {}):
                logger.warning("FALLBACK TRIGGER: Inline comment may not have positioned correctly")
                raise Exception("InlineCommentFallback")
                
        except Exception as e:
            if original_location and not fallback_attempted:
                logger.warning(f"FALLBACK ACTIVATED: Inline comment failed ({str(e)}), using smart aggregation")
                fallback_attempted = True
                
                # Smart aggregation for multiple fallback comments per file
                file_path = original_location.get("filePath", "unknown")
                file_position = original_location.get("filePosition", "unknown")
                pr_id = args["pull_request_id"]
                
                # Create unique key for this PR + file combination
                aggregation_key = f"{pr_id}:{file_path}"
                
                # Initialize tracker for this file if not exists
                if aggregation_key not in _fallback_comment_tracker:
                    _fallback_comment_tracker[aggregation_key] = []
                
                # Add this comment to the aggregation tracker
                comment_entry = {
                    "line": file_position,
                    "content": args['content'],
                    "timestamp": datetime.now().isoformat()
                }
                _fallback_comment_tracker[aggregation_key].append(comment_entry)
                
                # Check if we should aggregate (wait 2 seconds for potential batch)
                current_comments = _fallback_comment_tracker[aggregation_key]
                logger.info(f"AGGREGATION: {len(current_comments)} comments pending for {file_path}")
                
                # For now, post immediately but with aggregation-aware content
                # TODO: Could implement delayed posting for true batching
                
                # Collect all failed line numbers for better reporting
                failed_lines = [comment['line'] for comment in current_comments]
                failed_lines_str = ", ".join(map(str, failed_lines))
                
                aggregated_content = f"""📁 **File-Level Comments** for `{file_path}`

🚫 **Failed Inline Comment Attempts**:
   📂 File Path: {file_path}
   📍 Intended Lines: {failed_lines_str}
   ⚠️ Reason: These line numbers are not within the actual diff context

"""
                
                for i, comment in enumerate(current_comments, 1):
                    aggregated_content += f"""**#{i} - Originally intended for line {comment['line']}:**
{comment['content']}

---

"""
                
                aggregated_content += f"""💡 **How to Fix for Future Comments**:
   • Use pr_file_chunk(file_path="{file_path}") to see actual changed lines
   • Look for lines with +/- markers in the diff output
   • Only comment on lines that show actual changes
   • Avoid commenting on unchanged context lines

📊 **Summary**: {len(current_comments)} comments aggregated for {file_path}
🕒 **Posted**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
🔧 **Tool**: Smart fallback aggregation system"""
                
                # Remove location for file-level comment
                fallback_kwargs = kwargs.copy()
                fallback_kwargs.pop("location", None)
                fallback_kwargs["content"] = aggregated_content
                
                logger.info(f"AGGREGATED FALLBACK - Posting {len(current_comments)} comments for {file_path}")
                response = pr_manager.retry_with_backoff(
                    pr_manager.codecommit_client.post_comment_for_pull_request, **fallback_kwargs
                )
                
                # Clear the tracker for this file after successful posting
                _fallback_comment_tracker[aggregation_key] = []
                logger.info(f"AGGREGATION SUCCESS - Cleared tracker for {file_path}")
            else:
                raise e

        comment = response.get("comment", {})
        is_inline = "location" in args and not fallback_attempted
        
        # Determine comment type with aggregation info
        if is_inline:
            comment_type = "Inline"
        elif fallback_attempted:
            # Get the count from the aggregated content or tracker before it was cleared
            aggregation_key = f"{args['pull_request_id']}:{original_location.get('filePath', 'unknown')}"
            # Extract count from the posted content to show accurate aggregation
            try:
                # Count was captured before clearing tracker
                posted_content = response.get("comment", {}).get("content", "")
                if "Aggregated Comments" in posted_content:
                    import re
                    match = re.search(r"Aggregated Comments\*\*: (\d+)", posted_content)
                    comment_count = match.group(1) if match else "multiple"
                    comment_type = f"File-Level Aggregated ({comment_count} comments)"
                else:
                    comment_type = "File-Level Fallback"
            except:
                comment_type = "File-Level Fallback"
        else:
            comment_type = "General"

        result = f"""✅ Comment Posted:

💬 Details:
   Comment ID: {comment.get('commentId', 'Unknown')}
   PR ID: {args['pull_request_id']}
   Type: {comment_type}
   
📝 Content:
{args['content'] if not fallback_attempted else 'See file-level comment content above'}

"""

        if is_inline:
            location = args["location"]
            result += f"""📍 Location:
   File: {location.get('filePath', 'Unknown')}
   Position: {location.get('filePosition', 'Unknown')}
   Version: {location.get('relativeFileVersion', 'Unknown')}

"""
        elif fallback_attempted and original_location:
            file_path = original_location.get('filePath', 'Unknown')
            file_position = original_location.get('filePosition', 'Unknown')
            result += f"""📁 Fallback Info:
   🚫 Failed Inline Comment Target:
      📂 File Path: {file_path}
      📍 Intended Line: {file_position}
      📑 Version: {original_location.get('relativeFileVersion', 'Unknown')}
   
   ⚠️ Fallback Reason: Line {file_position} not in actual diff context for {file_path}
   ✅ Result: Successfully posted as file-level comment instead
   
   💡 Next Steps: Use pr_file_chunk(file_path="{file_path}") to see actual changed lines

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
• CRITICAL: filePosition must be within actual diff context (changed lines only)
• Use pr_file_chunk to see actual changed lines (look for +/- markers)
• Only comment on lines that appear in the diff output
• Check that the file path exists in the PR
• Ensure the relative_file_version is correct (BEFORE/AFTER)

💡 TIP: Use pr_file_chunk first to identify exact line numbers with changes
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


async def get_fallback_comment_status(
    pr_manager, args: dict
) -> List[types.TextContent]:
    """Get status of pending fallback comment aggregations"""
    try:
        pr_id = args.get("pull_request_id", "all")
        
        if not _fallback_comment_tracker:
            return [types.TextContent(
                type="text", 
                text="📊 Fallback Comment Status: No pending aggregations"
            )]
        
        result = "📊 **Fallback Comment Aggregation Status**\n\n"
        
        total_pending = 0
        for key, comments in _fallback_comment_tracker.items():
            if not comments:  # Skip empty entries
                continue
                
            tracked_pr_id, file_path = key.split(":", 1)
            
            if pr_id != "all" and tracked_pr_id != pr_id:
                continue
                
            total_pending += len(comments)
            result += f"**PR {tracked_pr_id}**:\n"
            result += f"  🚫 File with failed inline attempts: `{file_path}`\n"
            result += f"  📝 {len(comments)} comments pending aggregation\n"
            result += f"  📍 Failed line numbers: {', '.join(str(c['line']) for c in comments)}\n"
            
            for i, comment in enumerate(comments, 1):
                result += f"    {i}. Line {comment['line']} - {comment['content'][:30]}... ({comment['timestamp'][:19]})\n"
            result += "\n"
        
        if total_pending == 0:
            result += "✅ No pending aggregations found\n"
        else:
            result += f"📊 **Total**: {total_pending} comments pending across {len([k for k, v in _fallback_comment_tracker.items() if v])} files\n"
            result += "\n💡 **Note**: Comments are aggregated automatically when fallback is triggered."
        
        return [types.TextContent(type="text", text=result)]
        
    except Exception as e:
        return [types.TextContent(
            type="text", 
            text=f"❌ Error checking fallback status: {str(e)}"
        )]


async def bulk_add_comments(
    pr_manager, args: dict
) -> List[types.TextContent]:
    """Post multiple inline comments efficiently with smart aggregation and progress tracking"""
    try:
        comments = args.get("comments", [])
        pr_id = args["pull_request_id"]
        repo_name = args["repository_name"]
        before_commit = args["before_commit_id"]
        after_commit = args["after_commit_id"]
        
        if not comments:
            return [types.TextContent(
                type="text", 
                text="❌ No comments provided for bulk posting"
            )]
        
        logger.info(f"BULK COMMENTS: Starting bulk post of {len(comments)} comments for PR {pr_id}")
        
        # Statistics tracking
        total_comments = len(comments)
        successful_inline = 0
        successful_fallback = 0
        failed_comments = 0
        results = []
        fallback_files = set()  # Track which files had fallback issues
        
        # Process each comment
        for i, comment_data in enumerate(comments, 1):
            try:
                logger.info(f"BULK PROGRESS: Processing comment {i}/{total_comments}")
                
                # Prepare individual comment args
                individual_args = {
                    "pull_request_id": pr_id,
                    "repository_name": repo_name,
                    "before_commit_id": before_commit,
                    "after_commit_id": after_commit,
                    "content": comment_data.get("content", ""),
                }
                
                # Add location if provided
                if "location" in comment_data:
                    individual_args["location"] = comment_data["location"]
                
                # Call our existing comment handler which has smart aggregation
                result = await post_comment_for_pull_request(pr_manager, individual_args)
                
                # Analyze result for statistics
                result_text = result[0].text if result else ""
                if "Inline" in result_text:
                    successful_inline += 1
                    results.append(f"✅ Comment {i}: Inline - {comment_data.get('content', 'No content')[:50]}...")
                elif "Fallback" in result_text or "Aggregated" in result_text:
                    successful_fallback += 1
                    # Track which file had fallback
                    if "location" in comment_data:
                        fallback_file = comment_data["location"].get("filePath", "unknown")
                        fallback_files.add(fallback_file)
                        results.append(f"📁 Comment {i}: Fallback ({fallback_file}) - {comment_data.get('content', 'No content')[:50]}...")
                    else:
                        results.append(f"📁 Comment {i}: General - {comment_data.get('content', 'No content')[:50]}...")
                else:
                    successful_inline += 1  # Assume general comments are successful
                    results.append(f"✅ Comment {i}: Posted - {comment_data.get('content', 'No content')[:50]}...")
                
            except Exception as e:
                failed_comments += 1
                error_msg = str(e)[:100]
                results.append(f"❌ Comment {i}: Failed - {error_msg}...")
                logger.error(f"BULK ERROR: Comment {i} failed: {str(e)}")
        
        # Generate comprehensive summary
        success_rate = ((successful_inline + successful_fallback) / total_comments) * 100
        
        summary = f"""🎯 **Bulk Comment Posting Complete**

📊 **Summary Statistics**:
   Total Comments: {total_comments}
   ✅ Successful Inline: {successful_inline}
   📁 Fallback/Aggregated: {successful_fallback}
   ❌ Failed: {failed_comments}
   📈 Success Rate: {success_rate:.1f}%

📋 **Individual Results**:
"""
        
        for result in results:
            summary += f"   {result}\n"
        
        if successful_fallback > 0:
            fallback_files_list = ", ".join(sorted(fallback_files)) if fallback_files else "N/A"
            summary += f"""
🔄 **Smart Aggregation Applied**:
   📊 Comments with fallback: {successful_fallback}
   📂 Files affected by fallback: {fallback_files_list}
   ⚠️  Reason: Line numbers were not within actual diff context
   
💡 **Fix for affected files**: 
   • Use pr_file_chunk(file_path="<file>") for each affected file
   • Look for lines with +/- markers (actual changes)
   • Only comment on changed lines, not context lines
"""
        
        if failed_comments > 0:
            summary += f"""
⚠️ **Failed Comments**:
   {failed_comments} comments could not be posted. Check logs for details.
   Common causes: Invalid parameters, network issues, or permission problems.
"""
        
        summary += f"""
⏰ **Posted**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
🔧 **Tool**: bulk_add_comments (simulated batch via individual API calls)

📝 **Note**: AWS CodeCommit does not provide native bulk comment API. 
This tool efficiently processes multiple comments with smart aggregation fallback."""
        
        logger.info(f"BULK COMPLETE: {successful_inline + successful_fallback}/{total_comments} successful")
        
        return [types.TextContent(type="text", text=summary)]
        
    except Exception as e:
        logger.error(f"BULK COMMENTS FAILED: {str(e)}")
        return [types.TextContent(
            type="text", 
            text=f"❌ Bulk comment posting failed: {str(e)}"
        )]


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
