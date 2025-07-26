# Smart Pagination System for Huge PRs

## Problem Solved

The original system had a **critical memory issue**:
- `all_differences.extend(differences)` loaded ALL files into memory at once
- Huge PRs (1000+ files) could crash the system
- Claude received massive responses and couldn't process incrementally

## New Claude-Driven Approach

### 🎯 **Metadata-First Strategy**
1. **`pr_metadata`** - Get PR overview without loading content
2. **`pr_page`** - Get specific pages (100 files each)  
3. **`pr_file_chunk`** - Get file content in line chunks

### 🔄 **How Claude Should Use It**

```bash
# Step 1: Get metadata first
pr_metadata(pull_request_id="25802")
# Returns: Total files: 2,500, Total pages: 25

# Step 2: Process in pages (Claude-driven)
pr_page(pull_request_id="25802", page=1)  # Files 1-100
# Review first 100 files, then:
pr_page(pull_request_id="25802", page=2)  # Files 101-200

# Step 3: For large files, chunk by lines
pr_file_chunk(pull_request_id="25802", file_path="large-file.js", start_line=1, chunk_size=500)
# Review first 500 lines, then:
pr_file_chunk(pull_request_id="25802", file_path="large-file.js", start_line=501, chunk_size=500)
```

### 📊 **Memory Usage Comparison**

| Approach | Memory Usage | Max Files | System Impact |
|----------|-------------|-----------|---------------|
| **Old System** | ALL files at once | ~500 files | 💥 Crashes |
| **New System** | 100 files per call | ♾️ Unlimited | 🟢 Safe |

### 🛡️ **Memory Safety Features**

1. **No Mass Loading**: Only loads requested page/chunk
2. **Bounded Memory**: Fixed limit per call (100 files or 500 lines)
3. **Claude-Controlled**: Claude decides what to fetch next
4. **Progress Tracking**: Shows progress (e.g., "25% of file reviewed")

### 🚀 **Recommended Workflow for Claude**

For **Small PRs** (<100 files):
```bash
pr_changes(pull_request_id="25802")  # Use existing tool
```

For **Medium PRs** (100-1000 files):
```bash
pr_metadata(pull_request_id="25802")    # Get overview
pr_page(pull_request_id="25802", page=1)  # Review in batches
```

For **Huge PRs** (1000+ files):
```bash
pr_metadata(pull_request_id="25802")    # Get overview
pr_page(pull_request_id="25802", page=1)  # Review pages 1-5
# Review and provide feedback on first 500 files
pr_page(pull_request_id="25802", page=6)  # Continue to next batch
```

For **Massive Files** (1000+ lines):
```bash
pr_file_chunk(pull_request_id="25802", file_path="huge.js", start_line=1)
# Review first 500 lines, provide feedback
pr_file_chunk(pull_request_id="25802", file_path="huge.js", start_line=501)
# Continue reviewing in chunks
```

### 🎯 **Benefits**

1. **Memory Safe**: Never crashes from large PRs
2. **Incremental Review**: Claude can provide feedback per batch
3. **User-Friendly**: Clear progress indicators
4. **Scalable**: Works with PRs of any size
5. **Efficient**: Only fetches what's needed

### 🔧 **Technical Implementation**

- **`pr_metadata`**: Fast scan (no content loading) to get totals
- **`pr_page`**: Uses AWS pagination tokens to jump to specific pages
- **`pr_file_chunk`**: Retrieves file content and slices by line numbers
- **Memory Bounds**: Each call limited to prevent memory issues

This system transforms huge PR reviews from memory-crashing operations into manageable, incremental processes that Claude can handle intelligently.