#!/usr/bin/env python3
"""
AWS CodeCommit Pull Request MCP Server
A focused Model Context Protocol server for AWS CodeCommit pull request operations
using boto3 with comprehensive pagination handling.
"""

import asyncio
import json
import base64
import difflib
import os
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime
import logging

import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from mcp.server.models import InitializationOptions
from mcp.server import NotificationOptions, Server
from mcp.types import (
    Resource,
    Tool,
    TextContent,
    LoggingLevel
)
import mcp.types as types

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize the MCP server
server = Server("codecommit-pr-mcp")

class CodeCommitPRManager:
    """Main class for AWS CodeCommit pull request operations"""
    
    def __init__(self):
        self.session = None
        self.codecommit_client = None
        self.current_profile = None
        self.current_region = None
        self.initialize_aws_session()
    
    def initialize_aws_session(self):
        """Initialize AWS session with proper credential handling and profile support"""
        try:
            # Check for profile in environment variables
            profile_name = os.getenv('AWS_PROFILE')
            region_name = os.getenv('AWS_DEFAULT_REGION', 'us-east-1')
            
            # Initialize session with profile if specified
            if profile_name:
                self.session = boto3.Session(profile_name=profile_name, region_name=region_name)
                logger.info(f"Using AWS profile: {profile_name}")
            else:
                self.session = boto3.Session(region_name=region_name)
            
            self.current_profile = profile_name
            self.current_region = region_name
            self.codecommit_client = self.session.client('codecommit')
            
            # Test credentials
            sts_client = self.session.client('sts')
            identity = sts_client.get_caller_identity()
            logger.info(f"AWS Session initialized for account: {identity.get('Account')} in region: {region_name}")
            
        except NoCredentialsError:
            logger.warning("AWS credentials not found. Tools will not work.")
        except Exception as e:
            logger.error(f"Error initializing AWS session: {e}")
    
    def switch_profile(self, profile_name: str, region: str = None):
        """Switch to a different AWS profile"""
        try:
            if region is None:
                region = self.current_region or 'us-east-1'
            
            self.session = boto3.Session(profile_name=profile_name, region_name=region)
            self.codecommit_client = self.session.client('codecommit')
            self.current_profile = profile_name
            self.current_region = region
            
            # Test new credentials
            sts_client = self.session.client('sts')
            identity = sts_client.get_caller_identity()
            logger.info(f"Switched to profile: {profile_name}, account: {identity.get('Account')}, region: {region}")
            
            return True
        except Exception as e:
            logger.error(f"Error switching to profile {profile_name}: {e}")
            return False
    
    def get_client(self, region: str = None):
        """Get CodeCommit client for specific region"""
        if region and region != self.current_region:
            if self.current_profile:
                return self.session.client('codecommit', region_name=region)
            else:
                temp_session = boto3.Session(region_name=region)
                return temp_session.client('codecommit')
        return self.codecommit_client
    
    def get_current_profile_info(self):
        """Get information about current AWS profile and session"""
        try:
            sts_client = self.session.client('sts')
            identity = sts_client.get_caller_identity()
            return {
                'profile': self.current_profile or 'default',
                'region': self.current_region,
                'account': identity.get('Account'),
                'user_arn': identity.get('Arn'),
                'user_id': identity.get('UserId')
            }
        except Exception as e:
            logger.error(f"Error getting profile info: {e}")
            return None

# Initialize PR manager
pr_manager = CodeCommitPRManager()

@server.list_resources()
async def handle_list_resources() -> list[Resource]:
    """List available resources for CodeCommit PR operations"""
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
        return """CodeCommit Pull Request Management Overview:

This MCP server provides comprehensive tools for managing AWS CodeCommit pull requests:

1. Create and manage pull requests
2. Handle approval rules and states  
3. Get detailed PR information and events
4. Manage comments and reviews
5. Merge pull requests with different strategies
6. Retrieve complete code changes with pagination support

All operations support proper pagination handling for large codebases.
"""
    elif uri == "codecommit://pr-workflow/best-practices":
        return """CodeCommit PR Workflow Best Practices:

1. Always create meaningful PR titles and descriptions
2. Set up appropriate approval rules before merging
3. Use comments for code review feedback
4. Monitor PR events for audit trails
5. Choose appropriate merge strategies based on workflow
6. Handle large PRs with pagination-aware tools
7. Regularly clean up merged branches
"""
    else:
        raise ValueError(f"Unknown resource: {uri}")

