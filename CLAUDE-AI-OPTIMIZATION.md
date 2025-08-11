# Claude AI Optimization Guide

This MCP server has been specifically optimized for use with Claude AI to enable intelligent, efficient pull request reviews and AWS CodeCommit operations.

## Tool Name Optimizations

### Short, Descriptive Names
All tool names have been shortened to display properly in Claude Desktop:
- `list_repositories` → `repos_list`
- `get_pull_request` → `pr_get`  
- `post_pr_comment` → `comment_post`
- `update_approval_state` → `approval_set`
- `get_merge_conflicts` → `merge_conflicts_check`

### Logical Grouping
Tools are organized by functional area:
- **Repository Management**: `repos_list`, `repo_get`, `branches_list`, `file_get`, `folder_get`
- **Pull Request Management**: `prs_list`, `pr_get`, `pr_create`, `pr_update_title`, `pr_merge`
- **Comment & Review**: `comments_get`, `comment_post`, `comment_update`, `comment_reply`
- **Approval & State**: `approvals_get`, `approval_set`, `approval_rules_check`
- **Merge Management**: `merge_conflicts_check`, `merge_options_get`, `pr_merge`
- **AWS Credentials**: `aws_creds_refresh`, `aws_profile_switch`, `aws_profiles_list`

## Claude AI-Optimized Descriptions

### Comprehensive Context
Each tool description includes:

1. **Primary Purpose**: What the tool does
2. **When to Use**: Specific scenarios where Claude should use this tool
3. **Workflow Context**: How it fits into the PR review process
4. **Essential Information**: Critical details Claude needs to know

### Key Optimization Patterns

#### Critical Tools Highlighted
- **`diff_get`** - Marked as "THE MOST CRITICAL tool for code review"
- **`comments_get`** - Marked as "CRITICAL for PR review workflow"
- **`pr_get`** - Marked as "ESSENTIAL for PR review"

#### Workflow Guidance
- **Sequential Operations**: Tools like `prs_list` explicitly state "Always follow with pr_get"
- **Required Dependencies**: Tools specify which other tools must be called first
- **Parameter Sourcing**: Descriptions explain where to get required parameters

#### Context-Aware Instructions
- **Repository Discovery**: Start with `repos_list` for repository exploration
- **PR Review Flow**: `prs_list` → `pr_get` → `diff_get` → `comments_get` → analysis
- **Code Analysis**: Use `file_get` for context, `diff_get` for changes
- **Review Actions**: Post comments with `comment_post`, set approvals with `approval_set`

## Parameter Descriptions

### Detailed Parameter Context
Each parameter includes:
- **Purpose**: What the parameter is used for
- **Format Requirements**: Exact format expected (e.g., "40-character hex string")
- **Source Information**: Where Claude can find the value (e.g., "from pr_get response")
- **Usage Examples**: Concrete examples with realistic values

### Smart Defaults and Options
- **Optional Parameters**: Clearly marked with use cases
- **Enum Values**: Each option explained with context
- **Pagination**: Guidance on when to use nextToken
- **Error Prevention**: Parameter validation hints

## Workflow Intelligence

### PR Review Workflow
1. **Discovery**: `repos_list` → `prs_list` → `pr_get`
2. **Analysis**: `diff_get` → `file_get` (for context) → `comments_get`
3. **Review**: `comment_post` (with line-specific feedback)
4. **Decision**: `approval_set` or request changes
5. **Merge**: `merge_conflicts_check` → `pr_merge`

### Repository Exploration
1. **Structure**: `folder_get` (start with root "") → explore directories
2. **Files**: `file_get` for specific file contents
3. **History**: `commit_get` for commit details
4. **Comparison**: `diff_get` between branches/commits

### Comment Management
1. **Review Existing**: `comments_get` to see current feedback
2. **Add Feedback**: `comment_post` (general or line-specific)
3. **Respond**: `comment_reply` for threaded discussions
4. **Update**: `comment_update` for corrections

## Error Prevention

### Dependency Management
- Tools specify required prerequisites (e.g., need PR details before posting comments)
- Parameter dependencies clearly explained (e.g., revisionId comes from pr_get)

### Validation Hints
- Repository names must match exactly
- Commit IDs are 40-character hex strings
- File paths use forward slashes, no leading slash
- Branch names are case-sensitive

### Common Pitfalls Addressed
- ❌ Using wrong commit specifiers for diff_get
- ❌ Missing beforeCommitId/afterCommitId for comments
- ❌ Attempting to merge without checking approval rules
- ❌ Using outdated revision IDs for approvals

## Advanced Features

### Pagination Intelligence
- Auto-handles large result sets
- Provides guidance on when pagination is needed
- Optimizes batch sizes for different operations

### Credential Management
- Auto-refresh every 7.5 hours
- Profile switching without restart
- Status checking for troubleshooting

### Error Recovery
- Comprehensive AWS error handling
- Retry logic with exponential backoff
- Specific error codes for different scenarios

## Best Practices for Claude

### Efficient Operations
1. **Batch Related Calls**: Get PR details and comments together
2. **Cache Information**: Store PR metadata for multiple operations
3. **Verify Before Action**: Check approval rules before merging
4. **Provide Context**: Always include relevant file content when reviewing

### Smart Reviewing
1. **Comprehensive Analysis**: Use diff_get + file_get for full context
2. **Targeted Feedback**: Use line-specific comments with filePath/filePosition
3. **Constructive Comments**: Focus on specific issues and improvements
4. **Thread Management**: Use comment_reply to maintain conversation context

### Workflow Optimization
1. **Start Broad**: Repository → PRs → Specific PR
2. **Analyze Deep**: Differences → File contents → Existing comments
3. **Act Precisely**: Targeted comments → Approval decisions → Clean merges
4. **Follow Up**: Monitor comment threads and approval status

This optimization ensures Claude AI can efficiently navigate AWS CodeCommit, provide thorough PR reviews, and manage the complete pull request lifecycle with context-aware intelligence.