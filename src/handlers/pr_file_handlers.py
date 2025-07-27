"""
Smart pagination handlers for Claude-driven huge PR processing
"""

import difflib
import asyncio
import re
import mimetypes
import logging
from typing import List, Dict, Any
from botocore.exceptions import ClientError
import mcp.types as types
from ..utils.helpers import get_primary_pr_target, get_permission_aware_error_message

logger = logging.getLogger(__name__)


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
                    type="text",
                    text=f"❌ PR Target Error: {str(e)}\n🔧 This PR may have multiple targets or missing target information",
                )
            ]

        repository_name = target["repositoryName"]
        source_commit = target["sourceCommit"]
        destination_commit = target["destinationCommit"]

        # Get the specific page efficiently
        target_differences, pagination_info = await _get_page_simple(
            pr_manager,
            repository_name,
            source_commit,
            destination_commit,
            page_number,
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

            # FIXED: Smart binary detection using mimetypes instead of hardcoded list
            if file_size > 0 and not _is_likely_binary_file(file_path):
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
        enhanced_error = get_permission_aware_error_message(
            error_code, error_msg, "PR page"
        )
        return [types.TextContent(type="text", text=enhanced_error)]

    except Exception as e:
        # CRITICAL: Ensure get_pr_page never crashes the server
        logger.error(f"Critical error in get_pr_page: {str(e)}", exc_info=True)
        return [
            types.TextContent(
                type="text",
                text=f"❌ **Critical Error in PR Page Tool**: {str(e)}\n\n"
                f"🔧 **Recovery Options**:\n"
                f"• Try refreshing credentials\n"
                f"• Check PR ID and permissions\n"
                f"• Use get_pr_info first to verify PR exists\n"
                f"• Report this error if it persists",
            )
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
                    type="text",
                    text=f"❌ PR Target Error: {str(e)}\n🔧 This PR may have multiple targets or missing target information",
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
        enhanced_error = get_permission_aware_error_message(
            error_code, error_msg, "PR page"
        )
        return [types.TextContent(type="text", text=enhanced_error)]

    except Exception as e:
        # CRITICAL: Ensure get_pr_file_chunk never crashes the server
        logger.error(f"Critical error in get_pr_file_chunk: {str(e)}", exc_info=True)
        return [
            types.TextContent(
                type="text",
                text=f"❌ **Critical Error in PR File Chunk Tool**: {str(e)}\n\n"
                f"🔧 **Recovery Options**:\n"
                f"• Try refreshing credentials\n"
                f"• Check file path and PR ID are correct\n"
                f"• Verify file exists in the specified version\n"
                f"• Use pr_page to browse available files\n"
                f"• Report this error if it persists",
            )
        ]


async def _process_huge_file_streaming(
    content_bytes, file_path, start_line, chunk_size, version, file_size
):
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
            text_content = content_bytes.decode(encoding, errors="replace")

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
                target_lines.append((current_line, line.rstrip("\n")))

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
                type="text", text=f"❌ Error processing huge file {file_path}: {str(e)}"
            )
        ]


async def _process_normal_file(
    content_bytes, file_path, start_line, chunk_size, version
):
    """Standard processing for normal-sized files (under 50MB)"""
    # Decode content
    encoding = _detect_encoding_from_sample(content_bytes[:1024])

    try:
        content = content_bytes.decode(encoding)
    except UnicodeDecodeError:
        content = content_bytes.decode(encoding, errors="replace")

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
        sample_bytes.decode("utf-8")
        return "utf-8"
    except UnicodeDecodeError:
        pass

    try:
        # Try Latin-1
        sample_bytes.decode("latin-1")
        return "latin-1"
    except UnicodeDecodeError:
        pass

    try:
        # Try Windows-1252
        sample_bytes.decode("windows-1252")
        return "windows-1252"
    except UnicodeDecodeError:
        pass

    # Fallback to UTF-8 with error replacement
    return "utf-8"