@server.list_tools()
async def handle_list_tools() -> list[Tool]:
    """List all available CodeCommit PR tools"""
    return [
        # AWS Profile Management
        Tool(
            name="get_current_aws_profile",
            description="Get information about the current AWS profile and session",
            inputSchema={
                "type": "object",
                "properties": {},
                "additionalProperties": False
            },
        ),
        Tool(
            name="switch_aws_profile",
            description="Switch to a different AWS profile",
            inputSchema={
                "type": "object",
                "properties": {
                    "profile_name": {"type": "string", "description": "Name of the AWS profile to switch to"},
                    "region": {"type": "string", "description": "AWS region (optional, defaults to current region)"}
                },
                "required": ["profile_name"]
            },
        ),
        
        # PR Creation and Management
        Tool(
            name="create_pull_request",
            description="Create a new pull request in a CodeCommit repository",
            inputSchema={
                "type": "object",
                "properties": {
                    "repository_name": {"type": "string", "description": "Name of the CodeCommit repository"},
                    "title": {"type": "string", "description": "Title of the pull request"},
                    "description": {"type": "string", "description": "Description of the pull request"},
                    "source_commit": {"type": "string", "description": "Source commit ID or branch name"},
                    "destination_commit": {"type": "string", "description": "Destination commit ID or branch name"},
                    "client_request_token": {"type": "string", "description": "Unique token for idempotency (optional)"}
                },
                "required": ["repository_name", "title", "source_commit", "destination_commit"]
            },
        ),
        Tool(
            name="get_pull_request",
            description="Get detailed information about a specific pull request",
            inputSchema={
                "type": "object",
                "properties": {
                    "pull_request_id": {"type": "string", "description": "ID of the pull request"}
                },
                "required": ["pull_request_id"]
            },
        ),
        Tool(
            name="list_pull_requests",
            description="List pull requests for a repository with pagination support",
            inputSchema={
                "type": "object",
                "properties": {
                    "repository_name": {"type": "string", "description": "Name of the CodeCommit repository"},
                    "author_arn": {"type": "string", "description": "Filter by author ARN (optional)"},
                    "pr_status": {"type": "string", "enum": ["OPEN", "CLOSED"], "description": "Filter by PR status (optional)"},
                    "max_results": {"type": "integer", "description": "Maximum number of results (1-100)", "default": 50},
                    "next_token": {"type": "string", "description": "Token for pagination (optional)"}
                },
                "required": ["repository_name"]
            },
        ),
        Tool(
            name="update_pull_request_title",
            description="Update the title of a pull request",
            inputSchema={
                "type": "object",
                "properties": {
                    "pull_request_id": {"type": "string", "description": "ID of the pull request"},
                    "title": {"type": "string", "description": "New title for the pull request"}
                },
                "required": ["pull_request_id", "title"]
            },
        ),
        Tool(
            name="update_pull_request_description",
            description="Update the description of a pull request",
            inputSchema={
                "type": "object",
                "properties": {
                    "pull_request_id": {"type": "string", "description": "ID of the pull request"},
                    "description": {"type": "string", "description": "New description for the pull request"}
                },
                "required": ["pull_request_id", "description"]
            },
        ),
        Tool(
            name="update_pull_request_status",
            description="Update the status of a pull request",
            inputSchema={
                "type": "object",
                "properties": {
                    "pull_request_id": {"type": "string", "description": "ID of the pull request"},
                    "status": {"type": "string", "enum": ["OPEN", "CLOSED"], "description": "New status for the pull request"}
                },
                "required": ["pull_request_id", "status"]
            },
        ),
        
        # PR Approval Management (Read-only operations)
        Tool(
            name="get_pull_request_approval_states",
            description="Get approval states for a pull request",
            inputSchema={
                "type": "object",
                "properties": {
                    "pull_request_id": {"type": "string", "description": "ID of the pull request"},
                    "revision_id": {"type": "string", "description": "Revision ID (optional)"}
                },
                "required": ["pull_request_id"]
            },
        ),
        Tool(
            name="update_pull_request_approval_state",
            description="Update approval state for a pull request",
            inputSchema={
                "type": "object",
                "properties": {
                    "pull_request_id": {"type": "string", "description": "ID of the pull request"},
                    "revision_id": {"type": "string", "description": "Revision ID"},
                    "approval_state": {"type": "string", "enum": ["APPROVE", "REVOKE"], "description": "Approval state"}
                },
                "required": ["pull_request_id", "revision_id", "approval_state"]
            },
        ),
        Tool(
            name="override_pull_request_approval_rules",
            description="Override approval rules for a pull request",
            inputSchema={
                "type": "object",
                "properties": {
                    "pull_request_id": {"type": "string", "description": "ID of the pull request"},
                    "revision_id": {"type": "string", "description": "Revision ID"},
                    "override_status": {"type": "string", "enum": ["OVERRIDE", "REVOKE"], "description": "Override status"}
                },
                "required": ["pull_request_id", "revision_id", "override_status"]
            },
        ),
        Tool(
            name="get_pull_request_override_state",
            description="Get override state for pull request approval rules",
            inputSchema={
                "type": "object",
                "properties": {
                    "pull_request_id": {"type": "string", "description": "ID of the pull request"},
                    "revision_id": {"type": "string", "description": "Revision ID (optional)"}
                },
                "required": ["pull_request_id"]
            },
        ),
        
        # Comments and Events
        Tool(
            name="post_comment_for_pull_request",
            description="Post a comment on a pull request",
            inputSchema={
                "type": "object",
                "properties": {
                    "pull_request_id": {"type": "string", "description": "ID of the pull request"},
                    "repository_name": {"type": "string", "description": "Name of the repository"},
                    "before_commit_id": {"type": "string", "description": "Commit ID before the change"},
                    "after_commit_id": {"type": "string", "description": "Commit ID after the change"},
                    "content": {"type": "string", "description": "Comment content"},
                    "location": {
                        "type": "object",
                        "properties": {
                            "file_path": {"type": "string", "description": "Path to the file"},
                            "file_position": {"type": "integer", "description": "Position in the file"},
                            "relative_file_version": {"type": "string", "enum": ["BEFORE", "AFTER"], "description": "File version"}
                        },
                        "description": "Location for inline comments (optional)"
                    },
                    "client_request_token": {"type": "string", "description": "Unique token for idempotency (optional)"}
                },
                "required": ["pull_request_id", "repository_name", "before_commit_id", "after_commit_id", "content"]
            },
        ),
        Tool(
            name="get_comments_for_pull_request",
            description="Get all comments for a pull request with pagination support",
            inputSchema={
                "type": "object",
                "properties": {
                    "pull_request_id": {"type": "string", "description": "ID of the pull request"},
                    "repository_name": {"type": "string", "description": "Name of the repository (optional)"},
                    "before_commit_id": {"type": "string", "description": "Before commit ID (optional)"},
                    "after_commit_id": {"type": "string", "description": "After commit ID (optional)"},
                    "max_results": {"type": "integer", "description": "Maximum number of results (1-100)", "default": 100},
                    "next_token": {"type": "string", "description": "Token for pagination (optional)"}
                },
                "required": ["pull_request_id"]
            },
        ),
        Tool(
            name="describe_pull_request_events",
            description="Get events for a pull request with pagination support",
            inputSchema={
                "type": "object",
                "properties": {
                    "pull_request_id": {"type": "string", "description": "ID of the pull request"},
                    "pull_request_event_type": {"type": "string", "enum": ["PULL_REQUEST_CREATED", "PULL_REQUEST_SOURCE_REFERENCE_UPDATED", "PULL_REQUEST_STATUS_CHANGED", "PULL_REQUEST_MERGE_STATUS_CHANGED", "APPROVAL_RULE_CREATED", "APPROVAL_RULE_UPDATED", "APPROVAL_RULE_DELETED", "APPROVAL_RULE_OVERRIDDEN", "APPROVAL_STATE_CHANGED"], "description": "Filter by event type (optional)"},
                    "actor_arn": {"type": "string", "description": "Filter by actor ARN (optional)"},
                    "max_results": {"type": "integer", "description": "Maximum number of results (1-100)", "default": 100},
                    "next_token": {"type": "string", "description": "Token for pagination (optional)"}
                },
                "required": ["pull_request_id"]
            },
        ),
        
        
        # Code Changes Analysis
        Tool(
            name="get_pull_request_changes",
            description="Get all code changes in a pull request with pagination support and diff generation",
            inputSchema={
                "type": "object",
                "properties": {
                    "pull_request_id": {"type": "string", "description": "ID of the pull request"},
                    "include_diff": {"type": "boolean", "description": "Include detailed diff for each file", "default": true},
                    "max_files": {"type": "integer", "description": "Maximum number of files to process (default: all)", "default": 1000},
                    "file_path_filter": {"type": "string", "description": "Filter files by path pattern (optional)"}
                },
                "required": ["pull_request_id"]
            },
        ),
        Tool(
            name="get_pull_request_file_content",
            description="Get content of specific files from a pull request",
            inputSchema={
                "type": "object",
                "properties": {
                    "pull_request_id": {"type": "string", "description": "ID of the pull request"},
                    "file_paths": {"type": "array", "items": {"type": "string"}, "description": "List of file paths to retrieve"},
                    "version": {"type": "string", "enum": ["before", "after", "both"], "description": "Which version to retrieve", "default": "both"}
                },
                "required": ["pull_request_id", "file_paths"]
            },
        ),
    ]

