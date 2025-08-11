# AWS PR Reviewer MCP Server

A comprehensive Model Context Protocol (MCP) server for AWS CodeCommit that enables AI assistants to review pull requests, manage repositories, and perform code analysis directly within AWS CodeCommit.

## Features

### Repository Management
- List all accessible AWS CodeCommit repositories
- Get detailed repository information
- Search repositories by name or description
- List and manage branches
- Access commit history and details
- Browse file and folder contents at any commit

### Pull Request Operations
- List pull requests by status (open, closed)
- Get detailed PR metadata including targets, approval rules, and merge status
- Create new pull requests
- Update PR titles and descriptions
- Open/close pull requests
- Get available merge options and check for conflicts
- Merge pull requests with different strategies

### Code Review Capabilities
- Get file differences between commits
- Access complete file content for context
- Post comments at specific line numbers or file level
- Edit and delete comments
- Reply to existing comments
- Thread-based comment conversations

### Approval Management
- View approval states and rules
- Approve or revoke approvals
- Evaluate approval rule compliance
- Manage approval workflows

### AWS Authentication
- Support for AWS CLI profiles
- Environment variable credentials
- Session token support for temporary credentials
- Automatic credential refresh (7.5-hour intervals)
- Profile switching without restart
- Credential validation and status checking

### Advanced Features
- Comprehensive pagination handling for large datasets
- Retry logic with exponential backoff for resilience
- Detailed error handling with specific AWS error codes
- Modular architecture for easy maintenance and extension

## Installation

### Prerequisites
- Node.js 18+ and npm
- AWS CLI configured with appropriate permissions
- Access to AWS CodeCommit repositories

### Setup

1. **Clone and install dependencies:**
   ```bash
   npm install
   ```

2. **Build the TypeScript project:**
   ```bash
   npm run build
   ```

3. **Configure AWS credentials** (choose one method):
   
   **Method 1: AWS CLI Profile**
   ```bash
   aws configure --profile your-profile-name
   ```
   
   **Method 2: Environment variables**
   ```bash
   export AWS_PROFILE=your-profile-name
   export AWS_REGION=us-east-1
   ```
   
   **Method 3: Direct credentials**
   ```bash
   export AWS_ACCESS_KEY_ID=your-access-key
   export AWS_SECRET_ACCESS_KEY=your-secret-key
   export AWS_SESSION_TOKEN=your-session-token  # if using temporary credentials
   export AWS_REGION=us-east-1
   ```

## Usage

### Running the MCP Server

**Development mode:**
```bash
npm run dev
```

**Production mode:**
```bash
npm run build
npm start
```

### MCP Client Configuration

Add this server to your MCP client configuration:

```json
{
  "mcpServers": {
    "aws-pr-reviewer": {
      "command": "node",
      "args": ["/path/to/aws-pr-reviewer/dist/index.js"],
      "env": {
        "AWS_PROFILE": "your-profile-name",
        "AWS_REGION": "us-east-1"
      }
    }
  }
}
```

## Available Tools

### Repository Management Tools

#### `repos_list`
List all accessible repositories with optional search filtering.
```json
{
  "searchTerm": "optional-search-term",
  "nextToken": "pagination-token",
  "maxResults": 50
}
```

#### `repo_get`
Get detailed information about a specific repository.
```json
{
  "repositoryName": "my-repo"
}
```

#### `branches_list`
List all branches in a repository.
```json
{
  "repositoryName": "my-repo",
  "nextToken": "pagination-token"
}
```

#### `branch_get`
Get details of a specific branch.
```json
{
  "repositoryName": "my-repo",
  "branchName": "main"
}
```

#### `file_get`
Get the content of a file at a specific commit.
```json
{
  "repositoryName": "my-repo",
  "commitSpecifier": "main",
  "filePath": "src/index.ts"
}
```

#### `folder_get`
List contents of a folder at a specific commit.
```json
{
  "repositoryName": "my-repo",
  "commitSpecifier": "main",
  "folderPath": "src"
}
```