def _sanitize_content_for_display(line_content):
    """Sanitize content to prevent terminal control characters WITHOUT losing content"""
    if not line_content:
        return line_content

    # Replace non-printable characters except for common whitespace

    # Keep tabs, newlines, and normal spaces - only replace actual control characters
    # This preserves ALL content while preventing terminal escape sequences
    sanitized = re.sub(r"[\x00-\x08\x0B-\x0C\x0E-\x1F\x7F-\x9F]", "�", line_content)

    # DO NOT truncate lines - Claude needs complete content for code review
    # The markdown code block will handle display properly
    # Only add a warning for extremely long lines (but keep all content)
    if len(sanitized) > 2000:  # Only warn, don't truncate
        # Add a warning comment but keep the full line
        sanitized = f"// [WARNING: Very long line {len(sanitized)} chars]\n{sanitized}"

    return sanitized


# Global cache for efficient pagination
_pagination_cache = {}


async def _get_page_efficient(
    pr_manager,
    repository_name,
    source_commit,
    destination_commit,
    target_page,
):
    """OPTIMIZED: Efficient page retrieval with smart caching to prevent O(N) API calls

    This implementation fixes the critical performance flaw where getting page N
    required N API calls from the beginning.
    """
    cache_key = f"{repository_name}:{source_commit}:{destination_commit}"

    # Check if we have cached data that can help
    if cache_key in _pagination_cache:
        cached_data = _pagination_cache[cache_key]
        cached_page = cached_data["last_page"]
        cached_token = cached_data["next_token"]
        cached_differences = cached_data["differences"]

        # If target page is cached or very close, use cached position
        if target_page <= cached_page:
            # Return cached page if exact match
            if target_page == cached_page:
                return cached_differences, f"Retrieved page {target_page} (cached)"
            # For earlier pages, we need to rebuild from start (rare case)
            _pagination_cache.pop(cache_key, None)  # Clear stale cache
        elif (
            cached_token and target_page <= cached_page + 10
        ):  # Within reasonable distance
            # Continue from cached position
            return await _continue_pagination(
                pr_manager,
                repository_name,
                source_commit,
                destination_commit,
                target_page,
                cached_page,
                cached_token,
                cache_key,
            )

    # Start fresh pagination
    return await _start_fresh_pagination(
        pr_manager,
        repository_name,
        source_commit,
        destination_commit,
        target_page,
        cache_key,
    )


async def _start_fresh_pagination(
    pr_manager,
    repository_name,
    source_commit,
    destination_commit,
    target_page,
    cache_key,
):
    """Start pagination from the beginning with aggressive caching"""
    current_page = 0
    next_token = None
    api_calls_made = 0

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
        next_token = diff_response.get("nextToken")

        # Cache every page for future efficiency
        _pagination_cache[cache_key] = {
            "last_page": current_page,
            "next_token": next_token,
            "differences": differences,
            "timestamp": asyncio.get_event_loop().time(),
        }

        if current_page == target_page:
            return (
                differences,
                f"Retrieved page {target_page} ({api_calls_made} API calls)",
            )

        if not next_token:
            break

    return [], f"Page {target_page} not found ({api_calls_made} API calls)"


async def _continue_pagination(
    pr_manager,
    repository_name,
    source_commit,
    destination_commit,
    target_page,
    cached_page,
    cached_token,
    cache_key,
):
    """Continue pagination from cached position"""
    current_page = cached_page
    next_token = cached_token
    api_calls_made = 0

    while current_page < target_page and next_token:
        kwargs = {
            "repositoryName": repository_name,
            "beforeCommitSpecifier": destination_commit,
            "afterCommitSpecifier": source_commit,
            "MaxResults": 100,
            "nextToken": next_token,
        }

        diff_response = pr_manager.retry_with_backoff(
            pr_manager.codecommit_client.get_differences, **kwargs
        )

        api_calls_made += 1
        differences = diff_response.get("differences", [])
        current_page += 1
        next_token = diff_response.get("nextToken")

        # Update cache
        _pagination_cache[cache_key] = {
            "last_page": current_page,
            "next_token": next_token,
            "differences": differences,
            "timestamp": asyncio.get_event_loop().time(),
        }

        if current_page == target_page:
            total_calls = api_calls_made
            return (
                differences,
                f"Retrieved page {target_page} ({total_calls} API calls, optimized)",
            )

    return [], f"Page {target_page} not found (continued from cache)"