@server.call_tool()
async def handle_call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    """Handle tool calls for CodeCommit PR operations"""
    
    if not pr_manager.codecommit_client:
        return [types.TextContent(
            type="text",
            text="ERROR: AWS CodeCommit client not initialized. Please check AWS credentials."
        )]
    
    try:
        # Profile management
        if name == "get_current_aws_profile":
            return await get_current_aws_profile(arguments)
        elif name == "switch_aws_profile":
            return await switch_aws_profile(arguments)
        # PR management
        elif name == "create_pull_request":
            return await create_pull_request(arguments)
        elif name == "get_pull_request":
            return await get_pull_request(arguments)
        elif name == "list_pull_requests":
            return await list_pull_requests(arguments)
        elif name == "update_pull_request_title":
            return await update_pull_request_title(arguments)
        elif name == "update_pull_request_description":
            return await update_pull_request_description(arguments)
        elif name == "update_pull_request_status":
            return await update_pull_request_status(arguments)
        elif name == "get_pull_request_approval_states":
            return await get_pull_request_approval_states(arguments)
        elif name == "update_pull_request_approval_state":
            return await update_pull_request_approval_state(arguments)
        elif name == "override_pull_request_approval_rules":
            return await override_pull_request_approval_rules(arguments)
        elif name == "get_pull_request_override_state":
            return await get_pull_request_override_state(arguments)
        elif name == "post_comment_for_pull_request":
            return await post_comment_for_pull_request(arguments)
        elif name == "get_comments_for_pull_request":
            return await get_comments_for_pull_request(arguments)
        elif name == "describe_pull_request_events":
            return await describe_pull_request_events(arguments)
        elif name == "get_pull_request_changes":
            return await get_pull_request_changes(arguments)
        elif name == "get_pull_request_file_content":
            return await get_pull_request_file_content(arguments)
        else:
            raise ValueError(f"Unknown tool: {name}")
    except Exception as e:
        logger.error(f"Error in tool {name}: {str(e)}")
        return [types.TextContent(
            type="text",
            text=f"ERROR: {str(e)}"
        )]

# Tool implementations

# Profile Management Functions
async def get_current_aws_profile(args: dict) -> list[types.TextContent]:
    """Get information about current AWS profile"""
    try:
        profile_info = pr_manager.get_current_profile_info()
        
        if profile_info:
            result = f"""Current AWS Profile Information:

Profile: {profile_info['profile']}
Region: {profile_info['region']}
Account ID: {profile_info['account']}
User ARN: {profile_info['user_arn']}
User ID: {profile_info['user_id']}

Status: ✅ Active and configured properly
"""
        else:
            result = """Current AWS Profile Information:

Status: ❌ Unable to retrieve profile information
Please check your AWS credentials configuration.
"""
        
        return [types.TextContent(type="text", text=result)]
        
    except Exception as e:
        return [types.TextContent(
            type="text",
            text=f"ERROR: Could not get profile information: {str(e)}"
        )]

async def switch_aws_profile(args: dict) -> list[types.TextContent]:
    """Switch to a different AWS profile"""
    try:
        profile_name = args["profile_name"]
        region = args.get("region")
        
        success = pr_manager.switch_profile(profile_name, region)
        
        if success:
            # Get new profile info
            profile_info = pr_manager.get_current_profile_info()
            
            result = f"""AWS Profile Switched Successfully:

New Profile: {profile_info['profile']}
Region: {profile_info['region']}
Account ID: {profile_info['account']}
User ARN: {profile_info['user_arn']}

✅ Profile switch completed successfully!
"""
        else:
            result = f"""AWS Profile Switch Failed:

❌ Could not switch to profile: {profile_name}

Please check:
• Profile exists in ~/.aws/credentials or ~/.aws/config
• Profile has valid credentials
• You have necessary permissions
"""
        
        return [types.TextContent(type="text", text=result)]
        
    except Exception as e:
        return [types.TextContent(
            type="text",
            text=f"ERROR: Could not switch profile: {str(e)}"
        )]

async def create_pull_request(args: dict) -> list[types.TextContent]:
    """Create a new pull request"""
    try:
        kwargs = {
            'repositoryName': args['repository_name'],
            'title': args['title'],
            'targets': [{
                'sourceReference': args['source_commit'],
                'destinationReference': args['destination_commit']
            }]
        }
        
        if 'description' in args:
            kwargs['description'] = args['description']
        if 'client_request_token' in args:
            kwargs['clientRequestToken'] = args['client_request_token']
        
        response = pr_manager.codecommit_client.create_pull_request(**kwargs)
        
        pr_info = response['pullRequest']
        result = f"""Pull Request Created Successfully!

PR ID: {pr_info['pullRequestId']}
Title: {pr_info['title']}
Status: {pr_info['pullRequestStatus']}
Author: {pr_info.get('authorArn', 'Unknown')}
Created: {pr_info['creationDate'].strftime('%Y-%m-%d %H:%M:%S UTC')}

Source: {pr_info['pullRequestTargets'][0]['sourceReference']}
Destination: {pr_info['pullRequestTargets'][0]['destinationReference']}
Repository: {pr_info['pullRequestTargets'][0]['repositoryName']}

Description: {pr_info.get('description', 'No description provided')}
"""
        
        return [types.TextContent(type="text", text=result)]
        
    except ClientError as e:
        return [types.TextContent(
            type="text",
            text=f"AWS Error: {e.response['Error']['Message']}"
        )]

async def get_pull_request(args: dict) -> list[types.TextContent]:
    """Get detailed information about a pull request"""
    try:
        response = pr_manager.codecommit_client.get_pull_request(
            pullRequestId=args['pull_request_id']
        )
        
        pr = response['pullRequest']
        
        result = f"""Pull Request Details:

Basic Information:
• PR ID: {pr['pullRequestId']}
• Title: {pr['title']}
• Status: {pr['pullRequestStatus']}
• Author: {pr.get('authorArn', 'Unknown')}
• Created: {pr['creationDate'].strftime('%Y-%m-%d %H:%M:%S UTC')}
• Last Updated: {pr['lastActivityDate'].strftime('%Y-%m-%d %H:%M:%S UTC')}

Description:
{pr.get('description', 'No description provided')}

Targets:
"""
        
        for i, target in enumerate(pr['pullRequestTargets'], 1):
            result += f"""
Target {i}:
• Repository: {target['repositoryName']}
• Source: {target['sourceReference']} ({target.get('sourceCommit', 'Unknown commit')})
• Destination: {target['destinationReference']} ({target.get('destinationCommit', 'Unknown commit')})
• Merge Status: {target.get('mergeMetadata', {}).get('isMerged', 'Not merged')}
"""
        
        # Add approval rules if present
        if 'approvalRules' in pr and pr['approvalRules']:
            result += "\nApproval Rules:\n"
            for rule in pr['approvalRules']:
                result += f"• {rule['approvalRuleName']}: {rule.get('ruleContentSha256', 'N/A')}\n"
        
        return [types.TextContent(type="text", text=result)]
        
    except ClientError as e:
        return [types.TextContent(
            type="text",
            text=f"AWS Error: {e.response['Error']['Message']}"
        )]

