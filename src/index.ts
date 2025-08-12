#!/usr/bin/env node

import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
  Tool,
} from "@modelcontextprotocol/sdk/types.js";

import { AWSAuthManager } from "./auth/aws-auth.js";
import { RepositoryService } from "./services/repository-service.js";
import { PullRequestService } from "./services/pull-request-service.js";
import { MCPConfig } from "./types/index.js";
import { handleAWSError, retryWithBackoff } from "./utils/error-handler.js";
import { createPaginationOptions, getAllPages } from "./utils/pagination.js";
import { IntelligentDiffAnalyzer } from "./utils/intelligent-diff-analyzer.js";

class AWSPRReviewerServer {
  private server: Server;
  private authManager: AWSAuthManager;
  private repositoryService: RepositoryService;
  private pullRequestService: PullRequestService;
  private diffAnalyzer: IntelligentDiffAnalyzer;

  constructor() {
    this.server = new Server(
      {
        name: "aws-pr-reviewer",
        version: "1.0.0",
      },
      {
        capabilities: {
          tools: {},
        },
      }
    );

    const config: MCPConfig = {
      awsProfile: process.env.AWS_PROFILE,
      awsAccessKeyId: process.env.AWS_ACCESS_KEY_ID,
      awsSecretAccessKey: process.env.AWS_SECRET_ACCESS_KEY,
      awsSessionToken: process.env.AWS_SESSION_TOKEN,
      region: process.env.AWS_REGION || "us-east-1",
    };

    this.authManager = new AWSAuthManager(config);
    this.repositoryService = new RepositoryService(this.authManager);
    this.pullRequestService = new PullRequestService(this.authManager);
    this.diffAnalyzer = new IntelligentDiffAnalyzer(this.repositoryService);

    this.setupToolHandlers();
  }

