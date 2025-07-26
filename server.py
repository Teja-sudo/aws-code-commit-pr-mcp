"""
AWS CodeCommit Pull Request MCP Server - Modular Architecture
A robust Model Context Protocol server for AWS CodeCommit pull request operations
with comprehensive pagination handling, multi-profile support, and bulletproof
edge case handling for all PR states including huge PRs.

MODULAR ARCHITECTURE:
- Separated concerns into logical modules
- Enhanced maintainability and readability
- Improved code organization and testing
- Better error handling and logging
- Comprehensive documentation

FIXES APPLIED:
- Fixed pagination token case sensitivity (NextToken -> nextToken)
- Enhanced memory management for huge PRs with streaming approach
- Improved binary file handling and encoding detection
- Added retry logic with exponential backoff
- Enhanced file discovery with multiple fallback strategies
- Optimized diff generation for large files
- Added token validation and loop prevention
- Improved error handling and logging
- Enhanced chunk processing for extreme edge cases
"""

import asyncio
import logging
import sys
from mcp.server.models import InitializationOptions
from mcp.server import NotificationOptions, Server
from mcp.types import Resource, TextContent, LoggingLevel
import mcp.types as types

# Import our modular components
from src.aws_client import CodeCommitPRManager
from src.tools import get_tools
from src.handlers.profile_handlers import (
    get_current_aws_profile,
    switch_aws_profile,
    refresh_aws_credentials,
)
from src.handlers.pr_handlers import (
    create_pull_request,
    get_pr_info,
    list_pull_requests,
    update_pull_request_title,
    update_pull_request_description,
    update_pull_request_status,
)
from src.handlers.approval_handlers import (
    get_pr_approvals,
    manage_pr_approval,
    update_pull_request_approval_state,
    override_pull_request_approval_rules,
    get_pull_request_override_state,
)
from src.handlers.comment_handlers import (
    post_comment_for_pull_request,
    get_comments_for_pull_request,
    describe_pull_request_events,
)
from src.handlers.smart_pagination_handlers import (
    get_pr_page,
    get_pr_file_chunk,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Initialize the MCP server
server = Server("codecommit-pr-mcp")

# Initialize PR manager
pr_manager = CodeCommitPRManager()
# Ensure AWS session is initialized at startup
pr_manager.ensure_initialized()


@server.list_resources()
async def handle_list_resources() -> list[Resource]:
    """List available resources"""
    return [
        Resource(
            uri="codecommit://pr-management/overview",
            name="CodeCommit PR Management Overview",
            description="Overview of CodeCommit pull request management capabilities",
            mimeType="text/plain",
        ),
        Resource(
            uri="codecommit://pr-workflow/best-practices",
            name="CodeCommit PR Workflow Best Practices",
            description="Best practices for CodeCommit pull request workflows",
            mimeType="text/plain",
        ),
    ]


@server.read_resource()
async def handle_read_resource(uri: str) -> str:
    """Read resource content"""
    if uri == "codecommit://pr-management/overview":
        return """# CodeCommit PR Management Overview

This MCP server provides comprehensive AWS CodeCommit pull request management capabilities:

## Core Features
- Create, read, update pull requests
- Advanced change analysis with streaming for huge PRs
- File content retrieval with binary support
- Comment and approval management
- Multi-profile AWS support

## Enhanced Capabilities
- Bulletproof pagination handling
- Binary file detection and handling
- Multiple encoding support
- Streaming processing for large PRs
- Comprehensive error handling

## Available Tools
Use the list_tools command to see all available operations.
"""
    elif uri == "codecommit://pr-workflow/best-practices":
        return """# CodeCommit PR Workflow Best Practices

## Pull Request Creation
1. Use descriptive titles and detailed descriptions
2. Keep changes focused and atomic
3. Test changes before creating PR

## Review Process
1. Use inline comments for specific feedback
2. Approve only when ready to merge
3. Use approval rules for consistency

## Large PR Handling
1. Use streaming analysis for huge PRs
2. Filter files by type or pattern
3. Analyze changes incrementally

## Security
1. Review approval states before merging
2. Use override capabilities judiciously
3. Monitor PR events for audit trail
"""
    else:
        raise ValueError(f"Unknown resource: {uri}")


@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    """List all available CodeCommit PR tools"""
    return get_tools()


@server.call_tool()
async def handle_call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    """Handle tool calls for CodeCommit PR operations with enhanced error handling"""

    if not pr_manager.codecommit_client:
        return [
            types.TextContent(
                type="text",
                text="ERROR: AWS CodeCommit client not initialized. Please check AWS credentials.",
            )
        ]

    try:
        # Profile management
        if name == "current_profile":
            return await get_current_aws_profile(pr_manager, arguments)
        elif name == "switch_profile":
            return await switch_aws_profile(pr_manager, arguments)
        elif name == "refresh_credentials":
            return await refresh_aws_credentials(pr_manager, arguments)

        # PR creation and management
        elif name == "create_pr":
            return await create_pull_request(pr_manager, arguments)
        elif name == "get_pr_info":
            return await get_pr_info(pr_manager, arguments)
        elif name == "list_prs":
            return await list_pull_requests(pr_manager, arguments)
        elif name == "update_pr_title":
            return await update_pull_request_title(pr_manager, arguments)
        elif name == "update_pr_desc":
            return await update_pull_request_description(pr_manager, arguments)
        elif name == "update_pr_status":
            return await update_pull_request_status(pr_manager, arguments)

        # Consolidated approval management
        elif name == "get_pr_approvals":
            return await get_pr_approvals(pr_manager, arguments)
        elif name == "manage_pr_approval":
            return await manage_pr_approval(pr_manager, arguments)

        # Comment management
        elif name == "add_comment":
            return await post_comment_for_pull_request(pr_manager, arguments)
        elif name == "pr_comments":
            return await get_comments_for_pull_request(pr_manager, arguments)
        elif name == "pr_events":
            return await describe_pull_request_events(pr_manager, arguments)

        # Smart pagination for huge PRs
        elif name == "pr_page":
            return await get_pr_page(pr_manager, arguments)
        elif name == "pr_file_chunk":
            return await get_pr_file_chunk(pr_manager, arguments)
        else:
            raise ValueError(f"Unknown tool: {name}")

    except Exception as e:
        error_msg = str(e)
        logger.error(f"Error in tool {name}: {error_msg}")

        # Provide more helpful error messages for common issues
        if "No credentials" in error_msg or "Unable to locate credentials" in error_msg:
            return [
                types.TextContent(
                    type="text",
                    text="❌ AWS Credentials Error: No valid AWS credentials found.\n\n"
                    "🔧 To resolve:\n"
                    "1. Run: aws configure\n"
                    "2. Or set environment variables: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY\n"
                    "3. Or use: refresh_credentials tool\n"
                    "4. Verify with: aws sts get-caller-identity",
                )
            ]
        elif "ExpiredToken" in error_msg or "InvalidToken" in error_msg:
            return [
                types.TextContent(
                    type="text",
                    text="❌ AWS Token Expired: Your AWS session has expired.\n\n"
                    "🔧 To resolve:\n"
                    "1. Use the refresh_credentials tool\n"
                    "2. Or restart Claude Desktop\n"
                    "3. Check your AWS credentials are still valid",
                )
            ]
        else:
            return [types.TextContent(type="text", text=f"❌ ERROR: {error_msg}")]


async def main():
    """Main entry point for the enhanced modular MCP server"""
    try:
        from mcp.server.stdio import stdio_server

        async with stdio_server() as (read_stream, write_stream):
            await server.run(
                read_stream,
                write_stream,
                InitializationOptions(
                    server_name="codecommit-pr-mcp",
                    server_version="2.1.0",
                    capabilities=server.get_capabilities(
                        notification_options=NotificationOptions(),
                        experimental_capabilities={},
                    ),
                ),
            )
    except Exception as e:
        logger.error(f"Server failed to start or crashed: {str(e)}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