async def list_pull_requests(args: dict) -> list[types.TextContent]:
    """List pull requests with pagination support"""
    try:
        kwargs = {
            'repositoryName': args['repository_name'],
            'maxResults': args.get('max_results', 50)
        }
        
        if 'author_arn' in args:
            kwargs['authorArn'] = args['author_arn']
        if 'pr_status' in args:
            kwargs['pullRequestStatus'] = args['pr_status']
        if 'next_token' in args:
            kwargs['nextToken'] = args['next_token']
        
        response = pr_manager.codecommit_client.list_pull_requests(**kwargs)
        
        prs = response.get('pullRequestIds', [])
        next_token = response.get('nextToken')
        
        if not prs:
            result = f"No pull requests found in repository: {args['repository_name']}"
            if 'pr_status' in args:
                result += f" with status: {args['pr_status']}"
            return [types.TextContent(type="text", text=result)]
        
        result = f"""Pull Requests in {args['repository_name']}:
Found {len(prs)} pull request(s)

"""
        
        # Get detailed info for each PR (in batches to avoid rate limits)
        for i, pr_id in enumerate(prs, 1):
            try:
                pr_response = pr_manager.codecommit_client.get_pull_request(pullRequestId=pr_id)
                pr = pr_response['pullRequest']
                
                result += f"""{i}. PR #{pr['pullRequestId']}
   Title: {pr['title']}
   Status: {pr['pullRequestStatus']}
   Author: {pr.get('authorArn', 'Unknown').split('/')[-1] if pr.get('authorArn') else 'Unknown'}
   Created: {pr['creationDate'].strftime('%Y-%m-%d %H:%M:%S')}
   Source → Destination: {pr['pullRequestTargets'][0]['sourceReference']} → {pr['pullRequestTargets'][0]['destinationReference']}

"""
            except Exception as e:
                result += f"{i}. PR #{pr_id} (Error loading details: {str(e)})\n\n"
        
        if next_token:
            result += f"\n📄 More results available. Use next_token: {next_token}"
        
        return [types.TextContent(type="text", text=result)]
        
    except ClientError as e:
        return [types.TextContent(
            type="text",
            text=f"AWS Error: {e.response['Error']['Message']}"
        )]

async def update_pull_request_title(args: dict) -> list[types.TextContent]:
    """Update pull request title"""
    try:
        response = pr_manager.codecommit_client.update_pull_request_title(
            pullRequestId=args['pull_request_id'],
            title=args['title']
        )
        
        pr = response['pullRequest']
        result = f"""Pull Request Title Updated:

PR ID: {pr['pullRequestId']}
New Title: {pr['title']}
Last Updated: {pr['lastActivityDate'].strftime('%Y-%m-%d %H:%M:%S UTC')}
"""
        
        return [types.TextContent(type="text", text=result)]
        
    except ClientError as e:
        return [types.TextContent(
            type="text",
            text=f"AWS Error: {e.response['Error']['Message']}"
        )]

async def update_pull_request_description(args: dict) -> list[types.TextContent]:
    """Update pull request description"""
    try:
        response = pr_manager.codecommit_client.update_pull_request_description(
            pullRequestId=args['pull_request_id'],
            description=args['description']
        )
        
        pr = response['pullRequest']
        result = f"""Pull Request Description Updated:

PR ID: {pr['pullRequestId']}
Title: {pr['title']}
New Description: {pr.get('description', 'No description')}
Last Updated: {pr['lastActivityDate'].strftime('%Y-%m-%d %H:%M:%S UTC')}
"""
        
        return [types.TextContent(type="text", text=result)]
        
    except ClientError as e:
        return [types.TextContent(
            type="text",
            text=f"AWS Error: {e.response['Error']['Message']}"
        )]

async def update_pull_request_status(args: dict) -> list[types.TextContent]:
    """Update pull request status"""
    try:
        response = pr_manager.codecommit_client.update_pull_request_status(
            pullRequestId=args['pull_request_id'],
            pullRequestStatus=args['status']
        )
        
        pr = response['pullRequest']
        result = f"""Pull Request Status Updated:

PR ID: {pr['pullRequestId']}
Title: {pr['title']}
New Status: {pr['pullRequestStatus']}
Last Updated: {pr['lastActivityDate'].strftime('%Y-%m-%d %H:%M:%S UTC')}
"""
        
        return [types.TextContent(type="text", text=result)]
        
    except ClientError as e:
        return [types.TextContent(
            type="text",
            text=f"AWS Error: {e.response['Error']['Message']}"
        )]

async def create_pull_request_approval_rule(args: dict) -> list[types.TextContent]:
    """Create approval rule for pull request"""
    try:
        response = pr_manager.codecommit_client.create_pull_request_approval_rule(
            pullRequestId=args['pull_request_id'],
            approvalRuleName=args['approval_rule_name'],
            approvalRuleContent=args['approval_rule_content']
        )
        
        rule = response['approvalRule']
        result = f"""Approval Rule Created:

PR ID: {args['pull_request_id']}
Rule Name: {rule['approvalRuleName']}
Rule ID: {rule['approvalRuleId']}
Created: {rule['creationDate'].strftime('%Y-%m-%d %H:%M:%S UTC')}
Last Modified: {rule['lastModifiedDate'].strftime('%Y-%m-%d %H:%M:%S UTC')}

Rule Content:
{rule['approvalRuleContent']}
"""
        
        return [types.TextContent(type="text", text=result)]
        
    except ClientError as e:
        return [types.TextContent(
            type="text",
            text=f"AWS Error: {e.response['Error']['Message']}"
        )]

async def delete_pull_request_approval_rule(args: dict) -> list[types.TextContent]:
    """Delete approval rule from pull request"""
    try:
        response = pr_manager.codecommit_client.delete_pull_request_approval_rule(
            pullRequestId=args['pull_request_id'],
            approvalRuleName=args['approval_rule_name']
        )
        
        result = f"""Approval Rule Deleted:

PR ID: {args['pull_request_id']}
Deleted Rule: {args['approval_rule_name']}
Rule ID: {response['approvalRuleId']}
"""
        
        return [types.TextContent(type="text", text=result)]
        
    except ClientError as e:
        return [types.TextContent(
            type="text",
            text=f"AWS Error: {e.response['Error']['Message']}"
        )]

