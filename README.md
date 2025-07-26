# AWS CodeCommit Pull Request MCP Server

A focused Model Context Protocol (MCP) server specifically designed for AWS CodeCommit pull request operations using boto3. This server provides comprehensive tools for managing CodeCommit pull requests with streamlined workflows, consolidated tool interfaces, and proper pagination handling for large codebases and multi-profile support.

**Version 2.2.0** - Enhanced with consolidated tools (16 tools, down from 19) and streamlined 4-step workflow (down from 5 steps) for better user experience.

## 🚀 Features

### AWS Profile Management

- **Multi-Profile Support**: Switch between different AWS profiles dynamically
- **Credential Refresh**: Manual credential refresh without server restart
- **Environment Variable Integration**: Automatic profile detection from `AWS_PROFILE` env var
- **Session Management**: Persistent session state with profile switching
- **Credential Validation**: Real-time credential testing and validation

### Streamlined Pull Request Management

- **Consolidated PR Information**: Single `get_pr_info` call for comprehensive details + optional metadata
- **Create & Update PRs**: Create new pull requests and modify titles, descriptions, status
- **List Pull Requests**: Browse PRs with filtering and pagination support
- **Smart Review Planning**: Integrated file analysis for optimal review strategy

### Unified Approval Management

- **Comprehensive Approval Status**: Single `get_pr_approvals` call for all approval information + override status  
- **Action-Based Management**: Single `manage_pr_approval` tool handles approve/revoke/override/revoke_override
- **Security-Conscious Overrides**: Approval rule overrides with detailed audit trails

### Comments & Reviews

- **Post Comments**: Add general and inline comments
- **Get Comments**: Retrieve all comments with pagination
- **Review Support**: Full support for code review workflows

### Memory-Safe Code Analysis

- **Claude-Driven Pagination**: Smart pagination system prevents memory crashes on huge PRs
- **Three-Tier Architecture**: Metadata → Pages (100 files) → Line chunks (500 lines) 
- **Incremental Review**: Claude processes and provides feedback per batch
- **Eliminated Unsafe Tools**: Removed `pr_changes`, `pr_files`, `pr_file_paths` that loaded everything at once
- **Scalable**: Works with PRs of any size (tested with 10,000+ files)

### Event Tracking

- **PR Events**: Complete audit trail of PR activities
- **Event Filtering**: Filter by event type and actor
- **Pagination Support**: Handle large event histories

## 🔄 Tool Consolidations (v2.2.0)

**Major Update**: Tools have been consolidated from 19 to 16 tools (16% reduction) with streamlined workflows:

### Consolidated Tools
| Category | Consolidation | Benefit |
|----------|---------------|---------|
| **PR Core** | `get_pr` + `pr_metadata` → `get_pr_info(include_metadata=true)` | Single call for comprehensive PR info + file analysis |
| **Approvals** | `pr_approvals` + `override_status` → `get_pr_approvals` | Complete approval information in one call |
| **Approvals** | `approve_pr` + `override_approvals` → `manage_pr_approval` | Action-based management (approve/revoke/override/revoke_override) |

### Removed Unsafe Tools  
| Tool | Reason | Replacement |
|------|--------|-------------|
| ❌ `pr_changes` | Memory unsafe - loaded all changes | Use `pr_page` → `pr_file_chunk` workflow |
| ❌ `pr_files` | Memory unsafe - loaded all content | Use `pr_page` → `pr_file_chunk` workflow |
| ❌ `pr_file_paths` | Memory unsafe - loaded all paths | Use `pr_page` for file listing |

### Streamlined Workflow
- **Before**: 5 steps (get_pr → pr_metadata → pr_page → pr_file_chunk → comments)
- **After**: 4 steps (get_pr_info → pr_page → pr_file_chunk → comments/approvals)
- **Improvement**: 20% workflow reduction with enhanced functionality

## 📋 Prerequisites

- Python 3.8 or higher
- AWS CLI configured with CodeCommit permissions
- Multiple AWS profiles configured (optional)
- Claude MCP client or compatible MCP client

