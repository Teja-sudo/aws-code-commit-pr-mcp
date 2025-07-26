"""
Tool definitions for AWS CodeCommit PR MCP Server
"""

from mcp.types import Tool


def get_tools() -> list[Tool]:
    """List all available CodeCommit PR tools"""
    return [
        # AWS Profile Management
        Tool(
            name="current_profile",
            description="Get information about the current AWS profile and session",
            inputSchema={
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
        ),
        Tool(
            name="switch_profile",
            description="Switch to a different AWS profile",
            inputSchema={
                "type": "object",
                "properties": {
                    "profile_name": {
                        "type": "string",
                        "description": "Name of the AWS profile to switch to",
                    },
                    "region": {
                        "type": "string",
                        "description": "AWS region (optional, defaults to current region)",
                    },
                },
                "required": ["profile_name"],
            },
        ),
        Tool(
            name="refresh_credentials",
            description="🔄 Refresh expired or invalid AWS credentials. Use this when you encounter 'No result received', 'ExpiredToken', 'InvalidToken', or any credential-related errors. This resolves AWS session issues without restarting Claude Desktop. Essential for long-running sessions where credentials may expire.",
            inputSchema={
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
        ),
        # PR Creation and Management
        Tool(
            name="create_pr",
            description="Create a new pull request in a CodeCommit repository",
            inputSchema={
                "type": "object",
                "properties": {
                    "repository_name": {
                        "type": "string",
                        "description": "Name of the CodeCommit repository",
                    },
                    "title": {
                        "type": "string",
                        "description": "Title of the pull request",
                    },
                    "description": {
                        "type": "string",
                        "description": "Description of the pull request",
                    },
                    "source_commit": {
                        "type": "string",
                        "description": "Source commit ID or branch name",
                    },
                    "destination_commit": {
                        "type": "string",
                        "description": "Destination commit ID or branch name",
                    },
                    "client_request_token": {
                        "type": "string",
                        "description": "Unique token for idempotency (optional)",
                    },
                },
                "required": [
                    "repository_name",
                    "title",
                    "source_commit",
                    "destination_commit",
                ],
            },
        ),
        Tool(
            name="get_pr_info",
            description="📋 Get comprehensive PR information with optional metadata analysis. Essential first step providing title, description, status, author, branches, and commit IDs needed for comments. Use include_metadata=true for file counts, change distribution, and review strategy guidance. Single tool replaces get_pr + pr_metadata workflow.",
            inputSchema={
                "type": "object",
                "properties": {
                    "pull_request_id": {
                        "type": "string",
                        "description": "The pull request ID (numeric string)",
                    },
                    "include_metadata": {
                        "type": "boolean",
                        "description": "Include file analysis metadata (total files, pages, change distribution). Use true for PRs needing review planning.",
                        "default": False,
                    },
                },
                "required": ["pull_request_id"],
            },
        ),
        Tool(
            name="list_prs",
            description="List pull requests for a repository with enhanced pagination support",
            inputSchema={
                "type": "object",
                "properties": {
                    "repository_name": {
                        "type": "string",
                        "description": "Name of the CodeCommit repository",
                    },
                    "author_arn": {
                        "type": "string",
                        "description": "Filter by author ARN (optional)",
                    },
                    "pr_status": {
                        "type": "string",
                        "enum": ["OPEN", "CLOSED"],
                        "description": "Filter by PR status (optional)",
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of results (1-100)",
                        "default": 50,
                    },
                    "next_token": {
                        "type": "string",
                        "description": "Token for pagination (optional)",
                    },
                },
                "required": ["repository_name"],
            },
        ),
        # PR Update tools
        Tool(
            name="update_pr_title",
            description="Update the title of a pull request",
            inputSchema={
                "type": "object",
                "properties": {
                    "pull_request_id": {
                        "type": "string",
                        "description": "ID of the pull request",
                    },
                    "title": {
                        "type": "string",
                        "description": "New title for the pull request",
                    },
                },
                "required": ["pull_request_id", "title"],
            },
        ),
        Tool(
            name="update_pr_desc",
            description="Update the description of a pull request",
            inputSchema={
                "type": "object",
                "properties": {
                    "pull_request_id": {
                        "type": "string",
                        "description": "ID of the pull request",
                    },
                    "description": {
                        "type": "string",
                        "description": "New description for the pull request",
                    },
                },
                "required": ["pull_request_id", "description"],
            },
        ),
        Tool(
            name="update_pr_status",
            description="Update the status of a pull request",
            inputSchema={
                "type": "object",
                "properties": {
                    "pull_request_id": {
                        "type": "string",
                        "description": "ID of the pull request",
                    },
                    "status": {
                        "type": "string",
                        "enum": ["OPEN", "CLOSED"],
                        "description": "New status for the pull request",
                    },
                },
                "required": ["pull_request_id", "status"],
            },
        ),
        # Approval tools
        Tool(
            name="get_pr_approvals",
            description="🎯 Get comprehensive approval information including reviewer states and override status. Shows who approved/revoked, pending reviews, and current override status in one call. Essential for understanding PR approval readiness before merge decisions.",
            inputSchema={
                "type": "object",
                "properties": {
                    "pull_request_id": {
                        "type": "string",
                        "description": "The pull request ID (numeric string)",
                    },
                    "revision_id": {
                        "type": "string",
                        "description": "Specific revision ID (optional, uses latest if not provided)",
                    },
                    "include_override": {
                        "type": "boolean",
                        "description": "Include override status information (default: true)",
                        "default": True,
                    },
                },
                "required": ["pull_request_id"],
            },
        ),
        Tool(
            name="manage_pr_approval",
            description="✅ Unified approval management for all approval actions. Use action='approve/revoke' for standard reviews, action='override/revoke_override' for bypassing approval rules. Requires revision_id from get_pr_info. Single tool for all approval modifications.",
            inputSchema={
                "type": "object",
                "properties": {
                    "pull_request_id": {
                        "type": "string",
                        "description": "The pull request ID (numeric string)",
                    },
                    "revision_id": {
                        "type": "string",
                        "description": "Revision ID from get_pr_info (required for all actions)",
                    },
                    "action": {
                        "type": "string",
                        "enum": ["approve", "revoke", "override", "revoke_override"],
                        "description": "Action to perform: approve/revoke for reviews, override/revoke_override for bypassing rules",
                    },
                },
                "required": ["pull_request_id", "revision_id", "action"],
            },
        ),
        # Comment tools
        Tool(
            name="add_comment",
            description="💬 Post general or inline PR comments. ⚠️ CRITICAL FOR INLINE COMMENTS: filePosition MUST be within actual diff context (changed lines only)! If line has no changes, comment becomes general instead of inline. WORKFLOW: 1) Get commit IDs from get_pr_info, 2) Use pr_file_chunk to see ACTUAL CHANGED LINES (look for +/- markers), 3) Only use line numbers that appear in diff output. Tool includes intelligent fallback with smart aggregation - multiple failed inline comments for same file are automatically combined into single file-level comment.",
            inputSchema={
                "type": "object",
                "properties": {
                    "pull_request_id": {
                        "type": "string",
                        "description": "ID of the pull request",
                    },
                    "repository_name": {
                        "type": "string",
                        "description": "Name of the repository",
                    },
                    "before_commit_id": {
                        "type": "string",
                        "description": "Commit ID before the change",
                    },
                    "after_commit_id": {
                        "type": "string",
                        "description": "Commit ID after the change",
                    },
                    "content": {"type": "string", "description": "Comment content"},
                    "location": {
                        "type": "object",
                        "properties": {
                            "filePath": {
                                "type": "string",
                                "description": "Path to the file",
                            },
                            "filePosition": {
                                "type": "integer",
                                "description": "Position in the file",
                            },
                            "relativeFileVersion": {
                                "type": "string",
                                "enum": ["BEFORE", "AFTER"],
                                "description": "File version",
                            },
                        },
                        "description": "Location for inline comments",
                    },
                    "client_request_token": {
                        "type": "string",
                        "description": "Unique token for idempotency (optional)",
                    },
                },
                "required": [
                    "pull_request_id",
                    "repository_name",
                    "before_commit_id",
                    "after_commit_id",
                    "content",
                ],
            },
        ),
        Tool(
            name="pr_comments",
            description="Get all comments for a pull request with enhanced pagination support",
            inputSchema={
                "type": "object",
                "properties": {
                    "pull_request_id": {
                        "type": "string",
                        "description": "ID of the pull request",
                    },
                    "repository_name": {
                        "type": "string",
                        "description": "Name of the repository (optional)",
                    },
                    "before_commit_id": {
                        "type": "string",
                        "description": "Before commit ID (optional)",
                    },
                    "after_commit_id": {
                        "type": "string",
                        "description": "After commit ID (optional)",
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of results (1-100)",
                        "default": 100,
                    },
                    "next_token": {
                        "type": "string",
                        "description": "Token for pagination (optional)",
                    },
                },
                "required": ["pull_request_id"],
            },
        ),
        Tool(
            name="get_fallback_comment_status",
            description="📊 Check status of pending fallback comment aggregations. Shows which comments are waiting to be aggregated per file, useful for debugging multiple inline comment failures.",
            inputSchema={
                "type": "object",
                "properties": {
                    "pull_request_id": {
                        "type": "string",
                        "description": "PR ID to check (optional, defaults to all PRs)",
                    },
                },
                "additionalProperties": False,
            },
        ),
        Tool(
            name="bulk_add_comments",
            description="🎯 Post multiple inline comments efficiently in one operation. ⚠️ IMPORTANT: AWS CodeCommit has no native bulk API - this simulates batch posting via optimized individual calls with smart aggregation. Each comment must still have valid diff context line numbers. Includes comprehensive progress tracking and statistics.",
            inputSchema={
                "type": "object",
                "properties": {
                    "pull_request_id": {
                        "type": "string",
                        "description": "ID of the pull request",
                    },
                    "repository_name": {
                        "type": "string",
                        "description": "Name of the repository",
                    },
                    "before_commit_id": {
                        "type": "string",
                        "description": "Commit ID before the change",
                    },
                    "after_commit_id": {
                        "type": "string",
                        "description": "Commit ID after the change",
                    },
                    "comments": {
                        "type": "array",
                        "description": "Array of comments to post",
                        "items": {
                            "type": "object",
                            "properties": {
                                "content": {
                                    "type": "string",
                                    "description": "Comment content",
                                },
                                "location": {
                                    "type": "object",
                                    "properties": {
                                        "filePath": {
                                            "type": "string",
                                            "description": "Path to the file",
                                        },
                                        "filePosition": {
                                            "type": "integer",
                                            "description": "Line position (must be in diff context)",
                                        },
                                        "relativeFileVersion": {
                                            "type": "string",
                                            "enum": ["BEFORE", "AFTER"],
                                            "description": "File version",
                                        },
                                    },
                                    "description": "Location for inline comments (optional for general comments)",
                                },
                            },
                            "required": ["content"],
                        },
                    },
                },
                "required": [
                    "pull_request_id",
                    "repository_name", 
                    "before_commit_id",
                    "after_commit_id",
                    "comments",
                ],
            },
        ),
        Tool(
            name="pr_events",
            description="Get events for a pull request with enhanced pagination support",
            inputSchema={
                "type": "object",
                "properties": {
                    "pull_request_id": {
                        "type": "string",
                        "description": "ID of the pull request",
                    },
                    "pull_request_event_type": {
                        "type": "string",
                        "enum": [
                            "PULL_REQUEST_CREATED",
                            "PULL_REQUEST_SOURCE_REFERENCE_UPDATED",
                            "PULL_REQUEST_STATUS_CHANGED",
                            "PULL_REQUEST_MERGE_STATUS_CHANGED",
                            "APPROVAL_RULE_CREATED",
                            "APPROVAL_RULE_UPDATED",
                            "APPROVAL_RULE_DELETED",
                            "APPROVAL_RULE_OVERRIDDEN",
                            "APPROVAL_STATE_CHANGED",
                        ],
                        "description": "Filter by event type (optional)",
                    },
                    "actor_arn": {
                        "type": "string",
                        "description": "Filter by actor ARN (optional)",
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of results (1-100)",
                        "default": 100,
                    },
                    "next_token": {
                        "type": "string",
                        "description": "Token for pagination (optional)",
                    },
                },
                "required": ["pull_request_id"],
            },
        ),
        # Smart Pagination Tools for Huge PRs
        Tool(
            name="pr_page",
            description="📄 Memory-safe file listing by page (100 files max per call). Use after get_pr_info(include_metadata=true) to navigate through PR files systematically. Returns file paths, sizes, and estimated line counts without loading content. CRITICAL: Never set include_content=true - always use pr_file_chunk for actual file content. Process 5-10 pages per batch, provide feedback, then continue.",
            inputSchema={
                "type": "object",
                "properties": {
                    "pull_request_id": {
                        "type": "string",
                        "description": "The pull request ID (numeric string)",
                    },
                    "page": {
                        "type": "integer",
                        "description": "Page number (1-based indexing, 100 files per page). Total pages available from pr_metadata output.",
                        "default": 1,
                    },
                    "include_content": {
                        "type": "boolean",
                        "description": "❌ MUST stay false for memory safety. Content loading handled by pr_file_chunk only.",
                        "default": False,
                    },
                },
                "required": ["pull_request_id"],
            },
        ),
        Tool(
            name="pr_file_chunk",
            description="📝 Load file content in memory-safe chunks (500 lines maximum per call). ⚠️ CRITICAL VERSION RULE: For inline comments, ALWAYS use version='after' to see the modified code, then use those AFTER line numbers for commenting with relativeFileVersion='AFTER'. Using 'before' version line numbers for 'AFTER' comments causes positioning failures. DEFAULT: version='after' (recommended for 95% of use cases). Use 'before' only when specifically analyzing original code.",
            inputSchema={
                "type": "object",
                "properties": {
                    "pull_request_id": {
                        "type": "string",
                        "description": "The pull request ID (numeric string)",
                    },
                    "file_path": {
                        "type": "string",
                        "description": "Exact file path as returned by pr_page (case-sensitive, include full directory structure)",
                    },
                    "start_line": {
                        "type": "integer",
                        "description": "Starting line number (1-based indexing). Use 1 for first chunk, 501 for second, 1001 for third, etc.",
                        "default": 1,
                    },
                    "chunk_size": {
                        "type": "integer",
                        "description": "Number of lines to retrieve (maximum 500 for memory optimization)",
                        "default": 500,
                    },
                    "version": {
                        "type": "string",
                        "enum": ["before", "after"],
                        "description": "CRITICAL: File version - 'after' shows modified code with correct line numbers for inline comments (USE THIS for commenting), 'before' shows original code (analysis only). Line numbers from 'before' version DO NOT match 'after' version!",
                        "default": "after",
                    },
                },
                "required": ["pull_request_id", "file_path"],
            },
        ),
    ]