async def update_pull_request_approval_rule_content(args: dict) -> list[types.TextContent]:
    """Update approval rule content"""
    try:
        response = pr_manager.codecommit_client.update_pull_request_approval_rule_content(
            pullRequestId=args['pull_request_id'],
            approvalRuleName=args['approval_rule_name'],
            existingRuleContentSha256=args['existing_rule_content_sha256'],
            newRuleContent=args['new_rule_content']
        )
        
        rule = response['approvalRule']
        result = f"""Approval Rule Updated:

PR ID: {args['pull_request_id']}
Rule Name: {rule['approvalRuleName']}
Rule ID: {rule['approvalRuleId']}
Last Modified: {rule['lastModifiedDate'].strftime('%Y-%m-%d %H:%M:%S UTC')}

Updated Rule Content:
{rule['approvalRuleContent']}
"""
        
        return [types.TextContent(type="text", text=result)]
        
    except ClientError as e:
        return [types.TextContent(
            type="text",
            text=f"AWS Error: {e.response['Error']['Message']}"
        )]

async def get_pull_request_approval_states(args: dict) -> list[types.TextContent]:
    """Get approval states for pull request"""
    try:
        kwargs = {'pullRequestId': args['pull_request_id']}
        if 'revision_id' in args:
            kwargs['revisionId'] = args['revision_id']
            
        response = pr_manager.codecommit_client.get_pull_request_approval_states(**kwargs)
        
        approvals = response.get('approvals', [])
        
        result = f"""Pull Request Approval States:

PR ID: {args['pull_request_id']}
"""
        
        if 'revision_id' in args:
            result += f"Revision ID: {args['revision_id']}\n"
        
        result += f"Total Approvals: {len(approvals)}\n\n"
        
        if approvals:
            for i, approval in enumerate(approvals, 1):
                result += f"""{i}. Approval State:
   User ARN: {approval.get('userArn', 'Unknown')}
   Approval State: {approval.get('approvalState', 'Unknown')}

"""
        else:
            result += "No approvals found for this pull request.\n"
        
        return [types.TextContent(type="text", text=result)]
        
    except ClientError as e:
        return [types.TextContent(
            type="text",
            text=f"AWS Error: {e.response['Error']['Message']}"
        )]

async def update_pull_request_approval_state(args: dict) -> list[types.TextContent]:
    """Update approval state for pull request"""
    try:
        response = pr_manager.codecommit_client.update_pull_request_approval_state(
            pullRequestId=args['pull_request_id'],
            revisionId=args['revision_id'],
            approvalState=args['approval_state']
        )
        
        result = f"""Approval State Updated:

PR ID: {args['pull_request_id']}
Revision ID: {args['revision_id']}
New Approval State: {args['approval_state']}
Operation Successful: ✅
"""
        
        return [types.TextContent(type="text", text=result)]
        
    except ClientError as e:
        return [types.TextContent(
            type="text",
            text=f"AWS Error: {e.response['Error']['Message']}"
        )]

async def evaluate_pull_request_approval_rules(args: dict) -> list[types.TextContent]:
    """Evaluate pull request approval rules"""
    try:
        kwargs = {'pullRequestId': args['pull_request_id']}
        if 'revision_id' in args:
            kwargs['revisionId'] = args['revision_id']
            
        response = pr_manager.codecommit_client.evaluate_pull_request_approval_rules(**kwargs)
        
        evaluation = response.get('evaluation', {})
        
        result = f"""Pull Request Approval Rules Evaluation:

PR ID: {args['pull_request_id']}
"""
        
        if 'revision_id' in args:
            result += f"Revision ID: {args['revision_id']}\n"
        
        result += f"""
Overall Status: {evaluation.get('approved', 'Unknown')}
Overridden: {evaluation.get('overridden', 'Unknown')}

Approval Rules Status:
"""
        
        approval_rules_satisfied = evaluation.get('approvalRulesSatisfied', [])
        approval_rules_not_satisfied = evaluation.get('approvalRulesNotSatisfied', [])
        
        if approval_rules_satisfied:
            result += "\n✅ Satisfied Rules:\n"
            for rule in approval_rules_satisfied:
                result += f"   • {rule}\n"
        
        if approval_rules_not_satisfied:
            result += "\n❌ Not Satisfied Rules:\n"
            for rule in approval_rules_not_satisfied:
                result += f"   • {rule}\n"
        
        if not approval_rules_satisfied and not approval_rules_not_satisfied:
            result += "\nNo approval rules configured for this pull request.\n"
        
        return [types.TextContent(type="text", text=result)]
        
    except ClientError as e:
        return [types.TextContent(
            type="text",
            text=f"AWS Error: {e.response['Error']['Message']}"
        )]

async def override_pull_request_approval_rules(args: dict) -> list[types.TextContent]:
    """Override pull request approval rules"""
    try:
        response = pr_manager.codecommit_client.override_pull_request_approval_rules(
            pullRequestId=args['pull_request_id'],
            revisionId=args['revision_id'],
            overrideStatus=args['override_status']
        )
        
        result = f"""Approval Rules Override:

PR ID: {args['pull_request_id']}
Revision ID: {args['revision_id']}
Override Status: {args['override_status']}
Operation Successful: ✅
"""
        
        return [types.TextContent(type="text", text=result)]
        
    except ClientError as e:
        return [types.TextContent(
            type="text",
            text=f"AWS Error: {e.response['Error']['Message']}"
        )]

async def get_pull_request_override_state(args: dict) -> list[types.TextContent]:
    """Get override state for pull request approval rules"""
    try:
        kwargs = {'pullRequestId': args['pull_request_id']}
        if 'revision_id' in args:
            kwargs['revisionId'] = args['revision_id']
            
        response = pr_manager.codecommit_client.get_pull_request_override_state(**kwargs)
        
        result = f"""Pull Request Override State:

PR ID: {args['pull_request_id']}
"""
        
        if 'revision_id' in args:
            result += f"Revision ID: {args['revision_id']}\n"
        
        overridden = response.get('overridden', False)
        result += f"Overridden: {overridden}\n"
        
        if overridden:
            overrider = response.get('overrider')
            if overrider:
                result += f"Overrider ARN: {overrider}\n"
        
        return [types.TextContent(type="text", text=result)]
        
    except ClientError as e:
        return [types.TextContent(
            type="text",
            text=f"AWS Error: {e.response['Error']['Message']}"
        )]