## 🛠️ Installation

### Option 1: Docker (Recommended)

#### Quick Start with Docker

```bash
# Clone the repository
git clone <repository-url>
cd aws-pr-mcp

# Build and run with Docker Compose
docker-compose up -d
```

#### Docker Setup with AWS Credentials

1. **Create AWS credentials volume:**

```bash
# Create external volume for AWS credentials
docker volume create aws-credentials

# Copy your AWS credentials to the volume
docker run --rm -v aws-credentials:/aws -v ~/.aws:/host-aws alpine cp -r /host-aws/. /aws/
```

2. **Configure environment variables:**

```bash
# Copy example environment file
cp .env.example .env

# Edit .env file with your settings
nano .env
```

3. **Start the services:**

```bash
# Basic setup (MCP server only)
docker-compose up -d

# With Redis caching
docker-compose --profile cache up -d

# With PostgreSQL database for audit logging
docker-compose --profile database up -d

# Full setup with all services
docker-compose --profile cache --profile database --profile proxy up -d
```

### Option 2: Local Development

#### 1. Clone the Repository

```bash
git clone <repository-url>
cd aws-pr-mcp
```

#### 2. Create Virtual Environment

```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate
```

#### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

#### 4. Configure AWS Credentials and Profiles

#### Option A: Single Profile Setup

```bash
aws configure
```

#### Option B: Multiple Profiles Setup

```bash
# Configure default profile
aws configure

# Configure additional profiles
aws configure --profile dev
aws configure --profile staging
aws configure --profile prod
```

#### Option C: Environment Variables

```bash
export AWS_PROFILE=dev
export AWS_DEFAULT_REGION=us-east-1
```

#### Option D: AWS Credentials File with Multiple Profiles

Create `~/.aws/credentials`:

```ini
[default]
aws_access_key_id = your_default_access_key
aws_secret_access_key = your_default_secret_key
region = us-east-1

[dev]
aws_access_key_id = your_dev_access_key
aws_secret_access_key = your_dev_secret_key
region = us-west-2

[staging]
aws_access_key_id = your_staging_access_key
aws_secret_access_key = your_staging_secret_key
region = eu-west-1

[prod]
aws_access_key_id = your_prod_access_key
aws_secret_access_key = your_prod_secret_key
region = us-east-1
```

#### 5. Required IAM Permissions

Your AWS credentials need the following CodeCommit permissions:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "codecommit:CreatePullRequest",
        "codecommit:GetPullRequest",
        "codecommit:ListPullRequests",
        "codecommit:UpdatePullRequestTitle",
        "codecommit:UpdatePullRequestDescription",
        "codecommit:UpdatePullRequestStatus",
        "codecommit:GetPullRequestApprovalStates",
        "codecommit:UpdatePullRequestApprovalState",
        "codecommit:OverridePullRequestApprovalRules",
        "codecommit:GetPullRequestOverrideState",
        "codecommit:PostCommentForPullRequest",
        "codecommit:GetCommentsForPullRequest",
        "codecommit:DescribePullRequestEvents",
        "codecommit:GetDifferences",
        "codecommit:GetBlob",
        "codecommit:GetFile",
        "codecommit:GetMergeBase"
      ],
      "Resource": "*"
    }
  ]
}
```

## 🚀 Usage

### Option 1: Docker Usage

#### Basic Docker Run

```bash
# Build the image
docker build -t aws-pr-mcp .

# Run with environment variables
docker run -d \
  --name aws-pr-mcp-server \
  -e AWS_PROFILE=dev \
  -e AWS_DEFAULT_REGION=us-east-1 \
  -v ~/.aws:/root/.aws:ro \
  aws-pr-mcp
```

#### Docker Compose Usage

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f aws-pr-mcp

# Stop services
docker-compose down

# Rebuild and restart
docker-compose up -d --build
```

#### Docker Health Checks