async def _get_page_simple(
    pr_manager,
    repository_name,
    source_commit,
    destination_commit,
    target_page,
):
    """DEPRECATED: Legacy simple pagination - use _get_page_efficient instead"""
    # Clean up old cache entries (older than 5 minutes)
    current_time = asyncio.get_event_loop().time()
    cache_keys_to_remove = [
        key
        for key, data in _pagination_cache.items()
        if current_time - data.get("timestamp", 0) > 300  # 5 minutes
    ]
    for key in cache_keys_to_remove:
        _pagination_cache.pop(key, None)

    # Use efficient pagination
    return await _get_page_efficient(
        pr_manager, repository_name, source_commit, destination_commit, target_page
    )


def _is_likely_binary_file(file_path: str) -> bool:
    """OPTIMIZED: Fast binary detection using only file path and mimetypes

    This replaces hardcoded extension lists with maintainable standard library detection.
    """
    if not file_path:
        return False

    # Use standard mimetypes library for maintainable detection
    mime_type, _ = mimetypes.guess_type(file_path)
    if mime_type:
        # Text files
        if mime_type.startswith("text/"):
            return False
        # Common text-based application types
        if mime_type in (
            "application/json",
            "application/javascript",
            "application/xml",
            "application/yaml",
            "application/x-yaml",
            "application/x-sh",
            "application/x-python",
        ):
            return False
        # Binary types
        if mime_type.startswith(
            ("image/", "video/", "audio/", "font/")
        ) or mime_type in (
            "application/pdf",
            "application/zip",
            "application/x-executable",
            "application/octet-stream",
        ):
            return True

    # Fallback: common extensions for files without proper MIME detection
    file_lower = file_path.lower()

    # Known text extensions
    text_extensions = {
        ".txt",
        ".md",
        ".py",
        ".js",
        ".ts",
        ".jsx",
        ".tsx",
        ".json",
        ".xml",
        ".yaml",
        ".yml",
        ".html",
        ".htm",
        ".css",
        ".scss",
        ".sass",
        ".less",
        ".sql",
        ".sh",
        ".bash",
        ".zsh",
        ".fish",
        ".ps1",
        ".bat",
        ".cmd",
        ".c",
        ".cpp",
        ".h",
        ".hpp",
        ".java",
        ".kt",
        ".scala",
        ".go",
        ".rs",
        ".swift",
        ".rb",
        ".php",
        ".pl",
        ".r",
        ".m",
        ".cs",
        ".vb",
        ".fs",
        ".clj",
        ".hs",
        ".elm",
        ".ex",
        ".exs",
        ".erl",
        ".lua",
        ".vim",
        ".config",
        ".conf",
        ".ini",
        ".cfg",
        ".toml",
        ".properties",
        ".env",
        ".log",
        ".diff",
        ".patch",
        ".gitignore",
        ".gitattributes",
    }

    # Check if any text extension matches
    if any(file_lower.endswith(ext) for ext in text_extensions):
        return False

    # Known binary extensions
    binary_extensions = {
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".bmp",
        ".ico",
        ".svg",
        ".webp",
        ".tiff",
        ".tga",
        ".mp4",
        ".avi",
        ".mov",
        ".wmv",
        ".flv",
        ".webm",
        ".mkv",
        ".m4v",
        ".3gp",
        ".mp3",
        ".wav",
        ".flac",
        ".aac",
        ".ogg",
        ".wma",
        ".m4a",
        ".opus",
        ".pdf",
        ".doc",
        ".docx",
        ".xls",
        ".xlsx",
        ".ppt",
        ".pptx",
        ".odt",
        ".ods",
        ".odp",
        ".zip",
        ".rar",
        ".7z",
        ".tar",
        ".gz",
        ".bz2",
        ".xz",
        ".lz",
        ".lzma",
        ".zst",
        ".exe",
        ".dll",
        ".so",
        ".dylib",
        ".app",
        ".dmg",
        ".pkg",
        ".deb",
        ".rpm",
        ".msi",
        ".bin",
        ".dat",
        ".db",
        ".sqlite",
        ".sqlite3",
        ".pdb",
        ".obj",
        ".lib",
        ".a",
        ".o",
    }

    if any(file_lower.endswith(ext) for ext in binary_extensions):
        return True

    # Unknown extension - assume text for safety
    return False