async def post_comment_for_pull_request(args: dict) -> list[types.TextContent]:
    """Post comment on pull request"""
    try:
        kwargs = {
            'pullRequestId': args['pull_request_id'],
            'repositoryName': args['repository_name'],
            'beforeCommitId': args['before_commit_id'],
            'afterCommitId': args['after_commit_id'],
            'content': args['content']
        }
        
        if 'location' in args:
            location = args['location']
            kwargs['location'] = {
                'filePath': location['file_path'],
                'filePosition': location['file_position'],
                'relativeFileVersion': location['relative_file_version']
            }
        
        if 'client_request_token' in args:
            kwargs['clientRequestToken'] = args['client_request_token']
        
        response = pr_manager.codecommit_client.post_comment_for_pull_request(**kwargs)
        
        comment = response.get('comment', {})
        
        result = f"""Comment Posted Successfully:

PR ID: {args['pull_request_id']}
Comment ID: {comment.get('commentId', 'Unknown')}
Author: {comment.get('authorArn', 'Unknown')}
Posted: {comment.get('creationDate', 'Unknown')}

Content:
{comment.get('content', args['content'])}
"""
        
        if 'location' in args:
            location = args['location']
            result += f"""
Location:
• File: {location['file_path']}
• Position: {location['file_position']}
• Version: {location['relative_file_version']}
"""
        
        return [types.TextContent(type="text", text=result)]
        
    except ClientError as e:
        return [types.TextContent(
            type="text",
            text=f"AWS Error: {e.response['Error']['Message']}"
        )]

async def get_comments_for_pull_request(args: dict) -> list[types.TextContent]:
    """Get comments for pull request with pagination"""
    try:
        kwargs = {
            'pullRequestId': args['pull_request_id'],
            'maxResults': args.get('max_results', 100)
        }
        
        if 'repository_name' in args:
            kwargs['repositoryName'] = args['repository_name']
        if 'before_commit_id' in args:
            kwargs['beforeCommitId'] = args['before_commit_id']
        if 'after_commit_id' in args:
            kwargs['afterCommitId'] = args['after_commit_id']
        if 'next_token' in args:
            kwargs['nextToken'] = args['next_token']
        
        response = pr_manager.codecommit_client.get_comments_for_pull_request(**kwargs)
        
        comments = response.get('commentsForPullRequestData', [])
        next_token = response.get('nextToken')
        
        result = f"""Comments for Pull Request {args['pull_request_id']}:

Found {len(comments)} comment(s)

"""
        
        if not comments:
            result += "No comments found for this pull request.\n"
        else:
            for i, comment_data in enumerate(comments, 1):
                comment = comment_data.get('comments', [{}])[0]  # Get first comment in thread
                
                result += f"""{i}. Comment ID: {comment.get('commentId', 'Unknown')}
   Author: {comment.get('authorArn', 'Unknown').split('/')[-1] if comment.get('authorArn') else 'Unknown'}
   Posted: {comment.get('creationDate', 'Unknown')}
   
   Content:
   {comment.get('content', 'No content')}
   
"""
                
                # Add location info if it's an inline comment
                location = comment_data.get('location')
                if location:
                    result += f"""   Location:
   • File: {location.get('filePath', 'Unknown')}
   • Position: {location.get('filePosition', 'Unknown')}
   • Version: {location.get('relativeFileVersion', 'Unknown')}
   
"""
        
        if next_token:
            result += f"\n📄 More comments available. Use next_token: {next_token}"
        
        return [types.TextContent(type="text", text=result)]
        
    except ClientError as e:
        return [types.TextContent(
            type="text",
            text=f"AWS Error: {e.response['Error']['Message']}"
        )]

async def describe_pull_request_events(args: dict) -> list[types.TextContent]:
    """Get pull request events with pagination"""
    try:
        kwargs = {
            'pullRequestId': args['pull_request_id'],
            'maxResults': args.get('max_results', 100)
        }
        
        if 'pull_request_event_type' in args:
            kwargs['pullRequestEventType'] = args['pull_request_event_type']
        if 'actor_arn' in args:
            kwargs['actorArn'] = args['actor_arn']
        if 'next_token' in args:
            kwargs['nextToken'] = args['next_token']
        
        response = pr_manager.codecommit_client.describe_pull_request_events(**kwargs)
        
        events = response.get('pullRequestEvents', [])
        next_token = response.get('nextToken')
        
        result = f"""Pull Request Events for {args['pull_request_id']}:

Found {len(events)} event(s)

"""
        
        if not events:
            result += "No events found for this pull request.\n"
        else:
            for i, event in enumerate(events, 1):
                result += f"""{i}. Event: {event.get('pullRequestEventType', 'Unknown')}
   Date: {event.get('eventDate', 'Unknown')}
   Actor: {event.get('actorArn', 'Unknown').split('/')[-1] if event.get('actorArn') else 'Unknown'}
   
"""
                
                # Add event-specific details
                if 'pullRequestCreatedEventMetadata' in event:
                    metadata = event['pullRequestCreatedEventMetadata']
                    result += f"   Repository: {metadata.get('repositoryName', 'Unknown')}\n"
                    result += f"   Destination Reference: {metadata.get('destinationReference', 'Unknown')}\n"
                    result += f"   Source Reference: {metadata.get('sourceReference', 'Unknown')}\n"
                
                elif 'pullRequestStatusChangedEventMetadata' in event:
                    metadata = event['pullRequestStatusChangedEventMetadata']
                    result += f"   Status Changed From: {metadata.get('pullRequestStatus', 'Unknown')}\n"
                
                elif 'approvalStateChangedEventMetadata' in event:
                    metadata = event['approvalStateChangedEventMetadata']
                    result += f"   Approval State: {metadata.get('approvalStatus', 'Unknown')}\n"
                
                result += "\n"
        
        if next_token:
            result += f"📄 More events available. Use next_token: {next_token}"
        
        return [types.TextContent(type="text", text=result)]
        
    except ClientError as e:
        return [types.TextContent(
            type="text",
            text=f"AWS Error: {e.response['Error']['Message']}"
        )]

async def merge_pull_request_by_fast_forward(args: dict) -> list[types.TextContent]:
    """Merge pull request using fast-forward"""
    try:
        kwargs = {
            'pullRequestId': args['pull_request_id'],
            'repositoryName': args['repository_name']
        }
        
        if 'source_commit_id' in args:
            kwargs['sourceCommitId'] = args['source_commit_id']
        
        response = pr_manager.codecommit_client.merge_pull_request_by_fast_forward(**kwargs)
        
        pr = response.get('pullRequest', {})
        
        result = f"""Pull Request Merged (Fast-Forward):

PR ID: {pr.get('pullRequestId', args['pull_request_id'])}
Repository: {args['repository_name']}
Status: {pr.get('pullRequestStatus', 'MERGED')}
Merge Commit ID: {response.get('mergeCommitId', 'Unknown')}

Merge completed successfully! ✅
"""
        
        return [types.TextContent(type="text", text=result)]
        
    except ClientError as e:
        return [types.TextContent(
            type="text",
            text=f"AWS Error: {e.response['Error']['Message']}"
        )]