#### `commit_get`
Get detailed information about a commit.
```json
{
  "repositoryName": "my-repo",
  "commitId": "abc123..."
}
```

#### `diff_get`
Get file differences between two commits.
```json
{
  "repositoryName": "my-repo",
  "beforeCommitSpecifier": "main",
  "afterCommitSpecifier": "feature-branch",
  "beforePath": "optional-path-filter",
  "afterPath": "optional-path-filter"
}
```

### Pull Request Management Tools

#### `prs_list`
List pull requests in a repository.
```json
{
  "repositoryName": "my-repo",
  "pullRequestStatus": "OPEN",
  "nextToken": "pagination-token"
}
```

#### `pr_get`
Get detailed information about a pull request.
```json
{
  "pullRequestId": "123"
}
```

#### `pr_create`
Create a new pull request.
```json
{
  "repositoryName": "my-repo",
  "title": "Add new feature",
  "description": "This PR adds...",
  "sourceReference": "feature-branch",
  "destinationReference": "main"
}
```

#### `pr_update_title`
Update a pull request's title.
```json
{
  "pullRequestId": "123",
  "title": "Updated title"
}
```

#### `pr_update_desc`
Update a pull request's description.
```json
{
  "pullRequestId": "123",
  "description": "Updated description"
}
```

#### `pr_close` / `pr_reopen`
Close or reopen a pull request.
```json
{
  "pullRequestId": "123"
}
```

### Comment and Review Tools

#### `comments_get`
Get all comments for a pull request.
```json
{
  "pullRequestId": "123",
  "repositoryName": "my-repo",
  "beforeCommitId": "abc123...",
  "afterCommitId": "def456..."
}
```

#### `comment_post`
Post a comment on a pull request.
```json
{
  "pullRequestId": "123",
  "repositoryName": "my-repo",
  "beforeCommitId": "abc123...",
  "afterCommitId": "def456...",
  "content": "This looks good!",
  "filePath": "src/index.ts",
  "filePosition": 42,
  "relativeFileVersion": "AFTER"
}
```

#### `comment_update`
Update an existing comment.
```json
{
  "commentId": "comment-123",
  "content": "Updated comment content"
}
```

#### `comment_delete`
Delete a comment.
```json
{
  "commentId": "comment-123"
}
```

#### `comment_reply`
Reply to an existing comment.
```json
{
  "pullRequestId": "123",
  "repositoryName": "my-repo",
  "beforeCommitId": "abc123...",
  "afterCommitId": "def456...",
  "inReplyTo": "comment-123",
  "content": "I agree with this comment"
}
```

### Approval and Review State Tools

#### `approvals_get`
Get approval states for a pull request.
```json
{
  "pullRequestId": "123",
  "revisionId": "rev-123"
}
```

#### `approval_set`
Approve or revoke approval for a pull request.
```json
{
  "pullRequestId": "123",
  "revisionId": "rev-123",
  "approvalStatus": "APPROVE"
}
```

#### `approval_rules_check`
Evaluate if approval rules are met.
```json
{
  "pullRequestId": "123",
  "revisionId": "rev-123"
}
```

### Merge Management Tools

#### `merge_conflicts_check`
Check for merge conflicts.
```json
{
  "repositoryName": "my-repo",
  "destinationCommitSpecifier": "main",
  "sourceCommitSpecifier": "feature-branch",
  "mergeOption": "THREE_WAY_MERGE"
}
```

#### `merge_options_get`
Get available merge options.
```json
{
  "repositoryName": "my-repo",
  "sourceCommitSpecifier": "feature-branch",
  "destinationCommitSpecifier": "main"
}
```

#### `pr_merge`
Merge a pull request.
```json
{
  "pullRequestId": "123",
  "repositoryName": "my-repo",
  "mergeOption": "SQUASH_MERGE",
  "commitMessage": "Merge feature branch",
  "authorName": "John Doe",
  "email": "john@example.com"
}
```

### AWS Credential Management Tools

#### `aws_creds_refresh`
Manually refresh AWS credentials.
```json
{}
```