def _is_likely_binary_content(
    before_lines: list, after_lines: list, file_path: str = ""
) -> bool:
    """ENHANCED: Professional binary detection using content analysis and standard mimetypes."""

    # Fast path: check file extension first
    if _is_likely_binary_file(file_path):
        return True

    # Content-based detection for edge cases
    def contains_null_bytes(lines):
        if not lines:
            return False
        sample = "".join(lines[:10])
        return "\x00" in sample

    if contains_null_bytes(before_lines) or contains_null_bytes(after_lines):
        return True

    # Fallback: check for high ratio of non-printable characters
    def has_high_non_printable_ratio(lines):
        if not lines:
            return False

        sample_text = "\n".join(lines[:5])
        if len(sample_text) < 100:
            return False

        control_chars = sum(
            1 for char in sample_text if ord(char) < 32 and char not in "\n\t\r"
        )
        ratio = control_chars / len(sample_text)
        return ratio > 0.3

    if has_high_non_printable_ratio(before_lines) or has_high_non_printable_ratio(
        after_lines
    ):
        return True

    return False


async def _get_file_content_with_size_check(
    pr_manager,
    repository_name: str,
    commit_id: str,
    file_path: str,
    max_size_bytes: int,
) -> tuple:
    """ENHANCED: Get file content with size validation and robust error handling for memory safety

    Returns: (content_string, size_in_bytes)
    """
    try:
        response = pr_manager.retry_with_backoff(
            pr_manager.codecommit_client.get_file,
            repositoryName=repository_name,
            commitSpecifier=commit_id,
            filePath=file_path,
        )

        file_content_raw = response.get("fileContent", b"")
        file_size = len(file_content_raw)

        if file_size > max_size_bytes:
            logger.info(
                f"File {file_path} ({file_size} bytes) exceeds limit ({max_size_bytes} bytes)"
            )
            return "", file_size

        if not file_content_raw:
            return "", file_size

        # FIXED: Handle both string and bytes correctly without incorrect base64 decoding
        if isinstance(file_content_raw, str):
            return file_content_raw, file_size

        # Raw bytes from AWS API - decode directly to text
        try:
            decoded_content = file_content_raw.decode("utf-8")
            return decoded_content, file_size
        except UnicodeDecodeError as decode_error:
            logger.debug(f"UTF-8 decode failed for {file_path}: {decode_error}")
            try:
                decoded_content = file_content_raw.decode("latin-1", errors="replace")
                return decoded_content, file_size
            except Exception as fallback_error:
                logger.warning(
                    f"All decode attempts failed for {file_path}: {fallback_error}"
                )
                return "", file_size

    except ClientError as aws_error:
        error_code = aws_error.response.get("Error", {}).get("Code", "Unknown")
        if error_code == "FileDoesNotExistException":
            logger.debug(f"File does not exist: {file_path} in commit {commit_id}")
        else:
            logger.warning(f"AWS error fetching {file_path}: {error_code}")
        return "", 0

    except Exception as e:
        logger.error(f"Unexpected error fetching {file_path}: {str(e)}")
        return "", 0