async def merge_pull_request_by_squash(args: dict) -> list[types.TextContent]:
    """Merge pull request using squash"""
    try:
        kwargs = {
            'pullRequestId': args['pull_request_id'],
            'repositoryName': args['repository_name']
        }
        
        # Add optional parameters
        optional_params = ['source_commit_id', 'author_name', 'email', 'commit_message', 
                          'keep_empty_folders', 'conflict_detail_level', 'conflict_resolution_strategy']
        
        for param in optional_params:
            if param in args:
                # Convert snake_case to camelCase for AWS API
                api_param = ''.join(word.capitalize() if i > 0 else word for i, word in enumerate(param.split('_')))
                kwargs[api_param] = args[param]
        
        response = pr_manager.codecommit_client.merge_pull_request_by_squash(**kwargs)
        
        pr = response.get('pullRequest', {})
        
        result = f"""Pull Request Merged (Squash):

PR ID: {pr.get('pullRequestId', args['pull_request_id'])}
Repository: {args['repository_name']}
Status: {pr.get('pullRequestStatus', 'MERGED')}
Merge Commit ID: {response.get('mergeCommitId', 'Unknown')}
"""
        
        if 'commit_message' in args:
            result += f"Commit Message: {args['commit_message']}\n"
        
        result += "\nSquash merge completed successfully! ✅"
        
        return [types.TextContent(type="text", text=result)]
        
    except ClientError as e:
        return [types.TextContent(
            type="text",
            text=f"AWS Error: {e.response['Error']['Message']}"
        )]

async def merge_pull_request_by_three_way(args: dict) -> list[types.TextContent]:
    """Merge pull request using three-way merge"""
    try:
        kwargs = {
            'pullRequestId': args['pull_request_id'],
            'repositoryName': args['repository_name']
        }
        
        # Add optional parameters
        optional_params = ['source_commit_id', 'author_name', 'email', 'commit_message', 
                          'keep_empty_folders', 'conflict_detail_level', 'conflict_resolution_strategy']
        
        for param in optional_params:
            if param in args:
                # Convert snake_case to camelCase for AWS API
                api_param = ''.join(word.capitalize() if i > 0 else word for i, word in enumerate(param.split('_')))
                kwargs[api_param] = args[param]
        
        response = pr_manager.codecommit_client.merge_pull_request_by_three_way(**kwargs)
        
        pr = response.get('pullRequest', {})
        
        result = f"""Pull Request Merged (Three-Way):

PR ID: {pr.get('pullRequestId', args['pull_request_id'])}
Repository: {args['repository_name']}
Status: {pr.get('pullRequestStatus', 'MERGED')}
Merge Commit ID: {response.get('mergeCommitId', 'Unknown')}
"""
        
        if 'commit_message' in args:
            result += f"Commit Message: {args['commit_message']}\n"
        
        result += "\nThree-way merge completed successfully! ✅"
        
        return [types.TextContent(type="text", text=result)]
        
    except ClientError as e:
        return [types.TextContent(
            type="text",
            text=f"AWS Error: {e.response['Error']['Message']}"
        )]

async def get_pull_request_changes(args: dict) -> list[types.TextContent]:
    """Get all code changes in pull request with pagination and diff generation"""
    try:
        # First, get the pull request details
        pr_response = pr_manager.codecommit_client.get_pull_request(
            pullRequestId=args['pull_request_id']
        )
        
        pr = pr_response['pullRequest']
        target = pr['pullRequestTargets'][0]  # Assuming single target
        repository_name = target['repositoryName']
        source_commit = target['sourceCommit']
        destination_commit = target['destinationCommit']
        
        # Find the merge base
        merge_base_response = pr_manager.codecommit_client.get_merge_base(
            repositoryName=repository_name,
            sourceCommitSpecifier=source_commit,
            destinationCommitSpecifier=destination_commit
        )
        
        merge_base_commit = merge_base_response['mergeBaseCommitId']
        
        # Get differences with pagination
        all_differences = []
        next_token = None
        max_files = args.get('max_files', 1000)
        file_path_filter = args.get('file_path_filter')
        
        while True:
            kwargs = {
                'repositoryName': repository_name,
                'beforeCommitSpecifier': merge_base_commit,
                'afterCommitSpecifier': source_commit
            }
            
            if next_token:
                kwargs['NextToken'] = next_token
            
            diff_response = pr_manager.codecommit_client.get_differences(**kwargs)
            differences = diff_response.get('differences', [])
            
            # Apply file path filter if specified
            if file_path_filter:
                differences = [d for d in differences if file_path_filter in d.get('afterBlob', {}).get('path', '')]
            
            all_differences.extend(differences)
            
            next_token = diff_response.get('NextToken')
            if not next_token or len(all_differences) >= max_files:
                break
        
        # Limit results
        all_differences = all_differences[:max_files]
        
        result = f"""Pull Request Changes Analysis:

PR ID: {args['pull_request_id']}
Repository: {repository_name}
Source Commit: {source_commit}
Destination Commit: {destination_commit}
Merge Base: {merge_base_commit}

Total Files Changed: {len(all_differences)}

"""
        
        if not all_differences:
            result += "No file changes found in this pull request.\n"
            return [types.TextContent(type="text", text=result)]
        
        # Categorize changes
        added_files = []
        modified_files = []
        deleted_files = []
        
        for diff in all_differences:
            change_type = diff.get('changeType', 'UNKNOWN')
            if change_type == 'A':
                added_files.append(diff)
            elif change_type == 'M':
                modified_files.append(diff)
            elif change_type == 'D':
                deleted_files.append(diff)
        
        result += f"""Change Summary:
• Added: {len(added_files)} files
• Modified: {len(modified_files)} files  
• Deleted: {len(deleted_files)} files

"""
        
        include_diff = args.get('include_diff', True)
        
        # Process each category
        if added_files:
            result += "📄 ADDED FILES:\n"
            for i, diff in enumerate(added_files, 1):
                after_blob = diff.get('afterBlob', {})
                file_path = after_blob.get('path', 'Unknown')
                result += f"{i}. {file_path}\n"
                
                if include_diff and i <= 10:  # Limit detailed diffs
                    try:
                        blob_response = pr_manager.codecommit_client.get_blob(
                            repositoryName=repository_name,
                            blobId=after_blob.get('blobId', '')
                        )
                        content = base64.b64decode(blob_response['content']).decode('utf-8', errors='ignore')
                        result += f"   Content (first 10 lines):\n"
                        lines = content.split('\n')[:10]
                        for line_num, line in enumerate(lines, 1):
                            result += f"   +{line_num:3d}: {line}\n"
                        if len(content.split('\n')) > 10:
                            result += f"   ... ({len(content.split('\n')) - 10} more lines)\n"
                    except:
                        result += "   (Could not retrieve file content)\n"
                result += "\n"
        
        if modified_files:
            result += "📝 MODIFIED FILES:\n"
            for i, diff in enumerate(modified_files, 1):
                before_blob = diff.get('beforeBlob', {})
                after_blob = diff.get('afterBlob', {})
                file_path = after_blob.get('path', before_blob.get('path', 'Unknown'))
                result += f"{i}. {file_path}\n"
                
                if include_diff and i <= 5:  # Limit detailed diffs for modified files
                    try:
                        # Get before content
                        before_response = pr_manager.codecommit_client.get_blob(
                            repositoryName=repository_name,
                            blobId=before_blob.get('blobId', '')
                        )
                        before_content = base64.b64decode(before_response['content']).decode('utf-8', errors='ignore').splitlines()
                        
                        # Get after content
                        after_response = pr_manager.codecommit_client.get_blob(
                            repositoryName=repository_name,
                            blobId=after_blob.get('blobId', '')
                        )
                        after_content = base64.b64decode(after_response['content']).decode('utf-8', errors='ignore').splitlines()
                        
                        # Generate diff
                        diff_lines = list(difflib.unified_diff(
                            before_content, 
                            after_content,
                            fromfile=f"a/{file_path}",
                            tofile=f"b/{file_path}",
                            lineterm=''
                        ))
                        
                        if diff_lines:
                            result += "   Diff (first 20 lines):\n"
                            for line in diff_lines[:20]:
                                result += f"   {line}\n"
                            if len(diff_lines) > 20:
                                result += f"   ... ({len(diff_lines) - 20} more diff lines)\n"
                    except:
                        result += "   (Could not generate diff)\n"
                result += "\n"
        
        if deleted_files:
            result += "🗑️ DELETED FILES:\n"
            for i, diff in enumerate(deleted_files, 1):
                before_blob = diff.get('beforeBlob', {})
                file_path = before_blob.get('path', 'Unknown')
                result += f"{i}. {file_path}\n"
        
        if len(all_differences) == max_files:
            result += f"\n⚠️ Results limited to {max_files} files. Use file_path_filter to narrow down results.\n"
        
        return [types.TextContent(type="text", text=result)]
        
    except ClientError as e:
        return [types.TextContent(
            type="text",
            text=f"AWS Error: {e.response['Error']['Message']}"
        )]

