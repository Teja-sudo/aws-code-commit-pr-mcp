# 🎯 STREAMLINED: Smart PR Review Workflow

## ⚠️ SIMPLIFIED WORKFLOW - 4 Steps Instead of 5:

### 📋 Step 1: Get Comprehensive PR Information
```
get_pr_info(pull_request_id="XXX", include_metadata=true)
```
- **SINGLE CALL gets ALL essential info**: title, description, status, author, branches, commit IDs
- **Includes file analysis**: total files, page count, change distribution (A/M/D) 
- **Memory-safe metadata**: file counts without loading content
- **Strategic guidance**: recommends review approach based on PR size
- **Commit IDs provided**: ready for comments (before_commit_id, after_commit_id)

### 📄 Step 2: Navigate Files Page by Page
```
pr_page(pull_request_id="XXX", page=1)
```
- **Use file counts from Step 1** to plan total pages needed
- **CRITICAL: Keep include_content=false** for memory safety
- Process 5-10 pages per batch, provide feedback before continuing
- Returns file paths, sizes, estimated line counts (no content loaded)
- Navigate sequentially: page 1, 2, 3... based on Step 1 totals

### 📝 Step 3: Review File Content in Chunks
```
pr_file_chunk(pull_request_id="XXX", file_path="exact/path", start_line=1)
```
- Use EXACT file paths from pr_page (case-sensitive, full directory structure)
- Maximum 500 lines per chunk for memory optimization
- Sequential processing: lines 1-500, then 501-1000, then 1001-1500, etc.
- Provide detailed analysis per chunk for large files

### 💬 Step 4: Post Comments & Manage Approvals
```
add_comment(pull_request_id="XXX", repository_name="XXX", 
           before_commit_id="full_sha", after_commit_id="full_sha", 
           content="Your comprehensive review feedback")

get_pr_approvals(pull_request_id="XXX")
manage_pr_approval(pull_request_id="XXX", revision_id="XXX", action="approve")
```
- Use commit IDs from get_pr_info (step 1)
- Use exact file paths from pr_page (step 2)  
- Reference specific line numbers from pr_file_chunk analysis (step 3)
- Check approval status and manage approvals in single calls

## 🚫 DEPRECATED Tools (Use New Consolidated Versions):
- ❌ pr_metadata → Use get_pr_info(include_metadata=true) 
- ❌ pr_approvals → Use get_pr_approvals
- ❌ approve_pr/override_approvals → Use manage_pr_approval
- ❌ override_status → Included in get_pr_approvals
- ❌ pr_changes/pr_files/pr_file_paths (removed for memory safety)

## 🔄 Credential Issues:
```
refresh_credentials()
```
- Use when you get "No result received" errors
- Fixes expired credentials without restart

## 💡 Smart Review Strategy:
1. **Small PRs (<50 files)**: get_pr_info(include_metadata=true) → pr_page(pages 1-3) → pr_file_chunk for key files
2. **Medium PRs (50-200 files)**: get_pr_info(include_metadata=true) → pr_page in 5-page batches → targeted pr_file_chunk
3. **Large PRs (200+ files)**: get_pr_info(include_metadata=true) → pr_page in 10-page batches → focus on critical files

## 🎯 Key Rules:
- **Always start with get_pr_info(include_metadata=true) for analysis**
- **Never load all content at once - use pagination**
- **Provide feedback per batch/chunk**
- **Use exact paths/lines from previous calls**
- **Process incrementally to prevent crashes**

# 📝 Important Instructions
Do what has been asked; nothing more, nothing less.
NEVER create files unless they're absolutely necessary for achieving your goal.
ALWAYS prefer editing an existing file to creating a new one.
NEVER proactively create documentation files (*.md) or README files. Only create documentation files if explicitly requested by the User.

IMPORTANT: This MCP server uses a memory-safe, Claude-driven pagination system. You MUST follow the exact workflow above to prevent system crashes and provide efficient PR reviews.