#### `aws_profile_switch`
Switch to a different AWS profile.
```json
{
  "profileName": "production-profile"
}
```

#### `aws_profiles_list`
Get list of available AWS profiles.
```json
{}
```

#### `aws_creds_status`
Check current credential status.
```json
{}
```

## AWS Permissions

The following AWS IAM permissions are required:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "codecommit:ListRepositories",
        "codecommit:GetRepository",
        "codecommit:ListBranches",
        "codecommit:GetBranch",
        "codecommit:GetCommit",
        "codecommit:GetFile",
        "codecommit:GetFolder",
        "codecommit:GetDifferences",
        "codecommit:ListPullRequests",
        "codecommit:GetPullRequest",
        "codecommit:CreatePullRequest",
        "codecommit:UpdatePullRequestTitle",
        "codecommit:UpdatePullRequestDescription",
        "codecommit:UpdatePullRequestStatus",
        "codecommit:GetCommentsForPullRequest",
        "codecommit:PostCommentForPullRequest",
        "codecommit:UpdateComment",
        "codecommit:DeleteCommentContent",
        "codecommit:PostCommentReply",
        "codecommit:GetPullRequestApprovalStates",
        "codecommit:UpdatePullRequestApprovalState",
        "codecommit:EvaluatePullRequestApprovalRules",
        "codecommit:GetMergeConflicts",
        "codecommit:GetMergeOptions",
        "codecommit:MergePullRequestByFastForward",
        "codecommit:MergePullRequestBySquash",
        "codecommit:MergePullRequestByThreeWay"
      ],
      "Resource": "*"
    }
  ]
}
```

## Architecture

### Directory Structure
```
src/
├── auth/           # AWS authentication management
├── services/       # Core business logic services
├── types/          # TypeScript type definitions
├── utils/          # Utility functions and helpers
└── index.ts        # Main MCP server entry point
```

### Key Components

- **AWSAuthManager**: Handles AWS credential management, profile switching, and automatic refresh
- **RepositoryService**: Manages repository operations and code access
- **PullRequestService**: Handles all PR-related operations including comments and approvals
- **Error Handling**: Comprehensive AWS-specific error handling with retry logic
- **Pagination**: Efficient handling of large datasets with proper pagination

## Development

### Building
```bash
npm run build
```

### Development Server
```bash
npm run dev
```

### Project Structure
The codebase follows a modular architecture with clear separation of concerns:

- **Types**: Comprehensive TypeScript definitions for all AWS CodeCommit entities
- **Authentication**: Robust credential management with profile switching and refresh
- **Services**: Business logic separated by domain (repositories vs pull requests)
- **Error Handling**: AWS-specific error handling with retry mechanisms
- **Pagination**: Consistent pagination handling across all list operations

### Adding New Features

1. Add type definitions in `src/types/index.ts`
2. Implement business logic in appropriate service class
3. Add tool definition and handler in `src/index.ts`
4. Update this README with the new tool documentation

## Troubleshooting

### Common Issues

**Credentials Error**
```
Error: AWS credentials error: Unable to load credentials
```
- Ensure AWS CLI is configured: `aws configure`
- Check profile name: `aws configure list-profiles`
- Verify region setting: `aws configure get region`

**Repository Access Error**
```
Error: Access denied
```
- Check IAM permissions for CodeCommit
- Verify repository exists and you have access
- Ensure region matches repository location

**Connection Timeout**
```
Error: Connection timeout
```
- Check internet connectivity
- Verify AWS service availability
- Check if corporate firewall blocks AWS endpoints

### Debugging

Enable debug logging by setting environment variable:
```bash
DEBUG=aws-pr-reviewer npm run dev
```

### Performance Optimization

- Use pagination for large datasets
- Implement caching for frequently accessed data
- Monitor AWS API rate limits
- Use appropriate maxResults values for your use case

## Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass
5. Submit a pull request

## License

MIT License - see LICENSE file for details.

## Support

For issues and questions:
1. Check the troubleshooting section
2. Review AWS CodeCommit documentation
3. Open an issue with detailed error messages and steps to reproduce