  private setupToolHandlers() {
    this.server.setRequestHandler(ListToolsRequestSchema, async () => {
      return {
        tools: [
          // RECOMMENDED PR REVIEW WORKFLOW:
          // 1. repos_list → find repository
          // 2. prs_list → find PR to review
          // 3. pr_get → get PR details & extract mergeBase + sourceCommit from targets[0]
          // 4. diff_get → identify changed files (use mergeBase as beforeCommitSpecifier)
          // 5. batch_diff_analyze → get intelligent recommendations for all files (max 3-5 files per call)
          // 6. Based on recommendations:
          //    - file_diff_analyze → for detailed line-by-line analysis
          //    - file_get → for full context, CRITICAL: for modified files (M) ALWAYS provide beforeCommitId=mergeBase
          // 7. comment_post → add reviews (use mergeBase as beforeCommitId for line accuracy)
          //
          // IMPORTANT: For modified files, file_get MUST include beforeCommitId to show what changed!
          // This workflow ensures efficient, accurate analysis with proper line mapping.

          // Repository Management Tools
          {
            name: "repos_list",
            description:
              "Lists all AWS CodeCommit repositories you have access to. Use this when: 1) Starting a code review session to see available repos, 2) User asks about repositories, 3) Need to find a specific repo by name. Returns repository metadata including name, ID, description, default branch, creation date, and clone URLs. Supports search filtering and pagination for large lists. Essential first step for any repository operations.",
            inputSchema: {
              type: "object",
              properties: {
                searchTerm: {
                  type: "string",
                  description:
                    "Filter repositories by name or description (case-insensitive substring match). Use when user mentions a specific repo name or wants to find repos containing certain keywords.",
                },
                nextToken: {
                  type: "string",
                  description:
                    "Pagination token from previous response. Only use when you need to fetch more results after receiving a nextToken in the response.",
                },
                maxResults: {
                  type: "number",
                  description:
                    "Number of repositories to return (1-1000). Default 100. Use smaller values for quick overviews, larger for comprehensive lists.",
                },
              },
            },
          },
          {
            name: "repo_get",
            description:
              "Gets detailed information about a specific repository including metadata, default branch, clone URLs, creation date, and description. Use this when: 1) User asks about a specific repository, 2) Need repo details before operations, 3) Want to show repo information. Provides complete repository context needed for code review and PR operations.",
            inputSchema: {
              type: "object",
              properties: {
                repositoryName: {
                  type: "string",
                  description:
                    "Exact name of the AWS CodeCommit repository. Must match exactly as shown in repository listings. Required for all repository-specific operations.",
                },
              },
              required: ["repositoryName"],
            },
          },
          {
            name: "branches_list",
            description:
              "Lists all branches in a repository with their latest commit IDs. Use this when: 1) Starting PR review to see available branches, 2) User asks about branches, 3) Need to find source/target branches for PRs, 4) Checking branch structure. Essential for understanding repository branch topology and selecting correct branches for comparisons and PRs.",
            inputSchema: {
              type: "object",
              properties: {
                repositoryName: {
                  type: "string",
                  description:
                    "Repository name to list branches from. Must be exact repository name from repo listings.",
                },
                nextToken: {
                  type: "string",
                  description:
                    "Pagination token for fetching additional branches if repository has many branches.",
                },
              },
              required: ["repositoryName"],
            },
          },
          {
            name: "branch_get",
            description:
              "Gets detailed information about a specific branch including its latest commit ID and commit details. Use when: 1) Need specific branch information, 2) Want to see latest commit on a branch, 3) Validating branch exists before creating PRs. Provides branch head commit ID needed for PR operations and comparisons.",
            inputSchema: {
              type: "object",
              properties: {
                repositoryName: {
                  type: "string",
                  description: "Repository containing the branch",
                },
                branchName: {
                  type: "string",
                  description:
                    'Exact branch name (e.g., "main", "develop", "feature/new-feature"). Case-sensitive and must match exactly.',
                },
              },
              required: ["repositoryName", "branchName"],
            },
          },
          {
            name: "file_get",
            description:
              "Retrieves complete file content with exact line numbers that match AWS Console display, plus git diff comparison for modified files. CRITICAL FOR MODIFIED FILES: When analyzing modified files (M), you MUST provide beforeCommitId (typically mergeBase from PR) to get both the full current file content AND detailed diff showing exactly which lines were modified. This ensures you know precisely what changed for accurate code review and comment positioning. Returns file content with numbered lines (1-based indexing) plus diff analysis when beforeCommitId is provided. Use strategically: 1) For modified files - ALWAYS include beforeCommitId to see what changed, 2) For new files (A) or deleted files (D), 3) When you need full context beyond diff changes, 4) For small files where full content aids understanding. Line numbers in response match exactly what AWS Console shows for accurate comment positioning.",
            inputSchema: {
              type: "object",
              properties: {
                repositoryName: {
                  type: "string",
                  description: "Repository containing the file",
                },
                commitSpecifier: {
                  type: "string",
                  description:
                    'Branch name (e.g., "main", "develop") or specific commit ID. Use branch names for latest version, commit IDs for specific versions.',
                },
                filePath: {
                  type: "string",
                  description:
                    'Full path to file from repository root (e.g., "src/main.py", "docs/README.md"). Use forward slashes, no leading slash.',
                },
                beforeCommitId: {
                  type: "string",
                  description:
                    "REQUIRED for modified files (M): Base commit ID to compare against (typically mergeBase from PR targets). When provided, response includes both numbered file content AND comprehensive diff analysis showing exactly which lines were added, removed, or modified. This is essential for understanding what changed in the files for accurate code review.",
                },
                includeLineNumbers: {
                  type: "boolean",
                  description:
                    "Optional: Include line numbers in file content (default: true). Line numbers match AWS Console display exactly for accurate comment positioning.",
                },
                chunkOffset: {
                  type: "number",
                  description:
                    "Optional: Starting line number for chunked response (1-based). Use with chunkLimit for large files. For diff chunking, this represents the hunk number.",
                },
                chunkLimit: {
                  type: "number",
                  description:
                    "Optional: Maximum number of lines to return starting from chunkOffset. For diff chunking, this represents number of hunks to return. Use 500-1000 for optimal performance.",
                },
              },
              required: ["repositoryName", "commitSpecifier", "filePath"],
            },
          },
          {
            name: "folder_get",
            description:
              "Lists all files and subdirectories in a folder at specific commit/branch. Essential for: 1) Exploring repository structure, 2) Finding files for review, 3) Understanding project organization, 4) Discovering relevant files for PRs. Returns list of files with paths, blob IDs, and file modes. Use to navigate repository structure before detailed file analysis.",
            inputSchema: {
              type: "object",
              properties: {
                repositoryName: {
                  type: "string",
                  description: "Repository to explore",
                },
                commitSpecifier: {
                  type: "string",
                  description:
                    "Branch name or commit ID to get folder contents from",
                },
                folderPath: {
                  type: "string",
                  description:
                    'Path to folder from repository root (e.g., "src", "docs/api", ""). Use empty string for root directory.',
                },
              },
              required: ["repositoryName", "commitSpecifier", "folderPath"],
            },
          },
          {
            name: "commit_get",
            description:
              "Gets comprehensive details about a specific commit including message, author, committer, timestamp, parent commits, and tree ID. Use when: 1) Analyzing commit in PR, 2) Understanding commit history, 3) Getting commit metadata for review, 4) Investigating specific changes. Provides full commit context needed for thorough code review.",
            inputSchema: {
              type: "object",
              properties: {
                repositoryName: {
                  type: "string",
                  description: "Repository containing the commit",
                },
                commitId: {
                  type: "string",
                  description:
                    "Full commit SHA ID (40-character hex string). Get from branch info, PR details, or git history.",
                },
              },
              required: ["repositoryName", "commitId"],
            },
          },
          {
            name: "diff_get",
            description:
              "Gets high-level file differences between commits/branches showing which files changed (A/D/M) with paths and blob IDs. ESSENTIAL FIRST STEP for PR reviews. Provides the foundation for deeper analysis - use this to identify changed files, then follow up with batch_diff_analyze for intelligent recommendations on analysis approach, or file_diff_analyze for detailed line-by-line changes of specific files. The starting point that informs your analysis strategy.",
            inputSchema: {
              type: "object",
              properties: {
                repositoryName: {
                  type: "string",
                  description: "Repository to compare",
                },
                beforeCommitSpecifier: {
                  type: "string",
                  description:
                    "Base commit/branch (what you're comparing FROM). For PR reviews, use mergeBase from PR targets, not destinationCommit.",
                },
                afterCommitSpecifier: {
                  type: "string",
                  description:
                    "Compare commit/branch (what you're comparing TO). For PR reviews, use sourceCommit from PR targets.",
                },
                beforePath: {
                  type: "string",
                  description:
                    "Optional: Filter differences to specific path in before commit. Use to focus on specific directories or files.",
                },
                afterPath: {
                  type: "string",
                  description:
                    "Optional: Filter differences to specific path in after commit. Use to focus on specific directories or files.",
                },
                nextToken: {
                  type: "string",
                  description:
                    "Pagination token for large changesets with many file differences.",
                },
              },
              required: [
                "repositoryName",
                "beforeCommitSpecifier",
                "afterCommitSpecifier",
              ],
            },
          },
          {
            name: "file_diff_analyze",
            description:
              "Performs intelligent analysis of a single file's changes with git diff format and exact line numbers matching AWS Console. Essential for code review when you need to understand what exactly changed in a specific file. Provides line-by-line diff with precise line numbers (1-based indexing), change complexity analysis, and smart recommendations on whether full file context is needed or if focused diff is sufficient. Line numbers in response match exactly what AWS Console displays for accurate comment positioning.",
            inputSchema: {
              type: "object",
              properties: {
                repositoryName: {
                  type: "string",
                  description: "Repository containing the file",
                },
                beforeCommitId: {
                  type: "string",
                  description:
                    "Commit ID to compare from (use mergeBase from PR for accurate line mapping)",
                },
                afterCommitId: {
                  type: "string",
                  description:
                    "Commit ID to compare to (use sourceCommit from PR)",
                },
                filePath: {
                  type: "string",
                  description: "Path to the specific file to analyze",
                },
                changeType: {
                  type: "string",
                  enum: ["A", "D", "M"],
                  description:
                    "Change type from diff_get: A=Added, D=Deleted, M=Modified",
                },
              },
              required: [
                "repositoryName",
                "beforeCommitId",
                "afterCommitId",
                "filePath",
                "changeType",
              ],
            },
          },
          {
            name: "batch_diff_analyze",
            description:
              "Analyzes multiple files from a PR diff and provides intelligent batch recommendations with git diff format and exact line numbers. IMPORTANT: Process 3-5 files maximum per call to avoid memory/context overload. Perfect for PR review workflow - use this after diff_get to get smart analysis of changed files. Returns git diff format with precise line numbers matching AWS Console, plus change complexity assessment, context requirements, and strategic guidance on which files need full context vs focused diff analysis. For large PRs, make multiple calls with 3-5 files each.",
            inputSchema: {
              type: "object",
              properties: {
                repositoryName: {
                  type: "string",
                  description: "Repository name",
                },
                beforeCommitId: {
                  type: "string",
                  description:
                    "Base commit ID (use mergeBase from PR targets for accurate analysis)",
                },
                afterCommitId: {
                  type: "string",
                  description:
                    "Compare commit ID (use sourceCommit from PR targets)",
                },
                fileDifferences: {
                  type: "array",
                  description:
                    "Array of file differences from diff_get response",
                  items: {
                    type: "object",
                    properties: {
                      changeType: { type: "string", enum: ["A", "D", "M"] },
                      beforeBlob: {
                        type: "object",
                        properties: {
                          path: { type: "string" },
                          blobId: { type: "string" },
                        },
                      },
                      afterBlob: {
                        type: "object",
                        properties: {
                          path: { type: "string" },
                          blobId: { type: "string" },
                        },
                      },
                    },
                  },
                },
              },
              required: [
                "repositoryName",
                "beforeCommitId",
                "afterCommitId",
                "fileDifferences",
              ],
            },
          },

          // Pull Request Management Tools
          {
            name: "prs_list",
            description:
              "Lists pull requests in a repository by status (OPEN/CLOSED). Use when: 1) Starting review session to see active PRs, 2) User asks about PRs, 3) Finding specific PR to review, 4) Getting overview of repository PR activity. Returns PR IDs that you must use with pr_get to get full details. Always follow with pr_get for each PR you need to analyze.",
            inputSchema: {
              type: "object",
              properties: {
                repositoryName: {
                  type: "string",
                  description: "Repository to list PRs from",
                },
                pullRequestStatus: {
                  type: "string",
                  enum: ["OPEN", "CLOSED"],
                  description:
                    "OPEN for active PRs needing review, CLOSED for completed/abandoned PRs. Use OPEN by default for review workflow.",
                },
                nextToken: {
                  type: "string",
                  description:
                    "Pagination token for repositories with many PRs",
                },
              },
              required: ["repositoryName"],
            },
          },
          {
            name: "pr_get",
            description:
              "Gets complete PR details with critical commit IDs needed for accurate analysis. ESSENTIAL SECOND STEP after prs_list. Provides mergeBase (use for beforeCommitId in diff analysis) and sourceCommit/destinationCommit from targets array. Extract these commit IDs to use with diff_get → batch_diff_analyze → targeted file analysis workflow. The foundation for all subsequent PR analysis - provides the commit references that ensure accurate line mapping and change detection.",
            inputSchema: {
              type: "object",
              properties: {
                pullRequestId: {
                  type: "string",
                  description:
                    'PR ID from prs_list or user reference. Usually numeric string like "123" or "45".',
                },
              },
              required: ["pullRequestId"],
            },
          },
          {
            name: "pr_create",
            description:
              "Creates a new pull request from source branch to destination branch. Use when: 1) User wants to create PR, 2) Proposing code changes, 3) Starting review process for branch changes. Requires clear title, description, and valid source/destination branches. Returns created PR details with ID for further operations.",
            inputSchema: {
              type: "object",
              properties: {
                repositoryName: {
                  type: "string",
                  description: "Repository to create PR in",
                },
                title: {
                  type: "string",
                  description:
                    'Clear, descriptive PR title summarizing the changes (e.g., "Add user authentication feature", "Fix memory leak in parser")',
                },
                description: {
                  type: "string",
                  description:
                    "Detailed PR description explaining what changed, why, testing done, etc. Should provide context for reviewers.",
                },
                sourceReference: {
                  type: "string",
                  description:
                    'Source branch name containing changes to merge (e.g., "feature/auth", "bugfix/parser"). Must exist and have commits ahead of target.',
                },
                destinationReference: {
                  type: "string",
                  description:
                    'Target branch to merge into (e.g., "main", "develop"). Usually main development branch.',
                },
                clientRequestToken: {
                  type: "string",
                  description:
                    "Optional unique token to prevent duplicate PR creation. Use UUID or timestamp if provided.",
                },
              },
              required: [
                "repositoryName",
                "title",
                "sourceReference",
                "destinationReference",
              ],
            },
          },
          {
            name: "pr_update_title",
            description:
              "Updates pull request title. Use when: 1) PR title needs correction, 2) Title doesn't reflect changes, 3) User requests title change. Automatically updates PR and returns updated PR details. Use clear, descriptive titles that summarize the changes.",
            inputSchema: {
              type: "object",
              properties: {
                pullRequestId: {
                  type: "string",
                  description: "PR ID to update title for",
                },
                title: {
                  type: "string",
                  description:
                    "New title that clearly describes the PR changes",
                },
              },
              required: ["pullRequestId", "title"],
            },
          },
          {
            name: "pr_update_desc",
            description:
              "Updates pull request description. Use when: 1) PR description needs more detail, 2) Changes in scope/approach, 3) Adding context for reviewers. Provide comprehensive description explaining what changed, why, how to test, and any notes for reviewers.",
            inputSchema: {
              type: "object",
              properties: {
                pullRequestId: {
                  type: "string",
                  description: "PR ID to update description for",
                },
                description: {
                  type: "string",
                  description:
                    "New detailed description providing context, rationale, testing notes, and reviewer guidance",
                },
              },
              required: ["pullRequestId", "description"],
            },
          },
          {
            name: "pr_close",
            description:
              "Closes a pull request without merging. Use when: 1) PR is abandoned/obsolete, 2) Changes no longer needed, 3) Superseded by another PR, 4) User requests closure. Permanently closes PR - cannot be merged after closing but can be reopened if needed.",
            inputSchema: {
              type: "object",
              properties: {
                pullRequestId: {
                  type: "string",
                  description: "PR ID to close",
                },
              },
              required: ["pullRequestId"],
            },
          },
          {
            name: "pr_reopen",
            description:
              "Reopens a previously closed pull request. Use when: 1) Closed PR needs to be active again, 2) Premature closure, 3) Reviving abandoned changes. Only works on closed PRs - cannot reopen merged PRs.",
            inputSchema: {
              type: "object",
              properties: {
                pullRequestId: {
                  type: "string",
                  description: "Previously closed PR ID to reopen",
                },
              },
              required: ["pullRequestId"],
            },
          },

          // Comment and Review Tools
          {
            name: "comments_get",
            description:
              "Gets all comments on a pull request including general comments and line-specific comments. CRITICAL for PR review workflow. Use when: 1) Starting PR review to see existing feedback, 2) Understanding review conversation, 3) Checking if issues already raised. Returns comment threads with author, content, timestamps, and locations.",
            inputSchema: {
              type: "object",
              properties: {
                pullRequestId: {
                  type: "string",
                  description: "PR ID to get comments from",
                },
                repositoryName: {
                  type: "string",
                  description: "Repository containing the PR",
                },
                beforeCommitId: {
                  type: "string",
                  description:
                    "Optional: Before commit ID to filter comments to specific commit range. Use mergeBase from PR details.",
                },
                afterCommitId: {
                  type: "string",
                  description:
                    "Optional: After commit ID to filter comments to specific commit range. Use sourceCommit from PR details.",
                },
                nextToken: {
                  type: "string",
                  description: "Pagination for PRs with many comments",
                },
              },
              required: ["pullRequestId", "repositoryName"],
            },
          },
          {
            name: "comment_post",
            description:
              "Posts a comment on pull request - either general PR comment or line-specific code comment. Use when: 1) Providing PR feedback, 2) Asking questions about changes, 3) Suggesting improvements, 4) Highlighting specific code issues. Can post on specific lines by providing filePath and filePosition for targeted feedback.",
            inputSchema: {
              type: "object",
              properties: {
                pullRequestId: {
                  type: "string",
                  description: "PR ID to comment on",
                },
                repositoryName: {
                  type: "string",
                  description: "Repository containing the PR",
                },
                beforeCommitId: {
                  type: "string",
                  description:
                    "Before commit ID from PR details. For line-specific comments, use mergeBase from PR targets. For general comments, use destinationCommit. Required for all comments.",
                },
                afterCommitId: {
                  type: "string",
                  description:
                    "After commit ID from PR details. Use sourceCommit from PR targets. Required for all comments.",
                },
                content: {
                  type: "string",
                  description:
                    "Comment text. Be specific, constructive, and helpful. For line comments, reference the specific code issue.",
                },
                filePath: {
                  type: "string",
                  description:
                    'Optional: File path for line-specific comment (e.g., "src/main.py"). Omit for general PR comment.',
                },
                filePosition: {
                  type: "number",
                  description:
                    "Optional: Line number for line-specific comment. Use with filePath for precise code feedback.",
                },
                relativeFileVersion: {
                  type: "string",
                  enum: ["BEFORE", "AFTER"],
                  description:
                    "Optional: BEFORE for original file version, AFTER for changed file version. Use AFTER for comments on new/modified code.",
                },
                clientRequestToken: {
                  type: "string",
                  description:
                    "Optional: Unique token to prevent duplicate comments",
                },
              },
              required: [
                "pullRequestId",
                "repositoryName",
                "beforeCommitId",
                "afterCommitId",
                "content",
              ],
            },
          },
          {
            name: "comment_update",
            description:
              "Updates existing comment content. Use when: 1) Comment needs correction, 2) Adding more information, 3) Clarifying feedback. Can edit your own comments to improve clarity or add details after further analysis.",
            inputSchema: {
              type: "object",
              properties: {
                commentId: {
                  type: "string",
                  description: "Comment ID from comments_get response",
                },
                content: {
                  type: "string",
                  description:
                    "Updated comment content with corrections or additional information",
                },
              },
              required: ["commentId", "content"],
            },
          },
          {
            name: "comment_delete",
            description:
              "Deletes a comment (marks as deleted, preserves comment thread structure). Use when: 1) Comment is incorrect/inappropriate, 2) No longer relevant, 3) Duplicate feedback. Use sparingly - editing is usually better than deleting.",
            inputSchema: {
              type: "object",
              properties: {
                commentId: {
                  type: "string",
                  description: "Comment ID to delete",
                },
              },
              required: ["commentId"],
            },
          },
          {
            name: "comment_reply",
            description:
              "Replies to an existing comment, creating a threaded conversation. Use when: 1) Responding to questions, 2) Continuing discussion, 3) Addressing feedback, 4) Clarifying points. Maintains comment thread context for organized discussions.",
            inputSchema: {
              type: "object",
              properties: {
                pullRequestId: {
                  type: "string",
                  description: "PR containing the original comment",
                },
                repositoryName: {
                  type: "string",
                  description: "Repository containing the PR",
                },
                beforeCommitId: {
                  type: "string",
                  description:
                    "Before commit ID from PR details. Use mergeBase from PR targets.",
                },
                afterCommitId: {
                  type: "string",
                  description:
                    "After commit ID from PR details. Use sourceCommit from PR targets.",
                },
                inReplyTo: {
                  type: "string",
                  description:
                    "Comment ID you're replying to (from comments_get)",
                },
                content: {
                  type: "string",
                  description: "Reply content addressing the original comment",
                },
                clientRequestToken: {
                  type: "string",
                  description: "Optional: Unique token for reply",
                },
              },
              required: [
                "pullRequestId",
                "repositoryName",
                "beforeCommitId",
                "afterCommitId",
                "inReplyTo",
                "content",
              ],
            },
          },

          // Approval and Review State Tools
          {
            name: "approvals_get",
            description:
              "Gets current approval states for a pull request showing who approved/revoked and current status. Use when: 1) Checking if PR ready to merge, 2) Understanding approval status, 3) Seeing who reviewed. Critical for merge decisions and understanding PR approval workflow.",
            inputSchema: {
              type: "object",
              properties: {
                pullRequestId: {
                  type: "string",
                  description: "PR ID to check approvals for",
                },
                revisionId: {
                  type: "string",
                  description:
                    "PR revision ID from pr_get response. Approvals are tied to specific revisions.",
                },
              },
              required: ["pullRequestId", "revisionId"],
            },
          },
          {
            name: "approval_set",
            description:
              "Approve or revoke approval for a pull request. Use when: 1) PR looks good and ready to merge (APPROVE), 2) Found issues and withdrawing approval (REVOKE), 3) Completing code review process. Your approval/revoke affects whether PR can be merged based on approval rules.",
            inputSchema: {
              type: "object",
              properties: {
                pullRequestId: {
                  type: "string",
                  description: "PR ID to approve or revoke",
                },
                revisionId: {
                  type: "string",
                  description: "PR revision ID from pr_get response",
                },
                approvalStatus: {
                  type: "string",
                  enum: ["APPROVE", "REVOKE"],
                  description:
                    "APPROVE if code review passed and PR ready to merge, REVOKE if issues found or approval withdrawn",
                },
              },
              required: ["pullRequestId", "revisionId", "approvalStatus"],
            },
          },
          {
            name: "approval_rules_check",
            description:
              "Evaluates if pull request meets all approval rules (required approvers, approval counts, etc.). Use when: 1) Checking if PR can be merged, 2) Understanding why PR blocked, 3) Validating approval requirements. Shows which rules are satisfied and which need attention.",
            inputSchema: {
              type: "object",
              properties: {
                pullRequestId: {
                  type: "string",
                  description: "PR ID to evaluate approval rules for",
                },
                revisionId: {
                  type: "string",
                  description: "PR revision ID from pr_get response",
                },
              },
              required: ["pullRequestId", "revisionId"],
            },
          },

          // Merge Management Tools
          {
            name: "merge_conflicts_check",
            description:
              "Checks for merge conflicts between source and destination branches before attempting merge. Use when: 1) Before merging PR, 2) Understanding why merge failed, 3) Planning conflict resolution. Shows if merge is clean or has conflicts requiring resolution.",
            inputSchema: {
              type: "object",
              properties: {
                repositoryName: {
                  type: "string",
                  description: "Repository containing the branches",
                },
                destinationCommitSpecifier: {
                  type: "string",
                  description:
                    'Target branch or commit (e.g., "main", "develop") that changes will merge into',
                },
                sourceCommitSpecifier: {
                  type: "string",
                  description:
                    "Source branch or commit containing changes to merge",
                },
                mergeOption: {
                  type: "string",
                  enum: [
                    "FAST_FORWARD_MERGE",
                    "SQUASH_MERGE",
                    "THREE_WAY_MERGE",
                  ],
                  description:
                    "Merge strategy: FAST_FORWARD_MERGE (linear), SQUASH_MERGE (single commit), THREE_WAY_MERGE (preserve history)",
                },
              },
              required: [
                "repositoryName",
                "destinationCommitSpecifier",
                "sourceCommitSpecifier",
                "mergeOption",
              ],
            },
          },
          {
            name: "merge_options_get",
            description:
              "Gets available merge strategies for a pull request based on branch relationship and repository settings. Use when: 1) Planning PR merge, 2) Understanding merge options, 3) Before attempting merge. Shows which merge types (fast-forward, squash, three-way) are available.",
            inputSchema: {
              type: "object",
              properties: {
                repositoryName: {
                  type: "string",
                  description: "Repository containing the PR",
                },
                sourceCommitSpecifier: {
                  type: "string",
                  description: "Source branch/commit from PR details",
                },
                destinationCommitSpecifier: {
                  type: "string",
                  description: "Destination branch/commit from PR details",
                },
              },
              required: [
                "repositoryName",
                "sourceCommitSpecifier",
                "destinationCommitSpecifier",
              ],
            },
          },
          {
            name: "pr_merge",
            description:
              "Merges an approved pull request using specified merge strategy. Use when: 1) PR approved and ready to merge, 2) No conflicts exist, 3) All approval rules satisfied. IMPORTANT: This permanently merges changes into target branch. Verify approval status first.",
            inputSchema: {
              type: "object",
              properties: {
                pullRequestId: {
                  type: "string",
                  description: "Approved PR ID to merge",
                },
                repositoryName: {
                  type: "string",
                  description: "Repository containing the PR",
                },
                mergeOption: {
                  type: "string",
                  enum: [
                    "FAST_FORWARD_MERGE",
                    "SQUASH_MERGE",
                    "THREE_WAY_MERGE",
                  ],
                  description:
                    "FAST_FORWARD_MERGE: linear history, SQUASH_MERGE: single commit, THREE_WAY_MERGE: preserve branch history",
                },
                commitMessage: {
                  type: "string",
                  description:
                    "Optional: Custom merge commit message. Use for SQUASH_MERGE and THREE_WAY_MERGE to describe the merge.",
                },
                authorName: {
                  type: "string",
                  description: "Optional: Author name for merge commit",
                },
                email: {
                  type: "string",
                  description: "Optional: Author email for merge commit",
                },
              },
              required: ["pullRequestId", "repositoryName", "mergeOption"],
            },
          },

          // AWS Credential Management Tools
          {
            name: "aws_creds_refresh",
            description:
              "Manually refreshes AWS credentials (normally auto-refreshed every 7.5 hours). Use when: 1) Credentials expired, 2) Getting authentication errors, 3) Switched AWS configuration, 4) Testing credential validity. Reloads from configured source (profile/environment).",
            inputSchema: {
              type: "object",
              properties: {},
            },
          },
          {
            name: "aws_profile_switch",
            description:
              "Switches to different AWS profile for accessing different AWS accounts/roles. Use when: 1) Need to access different AWS account, 2) Switch between environments (dev/prod), 3) Use different IAM roles. Automatically refreshes credentials for new profile.",
            inputSchema: {
              type: "object",
              properties: {
                profileName: {
                  type: "string",
                  description:
                    'AWS profile name from ~/.aws/credentials or ~/.aws/config (e.g., "default", "production", "dev")',
                },
              },
              required: ["profileName"],
            },
          },
          {
            name: "aws_profiles_list",
            description:
              "Lists all available AWS profiles configured in ~/.aws/credentials. Use when: 1) User wants to switch profiles, 2) Checking available AWS accounts, 3) Troubleshooting authentication. Shows profile names that can be used with aws_profile_switch.",
            inputSchema: {
              type: "object",
              properties: {},
            },
          },
          {
            name: "aws_creds_status",
            description:
              "Shows current AWS credentials status including validity, expiration time, and access key info. Use when: 1) Troubleshooting authentication issues, 2) Checking if credentials expired, 3) Verifying correct AWS account. Helps diagnose credential-related problems.",
            inputSchema: {
              type: "object",
              properties: {},
            },
          },
        ] as Tool[],
      };
    });

    this.server.setRequestHandler(CallToolRequestSchema, async (request) => {
      const { name, arguments: args } = request.params;

      if (!args) {
        throw new Error("No arguments provided");
      }

      try {
        switch (name) {
          // Repository Management Tools
          case "repos_list":
            return await retryWithBackoff(async () => {
              const paginationOptions = createPaginationOptions(
                args.nextToken as string,
                args.maxResults as number
              );
              if (args.searchTerm) {
                const result = await this.repositoryService.searchRepositories(
                  args.searchTerm as string,
                  paginationOptions
                );
                return {
                  content: [
                    { type: "text", text: JSON.stringify(result, null, 2) },
                  ],
                };
              } else {
                const result = await this.repositoryService.listRepositories(
                  paginationOptions
                );
                return {
                  content: [
                    { type: "text", text: JSON.stringify(result, null, 2) },
                  ],
                };
              }
            });

          case "repo_get":
            return await retryWithBackoff(async () => {
              const result = await this.repositoryService.getRepository(
                args.repositoryName as string
              );
              return {
                content: [
                  { type: "text", text: JSON.stringify(result, null, 2) },
                ],
              };
            });

          case "branches_list":
            return await retryWithBackoff(async () => {
              const paginationOptions = createPaginationOptions(
                args.nextToken as string,
                args.maxResults as number
              );
              const result = await this.repositoryService.listBranches(
                args.repositoryName as string,
                paginationOptions
              );
              return {
                content: [
                  { type: "text", text: JSON.stringify(result, null, 2) },
                ],
              };
            });

          case "branch_get":
            return await retryWithBackoff(async () => {
              const result = await this.repositoryService.getBranch(
                args.repositoryName as string,
                args.branchName as string
              );
              return {
                content: [
                  { type: "text", text: JSON.stringify(result, null, 2) },
                ],
              };
            });

          case "file_get":
            return await retryWithBackoff(async () => {
              const fileResult = await this.repositoryService.getFile(
                args.repositoryName as string,
                args.commitSpecifier as string,
                args.filePath as string
              );

              const MAX_FILE_SIZE = 50000; // 50KB character limit
              const MAX_DIFF_SIZE = 100000; // 100KB diff limit
              const fileSize = fileResult.content.length;

              console.error(`File ${args.filePath}: ${fileSize} characters`);

              // If beforeCommitId is provided, always prioritize diff analysis
              if (args.beforeCommitId) {
                try {
                  const diffAnalysis = await this.diffAnalyzer.analyzeFileDiff(
                    args.repositoryName as string,
                    args.beforeCommitId as string,
                    args.commitSpecifier as string,
                    args.filePath as string,
                    "M" // Assume modified for diff analysis
                  );

                  const gitDiffSize = diffAnalysis.gitDiffFormat.length;
                  console.error(`Git diff size: ${gitDiffSize} characters`);

                  // If file is large, return only diff
                  if (fileSize > MAX_FILE_SIZE) {
                    if (gitDiffSize > MAX_DIFF_SIZE) {
                      // Check if chunking is requested
                      if (
                        args.chunkOffset !== undefined &&
                        args.chunkLimit !== undefined
                      ) {
                        // Return chunked diff
                        const chunkedDiff = this.chunkGitDiff(
                          diffAnalysis.gitDiffFormat,
                          args.chunkOffset as number,
                          args.chunkLimit as number
                        );

                        const result = {
                          filePath: args.filePath,
                          fileSize,
                          gitDiffSize,
                          status: "CHUNKED_DIFF_RESPONSE",
                          message: `Returning chunk ${args.chunkOffset} with ${args.chunkLimit} hunks of git diff.`,
                          gitDiffChunk: chunkedDiff.chunk,
                          chunkInfo: {
                            chunkOffset: args.chunkOffset,
                            chunkLimit: args.chunkLimit,
                            totalHunks: chunkedDiff.totalHunks,
                            hasMore: chunkedDiff.hasMore,
                            nextChunkOffset: chunkedDiff.nextChunkOffset,
                          },
                          diffSummary: diffAnalysis.summary,
                          lineNumberMapping: diffAnalysis.lineNumberMapping,
                        };
                        return {
                          content: [
                            {
                              type: "text",
                              text: JSON.stringify(result, null, 2),
                            },
                          ],
                        };
                      } else {
                        // Even diff is too large, provide chunking info
                        const totalHunks = (
                          diffAnalysis.gitDiffFormat.match(/@@/g) || []
                        ).length;
                        const result = {
                          filePath: args.filePath,
                          fileSize,
                          gitDiffSize,
                          status: "DIFF_TOO_LARGE_FOR_SINGLE_RESPONSE",
                          message:
                            "File and diff are both too large. Use chunkOffset and chunkLimit parameters to fetch in chunks.",
                          totalLines: fileResult.content.split("\n").length,
                          totalHunks,
                          diffSummary: diffAnalysis.summary,
                          chunkingInstructions: {
                            useParameters:
                              "chunkOffset (starting hunk number, 1-based) and chunkLimit (number of hunks)",
                            example:
                              "chunkOffset: 1, chunkLimit: 5 for first 5 hunks",
                            recommendedChunkSize:
                              "3-5 hunks per request for optimal performance",
                          },
                        };
                        return {
                          content: [
                            {
                              type: "text",
                              text: JSON.stringify(result, null, 2),
                            },
                          ],
                        };
                      }
                    } else {
                      // Return diff only
                      const result = {
                        filePath: args.filePath,
                        fileSize,
                        status: "FILE_TOO_LARGE_RETURNING_DIFF_ONLY",
                        message:
                          "File is too large (>50KB). Returning git diff format only to show what changed.",
                        gitDiffFormat: diffAnalysis.gitDiffFormat,
                        totalLines: fileResult.content.split("\n").length,
                        diffSummary: diffAnalysis.summary,
                        lineNumberMapping: diffAnalysis.lineNumberMapping,
                        modificationSummary: {
                          linesAdded: diffAnalysis.summary.linesAdded,
                          linesRemoved: diffAnalysis.summary.linesRemoved,
                          totalChanges: diffAnalysis.summary.totalChanges,
                          complexity:
                            diffAnalysis.analysisRecommendation.complexity,
                          changeType:
                            "Modified (M) - git diff format only due to file size",
                        },
                      };
                      return {
                        content: [
                          {
                            type: "text",
                            text: JSON.stringify(result, null, 2),
                          },
                        ],
                      };
                    }
                  } else {
                    // File is small enough, return both content with line numbers AND diff
                    const lines = fileResult.content.split("\n");
                    const contentWithLineNumbers = lines
                      .map(
                        (line, index) =>
                          `${(index + 1).toString().padStart(4, " ")}→${line}`
                      )
                      .join("\n");

                    const result = {
                      ...fileResult,
                      contentWithLineNumbers,
                      gitDiffFormat: diffAnalysis.gitDiffFormat,
                      totalLines: lines.length,
                      lineNumberFormat:
                        "AWS Console compatible (1-based indexing)",
                      analysisType: "modified_file_with_diff",
                      diffSummary: diffAnalysis.summary,
                      lineNumberMapping: diffAnalysis.lineNumberMapping,
                      modificationSummary: {
                        linesAdded: diffAnalysis.summary.linesAdded,
                        linesRemoved: diffAnalysis.summary.linesRemoved,
                        totalChanges: diffAnalysis.summary.totalChanges,
                        complexity:
                          diffAnalysis.analysisRecommendation.complexity,
                        changeType:
                          "Modified (M) - includes both full content and git diff",
                      },
                    };

                    console.error(
                      `File analysis completed for ${args.filePath}: ${diffAnalysis.summary.totalChanges} total changes`
                    );
                    return {
                      content: [
                        { type: "text", text: JSON.stringify(result, null, 2) },
                      ],
                    };
                  }
                } catch (error) {
                  console.error("Failed to generate diff analysis:", error);
                  // Fall back to content-only if diff fails
                }
              }

              // No beforeCommitId or diff failed - return content only (with size check)
              if (fileSize > MAX_FILE_SIZE) {
                // Check if chunking is requested for content
                if (
                  args.chunkOffset !== undefined &&
                  args.chunkLimit !== undefined
                ) {
                  const lines = fileResult.content.split("\n");
                  const startLine = Math.max(1, args.chunkOffset as number);
                  const endLine = Math.min(
                    lines.length,
                    startLine + (args.chunkLimit as number) - 1
                  );

                  const chunkLines = lines.slice(startLine - 1, endLine);
                  const contentWithLineNumbers = chunkLines
                    .map(
                      (line, index) =>
                        `${(startLine + index)
                          .toString()
                          .padStart(4, " ")}→${line}`
                    )
                    .join("\n");

                  const result = {
                    filePath: args.filePath,
                    fileSize,
                    status: "CHUNKED_CONTENT_RESPONSE",
                    message: `Returning lines ${startLine}-${endLine} of ${lines.length} total lines.`,
                    contentWithLineNumbers,
                    chunkInfo: {
                      chunkOffset: startLine,
                      chunkLimit: args.chunkLimit,
                      totalLines: lines.length,
                      startLine,
                      endLine,
                      hasMore: endLine < lines.length,
                      nextChunkOffset:
                        endLine < lines.length ? endLine + 1 : undefined,
                    },
                    lineNumberFormat:
                      "AWS Console compatible (1-based indexing)",
                    analysisType: "file_content_chunk",
                  };
                  return {
                    content: [
                      { type: "text", text: JSON.stringify(result, null, 2) },
                    ],
                  };
                } else {
                  const totalLines = fileResult.content.split("\n").length;
                  const result = {
                    filePath: args.filePath,
                    fileSize,
                    status: "FILE_TOO_LARGE",
                    message:
                      "File is too large (>50KB). For modified files, provide beforeCommitId to get git diff. For new files, use chunking.",
                    totalLines,
                    recommendation:
                      "Use beforeCommitId parameter to get git diff format, or use chunkOffset/chunkLimit for content chunking",
                    chunkingInstructions: {
                      useParameters:
                        "chunkOffset (starting line number, 1-based) and chunkLimit (number of lines)",
                      example:
                        "chunkOffset: 1, chunkLimit: 500 for first 500 lines",
                      recommendedChunkSize:
                        "500-1000 lines per request for optimal performance",
                    },
                  };
                  return {
                    content: [
                      { type: "text", text: JSON.stringify(result, null, 2) },
                    ],
                  };
                }
              }

              // File is small enough, return content with line numbers
              const lines = fileResult.content.split("\n");
              const contentWithLineNumbers = lines
                .map(
                  (line, index) =>
                    `${(index + 1).toString().padStart(4, " ")}→${line}`
                )
                .join("\n");

              const result = {
                ...fileResult,
                contentWithLineNumbers,
                totalLines: lines.length,
                lineNumberFormat: "AWS Console compatible (1-based indexing)",
                analysisType: "file_only",
                warning:
                  "If this is a modified file (M), provide beforeCommitId to see git diff of what changed",
              };

              return {
                content: [
                  { type: "text", text: JSON.stringify(result, null, 2) },
                ],
              };
            });

          case "folder_get":
            return await retryWithBackoff(async () => {
              const result = await this.repositoryService.getFolder(
                args.repositoryName as string,
                args.commitSpecifier as string,
                args.folderPath as string
              );
              return {
                content: [
                  { type: "text", text: JSON.stringify(result, null, 2) },
                ],
              };
            });

          case "commit_get":
            return await retryWithBackoff(async () => {
              const result = await this.repositoryService.getCommit(
                args.repositoryName as string,
                args.commitId as string
              );
              return {
                content: [
                  { type: "text", text: JSON.stringify(result, null, 2) },
                ],
              };
            });

          case "diff_get":
            return await retryWithBackoff(async () => {
              const paginationOptions = createPaginationOptions(
                args.nextToken as string,
                args.maxResults as number
              );
              const result = await this.repositoryService.getDifferences(
                args.repositoryName as string,
                args.beforeCommitSpecifier as string,
                args.afterCommitSpecifier as string,
                args.beforePath as string,
                args.afterPath as string,
                paginationOptions
              );
              return {
                content: [
                  { type: "text", text: JSON.stringify(result, null, 2) },
                ],
              };
            });

          case "file_diff_analyze":
            return await retryWithBackoff(async () => {
              const result = await this.diffAnalyzer.analyzeFileDiff(
                args.repositoryName as string,
                args.beforeCommitId as string,
                args.afterCommitId as string,
                args.filePath as string,
                args.changeType as "A" | "D" | "M"
              );

              const MAX_DIFF_SIZE = 100000; // 100KB limit
              const gitDiffSize = result.gitDiffFormat.length;

              if (gitDiffSize > MAX_DIFF_SIZE) {
                // Diff is too large, provide summary and chunking info
                const chunkedResult = {
                  filePath: result.filePath,
                  changeType: result.changeType,
                  gitDiffSize,
                  status: "DIFF_TOO_LARGE_FOR_SINGLE_RESPONSE",
                  message:
                    "Git diff is too large (>100KB). Use batch_diff_analyze for smaller chunks or multiple calls.",
                  diffSummary: result.summary,
                  analysisRecommendation: result.analysisRecommendation,
                  lineNumberMapping: result.lineNumberMapping,
                  chunkingRecommendation:
                    "Break analysis into smaller file batches or use specific line range requests",
                };

                console.error(
                  `Diff too large for ${args.filePath}: ${gitDiffSize} characters`
                );
                return {
                  content: [
                    {
                      type: "text",
                      text: JSON.stringify(chunkedResult, null, 2),
                    },
                  ],
                };
              }

              console.error(
                `Diff analysis for ${args.filePath}: ${gitDiffSize} characters, ${result.summary.totalChanges} changes`
              );
              return {
                content: [
                  { type: "text", text: JSON.stringify(result, null, 2) },
                ],
              };
            });

          case "batch_diff_analyze":
            return await retryWithBackoff(async () => {
              const fileDifferences = args.fileDifferences as any[];

              // Enforce 3-5 file limit
              if (fileDifferences.length > 5) {
                const result = {
                  status: "TOO_MANY_FILES",
                  message: `Received ${fileDifferences.length} files. Maximum 5 files per batch to avoid memory/context overload.`,
                  recommendedBatches: Math.ceil(fileDifferences.length / 5),
                  suggestion: `Split into ${Math.ceil(
                    fileDifferences.length / 5
                  )} batches of 3-5 files each`,
                  firstBatch: fileDifferences
                    .slice(0, 5)
                    .map((f) => f.afterBlob?.path || f.beforeBlob?.path),
                  remainingFiles: fileDifferences
                    .slice(5)
                    .map((f) => f.afterBlob?.path || f.beforeBlob?.path),
                };
                return {
                  content: [
                    { type: "text", text: JSON.stringify(result, null, 2) },
                  ],
                };
              }

              const result = await this.diffAnalyzer.analyzeBatchDiffs(
                args.repositoryName as string,
                args.beforeCommitId as string,
                args.afterCommitId as string,
                fileDifferences
              );

              // Check total response size
              const responseSize = JSON.stringify(result).length;
              const MAX_RESPONSE_SIZE = 200000; // 200KB limit for batch responses

              if (responseSize > MAX_RESPONSE_SIZE) {
                console.error(
                  `Batch response too large: ${responseSize} characters`
                );

                // Return summary only for large batches
                const compactResult = {
                  batchRecommendations: result.batchRecommendations,
                  files: result.analyses.map((analysis) => ({
                    filePath: analysis.filePath,
                    changeType: analysis.changeType,
                    gitDiffSize: analysis.gitDiffFormat.length,
                    diffSummary: analysis.summary,
                    analysisRecommendation: analysis.analysisRecommendation,
                    status:
                      analysis.gitDiffFormat.length > 50000
                        ? "LARGE_DIFF"
                        : "NORMAL",
                  })),
                  message:
                    "Batch analysis complete. Individual git diffs omitted due to size. Use file_diff_analyze for specific files.",
                  totalResponseSize: responseSize,
                  recommendation:
                    "Use file_diff_analyze for individual files to get full git diff format",
                };

                return {
                  content: [
                    {
                      type: "text",
                      text: JSON.stringify(compactResult, null, 2),
                    },
                  ],
                };
              }

              console.error(
                `Batch analysis complete: ${fileDifferences.length} files, ${responseSize} characters`
              );
              return {
                content: [
                  { type: "text", text: JSON.stringify(result, null, 2) },
                ],
              };
            });

          // Pull Request Management Tools
          case "prs_list":
            return await retryWithBackoff(async () => {
              const paginationOptions = createPaginationOptions(
                args.nextToken as string,
                args.maxResults as number
              );
              const result = await this.pullRequestService.listPullRequests(
                args.repositoryName as string,
                (args.pullRequestStatus as "OPEN" | "CLOSED") || "OPEN",
                paginationOptions
              );
              return {
                content: [
                  { type: "text", text: JSON.stringify(result, null, 2) },
                ],
              };
            });

          case "pr_get":
            return await retryWithBackoff(async () => {
              const result = await this.pullRequestService.getPullRequest(
                args.pullRequestId as string
              );
              return {
                content: [
                  { type: "text", text: JSON.stringify(result, null, 2) },
                ],
              };
            });

          case "pr_create":
            return await retryWithBackoff(async () => {
              const result = await this.pullRequestService.createPullRequest(
                args.repositoryName as string,
                args.title as string,
                (args.description as string) || "",
                args.sourceReference as string,
                args.destinationReference as string,
                args.clientRequestToken as string
              );
              return {
                content: [
                  { type: "text", text: JSON.stringify(result, null, 2) },
                ],
              };
            });

          case "pr_update_title":
            return await retryWithBackoff(async () => {
              const result =
                await this.pullRequestService.updatePullRequestTitle(
                  args.pullRequestId as string,
                  args.title as string
                );
              return {
                content: [
                  { type: "text", text: JSON.stringify(result, null, 2) },
                ],
              };
            });

          case "pr_update_desc":
            return await retryWithBackoff(async () => {
              const result =
                await this.pullRequestService.updatePullRequestDescription(
                  args.pullRequestId as string,
                  args.description as string
                );
              return {
                content: [
                  { type: "text", text: JSON.stringify(result, null, 2) },
                ],
              };
            });

          case "pr_close":
            return await retryWithBackoff(async () => {
              const result = await this.pullRequestService.closePullRequest(
                args.pullRequestId as string
              );
              return {
                content: [
                  { type: "text", text: JSON.stringify(result, null, 2) },
                ],
              };
            });

          case "pr_reopen":
            return await retryWithBackoff(async () => {
              const result = await this.pullRequestService.reopenPullRequest(
                args.pullRequestId as string
              );
              return {
                content: [
                  { type: "text", text: JSON.stringify(result, null, 2) },
                ],
              };
            });

          // Comment and Review Tools
          case "comments_get":
            return await retryWithBackoff(async () => {
              const paginationOptions = createPaginationOptions(
                args.nextToken as string,
                args.maxResults as number
              );
              const result = await this.pullRequestService.getComments(
                args.pullRequestId as string,
                args.repositoryName as string,
                args.beforeCommitId as string,
                args.afterCommitId as string,
                paginationOptions
              );
              return {
                content: [
                  { type: "text", text: JSON.stringify(result, null, 2) },
                ],
              };
            });

          case "comment_post":
            return await retryWithBackoff(async () => {
              const location = args.filePath
                ? {
                    filePath: args.filePath as string,
                    filePosition: args.filePosition as number,
                    relativeFileVersion: args.relativeFileVersion as
                      | "BEFORE"
                      | "AFTER",
                  }
                : undefined;

              const result = await this.pullRequestService.postComment(
                args.pullRequestId as string,
                args.repositoryName as string,
                args.beforeCommitId as string,
                args.afterCommitId as string,
                args.content as string,
                location,
                args.clientRequestToken as string
              );
              return {
                content: [
                  { type: "text", text: JSON.stringify(result, null, 2) },
                ],
              };
            });

          case "comment_update":
            return await retryWithBackoff(async () => {
              const result = await this.pullRequestService.updateComment(
                args.commentId as string,
                args.content as string
              );
              return {
                content: [
                  { type: "text", text: JSON.stringify(result, null, 2) },
                ],
              };
            });

          case "comment_delete":
            return await retryWithBackoff(async () => {
              const result = await this.pullRequestService.deleteComment(
                args.commentId as string
              );
              return {
                content: [
                  { type: "text", text: JSON.stringify(result, null, 2) },
                ],
              };
            });

          case "comment_reply":
            return await retryWithBackoff(async () => {
              const result = await this.pullRequestService.replyToComment(
                args.pullRequestId as string,
                args.repositoryName as string,
                args.beforeCommitId as string,
                args.afterCommitId as string,
                args.inReplyTo as string,
                args.content as string,
                args.clientRequestToken as string
              );
              return {
                content: [
                  { type: "text", text: JSON.stringify(result, null, 2) },
                ],
              };
            });

          // Approval and Review State Tools
          case "approvals_get":
            return await retryWithBackoff(async () => {
              const result = await this.pullRequestService.getApprovalStates(
                args.pullRequestId as string,
                args.revisionId as string
              );
              return {
                content: [
                  { type: "text", text: JSON.stringify(result, null, 2) },
                ],
              };
            });

          case "approval_set":
            return await retryWithBackoff(async () => {
              await this.pullRequestService.updateApprovalState(
                args.pullRequestId as string,
                args.revisionId as string,
                args.approvalStatus as "APPROVE" | "REVOKE"
              );
              return {
                content: [
                  {
                    type: "text",
                    text: `Approval state updated to ${args.approvalStatus}`,
                  },
                ],
              };
            });

          case "approval_rules_check":
            return await retryWithBackoff(async () => {
              const result =
                await this.pullRequestService.evaluateApprovalRules(
                  args.pullRequestId as string,
                  args.revisionId as string
                );
              return {
                content: [
                  { type: "text", text: JSON.stringify(result, null, 2) },
                ],
              };
            });

          // Merge Management Tools
          case "merge_conflicts_check":
            return await retryWithBackoff(async () => {
              const result = await this.pullRequestService.getMergeConflicts(
                args.repositoryName as string,
                args.destinationCommitSpecifier as string,
                args.sourceCommitSpecifier as string,
                args.mergeOption as
                  | "FAST_FORWARD_MERGE"
                  | "SQUASH_MERGE"
                  | "THREE_WAY_MERGE"
              );
              return {
                content: [
                  { type: "text", text: JSON.stringify(result, null, 2) },
                ],
              };
            });

          case "merge_options_get":
            return await retryWithBackoff(async () => {
              const result = await this.pullRequestService.getMergeOptions(
                args.repositoryName as string,
                args.sourceCommitSpecifier as string,
                args.destinationCommitSpecifier as string
              );
              return {
                content: [
                  { type: "text", text: JSON.stringify(result, null, 2) },
                ],
              };
            });

          case "pr_merge":
            return await retryWithBackoff(async () => {
              const result = await this.pullRequestService.mergePullRequest(
                args.pullRequestId as string,
                args.repositoryName as string,
                args.mergeOption as
                  | "FAST_FORWARD_MERGE"
                  | "SQUASH_MERGE"
                  | "THREE_WAY_MERGE",
                args.commitMessage as string,
                args.authorName as string,
                args.email as string
              );
              return {
                content: [
                  { type: "text", text: JSON.stringify(result, null, 2) },
                ],
              };
            });

          // AWS Credential Management Tools
          case "aws_creds_refresh":
            console.error("=== AWS CREDENTIALS REFRESH STARTED ===");
            await this.authManager.refreshCredentials();
            await this.reinitializeServices();
            console.error("=== AWS CREDENTIALS REFRESH COMPLETED ===");
            return {
              content: [
                {
                  type: "text",
                  text: "AWS credentials refreshed successfully and all services reinitialized",
                },
              ],
            };

          case "aws_profile_switch":
            console.error(
              `=== AWS PROFILE SWITCH TO ${args.profileName} STARTED ===`
            );
            await this.authManager.switchProfile(args.profileName as string);
            await this.reinitializeServices();
            console.error(
              `=== AWS PROFILE SWITCH TO ${args.profileName} COMPLETED ===`
            );
            return {
              content: [
                {
                  type: "text",
                  text: `Switched to AWS profile: ${args.profileName} and reinitialized all services`,
                },
              ],
            };

          case "aws_profiles_list":
            const profiles = this.authManager.getAvailableProfiles();
            return {
              content: [
                { type: "text", text: JSON.stringify(profiles, null, 2) },
              ],
            };

          case "aws_creds_status":
            const credentials = this.authManager.getCredentials();
            const isValid = this.authManager.isCredentialsValid();
            const status = {
              hasCredentials: !!credentials,
              isValid,
              accessKeyId:
                credentials?.accessKeyId?.substring(0, 8) + "..." || "Not set",
              expiration:
                credentials?.expiration?.toISOString() || "No expiration",
            };
            return {
              content: [
                { type: "text", text: JSON.stringify(status, null, 2) },
              ],
            };

          default:
            throw new Error(`Unknown tool: ${name}`);
        }
      } catch (error: any) {
        handleAWSError(error);
      }
    });
  }