```bash
# Check container health
docker ps

# View detailed health status
docker inspect aws-pr-mcp-server | grep -A 10 Health

# Manual health check
docker exec aws-pr-mcp-server python -c "import boto3; print('Health check passed')"
```

### Option 2: Local Development

#### Starting the MCP Server

```bash
python server.py
```

The server will start and listen for MCP protocol messages on stdin/stdout.

### Integrating with Claude Desktop

#### For Local Installation

Add the following configuration to your Claude Desktop MCP settings:

```json
{
  "mcpServers": {
    "codecommit-pr": {
      "command": "C:/aws-pr-mcp/start.bat",
      "args": [],
      "env": {
        "AWS_PROFILE": "ui_prod",
        "AWS_DEFAULT_REGION": "us-east-1"
      }
    }
  }
}
```

#### For Docker Installation

```json
{
  "mcpServers": {
    "codecommit-pr": {
      "command": "docker",
      "args": ["exec", "-i", "aws-pr-mcp-server", "python", "server.py"],
      "env": {
        "AWS_PROFILE": "dev",
        "AWS_DEFAULT_REGION": "us-east-1"
      }
    }
  }
}
```

## 🔧 Available Tools (16 Total)

### AWS Profile Management (3 tools)

#### 1. **current_profile**
Get information about the current AWS profile and session.

#### 2. **switch_profile** 
Switch to a different AWS profile dynamically.

#### 3. **refresh_credentials**
Refresh expired AWS credentials without restarting Claude Desktop. Essential for long-running sessions.

### Pull Request Management (6 tools)

#### 4. **create_pr**
Create a new pull request in a CodeCommit repository.

#### 5. **get_pr_info** ⭐ **CONSOLIDATED**
Get comprehensive PR information with optional file analysis metadata. Single call replaces `get_pr` + `pr_metadata` workflow.
- Use `include_metadata=true` for file counts, change distribution, and review planning
- Provides commit IDs needed for comments and approvals

#### 6. **list_prs**
List pull requests for a repository with enhanced pagination support.

#### 7-9. **update_pr_*** (title/desc/status)
Update PR title, description, or status individually.

### Unified Approval Management (2 tools)

#### 10. **get_pr_approvals** ⭐ **CONSOLIDATED**
Get comprehensive approval information including reviewer states and override status in single call. Replaces `pr_approvals` + `override_status`.

#### 11. **manage_pr_approval** ⭐ **CONSOLIDATED**  
Unified approval management for all approval actions. Action-based approach replaces `approve_pr` + `override_approvals`.
- `action="approve/revoke"` for standard reviews
- `action="override/revoke_override"` for bypassing approval rules

### Comments & Events (3 tools)

#### 12. **add_comment**
Post general or inline PR comments. Use commit IDs from `get_pr_info`, file paths from `pr_page`, and line numbers from `pr_file_chunk` analysis.

#### 13. **pr_comments**
Get all comments for a pull request with pagination support.

#### 14. **pr_events**
Get PR events and activity timeline with filtering support.

### Memory-Safe Smart Pagination (2 tools)

⚠️ **Removed Unsafe Tools**: `pr_changes`, `pr_files`, `pr_file_paths` (loaded everything at once)

#### 15. **pr_page**
Get a specific page of files (100 files max per call). Memory-safe navigation through PR files without loading content. Get file paths, sizes, and estimated line counts.

#### 16. **pr_file_chunk** 
Get file content in line chunks (500 lines max per call). For reviewing large files sequentially. Process files line-by-line with navigation guidance.

**⚠️ Smart Pagination Workflow:**
1. `get_pr_info(include_metadata=true)` - Get total files and page planning
2. `pr_page(page=1)` - Navigate files by page (no content loaded)  
3. `pr_file_chunk(file_path="exact/path", start_line=1)` - Review content in chunks
4. Continue with next chunks/pages as needed

**Benefits:**
- **Memory Safe**: Fixed limits prevent system crashes
- **Claude-Controlled**: Incremental review with feedback per batch
- **Scalable**: Works with PRs of any size (tested with 10,000+ files)
- **Progress Tracking**: Clear completion indicators and navigation

