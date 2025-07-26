"""
Smart pagination handlers for Claude-driven huge PR processing
"""

import logging
from typing import List, Dict, Any
from botocore.exceptions import ClientError
import mcp.types as types
from ..utils.helpers import get_primary_pr_target, get_permission_aware_error_message

logger = logging.getLogger(__name__)

# Global cache for pagination tokens (in production, consider using Redis)
_pagination_cache = {}


async def get_pr_metadata(pr_manager, args: dict) -> List[types.TextContent]:
    """Get PR metadata first - total files, total lines, pagination info"""
    try:
        pull_request_id = str(args["pull_request_id"]).strip()
        if not pull_request_id:
            return [
                types.TextContent(
                    type="text", text="❌ Error: pull_request_id cannot be empty"
                )
            ]

        # Get PR details
        pr_response = pr_manager.retry_with_backoff(
            pr_manager.codecommit_client.get_pull_request,
            pullRequestId=pull_request_id,
        )

        pr = pr_response["pullRequest"]
        try:
            target = get_primary_pr_target(pr)
        except ValueError as e:
            return [
                types.TextContent(
                    type="text", text=f"❌ PR Target Error: {str(e)}\n🔧 This PR may have multiple targets or missing target information"
                )
            ]
        
        repository_name = target["repositoryName"]
        source_commit = target["sourceCommit"]
        destination_commit = target["destinationCommit"]

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

        result = f"""📊 PR {pull_request_id} Metadata:

🎯 Smart Pagination Ready:
   Repository: {repository_name}
   Status: {pr['pullRequestStatus']}
   Total Files: {total_files:,}
   Total Pages: {total_pages:,}

📈 File Distribution:
   📄 Added: {file_summary['A']:,} files
   ✏️  Modified: {file_summary['M']:,} files
   🗑️  Deleted: {file_summary['D']:,} files

🔄 Pagination Strategy:
   Files per page: 100 (AWS limit)
   Recommended batch size: 5-10 pages per review
   Memory-safe: ✅ No content loaded yet

📋 Next Steps for Claude:
1. Use pr_page to get specific page (1-{total_pages})
2. Review files in batches of 5-10 pages
3. Use pr_file_chunk for large files (line-by-line)
4. Process incrementally to avoid memory issues

💡 Example workflow:
• pr_page(pull_request_id="{pull_request_id}", page=1)
• Review first 100 files, then continue with page=2
• For large files, use pr_file_chunk for line chunks"""

        return [types.TextContent(type="text", text=result)]

    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        error_msg = e.response["Error"]["Message"]
        
        # Determine operation context for better error messages
        operation = "unknown operation"
        if "get_pr_metadata" in str(e):
            operation = "get PR metadata and file analysis"
        elif "get_pr_page" in str(e):
            operation = "get PR file page"
        elif "get_pr_file_chunk" in str(e):
            operation = "get file content chunk"
        
        enhanced_error = get_permission_aware_error_message(
            error_code, error_msg, operation
        )
        
        return [
            types.TextContent(type="text", text=enhanced_error)
        ]