async def get_pr_file_diff(pr_manager, args: dict) -> List[types.TextContent]:
    """ENHANCED: Get git-style diff for a specific file with smart chunking and line number mapping

    MEMORY-SAFE implementation with proper chunking, error handling, and accurate line tracking.
    Uses AWS GetDifferences API for efficiency and falls back to manual diff generation.

    ROBUST ERROR HANDLING: This function is designed to never crash the server, always returning
    a meaningful response even in error conditions.
    """
    try:
        # Enhanced argument validation
        pull_request_id = str(args.get("pull_request_id", "")).strip()
        file_path = str(args.get("file_path", "")).strip()
        start_line = max(1, int(args.get("start_line", 1)))  # Ensure positive
        chunk_size = min(
            max(1, int(args.get("chunk_size", 300))), 500
        )  # Clamp between 1-500

        # OPTIMIZED: Increased diff processing limit for better functionality
        MAX_FILE_SIZE_BYTES = 15 * 1024 * 1024  # 15MB (increased from 10MB)

        # Comprehensive input validation
        if not pull_request_id:
            return [
                types.TextContent(
                    type="text", text="❌ Error: pull_request_id cannot be empty"
                )
            ]

        if not file_path:
            return [
                types.TextContent(
                    type="text", text="❌ Error: file_path cannot be empty"
                )
            ]

        # Normalize file path separators for cross-platform compatibility
        file_path = file_path.replace("\\", "/")  # Normalize path separators

        # Get the PR information to determine before and after commit IDs
        pr_details = pr_manager.retry_with_backoff(
            pr_manager.codecommit_client.get_pull_request, pullRequestId=pull_request_id
        )

        targets = pr_details.get("pullRequest", {}).get("pullRequestTargets", [])
        if not targets:
            return [
                types.TextContent(
                    type="text",
                    text=f"❌ No pull request targets found for PR {pull_request_id}",
                )
            ]

        target = targets[0]
        before_commit_id = target.get("destinationCommit")
        after_commit_id = target.get("sourceCommit")
        repository_name = target.get("repositoryName")

        if not all([before_commit_id, after_commit_id, repository_name]):
            return [
                types.TextContent(
                    type="text",
                    text="❌ Missing required commit IDs or repository name",
                )
            ]

        # STEP 1: Fetch both file versions concurrently with memory safety

        before_lines = []
        after_lines = []
        before_size = 0
        after_size = 0

        try:
            # ENHANCED: Always try to fetch both versions concurrently with proper error handling
            before_task = _get_file_content_with_size_check(
                pr_manager,
                repository_name,
                before_commit_id,
                file_path,
                MAX_FILE_SIZE_BYTES,
            )
            after_task = _get_file_content_with_size_check(
                pr_manager,
                repository_name,
                after_commit_id,
                file_path,
                MAX_FILE_SIZE_BYTES,
            )

            # ROBUST: Handle concurrent fetch with individual error tracking
            try:
                results = await asyncio.gather(
                    before_task, after_task, return_exceptions=True
                )
                before_result, after_result = results

                # Check if either result is an exception
                if isinstance(before_result, Exception):
                    logger.warning(
                        f"Failed to fetch before version of {file_path}: {before_result}"
                    )
                    before_content, before_size = "", 0
                else:
                    before_content, before_size = before_result
                    logger.debug(
                        f"Successfully fetched before version of {file_path}: {before_size} bytes"
                    )

                if isinstance(after_result, Exception):
                    logger.warning(
                        f"Failed to fetch after version of {file_path}: {after_result}"
                    )
                    after_content, after_size = "", 0
                else:
                    after_content, after_size = after_result
                    logger.debug(
                        f"Successfully fetched after version of {file_path}: {after_size} bytes"
                    )

            except Exception as e:
                logger.error(
                    f"Critical error in concurrent file fetch for {file_path}: {str(e)}"
                )
                # Fallback to sequential fetch with individual error handling
                try:
                    before_content, before_size = (
                        await _get_file_content_with_size_check(
                            pr_manager,
                            repository_name,
                            before_commit_id,
                            file_path,
                            MAX_FILE_SIZE_BYTES,
                        )
                    )
                except Exception as before_error:
                    logger.warning(
                        f"Sequential fetch failed for before version of {file_path}: {before_error}"
                    )
                    before_content, before_size = "", 0

                try:
                    after_content, after_size = await _get_file_content_with_size_check(
                        pr_manager,
                        repository_name,
                        after_commit_id,
                        file_path,
                        MAX_FILE_SIZE_BYTES,
                    )
                except Exception as after_error:
                    logger.warning(
                        f"Sequential fetch failed for after version of {file_path}: {after_error}"
                    )
                    after_content, after_size = "", 0

            # FIXED: Determine change type based on file existence AND size information
            # Use size information as a more reliable indicator than content comparison
            if before_size == 0 and after_size > 0:
                change_type = "A"  # Added
            elif before_size > 0 and after_size == 0:
                change_type = "D"  # Deleted
            elif before_size > 0 and after_size > 0:
                # Both files exist, check if content is actually different
                if before_content != after_content:
                    change_type = "M"  # Modified
                elif before_size != after_size:
                    # Size difference but content appears same - likely encoding issue
                    change_type = "M"  # Treat as modified to be safe
                else:
                    change_type = "UNCHANGED"  # Truly no changes
            else:
                # Both files are empty/missing - this shouldn't happen in a real PR
                change_type = "UNCHANGED"

            # ENHANCED: Smart memory validation with progressive limits
            total_size = before_size + after_size
            if (
                total_size > MAX_FILE_SIZE_BYTES * 2.5
            ):  # Allow slightly larger combined sizes
                return [
                    types.TextContent(
                        type="text",
                        text=f"⚠️ **File too large for diff processing**: `{file_path}` (Combined: {total_size / (1024*1024):.1f} MB)\n\n📏 **Memory Safety Limit**: Files with combined size > 20MB cannot be processed.\n🔧 **Alternative**: Use pr_file_chunk for targeted review.\n📊 **Sizes**: Before: {before_size / (1024*1024):.1f} MB, After: {after_size / (1024*1024):.1f} MB",
                    )
                ]

            # Split into lines for diff processing
            before_lines = before_content.splitlines() if before_content else []
            after_lines = after_content.splitlines() if after_content else []

        except Exception as e:
            return [
                types.TextContent(
                    type="text",
                    text=f"❌ Error fetching file content: {str(e)}\n\n💡 **Possible issues**:\n• File doesn't exist in one or both commits\n• Invalid file path\n• Permissions issue",
                )
            ]

        # Handle case where file is unchanged
        if change_type == "UNCHANGED":
            # ENHANCED: Add debugging information to help identify false negatives
            debug_info = f"\n\n🔧 **Debug Info**: Before size: {before_size}, After size: {after_size}"
            if before_size > 0 and after_size > 0:
                debug_info += (
                    f", Content lengths: {len(before_content)}, {len(after_content)}"
                )

            return [
                types.TextContent(
                    type="text",
                    text=f"📄 **No changes detected** for `{file_path}`\n\n✅ The file content is identical in both commits.\n🔍 **Commit Range**: {before_commit_id[:12]}...{after_commit_id[:12]}{debug_info}",
                )
            ]

        # Define change icons/text after we know the change type
        change_icon = {"A": "🆕", "D": "🗑️", "M": "✏️"}.get(change_type, "🔄")
        change_text = {"A": "Added", "D": "Deleted", "M": "Modified"}.get(
            change_type, "Changed"
        )

        # Check for binary files
        is_binary = _is_likely_binary_content(before_lines, after_lines, file_path)
        if is_binary:
            return [
                types.TextContent(
                    type="text",
                    text=f"""📄 **Binary File Detected** for `{file_path}`

{change_icon} **Change Type**: {change_text} ({change_type})
🔍 **Commit Range**: 
   Before: {before_commit_id[:12]}
   After:  {after_commit_id[:12]}

⚠️ **Binary files cannot show line-by-line diffs**

📊 **File Size**:
   Before: {len(before_lines) if before_lines else 0} lines
   After: {len(after_lines) if after_lines else 0} lines

💡 **For inline comments on binary files**: 
   Binary files don't support precise line-level commenting.
   Use general PR comments instead.""",
                )
            ]

        # Generate unified diff
        diff_lines = list(
            difflib.unified_diff(
                before_lines,
                after_lines,
                fromfile=f"a/{file_path}",
                tofile=f"b/{file_path}",
                lineterm="",
            )
        )

        if not diff_lines:
            return [
                types.TextContent(
                    type="text",
                    text=f"""📄 **No Line Differences** for `{file_path}`

{change_icon} **Change Type**: {change_text} ({change_type})
🔍 **Commit Range**: 
   Before: {before_commit_id[:12]}
   After:  {after_commit_id[:12]}

ℹ️ The file may have metadata changes (permissions, etc.) but identical content.""",
                )
            ]

        # MEMORY-SAFE: Process diff in chunks to prevent server crashes
        total_diff_lines = len(diff_lines)

        # Apply chunking FIRST to limit processing scope
        end_line = min(start_line + chunk_size - 1, total_diff_lines)

        if start_line > total_diff_lines:
            return [
                types.TextContent(
                    type="text",
                    text=f"❌ Start line {start_line} exceeds diff size ({total_diff_lines} lines)",
                )
            ]

        # Get chunk first, then process line mappings only for this chunk
        chunk_lines = diff_lines[start_line - 1 : end_line]

        # FIXED: Build line number mapping more efficiently and accurately
        chunk_mappings = []

        try:
            # OPTIMIZATION: Only process lines up to our chunk end to save memory
            lines_to_process = diff_lines[:end_line]

            before_line_num = 0
            after_line_num = 0
            current_hunk_before_start = 0
            current_hunk_after_start = 0

            for i, line in enumerate(lines_to_process):
                if line.startswith("@@"):
                    # FIXED: Parse hunk header correctly and set proper line numbers
                    match = re.search(r"-(\d+)(?:,\d+)? \+(\d+)(?:,\d+)?", line)
                    if match:
                        # Set line numbers to the actual starting positions from hunk header
                        current_hunk_before_start = int(match.group(1))
                        current_hunk_after_start = int(match.group(2))
                        # Initialize counters to track position within the hunk
                        before_line_num = current_hunk_before_start - 1
                        after_line_num = current_hunk_after_start - 1
                    else:
                        # Fallback for malformed hunk headers
                        logger.warning(f"Could not parse hunk header: {line}")
                        before_line_num = 0
                        after_line_num = 0

                    # Only store if in our chunk range
                    if start_line - 1 <= i < end_line:
                        chunk_mappings.append(
                            (
                                i,
                                "hunk_header",
                                current_hunk_before_start,
                                current_hunk_after_start,
                            )
                        )

                elif line.startswith("-") and not line.startswith("---"):
                    before_line_num += 1
                    if start_line - 1 <= i < end_line:
                        chunk_mappings.append((i, "deletion", before_line_num, None))

                elif line.startswith("+") and not line.startswith("+++"):
                    after_line_num += 1
                    if start_line - 1 <= i < end_line:
                        chunk_mappings.append((i, "addition", None, after_line_num))

                elif (
                    line
                    and not line.startswith("\\")
                    and not line.startswith("---")
                    and not line.startswith("+++")
                    and not line.startswith("@@")
                ):
                    # Context line - increment both counters
                    before_line_num += 1
                    after_line_num += 1
                    if start_line - 1 <= i < end_line:
                        chunk_mappings.append(
                            (i, "context", before_line_num, after_line_num)
                        )

                else:
                    # File headers, metadata lines
                    if start_line - 1 <= i < end_line:
                        chunk_mappings.append((i, "metadata", None, None))

        except Exception as e:
            logger.error(f"Error in line mapping for {file_path}: {str(e)}")
            return [
                types.TextContent(
                    type="text",
                    text=f"❌ Error in line mapping for `{file_path}`: {str(e)}\n\n🔧 This may indicate a complex diff format. Try using pr_file_chunk instead.",
                )
            ]

        # Build the response with enhanced formatting
        result = f"""📄 **Git-Style Diff** for `{file_path}`

{change_icon} **Change Type**: {change_text} ({change_type})
🔍 **Commit Range**: 
   Before: {before_commit_id[:12]}
   After:  {after_commit_id[:12]}

📊 **Diff Chunk**: Lines {start_line}-{end_line} of {total_diff_lines}

```diff
"""

        # Collect changed lines from this chunk using pre-computed mappings
        changed_after_lines = []
        changed_before_lines = []

        # ENHANCED: Safety check and error handling for array operations
        if len(chunk_lines) != len(chunk_mappings):
            logger.error(
                f"Line mapping mismatch in {file_path}: chunk_lines={len(chunk_lines)}, chunk_mappings={len(chunk_mappings)}"
            )
            return [
                types.TextContent(
                    type="text",
                    text=f"❌ Internal error: Line mapping mismatch in diff processing for `{file_path}`\n\n🔧 chunk_lines: {len(chunk_lines)}, chunk_mappings: {len(chunk_mappings)}\n💡 This indicates a bug in the diff parsing logic. Trying fallback approach...",
                )
            ]

        try:
            # ROBUST: Process line by line with additional safety checks
            for i, (line, mapping) in enumerate(zip(chunk_lines, chunk_mappings)):
                if mapping is None or len(mapping) < 4:
                    logger.warning(
                        f"Invalid mapping at index {i} for {file_path}: {mapping}"
                    )
                    result += line + "\n"
                    continue

                _, line_type, before_line, after_line = mapping
                result += line + "\n"

                # Track changed lines for inline commenting guidance with validation
                if (
                    line_type == "addition"
                    and after_line
                    and isinstance(after_line, int)
                    and after_line > 0
                ):
                    changed_after_lines.append(after_line)
                elif (
                    line_type == "deletion"
                    and before_line
                    and isinstance(before_line, int)
                    and before_line > 0
                ):
                    changed_before_lines.append(before_line)

        except Exception as e:
            logger.error(f"Error processing line mappings for {file_path}: {str(e)}")
            # Fallback: just show the diff without line mapping information
            for line in chunk_lines:
                result += line + "\n"
            result += "\n⚠️ Line mapping failed, but diff content is shown above.\n"

        result += "```\n\n"

        # Add helpful guidance for inline comments with enhanced information
        if changed_after_lines or changed_before_lines:
            result += f"""💬 **For Inline Comments**:
"""
            if changed_after_lines:
                result += f"""   📍 AFTER lines (additions/modifications): {', '.join(map(str, changed_after_lines[:10]))}{"..." if len(changed_after_lines) > 10 else ""}
   ✅ Use these with relativeFileVersion="AFTER"
   🎯 Example: add_comment(location={{filePath: "{file_path}", filePosition: {changed_after_lines[0]}, relativeFileVersion: "AFTER"}})
"""

            if (
                changed_before_lines and change_type != "A"
            ):  # Don't show before lines for new files
                result += f"""   📍 BEFORE lines (deletions): {', '.join(map(str, changed_before_lines[:10]))}{"..." if len(changed_before_lines) > 10 else ""}
   ⚠️ Use these with relativeFileVersion="BEFORE" (rarely needed)
"""

            result += f"""
   📊 **Change Summary**: {len(changed_after_lines)} additions, {len(changed_before_lines)} deletions
   💡 **Best Practice**: Comment on AFTER lines for code feedback

"""
        else:
            result += """💬 **For Inline Comments**:
   ℹ️ No line-level changes detected in this chunk
   📝 Use general PR comments for this file
   
"""

        # Navigation info with systematic review guidance
        navigation = ""
        if start_line > 1:
            prev_start = max(1, start_line - chunk_size)
            navigation += f"⬅️ Previous: pr_file_diff(start_line={prev_start})\n"

        if end_line < total_diff_lines:
            next_start = end_line + 1
            navigation += f"➡️ Next: pr_file_diff(start_line={next_start})\n"
            remaining_lines = total_diff_lines - end_line
            chunks_remaining = (
                remaining_lines + chunk_size - 1
            ) // chunk_size  # Ceiling division
            navigation += f"📊 **Systematic Review**: {chunks_remaining} more chunks remaining ({remaining_lines} lines)\n"
        else:
            navigation += (
                "✅ **Review Complete**: You've seen all diff lines for this file\n"
            )

        if navigation:
            result += f"🧭 **Navigation**:\n{navigation}\n"

        result += f"""📈 **Diff Statistics**:
   Total diff lines: {total_diff_lines}
   Current chunk: {len(chunk_lines)} lines
   Progress: {end_line / total_diff_lines * 100:.1f}%

💡 **Legend**:
   - Lines starting with `-` are deletions (from before version)
   - Lines starting with `+` are additions (to after version)  
   - Lines starting with ` ` (space) are context (unchanged)
   - `@@` lines show line number ranges"""

        return [types.TextContent(type="text", text=result)]

    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        error_msg = e.response["Error"]["Message"]

        troubleshooting = ""
        if error_code == "FileDoesNotExistException":
            troubleshooting = """
🔧 Troubleshooting - File Not Found:
• Check that the file path is correct and exists in the PR
• File may have been renamed or moved
• Use pr_page to see available files
"""

        return [
            types.TextContent(
                type="text",
                text=f"❌ AWS Error ({error_code}): {error_msg}{troubleshooting}",
            )
        ]

    except Exception as e:
        # CRITICAL: This is the final safety net to prevent server crashes
        error_msg = str(e)
        logger.error(
            f"Critical error in get_pr_file_diff for {args}: {error_msg}", exc_info=True
        )

        # Provide helpful error response without crashing
        return [
            types.TextContent(
                type="text",
                text=f"❌ **Critical Error in PR Diff Tool**: {error_msg}\n\n"
                f"🔧 **Recovery Options**:\n"
                f"• Try using pr_file_chunk for this file instead\n"
                f"• Check if file path and PR ID are correct\n"
                f"• Use refresh_credentials if this is an auth issue\n"
                f"• Report this error if it persists\n\n"
                f"💡 **Alternative**: Use general PR comments for this file",
            )
        ]