## 📚 Advanced Usage

### Multi-Profile Workflows

#### Example 1: Cross-Account PR Review

```bash
# Start with dev account
export AWS_PROFILE=dev
python server.py

# Within Claude:
# 1. current_profile - shows dev account
# 2. Review PRs in dev environment
# 3. switch_profile with profile_name="prod"
# 4. Review PRs in production environment
```

#### Example 2: Regional Operations

```json
{
  "profile_name": "global-ops",
  "region": "eu-west-1"
}
```

### Environment Configuration

Create a `.env` file for additional configuration:

```bash
# AWS Configuration
AWS_PROFILE=dev
AWS_DEFAULT_REGION=us-east-1

# Logging Configuration
LOG_LEVEL=INFO

# MCP Server Configuration
SERVER_NAME=codecommit-pr-mcp
SERVER_VERSION=1.0.0
```

### Pagination Handling

The server automatically handles pagination for:

- **Pull Request Lists**: Use `next_token` to get more results
- **Comments**: Paginate through large comment threads
- **Events**: Handle extensive PR event histories
- **File Changes**: Process PRs with thousands of files
- **File Differences**: Handle large diffs efficiently

Example pagination workflow:

```python
# First request
{
  "repository_name": "large-repo",
  "max_results": 50
}

# Subsequent requests using returned next_token
{
  "repository_name": "large-repo",
  "max_results": 50,
  "next_token": "returned-token-from-previous-call"
}
```

### Large Pull Request Handling

For PRs with many files, the server provides:

- **Automatic chunking** of file operations
- **Configurable limits** to prevent memory issues
- **File filtering** to focus on specific paths
- **Progressive loading** of diffs and content
- **Timeout handling** for large operations

## 🔧 Troubleshooting

### Docker-Specific Issues

1. **Container Health Check Failing**

   ```
   ERROR: Health check failing
   ```

   **Solution**: Check AWS credentials and boto3 installation

   ```bash
   docker exec aws-pr-mcp-server python -c "import boto3; print(boto3.__version__)"
   ```

2. **AWS Credentials Not Found in Container**

   ```
   ERROR: Unable to locate credentials
   ```

   **Solution**: Ensure AWS credentials volume is properly mounted

   ```bash
   docker run --rm -v aws-credentials:/aws alpine ls -la /aws
   ```

3. **Permission Denied on AWS Credentials**

   ```
   ERROR: Could not load credentials from any providers
   ```

   **Solution**: Fix credentials file permissions

   ```bash
   docker run --rm -v aws-credentials:/aws alpine chmod -R 600 /aws/*
   ```

4. **Container Won't Start**
   ```
   ERROR: Container exits immediately
   ```
   **Solution**: Check Docker logs for detailed error messages
   ```bash
   docker-compose logs aws-pr-mcp
   docker logs aws-pr-mcp-server
   ```

### Common Issues

1. **AWS Credentials Error**

   ```
   ERROR: AWS CodeCommit client not initialized
   ```

   **Solution**: Configure AWS credentials using `aws configure` or environment variables

2. **Expired Credentials While Server Running**

   ```
   ERROR: No result received from client-side tool execution
   ```

   **Solution**: Use the `refresh_credentials` tool instead of restarting Claude Desktop
   
   ```json
   {
     "tool": "refresh_credentials"
   }
   ```

3. **Profile Not Found**

   ```
   ERROR: Could not switch to profile: dev
   ```

   **Solution**: Ensure profile exists in `~/.aws/credentials` or `~/.aws/config`

4. **Access Denied**

   ```
   AWS Error: User is not authorized to perform action
   ```

   **Solution**: Ensure IAM user/role has required CodeCommit permissions

5. **Pull Request Not Found**
   ```
   AWS Error: Pull request does not exist
   ```
   **Solution**: Verify the pull request ID and repository access

### Debug Mode

#### Local Development