async def get_pull_request_file_content(args: dict) -> list[types.TextContent]:
    """Get content of specific files from pull request"""
    try:
        # Get pull request details
        pr_response = pr_manager.codecommit_client.get_pull_request(
            pullRequestId=args['pull_request_id']
        )
        
        pr = pr_response['pullRequest']
        target = pr['pullRequestTargets'][0]
        repository_name = target['repositoryName']
        source_commit = target['sourceCommit']
        destination_commit = target['destinationCommit']
        
        # Find merge base for "before" content
        merge_base_response = pr_manager.codecommit_client.get_merge_base(
            repositoryName=repository_name,
            sourceCommitSpecifier=source_commit,
            destinationCommitSpecifier=destination_commit
        )
        merge_base_commit = merge_base_response['mergeBaseCommitId']
        
        file_paths = args['file_paths']
        version = args.get('version', 'both')
        
        result = f"""File Content from Pull Request {args['pull_request_id']}:

Repository: {repository_name}
Source Commit: {source_commit}
Merge Base: {merge_base_commit}
Version: {version}

"""
        
        for file_path in file_paths:
            result += f"\n{'='*80}\nFILE: {file_path}\n{'='*80}\n"
            
            # Get file content from different versions
            if version in ['before', 'both']:
                try:
                    # Get file from merge base (before changes)
                    file_response = pr_manager.codecommit_client.get_file(
                        repositoryName=repository_name,
                        commitSpecifier=merge_base_commit,
                        filePath=file_path
                    )
                    
                    before_content = base64.b64decode(file_response['fileContent']).decode('utf-8', errors='ignore')
                    
                    result += f"\n--- BEFORE (Merge Base: {merge_base_commit}) ---\n"
                    lines = before_content.split('\n')
                    for line_num, line in enumerate(lines, 1):
                        result += f"{line_num:4d}: {line}\n"
                        if line_num > 100:  # Limit output
                            result += f"... ({len(lines) - 100} more lines)\n"
                            break
                    
                except ClientError as e:
                    if e.response['Error']['Code'] == 'FileDoesNotExistException':
                        result += f"\n--- BEFORE: File did not exist ---\n"
                    else:
                        result += f"\n--- BEFORE: Error retrieving file: {e.response['Error']['Message']} ---\n"
            
            if version in ['after', 'both']:
                try:
                    # Get file from source commit (after changes)
                    file_response = pr_manager.codecommit_client.get_file(
                        repositoryName=repository_name,
                        commitSpecifier=source_commit,
                        filePath=file_path
                    )
                    
                    after_content = base64.b64decode(file_response['fileContent']).decode('utf-8', errors='ignore')
                    
                    result += f"\n--- AFTER (Source: {source_commit}) ---\n"
                    lines = after_content.split('\n')
                    for line_num, line in enumerate(lines, 1):
                        result += f"{line_num:4d}: {line}\n"
                        if line_num > 100:  # Limit output
                            result += f"... ({len(lines) - 100} more lines)\n"
                            break
                    
                except ClientError as e:
                    if e.response['Error']['Code'] == 'FileDoesNotExistException':
                        result += f"\n--- AFTER: File was deleted ---\n"
                    else:
                        result += f"\n--- AFTER: Error retrieving file: {e.response['Error']['Message']} ---\n"
            
            # Generate diff if both versions requested
            if version == 'both':
                try:
                    before_response = pr_manager.codecommit_client.get_file(
                        repositoryName=repository_name,
                        commitSpecifier=merge_base_commit,
                        filePath=file_path
                    )
                    before_content = base64.b64decode(before_response['fileContent']).decode('utf-8', errors='ignore').splitlines()
                    
                    after_response = pr_manager.codecommit_client.get_file(
                        repositoryName=repository_name,
                        commitSpecifier=source_commit,
                        filePath=file_path
                    )
                    after_content = base64.b64decode(after_response['fileContent']).decode('utf-8', errors='ignore').splitlines()
                    
                    diff_lines = list(difflib.unified_diff(
                        before_content, 
                        after_content,
                        fromfile=f"a/{file_path}",
                        tofile=f"b/{file_path}",
                        lineterm=''
                    ))
                    
                    if diff_lines:
                        result += f"\n--- UNIFIED DIFF ---\n"
                        for line in diff_lines[:50]:  # Limit diff output
                            result += f"{line}\n"
                        if len(diff_lines) > 50:
                            result += f"... ({len(diff_lines) - 50} more diff lines)\n"
                
                except:
                    result += f"\n--- DIFF: Could not generate unified diff ---\n"
        
        return [types.TextContent(type="text", text=result)]
        
    except ClientError as e:
        return [types.TextContent(
            type="text",
            text=f"AWS Error: {e.response['Error']['Message']}"
        )]

async def main():
    """Main entry point for the MCP server"""
    from mcp.server.stdio import stdio_server
    
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="codecommit-pr-mcp",
                server_version="1.0.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )

if __name__ == "__main__":
    asyncio.run(main())