  async run() {
    try {
      await this.authManager.initialize();
      const transport = new StdioServerTransport();
      await this.server.connect(transport);
      console.error("AWS PR Reviewer MCP server running on stdio");
    } catch (error) {
      console.error("Failed to start server:", error);
      process.exit(1);
    }
  }

  /**
   * Chunks a git diff into smaller pieces based on hunks
   * @param gitDiff Complete git diff string
   * @param chunkOffset Starting hunk number (1-based)
   * @param chunkLimit Number of hunks to return
   * @returns Chunked diff information
   */
  private chunkGitDiff(
    gitDiff: string,
    chunkOffset: number,
    chunkLimit: number
  ): {
    chunk: string;
    totalHunks: number;
    hasMore: boolean;
    nextChunkOffset?: number;
  } {
    const lines = gitDiff.split("\n");
    const headerLines: string[] = [];
    const hunks: string[][] = [];
    let currentHunk: string[] = [];
    let inHunk = false;

    // Separate header and hunks
    for (const line of lines) {
      if (line.startsWith("@@")) {
        if (inHunk && currentHunk.length > 0) {
          hunks.push([...currentHunk]);
        }
        currentHunk = [line];
        inHunk = true;
      } else if (inHunk) {
        currentHunk.push(line);
      } else {
        headerLines.push(line);
      }
    }

    // Add the last hunk
    if (inHunk && currentHunk.length > 0) {
      hunks.push(currentHunk);
    }

    const totalHunks = hunks.length;
    const startIndex = Math.max(0, chunkOffset - 1); // Convert to 0-based
    const endIndex = Math.min(totalHunks, startIndex + chunkLimit);

    // Build chunked response
    const chunkLines = [...headerLines];
    for (let i = startIndex; i < endIndex; i++) {
      chunkLines.push(...hunks[i]);
    }

    const hasMore = endIndex < totalHunks;
    const nextChunkOffset = hasMore ? endIndex + 1 : undefined;

    return {
      chunk: chunkLines.join("\n"),
      totalHunks,
      hasMore,
      nextChunkOffset,
    };
  }

  /**
   * Reinitializes all services with fresh auth manager
   * This ensures any cached references are cleared
   */
  private async reinitializeServices(): Promise<void> {
    console.error("Reinitializing all services with fresh auth manager...");

    // Keep the same config but force fresh initialization
    this.repositoryService = new RepositoryService(this.authManager);
    this.pullRequestService = new PullRequestService(this.authManager);
    this.diffAnalyzer = new IntelligentDiffAnalyzer(this.repositoryService);

    console.error("All services reinitialized successfully");
  }

  async shutdown() {
    this.authManager.cleanup();
  }
}

// Handle graceful shutdown
const server = new AWSPRReviewerServer();
process.on("SIGINT", async () => {
  console.error("Received SIGINT, shutting down gracefully...");
  await server.shutdown();
  process.exit(0);
});

process.on("SIGTERM", async () => {
  console.error("Received SIGTERM, shutting down gracefully...");
  await server.shutdown();
  process.exit(0);
});

// Start the server
server.run();