Enable debug logging:

```bash
export LOG_LEVEL=DEBUG
python server.py
```

#### Docker

Enable debug logging in Docker:

```bash
# Using environment variables
docker run -e LOG_LEVEL=DEBUG aws-pr-mcp

# Using docker-compose
LOG_LEVEL=DEBUG docker-compose up -d
```

### Performance Tips

- **For All PRs**: Use streamlined workflow (`get_pr_info` → `pr_page` → `pr_file_chunk`)
- **Tool Consolidation**: Use consolidated tools to reduce API calls (16% fewer tools)
- **Memory Management**: Review files in batches of 5-10 pages for optimal memory usage
- **Credential Management**: Use `refresh_credentials` instead of restarting Claude Desktop
- Filter file changes by path when possible
- Use specific PR status filters to reduce results
- Switch profiles only when necessary to avoid authentication overhead

## 🏗️ Architecture (Version 2.2.0)

### Core Components

- **Modular Design**: Refactored from 4000+ line monolith to 12 focused modules
- **CodeCommitPRManager**: Central AWS session and client management 
- **Consolidated Tools**: 16 tools (down from 19) with enhanced descriptions
- **Smart Pagination**: Memory-safe processing for huge PRs
- **Enhanced Error Handling**: Comprehensive error management with troubleshooting guidance

### Key Improvements

- **16% Tool Reduction**: Intelligent consolidation without feature loss
- **20% Workflow Improvement**: Streamlined 4-step process (down from 5 steps)
- **Claude-Aware Descriptions**: Enhanced tool guidance for optimal usage
- **Memory Safety**: Eliminated unsafe tools, added bounded pagination
- **Better UX**: Action-based management, single-call efficiency

### Data Flow

1. **Profile Management** → Multi-profile support with dynamic switching
2. **Consolidated Tool Request** → Enhanced MCP tools with better descriptions
3. **Smart Validation** → Parameter validation with user-friendly errors
4. **Optimized AWS Calls** → Reduced API calls through tool consolidation
5. **Memory-Safe Processing** → Bounded pagination prevents crashes
6. **Enhanced Response** → Rich formatting with navigation guidance

## 📊 What's New in Version 2.2.0

### Tool Consolidations (Major UX Improvement)

**Consolidated from 19 → 16 tools** with enhanced functionality:

- ✅ **`get_pr_info`**: Combines `get_pr` + `pr_metadata` → Single call for comprehensive info
- ✅ **`get_pr_approvals`**: Combines `pr_approvals` + `override_status` → Complete approval status  
- ✅ **`manage_pr_approval`**: Combines `approve_pr` + `override_approvals` → Action-based management

### Enhanced Features

- ✅ **Streamlined Workflow**: 4 steps instead of 5 (20% improvement)
- ✅ **Claude-Aware Descriptions**: Enhanced tool guidance for optimal usage patterns
- ✅ **Memory Safety Focus**: Eliminated unsafe tools, enhanced pagination
- ✅ **Better Error Handling**: Troubleshooting guidance with solution steps
- ✅ **Modular Architecture**: 12 focused modules instead of monolithic structure

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Update documentation
6. Submit a pull request

### Development Guidelines

- Follow Python PEP 8 style guidelines
- Add type hints to all functions
- Include comprehensive docstrings
- Handle all pagination scenarios
- Test with multiple AWS profiles
- Update README for new tools

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙏 Acknowledgments

- AWS CodeCommit team for comprehensive API design
- Claude MCP SDK developers
- Python boto3 maintainers
- Community contributors and testers

---

**Note**: This tool is specifically designed for AWS CodeCommit pull request operations with Version 2.2.0 consolidations. It provides comprehensive support for CodeCommit PR features with streamlined workflows, consolidated tools, and memory-safe pagination handling for enterprise-scale repositories across multiple AWS accounts.

**Key Metrics**: 16 tools (down from 19), 4-step workflow (down from 5), enhanced Claude integration, memory-safe processing for PRs of any size.