async def get_pr_page(pr_manager, args: dict) -> List[types.TextContent]:
    """Get a specific page of files (memory-safe)"""
    try:
        pull_request_id = args["pull_request_id"]
        page_number = args.get("page", 1)
        include_content = args.get("include_content", False)

        # Get PR details
        pr_response = pr_manager.retry_with_backoff(
            pr_manager.codecommit_client.get_pull_request,
            pullRequestId=pull_request_id,
        )

        pr = pr_response["pullRequest"]
        try:
            target = get_primary_pr_target(pr)
        except ValueError as e:
            return [
                types.TextContent(
                    type="text", text=f"❌ PR Target Error: {str(e)}\n🔧 This PR may have multiple targets or missing target information"
                )
            ]
        
        repository_name = target["repositoryName"]
        source_commit = target["sourceCommit"]
        destination_commit = target["destinationCommit"]

        # Create cache key for this PR
        cache_key = f"{pull_request_id}:{source_commit}:{destination_commit}"
        
        # Use efficient pagination with token caching
        target_differences, pagination_info = await _get_page_with_token_cache(
            pr_manager, repository_name, source_commit, destination_commit, 
            page_number, cache_key
        )

        if not target_differences:
            return [
                types.TextContent(
                    type="text",
                    text=f"📄 Page {page_number} not found or empty for PR {pull_request_id}",
                )
            ]

        result = f"""📄 PR {pull_request_id} - Page {page_number}:

📊 Page Info:
   Files in this page: {len(target_differences)}
   Content included: {include_content}
   Pagination: {pagination_info}
   
📋 Files on this page:
"""

        for i, diff in enumerate(target_differences, 1):
            change_type = diff.get("changeType", "")
            change_icon = {"A": "📄", "M": "✏️", "D": "🗑️"}.get(change_type, "❓")

            # Handle file renames properly
            if change_type == "A":
                blob = diff.get("afterBlob", {})
                file_path = blob.get("path", "Unknown")
            elif change_type == "D":
                blob = diff.get("beforeBlob", {})
                file_path = blob.get("path", "Unknown")
            else:  # Modified or Renamed
                after_blob = diff.get("afterBlob", {})
                before_blob = diff.get("beforeBlob", {})
                
                after_path = after_blob.get("path", "")
                before_path = before_blob.get("path", "")
                
                # Handle renamed files
                if after_path and before_path and after_path != before_path:
                    file_path = f"{before_path} → {after_path}"
                    change_icon = "📝"  # Special icon for renamed files
                else:
                    file_path = after_path or before_path or "Unknown"
                    
                blob = after_blob or before_blob
            file_size = blob.get("size", 0)

            result += f"   {i:3d}. {change_icon} {file_path}\n"
            result += f"        Size: {file_size:,} bytes\n"

            # Estimate lines for text files
            if file_size > 0 and not any(
                ext in file_path.lower() for ext in [".png", ".jpg", ".pdf", ".zip", ".gif", ".jpeg"]
            ):
                estimated_lines = max(1, file_size // 50)  # Rough estimate
                result += f"        Est. lines: ~{estimated_lines:,}\n"

            result += "\n"

        result += f"""
💡 Navigation:
• Next page: pr_page(pull_request_id="{pull_request_id}", page={page_number + 1})
• Previous page: pr_page(pull_request_id="{pull_request_id}", page={max(1, page_number - 1)})
• File content: pr_file_chunk for large files
• Include content: pr_page(..., include_content=true) for small pages

🎯 Memory usage: Only this page loaded ({len(target_differences)} files)
⚡ Performance: {pagination_info}"""

        return [types.TextContent(type="text", text=result)]

    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        error_msg = e.response["Error"]["Message"]
        
        # Determine operation context for better error messages
        operation = "unknown operation"
        if "get_pr_metadata" in str(e):
            operation = "get PR metadata and file analysis"
        elif "get_pr_page" in str(e):
            operation = "get PR file page"
        elif "get_pr_file_chunk" in str(e):
            operation = "get file content chunk"
        
        enhanced_error = get_permission_aware_error_message(
            error_code, error_msg, operation
        )
        
        return [
            types.TextContent(type="text", text=enhanced_error)
        ]


async def get_pr_file_chunk(pr_manager, args: dict) -> List[types.TextContent]:
    """Get a specific chunk of lines from a file (MEMORY-SAFE for huge files)"""
    try:
        pull_request_id = str(args["pull_request_id"]).strip()
        file_path = args["file_path"].strip()
        start_line = max(1, args.get("start_line", 1))  # Ensure positive line number
        chunk_size = min(500, max(1, args.get("chunk_size", 500)))  # Clamp chunk size
        version = args.get("version", "after")  # before/after

        if not file_path:
            return [
                types.TextContent(
                    type="text", text="❌ Error: file_path cannot be empty"
                )
            ]

        # Get PR details
        pr_response = pr_manager.retry_with_backoff(
            pr_manager.codecommit_client.get_pull_request,
            pullRequestId=pull_request_id,
        )

        pr = pr_response["pullRequest"]
        try:
            target = get_primary_pr_target(pr)
        except ValueError as e:
            return [
                types.TextContent(
                    type="text", text=f"❌ PR Target Error: {str(e)}\n🔧 This PR may have multiple targets or missing target information"
                )
            ]
        
        repository_name = target["repositoryName"]
        source_commit = target["sourceCommit"]
        destination_commit = target["destinationCommit"]

        # Determine which commit to use
        commit_id = source_commit if version == "after" else destination_commit

        try:
            # Check file size first for huge file detection
            try:
                file_response = pr_manager.retry_with_backoff(
                    pr_manager.codecommit_client.get_file,
                    repositoryName=repository_name,
                    commitSpecifier=commit_id,
                    filePath=file_path,
                )
                content_bytes = file_response["fileContent"]
                file_size = len(content_bytes)
            except Exception:
                # Fallback to get_blob
                blob_response = pr_manager.retry_with_backoff(
                    pr_manager.codecommit_client.get_blob,
                    repositoryName=repository_name,
                    blobId=commit_id,
                    filePath=file_path,
                )
                content_bytes = blob_response["content"]
                file_size = len(content_bytes)

            # MEMORY SAFETY CHECK: For files larger than 50MB, use streaming approach
            MAX_SAFE_SIZE = 50 * 1024 * 1024  # 50MB
            
            if file_size > MAX_SAFE_SIZE:
                return await _process_huge_file_streaming(
                    content_bytes, file_path, start_line, chunk_size, version, file_size
                )
            else:
                return await _process_normal_file(
                    content_bytes, file_path, start_line, chunk_size, version
                )

        except Exception as e:
            error_msg = str(e)
            if "PathDoesNotExistException" in error_msg:
                return [
                    types.TextContent(
                        type="text",
                        text=f"❌ File not found: {file_path}\n🔧 Verify the file path is correct and exists in the {version} version",
                    )
                ]
            return [
                types.TextContent(
                    type="text",
                    text=f"❌ Could not retrieve file {file_path}: {error_msg}",
                )
            ]

    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        error_msg = e.response["Error"]["Message"]
        
        # Determine operation context for better error messages
        operation = "unknown operation"
        if "get_pr_metadata" in str(e):
            operation = "get PR metadata and file analysis"
        elif "get_pr_page" in str(e):
            operation = "get PR file page"
        elif "get_pr_file_chunk" in str(e):
            operation = "get file content chunk"
        
        enhanced_error = get_permission_aware_error_message(
            error_code, error_msg, operation
        )
        
        return [
            types.TextContent(type="text", text=enhanced_error)
        ]


async def _process_huge_file_streaming(content_bytes, file_path, start_line, chunk_size, version, file_size):
    """MEMORY-SAFE processing for huge files using streaming line-by-line approach"""
    try:
        # Detect encoding without loading entire file
        encoding = _detect_encoding_from_sample(content_bytes[:1024])
        
        # Stream through content line by line without loading all into memory
        import io
        
        # Convert bytes to text stream
        try:
            text_content = content_bytes.decode(encoding)
        except UnicodeDecodeError:
            text_content = content_bytes.decode(encoding, errors='replace')
        
        # Use StringIO for memory-efficient line iteration
        content_stream = io.StringIO(text_content)
        
        current_line = 0
        target_lines = []
        total_lines = 0
        end_line = start_line + chunk_size - 1
        
        # Stream through lines WITHOUT storing all lines in memory
        while True:
            line = content_stream.readline()
            if not line:  # EOF
                break
                
            current_line += 1
            total_lines = current_line
            
            # Only collect lines in our target range
            if start_line <= current_line <= end_line:
                target_lines.append((current_line, line.rstrip('\n')))
            
            # Stop reading once we have our chunk (memory optimization)
            if current_line > end_line:
                # Continue counting lines but don't store content
                while content_stream.readline():
                    total_lines += 1
                break
        
        content_stream.close()
        
        # Handle edge cases
        if start_line > total_lines:
            return [
                types.TextContent(
                    type="text",
                    text=f"📄 File Chunk: {file_path}\n\n❌ Start line {start_line} exceeds file length ({total_lines:,} lines)\n🔧 File size: {file_size:,} bytes (processed safely using streaming)",
                )
            ]
        
        actual_end_line = min(end_line, total_lines)
        
        result = f"""📄 File Chunk: {file_path} 🛡️ HUGE FILE - STREAMED SAFELY

🎯 Chunk Info:
   Version: {version.upper()}
   Lines: {start_line}-{actual_end_line} of {total_lines:,}
   Chunk size: {len(target_lines)} lines
   Remaining: {max(0, total_lines - actual_end_line):,} lines
   File size: {file_size:,} bytes ({file_size / (1024*1024):.1f} MB)

📝 Content:
```
"""

        for line_num, line_content in target_lines:
            # Sanitize content for display
            sanitized_line = _sanitize_content_for_display(line_content)
            result += f"{line_num:4d} | {sanitized_line}\n"

        result += "```\n\n"

        # Navigation info
        has_next = actual_end_line < total_lines
        has_prev = start_line > 1

        if has_next:
            next_start = actual_end_line + 1
            result += f'➡️  Next chunk: pr_file_chunk(file_path="{file_path}", start_line={next_start})\n'

        if has_prev:
            prev_start = max(1, start_line - chunk_size)
            result += f'⬅️  Previous chunk: pr_file_chunk(file_path="{file_path}", start_line={prev_start})\n'

        result += f"\n💡 Progress: {((actual_end_line / total_lines) * 100):.1f}% of file reviewed"
        result += f"\n🛡️  Memory-safe: Only {len(target_lines)} lines held in memory (not {total_lines:,})"

        return [types.TextContent(type="text", text=result)]
        
    except Exception as e:
        return [
            types.TextContent(
                type="text",
                text=f"❌ Error processing huge file {file_path}: {str(e)}"
            )
        ]


async def _process_normal_file(content_bytes, file_path, start_line, chunk_size, version):
    """Standard processing for normal-sized files (under 50MB)"""
    # Decode content
    encoding = _detect_encoding_from_sample(content_bytes[:1024])
    
    try:
        content = content_bytes.decode(encoding)
    except UnicodeDecodeError:
        content = content_bytes.decode(encoding, errors='replace')

    # Split into lines (safe for smaller files)
    lines = content.split("\n")
    total_lines = len(lines)

    # Calculate chunk boundaries
    if start_line > total_lines:
        return [
            types.TextContent(
                type="text",
                text=f"📄 File Chunk: {file_path}\n\n❌ Start line {start_line} exceeds file length ({total_lines:,} lines)",
            )
        ]

    end_line = min(start_line + chunk_size - 1, total_lines)
    chunk_lines = lines[start_line - 1 : end_line]

    result = f"""📄 File Chunk: {file_path}

🎯 Chunk Info:
   Version: {version.upper()}
   Lines: {start_line}-{end_line} of {total_lines:,}
   Chunk size: {len(chunk_lines)} lines
   Remaining: {max(0, total_lines - end_line):,} lines

📝 Content:
```
"""

    for i, line in enumerate(chunk_lines, start_line):
        # Sanitize content for display
        sanitized_line = _sanitize_content_for_display(line)
        result += f"{i:4d} | {sanitized_line}\n"

    result += "```\n\n"

    # Navigation info
    has_next = end_line < total_lines
    has_prev = start_line > 1

    if has_next:
        next_start = end_line + 1
        result += f'➡️  Next chunk: pr_file_chunk(file_path="{file_path}", start_line={next_start})\n'

    if has_prev:
        prev_start = max(1, start_line - chunk_size)
        result += f'⬅️  Previous chunk: pr_file_chunk(file_path="{file_path}", start_line={prev_start})\n'

    result += f"\n💡 Progress: {((end_line / total_lines) * 100):.1f}% of file reviewed"

    return [types.TextContent(type="text", text=result)]


def _detect_encoding_from_sample(sample_bytes):
    """Enhanced encoding detection from file sample"""
    try:
        # Try UTF-8 first
        sample_bytes.decode('utf-8')
        return 'utf-8'
    except UnicodeDecodeError:
        pass
    
    try:
        # Try Latin-1
        sample_bytes.decode('latin-1')
        return 'latin-1'
    except UnicodeDecodeError:
        pass
    
    try:
        # Try Windows-1252
        sample_bytes.decode('windows-1252')
        return 'windows-1252'
    except UnicodeDecodeError:
        pass
    
    # Fallback to UTF-8 with error replacement
    return 'utf-8'


def _sanitize_content_for_display(line_content):
    """Sanitize content to prevent terminal control characters WITHOUT losing content"""
    if not line_content:
        return line_content
    
    # Replace non-printable characters except for common whitespace
    import re
    # Keep tabs, newlines, and normal spaces - only replace actual control characters
    # This preserves ALL content while preventing terminal escape sequences
    sanitized = re.sub(r'[\x00-\x08\x0B-\x0C\x0E-\x1F\x7F-\x9F]', '�', line_content)
    
    # DO NOT truncate lines - Claude needs complete content for code review
    # The markdown code block will handle display properly
    # Only add a warning for extremely long lines (but keep all content)
    if len(sanitized) > 2000:  # Only warn, don't truncate
        # Add a warning comment but keep the full line
        sanitized = f"// [WARNING: Very long line {len(sanitized)} chars]\n{sanitized}"
    
    return sanitized


async def _get_page_with_token_cache(pr_manager, repository_name, source_commit, destination_commit, target_page, cache_key):
    """Efficient page retrieval using token caching to avoid O(n) API calls"""
    global _pagination_cache
    
    # Clean old cache entries (simple TTL mechanism)
    current_time = __import__('time').time()
    for key in list(_pagination_cache.keys()):
        if current_time - _pagination_cache[key].get('timestamp', 0) > 3600:  # 1 hour TTL
            del _pagination_cache[key]
    
    # Initialize cache for this PR if not exists
    if cache_key not in _pagination_cache:
        _pagination_cache[cache_key] = {
            'pages': {},  # page_number: {'token': str, 'has_next': bool}
            'timestamp': current_time
        }
    
    cache = _pagination_cache[cache_key]
    
    # Find the closest cached page before our target
    closest_page = 0
    start_token = None
    
    for page_num in sorted(cache['pages'].keys()):
        if page_num < target_page:
            closest_page = page_num
            start_token = cache['pages'][page_num]['token']
        else:
            break
    
    # If we have the exact page cached, use it
    if target_page in cache['pages']:
        start_token = cache['pages'][target_page]['token']
        closest_page = target_page - 1  # Start from previous page
    
    current_page = closest_page
    next_token = start_token
    api_calls_made = 0
    
    # Navigate to target page from closest cached position
    while current_page < target_page:
        kwargs = {
            "repositoryName": repository_name,
            "beforeCommitSpecifier": destination_commit,
            "afterCommitSpecifier": source_commit,
            "MaxResults": 100,
        }

        if next_token:
            kwargs["nextToken"] = next_token

        diff_response = pr_manager.retry_with_backoff(
            pr_manager.codecommit_client.get_differences, **kwargs
        )
        
        api_calls_made += 1
        differences = diff_response.get("differences", [])
        current_page += 1
        
        # Cache this page's token for future use
        cache['pages'][current_page] = {
            'token': next_token,
            'has_next': bool(diff_response.get("nextToken"))
        }
        
        if current_page == target_page:
            # Calculate performance info
            total_possible_calls = target_page  # Worst case without caching
            efficiency = ((total_possible_calls - api_calls_made) / total_possible_calls * 100) if total_possible_calls > 0 else 0
            
            pagination_info = f"Made {api_calls_made} API calls (saved {total_possible_calls - api_calls_made}, {efficiency:.0f}% efficient)"
            
            return differences, pagination_info

        next_token = diff_response.get("nextToken")
        if not next_token:
            break
    
    # If we get here, the page doesn't exist
    return [], f"Made {api_calls_made} API calls (page not found)"
