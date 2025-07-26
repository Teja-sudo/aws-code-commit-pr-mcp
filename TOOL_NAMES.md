# Tool Name Reference

This document shows the mapping between old and new (shortened) tool names for better display in Claude Desktop.

## Tool Name Changes

| Category | Old Name | New Name | Description |
|----------|----------|----------|-------------|
| **Profile** | `get_current_aws_profile` | `current_profile` | Get current AWS profile info |
| **Profile** | `switch_aws_profile` | `switch_profile` | Switch AWS profile |
| **PR Core** | `create_pull_request` | `create_pr` | Create a new pull request |
| **PR Core** | `get_pull_request` | `get_pr` | Get PR details |
| **PR Core** | `list_pull_requests` | `list_prs` | List PRs in repository |
| **PR Update** | `update_pull_request_title` | `update_pr_title` | Update PR title |
| **PR Update** | `update_pull_request_description` | `update_pr_desc` | Update PR description |
| **PR Update** | `update_pull_request_status` | `update_pr_status` | Update PR status |
| **Analysis** | `get_pull_request_changes` | `pr_changes` | Get PR file changes |
| **Analysis** | `get_pull_request_file_content` | `pr_files` | Get file contents |
| **Analysis** | `get_pull_request_file_paths` | `pr_file_paths` | Get changed file paths |
| **Approval** | `get_pull_request_approval_states` | `pr_approvals` | Get approval states |
| **Approval** | `update_pull_request_approval_state` | `approve_pr` | Approve/revoke PR |
| **Approval** | `override_pull_request_approval_rules` | `override_approvals` | Override approval rules |
| **Approval** | `get_pull_request_override_state` | `override_status` | Get override status |
| **Comments** | `post_comment_for_pull_request` | `add_comment` | Add PR comment |
| **Comments** | `get_comments_for_pull_request` | `pr_comments` | Get PR comments |
| **Comments** | `describe_pull_request_events` | `pr_events` | Get PR activity events |

## Usage Examples

### Before (Old Names)
```
get_current_aws_profile()
get_pull_request(pull_request_id="123")
get_pull_request_changes(pull_request_id="123")
```

### After (New Names)
```
current_profile()
get_pr(pull_request_id="123")
pr_changes(pull_request_id="123")
```

## Benefits

1. **Better UI Display**: Names fit within Claude Desktop's tool selection interface
2. **Faster Recognition**: Shorter names are easier to scan and identify
3. **Consistent Naming**: All PR-related tools use `pr_` prefix
4. **Maintained Functionality**: All parameters and behavior remain identical

## Migration Notes

- All functionality remains exactly the same
- Only the tool names have changed
- All parameters and schemas are unchanged
- Error handling and responses are identical