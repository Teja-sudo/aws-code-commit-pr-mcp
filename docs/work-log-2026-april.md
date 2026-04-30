# Work Log — April 2026

This document captures the work completed in the Apr 2026 modernization + audit cycle. Each item is sized for an Azure DevOps task / work item. Items are grouped into epics so they can be planned as one or split across sprints.

Branch: `main`
Final commits (newest first):

- `42df9a8` Update docs to reflect SDK-managed credential rotation
- `159f18b` Fix bugs surfaced by audit loop
- `d8d7efc` Use fromNodeProviderChain so the SDK rotates credentials
- `fc5cf99` Modernize dependencies to latest as of April 2026

PS C:\Users\sanik_unwtxkj\MyProjects\MCP servers\aws-code-commit-pr-mcp> git show 42df9a8d319a1b7b67738ec301f6de9295bc1e6e
commit 42df9a8d319a1b7b67738ec301f6de9295bc1e6e (HEAD -> main, origin/main, origin/HEAD)
Author: Teja <sanikommutejareddy@gmail.com>
Date: Wed Apr 29 21:12:22 2026 +0530

    Update docs to reflect SDK-managed credential rotation

    - README: AWS Authentication section rewritten around
      fromNodeProviderChain; setup step now documents Fargate / ECS / EKS
      / EC2 / SSO paths; comment_reply example trimmed to its real
      two-arg shape; Node 18 -> Node 20 prereq; AWSAuthManager component
      description updated.
    - CLAUDE-AI-OPTIMIZATION.md: drop the stale "Auto-refresh every 7.5
      hours" claim.
    - .env.example: drop the stale CREDENTIAL_REFRESH_INTERVAL hint;
      document that Fargate / ECS / EKS / EC2 don't need any of the env
      vars.

    Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>

diff --git a/.env.example b/.env.example
index 916398a..70a915b 100644
--- a/.env.example
+++ b/.env.example
@@ -7,6 +7,6 @@ AWS_REGION=us-east-1

# AWS_SECRET_ACCESS_KEY=your_secret_key_here

# AWS_SESSION_TOKEN=your_session_token_here

-# Optional: Override default refresh interval (in milliseconds)
-# Default is 7.5 hours (27000000ms)
-# CREDENTIAL_REFRESH_INTERVAL=27000000
\ No newline at end of file
+# In Fargate / ECS / EKS / EC2 leave the above unset — the AWS SDK reads
+# the task role / IRSA / instance profile automatically and rotates credentials
+# itself, so there is no manual refresh interval to configure.
\ No newline at end of file
diff --git a/CLAUDE-AI-OPTIMIZATION.md b/CLAUDE-AI-OPTIMIZATION.md
index 2665fc1..e2b006d 100644
--- a/CLAUDE-AI-OPTIMIZATION.md
+++ b/CLAUDE-AI-OPTIMIZATION.md
@@ -111,7 +111,7 @@ Each parameter includes:

- Optimizes batch sizes for different operations

### Credential Management

-- Auto-refresh every 7.5 hours
+- AWS SDK rotates short-lived credentials automatically between requests

- Profile switching without restart
- Status checking for troubleshooting

diff --git a/README.md b/README.md
index 622d088..401b3fd 100644
--- a/README.md
+++ b/README.md
@@ -39,12 +39,18 @@ A comprehensive Model Context Protocol (MCP) server for AWS CodeCommit that enab

- Manage approval workflows

### AWS Authentication

-- Support for AWS CLI profiles
-- Environment variable credentials
-- Session token support for temporary credentials
-- Automatic credential refresh (7.5-hour intervals)
-- Profile switching without restart
-- Credential validation and status checking
+- Uses the AWS SDK's standard Node.js credential provider chain (`fromNodeProviderChain`):

- - Environment variables
- - AWS SSO cached tokens
- - AWS CLI profiles (`~/.aws/credentials`, `~/.aws/config`)
- - `credential_process` helpers
- - **EKS IRSA** (web-identity token files)
- - **Fargate / ECS task roles** (container metadata endpoint)
- - **EC2 instance profiles** (IMDS)
    +- The SDK transparently rotates short-lived credentials between requests — no manual refresh timer
    +- Optional override of any source via static credentials passed to the constructor
    +- Profile switching at runtime via the `aws_profile_switch` tool
    +- Cross-mount WSL credential discovery (Windows-side `~/.aws/credentials` from WSL)

### Advanced Features

- Comprehensive pagination handling for large datasets
  @@ -55,8 +61,8 @@ A comprehensive Model Context Protocol (MCP) server for AWS CodeCommit that enab

## Installation

### Prerequisites

-- Node.js 18+ and npm
-- AWS CLI configured with appropriate permissions
+- Node.js 20+ and npm
+- AWS credentials available via any source supported by the AWS SDK Node.js provider chain (CLI profile, env vars, SSO, IAM role on Fargate /
ECS / EKS / EC2)

- Access to AWS CodeCommit repositories

### Setup

@@ -71,27 +77,35 @@ A comprehensive Model Context Protocol (MCP) server for AWS CodeCommit that enab
npm run build
```

-3. **Configure AWS credentials** (choose one method):

-
- **Method 1: AWS CLI Profile**
  +3. **Configure AWS credentials** — pick any source the AWS SDK already understands:

*
* **Local: AWS CLI profile**
  ```bash
  aws configure --profile your-profile-name
  ```

- ```

  ```
-
- **Method 2: Environment variables**
- ```bash
  export AWS_PROFILE=your-profile-name
  export AWS_REGION=us-east-1
  ```
-
- **Method 3: Direct credentials**

*
* **Local: direct credentials (IAM user keys or short-lived STS)**
  ```bash
  export AWS_ACCESS_KEY_ID=your-access-key
  export AWS_SECRET_ACCESS_KEY=your-secret-key
  ```

- export AWS_SESSION_TOKEN=your-session-token # if using temporary credentials

* export AWS_SESSION_TOKEN=your-session-token # only for STS / SSO
  export AWS_REGION=us-east-1

  ```

  ```

* **Local: AWS SSO**
* ```bash

  ```
* aws sso login --profile your-sso-profile
* export AWS_PROFILE=your-sso-profile
* ```

  ```
*
* **Fargate / ECS:** attach a task role with the IAM permissions below — no env vars needed.
*
* **EKS:** annotate the service account for IRSA — credentials are picked up via the projected web-identity token.
*
* **EC2:** attach an instance profile — credentials are read from IMDS automatically.
* ### WSL (Windows Subsystem for Linux) Support
  The server automatically detects WSL environments and intelligently searches for AWS credentials in both Linux and Windows locations:
  @@ -421,13 +435,9 @@ Delete a comment.
  ````

  #### `comment_reply`
  -Reply to an existing comment.
  +Reply to an existing comment. AWS scopes the reply to the parent comment automatically — no PR / commit IDs needed.
  ```json
  {
  ````

- "pullRequestId": "123",
- "repositoryName": "my-repo",
- "beforeCommitId": "abc123...",
- "afterCommitId": "def456...",
  "inReplyTo": "comment-123",
  "content": "I agree with this comment"
  }
  @@ -586,7 +596,7 @@ src/

### Key Components

-- **AWSAuthManager**: Handles AWS credential management, profile switching, and automatic refresh
+- **AWSAuthManager**: Builds the credential provider (default chain or static creds) and hands it to `CodeCommitClient`, so the SDK auto-rotat
es short-lived credentials between requests. Also handles profile switching and WSL credential discovery.

- **RepositoryService**: Manages repository operations and code access
- **PullRequestService**: Handles all PR-related operations including comments and approvals
- **Error Handling**: Comprehensive AWS-specific error handling with retry logic
  (END)

PS C:\Users\sanik_unwtxkj\MyProjects\MCP servers\aws-code-commit-pr-mcp> git show 159f18b338a14d4082e8a6f45ef106baf44b8f9e
commit 159f18b338a14d4082e8a6f45ef106baf44b8f9e
Author: Teja <sanikommutejareddy@gmail.com>
Date: Wed Apr 29 21:11:11 2026 +0530

    Fix bugs surfaced by audit loop

    Security / protocol:
    - retryWithBackoff no longer swallows errors with malformed
      {content:[{error}]} shape; lastError now propagates to handleAWSError
    - handleAWSError classifies CredentialsProviderError /
      ExpiredTokenException / ExpiredToken (was only matching legacy names);
      uses optional chaining to survive bare-string throws
    - New MCPValidationError class so input-validation throws map to 400
      instead of generic 500
    - Cap user-supplied regex patterns at 200 chars in code_search to
      reduce ReDoS surface; reject non-string patterns

    Correctness:
    - comment_reply tool inputSchema dropped four phantom required params
      (pullRequestId, repositoryName, beforeCommitId, afterCommitId);
      AWS PostCommentReply scopes the reply to the parent comment
      automatically. Service signature trimmed accordingly.
    - pull-request-service.ts now imports from "../types/index.js"
      (strict-ESM resolution)
    - getFolder("/") -> getFolder("") for AWS root (was rejected as
      FolderDoesNotExist)
    - comment_post validates filePosition is a number and
      relativeFileVersion is BEFORE/AFTER when filePath is provided
    - batch_diff_analyze validates fileDifferences is an array
    - chunkGitDiff returns a sane header-only response for binary / empty
      diffs (was silently dropping metadata)
    - aws_creds_status no longer renders "undefined...undefined" when no
      credentials are loaded (|| precedence bug)
    - searchRepositories paginates across all pages (cap 20 = ~2k repos)
      instead of filtering only the first
    - listRepositories stops fabricating undefined for fields the AWS
      ListRepositories API doesn't return
    - generateProperGitDiff uses sha1(content) for the index hash so
      consecutive runs produce identical output
    - performLineDiffWithLibrary's lines.pop() only fires when value
      actually ends with \n (was off-by-one for content without trailing
      newline)
    - getAvailableProfiles reads ~/.aws/config too, stripping the
      "profile " prefix (was missing every profile defined there)
    - Empty-args MCP requests no longer rejected (tools with empty
      inputSchema like aws_creds_refresh need to be callable with no args)
    - Server serverInfo.version now read from package.json at startup
      (was hardcoded 1.0.0)
    - SIGINT / SIGTERM handlers register only after \`await server.run()\`
      resolves, so signals during init can no longer tear down half-built
      state

    Cleanup (~840 lines of dead code, all verified to have zero callers
    in src/):
    - 8 unused private methods + 1 unused interface in
      intelligent-diff-analyzer.ts
    - 4 unused public methods in line-position-calculator.ts
    - 2 unused exports in pagination.ts

    Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>

diff --git a/src/index.ts b/src/index.ts
index 036d16b..f2f0c2c 100644
--- a/src/index.ts
+++ b/src/index.ts
@@ -1,5 +1,9 @@
#!/usr/bin/env node

+import { readFileSync } from "node:fs";
+import { dirname, join } from "node:path";
+import { fileURLToPath } from "node:url";

- import { Server } from "@modelcontextprotocol/sdk/server/index.js";
  import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
  import {
  @@ -12,10 +16,20 @@ import { AWSAuthManager } from "./auth/aws-auth.js";
  import { RepositoryService } from "./services/repository-service.js";
  import { PullRequestService } from "./services/pull-request-service.js";
  import { MCPConfig } from "./types/index.js";
  -import { handleAWSError, retryWithBackoff } from "./utils/error-handler.js";
  +import { handleAWSError, MCPValidationError, retryWithBackoff } from "./utils/error-handler.js";
  import { createPaginationOptions } from "./utils/pagination.js";
  import { IntelligentDiffAnalyzer } from "./utils/intelligent-diff-analyzer.js";
  +function readPackageVersion(): string {
- try {
- const here = dirname(fileURLToPath(import.meta.url));
- const pkg = JSON.parse(readFileSync(join(here, "..", "package.json"), "utf8"));
- return typeof pkg.version === "string" ? pkg.version : "0.0.0";
- } catch {
- return "0.0.0";
- }
  +}
- class AWSPRReviewerServer {
  private server: Server;
  private authManager: AWSAuthManager;
  @@ -27,7 +41,7 @@ class AWSPRReviewerServer {
  this.server = new Server(
  {
  name: "aws-pr-reviewer",

*        version: "1.0.0",

-        version: readPackageVersion(),
         },
         {
           capabilities: {
  @@ -773,50 +787,25 @@ class AWSPRReviewerServer {
  {
  name: "comment_reply",
  description:

*              "Replies to an existing comment, creating a threaded conversation. Use when: 1) Responding to questions, 2) Continuing discussion, 3) Addressing feedback, 4) Clarifying points. Maintains comment thread context for organized discussions.",

-              "Replies to an existing comment, creating a threaded conversation. Use when: 1) Responding to questions, 2) Continuing discussion, 3) Addressing feedback, 4) Clarifying points. AWS scopes the reply to the parent comment automatically — only the parent comment ID and reply content are required.",
             inputSchema: {
               type: "object",
               properties: {

*                pullRequestId: {
*                  type: "string",
*                  description: "PR containing the original comment",
*                },
*                repositoryName: {
*                  type: "string",
*                  description: "Repository containing the PR",
*                },
*                beforeCommitId: {
*                  type: "string",
*                  description:
*                    "Before commit ID from PR details. Use mergeBase from PR targets.",
*                },
*                afterCommitId: {
*                  type: "string",
*                  description:
*                    "After commit ID from PR details. Use sourceCommit from PR targets.",
*                },
                 inReplyTo: {
                   type: "string",
                   description:
*                    "Comment ID you're replying to (from comments_get)",

-                    "Comment ID you're replying to (from comments_get).",
                 },
                 content: {
                   type: "string",

*                  description: "Reply content addressing the original comment",

-                  description: "Reply content addressing the original comment.",
                 },
                 clientRequestToken: {
                   type: "string",

*                  description: "Optional: Unique token for reply",

-                  description: "Optional: unique token to prevent duplicate replies.",
                 },
               },

*              required: [
*                "pullRequestId",
*                "repositoryName",
*                "beforeCommitId",
*                "afterCommitId",
*                "inReplyTo",
*                "content",
*              ],

-              required: ["inReplyTo", "content"],
             },
           },

@@ -1001,7 +990,7 @@ class AWSPRReviewerServer {
{
name: "aws_creds_refresh",
description:

-              "Manually refreshes AWS credentials (normally auto-refreshed every 7.5 hours). Use when: 1) Credentials expired, 2) Getting authentication errors, 3) Switched AWS configuration, 4) Testing credential validity. Reloads from configured source (profile/environment).",

*              "Manually rebuilds the AWS credential provider and CodeCommit client (the SDK auto-refreshes rotating credentials between calls). Use when: 1) credentials/source were updated externally, 2) you're seeing authentication errors, 3) you switched AWS configuration outside this server, 4) verifying credential validity.",
               inputSchema: {
                 type: "object",
                 properties: {},
  @@ -1046,11 +1035,8 @@ class AWSPRReviewerServer {
  });
       this.server.setRequestHandler(CallToolRequestSchema, async (request) => {

-      const { name, arguments: args } = request.params;
-
-      if (!args) {
-        throw new Error("No arguments provided");
-      }

*      const { name } = request.params;
*      const args: Record<string, unknown> = request.params.arguments ?? {};

         try {
           switch (name) {
  @@ -1429,9 +1415,11 @@ class AWSPRReviewerServer {
  case "code_search":
  return await retryWithBackoff(async () => {
  const mode = args.mode as "search" | "tree";
*              if (mode !== "search" && mode !== "tree") {
*                throw new MCPValidationError("mode must be 'search' or 'tree'");
*              }

               if (mode === "tree") {

-                // Tree mode - list repository structure
                   const result = await this.repositoryService.getRepositoryTree(
                     args.repositoryName as string,
                     args.commitSpecifier as string,
  @@ -1444,39 +1432,51 @@ class AWSPRReviewerServer {
  { type: "text", text: JSON.stringify(result, null, 2) },
  ],
  };
-              } else {
-                // Search mode - find code patterns in specific file
-                const filePath = args.filePath as string;
-                const searchPatterns = args.searchPatterns as any[];

*              }

-                if (!filePath) {
-                  throw new Error("File path is required for search mode");
-                }

*              // Search mode
*              const filePath = args.filePath as string;
*              const searchPatterns = args.searchPatterns as any[];

-                if (!searchPatterns || searchPatterns.length === 0) {
-                  throw new Error(
-                    "Search patterns are required for search mode"

*              if (!filePath) {
*                throw new MCPValidationError("File path is required for search mode");
*              }
*              if (!Array.isArray(searchPatterns) || searchPatterns.length === 0) {
*                throw new MCPValidationError("Search patterns are required for search mode");
*              }
*
*              // Defend against ReDoS / oversized patterns from untrusted MCP clients.
*              const MAX_PATTERN_LEN = 200;
*              for (const p of searchPatterns) {
*                if (typeof p?.pattern !== "string") {
*                  throw new MCPValidationError(
*                    "Each search pattern must include a 'pattern' string"
*                  );
*                }
*                if (p.pattern.length > MAX_PATTERN_LEN) {
*                  throw new MCPValidationError(
*                    `Search pattern exceeds ${MAX_PATTERN_LEN} chars; refine it`
                   );
                 }
*              }

-                const result = await this.repositoryService.searchInFile(
-                  args.repositoryName as string,
-                  args.commitSpecifier as string,
-                  filePath,
-                  searchPatterns,
-                  {
-                    maxResults: (args.maxResults as number) || 50,
-                    includeContext: (args.includeContext as boolean) ?? true,
-                    contextLines: (args.contextLines as number) || 3,
-                  }
-                );

*              const result = await this.repositoryService.searchInFile(
*                args.repositoryName as string,
*                args.commitSpecifier as string,
*                filePath,
*                searchPatterns,
*                {
*                  maxResults: (args.maxResults as number) || 50,
*                  includeContext: (args.includeContext as boolean) ?? true,
*                  contextLines: (args.contextLines as number) || 3,
*                }
*              );

-                return {
-                  content: [
-                    { type: "text", text: JSON.stringify(result, null, 2) },
-                  ],
-                };
-              }

*              return {
*                content: [
*                  { type: "text", text: JSON.stringify(result, null, 2) },
*                ],
*              };
               });

             case "commit_get":

  @@ -1616,6 +1616,10 @@ class AWSPRReviewerServer {
  return await retryWithBackoff(async () => {
  const fileDifferences = args.fileDifferences as any[];

*              if (!Array.isArray(fileDifferences)) {
*                throw new MCPValidationError("fileDifferences must be an array");
*              }
*                // Enforce 3-5 file limit
                 if (fileDifferences.length > 5) {
                   const result = {
  @@ -1865,15 +1869,33 @@ class AWSPRReviewerServer {
             case "comment_post":
               return await retryWithBackoff(async () => {

-              const location = args.filePath
-                ? {
-                    filePath: args.filePath as string,
-                    filePosition: args.filePosition as number,
-                    relativeFileVersion: args.relativeFileVersion as
-                      | "BEFORE"
-                      | "AFTER",

*              let location:
*                | {
*                    filePath: string;
*                    filePosition?: number;
*                    relativeFileVersion: "BEFORE" | "AFTER";
                   }

-                : undefined;

*                | undefined;
*              if (args.filePath !== undefined) {
*                if (typeof args.filePosition !== "number") {
*                  throw new MCPValidationError(
*                    "filePosition (number) is required when filePath is provided"
*                  );
*                }
*                if (
*                  args.relativeFileVersion !== "BEFORE" &&
*                  args.relativeFileVersion !== "AFTER"
*                ) {
*                  throw new MCPValidationError(
*                    "relativeFileVersion must be 'BEFORE' or 'AFTER' when filePath is provided"
*                  );
*                }
*                location = {
*                  filePath: args.filePath as string,
*                  filePosition: args.filePosition,
*                  relativeFileVersion: args.relativeFileVersion,
*                };
*              }

                 const result = await this.pullRequestService.postComment(
                   args.pullRequestId as string,
  @@ -1919,10 +1941,6 @@ class AWSPRReviewerServer {
  case "comment_reply":
  return await retryWithBackoff(async () => {
  const result = await this.pullRequestService.replyToComment(

-                args.pullRequestId as string,
-                args.repositoryName as string,
-                args.beforeCommitId as string,
-                args.afterCommitId as string,
                   args.inReplyTo as string,
                   args.content as string,
                   args.clientRequestToken as string
  @@ -2078,15 +2096,14 @@ class AWSPRReviewerServer {
  case "aws_creds_status": {
  const credentials = await this.authManager.getCredentials();
  const isValid = await this.authManager.isCredentialsValid();

*            const accessKeyId = credentials?.accessKeyId
*              ? `${credentials.accessKeyId.slice(0, 8)}...${credentials.accessKeyId.slice(-6)}`
*              : "Not set";
             const status = {
               hasCredentials: !!credentials,
               isValid,

-              accessKeyId:
-                credentials?.accessKeyId?.slice(0, 8) +
-                  "..." +
-                  credentials?.accessKeyId?.slice(-6) || "Not set",
-              expiration:
-                credentials?.expiration?.toISOString() || "No expiration",

*              accessKeyId,
*              expiration: credentials?.expiration?.toISOString() || "No expiration",
               };
               return {
                 content: [
  @@ -2139,7 +2156,6 @@ class AWSPRReviewerServer {
  let currentHunk: string[] = [];
  let inHunk = false;

- // Separate header and hunks
  for (const line of lines) {
  if (line.startsWith("@@")) {
  if (inHunk && currentHunk.length > 0) {
  @@ -2154,16 +2170,25 @@ class AWSPRReviewerServer {
  }
  }

- // Add the last hunk
  if (inHunk && currentHunk.length > 0) {
  hunks.push(currentHunk);
  }

  const totalHunks = hunks.length;

- const startIndex = Math.max(0, chunkOffset - 1); // Convert to 0-based

*
* // No hunks: binary file, deletion, or empty diff. Return the header as-is
* // so callers can still see metadata, but flag the no-hunks state explicitly.
* if (totalHunks === 0) {
*      return {
*        chunk: headerLines.join("\n"),
*        totalHunks: 0,
*        hasMore: false,
*      };
* }
*
* const startIndex = Math.max(0, chunkOffset - 1);
  const endIndex = Math.min(totalHunks, startIndex + chunkLimit);

- // Build chunked response
  const chunkLines = [...headerLines];
  for (let i = startIndex; i < endIndex; i++) {
  chunkLines.push(...hunks[i]);
  @@ -2200,19 +2225,23 @@ class AWSPRReviewerServer {
  }
  }

-// Handle graceful shutdown
-const server = new AWSPRReviewerServer();
-process.on("SIGINT", async () => {

- console.error("Received SIGINT, shutting down gracefully...");
- await server.shutdown();
- process.exit(0);
  -});
  +// Start the server, then wire up shutdown only after init succeeds so a signal
  +// arriving mid-init doesn't tear down half-initialized state.
  +async function main() {

* const server = new AWSPRReviewerServer();
* await server.run();

-process.on("SIGTERM", async () => {

- console.error("Received SIGTERM, shutting down gracefully...");
- await server.shutdown();
- process.exit(0);
  -});

* const shutdown = async (signal: string) => {
* console.error(`Received ${signal}, shutting down gracefully...`);
* await server.shutdown();
* process.exit(0);
* };

-// Start the server
-server.run();

- process.on("SIGINT", () => void shutdown("SIGINT"));
- process.on("SIGTERM", () => void shutdown("SIGTERM"));
  +}
- +main().catch((error) => {
- console.error("Fatal error in main:", error);
- process.exit(1);
  +});
  diff --git a/src/services/pull-request-service.ts b/src/services/pull-request-service.ts
  index 08a00e4..4e70d5b 100644
  --- a/src/services/pull-request-service.ts
  +++ b/src/services/pull-request-service.ts
  @@ -29,7 +29,7 @@ import {
  PaginatedResult,
  PaginationOptions,
  ApprovalState,
  -} from "../types";
  +} from "../types/index.js";

export class PullRequestService {
private repositoryService: RepositoryService;
@@ -407,10 +407,6 @@ export class PullRequestService {
}

async replyToComment(

- \_pullRequestId: string,
- \_repositoryName: string,
- \_beforeCommitId: string,
- \_afterCommitId: string,
  inReplyTo: string,
  content: string,
  clientRequestToken?: string
  diff --git a/src/services/repository-service.ts b/src/services/repository-service.ts
  index 8d8a8bd..b852c62 100644
  --- a/src/services/repository-service.ts
  +++ b/src/services/repository-service.ts
  @@ -22,17 +22,12 @@ export class RepositoryService {
  });
       const response = await client.send(command);
-

*
* // AWS ListRepositories only returns name+id. Don't fabricate undefined values for
* // the richer metadata fields — callers wanting those should use repo_get.
  const repositories: Repository[] = (response.repositories || []).map(repo => ({
  repositoryName: repo.repositoryName || '',
  repositoryId: repo.repositoryId || '',

-      repositoryDescription: undefined,
-      defaultBranch: undefined,
-      lastModifiedDate: undefined,
-      creationDate: undefined,
-      cloneUrlHttp: undefined,
-      cloneUrlSsh: undefined,
-      arn: undefined,
       }));

       return {

  @@ -240,17 +235,37 @@ export class RepositoryService {
  return files;
  }

- async searchRepositories(searchTerm: string, options: PaginationOptions = {}): Promise<PaginatedResult<Repository>> {
- const allRepos = await this.listRepositories(options);
-
- const filteredRepos = allRepos.items.filter(repo =>
-      repo.repositoryName.toLowerCase().includes(searchTerm.toLowerCase()) ||
-      (repo.repositoryDescription && repo.repositoryDescription.toLowerCase().includes(searchTerm.toLowerCase()))
- );

* async searchRepositories(
* searchTerm: string,
* options: PaginationOptions = {}
* ): Promise<PaginatedResult<Repository>> {
* // AWS ListRepositories has no server-side filter, so we paginate fully and
* // filter client-side. We cap iterations to avoid unbounded scans on huge accounts.
* const MAX_PAGES = 20;
* const term = searchTerm.toLowerCase();
*
* const matches: Repository[] = [];
* let nextToken = options.nextToken;
* let pages = 0;
*
* do {
*      const page = await this.listRepositories({ nextToken });
*      for (const repo of page.items) {
*        if (
*          repo.repositoryName.toLowerCase().includes(term) ||
*          (repo.repositoryDescription &&
*            repo.repositoryDescription.toLowerCase().includes(term))
*        ) {
*          matches.push(repo);
*        }
*      }
*      nextToken = page.nextToken;
*      pages++;
* } while (nextToken && pages < MAX_PAGES);

  return {

-      items: filteredRepos,
-      nextToken: allRepos.nextToken,

*      items: matches,
*      nextToken,
  };
  }

@@ -371,12 +386,14 @@ export class RepositoryService {
}

     try {

-      // AWS expects "" for the repo root, not "/". The caller normalizes "/" to "" earlier;
-      // here we just pass the path through verbatim and never substitute "/".
       const command = new GetFolderCommand({
         repositoryName,
         commitSpecifier,

*        folderPath: folderPath || "/",

-        folderPath: folderPath || "",
       });

*

-        const response = await client.send(command);

         // Add files
  @@ -416,7 +433,7 @@ export class RepositoryService {
  let files = 0;
  let folders = 0;

* for (const [_key, value] of Object.entries(tree)) {

- for (const value of Object.values(tree)) {
  if (value === null) {
  files++;
  } else if (typeof value === 'object') {
  diff --git a/src/utils/error-handler.ts b/src/utils/error-handler.ts
  index aca74f6..2b175ce 100644
  --- a/src/utils/error-handler.ts
  +++ b/src/utils/error-handler.ts
  @@ -10,8 +10,28 @@ export class AWSCodeCommitError extends Error {
  }
  }

+/\*\*

- - Thrown by tool handlers when input validation fails. Maps to a 400-class
- - AWSCodeCommitError so callers can distinguish bad input from server failures.
- \*/
  +export class MCPValidationError extends Error {
- constructor(message: string) {
- super(message);
- this.name = "MCPValidationError";
- }
  +}
- export function handleAWSError(error: any): never {

* if (error.name === "RepositoryDoesNotExistException") {

- if (error instanceof MCPValidationError) {
- throw new AWSCodeCommitError(
-      error.message,
-      "VALIDATION_ERROR",
-      400,
-      error
- );
- }
-
- if (error?.name === "RepositoryDoesNotExistException") {
  throw new AWSCodeCommitError(
  `Repository does not exist: ${error.message}`,
  "REPOSITORY_NOT_FOUND",
  @@ -20,7 +40,7 @@ export function handleAWSError(error: any): never {
  );
  }

* if (error.name === "PullRequestDoesNotExistException") {

- if (error?.name === "PullRequestDoesNotExistException") {
  throw new AWSCodeCommitError(
  `Pull request does not exist: ${error.message}`,
  "PULL_REQUEST_NOT_FOUND",
  @@ -29,7 +49,7 @@ export function handleAWSError(error: any): never {
  );
  }

* if (error.name === "BranchDoesNotExistException") {

- if (error?.name === "BranchDoesNotExistException") {
  throw new AWSCodeCommitError(
  `Branch does not exist: ${error.message}`,
  "BRANCH_NOT_FOUND",
  @@ -38,7 +58,7 @@ export function handleAWSError(error: any): never {
  );
  }

* if (error.name === "CommitDoesNotExistException") {

- if (error?.name === "CommitDoesNotExistException") {
  throw new AWSCodeCommitError(
  `Commit does not exist: ${error.message}`,
  "COMMIT_NOT_FOUND",
  @@ -47,7 +67,7 @@ export function handleAWSError(error: any): never {
  );
  }

* if (error.name === "FileDoesNotExistException") {

- if (error?.name === "FileDoesNotExistException") {
  throw new AWSCodeCommitError(
  `File does not exist: ${error.message}`,
  "FILE_NOT_FOUND",
  @@ -56,7 +76,7 @@ export function handleAWSError(error: any): never {
  );
  }

* if (error.name === "AccessDeniedException") {

- if (error?.name === "AccessDeniedException") {
  throw new AWSCodeCommitError(
  `Access denied: ${error.message}`,
  "ACCESS_DENIED",
  @@ -65,7 +85,7 @@ export function handleAWSError(error: any): never {
  );
  }

* if (error.name === "InvalidParameterException") {

- if (error?.name === "InvalidParameterException") {
  throw new AWSCodeCommitError(
  `Invalid parameter: ${error.message}`,
  "INVALID_PARAMETER",
  @@ -74,44 +94,52 @@ export function handleAWSError(error: any): never {
  );
  }

- const credentialErrorNames = new Set([
- "CredentialsError",
- "CredentialsProviderError",
- "ExpiredTokenException",
- "ExpiredToken",
- "UnauthorizedOperation",
- "TokenRefreshRequired",
- ]);
  if (

* error.name === "CredentialsError" ||
* error.name === "UnauthorizedOperation" ||
* error.name === "TokenRefreshRequired" ||
* error.message?.includes("security token included in the request is expired")

- (error?.name && credentialErrorNames.has(error.name)) ||
- (typeof error?.message === "string" &&
-      error.message.includes("security token included in the request is expired"))
  ) {
  throw new AWSCodeCommitError(

*      `AWS credentials error (possibly expired): ${error.message}. Please run aws_creds_refresh to update credentials.`,

-      `AWS credentials error (possibly expired): ${error?.message}. Please run aws_creds_refresh to update credentials.`,
       "CREDENTIALS_ERROR",
       401,
       error
  );
  }

* // Generic error handling
  throw new AWSCodeCommitError(
* error.message || "An unknown AWS CodeCommit error occurred",
* error.name || "UNKNOWN_ERROR",
* error.$metadata?.httpStatusCode || 500,

- error?.message || "An unknown AWS CodeCommit error occurred",
- error?.name || "UNKNOWN_ERROR",
- error?.$metadata?.httpStatusCode || 500,
  error
  );
  }

export function isRetryableError(error: any): boolean {

- // AWS SDK errors that should be retried
- const retryableCodes = [

* if (!error || typeof error !== "object") return false;
*
* const retryableCodes = new Set([
  "ThrottlingException",
  "TooManyRequestsException",
  "ServiceUnavailableException",
  "InternalServerError",
  "RequestTimeout",

- ];

* ]);

- return (
- retryableCodes.includes(error.name) ||
- (error.$metadata?.httpStatusCode >= 500 &&
-      error.$metadata?.httpStatusCode < 600)
- );

* if (typeof error.name === "string" && retryableCodes.has(error.name)) {
* return true;
* }
*
* const status = error.$metadata?.httpStatusCode;
* return typeof status === "number" && status >= 500 && status < 600;
  }

export async function retryWithBackoff<T>(
@@ -119,30 +147,22 @@ export async function retryWithBackoff<T>(
maxRetries: number = 3,
baseDelayMs: number = 1000
): Promise<T> {

- try {
- let lastError: any;

* let lastError: any;

- for (let attempt = 0; attempt <= maxRetries; attempt++) {
-      try {
-        return await operation();
-      } catch (error) {
-        lastError = error;

* for (let attempt = 0; attempt <= maxRetries; attempt++) {
* try {
*      return await operation();
* } catch (error) {
*      lastError = error;

-        if (attempt === maxRetries || !isRetryableError(error)) {
-          break;
-        }
-
-        const delay = baseDelayMs * Math.pow(2, attempt) + Math.random() * 1000;
-        await new Promise((resolve) => setTimeout(resolve, delay));

*      if (attempt === maxRetries || !isRetryableError(error)) {
*        break;
       }

- }

- throw lastError;
- } catch (e) {
- return {
-      content: [
-        { type: "text", error: `**Error :** ${JSON.stringify(e, null, 2)}` },
-      ],
- } as T;

*      const delay = baseDelayMs * Math.pow(2, attempt) + Math.random() * 1000;
*      await new Promise((resolve) => setTimeout(resolve, delay));
* }
  }
*
* throw lastError;
  }
  diff --git a/src/utils/intelligent-diff-analyzer.ts b/src/utils/intelligent-diff-analyzer.ts
  index 6ba6136..60f9553 100644
  --- a/src/utils/intelligent-diff-analyzer.ts
  +++ b/src/utils/intelligent-diff-analyzer.ts
  @@ -1,3 +1,4 @@
  +import { createHash } from "node:crypto";
  import { RepositoryService } from "../services/repository-service.js";
  import { FileDifference } from "../types/index.js";
  import \* as Diff from "diff";
  @@ -38,21 +39,12 @@ export interface IntelligentDiff {
  };
  }

-export interface FileAnalysisContext {

- isNewFile: boolean;
- isDeletedFile: boolean;
- isLargeFile: boolean;
- hasStructuralChanges: boolean;
- changeComplexity: "low" | "medium" | "high";
- recommendedApproach: "diff_only" | "diff_with_context" | "full_file";
  -}
- export class IntelligentDiffAnalyzer {
  constructor(private repositoryService: RepositoryService) {}

  /\*\*
  - Analyzes file differences and provides intelligent recommendations

- - for the best approach to understand the changes

* - for the best approach to understand the changes.
    \*/
    async analyzeFileDiff(
    repositoryName: string,
    @@ -65,7 +57,6 @@ export class IntelligentDiffAnalyzer {
    let afterContent = "";
         try {

-      // Get file contents based on change type
         if (changeType !== "A") {
           const beforeFile = await this.repositoryService.getFile(
             repositoryName,

  @@ -84,7 +75,6 @@ export class IntelligentDiffAnalyzer {
  afterContent = afterFile.content;
  }

-      // Perform line-by-line diff analysis using proper diff library
         const diffResult = this.performLineDiffWithLibrary(beforeContent, afterContent);
         const chunks = diffResult.chunks;
         const summary = diffResult.summary;
  @@ -94,23 +84,21 @@ export class IntelligentDiffAnalyzer {
  afterContent,
  changeType
  );
-
-      // Generate git diff format using the diff library directly

*       const gitDiffFormat = this.generateProperGitDiff(
          filePath,
          beforeContent,
          afterContent,
          changeType
        );

-
-      // Create line number mapping
-      const beforeLines = beforeContent.split('\n');
-      const afterLines = afterContent.split('\n');

*
*      const beforeLines = beforeContent.split("\n");
*      const afterLines = afterContent.split("\n");
       const lineNumberMapping = {
         beforeLineCount: beforeLines.length,
         afterLineCount: afterLines.length,
         exactLineNumbers: true,

-        awsConsoleCompatible: true

*        awsConsoleCompatible: true,
         };

         return {
  @@ -123,308 +111,90 @@ export class IntelligentDiffAnalyzer {
  lineNumberMapping,
  };
  } catch (error) {

-      // Fallback analysis for files that couldn't be retrieved
       return this.createFallbackAnalysis(filePath, changeType, error);

  }
  }

  /\*\*

- - Performs intelligent line-by-line diff analysis using the diff library

* - Performs line-by-line diff analysis using the diff library.
* - Tracks before/after line numbers correctly even when content lacks a
* - trailing newline (otherwise the last real line gets dropped).
    \*/
    private performLineDiffWithLibrary(
    beforeContent: string,
    afterContent: string

- ): { chunks: DiffChunk[], summary: { linesAdded: number, linesRemoved: number, linesModified: number, totalChanges: number } } {
- // Use the diff library for accurate line-by-line comparison

* ): {
* chunks: DiffChunk[];
* summary: {
*      linesAdded: number;
*      linesRemoved: number;
*      linesModified: number;
*      totalChanges: number;
* };
* } {
  const diff = Diff.diffLines(beforeContent, afterContent);

-

*     const chunks: DiffChunk[] = [];
      let beforeLineNum = 1;
      let afterLineNum = 1;
      let linesAdded = 0;
      let linesRemoved = 0;

- // let linesModified = 0; // Currently not used
-

*     for (const part of diff) {

-      const lines = part.value.split('\n');
-      // Remove empty last line if it exists (common with split)
-      if (lines[lines.length - 1] === '') {

*      const lines = part.value.split("\n");
*      // split('\n') leaves a trailing "" only when the value ends with \n.
*      // If it doesn't, the last element is a real (un-newlined) line we must keep.
*      if (lines.length > 0 && part.value.endsWith("\n") && lines[lines.length - 1] === "") {
         lines.pop();
       }

-

*       if (part.added) {

-        // Lines added
         linesAdded += lines.length;
         chunks.push({
           type: "added",
           beforeLineStart: beforeLineNum,
-          beforeLineEnd: beforeLineNum - 1, // No lines in before

*          beforeLineEnd: beforeLineNum - 1,
           afterLineStart: afterLineNum,
           afterLineEnd: afterLineNum + lines.length - 1,
           content: lines,
         });
         afterLineNum += lines.length;
       } else if (part.removed) {

-        // Lines removed
         linesRemoved += lines.length;
         chunks.push({
           type: "removed",
           beforeLineStart: beforeLineNum,
           beforeLineEnd: beforeLineNum + lines.length - 1,
           afterLineStart: afterLineNum,
-          afterLineEnd: afterLineNum - 1, // No lines in after

*          afterLineEnd: afterLineNum - 1,
           content: lines,
         });
         beforeLineNum += lines.length;

-      } else {
-        // Unchanged lines (context)
-        if (lines.length > 0) {
-          chunks.push({
-            type: "context",
-            beforeLineStart: beforeLineNum,
-            beforeLineEnd: beforeLineNum + lines.length - 1,
-            afterLineStart: afterLineNum,
-            afterLineEnd: afterLineNum + lines.length - 1,
-            content: lines,
-          });
-          beforeLineNum += lines.length;
-          afterLineNum += lines.length;
-        }

*      } else if (lines.length > 0) {
*        chunks.push({
*          type: "context",
*          beforeLineStart: beforeLineNum,
*          beforeLineEnd: beforeLineNum + lines.length - 1,
*          afterLineStart: afterLineNum,
*          afterLineEnd: afterLineNum + lines.length - 1,
*          content: lines,
*        });
*        beforeLineNum += lines.length;
*        afterLineNum += lines.length;
       }
  }

-

*     return {
        chunks,
        summary: {
          linesAdded,
          linesRemoved,

-        linesModified: 0, // We'll calculate this differently if needed
-        totalChanges: linesAdded + linesRemoved
-      }
- };
- }
-
- /\*\*
- - Legacy method - kept for compatibility, now uses the library method
- \*/
- private performLineDiff(
- beforeContent: string,
- afterContent: string
- ): DiffChunk[] {
- const beforeLines = beforeContent.split("\n");
- const afterLines = afterContent.split("\n");
-
- const chunks: DiffChunk[] = [];
- let beforeIndex = 0;
- let afterIndex = 0;
-
- // Simple LCS-based diff algorithm with context awareness
- const lcs = this.longestCommonSubsequence(beforeLines, afterLines);
-
- for (const change of lcs) {
-      if (change.type === "equal") {
-        // Context lines - include selectively
-        if (chunks.length > 0 || beforeIndex < beforeLines.length - 1) {
-          chunks.push({
-            type: "context",
-            beforeLineStart: beforeIndex + 1,
-            beforeLineEnd: beforeIndex + change.count,
-            afterLineStart: afterIndex + 1,
-            afterLineEnd: afterIndex + change.count,
-            content: beforeLines.slice(beforeIndex, beforeIndex + change.count),
-          });
-        }
-        beforeIndex += change.count;
-        afterIndex += change.count;
-      } else if (change.type === "delete") {
-        chunks.push({
-          type: "removed",
-          beforeLineStart: beforeIndex + 1,
-          beforeLineEnd: beforeIndex + change.count,
-          afterLineStart: afterIndex + 1,
-          afterLineEnd: afterIndex,
-          content: beforeLines.slice(beforeIndex, beforeIndex + change.count),
-        });
-        beforeIndex += change.count;
-      } else if (change.type === "insert") {
-        chunks.push({
-          type: "added",
-          beforeLineStart: beforeIndex + 1,
-          beforeLineEnd: beforeIndex,
-          afterLineStart: afterIndex + 1,
-          afterLineEnd: afterIndex + change.count,
-          content: afterLines.slice(afterIndex, afterIndex + change.count),
-        });
-        afterIndex += change.count;
-      }
- }
-
- return this.addContextToChunks(chunks, beforeLines, afterLines);
- }
-
- /\*\*
- - Adds intelligent context around changes
- \*/
- private addContextToChunks(
- chunks: DiffChunk[],
- beforeLines: string[],
- afterLines: string[]
- ): DiffChunk[] {
- return chunks.map((chunk) => {
-      if (chunk.type === "context") return chunk;
-
-      const contextSize = this.determineContextSize(chunk);
-
-      // Add context before the change
-      const contextBefore = this.getContextLines(
-        chunk.type === "removed" ? beforeLines : afterLines,
-        chunk.type === "removed"
-          ? chunk.beforeLineStart - 1
-          : chunk.afterLineStart - 1,
-        contextSize,
-        "before"
-      );
-
-      // Add context after the change
-      const contextAfter = this.getContextLines(
-        chunk.type === "removed" ? beforeLines : afterLines,
-        chunk.type === "removed" ? chunk.beforeLineEnd : chunk.afterLineEnd,
-        contextSize,
-        "after"
-      );
-
-      return {
-        ...chunk,
-        contextBefore,
-        contextAfter,
-      };
- });
- }
-
- /\*\*
- - Determines appropriate context size based on change complexity
- \*/
- private determineContextSize(chunk: DiffChunk): number {
- const changeSize = chunk.content.length;
-
- // Look for structural indicators
- const hasClassOrFunction = chunk.content.some((line) =>
-      /^(class|function|def|public|private|protected|async|export)/.test(
-        line.trim()
-      )
- );
-
- if (hasClassOrFunction) return 5;
- if (changeSize > 10) return 4;
- if (changeSize > 5) return 3;
- return 2;
- }
-
- /\*\*
- - Gets contextual lines around a change
- \*/
- private getContextLines(
- lines: string[],
- fromIndex: number,
- count: number,
- direction: "before" | "after"
- ): string[] {
- if (direction === "before") {
-      const start = Math.max(0, fromIndex - count);
-      return lines.slice(start, fromIndex);
- } else {
-      const end = Math.min(lines.length, fromIndex + count);
-      return lines.slice(fromIndex, end);
- }
- }
-
- /\*\*
- - Simple LCS implementation for diff calculation
- \*/
- private longestCommonSubsequence(
- before: string[],
- after: string[]
- ): Array<{ type: string; count: number }> {
- // Simplified diff algorithm - in production, consider using a more robust library
- const result: Array<{ type: string; count: number }> = [];
- let i = 0,
-      j = 0;
-
- while (i < before.length || j < after.length) {
-      if (i < before.length && j < after.length && before[i] === after[j]) {
-        let count = 0;
-        while (
-          i < before.length &&
-          j < after.length &&
-          before[i] === after[j]
-        ) {
-          count++;
-          i++;
-          j++;
-        }
-        result.push({ type: "equal", count });
-      } else if (
-        i < before.length &&
-        (j >= after.length || before[i] !== after[j])
-      ) {
-        let count = 0;
-        while (
-          i < before.length &&
-          (j >= after.length || before[i] !== after[j])
-        ) {
-          count++;
-          i++;
-        }
-        result.push({ type: "delete", count });
-      } else {
-        let count = 0;
-        while (
-          j < after.length &&
-          (i >= before.length || before[i] !== after[j])
-        ) {
-          count++;
-          j++;
-        }
-        result.push({ type: "insert", count });
-      }
- }
-
- return result;
- }
-
- /\*\*
- - Calculates summary statistics for the diff
- \*/
- private calculateSummary(chunks: DiffChunk[]) {
- let linesAdded = 0;
- let linesRemoved = 0;
- let linesModified = 0;
-
- chunks.forEach((chunk) => {
-      switch (chunk.type) {
-        case "added":
-          linesAdded += chunk.content.length;
-          break;
-        case "removed":
-          linesRemoved += chunk.content.length;
-          break;
-        case "modified":
-          linesModified += chunk.content.length;
-          break;
-      }
- });
-
- return {
-      linesAdded,
-      linesRemoved,
-      linesModified,
-      totalChanges: linesAdded + linesRemoved + linesModified,

*        linesModified: 0,
*        totalChanges: linesAdded + linesRemoved,
*      },
  };
  }

- /\*\*
- - Analyzes change complexity and provides recommendations
- \*/
  private analyzeComplexity(
  chunks: DiffChunk[],
  beforeContent: string,
  @@ -436,7 +206,6 @@ export class IntelligentDiffAnalyzer {
  const totalChanges = chunks.filter((c) => c.type !== "context").length;
  const changeRatio = totalChanges / Math.max(beforeLines, afterLines, 1);

- // Determine if full file context is needed
  const needsFullFile = this.shouldRecommendFullFile(
  chunks,
  beforeContent,
  @@ -444,7 +213,6 @@ export class IntelligentDiffAnalyzer {
  changeType
  );

- // Determine complexity
  let complexity: "low" | "medium" | "high" = "low";
  if (changeRatio > 0.5 || totalChanges > 20) {
  complexity = "high";
  @@ -452,61 +220,39 @@ export class IntelligentDiffAnalyzer {
  complexity = "medium";
  }

- // Determine reason and context lines needed
- const reason = this.getRecommendationReason(
-      needsFullFile,
-      complexity,
-      changeType
- );
- const contextLines = this.getRecommendedContextLines(complexity);
-     return {
        needsFullFile,
-      reason,
-      contextLines,

*      reason: this.getRecommendationReason(needsFullFile, complexity, changeType),
*      contextLines: this.getRecommendedContextLines(complexity),
       complexity,
  };
  }

- /\*\*
- - Determines if full file context is recommended
- \*/
  private shouldRecommendFullFile(
  chunks: DiffChunk[],
  beforeContent: string,
  afterContent: string,
  changeType: "A" | "D" | "M"
  ): boolean {
- // New or deleted files always need full context
  if (changeType === "A" || changeType === "D") return true;

  const beforeLines = beforeContent.split("\n").length;
  const afterLines = afterContent.split("\n").length;

- // Small files - show full content
  if (Math.max(beforeLines, afterLines) <= 500) return true;

- // High change ratio
  const totalChanges = chunks.filter((c) => c.type !== "context").length;
  const changeRatio = totalChanges / Math.max(beforeLines, afterLines);
  if (changeRatio > 0.3) return true;

- // Structural changes (imports, exports, class definitions)
  const hasStructuralChanges = chunks.some((chunk) =>
  chunk.content.some((line) =>
-        /^(import|export|class|interface|function|def|from|package)/.test(
-          line.trim()
-        )

*        /^(import|export|class|interface|function|def|from|package)/.test(line.trim())
       )
  );

- if (hasStructuralChanges) return true;
-
- return false;

* return hasStructuralChanges;
  }

- /\*\*
- - Gets recommendation reason text
- \*/
  private getRecommendationReason(
  needsFullFile: boolean,
  complexity: "low" | "medium" | "high",
  @@ -526,9 +272,6 @@ export class IntelligentDiffAnalyzer {
  return "Focused diff with context should be sufficient for understanding changes";
  }

- /\*\*
- - Gets recommended context lines based on complexity
- \*/
  private getRecommendedContextLines(
  complexity: "low" | "medium" | "high"
  ): number {
  @@ -543,8 +286,8 @@ export class IntelligentDiffAnalyzer {
  }

/\*\*

- - Generates proper git diff format using only the diff library
- - This creates unified diff format exactly like git diff command

* - Generates a unified diff in git's format. For new/deleted files we synthesize
* - the appropriate header lines; for modified files we delegate to Diff.createPatch.
    \*/
    private generateProperGitDiff(
    filePath: string,
    @@ -552,57 +295,46 @@ export class IntelligentDiffAnalyzer {
    afterContent: string,
    changeType: "A" | "D" | "M"
    ): string {

- // For new files (A) - show all content as added
  if (changeType === "A") {
  const unifiedDiff = Diff.createPatch(
  filePath,
-        "", // Empty before content

*        "",
         afterContent,
         "/dev/null",
         "b/" + filePath,
         { context: 3 }
       );

-
-      // Replace the header to match git format
-      const lines = unifiedDiff.split('\n');
-      const result = [

*      const body = unifiedDiff.split("\n").slice(4);
*      return [
         `diff --git a/${filePath} b/${filePath}`,
         `new file mode 100644`,

-        `index 0000000..${this.generateHashPlaceholder()}`,

*        `index 0000000..${this.shortHash(afterContent)}`,
         `--- /dev/null`,
         `+++ b/${filePath}`,

-        ...lines.slice(4) // Skip the createPatch header
-      ];
-
-      return result.join('\n');

*        ...body,
*      ].join("\n");
  }

-
- // For deleted files (D) - show all content as removed

*     if (changeType === "D") {
        const unifiedDiff = Diff.createPatch(
          filePath,
          beforeContent,

-        "", // Empty after content

*        "",
         "a/" + filePath,
         "/dev/null",
         { context: 3 }
       );

-
-      // Replace the header to match git format
-      const lines = unifiedDiff.split('\n');
-      const result = [

*      const body = unifiedDiff.split("\n").slice(4);
*      return [
         `diff --git a/${filePath} b/${filePath}`,
         `deleted file mode 100644`,

-        `index ${this.generateHashPlaceholder()}..0000000`,

*        `index ${this.shortHash(beforeContent)}..0000000`,
         `--- a/${filePath}`,
         `+++ /dev/null`,

-        ...lines.slice(4) // Skip the createPatch header
-      ];
-
-      return result.join('\n');

*        ...body,
*      ].join("\n");
  }

-
- // For modified files (M) - show the actual diff

*      const unifiedDiff = Diff.createPatch(
         filePath,
         beforeContent,
  @@ -611,97 +343,20 @@ export class IntelligentDiffAnalyzer {
  "b/" + filePath,
  { context: 3 }
  );

-
- // Replace the header to match git format
- const lines = unifiedDiff.split('\n');
- const result = [

* const body = unifiedDiff.split("\n").slice(4);
* return [
  `diff --git a/${filePath} b/${filePath}`,

-      `index ${this.generateHashPlaceholder()}..${this.generateHashPlaceholder()} 100644`,

*      `index ${this.shortHash(beforeContent)}..${this.shortHash(afterContent)} 100644`,
       `--- a/${filePath}`,
       `+++ b/${filePath}`,

-      ...lines.slice(4) // Skip the createPatch header
- ];
-
- return result.join('\n');

*      ...body,
* ].join("\n");
  }

- /\*\*
- - Generates a placeholder hash for git diff (simplified)
- \*/
- private generateHashPlaceholder(): string {
- return Math.random().toString(36).substring(2, 9);

* private shortHash(content: string): string {
* return createHash("sha1").update(content).digest("hex").slice(0, 7);
  }

- /\*\*
- - Legacy method - generates proper git diff format using the diff library
- - This creates unified diff format exactly like git diff command
- \*/
- private generateGitDiffFormat(
- filePath: string,
- beforeContent: string,
- afterContent: string,
- chunks: DiffChunk[],
- changeType: "A" | "D" | "M"
- ): string {
- const diffOutput: string[] = [];
-
- // Generate proper git hash placeholders (simplified)
- const beforeHash = "a".repeat(7) + (Math.random().toString(36).substring(2, 9));
- const afterHash = "b".repeat(7) + (Math.random().toString(36).substring(2, 9));
-
- // Add git diff header
- diffOutput.push(`diff --git a/${filePath} b/${filePath}`);
-
- if (changeType === "A") {
-      diffOutput.push(`new file mode 100644`);
-      diffOutput.push(`index 0000000..${afterHash.substring(0, 7)}`);
-      diffOutput.push(`--- /dev/null`);
-      diffOutput.push(`+++ b/${filePath}`);
- } else if (changeType === "D") {
-      diffOutput.push(`deleted file mode 100644`);
-      diffOutput.push(`index ${beforeHash.substring(0, 7)}..0000000`);
-      diffOutput.push(`--- a/${filePath}`);
-      diffOutput.push(`+++ /dev/null`);
- } else {
-      diffOutput.push(`index ${beforeHash.substring(0, 7)}..${afterHash.substring(0, 7)} 100644`);
-      diffOutput.push(`--- a/${filePath}`);
-      diffOutput.push(`+++ b/${filePath}`);
- }
-
- // Use the diff library to generate proper unified diff
- const unifiedDiff = Diff.createPatch(
-      filePath,
-      beforeContent,
-      afterContent,
-      "a/" + filePath,
-      "b/" + filePath,
-      {
-        context: 3  // 3 lines of context like git default
-      }
- );
-
- // Parse the unified diff and extract the hunks (skip the header lines)
- const lines = unifiedDiff.split('\n');
- let inHunk = false;
-
- for (const line of lines) {
-      if (line.startsWith('@@')) {
-        inHunk = true;
-        diffOutput.push(line);
-      } else if (inHunk && (line.startsWith(' ') || line.startsWith('+') || line.startsWith('-'))) {
-        diffOutput.push(line);
-      } else if (inHunk && line === '') {
-        // Empty line in diff
-        diffOutput.push(line);
-      }
- }
-
- return diffOutput.join('\n');
- }
-
- /\*\*
- - Creates fallback analysis when file retrieval fails
- \*/
  private createFallbackAnalysis(
  filePath: string,
  changeType: "A" | "D" | "M",
  @@ -711,7 +366,7 @@ export class IntelligentDiffAnalyzer {
  filePath,
  changeType,
  chunks: [],
-      gitDiffFormat: `# Diff analysis failed for ${filePath}\n# Error: ${error.message}\n# Recommend using file_get for manual analysis`,

*      gitDiffFormat: `# Diff analysis failed for ${filePath}\n# Error: ${error?.message ?? error}\n# Recommend using file_get for manual analysis`,
         summary: {
           linesAdded: 0,
           linesRemoved: 0,
  @@ -720,7 +375,7 @@ export class IntelligentDiffAnalyzer {
  },
  analysisRecommendation: {
  needsFullFile: changeType === "A" || changeType === "D",

-        reason: `File analysis failed (${error.message}). Recommend using file_get for manual analysis.`,

*        reason: `File analysis failed (${error?.message ?? error}). Recommend using file_get for manual analysis.`,
           contextLines: 3,
           complexity: "medium",
         },
  @@ -728,14 +383,11 @@ export class IntelligentDiffAnalyzer {
  beforeLineCount: 0,
  afterLineCount: 0,
  exactLineNumbers: false,

-        awsConsoleCompatible: false

*        awsConsoleCompatible: false,
       },
  };
  }

- /\*\*
- - Analyzes multiple files and provides batch recommendations
- \*/
  async analyzeBatchDiffs(
  repositoryName: string,
  beforeCommitId: string,
  @@ -780,17 +432,13 @@ export class IntelligentDiffAnalyzer {
  return { analyses, batchRecommendations };
  }

- /\*\*
- - Generates a summary of recommended approaches for the batch
- \*/
  private generateBatchApproachSummary(analyses: IntelligentDiff[]): string {
  const fullFileCount = analyses.filter(
  (a) => a.analysisRecommendation.needsFullFile
  ).length;
  const totalFiles = analyses.length;
-

*     let summary = "";

-      if (fullFileCount === totalFiles) {
         summary = "All files require full context - significant changes detected";
       } else if (fullFileCount > totalFiles / 2) {
  @@ -800,14 +448,13 @@ export class IntelligentDiffAnalyzer {
  } else {
  summary = "Focused diff analysis sufficient for all files - targeted changes detected";
  }
-
- // Add batch size guidance

*     if (totalFiles > 5) {
        summary += `. NOTE: Processed ${totalFiles} files (recommended maximum: 3-5 files per batch for optimal performance)`;
      } else {
        summary += `. Batch size: ${totalFiles} files (optimal for analysis)`;
      }

-

*      return summary;
  }
  }
  diff --git a/src/utils/line-position-calculator.ts b/src/utils/line-position-calculator.ts
  index 64833db..3472b4b 100644
  --- a/src/utils/line-position-calculator.ts
  +++ b/src/utils/line-position-calculator.ts
  @@ -1,20 +1,16 @@
  import { RepositoryService } from '../services/repository-service.js';
  /\*\*

- - Utility for calculating and validating line positions for AWS CodeCommit comments

* - Validates that a line number falls within the bounds of a file at a given commit.
* - AWS CodeCommit comment positions are 1-based and relative to the specific file version
* - (BEFORE = destination commit, AFTER = source commit).
    \*/
    export class LinePositionCalculator {
    constructor(private repositoryService: RepositoryService) {}

    /\*\*

- - Validates and adjusts line position for a file comment
- - AWS CodeCommit line positions are 1-based and relative to the specific file version
- - @param repositoryName Repository name
- - @param filePath Path to the file
- - @param lineNumber Requested line number (1-based)
- - @param commitSpecifier Commit ID or branch name
- - @param relativeFileVersion BEFORE or AFTER version
- - @returns Valid line position or throws error

* - Returns the line number, clamped to [1, totalLines]. Throws if the file
* - cannot be retrieved (so the caller can fall back to the original position).
    \*/
    async validateAndAdjustLinePosition(
    repositoryName: string,
    @@ -23,276 +19,34 @@ export class LinePositionCalculator {
    commitSpecifier: string,
    relativeFileVersion: 'BEFORE' | 'AFTER'
    ): Promise<number> {

- try {
-      // Get the file content for the specified version
-      const fileData = await this.repositoryService.getFile(
-        repositoryName,
-        commitSpecifier,
-        filePath
-      );
-
-      const lines = fileData.content.split('\n');
-      const totalLines = lines.length;
-
-      console.error(`Line validation for ${filePath}:`, {
-        requestedLine: lineNumber,
-        totalLines,
-        commitSpecifier: commitSpecifier.substring(0, 8),
-        relativeFileVersion
-      });
-
-      // Validate line number bounds - AWS CodeCommit uses 1-based indexing
-      if (lineNumber < 1) {
-        console.error(`Line number ${lineNumber} is too low, adjusting to 1`);
-        return 1;
-      }
-
-      if (lineNumber > totalLines) {
-        console.error(`Line number ${lineNumber} exceeds file length (${totalLines}), adjusting to ${totalLines}`);
-        return totalLines;
-      }
-
-      // Line number is valid for this specific file version
-      console.error(`Line ${lineNumber} is valid for ${relativeFileVersion} version (total: ${totalLines})`);
-      return lineNumber;
- } catch (error) {
-      console.error(`Error validating line position for ${filePath}:${lineNumber}`, error);
-
-      // If file doesn't exist or can't be read, return a safe default
-      throw new Error(`Cannot validate line position: ${error instanceof Error ? error.message : 'Unknown error'}`);
- }
- }
-
- /\*\*
- - Maps line numbers between BEFORE and AFTER versions of a file using diff information
- - @param repositoryName Repository name
- - @param filePath Path to the file
- - @param lineNumber Line number in the source version
- - @param fromVersion Source version (BEFORE or AFTER)
- - @param toVersion Target version (BEFORE or AFTER)
- - @param beforeCommit Before commit ID
- - @param afterCommit After commit ID
- - @returns Mapped line number or null if not mappable
- \*/
- async mapLineBetweenVersions(
- repositoryName: string,
- filePath: string,
- lineNumber: number,
- fromVersion: 'BEFORE' | 'AFTER',
- toVersion: 'BEFORE' | 'AFTER',
- beforeCommit: string,
- afterCommit: string
- ): Promise<number | null> {
- if (fromVersion === toVersion) {
-      return lineNumber;
- }
-
- try {
-      // Get both file versions
-      const beforeFile = await this.repositoryService.getFile(repositoryName, beforeCommit, filePath);
-      const afterFile = await this.repositoryService.getFile(repositoryName, afterCommit, filePath);
-
-      const beforeLines = beforeFile.content.split('\n');
-      const afterLines = afterFile.content.split('\n');
-
-      console.error(`Mapping line ${lineNumber} from ${fromVersion} to ${toVersion}:`, {
-        beforeLines: beforeLines.length,
-        afterLines: afterLines.length
-      });
-
-      // Simple heuristic: if the line content matches, use that line number
-      if (fromVersion === 'BEFORE' && toVersion === 'AFTER') {
-        const beforeLineContent = beforeLines[lineNumber - 1]?.trim();
-        if (beforeLineContent) {
-          // Find the same content in the after version
-          const afterLineIndex = afterLines.findIndex(line => line.trim() === beforeLineContent);
-          if (afterLineIndex !== -1) {
-            return afterLineIndex + 1; // Convert to 1-based
-          }
-        }
-      } else if (fromVersion === 'AFTER' && toVersion === 'BEFORE') {
-        const afterLineContent = afterLines[lineNumber - 1]?.trim();
-        if (afterLineContent) {
-          // Find the same content in the before version
-          const beforeLineIndex = beforeLines.findIndex(line => line.trim() === afterLineContent);
-          if (beforeLineIndex !== -1) {
-            return beforeLineIndex + 1; // Convert to 1-based
-          }
-        }
-      }
-
-      // If exact match not found, return approximate position
-      if (fromVersion === 'BEFORE' && toVersion === 'AFTER') {
-        const ratio = afterLines.length / beforeLines.length;
-        return Math.min(Math.ceil(lineNumber * ratio), afterLines.length);
-      } else {
-        const ratio = beforeLines.length / afterLines.length;
-        return Math.min(Math.ceil(lineNumber * ratio), beforeLines.length);
-      }
- } catch (error) {
-      console.error(`Error mapping line between versions:`, error);
-      return null;
- }
- }
-
- /\*\*
- - Finds the best line position for a comment based on content analysis
- - @param repositoryName Repository name
- - @param filePath Path to the file
- - @param searchContent Content to search for (partial match)
- - @param commitSpecifier Commit ID or branch name
- - @param relativeFileVersion BEFORE or AFTER version
- - @returns Best matching line number or null if not found
- \*/
- async findBestLinePosition(
- repositoryName: string,
- filePath: string,
- searchContent: string,
- commitSpecifier: string,
- relativeFileVersion: 'BEFORE' | 'AFTER'
- ): Promise<number | null> {
- try {
-      const fileData = await this.repositoryService.getFile(
-        repositoryName,
-        commitSpecifier,
-        filePath
-      );
-
-      const lines = fileData.content.split('\n');
-
-      // Search for exact match first
-      for (let i = 0; i < lines.length; i++) {
-        if (lines[i].includes(searchContent.trim())) {
-          console.error(`Found exact match for "${searchContent}" at line ${i + 1}`);
-          return i + 1; // Convert to 1-based
-        }
-      }
-
-      // Search for partial matches with fuzzy matching
-      const searchTerms = searchContent.toLowerCase().split(/\s+/).filter(term => term.length > 2);
-      let bestMatch = { line: -1, score: 0 };
-
-      for (let i = 0; i < lines.length; i++) {
-        const lineContent = lines[i].toLowerCase();
-        let score = 0;
-
-        for (const term of searchTerms) {
-          if (lineContent.includes(term)) {
-            score++;
-          }
-        }
-
-        if (score > bestMatch.score) {
-          bestMatch = { line: i + 1, score };
-        }
-      }
-
-      if (bestMatch.score > 0) {
-        console.error(`Found best match for "${searchContent}" at line ${bestMatch.line} (score: ${bestMatch.score})`);
-        return bestMatch.line;
-      }
-
-      console.error(`No match found for "${searchContent}" in ${filePath}`);
-      return null;
- } catch (error) {
-      console.error(`Error finding best line position:`, error);
-      return null;

* const fileData = await this.repositoryService.getFile(
*      repositoryName,
*      commitSpecifier,
*      filePath
* );
*
* const lines = fileData.content.split('\n');
* const totalLines = lines.length;
*
* console.error(`Line validation for ${filePath}:`, {
*      requestedLine: lineNumber,
*      totalLines,
*      commitSpecifier: commitSpecifier.substring(0, 8),
*      relativeFileVersion,
* });
*
* if (lineNumber < 1) {
*      console.error(`Line number ${lineNumber} is too low, adjusting to 1`);
*      return 1;
  }

- }

- /\*\*
- - Maps line position from AI analysis context to AWS CodeCommit PR context
- - This handles the specific case where AI analyzes full files but comments need
- - to be positioned relative to the PR diff context
- - @param repositoryName Repository name
- - @param filePath Path to the file
- - @param aiLineNumber Line number from AI analysis (1-based)
- - @param beforeCommitId Before commit ID for PR
- - @param afterCommitId After commit ID for PR
- - @param relativeFileVersion BEFORE or AFTER version for comment
- - @returns Correctly positioned line number for AWS CodeCommit
- \*/
- async mapAILineToCodeCommitPosition(
- repositoryName: string,
- filePath: string,
- aiLineNumber: number,
- beforeCommitId: string,
- afterCommitId: string,
- relativeFileVersion: 'BEFORE' | 'AFTER'
- ): Promise<number> {
- try {
-      // Get the file content for the target version
-      const targetCommit = relativeFileVersion === 'BEFORE' ? beforeCommitId : afterCommitId;
-      const fileData = await this.repositoryService.getFile(
-        repositoryName,
-        targetCommit,
-        filePath

* if (lineNumber > totalLines) {
*      console.error(
*        `Line number ${lineNumber} exceeds file length (${totalLines}), adjusting to ${totalLines}`
       );

-
-      const lines = fileData.content.split('\n');
-      const totalLines = lines.length;
-
-      console.error(`Mapping AI line ${aiLineNumber} to CodeCommit position:`, {
-        filePath,
-        aiLineNumber,
-        targetCommit: targetCommit.substring(0, 8),
-        relativeFileVersion,
-        totalLines
-      });
-
-      // Validate that the AI line number is within bounds
-      if (aiLineNumber < 1) {
-        console.error(`AI line number ${aiLineNumber} is too low, using line 1`);
-        return 1;
-      }
-
-      if (aiLineNumber > totalLines) {
-        console.error(`AI line number ${aiLineNumber} exceeds file length (${totalLines}), using last line`);
-        return totalLines;
-      }
-
-      // For now, return the AI line number as-is since it should be relative to the correct file version
-      // Future enhancement: implement more sophisticated diff-based mapping if needed
-      console.error(`Mapped AI line ${aiLineNumber} to CodeCommit position ${aiLineNumber}`);
-      return aiLineNumber;
- } catch (error) {
-      console.error(`Error mapping AI line to CodeCommit position:`, error);
-      // Return the original line number as fallback
-      return aiLineNumber;

*      return totalLines;
  }

- }
-
- /\*\*
- - Gets file content summary for debugging
- - @param repositoryName Repository name
- - @param filePath Path to the file
- - @param commitSpecifier Commit ID or branch name
- - @returns Summary with line count and sample lines
- \*/
- async getFileContentSummary(
- repositoryName: string,
- filePath: string,
- commitSpecifier: string
- ): Promise<{ totalLines: number; sampleLines: string[]; }> {
- try {
-      const fileData = await this.repositoryService.getFile(
-        repositoryName,
-        commitSpecifier,
-        filePath
-      );

-      const lines = fileData.content.split('\n');
-      const sampleLines = lines.slice(0, 20).map((line, index) =>
-        `${index + 1}: ${line.substring(0, 100)}${line.length > 100 ? '...' : ''}`
-      );
-
-      return {
-        totalLines: lines.length,
-        sampleLines
-      };
- } catch (error) {
-      console.error(`Error getting file content summary:`, error);
-      return { totalLines: 0, sampleLines: [] };
- }

* return lineNumber;
  }
  }
  diff --git a/src/utils/pagination.ts b/src/utils/pagination.ts
  index ae43a13..f3de76e 100644
  --- a/src/utils/pagination.ts
  +++ b/src/utils/pagination.ts
  @@ -1,4 +1,4 @@
  -import { PaginatedResult, PaginationOptions } from '../types/index.js';
  +import { PaginationOptions } from '../types/index.js';

export function createPaginationOptions(
nextToken?: string,
@@ -9,52 +9,3 @@ export function createPaginationOptions(
maxResults: Math.min(maxResults || 100, 1000), // AWS CodeCommit max is 1000
};
}

- -export async function getAllPages<T>(
- fetchPage: (options: PaginationOptions) => Promise<PaginatedResult<T>>,
- maxItems?: number
  -): Promise<T[]> {
- const results: T[] = [];
- let nextToken: string | undefined;
- let totalFetched = 0;
-
- do {
- const maxResults = maxItems
-      ? Math.min(100, maxItems - totalFetched)
-      : 100;
-
- if (maxResults <= 0) break;
-
- const page = await fetchPage({ nextToken, maxResults });
- results.push(...page.items);
- nextToken = page.nextToken;
- totalFetched += page.items.length;
-
- if (maxItems && totalFetched >= maxItems) {
-      break;
- }
- } while (nextToken);
-
- return maxItems ? results.slice(0, maxItems) : results;
  -}
- -export function formatPaginationInfo(
- currentPage: number,
- itemsPerPage: number,
- totalItems: number,
- hasNextPage: boolean
  -): string {
- const startItem = (currentPage - 1) \* itemsPerPage + 1;
- const endItem = Math.min(currentPage \* itemsPerPage, totalItems);
-
- let info = `Showing ${startItem}-${endItem}`;
- if (totalItems > 0) {
- info += ` of ${totalItems} items`;
- }
-
- if (hasNextPage) {
- info += ' (more available)';
- }
-
- return info;
  -}
  \ No newline at end of file
  PS C:\Users\sanik_unwtxkj\MyProjects\MCP servers\aws-code-commit-pr-mcp>

PS C:\Users\sanik_unwtxkj\MyProjects\MCP servers\aws-code-commit-pr-mcp> git show d8d7efc91dc3385314912ef6088fc9ea14f6e2d2
commit d8d7efc91dc3385314912ef6088fc9ea14f6e2d2
Author: Teja <sanikommutejareddy@gmail.com>
Date: Wed Apr 29 21:09:08 2026 +0530

    Use fromNodeProviderChain so the SDK rotates credentials

    Replaces the static-credentials snapshot pattern (resolve once, hand
    the result to CodeCommitClient, refresh manually on a 6-min timer)
    with a provider-direct pattern: build a fromNodeProviderChain provider
    once and pass it to CodeCommitClient. The SDK calls the provider on
    each request and refreshes when expiration nears, so the manual
    setInterval and the _isRefresh plumbing are gone.

    This unlocks Fargate / ECS task roles, EKS IRSA, EC2 IMDS, and SSO
    without code changes - the chain visits all of them in order. WSL
    cross-mount credential discovery is preserved by passing
    {filepath, configFilepath} options to the chain rather than mutating
    process.env (which previously polluted the host process for the
    lifetime of the server).

    API change: AWSAuthManager.getCredentials() and isCredentialsValid()
    are now async (they invoke the provider rather than read a cached
    field). The aws_creds_status tool handler is updated to await both.

    Also drops the stderr line that JSON-stringified resolved credentials,
    which previously logged the full secret access key + session token to
    host logs, and replaces a buggy path.replace("credentials","config")
    with path.dirname + path.join (the old form mangled paths like
    .../Users/credentials_admin/.aws/credentials).

    Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>

diff --git a/src/auth/aws-auth.ts b/src/auth/aws-auth.ts
index f835a18..2ed9124 100644
--- a/src/auth/aws-auth.ts
+++ b/src/auth/aws-auth.ts
@@ -1,5 +1,6 @@
import { CodeCommitClient } from "@aws-sdk/client-codecommit";
-import { fromIni, fromEnv } from "@aws-sdk/credential-providers";
+import { fromNodeProviderChain } from "@aws-sdk/credential-providers";
+import type { AwsCredentialIdentity, AwsCredentialIdentityProvider } from "@aws-sdk/types";
import { AWSCredentials, MCPConfig } from "../types/index.js";
import _ as fs from "fs";
import _ as path from "path";
@@ -7,165 +8,67 @@ import \* as os from "os";

export class AWSAuthManager {
private client: CodeCommitClient | null = null;

- private credentials: AWSCredentials | null = null;

* private credentialProvider: AwsCredentialIdentityProvider | null = null;
  private config: MCPConfig;

- private refreshTimer: NodeJS.Timeout | null = null;

  constructor(config: MCPConfig) {
  this.config = config;
  }

  async initialize(): Promise<void> {

- await this.loadCredentials();
- this.setupCredentialRefresh();

* this.buildClient();
  }

- private async loadCredentials(isRefresh?: boolean): Promise<void> {
- try {
-      let credentialProvider;
-
-      if (this.config.awsAccessKeyId && this.config.awsSecretAccessKey) {
-        credentialProvider = {
-          accessKeyId: this.config.awsAccessKeyId,
-          secretAccessKey: this.config.awsSecretAccessKey,
-          sessionToken: this.config.awsSessionToken,
-        };
-      } else if (this.config.awsProfile) {
-        const credentialsPath = this.getCredentialsPath();
-        const defaultCredPath = path.join(os.homedir(), ".aws", "credentials");
-
-        // Only specify custom paths if credentials are in a non-default location
-        if (credentialsPath && credentialsPath !== defaultCredPath) {
-          const configPath = credentialsPath.replace("credentials", "config");
-          console.error(`Using credentials from: ${credentialsPath}`);

* /\*\*
* - Build the credential provider and CodeCommit client.
* - The provider is passed directly to the SDK so token rotation
* - (Fargate task role, EKS IRSA, EC2 IMDS, SSO) is handled automatically.
* \*/
* private buildClient(): void {
* if (this.config.awsAccessKeyId && this.config.awsSecretAccessKey) {
*      // Static credentials forced via constructor config — return them as a provider.
*      const accessKeyId = this.config.awsAccessKeyId;
*      const secretAccessKey = this.config.awsSecretAccessKey;
*      const sessionToken = this.config.awsSessionToken;
*      this.credentialProvider = async () => ({
*        accessKeyId,
*        secretAccessKey,
*        sessionToken,
*      });
* } else {
*      // Default chain: env → SSO → ini → process → web identity (IRSA) → ECS metadata → EC2 IMDS.
*      // For WSL cross-mount, we pass an explicit ini filepath rather than mutating process.env.
*      const credentialsPath = this.getCredentialsPath();
*      const defaultCredPath = path.join(os.homedir(), ".aws", "credentials");

-          credentialProvider = fromIni({
-            profile: this.config.awsProfile,
-            ignoreCache: Boolean(isRefresh),
-            filepath: credentialsPath,
-            configFilepath: configPath,
-          });
-        } else {
-          // Use default AWS SDK path resolution
-          credentialProvider = fromIni({
-            profile: this.config.awsProfile,
-            ignoreCache: Boolean(isRefresh),
-          });
-        }
-      } else {
-        credentialProvider = fromEnv();

*      const init: Parameters<typeof fromNodeProviderChain>[0] = {};
*      if (this.config.awsProfile) {
*        init.profile = this.config.awsProfile;
       }

-
-      if (typeof credentialProvider === "function") {
-        console.error("Resolving credentials from provider function...");
-        const resolvedCredentials = await credentialProvider();
-        console.error(
-          "Resolved credentials:" + JSON.stringify(resolvedCredentials)
-        );
-
-        if (
-          !resolvedCredentials.accessKeyId ||
-          !resolvedCredentials.secretAccessKey
-        ) {
-          throw new Error(
-            "Credential provider returned incomplete credentials"
-          );
-        }
-
-        this.credentials = {
-          accessKeyId: resolvedCredentials.accessKeyId,
-          secretAccessKey: resolvedCredentials.secretAccessKey,
-          sessionToken: resolvedCredentials.sessionToken,
-          expiration: resolvedCredentials.expiration,
-        };
-
-        console.error(
-          `Resolved credentials: accessKeyId=${resolvedCredentials.accessKeyId.substring(
-            0,
-            8
-          )}..., hasSessionToken=${!!resolvedCredentials.sessionToken}, expiration=${
-            resolvedCredentials.expiration
-              ? resolvedCredentials.expiration.toISOString()
-              : "none"
-          }`
-        );
-      } else {
-        console.error("Using static credentials...");
-        this.credentials = credentialProvider as AWSCredentials;
-
-        if (
-          !this.credentials.accessKeyId ||
-          !this.credentials.secretAccessKey
-        ) {
-          throw new Error("Static credentials are incomplete");
-        }

*      if (credentialsPath && credentialsPath !== defaultCredPath) {
*        init.filepath = credentialsPath;
*        init.configFilepath = path.join(path.dirname(credentialsPath), "config");
*        console.error(`Using credentials from: ${credentialsPath}`);
       }

-      // CRITICAL: Always recreate the client with fresh credentials
-      // This ensures expired credentials are replaced
-      this.client = new CodeCommitClient({
-        region: this.config.region || "us-east-1",
-        credentials: this.credentials,
-      });
-
-      console.error(
-        `AWS credentials loaded successfully${
-          this.config.awsProfile
-            ? ` for profile: ${this.config.awsProfile}`
-            : ""
-        }`
-      );
-      console.error(
-        `Credentials expire: ${
-          this.credentials.expiration
-            ? this.credentials.expiration.toISOString()
-            : "no expiration"
-        }`
-      );
- } catch (error) {
-      throw new Error(
-        `Failed to load AWS credentials: ${
-          error instanceof Error ? error.message : "Unknown error"
-        }`
-      );

*      this.credentialProvider = fromNodeProviderChain(init);
  }

- }
-
- private setupCredentialRefresh(): void {
- const refreshInterval = 0.1 _ 60 _ 60 \* 1000; // 6 minutes
-
- this.refreshTimer = setInterval(async () => {
-      try {
-        console.error("Refreshing AWS credentials...");
-        await this.loadCredentials(true);
-        console.error("AWS credentials refreshed successfully");
-      } catch (error) {
-        console.error("Failed to refresh AWS credentials:", error);
-      }
- }, refreshInterval);
- }
-
- async refreshCredentials(): Promise<void> {
- console.error("Manual credential refresh requested...");

- // Store old expiration for comparison
- const oldExpiration =
-      this.credentials?.expiration?.toISOString() || "no expiration";

* this.client = new CodeCommitClient({
*      region: this.config.region || "us-east-1",
*      credentials: this.credentialProvider,
* });

- await this.loadCredentials(true);
-
- const newExpiration =
-      this.credentials?.expiration?.toISOString() || "no expiration";
  console.error(
-      `Manual credential refresh completed. Old expiration: ${oldExpiration}, New expiration: ${newExpiration}`

*      `AWS client initialized${
*        this.config.awsProfile ? ` for profile: ${this.config.awsProfile}` : ""
*      }`
  );
* }

- // Verify the client was recreated
- if (this.client) {
-      console.error("AWS client recreated with fresh credentials");
- } else {
-      console.error("WARNING: AWS client not properly recreated");
- }

* async refreshCredentials(): Promise<void> {
* console.error("Rebuilding credential provider and client...");
* this.buildClient();
  }

async switchProfile(profileName: string): Promise<void> {
@@ -173,143 +76,86 @@ export class AWSAuthManager {
this.config.awsAccessKeyId = undefined;
this.config.awsSecretAccessKey = undefined;
this.config.awsSessionToken = undefined;

- await this.loadCredentials();

* this.buildClient();
  }

async getClient(): Promise<CodeCommitClient> {

- if (!this.client) {
-      console.error("AWS client not initialized, initializing now...");
-      await this.initialize();
- }
-
- // Check if credentials are expired and refresh if needed
- if (!this.isCredentialsValid()) {
-      console.error("Credentials expired or invalid, refreshing...");
-      try {
-        await this.refreshCredentials();
-        console.error("Credentials refreshed successfully");
-      } catch (error) {
-        console.error("Failed to refresh credentials:", error);
-        throw new Error(
-          `Credential refresh failed: ${
-            error instanceof Error ? error.message : "Unknown error"
-          }`
-        );
-      }
- }
-

* if (!this.client) this.buildClient();
  return this.client!;
  }

- getCredentials(): AWSCredentials | null {
- return this.credentials;
- }
-
- isCredentialsValid(): boolean {
- if (!this.credentials) {
-      console.error("No credentials available");
-      return false;
- }
-
- // Check if required credentials fields are present
- if (!this.credentials.accessKeyId || !this.credentials.secretAccessKey) {
-      console.error(
-        "Credentials missing required fields (accessKeyId or secretAccessKey)"
-      );
-      return false;

* /\*\*
* - Resolve current credentials by invoking the provider.
* - The SDK caches and refreshes internally; this just peeks at the current state.
* \*/
* async getCredentials(): Promise<AWSCredentials | null> {
* if (!this.credentialProvider) return null;
* try {
*      const resolved: AwsCredentialIdentity = await this.credentialProvider();
*      return {
*        accessKeyId: resolved.accessKeyId,
*        secretAccessKey: resolved.secretAccessKey,
*        sessionToken: resolved.sessionToken,
*        expiration: resolved.expiration,
*      };
* } catch (error) {
*      console.error("Failed to resolve credentials:", error);
*      return null;
  }
* }

- // Check expiration if present
- if (this.credentials.expiration) {
-      const now = new Date();
-      const buffer = 5 * 60 * 1000; // 5 minutes buffer
-      const isValid =
-        this.credentials.expiration.getTime() > now.getTime() + buffer;
-
-      if (!isValid) {
-        console.error(
-          `Credentials expired. Expiration: ${this.credentials.expiration.toISOString()}, Now: ${now.toISOString()}, Buffer: 5 minutes`
-        );
-      } else {
-        const timeUntilExpiry =
-          this.credentials.expiration.getTime() - now.getTime();
-        console.error(
-          `Credentials valid. Time until expiry: ${Math.round(
-            timeUntilExpiry / 1000 / 60
-          )} minutes`
-        );
-      }
-
-      return isValid;

* async isCredentialsValid(): Promise<boolean> {
* const creds = await this.getCredentials();
* if (!creds) return false;
* if (!creds.accessKeyId || !creds.secretAccessKey) return false;
* if (creds.expiration) {
*      const buffer = 5 * 60 * 1000;
*      return creds.expiration.getTime() > Date.now() + buffer;
  }

-
- // If no expiration, assume credentials are long-lived (IAM user keys)
- console.error("Credentials have no expiration (long-lived credentials)");
  return true;
  }

private getCredentialsPath(): string | null {

- // Try multiple paths in order of preference
- const pathsToTry = [
-      // 1. Standard WSL/Linux home directory
-      path.join(os.homedir(), ".aws", "credentials"),
- ];

* const candidates = [path.join(os.homedir(), ".aws", "credentials")];

- // 2. If running in WSL, also check Windows user directories
  if (this.isWSL()) {
-      const windowsUsers = this.getWindowsUserPaths();
-      windowsUsers.forEach((userPath) => {
-        pathsToTry.push(path.join(userPath, ".aws", "credentials"));

*      this.getWindowsUserPaths().forEach((userPath) => {
*        candidates.push(path.join(userPath, ".aws", "credentials"));
       });
  }

- // Return the first path that exists
- for (const credPath of pathsToTry) {

* for (const credPath of candidates) {
  if (fs.existsSync(credPath)) {
  console.error(`Found AWS credentials at: ${credPath}`);
  return credPath;
  }
  }

- console.error(
-      `AWS credentials not found. Searched paths: ${pathsToTry.join(", ")}`
- );

* console.error(`AWS credentials not found. Searched: ${candidates.join(", ")}`);
  return null;
  }

private isWSL(): boolean {
try {
if (process.platform !== "linux") return false;

-
-      // Check /proc/version for WSL indicators
       if (fs.existsSync("/proc/version")) {
-        const procVersion = fs.readFileSync("/proc/version", "utf8");
-        return (
-          procVersion.toLowerCase().includes("microsoft") ||
-          procVersion.toLowerCase().includes("wsl")
-        );

*        const procVersion = fs.readFileSync("/proc/version", "utf8").toLowerCase();
*        return procVersion.includes("microsoft") || procVersion.includes("wsl");
       }

- } catch (error) {
-      // Ignore errors, assume not WSL

* } catch {
*      // ignore

  }
  return false;
  }

  private getWindowsUserPaths(): string[] {
  const paths: string[] = [];

-     try {
-      // Try to find Windows user directories in /mnt/c/Users/
       const usersDir = "/mnt/c/Users";
       if (fs.existsSync(usersDir)) {
-        const userDirs = fs.readdirSync(usersDir, { withFileTypes: true });
-        for (const dir of userDirs) {
-          if (
-            dir.isDirectory() &&
-            !["Public", "Default", "All Users", "Default User"].includes(
-              dir.name
-            )
-          ) {

*        const skip = new Set(["Public", "Default", "All Users", "Default User"]);
*        for (const dir of fs.readdirSync(usersDir, { withFileTypes: true })) {
*          if (dir.isDirectory() && !skip.has(dir.name)) {
               paths.push(path.join(usersDir, dir.name));
             }
           }
  @@ -317,35 +163,50 @@ export class AWSAuthManager {
  } catch (error) {
  console.error("Failed to enumerate Windows user directories:", error);
  }

-     return paths;
  }

* /\*\*
* - Reads profile names from BOTH ~/.aws/credentials and ~/.aws/config.
* - Config file uses [profile NAME] syntax for non-default profiles; we strip the prefix.
* \*/
  getAvailableProfiles(): string[] {

- try {
-      const credentialsPath = this.getCredentialsPath();
-      if (!credentialsPath) {
-        return [];
-      }

* const profiles = new Set<string>();
* const credPath = this.getCredentialsPath();
* if (!credPath) return [];

-      const content = fs.readFileSync(credentialsPath, "utf8");
-      const profiles = content.match(/^\[([^\]]+)\]/gm);

* const sectionRegex = /^\[([^\]]+)\]/gm;

-      if (!profiles) return [];

* try {
*      const content = fs.readFileSync(credPath, "utf8");
*      let match: RegExpExecArray | null;
*      while ((match = sectionRegex.exec(content)) !== null) {
*        profiles.add(match[1]);
*      }
* } catch (error) {
*      console.error("Failed to read credentials file:", error);
* }

-      return profiles
-        .map((profile) => profile.slice(1, -1))
-        .filter((profile) => profile !== "default");

* const configPath = path.join(path.dirname(credPath), "config");
* try {
*      if (fs.existsSync(configPath)) {
*        const content = fs.readFileSync(configPath, "utf8");
*        sectionRegex.lastIndex = 0;
*        let match: RegExpExecArray | null;
*        while ((match = sectionRegex.exec(content)) !== null) {
*          const name = match[1];
*          profiles.add(name.startsWith("profile ") ? name.slice(8) : name);
*        }
*      }
  } catch (error) {

-      console.error("Failed to read AWS profiles:", error);
-      return [];

*      console.error("Failed to read config file:", error);
  }
*
* return Array.from(profiles).filter((p) => p !== "default");
  }

cleanup(): void {

- if (this.refreshTimer) {
-      clearInterval(this.refreshTimer);
-      this.refreshTimer = null;
- }

* // No timers or background work to release. The SDK's internal credential
* // cache is GC'd with the client when the auth manager is discarded.
  }
  }
  diff --git a/src/index.ts b/src/index.ts
  index ede0774..036d16b 100644
  --- a/src/index.ts
  +++ b/src/index.ts
  @@ -2076,8 +2076,8 @@ class AWSPRReviewerServer {
  }
             case "aws_creds_status": {

-            const credentials = this.authManager.getCredentials();
-            const isValid = this.authManager.isCredentialsValid();

*            const credentials = await this.authManager.getCredentials();
*            const isValid = await this.authManager.isCredentialsValid();
             const status = {
               hasCredentials: !!credentials,
               isValid,

PS C:\Users\sanik_unwtxkj\MyProjects\MCP servers\aws-code-commit-pr-mcp> git show fc5cf9912ddfcca69b3ae6c7dda3b09fab2ac88f
commit fc5cf9912ddfcca69b3ae6c7dda3b09fab2ac88f
Author: Teja <sanikommutejareddy@gmail.com>
Date: Wed Apr 29 21:07:20 2026 +0530

    Modernize dependencies to latest as of April 2026

    Bumps:
    - TypeScript 5.9 -> 6.0 (add "types": ["node"] to tsconfig since TS 6
      no longer auto-loads @types/* packages)
    - AWS SDK 3.864 -> 3.1038
    - @modelcontextprotocol/sdk 1.17 -> 1.29
    - diff 8 -> 9 (drop @types/diff; diff@9 ships its own types)
    - @types/node 24 -> 25, nodemon 3.1.10 -> 3.1.14, tsx 4.20 -> 4.21
    - engines: Node 18 -> Node 20 (Node 18 EOL'd April 2025; TS 6 needs 20+)

    Also moves @types/treeify into devDependencies (was misplaced under
    runtime deps).

    Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>

diff --git a/package-lock.json b/package-lock.json
index cd3a40f..6a3f16b 100644
--- a/package-lock.json
+++ b/package-lock.json
@@ -1,37 +1,38 @@
{

- "name": "aws-pr-reviewer",
- "version": "1.0.0",

* "name": "@tejasanik/aws-pr-reviewer",
* "version": "1.3.0",
  "lockfileVersion": 3,
  "requires": true,
  "packages": {
  "": {

-      "name": "aws-pr-reviewer",
-      "version": "1.0.0",

*      "name": "@tejasanik/aws-pr-reviewer",
*      "version": "1.3.0",
       "license": "MIT",
       "dependencies": {

-        "@aws-sdk/client-codecommit": "^3.864.0",
-        "@aws-sdk/credential-providers": "^3.864.0",
-        "@modelcontextprotocol/sdk": "^1.17.2",
-        "@types/diff": "^7.0.2",
-        "@types/treeify": "^1.0.3",
-        "diff": "^8.0.2",

*        "@aws-sdk/client-codecommit": "^3.1038.0",
*        "@aws-sdk/credential-providers": "^3.1038.0",
*        "@modelcontextprotocol/sdk": "^1.29.0",
*        "diff": "^9.0.0",
         "treeify": "^1.1.0"
       },
       "bin": {
         "aws-pr-reviewer": "dist/index.js"
       },
       "devDependencies": {

-        "@types/node": "^24.2.1",
-        "nodemon": "^3.1.10",
-        "tsx": "^4.20.3",
-        "typescript": "^5.9.2"

*        "@types/node": "^25.6.0",
*        "@types/treeify": "^1.0.3",
*        "nodemon": "^3.1.14",
*        "tsx": "^4.21.0",
*        "typescript": "^6.0.3"
*      },
*      "engines": {
*        "node": ">=20.0.0"
       }
  },
  "node_modules/@aws-crypto/sha256-browser": {
  "version": "5.2.0",
  "resolved": "https://registry.npmjs.org/@aws-crypto/sha256-browser/-/sha256-browser-5.2.0.tgz",
  "integrity": "sha512-AXfN/lGotSQwu6HNcEsIASo7kWXZ5HYWvfOmSNKDsEqC4OashTp8alTmaz+F7TC2L083SFv5RdB+qU3Vs1kZqw==",

-      "license": "Apache-2.0",
         "dependencies": {
           "@aws-crypto/sha256-js": "^5.2.0",
           "@aws-crypto/supports-web-crypto": "^5.2.0",
  @@ -46,7 +47,6 @@
  "version": "2.2.0",
  "resolved": "https://registry.npmjs.org/@smithy/is-array-buffer/-/is-array-buffer-2.2.0.tgz",
  "integrity": "sha512-GGP3O9QFD24uGeAXYUjwSTXARoqpZykHadOmA8G5vfJPK0/DC67qa//0qvqrJzL1xc8WQWX7/yc7fwudjPHPhA==",
-      "license": "Apache-2.0",
         "dependencies": {
           "tslib": "^2.6.2"
         },
  @@ -58,7 +58,6 @@
  "version": "2.2.0",
  "resolved": "https://registry.npmjs.org/@smithy/util-buffer-from/-/util-buffer-from-2.2.0.tgz",
  "integrity": "sha512-IJdWBbTcMQ6DA0gdNhh/BwrLkDR+ADW5Kr1aZmd4k3DIF6ezMV4R2NIAmT08wQJ3yUK82thHWmC/TnK/wpMMIA==",
-      "license": "Apache-2.0",
         "dependencies": {
           "@smithy/is-array-buffer": "^2.2.0",
           "tslib": "^2.6.2"
  @@ -71,7 +70,6 @@
  "version": "2.3.0",
  "resolved": "https://registry.npmjs.org/@smithy/util-utf8/-/util-utf8-2.3.0.tgz",
  "integrity": "sha512-R8Rdn8Hy72KKcebgLiv8jQcQkXoLMOGGv5uI1/k0l+snqkOzQ1R0ChUBCxWMlBsFMekWjq0wRudIweFs7sKT5A==",
-      "license": "Apache-2.0",
         "dependencies": {
           "@smithy/util-buffer-from": "^2.2.0",
           "tslib": "^2.6.2"
  @@ -84,7 +82,6 @@
  "version": "5.2.0",
  "resolved": "https://registry.npmjs.org/@aws-crypto/sha256-js/-/sha256-js-5.2.0.tgz",
  "integrity": "sha512-FFQQyu7edu4ufvIZ+OadFpHHOt+eSTBaYaki44c+akjg7qZg9oOQeLlk77F6tSYqjDAFClrHJk9tMf0HdVyOvA==",
-      "license": "Apache-2.0",
         "dependencies": {
           "@aws-crypto/util": "^5.2.0",
           "@aws-sdk/types": "^3.222.0",
  @@ -98,7 +95,6 @@
  "version": "5.2.0",
  "resolved": "https://registry.npmjs.org/@aws-crypto/supports-web-crypto/-/supports-web-crypto-5.2.0.tgz",
  "integrity": "sha512-iAvUotm021kM33eCdNfwIN//F77/IADDSs58i+MDaOqFrVjZo9bAal0NK7HurRuWLLpF1iLX7gbWrjHjeo+YFg==",
-      "license": "Apache-2.0",
         "dependencies": {
           "tslib": "^2.6.2"
         }
  @@ -107,7 +103,6 @@
  "version": "5.2.0",
  "resolved": "https://registry.npmjs.org/@aws-crypto/util/-/util-5.2.0.tgz",
  "integrity": "sha512-4RkU9EsI6ZpBve5fseQlGNUWKMa1RLPQ1dnjnQoe07ldfIzcsGb5hC5W0Dm7u423KWzawlrpbjXBrXCEv9zazQ==",
-      "license": "Apache-2.0",
         "dependencies": {
           "@aws-sdk/types": "^3.222.0",
           "@smithy/util-utf8": "^2.0.0",
  @@ -118,7 +113,6 @@
  "version": "2.2.0",
  "resolved": "https://registry.npmjs.org/@smithy/is-array-buffer/-/is-array-buffer-2.2.0.tgz",
  "integrity": "sha512-GGP3O9QFD24uGeAXYUjwSTXARoqpZykHadOmA8G5vfJPK0/DC67qa//0qvqrJzL1xc8WQWX7/yc7fwudjPHPhA==",
-      "license": "Apache-2.0",
         "dependencies": {
           "tslib": "^2.6.2"
         },
  @@ -130,7 +124,6 @@
  "version": "2.2.0",
  "resolved": "https://registry.npmjs.org/@smithy/util-buffer-from/-/util-buffer-from-2.2.0.tgz",
  "integrity": "sha512-IJdWBbTcMQ6DA0gdNhh/BwrLkDR+ADW5Kr1aZmd4k3DIF6ezMV4R2NIAmT08wQJ3yUK82thHWmC/TnK/wpMMIA==",
-      "license": "Apache-2.0",
         "dependencies": {
           "@smithy/is-array-buffer": "^2.2.0",
           "tslib": "^2.6.2"
  @@ -143,7 +136,6 @@
  "version": "2.3.0",
  "resolved": "https://registry.npmjs.org/@smithy/util-utf8/-/util-utf8-2.3.0.tgz",
  "integrity": "sha512-R8Rdn8Hy72KKcebgLiv8jQcQkXoLMOGGv5uI1/k0l+snqkOzQ1R0ChUBCxWMlBsFMekWjq0wRudIweFs7sKT5A==",
-      "license": "Apache-2.0",
         "dependencies": {
           "@smithy/util-buffer-from": "^2.2.0",
           "tslib": "^2.6.2"
  @@ -153,578 +145,577 @@
  }
  },
  "node_modules/@aws-sdk/client-codecommit": {
-      "version": "3.864.0",
-      "resolved": "https://registry.npmjs.org/@aws-sdk/client-codecommit/-/client-codecommit-3.864.0.tgz",
-      "integrity": "sha512-jZWauD3aDxicPmnb25rxbEz7L9ikqNJmROncpVB2CEKBTzKy7xTakS1FUGqGi/4UZlSsfYKS35RUT/GAq5U/Hw==",
-      "license": "Apache-2.0",
-      "dependencies": {
-        "@aws-crypto/sha256-browser": "5.2.0",
-        "@aws-crypto/sha256-js": "5.2.0",
-        "@aws-sdk/core": "3.864.0",
-        "@aws-sdk/credential-provider-node": "3.864.0",
-        "@aws-sdk/middleware-host-header": "3.862.0",
-        "@aws-sdk/middleware-logger": "3.862.0",
-        "@aws-sdk/middleware-recursion-detection": "3.862.0",
-        "@aws-sdk/middleware-user-agent": "3.864.0",
-        "@aws-sdk/region-config-resolver": "3.862.0",
-        "@aws-sdk/types": "3.862.0",
-        "@aws-sdk/util-endpoints": "3.862.0",
-        "@aws-sdk/util-user-agent-browser": "3.862.0",
-        "@aws-sdk/util-user-agent-node": "3.864.0",
-        "@smithy/config-resolver": "^4.1.5",
-        "@smithy/core": "^3.8.0",
-        "@smithy/fetch-http-handler": "^5.1.1",
-        "@smithy/hash-node": "^4.0.5",
-        "@smithy/invalid-dependency": "^4.0.5",
-        "@smithy/middleware-content-length": "^4.0.5",
-        "@smithy/middleware-endpoint": "^4.1.18",
-        "@smithy/middleware-retry": "^4.1.19",
-        "@smithy/middleware-serde": "^4.0.9",
-        "@smithy/middleware-stack": "^4.0.5",
-        "@smithy/node-config-provider": "^4.1.4",
-        "@smithy/node-http-handler": "^4.1.1",
-        "@smithy/protocol-http": "^5.1.3",
-        "@smithy/smithy-client": "^4.4.10",
-        "@smithy/types": "^4.3.2",
-        "@smithy/url-parser": "^4.0.5",
-        "@smithy/util-base64": "^4.0.0",
-        "@smithy/util-body-length-browser": "^4.0.0",
-        "@smithy/util-body-length-node": "^4.0.0",
-        "@smithy/util-defaults-mode-browser": "^4.0.26",
-        "@smithy/util-defaults-mode-node": "^4.0.26",
-        "@smithy/util-endpoints": "^3.0.7",
-        "@smithy/util-middleware": "^4.0.5",
-        "@smithy/util-retry": "^4.0.7",
-        "@smithy/util-utf8": "^4.0.0",
-        "@types/uuid": "^9.0.1",
-        "tslib": "^2.6.2",
-        "uuid": "^9.0.1"
-      },
-      "engines": {
-        "node": ">=18.0.0"
-      }
- },
- "node_modules/@aws-sdk/client-cognito-identity": {
-      "version": "3.864.0",
-      "resolved": "https://registry.npmjs.org/@aws-sdk/client-cognito-identity/-/client-cognito-identity-3.864.0.tgz",
-      "integrity": "sha512-IH3RSg/Zy2+yXQ2d4jmMk2U8A+BuJ9uNUYPWAg144yUUxanN1Czb+GyFKeJO4NGhVnn5D+j1YoRLpJN8PW2B0g==",
-      "license": "Apache-2.0",

*      "version": "3.1038.0",
*      "resolved": "https://registry.npmjs.org/@aws-sdk/client-codecommit/-/client-codecommit-3.1038.0.tgz",
*      "integrity": "sha512-ikkcaJjt6bn30dNAK1hzvUJv0x1ddn2h+/35U0CLknZ5pDeyLLNoMWb5lHUF9MWP1muqsKRT+/T6ggUorfWbOQ==",
       "dependencies": {
         "@aws-crypto/sha256-browser": "5.2.0",
         "@aws-crypto/sha256-js": "5.2.0",

-        "@aws-sdk/core": "3.864.0",
-        "@aws-sdk/credential-provider-node": "3.864.0",
-        "@aws-sdk/middleware-host-header": "3.862.0",
-        "@aws-sdk/middleware-logger": "3.862.0",
-        "@aws-sdk/middleware-recursion-detection": "3.862.0",
-        "@aws-sdk/middleware-user-agent": "3.864.0",
-        "@aws-sdk/region-config-resolver": "3.862.0",
-        "@aws-sdk/types": "3.862.0",
-        "@aws-sdk/util-endpoints": "3.862.0",
-        "@aws-sdk/util-user-agent-browser": "3.862.0",
-        "@aws-sdk/util-user-agent-node": "3.864.0",
-        "@smithy/config-resolver": "^4.1.5",
-        "@smithy/core": "^3.8.0",
-        "@smithy/fetch-http-handler": "^5.1.1",
-        "@smithy/hash-node": "^4.0.5",
-        "@smithy/invalid-dependency": "^4.0.5",
-        "@smithy/middleware-content-length": "^4.0.5",
-        "@smithy/middleware-endpoint": "^4.1.18",
-        "@smithy/middleware-retry": "^4.1.19",
-        "@smithy/middleware-serde": "^4.0.9",
-        "@smithy/middleware-stack": "^4.0.5",
-        "@smithy/node-config-provider": "^4.1.4",
-        "@smithy/node-http-handler": "^4.1.1",
-        "@smithy/protocol-http": "^5.1.3",
-        "@smithy/smithy-client": "^4.4.10",
-        "@smithy/types": "^4.3.2",
-        "@smithy/url-parser": "^4.0.5",
-        "@smithy/util-base64": "^4.0.0",
-        "@smithy/util-body-length-browser": "^4.0.0",
-        "@smithy/util-body-length-node": "^4.0.0",
-        "@smithy/util-defaults-mode-browser": "^4.0.26",
-        "@smithy/util-defaults-mode-node": "^4.0.26",
-        "@smithy/util-endpoints": "^3.0.7",
-        "@smithy/util-middleware": "^4.0.5",
-        "@smithy/util-retry": "^4.0.7",
-        "@smithy/util-utf8": "^4.0.0",

*        "@aws-sdk/core": "^3.974.6",
*        "@aws-sdk/credential-provider-node": "^3.972.37",
*        "@aws-sdk/middleware-host-header": "^3.972.10",
*        "@aws-sdk/middleware-logger": "^3.972.10",
*        "@aws-sdk/middleware-recursion-detection": "^3.972.11",
*        "@aws-sdk/middleware-user-agent": "^3.972.36",
*        "@aws-sdk/region-config-resolver": "^3.972.13",
*        "@aws-sdk/types": "^3.973.8",
*        "@aws-sdk/util-endpoints": "^3.996.8",
*        "@aws-sdk/util-user-agent-browser": "^3.972.10",
*        "@aws-sdk/util-user-agent-node": "^3.973.22",
*        "@smithy/config-resolver": "^4.4.17",
*        "@smithy/core": "^3.23.17",
*        "@smithy/fetch-http-handler": "^5.3.17",
*        "@smithy/hash-node": "^4.2.14",
*        "@smithy/invalid-dependency": "^4.2.14",
*        "@smithy/middleware-content-length": "^4.2.14",
*        "@smithy/middleware-endpoint": "^4.4.32",
*        "@smithy/middleware-retry": "^4.5.6",
*        "@smithy/middleware-serde": "^4.2.20",
*        "@smithy/middleware-stack": "^4.2.14",
*        "@smithy/node-config-provider": "^4.3.14",
*        "@smithy/node-http-handler": "^4.6.1",
*        "@smithy/protocol-http": "^5.3.14",
*        "@smithy/smithy-client": "^4.12.13",
*        "@smithy/types": "^4.14.1",
*        "@smithy/url-parser": "^4.2.14",
*        "@smithy/util-base64": "^4.3.2",
*        "@smithy/util-body-length-browser": "^4.2.2",
*        "@smithy/util-body-length-node": "^4.2.3",
*        "@smithy/util-defaults-mode-browser": "^4.3.49",
*        "@smithy/util-defaults-mode-node": "^4.2.54",
*        "@smithy/util-endpoints": "^3.4.2",
*        "@smithy/util-middleware": "^4.2.14",
*        "@smithy/util-retry": "^4.3.5",
*        "@smithy/util-utf8": "^4.2.2",
         "tslib": "^2.6.2"
       },
       "engines": {

-        "node": ">=18.0.0"

*        "node": ">=20.0.0"
       }
  },

- "node_modules/@aws-sdk/client-sso": {
-      "version": "3.864.0",
-      "resolved": "https://registry.npmjs.org/@aws-sdk/client-sso/-/client-sso-3.864.0.tgz",
-      "integrity": "sha512-THiOp0OpQROEKZ6IdDCDNNh3qnNn/kFFaTSOiugDpgcE5QdsOxh1/RXq7LmHpTJum3cmnFf8jG59PHcz9Tjnlw==",
-      "license": "Apache-2.0",

* "node_modules/@aws-sdk/client-cognito-identity": {
*      "version": "3.1038.0",
*      "resolved": "https://registry.npmjs.org/@aws-sdk/client-cognito-identity/-/client-cognito-identity-3.1038.0.tgz",
*      "integrity": "sha512-tTSXUZXzydM0VUoxcrM4YrhhQfFgepfpbRLEq460650rFAC8NsGhGQ6Ixo7UPV6TKEyI/jQcCnQVi4RVM4SkAg==",
       "dependencies": {
         "@aws-crypto/sha256-browser": "5.2.0",
         "@aws-crypto/sha256-js": "5.2.0",

-        "@aws-sdk/core": "3.864.0",
-        "@aws-sdk/middleware-host-header": "3.862.0",
-        "@aws-sdk/middleware-logger": "3.862.0",
-        "@aws-sdk/middleware-recursion-detection": "3.862.0",
-        "@aws-sdk/middleware-user-agent": "3.864.0",
-        "@aws-sdk/region-config-resolver": "3.862.0",
-        "@aws-sdk/types": "3.862.0",
-        "@aws-sdk/util-endpoints": "3.862.0",
-        "@aws-sdk/util-user-agent-browser": "3.862.0",
-        "@aws-sdk/util-user-agent-node": "3.864.0",
-        "@smithy/config-resolver": "^4.1.5",
-        "@smithy/core": "^3.8.0",
-        "@smithy/fetch-http-handler": "^5.1.1",
-        "@smithy/hash-node": "^4.0.5",
-        "@smithy/invalid-dependency": "^4.0.5",
-        "@smithy/middleware-content-length": "^4.0.5",
-        "@smithy/middleware-endpoint": "^4.1.18",
-        "@smithy/middleware-retry": "^4.1.19",
-        "@smithy/middleware-serde": "^4.0.9",
-        "@smithy/middleware-stack": "^4.0.5",
-        "@smithy/node-config-provider": "^4.1.4",
-        "@smithy/node-http-handler": "^4.1.1",
-        "@smithy/protocol-http": "^5.1.3",
-        "@smithy/smithy-client": "^4.4.10",
-        "@smithy/types": "^4.3.2",
-        "@smithy/url-parser": "^4.0.5",
-        "@smithy/util-base64": "^4.0.0",
-        "@smithy/util-body-length-browser": "^4.0.0",
-        "@smithy/util-body-length-node": "^4.0.0",
-        "@smithy/util-defaults-mode-browser": "^4.0.26",
-        "@smithy/util-defaults-mode-node": "^4.0.26",
-        "@smithy/util-endpoints": "^3.0.7",
-        "@smithy/util-middleware": "^4.0.5",
-        "@smithy/util-retry": "^4.0.7",
-        "@smithy/util-utf8": "^4.0.0",

*        "@aws-sdk/core": "^3.974.6",
*        "@aws-sdk/credential-provider-node": "^3.972.37",
*        "@aws-sdk/middleware-host-header": "^3.972.10",
*        "@aws-sdk/middleware-logger": "^3.972.10",
*        "@aws-sdk/middleware-recursion-detection": "^3.972.11",
*        "@aws-sdk/middleware-user-agent": "^3.972.36",
*        "@aws-sdk/region-config-resolver": "^3.972.13",
*        "@aws-sdk/types": "^3.973.8",
*        "@aws-sdk/util-endpoints": "^3.996.8",
*        "@aws-sdk/util-user-agent-browser": "^3.972.10",
*        "@aws-sdk/util-user-agent-node": "^3.973.22",
*        "@smithy/config-resolver": "^4.4.17",
*        "@smithy/core": "^3.23.17",
*        "@smithy/fetch-http-handler": "^5.3.17",
*        "@smithy/hash-node": "^4.2.14",
*        "@smithy/invalid-dependency": "^4.2.14",
*        "@smithy/middleware-content-length": "^4.2.14",
*        "@smithy/middleware-endpoint": "^4.4.32",
*        "@smithy/middleware-retry": "^4.5.6",
*        "@smithy/middleware-serde": "^4.2.20",
*        "@smithy/middleware-stack": "^4.2.14",
*        "@smithy/node-config-provider": "^4.3.14",
*        "@smithy/node-http-handler": "^4.6.1",
*        "@smithy/protocol-http": "^5.3.14",
*        "@smithy/smithy-client": "^4.12.13",
*        "@smithy/types": "^4.14.1",
*        "@smithy/url-parser": "^4.2.14",
*        "@smithy/util-base64": "^4.3.2",
*        "@smithy/util-body-length-browser": "^4.2.2",
*        "@smithy/util-body-length-node": "^4.2.3",
*        "@smithy/util-defaults-mode-browser": "^4.3.49",
*        "@smithy/util-defaults-mode-node": "^4.2.54",
*        "@smithy/util-endpoints": "^3.4.2",
*        "@smithy/util-middleware": "^4.2.14",
*        "@smithy/util-retry": "^4.3.5",
*        "@smithy/util-utf8": "^4.2.2",
         "tslib": "^2.6.2"
       },
       "engines": {

-        "node": ">=18.0.0"

*        "node": ">=20.0.0"
       }
  },
  "node_modules/@aws-sdk/core": {

-      "version": "3.864.0",
-      "resolved": "https://registry.npmjs.org/@aws-sdk/core/-/core-3.864.0.tgz",
-      "integrity": "sha512-LFUREbobleHEln+Zf7IG83lAZwvHZG0stI7UU0CtwyuhQy5Yx0rKksHNOCmlM7MpTEbSCfntEhYi3jUaY5e5lg==",
-      "license": "Apache-2.0",
-      "dependencies": {
-        "@aws-sdk/types": "3.862.0",
-        "@aws-sdk/xml-builder": "3.862.0",
-        "@smithy/core": "^3.8.0",
-        "@smithy/node-config-provider": "^4.1.4",
-        "@smithy/property-provider": "^4.0.5",
-        "@smithy/protocol-http": "^5.1.3",
-        "@smithy/signature-v4": "^5.1.3",
-        "@smithy/smithy-client": "^4.4.10",
-        "@smithy/types": "^4.3.2",
-        "@smithy/util-base64": "^4.0.0",
-        "@smithy/util-body-length-browser": "^4.0.0",
-        "@smithy/util-middleware": "^4.0.5",
-        "@smithy/util-utf8": "^4.0.0",
-        "fast-xml-parser": "5.2.5",

*      "version": "3.974.6",
*      "resolved": "https://registry.npmjs.org/@aws-sdk/core/-/core-3.974.6.tgz",
*      "integrity": "sha512-8Vu7zGxu+39ChR/s5J7nXBw3a2kMHAi0OfKT8ohgTVjX0qYed/8mIfdBb638oBmKrWCwwKjYAM5J/4gMJ8nAJA==",
*      "dependencies": {
*        "@aws-sdk/types": "^3.973.8",
*        "@aws-sdk/xml-builder": "^3.972.20",
*        "@smithy/core": "^3.23.17",
*        "@smithy/node-config-provider": "^4.3.14",
*        "@smithy/property-provider": "^4.2.14",
*        "@smithy/protocol-http": "^5.3.14",
*        "@smithy/signature-v4": "^5.3.14",
*        "@smithy/smithy-client": "^4.12.13",
*        "@smithy/types": "^4.14.1",
*        "@smithy/util-base64": "^4.3.2",
*        "@smithy/util-middleware": "^4.2.14",
*        "@smithy/util-retry": "^4.3.5",
*        "@smithy/util-utf8": "^4.2.2",
         "tslib": "^2.6.2"
       },
       "engines": {

-        "node": ">=18.0.0"

*        "node": ">=20.0.0"
       }
  },
  "node_modules/@aws-sdk/credential-provider-cognito-identity": {

-      "version": "3.864.0",
-      "resolved": "https://registry.npmjs.org/@aws-sdk/credential-provider-cognito-identity/-/credential-provider-cognito-identity-3.864.0.tgz",
-      "integrity": "sha512-jF6xJS67nPvJ/ElvdA2Q/EDArTcd0fKS3R6zImupOkTMm9PwmEM/BM7hpQCUFkVcaUhtvPpYCtuolGq9ezuKng==",
-      "license": "Apache-2.0",

*      "version": "3.972.29",
*      "resolved": "https://registry.npmjs.org/@aws-sdk/credential-provider-cognito-identity/-/credential-provider-cognito-identity-3.972.29.tgz",
*      "integrity": "sha512-fklwtMw+9+1TRNa7KOCaaE9P9ubN6PdKCVlviX/vPRNtnMGIivAFrWcYsAcyw+sHPPioiSCSOHKKAhtOkO6IGg==",
       "dependencies": {

-        "@aws-sdk/client-cognito-identity": "3.864.0",
-        "@aws-sdk/types": "3.862.0",
-        "@smithy/property-provider": "^4.0.5",
-        "@smithy/types": "^4.3.2",

*        "@aws-sdk/nested-clients": "^3.997.4",
*        "@aws-sdk/types": "^3.973.8",
*        "@smithy/property-provider": "^4.2.14",
*        "@smithy/types": "^4.14.1",
         "tslib": "^2.6.2"
       },
       "engines": {

-        "node": ">=18.0.0"

*        "node": ">=20.0.0"
       }
  },
  "node_modules/@aws-sdk/credential-provider-env": {

-      "version": "3.864.0",
-      "resolved": "https://registry.npmjs.org/@aws-sdk/credential-provider-env/-/credential-provider-env-3.864.0.tgz",
-      "integrity": "sha512-StJPOI2Rt8UE6lYjXUpg6tqSZaM72xg46ljPg8kIevtBAAfdtq9K20qT/kSliWGIBocMFAv0g2mC0hAa+ECyvg==",
-      "license": "Apache-2.0",

*      "version": "3.972.32",
*      "resolved": "https://registry.npmjs.org/@aws-sdk/credential-provider-env/-/credential-provider-env-3.972.32.tgz",
*      "integrity": "sha512-7vA4GHg8NSmQxquJHSBcSM3RgB4ZaaRi6u4+zGFKOmOH6aqlgr2Sda46clkZDYzlirgfY96w15Zj0jh6PT48ng==",
       "dependencies": {

-        "@aws-sdk/core": "3.864.0",
-        "@aws-sdk/types": "3.862.0",
-        "@smithy/property-provider": "^4.0.5",
-        "@smithy/types": "^4.3.2",

*        "@aws-sdk/core": "^3.974.6",
*        "@aws-sdk/types": "^3.973.8",
*        "@smithy/property-provider": "^4.2.14",
*        "@smithy/types": "^4.14.1",
         "tslib": "^2.6.2"
       },
       "engines": {

-        "node": ">=18.0.0"

*        "node": ">=20.0.0"
       }
  },
  "node_modules/@aws-sdk/credential-provider-http": {

-      "version": "3.864.0",
-      "resolved": "https://registry.npmjs.org/@aws-sdk/credential-provider-http/-/credential-provider-http-3.864.0.tgz",
-      "integrity": "sha512-E/RFVxGTuGnuD+9pFPH2j4l6HvrXzPhmpL8H8nOoJUosjx7d4v93GJMbbl1v/fkDLqW9qN4Jx2cI6PAjohA6OA==",
-      "license": "Apache-2.0",

*      "version": "3.972.34",
*      "resolved": "https://registry.npmjs.org/@aws-sdk/credential-provider-http/-/credential-provider-http-3.972.34.tgz",
*      "integrity": "sha512-vBrhWujFCLp1u8ptJRWYlipMutzPptb8pDQ00rKVH9q67T7rGd3VTWIj63aKrlLuY6qSsw1Rt5F/D/7wnNgryA==",
       "dependencies": {

-        "@aws-sdk/core": "3.864.0",
-        "@aws-sdk/types": "3.862.0",
-        "@smithy/fetch-http-handler": "^5.1.1",
-        "@smithy/node-http-handler": "^4.1.1",
-        "@smithy/property-provider": "^4.0.5",
-        "@smithy/protocol-http": "^5.1.3",
-        "@smithy/smithy-client": "^4.4.10",
-        "@smithy/types": "^4.3.2",
-        "@smithy/util-stream": "^4.2.4",

*        "@aws-sdk/core": "^3.974.6",
*        "@aws-sdk/types": "^3.973.8",
*        "@smithy/fetch-http-handler": "^5.3.17",
*        "@smithy/node-http-handler": "^4.6.1",
*        "@smithy/property-provider": "^4.2.14",
*        "@smithy/protocol-http": "^5.3.14",
*        "@smithy/smithy-client": "^4.12.13",
*        "@smithy/types": "^4.14.1",
*        "@smithy/util-stream": "^4.5.25",
         "tslib": "^2.6.2"
       },
       "engines": {

-        "node": ">=18.0.0"

*        "node": ">=20.0.0"
       }
  },
  "node_modules/@aws-sdk/credential-provider-ini": {

-      "version": "3.864.0",
-      "resolved": "https://registry.npmjs.org/@aws-sdk/credential-provider-ini/-/credential-provider-ini-3.864.0.tgz",
-      "integrity": "sha512-PlxrijguR1gxyPd5EYam6OfWLarj2MJGf07DvCx9MAuQkw77HBnsu6+XbV8fQriFuoJVTBLn9ROhMr/ROAYfUg==",
-      "license": "Apache-2.0",
-      "dependencies": {
-        "@aws-sdk/core": "3.864.0",
-        "@aws-sdk/credential-provider-env": "3.864.0",
-        "@aws-sdk/credential-provider-http": "3.864.0",
-        "@aws-sdk/credential-provider-process": "3.864.0",
-        "@aws-sdk/credential-provider-sso": "3.864.0",
-        "@aws-sdk/credential-provider-web-identity": "3.864.0",
-        "@aws-sdk/nested-clients": "3.864.0",
-        "@aws-sdk/types": "3.862.0",
-        "@smithy/credential-provider-imds": "^4.0.7",
-        "@smithy/property-provider": "^4.0.5",
-        "@smithy/shared-ini-file-loader": "^4.0.5",
-        "@smithy/types": "^4.3.2",

*      "version": "3.972.36",
*      "resolved": "https://registry.npmjs.org/@aws-sdk/credential-provider-ini/-/credential-provider-ini-3.972.36.tgz",
*      "integrity": "sha512-FBHyCmV8EB0gUvh1d+CZm87zt2PrdC7OyWexLRoH3I5zWSOUGa+9t58Y5jbxRfwUp3AWpHAFvKY6YzgR845sVA==",
*      "dependencies": {
*        "@aws-sdk/core": "^3.974.6",
*        "@aws-sdk/credential-provider-env": "^3.972.32",
*        "@aws-sdk/credential-provider-http": "^3.972.34",
*        "@aws-sdk/credential-provider-login": "^3.972.36",
*        "@aws-sdk/credential-provider-process": "^3.972.32",
*        "@aws-sdk/credential-provider-sso": "^3.972.36",
*        "@aws-sdk/credential-provider-web-identity": "^3.972.36",
*        "@aws-sdk/nested-clients": "^3.997.4",
*        "@aws-sdk/types": "^3.973.8",
*        "@smithy/credential-provider-imds": "^4.2.14",
*        "@smithy/property-provider": "^4.2.14",
*        "@smithy/shared-ini-file-loader": "^4.4.9",
*        "@smithy/types": "^4.14.1",
         "tslib": "^2.6.2"
       },
       "engines": {

-        "node": ">=18.0.0"

*        "node": ">=20.0.0"
*      }
* },
* "node_modules/@aws-sdk/credential-provider-login": {
*      "version": "3.972.36",
*      "resolved": "https://registry.npmjs.org/@aws-sdk/credential-provider-login/-/credential-provider-login-3.972.36.tgz",
*      "integrity": "sha512-IFap01lJKxQc0C/OHmZwZQr/cKq0DhrcmKedRrdnnl42D+P0SImnnnWQjv07uIPqpEdtqmkPXb9TiPYTU+prxQ==",
*      "dependencies": {
*        "@aws-sdk/core": "^3.974.6",
*        "@aws-sdk/nested-clients": "^3.997.4",
*        "@aws-sdk/types": "^3.973.8",
*        "@smithy/property-provider": "^4.2.14",
*        "@smithy/protocol-http": "^5.3.14",
*        "@smithy/shared-ini-file-loader": "^4.4.9",
*        "@smithy/types": "^4.14.1",
*        "tslib": "^2.6.2"
*      },
*      "engines": {
*        "node": ">=20.0.0"
       }
  },
  "node_modules/@aws-sdk/credential-provider-node": {

-      "version": "3.864.0",
-      "resolved": "https://registry.npmjs.org/@aws-sdk/credential-provider-node/-/credential-provider-node-3.864.0.tgz",
-      "integrity": "sha512-2BEymFeXURS+4jE9tP3vahPwbYRl0/1MVaFZcijj6pq+nf5EPGvkFillbdBRdc98ZI2NedZgSKu3gfZXgYdUhQ==",
-      "license": "Apache-2.0",

*      "version": "3.972.37",
*      "resolved": "https://registry.npmjs.org/@aws-sdk/credential-provider-node/-/credential-provider-node-3.972.37.tgz",
*      "integrity": "sha512-/WFixFAAiw8WpmjZcI0l4t3DerXLmVinOIfuotmRZnu2qmsFPoqqmstASz0z8bi1pGdFXzeLzf6bwucM3mZcUQ==",
       "dependencies": {

-        "@aws-sdk/credential-provider-env": "3.864.0",
-        "@aws-sdk/credential-provider-http": "3.864.0",
-        "@aws-sdk/credential-provider-ini": "3.864.0",
-        "@aws-sdk/credential-provider-process": "3.864.0",
-        "@aws-sdk/credential-provider-sso": "3.864.0",
-        "@aws-sdk/credential-provider-web-identity": "3.864.0",
-        "@aws-sdk/types": "3.862.0",
-        "@smithy/credential-provider-imds": "^4.0.7",
-        "@smithy/property-provider": "^4.0.5",
-        "@smithy/shared-ini-file-loader": "^4.0.5",
-        "@smithy/types": "^4.3.2",

*        "@aws-sdk/credential-provider-env": "^3.972.32",
*        "@aws-sdk/credential-provider-http": "^3.972.34",
*        "@aws-sdk/credential-provider-ini": "^3.972.36",
*        "@aws-sdk/credential-provider-process": "^3.972.32",
*        "@aws-sdk/credential-provider-sso": "^3.972.36",
*        "@aws-sdk/credential-provider-web-identity": "^3.972.36",
*        "@aws-sdk/types": "^3.973.8",
*        "@smithy/credential-provider-imds": "^4.2.14",
*        "@smithy/property-provider": "^4.2.14",
*        "@smithy/shared-ini-file-loader": "^4.4.9",
*        "@smithy/types": "^4.14.1",
         "tslib": "^2.6.2"
       },
       "engines": {

-        "node": ">=18.0.0"

*        "node": ">=20.0.0"
       }
  },
  "node_modules/@aws-sdk/credential-provider-process": {

-      "version": "3.864.0",
-      "resolved": "https://registry.npmjs.org/@aws-sdk/credential-provider-process/-/credential-provider-process-3.864.0.tgz",
-      "integrity": "sha512-Zxnn1hxhq7EOqXhVYgkF4rI9MnaO3+6bSg/tErnBQ3F8kDpA7CFU24G1YxwaJXp2X4aX3LwthefmSJHwcVP/2g==",
-      "license": "Apache-2.0",

*      "version": "3.972.32",
*      "resolved": "https://registry.npmjs.org/@aws-sdk/credential-provider-process/-/credential-provider-process-3.972.32.tgz",
*      "integrity": "sha512-uZp4tlGbpczV8QxmtIwOpSkcyGtBRR8/T4BAumRKfAt1nwCig3FSCZvrKl6ARDIDVRYn5p2oRcAsfFR01EgMGA==",
       "dependencies": {

-        "@aws-sdk/core": "3.864.0",
-        "@aws-sdk/types": "3.862.0",
-        "@smithy/property-provider": "^4.0.5",
-        "@smithy/shared-ini-file-loader": "^4.0.5",
-        "@smithy/types": "^4.3.2",

*        "@aws-sdk/core": "^3.974.6",
*        "@aws-sdk/types": "^3.973.8",
*        "@smithy/property-provider": "^4.2.14",
*        "@smithy/shared-ini-file-loader": "^4.4.9",
*        "@smithy/types": "^4.14.1",
         "tslib": "^2.6.2"
       },
       "engines": {

-        "node": ">=18.0.0"

*        "node": ">=20.0.0"
       }
  },
  "node_modules/@aws-sdk/credential-provider-sso": {

-      "version": "3.864.0",
-      "resolved": "https://registry.npmjs.org/@aws-sdk/credential-provider-sso/-/credential-provider-sso-3.864.0.tgz",
-      "integrity": "sha512-UPyPNQbxDwHVGmgWdGg9/9yvzuedRQVF5jtMkmP565YX9pKZ8wYAcXhcYdNPWFvH0GYdB0crKOmvib+bmCuwkw==",
-      "license": "Apache-2.0",

*      "version": "3.972.36",
*      "resolved": "https://registry.npmjs.org/@aws-sdk/credential-provider-sso/-/credential-provider-sso-3.972.36.tgz",
*      "integrity": "sha512-DsLr0UHMyKzRJKe2bjlwU8q1cfoXg8TIJKV/xwvnalAemiZLOZunFzj/whGnFDZIBVLdnbLiwv5SvRf1+CSwkg==",
       "dependencies": {

-        "@aws-sdk/client-sso": "3.864.0",
-        "@aws-sdk/core": "3.864.0",
-        "@aws-sdk/token-providers": "3.864.0",
-        "@aws-sdk/types": "3.862.0",
-        "@smithy/property-provider": "^4.0.5",
-        "@smithy/shared-ini-file-loader": "^4.0.5",
-        "@smithy/types": "^4.3.2",

*        "@aws-sdk/core": "^3.974.6",
*        "@aws-sdk/nested-clients": "^3.997.4",
*        "@aws-sdk/token-providers": "3.1038.0",
*        "@aws-sdk/types": "^3.973.8",
*        "@smithy/property-provider": "^4.2.14",
*        "@smithy/shared-ini-file-loader": "^4.4.9",
*        "@smithy/types": "^4.14.1",
         "tslib": "^2.6.2"
       },
       "engines": {

-        "node": ">=18.0.0"

*        "node": ">=20.0.0"
       }
  },
  "node_modules/@aws-sdk/credential-provider-web-identity": {

-      "version": "3.864.0",
-      "resolved": "https://registry.npmjs.org/@aws-sdk/credential-provider-web-identity/-/credential-provider-web-identity-3.864.0.tgz",
-      "integrity": "sha512-nNcjPN4SYg8drLwqK0vgVeSvxeGQiD0FxOaT38mV2H8cu0C5NzpvA+14Xy+W6vT84dxgmJYKk71Cr5QL2Oz+rA==",
-      "license": "Apache-2.0",

*      "version": "3.972.36",
*      "resolved": "https://registry.npmjs.org/@aws-sdk/credential-provider-web-identity/-/credential-provider-web-identity-3.972.36.tgz",
*      "integrity": "sha512-uzrURO7frJhHQVVNR5zBJcCYeMYflmXcWBK1+MiBym2Dfjh6nXATrMixrmGZi+97Q7ETZ+y/4lUwAy0Nfnznjw==",
       "dependencies": {

-        "@aws-sdk/core": "3.864.0",
-        "@aws-sdk/nested-clients": "3.864.0",
-        "@aws-sdk/types": "3.862.0",
-        "@smithy/property-provider": "^4.0.5",
-        "@smithy/types": "^4.3.2",

*        "@aws-sdk/core": "^3.974.6",
*        "@aws-sdk/nested-clients": "^3.997.4",
*        "@aws-sdk/types": "^3.973.8",
*        "@smithy/property-provider": "^4.2.14",
*        "@smithy/shared-ini-file-loader": "^4.4.9",
*        "@smithy/types": "^4.14.1",
         "tslib": "^2.6.2"
       },
       "engines": {

-        "node": ">=18.0.0"

*        "node": ">=20.0.0"
       }
  },
  "node_modules/@aws-sdk/credential-providers": {

-      "version": "3.864.0",
-      "resolved": "https://registry.npmjs.org/@aws-sdk/credential-providers/-/credential-providers-3.864.0.tgz",
-      "integrity": "sha512-k4K7PzvHpdHQLczgWT26Yk6t+VBwZ35jkIQ3dKODvBjfzlYHTX0y+VgemmDWrat1ahKfYb/OAw/gdwmnyxsAsw==",
-      "license": "Apache-2.0",
-      "dependencies": {
-        "@aws-sdk/client-cognito-identity": "3.864.0",
-        "@aws-sdk/core": "3.864.0",
-        "@aws-sdk/credential-provider-cognito-identity": "3.864.0",
-        "@aws-sdk/credential-provider-env": "3.864.0",
-        "@aws-sdk/credential-provider-http": "3.864.0",
-        "@aws-sdk/credential-provider-ini": "3.864.0",
-        "@aws-sdk/credential-provider-node": "3.864.0",
-        "@aws-sdk/credential-provider-process": "3.864.0",
-        "@aws-sdk/credential-provider-sso": "3.864.0",
-        "@aws-sdk/credential-provider-web-identity": "3.864.0",
-        "@aws-sdk/nested-clients": "3.864.0",
-        "@aws-sdk/types": "3.862.0",
-        "@smithy/config-resolver": "^4.1.5",
-        "@smithy/core": "^3.8.0",
-        "@smithy/credential-provider-imds": "^4.0.7",
-        "@smithy/node-config-provider": "^4.1.4",
-        "@smithy/property-provider": "^4.0.5",
-        "@smithy/types": "^4.3.2",

*      "version": "3.1038.0",
*      "resolved": "https://registry.npmjs.org/@aws-sdk/credential-providers/-/credential-providers-3.1038.0.tgz",
*      "integrity": "sha512-+B9BuRVPPKF0Q6msVS4vUGOsL4eUg7XYogikp56rUEQVoUVxn5ONyWlnNzsDMTv+BwuBgFo5N7gRZtEToAnSgg==",
*      "dependencies": {
*        "@aws-sdk/client-cognito-identity": "3.1038.0",
*        "@aws-sdk/core": "^3.974.6",
*        "@aws-sdk/credential-provider-cognito-identity": "^3.972.29",
*        "@aws-sdk/credential-provider-env": "^3.972.32",
*        "@aws-sdk/credential-provider-http": "^3.972.34",
*        "@aws-sdk/credential-provider-ini": "^3.972.36",
*        "@aws-sdk/credential-provider-login": "^3.972.36",
*        "@aws-sdk/credential-provider-node": "^3.972.37",
*        "@aws-sdk/credential-provider-process": "^3.972.32",
*        "@aws-sdk/credential-provider-sso": "^3.972.36",
*        "@aws-sdk/credential-provider-web-identity": "^3.972.36",
*        "@aws-sdk/nested-clients": "^3.997.4",
*        "@aws-sdk/types": "^3.973.8",
*        "@smithy/config-resolver": "^4.4.17",
*        "@smithy/core": "^3.23.17",
*        "@smithy/credential-provider-imds": "^4.2.14",
*        "@smithy/node-config-provider": "^4.3.14",
*        "@smithy/property-provider": "^4.2.14",
*        "@smithy/types": "^4.14.1",
         "tslib": "^2.6.2"
       },
       "engines": {

-        "node": ">=18.0.0"

*        "node": ">=20.0.0"
       }
  },
  "node_modules/@aws-sdk/middleware-host-header": {

-      "version": "3.862.0",
-      "resolved": "https://registry.npmjs.org/@aws-sdk/middleware-host-header/-/middleware-host-header-3.862.0.tgz",
-      "integrity": "sha512-jDje8dCFeFHfuCAxMDXBs8hy8q9NCTlyK4ThyyfAj3U4Pixly2mmzY2u7b7AyGhWsjJNx8uhTjlYq5zkQPQCYw==",
-      "license": "Apache-2.0",

*      "version": "3.972.10",
*      "resolved": "https://registry.npmjs.org/@aws-sdk/middleware-host-header/-/middleware-host-header-3.972.10.tgz",
*      "integrity": "sha512-IJSsIMeVQ8MMCPbuh1AbltkFhLBLXn7aejzfX5YKT/VLDHn++Dcz8886tXckE+wQssyPUhaXrJhdakO2VilRhg==",
       "dependencies": {

-        "@aws-sdk/types": "3.862.0",
-        "@smithy/protocol-http": "^5.1.3",
-        "@smithy/types": "^4.3.2",

*        "@aws-sdk/types": "^3.973.8",
*        "@smithy/protocol-http": "^5.3.14",
*        "@smithy/types": "^4.14.1",
         "tslib": "^2.6.2"
       },
       "engines": {

-        "node": ">=18.0.0"

*        "node": ">=20.0.0"
       }
  },
  "node_modules/@aws-sdk/middleware-logger": {

-      "version": "3.862.0",
-      "resolved": "https://registry.npmjs.org/@aws-sdk/middleware-logger/-/middleware-logger-3.862.0.tgz",
-      "integrity": "sha512-N/bXSJznNBR/i7Ofmf9+gM6dx/SPBK09ZWLKsW5iQjqKxAKn/2DozlnE54uiEs1saHZWoNDRg69Ww4XYYSlG1Q==",
-      "license": "Apache-2.0",

*      "version": "3.972.10",
*      "resolved": "https://registry.npmjs.org/@aws-sdk/middleware-logger/-/middleware-logger-3.972.10.tgz",
*      "integrity": "sha512-OOuGvvz1Dm20SjZo5oEBePFqxt5nf8AwkNDSyUHvD9/bfNASmstcYxFAHUowy4n6Io7mWUZ04JURZwSBvyQanQ==",
       "dependencies": {

-        "@aws-sdk/types": "3.862.0",
-        "@smithy/types": "^4.3.2",

*        "@aws-sdk/types": "^3.973.8",
*        "@smithy/types": "^4.14.1",
         "tslib": "^2.6.2"
       },
       "engines": {

-        "node": ">=18.0.0"

*        "node": ">=20.0.0"
       }
  },
  "node_modules/@aws-sdk/middleware-recursion-detection": {

-      "version": "3.862.0",
-      "resolved": "https://registry.npmjs.org/@aws-sdk/middleware-recursion-detection/-/middleware-recursion-detection-3.862.0.tgz",
-      "integrity": "sha512-KVoo3IOzEkTq97YKM4uxZcYFSNnMkhW/qj22csofLegZi5fk90ztUnnaeKfaEJHfHp/tm1Y3uSoOXH45s++kKQ==",
-      "license": "Apache-2.0",

*      "version": "3.972.11",
*      "resolved": "https://registry.npmjs.org/@aws-sdk/middleware-recursion-detection/-/middleware-recursion-detection-3.972.11.tgz",
*      "integrity": "sha512-+zz6f79Kj9V5qFK2P+D8Ehjnw4AhphAlCAsPjUqEcInA9umtSSKMrHbSagEeOIsDNuvVrH98bjRHcyQukTrhaQ==",
       "dependencies": {

-        "@aws-sdk/types": "3.862.0",
-        "@smithy/protocol-http": "^5.1.3",
-        "@smithy/types": "^4.3.2",

*        "@aws-sdk/types": "^3.973.8",
*        "@aws/lambda-invoke-store": "^0.2.2",
*        "@smithy/protocol-http": "^5.3.14",
*        "@smithy/types": "^4.14.1",
         "tslib": "^2.6.2"
       },
       "engines": {

-        "node": ">=18.0.0"

*        "node": ">=20.0.0"
*      }
* },
* "node_modules/@aws-sdk/middleware-sdk-s3": {
*      "version": "3.972.35",
*      "resolved": "https://registry.npmjs.org/@aws-sdk/middleware-sdk-s3/-/middleware-sdk-s3-3.972.35.tgz",
*      "integrity": "sha512-lLppaNTAz+wNgLdi4FtHzrlwrGF0ODTnBWHBaFg85SKs0eJ+M+tP5ifrA8f/0lNd+Ak3MC1NGC6RavV3ny4HTg==",
*      "dependencies": {
*        "@aws-sdk/core": "^3.974.6",
*        "@aws-sdk/types": "^3.973.8",
*        "@aws-sdk/util-arn-parser": "^3.972.3",
*        "@smithy/core": "^3.23.17",
*        "@smithy/node-config-provider": "^4.3.14",
*        "@smithy/protocol-http": "^5.3.14",
*        "@smithy/signature-v4": "^5.3.14",
*        "@smithy/smithy-client": "^4.12.13",
*        "@smithy/types": "^4.14.1",
*        "@smithy/util-config-provider": "^4.2.2",
*        "@smithy/util-middleware": "^4.2.14",
*        "@smithy/util-stream": "^4.5.25",
*        "@smithy/util-utf8": "^4.2.2",
*        "tslib": "^2.6.2"
*      },
*      "engines": {
*        "node": ">=20.0.0"
       }
  },
  "node_modules/@aws-sdk/middleware-user-agent": {

-      "version": "3.864.0",
-      "resolved": "https://registry.npmjs.org/@aws-sdk/middleware-user-agent/-/middleware-user-agent-3.864.0.tgz",
-      "integrity": "sha512-wrddonw4EyLNSNBrApzEhpSrDwJiNfjxDm5E+bn8n32BbAojXASH8W8jNpxz/jMgNkkJNxCfyqybGKzBX0OhbQ==",
-      "license": "Apache-2.0",

*      "version": "3.972.36",
*      "resolved": "https://registry.npmjs.org/@aws-sdk/middleware-user-agent/-/middleware-user-agent-3.972.36.tgz",
*      "integrity": "sha512-O2beToxguBvrZFFZ+fFgPbbae8MvyIBjQ6lImee4APHEXXNAD5ZJ2ayLF1mb7rsKw86TM81y5czg82bZncjSjg==",
       "dependencies": {

-        "@aws-sdk/core": "3.864.0",
-        "@aws-sdk/types": "3.862.0",
-        "@aws-sdk/util-endpoints": "3.862.0",
-        "@smithy/core": "^3.8.0",
-        "@smithy/protocol-http": "^5.1.3",
-        "@smithy/types": "^4.3.2",

*        "@aws-sdk/core": "^3.974.6",
*        "@aws-sdk/types": "^3.973.8",
*        "@aws-sdk/util-endpoints": "^3.996.8",
*        "@smithy/core": "^3.23.17",
*        "@smithy/protocol-http": "^5.3.14",
*        "@smithy/types": "^4.14.1",
*        "@smithy/util-retry": "^4.3.5",
         "tslib": "^2.6.2"
       },
       "engines": {

-        "node": ">=18.0.0"

*        "node": ">=20.0.0"
       }
  },
  "node_modules/@aws-sdk/nested-clients": {

-      "version": "3.864.0",
-      "resolved": "https://registry.npmjs.org/@aws-sdk/nested-clients/-/nested-clients-3.864.0.tgz",
-      "integrity": "sha512-H1C+NjSmz2y8Tbgh7Yy89J20yD/hVyk15hNoZDbCYkXg0M358KS7KVIEYs8E2aPOCr1sK3HBE819D/yvdMgokA==",
-      "license": "Apache-2.0",

*      "version": "3.997.4",
*      "resolved": "https://registry.npmjs.org/@aws-sdk/nested-clients/-/nested-clients-3.997.4.tgz",
*      "integrity": "sha512-4Sf+WY1lMJzXlw5MiyCMe/UzdILCwvuaHThbqMXS6dfh9gZy3No360I42RXquOI/ULUOhWy2HCyU0Fp20fQGPQ==",
       "dependencies": {
         "@aws-crypto/sha256-browser": "5.2.0",
         "@aws-crypto/sha256-js": "5.2.0",

-        "@aws-sdk/core": "3.864.0",
-        "@aws-sdk/middleware-host-header": "3.862.0",
-        "@aws-sdk/middleware-logger": "3.862.0",
-        "@aws-sdk/middleware-recursion-detection": "3.862.0",
-        "@aws-sdk/middleware-user-agent": "3.864.0",
-        "@aws-sdk/region-config-resolver": "3.862.0",
-        "@aws-sdk/types": "3.862.0",
-        "@aws-sdk/util-endpoints": "3.862.0",
-        "@aws-sdk/util-user-agent-browser": "3.862.0",
-        "@aws-sdk/util-user-agent-node": "3.864.0",
-        "@smithy/config-resolver": "^4.1.5",
-        "@smithy/core": "^3.8.0",
-        "@smithy/fetch-http-handler": "^5.1.1",
-        "@smithy/hash-node": "^4.0.5",
-        "@smithy/invalid-dependency": "^4.0.5",
-        "@smithy/middleware-content-length": "^4.0.5",
-        "@smithy/middleware-endpoint": "^4.1.18",
-        "@smithy/middleware-retry": "^4.1.19",
-        "@smithy/middleware-serde": "^4.0.9",
-        "@smithy/middleware-stack": "^4.0.5",
-        "@smithy/node-config-provider": "^4.1.4",
-        "@smithy/node-http-handler": "^4.1.1",
-        "@smithy/protocol-http": "^5.1.3",
-        "@smithy/smithy-client": "^4.4.10",
-        "@smithy/types": "^4.3.2",
-        "@smithy/url-parser": "^4.0.5",
-        "@smithy/util-base64": "^4.0.0",
-        "@smithy/util-body-length-browser": "^4.0.0",
-        "@smithy/util-body-length-node": "^4.0.0",
-        "@smithy/util-defaults-mode-browser": "^4.0.26",
-        "@smithy/util-defaults-mode-node": "^4.0.26",
-        "@smithy/util-endpoints": "^3.0.7",
-        "@smithy/util-middleware": "^4.0.5",
-        "@smithy/util-retry": "^4.0.7",
-        "@smithy/util-utf8": "^4.0.0",

*        "@aws-sdk/core": "^3.974.6",
*        "@aws-sdk/middleware-host-header": "^3.972.10",
*        "@aws-sdk/middleware-logger": "^3.972.10",
*        "@aws-sdk/middleware-recursion-detection": "^3.972.11",
*        "@aws-sdk/middleware-user-agent": "^3.972.36",
*        "@aws-sdk/region-config-resolver": "^3.972.13",
*        "@aws-sdk/signature-v4-multi-region": "^3.996.23",
*        "@aws-sdk/types": "^3.973.8",
*        "@aws-sdk/util-endpoints": "^3.996.8",
*        "@aws-sdk/util-user-agent-browser": "^3.972.10",
*        "@aws-sdk/util-user-agent-node": "^3.973.22",
*        "@smithy/config-resolver": "^4.4.17",
*        "@smithy/core": "^3.23.17",
*        "@smithy/fetch-http-handler": "^5.3.17",
*        "@smithy/hash-node": "^4.2.14",
*        "@smithy/invalid-dependency": "^4.2.14",
*        "@smithy/middleware-content-length": "^4.2.14",
*        "@smithy/middleware-endpoint": "^4.4.32",
*        "@smithy/middleware-retry": "^4.5.6",
*        "@smithy/middleware-serde": "^4.2.20",
*        "@smithy/middleware-stack": "^4.2.14",
*        "@smithy/node-config-provider": "^4.3.14",
*        "@smithy/node-http-handler": "^4.6.1",
*        "@smithy/protocol-http": "^5.3.14",
*        "@smithy/smithy-client": "^4.12.13",
*        "@smithy/types": "^4.14.1",
*        "@smithy/url-parser": "^4.2.14",
*        "@smithy/util-base64": "^4.3.2",
*        "@smithy/util-body-length-browser": "^4.2.2",
*        "@smithy/util-body-length-node": "^4.2.3",
*        "@smithy/util-defaults-mode-browser": "^4.3.49",
*        "@smithy/util-defaults-mode-node": "^4.2.54",
*        "@smithy/util-endpoints": "^3.4.2",
*        "@smithy/util-middleware": "^4.2.14",
*        "@smithy/util-retry": "^4.3.5",
*        "@smithy/util-utf8": "^4.2.2",
         "tslib": "^2.6.2"
       },
       "engines": {

-        "node": ">=18.0.0"

*        "node": ">=20.0.0"
       }
  },
  "node_modules/@aws-sdk/region-config-resolver": {

-      "version": "3.862.0",
-      "resolved": "https://registry.npmjs.org/@aws-sdk/region-config-resolver/-/region-config-resolver-3.862.0.tgz",
-      "integrity": "sha512-VisR+/HuVFICrBPY+q9novEiE4b3mvDofWqyvmxHcWM7HumTz9ZQSuEtnlB/92GVM3KDUrR9EmBHNRrfXYZkcQ==",
-      "license": "Apache-2.0",

*      "version": "3.972.13",
*      "resolved": "https://registry.npmjs.org/@aws-sdk/region-config-resolver/-/region-config-resolver-3.972.13.tgz",
*      "integrity": "sha512-CvJ2ZIjK/jVD/lbOpowBVElJyC1YxLTIJ13yM0AEo0t2v7swOzGjSA6lJGH+DwZXQhcjUjoYwc8bVYCX5MDr1A==",
       "dependencies": {

-        "@aws-sdk/types": "3.862.0",
-        "@smithy/node-config-provider": "^4.1.4",
-        "@smithy/types": "^4.3.2",
-        "@smithy/util-config-provider": "^4.0.0",
-        "@smithy/util-middleware": "^4.0.5",

*        "@aws-sdk/types": "^3.973.8",
*        "@smithy/config-resolver": "^4.4.17",
*        "@smithy/node-config-provider": "^4.3.14",
*        "@smithy/types": "^4.14.1",
         "tslib": "^2.6.2"
       },
       "engines": {

-        "node": ">=18.0.0"

*        "node": ">=20.0.0"
*      }
* },
* "node_modules/@aws-sdk/signature-v4-multi-region": {
*      "version": "3.996.23",
*      "resolved": "https://registry.npmjs.org/@aws-sdk/signature-v4-multi-region/-/signature-v4-multi-region-3.996.23.tgz",
*      "integrity": "sha512-wBbys3Y53Ikly556vyADurKpYQHXS7Jjaskbz+Ga9PZCz7PB/9f3VdKbDlz7dqIzn+xwz7L/a6TR4iXcOi8IRw==",
*      "dependencies": {
*        "@aws-sdk/middleware-sdk-s3": "^3.972.35",
*        "@aws-sdk/types": "^3.973.8",
*        "@smithy/protocol-http": "^5.3.14",
*        "@smithy/signature-v4": "^5.3.14",
*        "@smithy/types": "^4.14.1",
*        "tslib": "^2.6.2"
*      },
*      "engines": {
*        "node": ">=20.0.0"
       }
  },
  "node_modules/@aws-sdk/token-providers": {

-      "version": "3.864.0",
-      "resolved": "https://registry.npmjs.org/@aws-sdk/token-providers/-/token-providers-3.864.0.tgz",
-      "integrity": "sha512-gTc2QHOBo05SCwVA65dUtnJC6QERvFaPiuppGDSxoF7O5AQNK0UR/kMSenwLqN8b5E1oLYvQTv3C1idJLRX0cg==",
-      "license": "Apache-2.0",

*      "version": "3.1038.0",
*      "resolved": "https://registry.npmjs.org/@aws-sdk/token-providers/-/token-providers-3.1038.0.tgz",
*      "integrity": "sha512-Qniru+9oGGb/HNK/gGZWbV3jsD0k71ngE7qMQ/x6gYNYLd2EOwHCS6E2E6jfkaqO4i0d+nNKmfRy8bNcshKdGQ==",
       "dependencies": {

-        "@aws-sdk/core": "3.864.0",
-        "@aws-sdk/nested-clients": "3.864.0",
-        "@aws-sdk/types": "3.862.0",
-        "@smithy/property-provider": "^4.0.5",
-        "@smithy/shared-ini-file-loader": "^4.0.5",
-        "@smithy/types": "^4.3.2",

*        "@aws-sdk/core": "^3.974.6",
*        "@aws-sdk/nested-clients": "^3.997.4",
*        "@aws-sdk/types": "^3.973.8",
*        "@smithy/property-provider": "^4.2.14",
*        "@smithy/shared-ini-file-loader": "^4.4.9",
*        "@smithy/types": "^4.14.1",
         "tslib": "^2.6.2"
       },
       "engines": {

-        "node": ">=18.0.0"

*        "node": ">=20.0.0"
       }
  },
  "node_modules/@aws-sdk/types": {

-      "version": "3.862.0",
-      "resolved": "https://registry.npmjs.org/@aws-sdk/types/-/types-3.862.0.tgz",
-      "integrity": "sha512-Bei+RL0cDxxV+lW2UezLbCYYNeJm6Nzee0TpW0FfyTRBhH9C1XQh4+x+IClriXvgBnRquTMMYsmJfvx8iyLKrg==",
-      "license": "Apache-2.0",

*      "version": "3.973.8",
*      "resolved": "https://registry.npmjs.org/@aws-sdk/types/-/types-3.973.8.tgz",
*      "integrity": "sha512-gjlAdtHMbtR9X5iIhVUvbVcy55KnznpC6bkDUWW9z915bi0ckdUr5cjf16Kp6xq0bP5HBD2xzgbL9F9Quv5vUw==",
       "dependencies": {

-        "@smithy/types": "^4.3.2",

*        "@smithy/types": "^4.14.1",
         "tslib": "^2.6.2"
       },
       "engines": {

-        "node": ">=18.0.0"

*        "node": ">=20.0.0"
*      }
* },
* "node_modules/@aws-sdk/util-arn-parser": {
*      "version": "3.972.3",
*      "resolved": "https://registry.npmjs.org/@aws-sdk/util-arn-parser/-/util-arn-parser-3.972.3.tgz",
*      "integrity": "sha512-HzSD8PMFrvgi2Kserxuff5VitNq2sgf3w9qxmskKDiDTThWfVteJxuCS9JXiPIPtmCrp+7N9asfIaVhBFORllA==",
*      "dependencies": {
*        "tslib": "^2.6.2"
*      },
*      "engines": {
*        "node": ">=20.0.0"
       }
  },
  "node_modules/@aws-sdk/util-endpoints": {

-      "version": "3.862.0",
-      "resolved": "https://registry.npmjs.org/@aws-sdk/util-endpoints/-/util-endpoints-3.862.0.tgz",
-      "integrity": "sha512-eCZuScdE9MWWkHGM2BJxm726MCmWk/dlHjOKvkM0sN1zxBellBMw5JohNss1Z8/TUmnW2gb9XHTOiHuGjOdksA==",
-      "license": "Apache-2.0",

*      "version": "3.996.8",
*      "resolved": "https://registry.npmjs.org/@aws-sdk/util-endpoints/-/util-endpoints-3.996.8.tgz",
*      "integrity": "sha512-oOZHcRDihk5iEe5V25NVWg45b3qEA8OpHWVdU/XQh8Zj4heVPAJqWvMphQnU7LkufmUo10EpvFPZuQMiFLJK3g==",
       "dependencies": {

-        "@aws-sdk/types": "3.862.0",
-        "@smithy/types": "^4.3.2",
-        "@smithy/url-parser": "^4.0.5",
-        "@smithy/util-endpoints": "^3.0.7",

*        "@aws-sdk/types": "^3.973.8",
*        "@smithy/types": "^4.14.1",
*        "@smithy/url-parser": "^4.2.14",
*        "@smithy/util-endpoints": "^3.4.2",
         "tslib": "^2.6.2"
       },
       "engines": {

-        "node": ">=18.0.0"

*        "node": ">=20.0.0"
       }
  },
  "node_modules/@aws-sdk/util-locate-window": {

-      "version": "3.804.0",
-      "resolved": "https://registry.npmjs.org/@aws-sdk/util-locate-window/-/util-locate-window-3.804.0.tgz",
-      "integrity": "sha512-zVoRfpmBVPodYlnMjgVjfGoEZagyRF5IPn3Uo6ZvOZp24chnW/FRstH7ESDHDDRga4z3V+ElUQHKpFDXWyBW5A==",
-      "license": "Apache-2.0",

*      "version": "3.965.5",
*      "resolved": "https://registry.npmjs.org/@aws-sdk/util-locate-window/-/util-locate-window-3.965.5.tgz",
*      "integrity": "sha512-WhlJNNINQB+9qtLtZJcpQdgZw3SCDCpXdUJP7cToGwHbCWCnRckGlc6Bx/OhWwIYFNAn+FIydY8SZ0QmVu3xTQ==",
       "dependencies": {
         "tslib": "^2.6.2"
       },
       "engines": {

-        "node": ">=18.0.0"

*        "node": ">=20.0.0"
       }
  },
  "node_modules/@aws-sdk/util-user-agent-browser": {

-      "version": "3.862.0",
-      "resolved": "https://registry.npmjs.org/@aws-sdk/util-user-agent-browser/-/util-user-agent-browser-3.862.0.tgz",
-      "integrity": "sha512-BmPTlm0r9/10MMr5ND9E92r8KMZbq5ltYXYpVcUbAsnB1RJ8ASJuRoLne5F7mB3YMx0FJoOTuSq7LdQM3LgW3Q==",
-      "license": "Apache-2.0",

*      "version": "3.972.10",
*      "resolved": "https://registry.npmjs.org/@aws-sdk/util-user-agent-browser/-/util-user-agent-browser-3.972.10.tgz",
*      "integrity": "sha512-FAzqXvfEssGdSIz8ejatan0bOdx1qefBWKF/gWmVBXIP1HkS7v/wjjaqrAGGKvyihrXTXW00/2/1nTJtxpXz7g==",
       "dependencies": {

-        "@aws-sdk/types": "3.862.0",
-        "@smithy/types": "^4.3.2",

*        "@aws-sdk/types": "^3.973.8",
*        "@smithy/types": "^4.14.1",
         "bowser": "^2.11.0",
         "tslib": "^2.6.2"
       }
  },
  "node_modules/@aws-sdk/util-user-agent-node": {

-      "version": "3.864.0",
-      "resolved": "https://registry.npmjs.org/@aws-sdk/util-user-agent-node/-/util-user-agent-node-3.864.0.tgz",
-      "integrity": "sha512-d+FjUm2eJEpP+FRpVR3z6KzMdx1qwxEYDz8jzNKwxYLBBquaBaP/wfoMtMQKAcbrR7aT9FZVZF7zDgzNxUvQlQ==",
-      "license": "Apache-2.0",

*      "version": "3.973.22",
*      "resolved": "https://registry.npmjs.org/@aws-sdk/util-user-agent-node/-/util-user-agent-node-3.973.22.tgz",
*      "integrity": "sha512-YTYqTmOUrwbm1h99Ee4y/mVYpFRl0oSO/amtP5cc1BZZWdaAVWs9zj3TkyRHWvR9aI/ZS8m3mS6awXtYUlWyaw==",
       "dependencies": {

-        "@aws-sdk/middleware-user-agent": "3.864.0",
-        "@aws-sdk/types": "3.862.0",
-        "@smithy/node-config-provider": "^4.1.4",
-        "@smithy/types": "^4.3.2",

*        "@aws-sdk/middleware-user-agent": "^3.972.36",
*        "@aws-sdk/types": "^3.973.8",
*        "@smithy/node-config-provider": "^4.3.14",
*        "@smithy/types": "^4.14.1",
*        "@smithy/util-config-provider": "^4.2.2",
         "tslib": "^2.6.2"
       },
       "engines": {

-        "node": ">=18.0.0"

*        "node": ">=20.0.0"
         },
         "peerDependencies": {
           "aws-crt": ">=1.0.0"
  @@ -736,27 +727,35 @@
  }
  },
  "node_modules/@aws-sdk/xml-builder": {

-      "version": "3.862.0",
-      "resolved": "https://registry.npmjs.org/@aws-sdk/xml-builder/-/xml-builder-3.862.0.tgz",
-      "integrity": "sha512-6Ed0kmC1NMbuFTEgNmamAUU1h5gShgxL1hBVLbEzUa3trX5aJBz1vU4bXaBTvOYUAnOHtiy1Ml4AMStd6hJnFA==",
-      "license": "Apache-2.0",

*      "version": "3.972.21",
*      "resolved": "https://registry.npmjs.org/@aws-sdk/xml-builder/-/xml-builder-3.972.21.tgz",
*      "integrity": "sha512-qxNiHUtlrsjTeSlrPWiFkWps7uD6YB4eKzg7eLAFH8jbiHTlt0ePNlo2Xu+WlftP38JIcMaIX4jTUjOlE2ySWw==",
       "dependencies": {

-        "@smithy/types": "^4.3.2",

*        "@nodable/entities": "2.1.0",
*        "@smithy/types": "^4.14.1",
*        "fast-xml-parser": "5.7.2",
         "tslib": "^2.6.2"
       },
*      "engines": {
*        "node": ">=20.0.0"
*      }
* },
* "node_modules/@aws/lambda-invoke-store": {
*      "version": "0.2.4",
*      "resolved": "https://registry.npmjs.org/@aws/lambda-invoke-store/-/lambda-invoke-store-0.2.4.tgz",
*      "integrity": "sha512-iY8yvjE0y651BixKNPgmv1WrQc+GZ142sb0z4gYnChDDY2YqI4P/jsSopBWrKfAt7LOJAkOXt7rC/hms+WclQQ==",
       "engines": {
         "node": ">=18.0.0"
       }
  },
  "node_modules/@esbuild/aix-ppc64": {

-      "version": "0.25.8",
-      "resolved": "https://registry.npmjs.org/@esbuild/aix-ppc64/-/aix-ppc64-0.25.8.tgz",
-      "integrity": "sha512-urAvrUedIqEiFR3FYSLTWQgLu5tb+m0qZw0NBEasUeo6wuqatkMDaRT+1uABiGXEu5vqgPd7FGE1BhsAIy9QVA==",

*      "version": "0.27.7",
*      "resolved": "https://registry.npmjs.org/@esbuild/aix-ppc64/-/aix-ppc64-0.27.7.tgz",
*      "integrity": "sha512-EKX3Qwmhz1eMdEJokhALr0YiD0lhQNwDqkPYyPhiSwKrh7/4KRjQc04sZ8db+5DVVnZ1LmbNDI1uAMPEUBnQPg==",
       "cpu": [
         "ppc64"
       ],
       "dev": true,

-      "license": "MIT",
         "optional": true,
         "os": [
           "aix"
  @@ -766,14 +765,13 @@
  }
  },
  "node_modules/@esbuild/android-arm": {
-      "version": "0.25.8",
-      "resolved": "https://registry.npmjs.org/@esbuild/android-arm/-/android-arm-0.25.8.tgz",
-      "integrity": "sha512-RONsAvGCz5oWyePVnLdZY/HHwA++nxYWIX1atInlaW6SEkwq6XkP3+cb825EUcRs5Vss/lGh/2YxAb5xqc07Uw==",

*      "version": "0.27.7",
*      "resolved": "https://registry.npmjs.org/@esbuild/android-arm/-/android-arm-0.27.7.tgz",
*      "integrity": "sha512-jbPXvB4Yj2yBV7HUfE2KHe4GJX51QplCN1pGbYjvsyCZbQmies29EoJbkEc+vYuU5o45AfQn37vZlyXy4YJ8RQ==",
       "cpu": [
         "arm"
       ],
       "dev": true,

-      "license": "MIT",
         "optional": true,
         "os": [
           "android"
  @@ -783,14 +781,13 @@
  }
  },
  "node_modules/@esbuild/android-arm64": {
-      "version": "0.25.8",
-      "resolved": "https://registry.npmjs.org/@esbuild/android-arm64/-/android-arm64-0.25.8.tgz",
-      "integrity": "sha512-OD3p7LYzWpLhZEyATcTSJ67qB5D+20vbtr6vHlHWSQYhKtzUYrETuWThmzFpZtFsBIxRvhO07+UgVA9m0i/O1w==",

*      "version": "0.27.7",
*      "resolved": "https://registry.npmjs.org/@esbuild/android-arm64/-/android-arm64-0.27.7.tgz",
*      "integrity": "sha512-62dPZHpIXzvChfvfLJow3q5dDtiNMkwiRzPylSCfriLvZeq0a1bWChrGx/BbUbPwOrsWKMn8idSllklzBy+dgQ==",
       "cpu": [
         "arm64"
       ],
       "dev": true,

-      "license": "MIT",
         "optional": true,
         "os": [
           "android"
  @@ -800,14 +797,13 @@
  }
  },
  "node_modules/@esbuild/android-x64": {
-      "version": "0.25.8",
-      "resolved": "https://registry.npmjs.org/@esbuild/android-x64/-/android-x64-0.25.8.tgz",
-      "integrity": "sha512-yJAVPklM5+4+9dTeKwHOaA+LQkmrKFX96BM0A/2zQrbS6ENCmxc4OVoBs5dPkCCak2roAD+jKCdnmOqKszPkjA==",

*      "version": "0.27.7",
*      "resolved": "https://registry.npmjs.org/@esbuild/android-x64/-/android-x64-0.27.7.tgz",
*      "integrity": "sha512-x5VpMODneVDb70PYV2VQOmIUUiBtY3D3mPBG8NxVk5CogneYhkR7MmM3yR/uMdITLrC1ml/NV1rj4bMJuy9MCg==",
       "cpu": [
         "x64"
       ],
       "dev": true,

-      "license": "MIT",
         "optional": true,
         "os": [
           "android"
  @@ -817,14 +813,13 @@
  }
  },
  "node_modules/@esbuild/darwin-arm64": {
-      "version": "0.25.8",
-      "resolved": "https://registry.npmjs.org/@esbuild/darwin-arm64/-/darwin-arm64-0.25.8.tgz",
-      "integrity": "sha512-Jw0mxgIaYX6R8ODrdkLLPwBqHTtYHJSmzzd+QeytSugzQ0Vg4c5rDky5VgkoowbZQahCbsv1rT1KW72MPIkevw==",

*      "version": "0.27.7",
*      "resolved": "https://registry.npmjs.org/@esbuild/darwin-arm64/-/darwin-arm64-0.27.7.tgz",
*      "integrity": "sha512-5lckdqeuBPlKUwvoCXIgI2D9/ABmPq3Rdp7IfL70393YgaASt7tbju3Ac+ePVi3KDH6N2RqePfHnXkaDtY9fkw==",
       "cpu": [
         "arm64"
       ],
       "dev": true,

-      "license": "MIT",
         "optional": true,
         "os": [
           "darwin"
  @@ -834,14 +829,13 @@
  }
  },
  "node_modules/@esbuild/darwin-x64": {
-      "version": "0.25.8",
-      "resolved": "https://registry.npmjs.org/@esbuild/darwin-x64/-/darwin-x64-0.25.8.tgz",
-      "integrity": "sha512-Vh2gLxxHnuoQ+GjPNvDSDRpoBCUzY4Pu0kBqMBDlK4fuWbKgGtmDIeEC081xi26PPjn+1tct+Bh8FjyLlw1Zlg==",

*      "version": "0.27.7",
*      "resolved": "https://registry.npmjs.org/@esbuild/darwin-x64/-/darwin-x64-0.27.7.tgz",
*      "integrity": "sha512-rYnXrKcXuT7Z+WL5K980jVFdvVKhCHhUwid+dDYQpH+qu+TefcomiMAJpIiC2EM3Rjtq0sO3StMV/+3w3MyyqQ==",
       "cpu": [
         "x64"
       ],
       "dev": true,

-      "license": "MIT",
         "optional": true,
         "os": [
           "darwin"
  @@ -851,14 +845,13 @@
  }
  },
  "node_modules/@esbuild/freebsd-arm64": {
-      "version": "0.25.8",
-      "resolved": "https://registry.npmjs.org/@esbuild/freebsd-arm64/-/freebsd-arm64-0.25.8.tgz",
-      "integrity": "sha512-YPJ7hDQ9DnNe5vxOm6jaie9QsTwcKedPvizTVlqWG9GBSq+BuyWEDazlGaDTC5NGU4QJd666V0yqCBL2oWKPfA==",

*      "version": "0.27.7",
*      "resolved": "https://registry.npmjs.org/@esbuild/freebsd-arm64/-/freebsd-arm64-0.27.7.tgz",
*      "integrity": "sha512-B48PqeCsEgOtzME2GbNM2roU29AMTuOIN91dsMO30t+Ydis3z/3Ngoj5hhnsOSSwNzS+6JppqWsuhTp6E82l2w==",
       "cpu": [
         "arm64"
       ],
       "dev": true,

-      "license": "MIT",
         "optional": true,
         "os": [
           "freebsd"
  @@ -868,14 +861,13 @@
  }
  },
  "node_modules/@esbuild/freebsd-x64": {
-      "version": "0.25.8",
-      "resolved": "https://registry.npmjs.org/@esbuild/freebsd-x64/-/freebsd-x64-0.25.8.tgz",
-      "integrity": "sha512-MmaEXxQRdXNFsRN/KcIimLnSJrk2r5H8v+WVafRWz5xdSVmWLoITZQXcgehI2ZE6gioE6HirAEToM/RvFBeuhw==",

*      "version": "0.27.7",
*      "resolved": "https://registry.npmjs.org/@esbuild/freebsd-x64/-/freebsd-x64-0.27.7.tgz",
*      "integrity": "sha512-jOBDK5XEjA4m5IJK3bpAQF9/Lelu/Z9ZcdhTRLf4cajlB+8VEhFFRjWgfy3M1O4rO2GQ/b2dLwCUGpiF/eATNQ==",
       "cpu": [
         "x64"
       ],
       "dev": true,

-      "license": "MIT",
         "optional": true,
         "os": [
           "freebsd"
  @@ -885,14 +877,13 @@
  }
  },
  "node_modules/@esbuild/linux-arm": {
-      "version": "0.25.8",
-      "resolved": "https://registry.npmjs.org/@esbuild/linux-arm/-/linux-arm-0.25.8.tgz",
-      "integrity": "sha512-FuzEP9BixzZohl1kLf76KEVOsxtIBFwCaLupVuk4eFVnOZfU+Wsn+x5Ryam7nILV2pkq2TqQM9EZPsOBuMC+kg==",

*      "version": "0.27.7",
*      "resolved": "https://registry.npmjs.org/@esbuild/linux-arm/-/linux-arm-0.27.7.tgz",
*      "integrity": "sha512-RkT/YXYBTSULo3+af8Ib0ykH8u2MBh57o7q/DAs3lTJlyVQkgQvlrPTnjIzzRPQyavxtPtfg0EopvDyIt0j1rA==",
       "cpu": [
         "arm"
       ],
       "dev": true,

-      "license": "MIT",
         "optional": true,
         "os": [
           "linux"
  @@ -902,14 +893,13 @@
  }
  },
  "node_modules/@esbuild/linux-arm64": {
-      "version": "0.25.8",
-      "resolved": "https://registry.npmjs.org/@esbuild/linux-arm64/-/linux-arm64-0.25.8.tgz",
-      "integrity": "sha512-WIgg00ARWv/uYLU7lsuDK00d/hHSfES5BzdWAdAig1ioV5kaFNrtK8EqGcUBJhYqotlUByUKz5Qo6u8tt7iD/w==",

*      "version": "0.27.7",
*      "resolved": "https://registry.npmjs.org/@esbuild/linux-arm64/-/linux-arm64-0.27.7.tgz",
*      "integrity": "sha512-RZPHBoxXuNnPQO9rvjh5jdkRmVizktkT7TCDkDmQ0W2SwHInKCAV95GRuvdSvA7w4VMwfCjUiPwDi0ZO6Nfe9A==",
       "cpu": [
         "arm64"
       ],
       "dev": true,

-      "license": "MIT",
         "optional": true,
         "os": [
           "linux"
  @@ -919,14 +909,13 @@
  }
  },
  "node_modules/@esbuild/linux-ia32": {
-      "version": "0.25.8",
-      "resolved": "https://registry.npmjs.org/@esbuild/linux-ia32/-/linux-ia32-0.25.8.tgz",
-      "integrity": "sha512-A1D9YzRX1i+1AJZuFFUMP1E9fMaYY+GnSQil9Tlw05utlE86EKTUA7RjwHDkEitmLYiFsRd9HwKBPEftNdBfjg==",

*      "version": "0.27.7",
*      "resolved": "https://registry.npmjs.org/@esbuild/linux-ia32/-/linux-ia32-0.27.7.tgz",
*      "integrity": "sha512-GA48aKNkyQDbd3KtkplYWT102C5sn/EZTY4XROkxONgruHPU72l+gW+FfF8tf2cFjeHaRbWpOYa/uRBz/Xq1Pg==",
       "cpu": [
         "ia32"
       ],
       "dev": true,

-      "license": "MIT",
         "optional": true,
         "os": [
           "linux"
  @@ -936,14 +925,13 @@
  }
  },
  "node_modules/@esbuild/linux-loong64": {
-      "version": "0.25.8",
-      "resolved": "https://registry.npmjs.org/@esbuild/linux-loong64/-/linux-loong64-0.25.8.tgz",
-      "integrity": "sha512-O7k1J/dwHkY1RMVvglFHl1HzutGEFFZ3kNiDMSOyUrB7WcoHGf96Sh+64nTRT26l3GMbCW01Ekh/ThKM5iI7hQ==",

*      "version": "0.27.7",
*      "resolved": "https://registry.npmjs.org/@esbuild/linux-loong64/-/linux-loong64-0.27.7.tgz",
*      "integrity": "sha512-a4POruNM2oWsD4WKvBSEKGIiWQF8fZOAsycHOt6JBpZ+JN2n2JH9WAv56SOyu9X5IqAjqSIPTaJkqN8F7XOQ5Q==",
       "cpu": [
         "loong64"
       ],
       "dev": true,

-      "license": "MIT",
         "optional": true,
         "os": [
           "linux"
  @@ -953,14 +941,13 @@
  }
  },
  "node_modules/@esbuild/linux-mips64el": {
-      "version": "0.25.8",
-      "resolved": "https://registry.npmjs.org/@esbuild/linux-mips64el/-/linux-mips64el-0.25.8.tgz",
-      "integrity": "sha512-uv+dqfRazte3BzfMp8PAQXmdGHQt2oC/y2ovwpTteqrMx2lwaksiFZ/bdkXJC19ttTvNXBuWH53zy/aTj1FgGw==",

*      "version": "0.27.7",
*      "resolved": "https://registry.npmjs.org/@esbuild/linux-mips64el/-/linux-mips64el-0.27.7.tgz",
*      "integrity": "sha512-KabT5I6StirGfIz0FMgl1I+R1H73Gp0ofL9A3nG3i/cYFJzKHhouBV5VWK1CSgKvVaG4q1RNpCTR2LuTVB3fIw==",
       "cpu": [
         "mips64el"
       ],
       "dev": true,

-      "license": "MIT",
         "optional": true,
         "os": [
           "linux"
  @@ -970,14 +957,13 @@
  }
  },
  "node_modules/@esbuild/linux-ppc64": {
-      "version": "0.25.8",
-      "resolved": "https://registry.npmjs.org/@esbuild/linux-ppc64/-/linux-ppc64-0.25.8.tgz",
-      "integrity": "sha512-GyG0KcMi1GBavP5JgAkkstMGyMholMDybAf8wF5A70CALlDM2p/f7YFE7H92eDeH/VBtFJA5MT4nRPDGg4JuzQ==",

*      "version": "0.27.7",
*      "resolved": "https://registry.npmjs.org/@esbuild/linux-ppc64/-/linux-ppc64-0.27.7.tgz",
*      "integrity": "sha512-gRsL4x6wsGHGRqhtI+ifpN/vpOFTQtnbsupUF5R5YTAg+y/lKelYR1hXbnBdzDjGbMYjVJLJTd2OFmMewAgwlQ==",
       "cpu": [
         "ppc64"
       ],
       "dev": true,

-      "license": "MIT",
         "optional": true,
         "os": [
           "linux"
  @@ -987,14 +973,13 @@
  }
  },
  "node_modules/@esbuild/linux-riscv64": {
-      "version": "0.25.8",
-      "resolved": "https://registry.npmjs.org/@esbuild/linux-riscv64/-/linux-riscv64-0.25.8.tgz",
-      "integrity": "sha512-rAqDYFv3yzMrq7GIcen3XP7TUEG/4LK86LUPMIz6RT8A6pRIDn0sDcvjudVZBiiTcZCY9y2SgYX2lgK3AF+1eg==",

*      "version": "0.27.7",
*      "resolved": "https://registry.npmjs.org/@esbuild/linux-riscv64/-/linux-riscv64-0.27.7.tgz",
*      "integrity": "sha512-hL25LbxO1QOngGzu2U5xeXtxXcW+/GvMN3ejANqXkxZ/opySAZMrc+9LY/WyjAan41unrR3YrmtTsUpwT66InQ==",
       "cpu": [
         "riscv64"
       ],
       "dev": true,

-      "license": "MIT",
         "optional": true,
         "os": [
           "linux"
  @@ -1004,14 +989,13 @@
  }
  },
  "node_modules/@esbuild/linux-s390x": {
-      "version": "0.25.8",
-      "resolved": "https://registry.npmjs.org/@esbuild/linux-s390x/-/linux-s390x-0.25.8.tgz",
-      "integrity": "sha512-Xutvh6VjlbcHpsIIbwY8GVRbwoviWT19tFhgdA7DlenLGC/mbc3lBoVb7jxj9Z+eyGqvcnSyIltYUrkKzWqSvg==",

*      "version": "0.27.7",
*      "resolved": "https://registry.npmjs.org/@esbuild/linux-s390x/-/linux-s390x-0.27.7.tgz",
*      "integrity": "sha512-2k8go8Ycu1Kb46vEelhu1vqEP+UeRVj2zY1pSuPdgvbd5ykAw82Lrro28vXUrRmzEsUV0NzCf54yARIK8r0fdw==",
       "cpu": [
         "s390x"
       ],
       "dev": true,

-      "license": "MIT",
         "optional": true,
         "os": [
           "linux"
  @@ -1021,14 +1005,13 @@
  }
  },
  "node_modules/@esbuild/linux-x64": {
-      "version": "0.25.8",
-      "resolved": "https://registry.npmjs.org/@esbuild/linux-x64/-/linux-x64-0.25.8.tgz",
-      "integrity": "sha512-ASFQhgY4ElXh3nDcOMTkQero4b1lgubskNlhIfJrsH5OKZXDpUAKBlNS0Kx81jwOBp+HCeZqmoJuihTv57/jvQ==",

*      "version": "0.27.7",
*      "resolved": "https://registry.npmjs.org/@esbuild/linux-x64/-/linux-x64-0.27.7.tgz",
*      "integrity": "sha512-hzznmADPt+OmsYzw1EE33ccA+HPdIqiCRq7cQeL1Jlq2gb1+OyWBkMCrYGBJ+sxVzve2ZJEVeePbLM2iEIZSxA==",
       "cpu": [
         "x64"
       ],
       "dev": true,

-      "license": "MIT",
         "optional": true,
         "os": [
           "linux"
  @@ -1038,14 +1021,13 @@
  }
  },
  "node_modules/@esbuild/netbsd-arm64": {
-      "version": "0.25.8",
-      "resolved": "https://registry.npmjs.org/@esbuild/netbsd-arm64/-/netbsd-arm64-0.25.8.tgz",
-      "integrity": "sha512-d1KfruIeohqAi6SA+gENMuObDbEjn22olAR7egqnkCD9DGBG0wsEARotkLgXDu6c4ncgWTZJtN5vcgxzWRMzcw==",

*      "version": "0.27.7",
*      "resolved": "https://registry.npmjs.org/@esbuild/netbsd-arm64/-/netbsd-arm64-0.27.7.tgz",
*      "integrity": "sha512-b6pqtrQdigZBwZxAn1UpazEisvwaIDvdbMbmrly7cDTMFnw/+3lVxxCTGOrkPVnsYIosJJXAsILG9XcQS+Yu6w==",
       "cpu": [
         "arm64"
       ],
       "dev": true,

-      "license": "MIT",
         "optional": true,
         "os": [
           "netbsd"
  @@ -1055,14 +1037,13 @@
  }
  },
  "node_modules/@esbuild/netbsd-x64": {
-      "version": "0.25.8",
-      "resolved": "https://registry.npmjs.org/@esbuild/netbsd-x64/-/netbsd-x64-0.25.8.tgz",
-      "integrity": "sha512-nVDCkrvx2ua+XQNyfrujIG38+YGyuy2Ru9kKVNyh5jAys6n+l44tTtToqHjino2My8VAY6Lw9H7RI73XFi66Cg==",

*      "version": "0.27.7",
*      "resolved": "https://registry.npmjs.org/@esbuild/netbsd-x64/-/netbsd-x64-0.27.7.tgz",
*      "integrity": "sha512-OfatkLojr6U+WN5EDYuoQhtM+1xco+/6FSzJJnuWiUw5eVcicbyK3dq5EeV/QHT1uy6GoDhGbFpprUiHUYggrw==",
       "cpu": [
         "x64"
       ],
       "dev": true,

-      "license": "MIT",
         "optional": true,
         "os": [
           "netbsd"
  @@ -1072,14 +1053,13 @@
  }
  },
  "node_modules/@esbuild/openbsd-arm64": {
-      "version": "0.25.8",
-      "resolved": "https://registry.npmjs.org/@esbuild/openbsd-arm64/-/openbsd-arm64-0.25.8.tgz",
-      "integrity": "sha512-j8HgrDuSJFAujkivSMSfPQSAa5Fxbvk4rgNAS5i3K+r8s1X0p1uOO2Hl2xNsGFppOeHOLAVgYwDVlmxhq5h+SQ==",

*      "version": "0.27.7",
*      "resolved": "https://registry.npmjs.org/@esbuild/openbsd-arm64/-/openbsd-arm64-0.27.7.tgz",
*      "integrity": "sha512-AFuojMQTxAz75Fo8idVcqoQWEHIXFRbOc1TrVcFSgCZtQfSdc1RXgB3tjOn/krRHENUB4j00bfGjyl2mJrU37A==",
       "cpu": [
         "arm64"
       ],
       "dev": true,

-      "license": "MIT",
         "optional": true,
         "os": [
           "openbsd"
  @@ -1089,14 +1069,13 @@
  }
  },
  "node_modules/@esbuild/openbsd-x64": {
-      "version": "0.25.8",
-      "resolved": "https://registry.npmjs.org/@esbuild/openbsd-x64/-/openbsd-x64-0.25.8.tgz",
-      "integrity": "sha512-1h8MUAwa0VhNCDp6Af0HToI2TJFAn1uqT9Al6DJVzdIBAd21m/G0Yfc77KDM3uF3T/YaOgQq3qTJHPbTOInaIQ==",

*      "version": "0.27.7",
*      "resolved": "https://registry.npmjs.org/@esbuild/openbsd-x64/-/openbsd-x64-0.27.7.tgz",
*      "integrity": "sha512-+A1NJmfM8WNDv5CLVQYJ5PshuRm/4cI6WMZRg1by1GwPIQPCTs1GLEUHwiiQGT5zDdyLiRM/l1G0Pv54gvtKIg==",
       "cpu": [
         "x64"
       ],
       "dev": true,

-      "license": "MIT",
         "optional": true,
         "os": [
           "openbsd"
  @@ -1106,14 +1085,13 @@
  }
  },
  "node_modules/@esbuild/openharmony-arm64": {
-      "version": "0.25.8",
-      "resolved": "https://registry.npmjs.org/@esbuild/openharmony-arm64/-/openharmony-arm64-0.25.8.tgz",
-      "integrity": "sha512-r2nVa5SIK9tSWd0kJd9HCffnDHKchTGikb//9c7HX+r+wHYCpQrSgxhlY6KWV1nFo1l4KFbsMlHk+L6fekLsUg==",

*      "version": "0.27.7",
*      "resolved": "https://registry.npmjs.org/@esbuild/openharmony-arm64/-/openharmony-arm64-0.27.7.tgz",
*      "integrity": "sha512-+KrvYb/C8zA9CU/g0sR6w2RBw7IGc5J2BPnc3dYc5VJxHCSF1yNMxTV5LQ7GuKteQXZtspjFbiuW5/dOj7H4Yw==",
       "cpu": [
         "arm64"
       ],
       "dev": true,

-      "license": "MIT",
         "optional": true,
         "os": [
           "openharmony"
  @@ -1123,14 +1101,13 @@
  }
  },
  "node_modules/@esbuild/sunos-x64": {
-      "version": "0.25.8",
-      "resolved": "https://registry.npmjs.org/@esbuild/sunos-x64/-/sunos-x64-0.25.8.tgz",
-      "integrity": "sha512-zUlaP2S12YhQ2UzUfcCuMDHQFJyKABkAjvO5YSndMiIkMimPmxA+BYSBikWgsRpvyxuRnow4nS5NPnf9fpv41w==",

*      "version": "0.27.7",
*      "resolved": "https://registry.npmjs.org/@esbuild/sunos-x64/-/sunos-x64-0.27.7.tgz",
*      "integrity": "sha512-ikktIhFBzQNt/QDyOL580ti9+5mL/YZeUPKU2ivGtGjdTYoqz6jObj6nOMfhASpS4GU4Q/Clh1QtxWAvcYKamA==",
       "cpu": [
         "x64"
       ],
       "dev": true,

-      "license": "MIT",
         "optional": true,
         "os": [
           "sunos"
  @@ -1140,14 +1117,13 @@
  }
  },
  "node_modules/@esbuild/win32-arm64": {
-      "version": "0.25.8",
-      "resolved": "https://registry.npmjs.org/@esbuild/win32-arm64/-/win32-arm64-0.25.8.tgz",
-      "integrity": "sha512-YEGFFWESlPva8hGL+zvj2z/SaK+pH0SwOM0Nc/d+rVnW7GSTFlLBGzZkuSU9kFIGIo8q9X3ucpZhu8PDN5A2sQ==",

*      "version": "0.27.7",
*      "resolved": "https://registry.npmjs.org/@esbuild/win32-arm64/-/win32-arm64-0.27.7.tgz",
*      "integrity": "sha512-7yRhbHvPqSpRUV7Q20VuDwbjW5kIMwTHpptuUzV+AA46kiPze5Z7qgt6CLCK3pWFrHeNfDd1VKgyP4O+ng17CA==",
       "cpu": [
         "arm64"
       ],
       "dev": true,

-      "license": "MIT",
         "optional": true,
         "os": [
           "win32"
  @@ -1157,14 +1133,13 @@
  }
  },
  "node_modules/@esbuild/win32-ia32": {
-      "version": "0.25.8",
-      "resolved": "https://registry.npmjs.org/@esbuild/win32-ia32/-/win32-ia32-0.25.8.tgz",
-      "integrity": "sha512-hiGgGC6KZ5LZz58OL/+qVVoZiuZlUYlYHNAmczOm7bs2oE1XriPFi5ZHHrS8ACpV5EjySrnoCKmcbQMN+ojnHg==",

*      "version": "0.27.7",
*      "resolved": "https://registry.npmjs.org/@esbuild/win32-ia32/-/win32-ia32-0.27.7.tgz",
*      "integrity": "sha512-SmwKXe6VHIyZYbBLJrhOoCJRB/Z1tckzmgTLfFYOfpMAx63BJEaL9ExI8x7v0oAO3Zh6D/Oi1gVxEYr5oUCFhw==",
       "cpu": [
         "ia32"
       ],
       "dev": true,

-      "license": "MIT",
         "optional": true,
         "os": [
           "win32"
  @@ -1174,14 +1149,13 @@
  }
  },
  "node_modules/@esbuild/win32-x64": {
-      "version": "0.25.8",
-      "resolved": "https://registry.npmjs.org/@esbuild/win32-x64/-/win32-x64-0.25.8.tgz",
-      "integrity": "sha512-cn3Yr7+OaaZq1c+2pe+8yxC8E144SReCQjN6/2ynubzYjvyqZjTXfQJpAcQpsdJq3My7XADANiYGHoFC69pLQw==",

*      "version": "0.27.7",
*      "resolved": "https://registry.npmjs.org/@esbuild/win32-x64/-/win32-x64-0.27.7.tgz",
*      "integrity": "sha512-56hiAJPhwQ1R4i+21FVF7V8kSD5zZTdHcVuRFMW0hn753vVfQN8xlx4uOPT4xoGH0Z/oVATuR82AiqSTDIpaHg==",
       "cpu": [
         "x64"
       ],
       "dev": true,

-      "license": "MIT",
         "optional": true,
         "os": [
           "win32"
  @@ -1190,52 +1164,77 @@
  "node": ">=18"
  }
  },

* "node_modules/@hono/node-server": {
*      "version": "1.19.14",
*      "resolved": "https://registry.npmjs.org/@hono/node-server/-/node-server-1.19.14.tgz",
*      "integrity": "sha512-GwtvgtXxnWsucXvbQXkRgqksiH2Qed37H9xHZocE5sA3N8O8O8/8FA3uclQXxXVzc9XBZuEOMK7+r02FmSpHtw==",
*      "engines": {
*        "node": ">=18.14.1"
*      },
*      "peerDependencies": {
*        "hono": "^4"
*      }
* },
  "node_modules/@modelcontextprotocol/sdk": {

-      "version": "1.17.2",
-      "resolved": "https://registry.npmjs.org/@modelcontextprotocol/sdk/-/sdk-1.17.2.tgz",
-      "integrity": "sha512-EFLRNXR/ixpXQWu6/3Cu30ndDFIFNaqUXcTqsGebujeMan9FzhAaFFswLRiFj61rgygDRr8WO1N+UijjgRxX9g==",
-      "license": "MIT",

*      "version": "1.29.0",
*      "resolved": "https://registry.npmjs.org/@modelcontextprotocol/sdk/-/sdk-1.29.0.tgz",
*      "integrity": "sha512-zo37mZA9hJWpULgkRpowewez1y6ML5GsXJPY8FI0tBBCd77HEvza4jDqRKOXgHNn867PVGCyTdzqpz0izu5ZjQ==",
       "dependencies": {

-        "ajv": "^6.12.6",

*        "@hono/node-server": "^1.19.9",
*        "ajv": "^8.17.1",
*        "ajv-formats": "^3.0.1",
         "content-type": "^1.0.5",
         "cors": "^2.8.5",
         "cross-spawn": "^7.0.5",
         "eventsource": "^3.0.2",
         "eventsource-parser": "^3.0.0",

-        "express": "^5.0.1",
-        "express-rate-limit": "^7.5.0",

*        "express": "^5.2.1",
*        "express-rate-limit": "^8.2.1",
*        "hono": "^4.11.4",
*        "jose": "^6.1.3",
*        "json-schema-typed": "^8.0.2",
         "pkce-challenge": "^5.0.0",
         "raw-body": "^3.0.0",

-        "zod": "^3.23.8",
-        "zod-to-json-schema": "^3.24.1"

*        "zod": "^3.25 || ^4.0",
*        "zod-to-json-schema": "^3.25.1"
       },
       "engines": {
         "node": ">=18"

-      }
- },
- "node_modules/@smithy/abort-controller": {
-      "version": "4.0.5",
-      "resolved": "https://registry.npmjs.org/@smithy/abort-controller/-/abort-controller-4.0.5.tgz",
-      "integrity": "sha512-jcrqdTQurIrBbUm4W2YdLVMQDoL0sA9DTxYd2s+R/y+2U9NLOP7Xf/YqfSg1FZhlZIYEnvk2mwbyvIfdLEPo8g==",
-      "license": "Apache-2.0",
-      "dependencies": {
-        "@smithy/types": "^4.3.2",
-        "tslib": "^2.6.2"
       },
-      "engines": {
-        "node": ">=18.0.0"

*      "peerDependencies": {
*        "@cfworker/json-schema": "^4.1.1",
*        "zod": "^3.25 || ^4.0"
*      },
*      "peerDependenciesMeta": {
*        "@cfworker/json-schema": {
*          "optional": true
*        },
*        "zod": {
*          "optional": false
*        }
       }
  },
* "node_modules/@nodable/entities": {
*      "version": "2.1.0",
*      "resolved": "https://registry.npmjs.org/@nodable/entities/-/entities-2.1.0.tgz",
*      "integrity": "sha512-nyT7T3nbMyBI/lvr6L5TyWbFJAI9FTgVRakNoBqCD+PmID8DzFrrNdLLtHMwMszOtqZa8PAOV24ZqDnQrhQINA==",
*      "funding": [
*        {
*          "type": "github",
*          "url": "https://github.com/sponsors/nodable"
*        }
*      ]
* },
  "node_modules/@smithy/config-resolver": {

-      "version": "4.1.5",
-      "resolved": "https://registry.npmjs.org/@smithy/config-resolver/-/config-resolver-4.1.5.tgz",
-      "integrity": "sha512-viuHMxBAqydkB0AfWwHIdwf/PRH2z5KHGUzqyRtS/Wv+n3IHI993Sk76VCA7dD/+GzgGOmlJDITfPcJC1nIVIw==",
-      "license": "Apache-2.0",

*      "version": "4.4.17",
*      "resolved": "https://registry.npmjs.org/@smithy/config-resolver/-/config-resolver-4.4.17.tgz",
*      "integrity": "sha512-TzDZcAnhTyAHbXVxWZo7/tEcrIeFq20IBk8So3OLOetWpR8EwY/yEqBMBFaJMeyEiREDq4NfEl+qO3OAUD+vbQ==",
       "dependencies": {

-        "@smithy/node-config-provider": "^4.1.4",
-        "@smithy/types": "^4.3.2",
-        "@smithy/util-config-provider": "^4.0.0",
-        "@smithy/util-middleware": "^4.0.5",

*        "@smithy/node-config-provider": "^4.3.14",
*        "@smithy/types": "^4.14.1",
*        "@smithy/util-config-provider": "^4.2.2",
*        "@smithy/util-endpoints": "^3.4.2",
*        "@smithy/util-middleware": "^4.2.14",
           "tslib": "^2.6.2"
         },
         "engines": {
  @@ -1243,37 +1242,34 @@
  }
  },
  "node_modules/@smithy/core": {

-      "version": "3.8.0",
-      "resolved": "https://registry.npmjs.org/@smithy/core/-/core-3.8.0.tgz",
-      "integrity": "sha512-EYqsIYJmkR1VhVE9pccnk353xhs+lB6btdutJEtsp7R055haMJp2yE16eSxw8fv+G0WUY6vqxyYOP8kOqawxYQ==",
-      "license": "Apache-2.0",
-      "dependencies": {
-        "@smithy/middleware-serde": "^4.0.9",
-        "@smithy/protocol-http": "^5.1.3",
-        "@smithy/types": "^4.3.2",
-        "@smithy/util-base64": "^4.0.0",
-        "@smithy/util-body-length-browser": "^4.0.0",
-        "@smithy/util-middleware": "^4.0.5",
-        "@smithy/util-stream": "^4.2.4",
-        "@smithy/util-utf8": "^4.0.0",
-        "@types/uuid": "^9.0.1",
-        "tslib": "^2.6.2",
-        "uuid": "^9.0.1"

*      "version": "3.23.17",
*      "resolved": "https://registry.npmjs.org/@smithy/core/-/core-3.23.17.tgz",
*      "integrity": "sha512-x7BlLbUFL8NWCGjMF9C+1N5cVCxcPa7g6Tv9B4A2luWx3be3oU8hQ96wIwxe/s7OhIzvoJH73HAUSg5JXVlEtQ==",
*      "dependencies": {
*        "@smithy/protocol-http": "^5.3.14",
*        "@smithy/types": "^4.14.1",
*        "@smithy/url-parser": "^4.2.14",
*        "@smithy/util-base64": "^4.3.2",
*        "@smithy/util-body-length-browser": "^4.2.2",
*        "@smithy/util-middleware": "^4.2.14",
*        "@smithy/util-stream": "^4.5.25",
*        "@smithy/util-utf8": "^4.2.2",
*        "@smithy/uuid": "^1.1.2",
*        "tslib": "^2.6.2"
       },
       "engines": {
         "node": ">=18.0.0"
       }
  },
  "node_modules/@smithy/credential-provider-imds": {

-      "version": "4.0.7",
-      "resolved": "https://registry.npmjs.org/@smithy/credential-provider-imds/-/credential-provider-imds-4.0.7.tgz",
-      "integrity": "sha512-dDzrMXA8d8riFNiPvytxn0mNwR4B3h8lgrQ5UjAGu6T9z/kRg/Xncf4tEQHE/+t25sY8IH3CowcmWi+1U5B1Gw==",
-      "license": "Apache-2.0",

*      "version": "4.2.14",
*      "resolved": "https://registry.npmjs.org/@smithy/credential-provider-imds/-/credential-provider-imds-4.2.14.tgz",
*      "integrity": "sha512-Au28zBN48ZAoXdooGUHemuVBrkE+Ie6RPmGNIAJsFqj33Vhb6xAgRifUydZ2aY+M+KaMAETAlKk5NC5h1G7wpg==",
       "dependencies": {

-        "@smithy/node-config-provider": "^4.1.4",
-        "@smithy/property-provider": "^4.0.5",
-        "@smithy/types": "^4.3.2",
-        "@smithy/url-parser": "^4.0.5",

*        "@smithy/node-config-provider": "^4.3.14",
*        "@smithy/property-provider": "^4.2.14",
*        "@smithy/types": "^4.14.1",
*        "@smithy/url-parser": "^4.2.14",
           "tslib": "^2.6.2"
         },
         "engines": {
  @@ -1281,15 +1277,14 @@
  }
  },
  "node_modules/@smithy/fetch-http-handler": {

-      "version": "5.1.1",
-      "resolved": "https://registry.npmjs.org/@smithy/fetch-http-handler/-/fetch-http-handler-5.1.1.tgz",
-      "integrity": "sha512-61WjM0PWmZJR+SnmzaKI7t7G0UkkNFboDpzIdzSoy7TByUzlxo18Qlh9s71qug4AY4hlH/CwXdubMtkcNEb/sQ==",
-      "license": "Apache-2.0",

*      "version": "5.3.17",
*      "resolved": "https://registry.npmjs.org/@smithy/fetch-http-handler/-/fetch-http-handler-5.3.17.tgz",
*      "integrity": "sha512-bXOvQzaSm6MnmLaWA1elgfQcAtN4UP3vXqV97bHuoOrHQOJiLT3ds6o9eo5bqd0TJfRFpzdGnDQdW3FACiAVdw==",
       "dependencies": {

-        "@smithy/protocol-http": "^5.1.3",
-        "@smithy/querystring-builder": "^4.0.5",
-        "@smithy/types": "^4.3.2",
-        "@smithy/util-base64": "^4.0.0",

*        "@smithy/protocol-http": "^5.3.14",
*        "@smithy/querystring-builder": "^4.2.14",
*        "@smithy/types": "^4.14.1",
*        "@smithy/util-base64": "^4.3.2",
           "tslib": "^2.6.2"
         },
         "engines": {
  @@ -1297,14 +1292,13 @@
  }
  },
  "node_modules/@smithy/hash-node": {

-      "version": "4.0.5",
-      "resolved": "https://registry.npmjs.org/@smithy/hash-node/-/hash-node-4.0.5.tgz",
-      "integrity": "sha512-cv1HHkKhpyRb6ahD8Vcfb2Hgz67vNIXEp2vnhzfxLFGRukLCNEA5QdsorbUEzXma1Rco0u3rx5VTqbM06GcZqQ==",
-      "license": "Apache-2.0",

*      "version": "4.2.14",
*      "resolved": "https://registry.npmjs.org/@smithy/hash-node/-/hash-node-4.2.14.tgz",
*      "integrity": "sha512-8ZBDY2DD4wr+GGjTpPtiglEsqr0lUP+KHqgZcWczFf6qeZ/YRjMIOoQWVQlmwu7EtxKTd8YXD8lblmYcpBIA1g==",
       "dependencies": {

-        "@smithy/types": "^4.3.2",
-        "@smithy/util-buffer-from": "^4.0.0",
-        "@smithy/util-utf8": "^4.0.0",

*        "@smithy/types": "^4.14.1",
*        "@smithy/util-buffer-from": "^4.2.2",
*        "@smithy/util-utf8": "^4.2.2",
           "tslib": "^2.6.2"
         },
         "engines": {
  @@ -1312,12 +1306,11 @@
  }
  },
  "node_modules/@smithy/invalid-dependency": {

-      "version": "4.0.5",
-      "resolved": "https://registry.npmjs.org/@smithy/invalid-dependency/-/invalid-dependency-4.0.5.tgz",
-      "integrity": "sha512-IVnb78Qtf7EJpoEVo7qJ8BEXQwgC4n3igeJNNKEj/MLYtapnx8A67Zt/J3RXAj2xSO1910zk0LdFiygSemuLow==",
-      "license": "Apache-2.0",

*      "version": "4.2.14",
*      "resolved": "https://registry.npmjs.org/@smithy/invalid-dependency/-/invalid-dependency-4.2.14.tgz",
*      "integrity": "sha512-c21qJiTSb25xvvOp+H2TNZzPCngrvl5vIPqPB8zQ/DmJF4QWXO19x1dWfMJZ6wZuuWUPPm0gV8C0cU3+ifcWuw==",
       "dependencies": {

-        "@smithy/types": "^4.3.2",

*        "@smithy/types": "^4.14.1",
           "tslib": "^2.6.2"
         },
         "engines": {
  @@ -1325,10 +1318,9 @@
  }
  },
  "node_modules/@smithy/is-array-buffer": {

-      "version": "4.0.0",
-      "resolved": "https://registry.npmjs.org/@smithy/is-array-buffer/-/is-array-buffer-4.0.0.tgz",
-      "integrity": "sha512-saYhF8ZZNoJDTvJBEWgeBccCg+yvp1CX+ed12yORU3NilJScfc6gfch2oVb4QgxZrGUx3/ZJlb+c/dJbyupxlw==",
-      "license": "Apache-2.0",

*      "version": "4.2.2",
*      "resolved": "https://registry.npmjs.org/@smithy/is-array-buffer/-/is-array-buffer-4.2.2.tgz",
*      "integrity": "sha512-n6rQ4N8Jj4YTQO3YFrlgZuwKodf4zUFs7EJIWH86pSCWBaAtAGBFfCM7Wx6D2bBJ2xqFNxGBSrUWswT3M0VJow==",
         "dependencies": {
           "tslib": "^2.6.2"
         },
  @@ -1337,13 +1329,12 @@
  }
  },
  "node_modules/@smithy/middleware-content-length": {

-      "version": "4.0.5",
-      "resolved": "https://registry.npmjs.org/@smithy/middleware-content-length/-/middleware-content-length-4.0.5.tgz",
-      "integrity": "sha512-l1jlNZoYzoCC7p0zCtBDE5OBXZ95yMKlRlftooE5jPWQn4YBPLgsp+oeHp7iMHaTGoUdFqmHOPa8c9G3gBsRpQ==",
-      "license": "Apache-2.0",

*      "version": "4.2.14",
*      "resolved": "https://registry.npmjs.org/@smithy/middleware-content-length/-/middleware-content-length-4.2.14.tgz",
*      "integrity": "sha512-xhHq7fX4/3lv5NHxLUk3OeEvl0xZ+Ek3qIbWaCL4f9JwgDZEclPBElljaZCAItdGPQl/kSM4LPMOpy1MYgprpw==",
       "dependencies": {

-        "@smithy/protocol-http": "^5.1.3",
-        "@smithy/types": "^4.3.2",

*        "@smithy/protocol-http": "^5.3.14",
*        "@smithy/types": "^4.14.1",
           "tslib": "^2.6.2"
         },
         "engines": {
  @@ -1351,18 +1342,17 @@
  }
  },
  "node_modules/@smithy/middleware-endpoint": {

-      "version": "4.1.18",
-      "resolved": "https://registry.npmjs.org/@smithy/middleware-endpoint/-/middleware-endpoint-4.1.18.tgz",
-      "integrity": "sha512-ZhvqcVRPZxnZlokcPaTwb+r+h4yOIOCJmx0v2d1bpVlmP465g3qpVSf7wxcq5zZdu4jb0H4yIMxuPwDJSQc3MQ==",
-      "license": "Apache-2.0",

*      "version": "4.4.32",
*      "resolved": "https://registry.npmjs.org/@smithy/middleware-endpoint/-/middleware-endpoint-4.4.32.tgz",
*      "integrity": "sha512-ZZkgyjnJppiZbIm6Qbx92pbXYi1uzenIvGhBSCDlc7NwuAkiqSgS75j1czAD25ZLs2FjMjYy1q7gyRVWG6JA0Q==",
       "dependencies": {

-        "@smithy/core": "^3.8.0",
-        "@smithy/middleware-serde": "^4.0.9",
-        "@smithy/node-config-provider": "^4.1.4",
-        "@smithy/shared-ini-file-loader": "^4.0.5",
-        "@smithy/types": "^4.3.2",
-        "@smithy/url-parser": "^4.0.5",
-        "@smithy/util-middleware": "^4.0.5",

*        "@smithy/core": "^3.23.17",
*        "@smithy/middleware-serde": "^4.2.20",
*        "@smithy/node-config-provider": "^4.3.14",
*        "@smithy/shared-ini-file-loader": "^4.4.9",
*        "@smithy/types": "^4.14.1",
*        "@smithy/url-parser": "^4.2.14",
*        "@smithy/util-middleware": "^4.2.14",
           "tslib": "^2.6.2"
         },
         "engines": {
  @@ -1370,34 +1360,33 @@
  }
  },
  "node_modules/@smithy/middleware-retry": {

-      "version": "4.1.19",
-      "resolved": "https://registry.npmjs.org/@smithy/middleware-retry/-/middleware-retry-4.1.19.tgz",
-      "integrity": "sha512-X58zx/NVECjeuUB6A8HBu4bhx72EoUz+T5jTMIyeNKx2lf+Gs9TmWPNNkH+5QF0COjpInP/xSpJGJ7xEnAklQQ==",
-      "license": "Apache-2.0",
-      "dependencies": {
-        "@smithy/node-config-provider": "^4.1.4",
-        "@smithy/protocol-http": "^5.1.3",
-        "@smithy/service-error-classification": "^4.0.7",
-        "@smithy/smithy-client": "^4.4.10",
-        "@smithy/types": "^4.3.2",
-        "@smithy/util-middleware": "^4.0.5",
-        "@smithy/util-retry": "^4.0.7",
-        "@types/uuid": "^9.0.1",
-        "tslib": "^2.6.2",
-        "uuid": "^9.0.1"

*      "version": "4.5.7",
*      "resolved": "https://registry.npmjs.org/@smithy/middleware-retry/-/middleware-retry-4.5.7.tgz",
*      "integrity": "sha512-bRt6ZImqVSeTk39Nm81K20ObIiAZ3WefY7G6+iz/0tZjs4dgRRjvRX2sgsH+zi6iDCRR/aQvQofLKxxz4rPBZg==",
*      "dependencies": {
*        "@smithy/core": "^3.23.17",
*        "@smithy/node-config-provider": "^4.3.14",
*        "@smithy/protocol-http": "^5.3.14",
*        "@smithy/service-error-classification": "^4.3.1",
*        "@smithy/smithy-client": "^4.12.13",
*        "@smithy/types": "^4.14.1",
*        "@smithy/util-middleware": "^4.2.14",
*        "@smithy/util-retry": "^4.3.6",
*        "@smithy/uuid": "^1.1.2",
*        "tslib": "^2.6.2"
       },
       "engines": {
         "node": ">=18.0.0"
       }
  },
  "node_modules/@smithy/middleware-serde": {

-      "version": "4.0.9",
-      "resolved": "https://registry.npmjs.org/@smithy/middleware-serde/-/middleware-serde-4.0.9.tgz",
-      "integrity": "sha512-uAFFR4dpeoJPGz8x9mhxp+RPjo5wW0QEEIPPPbLXiRRWeCATf/Km3gKIVR5vaP8bN1kgsPhcEeh+IZvUlBv6Xg==",
-      "license": "Apache-2.0",

*      "version": "4.2.20",
*      "resolved": "https://registry.npmjs.org/@smithy/middleware-serde/-/middleware-serde-4.2.20.tgz",
*      "integrity": "sha512-Lx9JMO9vArPtiChE3wbEZ5akMIDQpWQtlu90lhACQmNOXcGXRbaDywMHDzuDZ2OkZzP+9wQfZi3YJT9F67zTQQ==",
       "dependencies": {

-        "@smithy/protocol-http": "^5.1.3",
-        "@smithy/types": "^4.3.2",

*        "@smithy/core": "^3.23.17",
*        "@smithy/protocol-http": "^5.3.14",
*        "@smithy/types": "^4.14.1",
           "tslib": "^2.6.2"
         },
         "engines": {
  @@ -1405,12 +1394,11 @@
  }
  },
  "node_modules/@smithy/middleware-stack": {

-      "version": "4.0.5",
-      "resolved": "https://registry.npmjs.org/@smithy/middleware-stack/-/middleware-stack-4.0.5.tgz",
-      "integrity": "sha512-/yoHDXZPh3ocRVyeWQFvC44u8seu3eYzZRveCMfgMOBcNKnAmOvjbL9+Cp5XKSIi9iYA9PECUuW2teDAk8T+OQ==",
-      "license": "Apache-2.0",

*      "version": "4.2.14",
*      "resolved": "https://registry.npmjs.org/@smithy/middleware-stack/-/middleware-stack-4.2.14.tgz",
*      "integrity": "sha512-2dvkUKLuFdKsCRmOE4Mn63co0Djtsm+JMh0bYZQupN1pJwMeE8FmQmRLLzzEMN0dnNi7CDCYYH8F0EVwWiPBeA==",
       "dependencies": {

-        "@smithy/types": "^4.3.2",

*        "@smithy/types": "^4.14.1",
           "tslib": "^2.6.2"
         },
         "engines": {
  @@ -1418,14 +1406,13 @@
  }
  },
  "node_modules/@smithy/node-config-provider": {

-      "version": "4.1.4",
-      "resolved": "https://registry.npmjs.org/@smithy/node-config-provider/-/node-config-provider-4.1.4.tgz",
-      "integrity": "sha512-+UDQV/k42jLEPPHSn39l0Bmc4sB1xtdI9Gd47fzo/0PbXzJ7ylgaOByVjF5EeQIumkepnrJyfx86dPa9p47Y+w==",
-      "license": "Apache-2.0",

*      "version": "4.3.14",
*      "resolved": "https://registry.npmjs.org/@smithy/node-config-provider/-/node-config-provider-4.3.14.tgz",
*      "integrity": "sha512-S+gFjyo/weSVL0P1b9Ts8C/CwIfNCgUPikk3sl6QVsfE/uUuO+QsF+NsE/JkpvWqqyz1wg7HFdiaZuj5CoBMRg==",
       "dependencies": {

-        "@smithy/property-provider": "^4.0.5",
-        "@smithy/shared-ini-file-loader": "^4.0.5",
-        "@smithy/types": "^4.3.2",

*        "@smithy/property-provider": "^4.2.14",
*        "@smithy/shared-ini-file-loader": "^4.4.9",
*        "@smithy/types": "^4.14.1",
           "tslib": "^2.6.2"
         },
         "engines": {
  @@ -1433,15 +1420,13 @@
  }
  },
  "node_modules/@smithy/node-http-handler": {

-      "version": "4.1.1",
-      "resolved": "https://registry.npmjs.org/@smithy/node-http-handler/-/node-http-handler-4.1.1.tgz",
-      "integrity": "sha512-RHnlHqFpoVdjSPPiYy/t40Zovf3BBHc2oemgD7VsVTFFZrU5erFFe0n52OANZZ/5sbshgD93sOh5r6I35Xmpaw==",
-      "license": "Apache-2.0",

*      "version": "4.6.1",
*      "resolved": "https://registry.npmjs.org/@smithy/node-http-handler/-/node-http-handler-4.6.1.tgz",
*      "integrity": "sha512-iB+orM4x3xrr57X3YaXazfKnntl0LHlZB1kcXSGzMV1Tt0+YwEjGlbjk/44qEGtBzXAz6yFDzkYTKSV6Pj2HUg==",
       "dependencies": {

-        "@smithy/abort-controller": "^4.0.5",
-        "@smithy/protocol-http": "^5.1.3",
-        "@smithy/querystring-builder": "^4.0.5",
-        "@smithy/types": "^4.3.2",

*        "@smithy/protocol-http": "^5.3.14",
*        "@smithy/querystring-builder": "^4.2.14",
*        "@smithy/types": "^4.14.1",
           "tslib": "^2.6.2"
         },
         "engines": {
  @@ -1449,12 +1434,11 @@
  }
  },
  "node_modules/@smithy/property-provider": {

-      "version": "4.0.5",
-      "resolved": "https://registry.npmjs.org/@smithy/property-provider/-/property-provider-4.0.5.tgz",
-      "integrity": "sha512-R/bswf59T/n9ZgfgUICAZoWYKBHcsVDurAGX88zsiUtOTA/xUAPyiT+qkNCPwFn43pZqN84M4MiUsbSGQmgFIQ==",
-      "license": "Apache-2.0",

*      "version": "4.2.14",
*      "resolved": "https://registry.npmjs.org/@smithy/property-provider/-/property-provider-4.2.14.tgz",
*      "integrity": "sha512-WuM31CgfsnQ/10i7NYr0PyxqknD72Y5uMfUMVSniPjbEPceiTErb4eIqJQ+pdxNEAUEWrewrGjIRjVbVHsxZiQ==",
       "dependencies": {

-        "@smithy/types": "^4.3.2",

*        "@smithy/types": "^4.14.1",
           "tslib": "^2.6.2"
         },
         "engines": {
  @@ -1462,12 +1446,11 @@
  }
  },
  "node_modules/@smithy/protocol-http": {

-      "version": "5.1.3",
-      "resolved": "https://registry.npmjs.org/@smithy/protocol-http/-/protocol-http-5.1.3.tgz",
-      "integrity": "sha512-fCJd2ZR7D22XhDY0l+92pUag/7je2BztPRQ01gU5bMChcyI0rlly7QFibnYHzcxDvccMjlpM/Q1ev8ceRIb48w==",
-      "license": "Apache-2.0",

*      "version": "5.3.14",
*      "resolved": "https://registry.npmjs.org/@smithy/protocol-http/-/protocol-http-5.3.14.tgz",
*      "integrity": "sha512-dN5F8kHx8RNU0r+pCwNmFZyz6ChjMkzShy/zup6MtkRmmix4vZzJdW+di7x//b1LiynIev88FM18ie+wwPcQtQ==",
       "dependencies": {

-        "@smithy/types": "^4.3.2",

*        "@smithy/types": "^4.14.1",
           "tslib": "^2.6.2"
         },
         "engines": {
  @@ -1475,13 +1458,12 @@
  }
  },
  "node_modules/@smithy/querystring-builder": {

-      "version": "4.0.5",
-      "resolved": "https://registry.npmjs.org/@smithy/querystring-builder/-/querystring-builder-4.0.5.tgz",
-      "integrity": "sha512-NJeSCU57piZ56c+/wY+AbAw6rxCCAOZLCIniRE7wqvndqxcKKDOXzwWjrY7wGKEISfhL9gBbAaWWgHsUGedk+A==",
-      "license": "Apache-2.0",

*      "version": "4.2.14",
*      "resolved": "https://registry.npmjs.org/@smithy/querystring-builder/-/querystring-builder-4.2.14.tgz",
*      "integrity": "sha512-XYA5Z0IqTeF+5XDdh4BBmSA0HvbgVZIyv4cmOoUheDNR57K1HgBp9ukUMx3Cr3XpDHHpLBnexPE3LAtDsZkj2A==",
       "dependencies": {

-        "@smithy/types": "^4.3.2",
-        "@smithy/util-uri-escape": "^4.0.0",

*        "@smithy/types": "^4.14.1",
*        "@smithy/util-uri-escape": "^4.2.2",
           "tslib": "^2.6.2"
         },
         "engines": {
  @@ -1489,12 +1471,11 @@
  }
  },
  "node_modules/@smithy/querystring-parser": {

-      "version": "4.0.5",
-      "resolved": "https://registry.npmjs.org/@smithy/querystring-parser/-/querystring-parser-4.0.5.tgz",
-      "integrity": "sha512-6SV7md2CzNG/WUeTjVe6Dj8noH32r4MnUeFKZrnVYsQxpGSIcphAanQMayi8jJLZAWm6pdM9ZXvKCpWOsIGg0w==",
-      "license": "Apache-2.0",

*      "version": "4.2.14",
*      "resolved": "https://registry.npmjs.org/@smithy/querystring-parser/-/querystring-parser-4.2.14.tgz",
*      "integrity": "sha512-hr+YyqBD23GVvRxGGrcc/oOeNlK3PzT5Fu4dzrDXxzS1LpFiuL2PQQqKPs87M79aW7ziMs+nvB3qdw77SqE7Lw==",
       "dependencies": {

-        "@smithy/types": "^4.3.2",

*        "@smithy/types": "^4.14.1",
           "tslib": "^2.6.2"
         },
         "engines": {
  @@ -1502,24 +1483,22 @@
  }
  },
  "node_modules/@smithy/service-error-classification": {

-      "version": "4.0.7",
-      "resolved": "https://registry.npmjs.org/@smithy/service-error-classification/-/service-error-classification-4.0.7.tgz",
-      "integrity": "sha512-XvRHOipqpwNhEjDf2L5gJowZEm5nsxC16pAZOeEcsygdjv9A2jdOh3YoDQvOXBGTsaJk6mNWtzWalOB9976Wlg==",
-      "license": "Apache-2.0",

*      "version": "4.3.1",
*      "resolved": "https://registry.npmjs.org/@smithy/service-error-classification/-/service-error-classification-4.3.1.tgz",
*      "integrity": "sha512-aUQuDGh760ts/8MU+APjIZhlLPKhIIfqyzZaJikLEIMrdxFvxuLYD0WxWzaYWpmLbQlXDe9p7EWM3HsBe0K6Gw==",
       "dependencies": {

-        "@smithy/types": "^4.3.2"

*        "@smithy/types": "^4.14.1"
       },
       "engines": {
         "node": ">=18.0.0"
       }
  },
  "node_modules/@smithy/shared-ini-file-loader": {

-      "version": "4.0.5",
-      "resolved": "https://registry.npmjs.org/@smithy/shared-ini-file-loader/-/shared-ini-file-loader-4.0.5.tgz",
-      "integrity": "sha512-YVVwehRDuehgoXdEL4r1tAAzdaDgaC9EQvhK0lEbfnbrd0bd5+CTQumbdPryX3J2shT7ZqQE+jPW4lmNBAB8JQ==",
-      "license": "Apache-2.0",

*      "version": "4.4.9",
*      "resolved": "https://registry.npmjs.org/@smithy/shared-ini-file-loader/-/shared-ini-file-loader-4.4.9.tgz",
*      "integrity": "sha512-495/V2I15SHgedSJoDPD23JuSfKAp726ZI1V0wtjB07Wh7q/0tri/0e0DLefZCHgxZonrGKt/OCTpAtP1wE1kQ==",
       "dependencies": {

-        "@smithy/types": "^4.3.2",

*        "@smithy/types": "^4.14.1",
           "tslib": "^2.6.2"
         },
         "engines": {
  @@ -1527,18 +1506,17 @@
  }
  },
  "node_modules/@smithy/signature-v4": {

-      "version": "5.1.3",
-      "resolved": "https://registry.npmjs.org/@smithy/signature-v4/-/signature-v4-5.1.3.tgz",
-      "integrity": "sha512-mARDSXSEgllNzMw6N+mC+r1AQlEBO3meEAkR/UlfAgnMzJUB3goRBWgip1EAMG99wh36MDqzo86SfIX5Y+VEaw==",
-      "license": "Apache-2.0",

*      "version": "5.3.14",
*      "resolved": "https://registry.npmjs.org/@smithy/signature-v4/-/signature-v4-5.3.14.tgz",
*      "integrity": "sha512-1D9Y/nmlVjCeSivCbhZ7hgEpmHyY1h0GvpSZt3l0xcD9JjmjVC1CHOozS6+Gh+/ldMH8JuJ6cujObQqfayAVFA==",
       "dependencies": {

-        "@smithy/is-array-buffer": "^4.0.0",
-        "@smithy/protocol-http": "^5.1.3",
-        "@smithy/types": "^4.3.2",
-        "@smithy/util-hex-encoding": "^4.0.0",
-        "@smithy/util-middleware": "^4.0.5",
-        "@smithy/util-uri-escape": "^4.0.0",
-        "@smithy/util-utf8": "^4.0.0",

*        "@smithy/is-array-buffer": "^4.2.2",
*        "@smithy/protocol-http": "^5.3.14",
*        "@smithy/types": "^4.14.1",
*        "@smithy/util-hex-encoding": "^4.2.2",
*        "@smithy/util-middleware": "^4.2.14",
*        "@smithy/util-uri-escape": "^4.2.2",
*        "@smithy/util-utf8": "^4.2.2",
           "tslib": "^2.6.2"
         },
         "engines": {
  @@ -1546,17 +1524,16 @@
  }
  },
  "node_modules/@smithy/smithy-client": {

-      "version": "4.4.10",
-      "resolved": "https://registry.npmjs.org/@smithy/smithy-client/-/smithy-client-4.4.10.tgz",
-      "integrity": "sha512-iW6HjXqN0oPtRS0NK/zzZ4zZeGESIFcxj2FkWed3mcK8jdSdHzvnCKXSjvewESKAgGKAbJRA+OsaqKhkdYRbQQ==",
-      "license": "Apache-2.0",

*      "version": "4.12.13",
*      "resolved": "https://registry.npmjs.org/@smithy/smithy-client/-/smithy-client-4.12.13.tgz",
*      "integrity": "sha512-y/Pcj1V9+qG98gyu1gvftHB7rDpdh+7kIBIggs55yGm3JdtBV8GT8IFF3a1qxZ79QnaJHX9GXzvBG6tAd+czJA==",
       "dependencies": {

-        "@smithy/core": "^3.8.0",
-        "@smithy/middleware-endpoint": "^4.1.18",
-        "@smithy/middleware-stack": "^4.0.5",
-        "@smithy/protocol-http": "^5.1.3",
-        "@smithy/types": "^4.3.2",
-        "@smithy/util-stream": "^4.2.4",

*        "@smithy/core": "^3.23.17",
*        "@smithy/middleware-endpoint": "^4.4.32",
*        "@smithy/middleware-stack": "^4.2.14",
*        "@smithy/protocol-http": "^5.3.14",
*        "@smithy/types": "^4.14.1",
*        "@smithy/util-stream": "^4.5.25",
           "tslib": "^2.6.2"
         },
         "engines": {
  @@ -1564,10 +1541,9 @@
  }
  },
  "node_modules/@smithy/types": {

-      "version": "4.3.2",
-      "resolved": "https://registry.npmjs.org/@smithy/types/-/types-4.3.2.tgz",
-      "integrity": "sha512-QO4zghLxiQ5W9UZmX2Lo0nta2PuE1sSrXUYDoaB6HMR762C0P7v/HEPHf6ZdglTVssJG1bsrSBxdc3quvDSihw==",
-      "license": "Apache-2.0",

*      "version": "4.14.1",
*      "resolved": "https://registry.npmjs.org/@smithy/types/-/types-4.14.1.tgz",
*      "integrity": "sha512-59b5HtSVrVR/eYNei3BUj3DCPKD/G7EtDDe7OEJE7i7FtQFugYo6MxbotS8mVJkLNVf8gYaAlEBwwtJ9HzhWSg==",
         "dependencies": {
           "tslib": "^2.6.2"
         },
  @@ -1576,13 +1552,12 @@
  }
  },
  "node_modules/@smithy/url-parser": {

-      "version": "4.0.5",
-      "resolved": "https://registry.npmjs.org/@smithy/url-parser/-/url-parser-4.0.5.tgz",
-      "integrity": "sha512-j+733Um7f1/DXjYhCbvNXABV53NyCRRA54C7bNEIxNPs0YjfRxeMKjjgm2jvTYrciZyCjsicHwQ6Q0ylo+NAUw==",
-      "license": "Apache-2.0",

*      "version": "4.2.14",
*      "resolved": "https://registry.npmjs.org/@smithy/url-parser/-/url-parser-4.2.14.tgz",
*      "integrity": "sha512-p06BiBigJ8bTA3MgnOfCtDUWnAMY0YfedO/GRpmc7p+wg3KW8vbXy1xwSu5ASy0wV7rRYtlfZOIKH4XqfhjSQQ==",
       "dependencies": {

-        "@smithy/querystring-parser": "^4.0.5",
-        "@smithy/types": "^4.3.2",

*        "@smithy/querystring-parser": "^4.2.14",
*        "@smithy/types": "^4.14.1",
           "tslib": "^2.6.2"
         },
         "engines": {
  @@ -1590,13 +1565,12 @@
  }
  },
  "node_modules/@smithy/util-base64": {

-      "version": "4.0.0",
-      "resolved": "https://registry.npmjs.org/@smithy/util-base64/-/util-base64-4.0.0.tgz",
-      "integrity": "sha512-CvHfCmO2mchox9kjrtzoHkWHxjHZzaFojLc8quxXY7WAAMAg43nuxwv95tATVgQFNDwd4M9S1qFzj40Ul41Kmg==",
-      "license": "Apache-2.0",

*      "version": "4.3.2",
*      "resolved": "https://registry.npmjs.org/@smithy/util-base64/-/util-base64-4.3.2.tgz",
*      "integrity": "sha512-XRH6b0H/5A3SgblmMa5ErXQ2XKhfbQB+Fm/oyLZ2O2kCUrwgg55bU0RekmzAhuwOjA9qdN5VU2BprOvGGUkOOQ==",
       "dependencies": {

-        "@smithy/util-buffer-from": "^4.0.0",
-        "@smithy/util-utf8": "^4.0.0",

*        "@smithy/util-buffer-from": "^4.2.2",
*        "@smithy/util-utf8": "^4.2.2",
           "tslib": "^2.6.2"
         },
         "engines": {
  @@ -1604,10 +1578,9 @@
  }
  },
  "node_modules/@smithy/util-body-length-browser": {

-      "version": "4.0.0",
-      "resolved": "https://registry.npmjs.org/@smithy/util-body-length-browser/-/util-body-length-browser-4.0.0.tgz",
-      "integrity": "sha512-sNi3DL0/k64/LO3A256M+m3CDdG6V7WKWHdAiBBMUN8S3hK3aMPhwnPik2A/a2ONN+9doY9UxaLfgqsIRg69QA==",
-      "license": "Apache-2.0",

*      "version": "4.2.2",
*      "resolved": "https://registry.npmjs.org/@smithy/util-body-length-browser/-/util-body-length-browser-4.2.2.tgz",
*      "integrity": "sha512-JKCrLNOup3OOgmzeaKQwi4ZCTWlYR5H4Gm1r2uTMVBXoemo1UEghk5vtMi1xSu2ymgKVGW631e2fp9/R610ZjQ==",
         "dependencies": {
           "tslib": "^2.6.2"
         },
  @@ -1616,10 +1589,9 @@
  }
  },
  "node_modules/@smithy/util-body-length-node": {

-      "version": "4.0.0",
-      "resolved": "https://registry.npmjs.org/@smithy/util-body-length-node/-/util-body-length-node-4.0.0.tgz",
-      "integrity": "sha512-q0iDP3VsZzqJyje8xJWEJCNIu3lktUGVoSy1KB0UWym2CL1siV3artm+u1DFYTLejpsrdGyCSWBdGNjJzfDPjg==",
-      "license": "Apache-2.0",

*      "version": "4.2.3",
*      "resolved": "https://registry.npmjs.org/@smithy/util-body-length-node/-/util-body-length-node-4.2.3.tgz",
*      "integrity": "sha512-ZkJGvqBzMHVHE7r/hcuCxlTY8pQr1kMtdsVPs7ex4mMU+EAbcXppfo5NmyxMYi2XU49eqaz56j2gsk4dHHPG/g==",
         "dependencies": {
           "tslib": "^2.6.2"
         },
  @@ -1628,12 +1600,11 @@
  }
  },
  "node_modules/@smithy/util-buffer-from": {

-      "version": "4.0.0",
-      "resolved": "https://registry.npmjs.org/@smithy/util-buffer-from/-/util-buffer-from-4.0.0.tgz",
-      "integrity": "sha512-9TOQ7781sZvddgO8nxueKi3+yGvkY35kotA0Y6BWRajAv8jjmigQ1sBwz0UX47pQMYXJPahSKEKYFgt+rXdcug==",
-      "license": "Apache-2.0",

*      "version": "4.2.2",
*      "resolved": "https://registry.npmjs.org/@smithy/util-buffer-from/-/util-buffer-from-4.2.2.tgz",
*      "integrity": "sha512-FDXD7cvUoFWwN6vtQfEta540Y/YBe5JneK3SoZg9bThSoOAC/eGeYEua6RkBgKjGa/sz6Y+DuBZj3+YEY21y4Q==",
       "dependencies": {

-        "@smithy/is-array-buffer": "^4.0.0",

*        "@smithy/is-array-buffer": "^4.2.2",
           "tslib": "^2.6.2"
         },
         "engines": {
  @@ -1641,10 +1612,9 @@
  }
  },
  "node_modules/@smithy/util-config-provider": {

-      "version": "4.0.0",
-      "resolved": "https://registry.npmjs.org/@smithy/util-config-provider/-/util-config-provider-4.0.0.tgz",
-      "integrity": "sha512-L1RBVzLyfE8OXH+1hsJ8p+acNUSirQnWQ6/EgpchV88G6zGBTDPdXiiExei6Z1wR2RxYvxY/XLw6AMNCCt8H3w==",
-      "license": "Apache-2.0",

*      "version": "4.2.2",
*      "resolved": "https://registry.npmjs.org/@smithy/util-config-provider/-/util-config-provider-4.2.2.tgz",
*      "integrity": "sha512-dWU03V3XUprJwaUIFVv4iOnS1FC9HnMHDfUrlNDSh4315v0cWyaIErP8KiqGVbf5z+JupoVpNM7ZB3jFiTejvQ==",
         "dependencies": {
           "tslib": "^2.6.2"
         },
  @@ -1653,15 +1623,13 @@
  }
  },
  "node_modules/@smithy/util-defaults-mode-browser": {

-      "version": "4.0.26",
-      "resolved": "https://registry.npmjs.org/@smithy/util-defaults-mode-browser/-/util-defaults-mode-browser-4.0.26.tgz",
-      "integrity": "sha512-xgl75aHIS/3rrGp7iTxQAOELYeyiwBu+eEgAk4xfKwJJ0L8VUjhO2shsDpeil54BOFsqmk5xfdesiewbUY5tKQ==",
-      "license": "Apache-2.0",
-      "dependencies": {
-        "@smithy/property-provider": "^4.0.5",
-        "@smithy/smithy-client": "^4.4.10",
-        "@smithy/types": "^4.3.2",
-        "bowser": "^2.11.0",

*      "version": "4.3.49",
*      "resolved": "https://registry.npmjs.org/@smithy/util-defaults-mode-browser/-/util-defaults-mode-browser-4.3.49.tgz",
*      "integrity": "sha512-a5bNrdiONYB/qE2BuKegvUMd/+ZDwdg4vsNuuSzYE8qs2EYAdK9CynL+Rzn29PbPiUqoz/cbpRbcLzD5lEevHw==",
*      "dependencies": {
*        "@smithy/property-provider": "^4.2.14",
*        "@smithy/smithy-client": "^4.12.13",
*        "@smithy/types": "^4.14.1",
           "tslib": "^2.6.2"
         },
         "engines": {
  @@ -1669,17 +1637,16 @@
  }
  },
  "node_modules/@smithy/util-defaults-mode-node": {

-      "version": "4.0.26",
-      "resolved": "https://registry.npmjs.org/@smithy/util-defaults-mode-node/-/util-defaults-mode-node-4.0.26.tgz",
-      "integrity": "sha512-z81yyIkGiLLYVDetKTUeCZQ8x20EEzvQjrqJtb/mXnevLq2+w3XCEWTJ2pMp401b6BkEkHVfXb/cROBpVauLMQ==",
-      "license": "Apache-2.0",

*      "version": "4.2.54",
*      "resolved": "https://registry.npmjs.org/@smithy/util-defaults-mode-node/-/util-defaults-mode-node-4.2.54.tgz",
*      "integrity": "sha512-g1cvrJvOnzeJgEdf7AE4luI7gp6L8weE0y9a9wQUSGtjb8QRHDbCJYuE4Sy0SD9N8RrnNPFsPltAz/OSoBR9Zw==",
       "dependencies": {

-        "@smithy/config-resolver": "^4.1.5",
-        "@smithy/credential-provider-imds": "^4.0.7",
-        "@smithy/node-config-provider": "^4.1.4",
-        "@smithy/property-provider": "^4.0.5",
-        "@smithy/smithy-client": "^4.4.10",
-        "@smithy/types": "^4.3.2",

*        "@smithy/config-resolver": "^4.4.17",
*        "@smithy/credential-provider-imds": "^4.2.14",
*        "@smithy/node-config-provider": "^4.3.14",
*        "@smithy/property-provider": "^4.2.14",
*        "@smithy/smithy-client": "^4.12.13",
*        "@smithy/types": "^4.14.1",
           "tslib": "^2.6.2"
         },
         "engines": {
  @@ -1687,13 +1654,12 @@
  }
  },
  "node_modules/@smithy/util-endpoints": {

-      "version": "3.0.7",
-      "resolved": "https://registry.npmjs.org/@smithy/util-endpoints/-/util-endpoints-3.0.7.tgz",
-      "integrity": "sha512-klGBP+RpBp6V5JbrY2C/VKnHXn3d5V2YrifZbmMY8os7M6m8wdYFoO6w/fe5VkP+YVwrEktW3IWYaSQVNZJ8oQ==",
-      "license": "Apache-2.0",

*      "version": "3.4.2",
*      "resolved": "https://registry.npmjs.org/@smithy/util-endpoints/-/util-endpoints-3.4.2.tgz",
*      "integrity": "sha512-a55Tr+3OKld4TTtnT+RhKOQHyPxm3j/xL4OR83WBUhLJaKDS9dnJ7arRMOp3t31dcLhApwG9bgvrRXBHlLdIkg==",
       "dependencies": {

-        "@smithy/node-config-provider": "^4.1.4",
-        "@smithy/types": "^4.3.2",

*        "@smithy/node-config-provider": "^4.3.14",
*        "@smithy/types": "^4.14.1",
           "tslib": "^2.6.2"
         },
         "engines": {
  @@ -1701,10 +1667,9 @@
  }
  },
  "node_modules/@smithy/util-hex-encoding": {

-      "version": "4.0.0",
-      "resolved": "https://registry.npmjs.org/@smithy/util-hex-encoding/-/util-hex-encoding-4.0.0.tgz",
-      "integrity": "sha512-Yk5mLhHtfIgW2W2WQZWSg5kuMZCVbvhFmC7rV4IO2QqnZdbEFPmQnCcGMAX2z/8Qj3B9hYYNjZOhWym+RwhePw==",
-      "license": "Apache-2.0",

*      "version": "4.2.2",
*      "resolved": "https://registry.npmjs.org/@smithy/util-hex-encoding/-/util-hex-encoding-4.2.2.tgz",
*      "integrity": "sha512-Qcz3W5vuHK4sLQdyT93k/rfrUwdJ8/HZ+nMUOyGdpeGA1Wxt65zYwi3oEl9kOM+RswvYq90fzkNDahPS8K0OIg==",
         "dependencies": {
           "tslib": "^2.6.2"
         },
  @@ -1713,12 +1678,11 @@
  }
  },
  "node_modules/@smithy/util-middleware": {

-      "version": "4.0.5",
-      "resolved": "https://registry.npmjs.org/@smithy/util-middleware/-/util-middleware-4.0.5.tgz",
-      "integrity": "sha512-N40PfqsZHRSsByGB81HhSo+uvMxEHT+9e255S53pfBw/wI6WKDI7Jw9oyu5tJTLwZzV5DsMha3ji8jk9dsHmQQ==",
-      "license": "Apache-2.0",

*      "version": "4.2.14",
*      "resolved": "https://registry.npmjs.org/@smithy/util-middleware/-/util-middleware-4.2.14.tgz",
*      "integrity": "sha512-1Su2vj9RYNDEv/V+2E+jXkkwGsgR7dc4sfHn9Z7ruzQHJIEni9zzw5CauvRXlFJfmgcqYP8fWa0dkh2Q2YaQyw==",
       "dependencies": {

-        "@smithy/types": "^4.3.2",

*        "@smithy/types": "^4.14.1",
           "tslib": "^2.6.2"
         },
         "engines": {
  @@ -1726,13 +1690,12 @@
  }
  },
  "node_modules/@smithy/util-retry": {

-      "version": "4.0.7",
-      "resolved": "https://registry.npmjs.org/@smithy/util-retry/-/util-retry-4.0.7.tgz",
-      "integrity": "sha512-TTO6rt0ppK70alZpkjwy+3nQlTiqNfoXja+qwuAchIEAIoSZW8Qyd76dvBv3I5bCpE38APafG23Y/u270NspiQ==",
-      "license": "Apache-2.0",

*      "version": "4.3.6",
*      "resolved": "https://registry.npmjs.org/@smithy/util-retry/-/util-retry-4.3.6.tgz",
*      "integrity": "sha512-p6/FO1n2KxMeQyna067i0uJ6TSbb165ZhnRtCpWh4Foxqbfc6oW+XITaL8QkFJj3KFnDe2URt4gOhgU06EP9ew==",
       "dependencies": {

-        "@smithy/service-error-classification": "^4.0.7",
-        "@smithy/types": "^4.3.2",

*        "@smithy/service-error-classification": "^4.3.1",
*        "@smithy/types": "^4.14.1",
           "tslib": "^2.6.2"
         },
         "engines": {
  @@ -1740,18 +1703,17 @@
  }
  },
  "node_modules/@smithy/util-stream": {

-      "version": "4.2.4",
-      "resolved": "https://registry.npmjs.org/@smithy/util-stream/-/util-stream-4.2.4.tgz",
-      "integrity": "sha512-vSKnvNZX2BXzl0U2RgCLOwWaAP9x/ddd/XobPK02pCbzRm5s55M53uwb1rl/Ts7RXZvdJZerPkA+en2FDghLuQ==",
-      "license": "Apache-2.0",

*      "version": "4.5.25",
*      "resolved": "https://registry.npmjs.org/@smithy/util-stream/-/util-stream-4.5.25.tgz",
*      "integrity": "sha512-/PFpG4k8Ze8Ei+mMKj3oiPICYekthuzePZMgZbCqMiXIHHf4n2aZ4Ps0aSRShycFTGuj/J6XldmC0x0DwednIA==",
       "dependencies": {

-        "@smithy/fetch-http-handler": "^5.1.1",
-        "@smithy/node-http-handler": "^4.1.1",
-        "@smithy/types": "^4.3.2",
-        "@smithy/util-base64": "^4.0.0",
-        "@smithy/util-buffer-from": "^4.0.0",
-        "@smithy/util-hex-encoding": "^4.0.0",
-        "@smithy/util-utf8": "^4.0.0",

*        "@smithy/fetch-http-handler": "^5.3.17",
*        "@smithy/node-http-handler": "^4.6.1",
*        "@smithy/types": "^4.14.1",
*        "@smithy/util-base64": "^4.3.2",
*        "@smithy/util-buffer-from": "^4.2.2",
*        "@smithy/util-hex-encoding": "^4.2.2",
*        "@smithy/util-utf8": "^4.2.2",
           "tslib": "^2.6.2"
         },
         "engines": {
  @@ -1759,10 +1721,9 @@
  }
  },
  "node_modules/@smithy/util-uri-escape": {

-      "version": "4.0.0",
-      "resolved": "https://registry.npmjs.org/@smithy/util-uri-escape/-/util-uri-escape-4.0.0.tgz",
-      "integrity": "sha512-77yfbCbQMtgtTylO9itEAdpPXSog3ZxMe09AEhm0dU0NLTalV70ghDZFR+Nfi1C60jnJoh/Re4090/DuZh2Omg==",
-      "license": "Apache-2.0",

*      "version": "4.2.2",
*      "resolved": "https://registry.npmjs.org/@smithy/util-uri-escape/-/util-uri-escape-4.2.2.tgz",
*      "integrity": "sha512-2kAStBlvq+lTXHyAZYfJRb/DfS3rsinLiwb+69SstC9Vb0s9vNWkRwpnj918Pfi85mzi42sOqdV72OLxWAISnw==",
         "dependencies": {
           "tslib": "^2.6.2"
         },
  @@ -1771,51 +1732,47 @@
  }
  },
  "node_modules/@smithy/util-utf8": {

-      "version": "4.0.0",
-      "resolved": "https://registry.npmjs.org/@smithy/util-utf8/-/util-utf8-4.0.0.tgz",
-      "integrity": "sha512-b+zebfKCfRdgNJDknHCob3O7FpeYQN6ZG6YLExMcasDHsCXlsXCEuiPZeLnJLpwa5dvPetGlnGCiMHuLwGvFow==",
-      "license": "Apache-2.0",

*      "version": "4.2.2",
*      "resolved": "https://registry.npmjs.org/@smithy/util-utf8/-/util-utf8-4.2.2.tgz",
*      "integrity": "sha512-75MeYpjdWRe8M5E3AW0O4Cx3UadweS+cwdXjwYGBW5h/gxxnbeZ877sLPX/ZJA9GVTlL/qG0dXP29JWFCD1Ayw==",
       "dependencies": {

-        "@smithy/util-buffer-from": "^4.0.0",

*        "@smithy/util-buffer-from": "^4.2.2",
         "tslib": "^2.6.2"
       },
       "engines": {
         "node": ">=18.0.0"
       }
  },

- "node_modules/@types/diff": {
-      "version": "7.0.2",
-      "resolved": "https://registry.npmjs.org/@types/diff/-/diff-7.0.2.tgz",
-      "integrity": "sha512-JSWRMozjFKsGlEjiiKajUjIJVKuKdE3oVy2DNtK+fUo8q82nhFZ2CPQwicAIkXrofahDXrWJ7mjelvZphMS98Q==",
-      "license": "MIT"

* "node_modules/@smithy/uuid": {
*      "version": "1.1.2",
*      "resolved": "https://registry.npmjs.org/@smithy/uuid/-/uuid-1.1.2.tgz",
*      "integrity": "sha512-O/IEdcCUKkubz60tFbGA7ceITTAJsty+lBjNoorP4Z6XRqaFb/OjQjZODophEcuq68nKm6/0r+6/lLQ+XVpk8g==",
*      "dependencies": {
*        "tslib": "^2.6.2"
*      },
*      "engines": {
*        "node": ">=18.0.0"
*      }
  },
  "node_modules/@types/node": {

-      "version": "24.2.1",
-      "resolved": "https://registry.npmjs.org/@types/node/-/node-24.2.1.tgz",
-      "integrity": "sha512-DRh5K+ka5eJic8CjH7td8QpYEV6Zo10gfRkjHCO3weqZHWDtAaSTFtl4+VMqOJ4N5jcuhZ9/l+yy8rVgw7BQeQ==",

*      "version": "25.6.0",
*      "resolved": "https://registry.npmjs.org/@types/node/-/node-25.6.0.tgz",
*      "integrity": "sha512-+qIYRKdNYJwY3vRCZMdJbPLJAtGjQBudzZzdzwQYkEPQd+PJGixUL5QfvCLDaULoLv+RhT3LDkwEfKaAkgSmNQ==",
       "dev": true,

-      "license": "MIT",
       "dependencies": {
-        "undici-types": "~7.10.0"

*        "undici-types": "~7.19.0"
       }
  },
  "node_modules/@types/treeify": {
  "version": "1.0.3",
  "resolved": "https://registry.npmjs.org/@types/treeify/-/treeify-1.0.3.tgz",
  "integrity": "sha512-hx0o7zWEUU4R2Amn+pjCBQQt23Khy/Dk56gQU5xi5jtPL1h83ACJCeFaB2M/+WO1AntvWrSoVnnCAfI1AQH4Cg==",

-      "license": "MIT"
- },
- "node_modules/@types/uuid": {
-      "version": "9.0.8",
-      "resolved": "https://registry.npmjs.org/@types/uuid/-/uuid-9.0.8.tgz",
-      "integrity": "sha512-jg+97EGIcY9AGHJJRaaPVgetKDsrTgbRjQ5Msgjh/DQKEFl0DtyRr/VCOyD1T2R1MNeWPK/u7JoGhlDZnKBAfA==",
-      "license": "MIT"

*      "dev": true
  },
  "node_modules/accepts": {
  "version": "2.0.0",
  "resolved": "https://registry.npmjs.org/accepts/-/accepts-2.0.0.tgz",
  "integrity": "sha512-5cvg6CtKwfgdmVqY1WIiXKc3Q1bkRqGLi+2W/6ao+6Y7gu/RCwRuAhGEzh5B4KlszSuTLgZYuqFqo5bImjNKng==",

-      "license": "MIT",
         "dependencies": {
           "mime-types": "^3.0.0",
           "negotiator": "^1.0.0"
  @@ -1825,27 +1782,41 @@
  }
  },
  "node_modules/ajv": {
-      "version": "6.12.6",
-      "resolved": "https://registry.npmjs.org/ajv/-/ajv-6.12.6.tgz",
-      "integrity": "sha512-j3fVLgvTo527anyYyJOGTYJbG+vnnQYvE0m5mmkc1TK+nxAppkCLMIL0aZ4dblVCNoGShhm+kzE4ZUykBoMg4g==",
-      "license": "MIT",

*      "version": "8.20.0",
*      "resolved": "https://registry.npmjs.org/ajv/-/ajv-8.20.0.tgz",
*      "integrity": "sha512-Thbli+OlOj+iMPYFBVBfJ3OmCAnaSyNn4M1vz9T6Gka5Jt9ba/HIR56joy65tY6kx/FCF5VXNB819Y7/GUrBGA==",
       "dependencies": {

-        "fast-deep-equal": "^3.1.1",
-        "fast-json-stable-stringify": "^2.0.0",
-        "json-schema-traverse": "^0.4.1",
-        "uri-js": "^4.2.2"

*        "fast-deep-equal": "^3.1.3",
*        "fast-uri": "^3.0.1",
*        "json-schema-traverse": "^1.0.0",
*        "require-from-string": "^2.0.2"
       },
       "funding": {
         "type": "github",
         "url": "https://github.com/sponsors/epoberezkin"
       }
  },
* "node_modules/ajv-formats": {
*      "version": "3.0.1",
*      "resolved": "https://registry.npmjs.org/ajv-formats/-/ajv-formats-3.0.1.tgz",
*      "integrity": "sha512-8iUql50EUR+uUcdRQ3HDqa6EVyo3docL8g5WJ3FNcWmu62IbkGUue/pEyLBW8VGKKucTPgqeks4fIU1DA4yowQ==",
*      "dependencies": {
*        "ajv": "^8.0.0"
*      },
*      "peerDependencies": {
*        "ajv": "^8.0.0"
*      },
*      "peerDependenciesMeta": {
*        "ajv": {
*          "optional": true
*        }
*      }
* },
  "node_modules/anymatch": {
  "version": "3.1.3",
  "resolved": "https://registry.npmjs.org/anymatch/-/anymatch-3.1.3.tgz",
  "integrity": "sha512-KMReFUr0B4t+D+OBkjR3KYqvocp2XaSzO55UcB6mgQMd3KbcE+mWTyvVV7D/zsdEbNnV6acZUutkiHQXvTr1Rw==",
  "dev": true,

-      "license": "ISC",
         "dependencies": {
           "normalize-path": "^3.0.0",
           "picomatch": "^2.0.4"
  @@ -1855,18 +1826,19 @@
  }
  },
  "node_modules/balanced-match": {
-      "version": "1.0.2",
-      "resolved": "https://registry.npmjs.org/balanced-match/-/balanced-match-1.0.2.tgz",
-      "integrity": "sha512-3oSeUO0TMV67hN1AmbXsK4yaqU7tjiHlbxRDZOpH0KW9+CeX4bRAaX0Anxt0tx2MrpRpWwQaPwIlISEJhYU5Pw==",

*      "version": "4.0.4",
*      "resolved": "https://registry.npmjs.org/balanced-match/-/balanced-match-4.0.4.tgz",
*      "integrity": "sha512-BLrgEcRTwX2o6gGxGOCNyMvGSp35YofuYzw9h1IMTRmKqttAZZVU67bdb9Pr2vUHA8+j3i2tJfjO6C6+4myGTA==",
       "dev": true,

-      "license": "MIT"

*      "engines": {
*        "node": "18 || 20 || >=22"
*      }
  },
  "node_modules/binary-extensions": {
  "version": "2.3.0",
  "resolved": "https://registry.npmjs.org/binary-extensions/-/binary-extensions-2.3.0.tgz",
  "integrity": "sha512-Ceh+7ox5qe7LJuLHoY0feh3pHuUDHAcRUeyL2VYghZwfpkNIy/+8Ocg0a3UuSoYzavmylwuLWQOf3hl0jjMMIw==",
  "dev": true,

-      "license": "MIT",
         "engines": {
           "node": ">=8"
         },
  @@ -1875,40 +1847,43 @@
  }
  },
  "node_modules/body-parser": {
-      "version": "2.2.0",
-      "resolved": "https://registry.npmjs.org/body-parser/-/body-parser-2.2.0.tgz",
-      "integrity": "sha512-02qvAaxv8tp7fBa/mw1ga98OGm+eCbqzJOKoRt70sLmfEEi+jyBYVTDGfCL/k06/4EMk/z01gCe7HoCH/f2LTg==",
-      "license": "MIT",

*      "version": "2.2.2",
*      "resolved": "https://registry.npmjs.org/body-parser/-/body-parser-2.2.2.tgz",
*      "integrity": "sha512-oP5VkATKlNwcgvxi0vM0p/D3n2C3EReYVX+DNYs5TjZFn/oQt2j+4sVJtSMr18pdRr8wjTcBl6LoV+FUwzPmNA==",
       "dependencies": {
         "bytes": "^3.1.2",
         "content-type": "^1.0.5",

-        "debug": "^4.4.0",

*        "debug": "^4.4.3",
         "http-errors": "^2.0.0",

-        "iconv-lite": "^0.6.3",

*        "iconv-lite": "^0.7.0",
         "on-finished": "^2.4.1",

-        "qs": "^6.14.0",
-        "raw-body": "^3.0.0",
-        "type-is": "^2.0.0"

*        "qs": "^6.14.1",
*        "raw-body": "^3.0.1",
*        "type-is": "^2.0.1"
       },
       "engines": {
         "node": ">=18"
*      },
*      "funding": {
*        "type": "opencollective",
*        "url": "https://opencollective.com/express"
       }
  },
  "node_modules/bowser": {

-      "version": "2.12.0",
-      "resolved": "https://registry.npmjs.org/bowser/-/bowser-2.12.0.tgz",
-      "integrity": "sha512-HcOcTudTeEWgbHh0Y1Tyb6fdeR71m4b/QACf0D4KswGTsNeIJQmg38mRENZPAYPZvGFN3fk3604XbQEPdxXdKg==",
-      "license": "MIT"

*      "version": "2.14.1",
*      "resolved": "https://registry.npmjs.org/bowser/-/bowser-2.14.1.tgz",
*      "integrity": "sha512-tzPjzCxygAKWFOJP011oxFHs57HzIhOEracIgAePE4pqB3LikALKnSzUyU4MGs9/iCEUuHlAJTjTc5M+u7YEGg=="
  },
  "node_modules/brace-expansion": {

-      "version": "1.1.12",
-      "resolved": "https://registry.npmjs.org/brace-expansion/-/brace-expansion-1.1.12.tgz",
-      "integrity": "sha512-9T9UjW3r0UW5c1Q7GTwllptXwhvYmEzFhzMfZ9H7FQWt+uZePjZPjBP/W1ZEyZ1twGWom5/56TF4lPcqjnDHcg==",

*      "version": "5.0.5",
*      "resolved": "https://registry.npmjs.org/brace-expansion/-/brace-expansion-5.0.5.tgz",
*      "integrity": "sha512-VZznLgtwhn+Mact9tfiwx64fA9erHH/MCXEUfB/0bX/6Fz6ny5EGTXYltMocqg4xFAQZtnO3DHWWXi8RiuN7cQ==",
       "dev": true,

-      "license": "MIT",
       "dependencies": {
-        "balanced-match": "^1.0.0",
-        "concat-map": "0.0.1"

*        "balanced-match": "^4.0.2"
*      },
*      "engines": {
*        "node": "18 || 20 || >=22"
         }
       },
       "node_modules/braces": {
  @@ -1916,7 +1891,6 @@
  "resolved": "https://registry.npmjs.org/braces/-/braces-3.0.3.tgz",
  "integrity": "sha512-yQbXgO/OSZVD2IsiLlro+7Hf6Q18EJrKSEsdoMzKePKXct3gvD8oLcOQdIzGupr5Fj+EDe8gO/lxc1BzfMpxvA==",
  "dev": true,

-      "license": "MIT",
         "dependencies": {
           "fill-range": "^7.1.1"
         },
  @@ -1928,7 +1902,6 @@
  "version": "3.1.2",
  "resolved": "https://registry.npmjs.org/bytes/-/bytes-3.1.2.tgz",
  "integrity": "sha512-/Nf7TyzTx6S3yRJObOAV7956r8cr2+Oj8AC5dt8wSP3BQAoeX58NoHyCU8P8zGkNXStjTSi6fzO6F0pBdcYbEg==",
-      "license": "MIT",
         "engines": {
           "node": ">= 0.8"
         }
  @@ -1937,7 +1910,6 @@
  "version": "1.0.2",
  "resolved": "https://registry.npmjs.org/call-bind-apply-helpers/-/call-bind-apply-helpers-1.0.2.tgz",
  "integrity": "sha512-Sp1ablJ0ivDkSzjcaJdxEunN5/XvksFJ2sMBFfq6x0ryhQV/2b/KwFe21cMpmHtPOSij8K99/wSfoEuTObmuMQ==",
-      "license": "MIT",
         "dependencies": {
           "es-errors": "^1.3.0",
           "function-bind": "^1.1.2"
  @@ -1950,7 +1922,6 @@
  "version": "1.0.4",
  "resolved": "https://registry.npmjs.org/call-bound/-/call-bound-1.0.4.tgz",
  "integrity": "sha512-+ys997U96po4Kx/ABpBCqhA9EuxJaQWDQg7295H4hBphv3IZg0boBKuwYpt4YXp6MZ5AmZQnU/tyMTlRpaSejg==",
-      "license": "MIT",
         "dependencies": {
           "call-bind-apply-helpers": "^1.0.2",
           "get-intrinsic": "^1.3.0"
  @@ -1967,7 +1938,6 @@
  "resolved": "https://registry.npmjs.org/chokidar/-/chokidar-3.6.0.tgz",
  "integrity": "sha512-7VT13fmjotKpGipCW9JEQAusEPE+Ei8nl6/g4FBAmIm0GOOLMua9NDDo/DWp0ZAxCr3cPq5ZpBqmPAQgDda2Pw==",
  "dev": true,
-      "license": "MIT",
         "dependencies": {
           "anymatch": "~3.1.2",
           "braces": "~3.0.2",
  @@ -1987,30 +1957,22 @@
  "fsevents": "~2.3.2"
  }
  },
- "node_modules/concat-map": {
-      "version": "0.0.1",
-      "resolved": "https://registry.npmjs.org/concat-map/-/concat-map-0.0.1.tgz",
-      "integrity": "sha512-/Srv4dswyQNBfohGpz9o6Yb3Gz3SrUDqBH5rTuhGR7ahtlbYKnVxw2bCFMRljaA7EXHaXZ8wsHdodFvbkhKmqg==",
-      "dev": true,
-      "license": "MIT"
- },
  "node_modules/content-disposition": {
-      "version": "1.0.0",
-      "resolved": "https://registry.npmjs.org/content-disposition/-/content-disposition-1.0.0.tgz",
-      "integrity": "sha512-Au9nRL8VNUut/XSzbQA38+M78dzP4D+eqg3gfJHMIHHYa3bg067xj1KxMUWj+VULbiZMowKngFFbKczUrNJ1mg==",
-      "license": "MIT",
-      "dependencies": {
-        "safe-buffer": "5.2.1"
-      },

*      "version": "1.1.0",
*      "resolved": "https://registry.npmjs.org/content-disposition/-/content-disposition-1.1.0.tgz",
*      "integrity": "sha512-5jRCH9Z/+DRP7rkvY83B+yGIGX96OYdJmzngqnw2SBSxqCFPd0w2km3s5iawpGX8krnwSGmF0FW5Nhr0Hfai3g==",
       "engines": {

-        "node": ">= 0.6"

*        "node": ">=18"
*      },
*      "funding": {
*        "type": "opencollective",
*        "url": "https://opencollective.com/express"
       }
  },
  "node_modules/content-type": {
  "version": "1.0.5",
  "resolved": "https://registry.npmjs.org/content-type/-/content-type-1.0.5.tgz",
  "integrity": "sha512-nTjqfcBFEipKdXCv4YDQWCfmcLZKm81ldF0pAopTvyrFGVbcR6P/VAAd5G7N+0tTr8QqiU0tFadD6FK4NtJwOA==",

-      "license": "MIT",
         "engines": {
           "node": ">= 0.6"
         }
  @@ -2019,7 +1981,6 @@
  "version": "0.7.2",
  "resolved": "https://registry.npmjs.org/cookie/-/cookie-0.7.2.tgz",
  "integrity": "sha512-yki5XnKuf750l50uGTllt6kKILY4nQ1eNIQatoXEByZ5dWgnKqbnqmTrBE5B4N7lrMJKQ2ytWMiTO2o0v6Ew/w==",
-      "license": "MIT",
         "engines": {
           "node": ">= 0.6"
         }
  @@ -2028,29 +1989,30 @@
  "version": "1.2.2",
  "resolved": "https://registry.npmjs.org/cookie-signature/-/cookie-signature-1.2.2.tgz",
  "integrity": "sha512-D76uU73ulSXrD1UXF4KE2TMxVVwhsnCgfAyTg9k8P6KGZjlXKrOLe4dJQKI3Bxi5wjesZoFXJWElNWBjPZMbhg==",
-      "license": "MIT",
       "engines": {
         "node": ">=6.6.0"
       }
  },
  "node_modules/cors": {
-      "version": "2.8.5",
-      "resolved": "https://registry.npmjs.org/cors/-/cors-2.8.5.tgz",
-      "integrity": "sha512-KIHbLJqu73RGr/hnbrO9uBeixNGuvSQjul/jdFvS/KFSIH1hWVd1ng7zOHx+YrEfInLG7q4n6GHQ9cDtxv/P6g==",
-      "license": "MIT",

*      "version": "2.8.6",
*      "resolved": "https://registry.npmjs.org/cors/-/cors-2.8.6.tgz",
*      "integrity": "sha512-tJtZBBHA6vjIAaF6EnIaq6laBBP9aq/Y3ouVJjEfoHbRBcHBAHYcMh/w8LDrk2PvIMMq8gmopa5D4V8RmbrxGw==",
       "dependencies": {
         "object-assign": "^4",
         "vary": "^1"
       },
       "engines": {
         "node": ">= 0.10"
*      },
*      "funding": {
*        "type": "opencollective",
*        "url": "https://opencollective.com/express"
       }
  },
  "node_modules/cross-spawn": {
  "version": "7.0.6",
  "resolved": "https://registry.npmjs.org/cross-spawn/-/cross-spawn-7.0.6.tgz",
  "integrity": "sha512-uV2QOWP2nWzsy2aMp8aRibhi9dlzF5Hgh5SHaB9OiTGEyDTiJJyx0uy51QXdyWbtAHNua4XJzUKca3OzKUd3vA==",

-      "license": "MIT",
         "dependencies": {
           "path-key": "^3.1.0",
           "shebang-command": "^2.0.0",
  @@ -2061,10 +2023,9 @@
  }
  },
  "node_modules/debug": {
-      "version": "4.4.1",
-      "resolved": "https://registry.npmjs.org/debug/-/debug-4.4.1.tgz",
-      "integrity": "sha512-KcKCqiftBJcZr++7ykoDIEwSa3XWowTfNPo92BYxjXiyYEVrUQh2aLyhxBCwww+heortUFxEJYcRzosstTEBYQ==",
-      "license": "MIT",

*      "version": "4.4.3",
*      "resolved": "https://registry.npmjs.org/debug/-/debug-4.4.3.tgz",
*      "integrity": "sha512-RGwwWnwQvkVfavKVt22FGLw+xYSdzARwm0ru6DhTVA3umU5hZc28V3kO4stgYryrTlLpuvgI9GiijltAjNbcqA==",
         "dependencies": {
           "ms": "^2.1.3"
         },
  @@ -2081,16 +2042,14 @@
  "version": "2.0.0",
  "resolved": "https://registry.npmjs.org/depd/-/depd-2.0.0.tgz",
  "integrity": "sha512-g7nH6P6dyDioJogAAGprGpCtVImJhpPk/roCzdb3fIh61/s/nPsfR6onyMwkCAR/OlC3yBC0lESvUoQEAssIrw==",

-      "license": "MIT",
       "engines": {
         "node": ">= 0.8"
       }
  },
  "node_modules/diff": {
-      "version": "8.0.2",
-      "resolved": "https://registry.npmjs.org/diff/-/diff-8.0.2.tgz",
-      "integrity": "sha512-sSuxWU5j5SR9QQji/o2qMvqRNYRDOcBTgsJ/DeCf4iSN4gW+gNMXM7wFIP+fdXZxoNiAnHUTGjCr+TSWXdRDKg==",
-      "license": "BSD-3-Clause",

*      "version": "9.0.0",
*      "resolved": "https://registry.npmjs.org/diff/-/diff-9.0.0.tgz",
*      "integrity": "sha512-svtcdpS8CgJyqAjEQIXdb3OjhFVVYjzGAPO8WGCmRbrml64SPw/jJD4GoE98aR7r25A0XcgrK3F02yw9R/vhQw==",
         "engines": {
           "node": ">=0.3.1"
         }
  @@ -2099,7 +2058,6 @@
  "version": "1.0.1",
  "resolved": "https://registry.npmjs.org/dunder-proto/-/dunder-proto-1.0.1.tgz",
  "integrity": "sha512-KIN/nDJBQRcXw0MLVhZE9iQHmG68qAVIBg9CqmUYjmQIhgij9U5MFvrqkUL5FbtyyzZuOeOt0zdeRe4UY7ct+A==",

-      "license": "MIT",
         "dependencies": {
           "call-bind-apply-helpers": "^1.0.1",
           "es-errors": "^1.3.0",
  @@ -2112,14 +2070,12 @@
  "node_modules/ee-first": {
  "version": "1.1.1",
  "resolved": "https://registry.npmjs.org/ee-first/-/ee-first-1.1.1.tgz",
-      "integrity": "sha512-WMwm9LhRUo+WUaRN+vRuETqG89IgZphVSNkdFgeb6sS/E4OrDIN7t48CAewSHXc6C8lefD8KKfr5vY61brQlow==",
-      "license": "MIT"

*      "integrity": "sha512-WMwm9LhRUo+WUaRN+vRuETqG89IgZphVSNkdFgeb6sS/E4OrDIN7t48CAewSHXc6C8lefD8KKfr5vY61brQlow=="
  },
  "node_modules/encodeurl": {
  "version": "2.0.0",
  "resolved": "https://registry.npmjs.org/encodeurl/-/encodeurl-2.0.0.tgz",
  "integrity": "sha512-Q0n9HRi4m6JuGIV1eFlmvJB7ZEVxu93IrMyiMsGC0lrMJMWzRgx6WGquyfQgZVb31vhGgXnfmPNNXmxnOkRBrg==",

-      "license": "MIT",
         "engines": {
           "node": ">= 0.8"
         }
  @@ -2128,7 +2084,6 @@
  "version": "1.0.1",
  "resolved": "https://registry.npmjs.org/es-define-property/-/es-define-property-1.0.1.tgz",
  "integrity": "sha512-e3nRfgfUZ4rNGL232gUgX06QNyyez04KdjFrF+LTRoOXmrOgFKDg4BCdsjW8EnT69eqdYGmRpJwiPVYNrCaW3g==",
-      "license": "MIT",
         "engines": {
           "node": ">= 0.4"
         }
  @@ -2137,7 +2092,6 @@
  "version": "1.3.0",
  "resolved": "https://registry.npmjs.org/es-errors/-/es-errors-1.3.0.tgz",
  "integrity": "sha512-Zf5H2Kxt2xjTvbJvP2ZWLEICxA6j+hAmMzIlypy4xcBg1vKVnx89Wy0GbS+kf5cwCVFFzdCFh2XSCFNULS6csw==",
-      "license": "MIT",
         "engines": {
           "node": ">= 0.4"
         }
  @@ -2146,7 +2100,6 @@
  "version": "1.1.1",
  "resolved": "https://registry.npmjs.org/es-object-atoms/-/es-object-atoms-1.1.1.tgz",
  "integrity": "sha512-FGgH2h8zKNim9ljj7dankFPcICIK9Cp5bm+c2gQSYePhpaG5+esrLODihIorn+Pe6FGJzWhXQotPv73jTaldXA==",
-      "license": "MIT",
         "dependencies": {
           "es-errors": "^1.3.0"
         },
  @@ -2155,12 +2108,11 @@
  }
  },
  "node_modules/esbuild": {
-      "version": "0.25.8",
-      "resolved": "https://registry.npmjs.org/esbuild/-/esbuild-0.25.8.tgz",
-      "integrity": "sha512-vVC0USHGtMi8+R4Kz8rt6JhEWLxsv9Rnu/lGYbPR8u47B+DCBksq9JarW0zOO7bs37hyOK1l2/oqtbciutL5+Q==",

*      "version": "0.27.7",
*      "resolved": "https://registry.npmjs.org/esbuild/-/esbuild-0.27.7.tgz",
*      "integrity": "sha512-IxpibTjyVnmrIQo5aqNpCgoACA/dTKLTlhMHihVHhdkxKyPO1uBBthumT0rdHmcsk9uMonIWS0m4FljWzILh3w==",
       "dev": true,
       "hasInstallScript": true,

-      "license": "MIT",
         "bin": {
           "esbuild": "bin/esbuild"
         },
  @@ -2168,45 +2120,43 @@
  "node": ">=18"
  },
  "optionalDependencies": {
-        "@esbuild/aix-ppc64": "0.25.8",
-        "@esbuild/android-arm": "0.25.8",
-        "@esbuild/android-arm64": "0.25.8",
-        "@esbuild/android-x64": "0.25.8",
-        "@esbuild/darwin-arm64": "0.25.8",
-        "@esbuild/darwin-x64": "0.25.8",
-        "@esbuild/freebsd-arm64": "0.25.8",
-        "@esbuild/freebsd-x64": "0.25.8",
-        "@esbuild/linux-arm": "0.25.8",
-        "@esbuild/linux-arm64": "0.25.8",
-        "@esbuild/linux-ia32": "0.25.8",
-        "@esbuild/linux-loong64": "0.25.8",
-        "@esbuild/linux-mips64el": "0.25.8",
-        "@esbuild/linux-ppc64": "0.25.8",
-        "@esbuild/linux-riscv64": "0.25.8",
-        "@esbuild/linux-s390x": "0.25.8",
-        "@esbuild/linux-x64": "0.25.8",
-        "@esbuild/netbsd-arm64": "0.25.8",
-        "@esbuild/netbsd-x64": "0.25.8",
-        "@esbuild/openbsd-arm64": "0.25.8",
-        "@esbuild/openbsd-x64": "0.25.8",
-        "@esbuild/openharmony-arm64": "0.25.8",
-        "@esbuild/sunos-x64": "0.25.8",
-        "@esbuild/win32-arm64": "0.25.8",
-        "@esbuild/win32-ia32": "0.25.8",
-        "@esbuild/win32-x64": "0.25.8"

*        "@esbuild/aix-ppc64": "0.27.7",
*        "@esbuild/android-arm": "0.27.7",
*        "@esbuild/android-arm64": "0.27.7",
*        "@esbuild/android-x64": "0.27.7",
*        "@esbuild/darwin-arm64": "0.27.7",
*        "@esbuild/darwin-x64": "0.27.7",
*        "@esbuild/freebsd-arm64": "0.27.7",
*        "@esbuild/freebsd-x64": "0.27.7",
*        "@esbuild/linux-arm": "0.27.7",
*        "@esbuild/linux-arm64": "0.27.7",
*        "@esbuild/linux-ia32": "0.27.7",
*        "@esbuild/linux-loong64": "0.27.7",
*        "@esbuild/linux-mips64el": "0.27.7",
*        "@esbuild/linux-ppc64": "0.27.7",
*        "@esbuild/linux-riscv64": "0.27.7",
*        "@esbuild/linux-s390x": "0.27.7",
*        "@esbuild/linux-x64": "0.27.7",
*        "@esbuild/netbsd-arm64": "0.27.7",
*        "@esbuild/netbsd-x64": "0.27.7",
*        "@esbuild/openbsd-arm64": "0.27.7",
*        "@esbuild/openbsd-x64": "0.27.7",
*        "@esbuild/openharmony-arm64": "0.27.7",
*        "@esbuild/sunos-x64": "0.27.7",
*        "@esbuild/win32-arm64": "0.27.7",
*        "@esbuild/win32-ia32": "0.27.7",
*        "@esbuild/win32-x64": "0.27.7"
       }
  },
  "node_modules/escape-html": {
  "version": "1.0.3",
  "resolved": "https://registry.npmjs.org/escape-html/-/escape-html-1.0.3.tgz",

-      "integrity": "sha512-NiSupZ4OeuGwr68lGIeym/ksIZMJodUGOSCZ/FSnTxcrekbvqrgdUxlJOMpijaKZVjAJrWrGs/6Jy8OMuyj9ow==",
-      "license": "MIT"

*      "integrity": "sha512-NiSupZ4OeuGwr68lGIeym/ksIZMJodUGOSCZ/FSnTxcrekbvqrgdUxlJOMpijaKZVjAJrWrGs/6Jy8OMuyj9ow=="
  },
  "node_modules/etag": {
  "version": "1.8.1",
  "resolved": "https://registry.npmjs.org/etag/-/etag-1.8.1.tgz",
  "integrity": "sha512-aIL5Fx7mawVa300al2BnEE4iNvo1qETxLrPI/o05L7z6go7fCw1J6EQmbK4FmJ2AS7kgVF/KEZWufBfdClMcPg==",

-      "license": "MIT",
         "engines": {
           "node": ">= 0.6"
         }
  @@ -2215,7 +2165,6 @@
  "version": "3.0.7",
  "resolved": "https://registry.npmjs.org/eventsource/-/eventsource-3.0.7.tgz",
  "integrity": "sha512-CRT1WTyuQoD771GW56XEZFQ/ZoSfWid1alKGDYMmkt2yl8UXrVR4pspqWNEcqKvVIzg6PAltWjxcSSPrboA4iA==",
-      "license": "MIT",
         "dependencies": {
           "eventsource-parser": "^3.0.1"
         },
  @@ -2224,27 +2173,26 @@
  }
  },
  "node_modules/eventsource-parser": {
-      "version": "3.0.3",
-      "resolved": "https://registry.npmjs.org/eventsource-parser/-/eventsource-parser-3.0.3.tgz",
-      "integrity": "sha512-nVpZkTMM9rF6AQ9gPJpFsNAMt48wIzB5TQgiTLdHiuO8XEDhUgZEhqKlZWXbIzo9VmJ/HvysHqEaVeD5v9TPvA==",
-      "license": "MIT",

*      "version": "3.0.8",
*      "resolved": "https://registry.npmjs.org/eventsource-parser/-/eventsource-parser-3.0.8.tgz",
*      "integrity": "sha512-70QWGkr4snxr0OXLRWsFLeRBIRPuQOvt4s8QYjmUlmlkyTZkRqS7EDVRZtzU3TiyDbXSzaOeF0XUKy8PchzukQ==",
       "engines": {

-        "node": ">=20.0.0"

*        "node": ">=18.0.0"
       }
  },
  "node_modules/express": {

-      "version": "5.1.0",
-      "resolved": "https://registry.npmjs.org/express/-/express-5.1.0.tgz",
-      "integrity": "sha512-DT9ck5YIRU+8GYzzU5kT3eHGA5iL+1Zd0EutOmTE9Dtk+Tvuzd23VBU+ec7HPNSTxXYO55gPV/hq4pSBJDjFpA==",
-      "license": "MIT",

*      "version": "5.2.1",
*      "resolved": "https://registry.npmjs.org/express/-/express-5.2.1.tgz",
*      "integrity": "sha512-hIS4idWWai69NezIdRt2xFVofaF4j+6INOpJlVOLDO8zXGpUVEVzIYk12UUi2JzjEzWL3IOAxcTubgz9Po0yXw==",
       "dependencies": {
         "accepts": "^2.0.0",

-        "body-parser": "^2.2.0",

*        "body-parser": "^2.2.1",
         "content-disposition": "^1.0.0",
         "content-type": "^1.0.5",
         "cookie": "^0.7.1",
         "cookie-signature": "^1.2.1",
         "debug": "^4.4.0",
*        "depd": "^2.0.0",
           "encodeurl": "^2.0.0",
           "escape-html": "^1.0.3",
           "etag": "^1.8.1",
  @@ -2275,10 +2223,12 @@
  }
  },
  "node_modules/express-rate-limit": {

-      "version": "7.5.1",
-      "resolved": "https://registry.npmjs.org/express-rate-limit/-/express-rate-limit-7.5.1.tgz",
-      "integrity": "sha512-7iN8iPMDzOMHPUYllBEsQdWVB6fPDMPqwjBaFrgr4Jgr/+okjvzAy+UHlYYL/Vs0OsOrMkwS6PJDkFlJwoxUnw==",
-      "license": "MIT",

*      "version": "8.4.1",
*      "resolved": "https://registry.npmjs.org/express-rate-limit/-/express-rate-limit-8.4.1.tgz",
*      "integrity": "sha512-NGVYwQSAyEQgzxX1iCM978PP9AdO/hW93gMcF6ZwQCm+rFvLsBH6w4xcXWTcliS8La5EPRN3p9wzItqBwJrfNw==",
*      "dependencies": {
*        "ip-address": "10.1.0"
*      },
         "engines": {
           "node": ">= 16"
         },
  @@ -2292,28 +2242,52 @@
  "node_modules/fast-deep-equal": {
  "version": "3.1.3",
  "resolved": "https://registry.npmjs.org/fast-deep-equal/-/fast-deep-equal-3.1.3.tgz",

-      "integrity": "sha512-f3qQ9oQy9j2AhBe/H9VC91wLmKBCCU/gDOnKNAYG5hswO7BLKj09Hc5HYNz9cGI++xlpDCIgDaitVs03ATR84Q==",
-      "license": "MIT"

*      "integrity": "sha512-f3qQ9oQy9j2AhBe/H9VC91wLmKBCCU/gDOnKNAYG5hswO7BLKj09Hc5HYNz9cGI++xlpDCIgDaitVs03ATR84Q=="
  },

- "node_modules/fast-json-stable-stringify": {
-      "version": "2.1.0",
-      "resolved": "https://registry.npmjs.org/fast-json-stable-stringify/-/fast-json-stable-stringify-2.1.0.tgz",
-      "integrity": "sha512-lhd/wF+Lk98HZoTCtlVraHtfh5XYijIjalXck7saUtuanSDyLMxnHhSXEDJqHxD7msR8D0uCmqlkwjCV8xvwHw==",
-      "license": "MIT"

* "node_modules/fast-uri": {
*      "version": "3.1.0",
*      "resolved": "https://registry.npmjs.org/fast-uri/-/fast-uri-3.1.0.tgz",
*      "integrity": "sha512-iPeeDKJSWf4IEOasVVrknXpaBV0IApz/gp7S2bb7Z4Lljbl2MGJRqInZiUrQwV16cpzw/D3S5j5Julj/gT52AA==",
*      "funding": [
*        {
*          "type": "github",
*          "url": "https://github.com/sponsors/fastify"
*        },
*        {
*          "type": "opencollective",
*          "url": "https://opencollective.com/fastify"
*        }
*      ]
* },
* "node_modules/fast-xml-builder": {
*      "version": "1.1.5",
*      "resolved": "https://registry.npmjs.org/fast-xml-builder/-/fast-xml-builder-1.1.5.tgz",
*      "integrity": "sha512-4TJn/8FKLeslLAH3dnohXqE3QSoxkhvaMzepOIZytwJXZO69Bfz0HBdDHzOTOon6G59Zrk6VQ2bEiv1t61rfkA==",
*      "funding": [
*        {
*          "type": "github",
*          "url": "https://github.com/sponsors/NaturalIntelligence"
*        }
*      ],
*      "dependencies": {
*        "path-expression-matcher": "^1.1.3"
*      }
  },
  "node_modules/fast-xml-parser": {

-      "version": "5.2.5",
-      "resolved": "https://registry.npmjs.org/fast-xml-parser/-/fast-xml-parser-5.2.5.tgz",
-      "integrity": "sha512-pfX9uG9Ki0yekDHx2SiuRIyFdyAr1kMIMitPvb0YBo8SUfKvia7w7FIyd/l6av85pFYRhZscS75MwMnbvY+hcQ==",

*      "version": "5.7.2",
*      "resolved": "https://registry.npmjs.org/fast-xml-parser/-/fast-xml-parser-5.7.2.tgz",
*      "integrity": "sha512-P7oW7tLbYnhOLQk/Gv7cZgzgMPP/XN03K02/Jy6Y/NHzyIAIpxuZIM/YqAkfiXFPxA2CTm7NtCijK9EDu09u2w==",
       "funding": [
         {
           "type": "github",
           "url": "https://github.com/sponsors/NaturalIntelligence"
         }
       ],

-      "license": "MIT",
       "dependencies": {
-        "strnum": "^2.1.0"

*        "@nodable/entities": "^2.1.0",
*        "fast-xml-builder": "^1.1.5",
*        "path-expression-matcher": "^1.5.0",
*        "strnum": "^2.2.3"
         },
         "bin": {
           "fxparser": "src/cli/cli.js"
  @@ -2324,7 +2298,6 @@
  "resolved": "https://registry.npmjs.org/fill-range/-/fill-range-7.1.1.tgz",
  "integrity": "sha512-YsGpe3WHLK8ZYi4tWDg2Jy3ebRz2rXowDxnld4bkQB00cc/1Zw9AWnC0i9ztDJitivtQvaI9KaLyKrc+hBW0yg==",
  "dev": true,

-      "license": "MIT",
         "dependencies": {
           "to-regex-range": "^5.0.1"
         },
  @@ -2333,10 +2306,9 @@
  }
  },
  "node_modules/finalhandler": {
-      "version": "2.1.0",
-      "resolved": "https://registry.npmjs.org/finalhandler/-/finalhandler-2.1.0.tgz",
-      "integrity": "sha512-/t88Ty3d5JWQbWYgaOGCCYfXRwV1+be02WqYYlL6h0lEiUAMPM8o8qKGO01YIkOHzka2up08wvgYD0mDiI+q3Q==",
-      "license": "MIT",

*      "version": "2.1.1",
*      "resolved": "https://registry.npmjs.org/finalhandler/-/finalhandler-2.1.1.tgz",
*      "integrity": "sha512-S8KoZgRZN+a5rNwqTxlZZePjT/4cnm0ROV70LedRHZ0p8u9fRID0hJUZQpkKLzro8LfmC8sx23bY6tVNxv8pQA==",
         "dependencies": {
           "debug": "^4.4.0",
           "encodeurl": "^2.0.0",
  @@ -2346,14 +2318,17 @@
  "statuses": "^2.0.1"
  },
  "engines": {

-        "node": ">= 0.8"

*        "node": ">= 18.0.0"
*      },
*      "funding": {
*        "type": "opencollective",
*        "url": "https://opencollective.com/express"
       }
  },
  "node_modules/forwarded": {
  "version": "0.2.0",
  "resolved": "https://registry.npmjs.org/forwarded/-/forwarded-0.2.0.tgz",
  "integrity": "sha512-buRG0fpBtRHSTCOASe6hD258tEubFoRLb4ZNA6NxMVHNw2gOcwHo9wyablzMzOA5z9xA9L1KNjk/Nt6MT9aYow==",

-      "license": "MIT",
         "engines": {
           "node": ">= 0.6"
         }
  @@ -2362,7 +2337,6 @@
  "version": "2.0.0",
  "resolved": "https://registry.npmjs.org/fresh/-/fresh-2.0.0.tgz",
  "integrity": "sha512-Rx/WycZ60HOaqLKAi6cHRKKI7zxWbJ31MhntmtwMoaTeF7XFH9hhBp8vITaMidfljRQ6eYWCKkaTK+ykVJHP2A==",
-      "license": "MIT",
         "engines": {
           "node": ">= 0.8"
         }
  @@ -2373,7 +2347,6 @@
  "integrity": "sha512-5xoDfX+fL7faATnagmWPpbFtwh/R77WmMMqqHGS65C3vvB0YHrgF+B1YmZ3441tMj5n63k0212XNoJwzlhffQw==",
  "dev": true,
  "hasInstallScript": true,
-      "license": "MIT",
         "optional": true,
         "os": [
           "darwin"
  @@ -2386,7 +2359,6 @@
  "version": "1.1.2",
  "resolved": "https://registry.npmjs.org/function-bind/-/function-bind-1.1.2.tgz",
  "integrity": "sha512-7XHNxH7qX9xG5mIwxkhumTox/MIRNcOgDrxWsMt2pAr23WHp6MrRlN7FBSFpCpr+oVO0F744iUgR82nJMfG2SA==",
-      "license": "MIT",
         "funding": {
           "url": "https://github.com/sponsors/ljharb"
         }
  @@ -2395,7 +2367,6 @@
  "version": "1.3.0",
  "resolved": "https://registry.npmjs.org/get-intrinsic/-/get-intrinsic-1.3.0.tgz",
  "integrity": "sha512-9fSjSaos/fRIVIp+xSJlE6lfwhES7LNtKaCBIamHsjr2na1BiABJPo0mOjjz8GJDURarmCPGqaiVg5mfjb98CQ==",
-      "license": "MIT",
         "dependencies": {
           "call-bind-apply-helpers": "^1.0.2",
           "es-define-property": "^1.0.1",
  @@ -2419,7 +2390,6 @@
  "version": "1.0.1",
  "resolved": "https://registry.npmjs.org/get-proto/-/get-proto-1.0.1.tgz",
  "integrity": "sha512-sTSfBjoXBp89JvIKIefqw7U2CCebsc74kiY6awiGogKtoSGbgjYE/G/+l9sF3MWFPNc9IcoOC4ODfKHfxFmp0g==",
-      "license": "MIT",
         "dependencies": {
           "dunder-proto": "^1.0.1",
           "es-object-atoms": "^1.0.0"
  @@ -2429,11 +2399,10 @@
  }
  },
  "node_modules/get-tsconfig": {
-      "version": "4.10.1",
-      "resolved": "https://registry.npmjs.org/get-tsconfig/-/get-tsconfig-4.10.1.tgz",
-      "integrity": "sha512-auHyJ4AgMz7vgS8Hp3N6HXSmlMdUyhSUrfBF16w153rxtLIEOE+HGqaBppczZvnHLqQJfiHotCYpNhl0lUROFQ==",

*      "version": "4.14.0",
*      "resolved": "https://registry.npmjs.org/get-tsconfig/-/get-tsconfig-4.14.0.tgz",
*      "integrity": "sha512-yTb+8DXzDREzgvYmh6s9vHsSVCHeC0G3PI5bEXNBHtmshPnO+S5O7qgLEOn0I5QvMy6kpZN8K1NKGyilLb93wA==",
       "dev": true,

-      "license": "MIT",
         "dependencies": {
           "resolve-pkg-maps": "^1.0.0"
         },
  @@ -2446,7 +2415,6 @@
  "resolved": "https://registry.npmjs.org/glob-parent/-/glob-parent-5.1.2.tgz",
  "integrity": "sha512-AOIgSQCepiJYwP3ARnGx+5VnTu2HBYdzbGP45eLw1vr3zB3vZLeyed1sC9hnbcOc9/SrMyM5RPQrkGz4aS9Zow==",
  "dev": true,
-      "license": "ISC",
         "dependencies": {
           "is-glob": "^4.0.1"
         },
  @@ -2458,7 +2426,6 @@
  "version": "1.2.0",
  "resolved": "https://registry.npmjs.org/gopd/-/gopd-1.2.0.tgz",
  "integrity": "sha512-ZUKRh6/kUFoAiTAtTYPZJ3hw9wNxx+BIBOijnlG9PnrJsCcSjs1wyyD6vJpaYtgnzDrKYRSqf3OO6Rfa93xsRg==",
-      "license": "MIT",
         "engines": {
           "node": ">= 0.4"
         },
  @@ -2471,7 +2438,6 @@
  "resolved": "https://registry.npmjs.org/has-flag/-/has-flag-3.0.0.tgz",
  "integrity": "sha512-sKJf1+ceQBr4SMkvQnBDNDtf4TXpVhVGateu0t918bl30FnbE2m4vNLX+VWe/dpjlb+HugGYzW7uQXH98HPEYw==",
  "dev": true,
-      "license": "MIT",
         "engines": {
           "node": ">=4"
         }
  @@ -2480,7 +2446,6 @@
  "version": "1.1.0",
  "resolved": "https://registry.npmjs.org/has-symbols/-/has-symbols-1.1.0.tgz",
  "integrity": "sha512-1cDNdwJ2Jaohmb3sg4OmKaMBwuC48sYni5HUw2DvsC8LjGTLK9h+eb1X6RyuOHe4hT0ULCW68iomhjUoKUqlPQ==",
-      "license": "MIT",
         "engines": {
           "node": ">= 0.4"
         },
  @@ -2489,10 +2454,9 @@
  }
  },
  "node_modules/hasown": {
-      "version": "2.0.2",
-      "resolved": "https://registry.npmjs.org/hasown/-/hasown-2.0.2.tgz",
-      "integrity": "sha512-0hJU9SCPvmMzIBdZFqNPXWa6dqh7WdH0cII9y+CyS8rG3nL48Bclra9HmKhVVUHyPWNH5Y7xDwAB7bfgSjkUMQ==",
-      "license": "MIT",

*      "version": "2.0.3",
*      "resolved": "https://registry.npmjs.org/hasown/-/hasown-2.0.3.tgz",
*      "integrity": "sha512-ej4AhfhfL2Q2zpMmLo7U1Uv9+PyhIZpgQLGT1F9miIGmiCJIoCgSmczFdrc97mWT4kVY72KA+WnnhJ5pghSvSg==",
         "dependencies": {
           "function-bind": "^1.1.2"
         },
  @@ -2500,61 +2464,71 @@
  "node": ">= 0.4"
  }
  },

- "node_modules/http-errors": {
-      "version": "2.0.0",
-      "resolved": "https://registry.npmjs.org/http-errors/-/http-errors-2.0.0.tgz",
-      "integrity": "sha512-FtwrG/euBzaEjYeRqOgly7G0qviiXoJWnvEH2Z1plBdXgbyjv34pHTSb9zoeHMyDy33+DWy5Wt9Wo+TURtOYSQ==",
-      "license": "MIT",
-      "dependencies": {
-        "depd": "2.0.0",
-        "inherits": "2.0.4",
-        "setprototypeof": "1.2.0",
-        "statuses": "2.0.1",
-        "toidentifier": "1.0.1"
-      },

* "node_modules/hono": {
*      "version": "4.12.15",
*      "resolved": "https://registry.npmjs.org/hono/-/hono-4.12.15.tgz",
*      "integrity": "sha512-qM0jDhFEaCBb4TxoW7f53Qrpv9RBiayUHo0S52JudprkhvpjIrGoU1mnnr29Fvd1U335ZFPZQY1wlkqgfGXyLg==",
       "engines": {

-        "node": ">= 0.8"

*        "node": ">=16.9.0"
       }
  },

- "node_modules/http-errors/node_modules/statuses": {

* "node_modules/http-errors": {
  "version": "2.0.1",

-      "resolved": "https://registry.npmjs.org/statuses/-/statuses-2.0.1.tgz",
-      "integrity": "sha512-RwNA9Z/7PrK06rYLIzFMlaF+l73iwpzsqRIFgbMLbTcLD6cOao82TaWefPXQvB2fOC4AjuYSEndS7N/mTCbkdQ==",
-      "license": "MIT",

*      "resolved": "https://registry.npmjs.org/http-errors/-/http-errors-2.0.1.tgz",
*      "integrity": "sha512-4FbRdAX+bSdmo4AUFuS0WNiPz8NgFt+r8ThgNWmlrjQjt1Q7ZR9+zTlce2859x4KSXrwIsaeTqDoKQmtP8pLmQ==",
*      "dependencies": {
*        "depd": "~2.0.0",
*        "inherits": "~2.0.4",
*        "setprototypeof": "~1.2.0",
*        "statuses": "~2.0.2",
*        "toidentifier": "~1.0.1"
*      },
       "engines": {
         "node": ">= 0.8"
*      },
*      "funding": {
*        "type": "opencollective",
*        "url": "https://opencollective.com/express"
       }
  },
  "node_modules/iconv-lite": {

-      "version": "0.6.3",
-      "resolved": "https://registry.npmjs.org/iconv-lite/-/iconv-lite-0.6.3.tgz",
-      "integrity": "sha512-4fCk79wshMdzMp2rH06qWrJE4iolqLhCUH+OiuIgU++RB0+94NlDL81atO7GX55uUKueo0txHNtvEyI6D7WdMw==",
-      "license": "MIT",

*      "version": "0.7.2",
*      "resolved": "https://registry.npmjs.org/iconv-lite/-/iconv-lite-0.7.2.tgz",
*      "integrity": "sha512-im9DjEDQ55s9fL4EYzOAv0yMqmMBSZp6G0VvFyTMPKWxiSBHUj9NW/qqLmXUwXrrM7AvqSlTCfvqRb0cM8yYqw==",
       "dependencies": {
         "safer-buffer": ">= 2.1.2 < 3.0.0"
       },
       "engines": {
         "node": ">=0.10.0"
*      },
*      "funding": {
*        "type": "opencollective",
*        "url": "https://opencollective.com/express"
       }
  },
  "node_modules/ignore-by-default": {
  "version": "1.0.1",
  "resolved": "https://registry.npmjs.org/ignore-by-default/-/ignore-by-default-1.0.1.tgz",
  "integrity": "sha512-Ius2VYcGNk7T90CppJqcIkS5ooHUZyIQK+ClZfMfMNFEF9VSE73Fq+906u/CWu92x4gzZMWOwfFYckPObzdEbA==",

-      "dev": true,
-      "license": "ISC"

*      "dev": true
  },
  "node_modules/inherits": {
  "version": "2.0.4",
  "resolved": "https://registry.npmjs.org/inherits/-/inherits-2.0.4.tgz",

-      "integrity": "sha512-k/vGaX4/Yla3WzyMCvTQOXYeIHvqOKtnqBduzTHpzpQZzAskKMhZ2K+EnBiSM9zGSoIFeMpXKxa4dYeZIQqewQ==",
-      "license": "ISC"

*      "integrity": "sha512-k/vGaX4/Yla3WzyMCvTQOXYeIHvqOKtnqBduzTHpzpQZzAskKMhZ2K+EnBiSM9zGSoIFeMpXKxa4dYeZIQqewQ=="
* },
* "node_modules/ip-address": {
*      "version": "10.1.0",
*      "resolved": "https://registry.npmjs.org/ip-address/-/ip-address-10.1.0.tgz",
*      "integrity": "sha512-XXADHxXmvT9+CRxhXg56LJovE+bmWnEWB78LB83VZTprKTmaC5QfruXocxzTZ2Kl0DNwKuBdlIhjL8LeY8Sf8Q==",
*      "engines": {
*        "node": ">= 12"
*      }
  },
  "node_modules/ipaddr.js": {
  "version": "1.9.1",
  "resolved": "https://registry.npmjs.org/ipaddr.js/-/ipaddr.js-1.9.1.tgz",
  "integrity": "sha512-0KI/607xoxSToH7GjN1FfSbLoU0+btTicjsQSWQlh/hZykN8KpmMf7uYwPW3R+akZ6R/w18ZlXSHBYXiYUPO3g==",

-      "license": "MIT",
         "engines": {
           "node": ">= 0.10"
         }
  @@ -2564,7 +2538,6 @@
  "resolved": "https://registry.npmjs.org/is-binary-path/-/is-binary-path-2.1.0.tgz",
  "integrity": "sha512-ZMERYes6pDydyuGidse7OsHxtbI7WVeUEozgR/g7rd0xUimYNlvZRE/K2MgZTjWy725IfelLeVcEM97mmtRGXw==",
  "dev": true,
-      "license": "MIT",
         "dependencies": {
           "binary-extensions": "^2.0.0"
         },
  @@ -2577,7 +2550,6 @@
  "resolved": "https://registry.npmjs.org/is-extglob/-/is-extglob-2.1.1.tgz",
  "integrity": "sha512-SbKbANkN603Vi4jEZv49LeVJMn4yGwsbzZworEoyEiutsN3nJYdbO36zfhGJ6QEDpOZIFkDtnq5JRxmvl3jsoQ==",
  "dev": true,
-      "license": "MIT",
         "engines": {
           "node": ">=0.10.0"
         }
  @@ -2587,7 +2559,6 @@
  "resolved": "https://registry.npmjs.org/is-glob/-/is-glob-4.0.3.tgz",
  "integrity": "sha512-xelSayHH36ZgE7ZWhli7pW34hNbNl8Ojv5KVmkJD4hBdD3th8Tfk9vYasLM+mXWOZhFkgZfxhLSnrwRr4elSSg==",
  "dev": true,
-      "license": "MIT",
         "dependencies": {
           "is-extglob": "^2.1.1"
         },
  @@ -2600,7 +2571,6 @@
  "resolved": "https://registry.npmjs.org/is-number/-/is-number-7.0.0.tgz",
  "integrity": "sha512-41Cifkg6e8TylSpdtTpeLVMqvSBEVzTttHvERD741+pnZ8ANv0004MRL43QKPDlK9cGvNp6NZWZUBlbGXYxxng==",
  "dev": true,
-      "license": "MIT",
         "engines": {
           "node": ">=0.12.0"
         }
  @@ -2608,26 +2578,35 @@
  "node_modules/is-promise": {
  "version": "4.0.0",
  "resolved": "https://registry.npmjs.org/is-promise/-/is-promise-4.0.0.tgz",
-      "integrity": "sha512-hvpoI6korhJMnej285dSg6nu1+e6uxs7zG3BYAm5byqDsgJNWwxzM6z6iZiAgQR4TJ30JmBTOwqZUw3WlyH3AQ==",
-      "license": "MIT"

*      "integrity": "sha512-hvpoI6korhJMnej285dSg6nu1+e6uxs7zG3BYAm5byqDsgJNWwxzM6z6iZiAgQR4TJ30JmBTOwqZUw3WlyH3AQ=="
  },
  "node_modules/isexe": {
  "version": "2.0.0",
  "resolved": "https://registry.npmjs.org/isexe/-/isexe-2.0.0.tgz",

-      "integrity": "sha512-RHxMLp9lnKHGHRng9QFhRCMbYAcVpn69smSGcq3f36xjgVVWThj4qqLbTLlq7Ssj8B+fIQ1EuCEGI2lKsyQeIw==",
-      "license": "ISC"

*      "integrity": "sha512-RHxMLp9lnKHGHRng9QFhRCMbYAcVpn69smSGcq3f36xjgVVWThj4qqLbTLlq7Ssj8B+fIQ1EuCEGI2lKsyQeIw=="
* },
* "node_modules/jose": {
*      "version": "6.2.3",
*      "resolved": "https://registry.npmjs.org/jose/-/jose-6.2.3.tgz",
*      "integrity": "sha512-YYVDInQKFJfR/xa3ojUTl8c2KoTwiL1R5Wg9YCydwH0x0B9grbzlg5HC7mMjCtUJjbQ/YnGEZIhI5tCgfTb4Hw==",
*      "funding": {
*        "url": "https://github.com/sponsors/panva"
*      }
  },
  "node_modules/json-schema-traverse": {

-      "version": "0.4.1",
-      "resolved": "https://registry.npmjs.org/json-schema-traverse/-/json-schema-traverse-0.4.1.tgz",
-      "integrity": "sha512-xbbCH5dCYU5T8LcEhhuh7HJ88HXuW3qsI3Y0zOZFKfZEHcpWiHU/Jxzk629Brsab/mMiHQti9wMP+845RPe3Vg==",
-      "license": "MIT"

*      "version": "1.0.0",
*      "resolved": "https://registry.npmjs.org/json-schema-traverse/-/json-schema-traverse-1.0.0.tgz",
*      "integrity": "sha512-NM8/P9n3XjXhIZn1lLhkFaACTOURQXjWhV4BA/RnOv8xvgqtqpAX9IO4mRQxSx1Rlo4tqzeqb0sOlruaOy3dug=="
* },
* "node_modules/json-schema-typed": {
*      "version": "8.0.2",
*      "resolved": "https://registry.npmjs.org/json-schema-typed/-/json-schema-typed-8.0.2.tgz",
*      "integrity": "sha512-fQhoXdcvc3V28x7C7BMs4P5+kNlgUURe2jmUT1T//oBRMDrqy1QPelJimwZGo7Hg9VPV3EQV5Bnq4hbFy2vetA=="
  },
  "node_modules/math-intrinsics": {
  "version": "1.1.0",
  "resolved": "https://registry.npmjs.org/math-intrinsics/-/math-intrinsics-1.1.0.tgz",
  "integrity": "sha512-/IXtbwEk5HTPyEwyKX6hGkYXxM9nbj64B+ilVJnC/R6B0pH5G4V3b0pVbL7DBj4tkhBAppbQUlf6F6Xl9LHu1g==",

-      "license": "MIT",
         "engines": {
           "node": ">= 0.4"
         }
  @@ -2636,7 +2615,6 @@
  "version": "1.1.0",
  "resolved": "https://registry.npmjs.org/media-typer/-/media-typer-1.1.0.tgz",
  "integrity": "sha512-aisnrDP4GNe06UcKFnV5bfMNPBUw4jsLGaWwWfnH3v02GnBuXX2MCVn5RbrWo0j3pczUilYblq7fQ7Nw2t5XKw==",
-      "license": "MIT",
         "engines": {
           "node": ">= 0.8"
         }
  @@ -2645,7 +2623,6 @@
  "version": "2.0.0",
  "resolved": "https://registry.npmjs.org/merge-descriptors/-/merge-descriptors-2.0.0.tgz",
  "integrity": "sha512-Snk314V5ayFLhp3fkUREub6WtjBfPdCPY1Ln8/8munuLuiYhsABgBVWsozAG+MWMbVEvcdcpbi9R7ww22l9Q3g==",
-      "license": "MIT",
         "engines": {
           "node": ">=18"
         },
  @@ -2657,62 +2634,63 @@
  "version": "1.54.0",
  "resolved": "https://registry.npmjs.org/mime-db/-/mime-db-1.54.0.tgz",
  "integrity": "sha512-aU5EJuIN2WDemCcAp2vFBfp/m4EAhWJnUNSSw0ixs7/kXbd6Pg64EmwJkNdFhB8aWt1sH2CTXrLxo/iAGV3oPQ==",
-      "license": "MIT",
       "engines": {
         "node": ">= 0.6"
       }
  },
  "node_modules/mime-types": {
-      "version": "3.0.1",
-      "resolved": "https://registry.npmjs.org/mime-types/-/mime-types-3.0.1.tgz",
-      "integrity": "sha512-xRc4oEhT6eaBpU1XF7AjpOFD+xQmXNB5OVKwp4tqCuBpHLS/ZbBDrc07mYTDqVMg6PfxUjjNp85O6Cd2Z/5HWA==",
-      "license": "MIT",

*      "version": "3.0.2",
*      "resolved": "https://registry.npmjs.org/mime-types/-/mime-types-3.0.2.tgz",
*      "integrity": "sha512-Lbgzdk0h4juoQ9fCKXW4by0UJqj+nOOrI9MJ1sSj4nI8aI2eo1qmvQEie4VD1glsS250n15LsWsYtCugiStS5A==",
       "dependencies": {
         "mime-db": "^1.54.0"
       },
       "engines": {

-        "node": ">= 0.6"

*        "node": ">=18"
*      },
*      "funding": {
*        "type": "opencollective",
*        "url": "https://opencollective.com/express"
       }
  },
  "node_modules/minimatch": {

-      "version": "3.1.2",
-      "resolved": "https://registry.npmjs.org/minimatch/-/minimatch-3.1.2.tgz",
-      "integrity": "sha512-J7p63hRiAjw1NDEww1W7i37+ByIrOWO5XQQAzZ3VOcL0PNybwpfmV/N05zFAzwQ9USyEcX6t3UO+K5aqBQOIHw==",

*      "version": "10.2.5",
*      "resolved": "https://registry.npmjs.org/minimatch/-/minimatch-10.2.5.tgz",
*      "integrity": "sha512-MULkVLfKGYDFYejP07QOurDLLQpcjk7Fw+7jXS2R2czRQzR56yHRveU5NDJEOviH+hETZKSkIk5c+T23GjFUMg==",
       "dev": true,

-      "license": "ISC",
       "dependencies": {
-        "brace-expansion": "^1.1.7"

*        "brace-expansion": "^5.0.5"
       },
       "engines": {

-        "node": "*"

*        "node": "18 || 20 || >=22"
*      },
*      "funding": {
*        "url": "https://github.com/sponsors/isaacs"
       }
  },
  "node_modules/ms": {
  "version": "2.1.3",
  "resolved": "https://registry.npmjs.org/ms/-/ms-2.1.3.tgz",

-      "integrity": "sha512-6FlzubTLZG3J2a/NVCAleEhjzq5oxgHyaCU9yYXvcLsvoVaHJq/s5xXI6/XXP6tz7R9xAOtHnSO/tXtF3WRTlA==",
-      "license": "MIT"

*      "integrity": "sha512-6FlzubTLZG3J2a/NVCAleEhjzq5oxgHyaCU9yYXvcLsvoVaHJq/s5xXI6/XXP6tz7R9xAOtHnSO/tXtF3WRTlA=="
  },
  "node_modules/negotiator": {
  "version": "1.0.0",
  "resolved": "https://registry.npmjs.org/negotiator/-/negotiator-1.0.0.tgz",
  "integrity": "sha512-8Ofs/AUQh8MaEcrlq5xOX0CQ9ypTF5dl78mjlMNfOK08fzpgTHQRQPBxcPlEtIw0yRpws+Zo/3r+5WRby7u3Gg==",

-      "license": "MIT",
       "engines": {
         "node": ">= 0.6"
       }
  },
  "node_modules/nodemon": {
-      "version": "3.1.10",
-      "resolved": "https://registry.npmjs.org/nodemon/-/nodemon-3.1.10.tgz",
-      "integrity": "sha512-WDjw3pJ0/0jMFmyNDp3gvY2YizjLmmOUQo6DEBY+JgdvW/yQ9mEeSw6H5ythl5Ny2ytb7f9C2nIbjSxMNzbJXw==",

*      "version": "3.1.14",
*      "resolved": "https://registry.npmjs.org/nodemon/-/nodemon-3.1.14.tgz",
*      "integrity": "sha512-jakjZi93UtB3jHMWsXL68FXSAosbLfY0In5gtKq3niLSkrWznrVBzXFNOEMJUfc9+Ke7SHWoAZsiMkNP3vq6Jw==",
       "dev": true,

-      "license": "MIT",
       "dependencies": {
         "chokidar": "^3.5.2",
         "debug": "^4",
         "ignore-by-default": "^1.0.1",
-        "minimatch": "^3.1.2",

*        "minimatch": "^10.2.1",
           "pstree.remy": "^1.1.8",
           "semver": "^7.5.3",
           "simple-update-notifier": "^2.0.0",
  @@ -2736,7 +2714,6 @@
  "resolved": "https://registry.npmjs.org/normalize-path/-/normalize-path-3.0.0.tgz",
  "integrity": "sha512-6eZs5Ls3WtCisHWp9S2GUy8dqkpGi4BVSz3GaqiE6ezub0512ESztXUwUB6C6IKbQkY2Pnb/mD4WYojCRwcwLA==",
  "dev": true,

-      "license": "MIT",
         "engines": {
           "node": ">=0.10.0"
         }
  @@ -2745,7 +2722,6 @@
  "version": "4.1.1",
  "resolved": "https://registry.npmjs.org/object-assign/-/object-assign-4.1.1.tgz",
  "integrity": "sha512-rJgTQnkUnH1sFw8yT6VSU3zD3sWmu6sZhIseY8VX+GRu3P6F7Fu+JNDoXfklElbLJSnc3FUQHVe4cU5hj+BcUg==",
-      "license": "MIT",
         "engines": {
           "node": ">=0.10.0"
         }
  @@ -2754,7 +2730,6 @@
  "version": "1.13.4",
  "resolved": "https://registry.npmjs.org/object-inspect/-/object-inspect-1.13.4.tgz",
  "integrity": "sha512-W67iLl4J2EXEGTbfeHCffrjDfitvLANg0UlX3wFUUSTx92KXRFegMHUVgSqE+wvhAbi4WqjGg9czysTV2Epbew==",
-      "license": "MIT",
         "engines": {
           "node": ">= 0.4"
         },
  @@ -2766,7 +2741,6 @@
  "version": "2.4.1",
  "resolved": "https://registry.npmjs.org/on-finished/-/on-finished-2.4.1.tgz",
  "integrity": "sha512-oVlzkg3ENAhCk2zdv7IJwd/QUD4z2RxRwpkcGY8psCVcCYZNq4wYnVWALHM+brtuJjePWiYF/ClmuDr8Ch5+kg==",
-      "license": "MIT",
         "dependencies": {
           "ee-first": "1.1.1"
         },
  @@ -2778,7 +2752,6 @@
  "version": "1.4.0",
  "resolved": "https://registry.npmjs.org/once/-/once-1.4.0.tgz",
  "integrity": "sha512-lNaJgI+2Q5URQBkccEKHTQOPaXdUxnZZElQTZY0MFUAuaEqe1E+Nyvgdz/aIyNi6Z9MzO5dv1H8n58/GELp3+w==",
-      "license": "ISC",
         "dependencies": {
           "wrappy": "1"
         }
  @@ -2787,35 +2760,46 @@
  "version": "1.3.3",
  "resolved": "https://registry.npmjs.org/parseurl/-/parseurl-1.3.3.tgz",
  "integrity": "sha512-CiyeOxFT/JZyN5m0z9PfXw4SCBJ6Sygz1Dpl0wqjlhDEGGBP1GnsUVEL0p63hoG1fcj3fHynXi9NYO4nWOL+qQ==",
-      "license": "MIT",
       "engines": {
         "node": ">= 0.8"
       }
  },

* "node_modules/path-expression-matcher": {
*      "version": "1.5.0",
*      "resolved": "https://registry.npmjs.org/path-expression-matcher/-/path-expression-matcher-1.5.0.tgz",
*      "integrity": "sha512-cbrerZV+6rvdQrrD+iGMcZFEiiSrbv9Tfdkvnusy6y0x0GKBXREFg/Y65GhIfm0tnLntThhzCnfKwp1WRjeCyQ==",
*      "funding": [
*        {
*          "type": "github",
*          "url": "https://github.com/sponsors/NaturalIntelligence"
*        }
*      ],
*      "engines": {
*        "node": ">=14.0.0"
*      }
* },
  "node_modules/path-key": {
  "version": "3.1.1",
  "resolved": "https://registry.npmjs.org/path-key/-/path-key-3.1.1.tgz",
  "integrity": "sha512-ojmeN0qd+y0jszEtoY48r0Peq5dwMEkIlCOu6Q5f41lfkswXuKtYrhgoTpLnyIcHm24Uhqx+5Tqm2InSwLhE6Q==",

-      "license": "MIT",
       "engines": {
         "node": ">=8"
       }
  },
  "node_modules/path-to-regexp": {
-      "version": "8.2.0",
-      "resolved": "https://registry.npmjs.org/path-to-regexp/-/path-to-regexp-8.2.0.tgz",
-      "integrity": "sha512-TdrF7fW9Rphjq4RjrW0Kp2AW0Ahwu9sRGTkS6bvDi0SCwZlEZYmcfDbEsTz8RVk0EHIS/Vd1bv3JhG+1xZuAyQ==",
-      "license": "MIT",
-      "engines": {
-        "node": ">=16"

*      "version": "8.4.2",
*      "resolved": "https://registry.npmjs.org/path-to-regexp/-/path-to-regexp-8.4.2.tgz",
*      "integrity": "sha512-qRcuIdP69NPm4qbACK+aDogI5CBDMi1jKe0ry5rSQJz8JVLsC7jV8XpiJjGRLLol3N+R5ihGYcrPLTno6pAdBA==",
*      "funding": {
*        "type": "opencollective",
*        "url": "https://opencollective.com/express"
       }
  },
  "node_modules/picomatch": {

-      "version": "2.3.1",
-      "resolved": "https://registry.npmjs.org/picomatch/-/picomatch-2.3.1.tgz",
-      "integrity": "sha512-JU3teHTNjmE2VCGFzuY8EXzCDVwEqB2a8fsIvwaStHhAWJEeVd1o1QD80CU6+ZdEXXSLbSsuLwJjkCBWqRQUVA==",

*      "version": "2.3.2",
*      "resolved": "https://registry.npmjs.org/picomatch/-/picomatch-2.3.2.tgz",
*      "integrity": "sha512-V7+vQEJ06Z+c5tSye8S+nHUfI51xoXIXjHQ99cQtKUkQqqO1kO/KCJUfZXuB47h/YBlDhah2H3hdUGXn8ie0oA==",
       "dev": true,

-      "license": "MIT",
         "engines": {
           "node": ">=8.6"
         },
  @@ -2824,10 +2808,9 @@
  }
  },
  "node_modules/pkce-challenge": {
-      "version": "5.0.0",
-      "resolved": "https://registry.npmjs.org/pkce-challenge/-/pkce-challenge-5.0.0.tgz",
-      "integrity": "sha512-ueGLflrrnvwB3xuo/uGob5pd5FN7l0MsLf0Z87o/UQmRtwjvfylfc9MurIxRAWywCYTgrvpXBcqjV4OfCYGCIQ==",
-      "license": "MIT",

*      "version": "5.0.1",
*      "resolved": "https://registry.npmjs.org/pkce-challenge/-/pkce-challenge-5.0.1.tgz",
*      "integrity": "sha512-wQ0b/W4Fr01qtpHlqSqspcj3EhBvimsdh0KlHhH8HRZnMsEa0ea2fTULOXOS9ccQr3om+GcGRk4e+isrZWV8qQ==",
         "engines": {
           "node": ">=16.20.0"
         }
  @@ -2836,7 +2819,6 @@
  "version": "2.0.7",
  "resolved": "https://registry.npmjs.org/proxy-addr/-/proxy-addr-2.0.7.tgz",
  "integrity": "sha512-llQsMLSUDUPT44jdrU/O37qlnifitDP+ZwrmmZcoSKyLKvtZxpyV0n2/bD/N4tBAAZ/gJEdZU7KMraoK1+XYAg==",

-      "license": "MIT",
         "dependencies": {
           "forwarded": "0.2.0",
           "ipaddr.js": "1.9.1"
  @@ -2849,23 +2831,12 @@
  "version": "1.1.8",
  "resolved": "https://registry.npmjs.org/pstree.remy/-/pstree.remy-1.1.8.tgz",
  "integrity": "sha512-77DZwxQmxKnu3aR542U+X8FypNzbfJ+C5XQDk3uWjWxn6151aIMGthWYRXTqT1E5oJvg+ljaa2OJi+VfvCOQ8w==",
-      "dev": true,
-      "license": "MIT"
- },
- "node_modules/punycode": {
-      "version": "2.3.1",
-      "resolved": "https://registry.npmjs.org/punycode/-/punycode-2.3.1.tgz",
-      "integrity": "sha512-vYt7UD1U9Wg6138shLtLOvdAu+8DsC/ilFtEVHcH+wydcSpNE20AfSOduf6MkRFahL5FY7X1oU7nKVZFtfq8Fg==",
-      "license": "MIT",
-      "engines": {
-        "node": ">=6"
-      }

*      "dev": true
  },
  "node_modules/qs": {

-      "version": "6.14.0",
-      "resolved": "https://registry.npmjs.org/qs/-/qs-6.14.0.tgz",
-      "integrity": "sha512-YWWTjgABSKcvs/nWBi9PycY/JiPJqOD4JA6o9Sej2AtvSGarXxKC3OQSk4pAarbdQlKAh5D4FCQkJNkW+GAn3w==",
-      "license": "BSD-3-Clause",

*      "version": "6.15.1",
*      "resolved": "https://registry.npmjs.org/qs/-/qs-6.15.1.tgz",
*      "integrity": "sha512-6YHEFRL9mfgcAvql/XhwTvf5jKcOiiupt2FiJxHkiX1z4j7WL8J/jRHYLluORvc1XxB5rV20KoeK00gVJamspg==",
         "dependencies": {
           "side-channel": "^1.1.0"
         },
  @@ -2880,24 +2851,22 @@
  "version": "1.2.1",
  "resolved": "https://registry.npmjs.org/range-parser/-/range-parser-1.2.1.tgz",
  "integrity": "sha512-Hrgsx+orqoygnmhFbKaHE6c296J+HTAQXoxEF6gNupROmmGJRoyzfG3ccAveqCBrwr/2yxQ5BVd/GTl5agOwSg==",

-      "license": "MIT",
       "engines": {
         "node": ">= 0.6"
       }
  },
  "node_modules/raw-body": {
-      "version": "3.0.0",
-      "resolved": "https://registry.npmjs.org/raw-body/-/raw-body-3.0.0.tgz",
-      "integrity": "sha512-RmkhL8CAyCRPXCE28MMH0z2PNWQBNk2Q09ZdxM9IOOXwxwZbN+qbWaatPkdkWIKL2ZVDImrN/pK5HTRz2PcS4g==",
-      "license": "MIT",

*      "version": "3.0.2",
*      "resolved": "https://registry.npmjs.org/raw-body/-/raw-body-3.0.2.tgz",
*      "integrity": "sha512-K5zQjDllxWkf7Z5xJdV0/B0WTNqx6vxG70zJE4N0kBs4LovmEYWJzQGxC9bS9RAKu3bgM40lrd5zoLJ12MQ5BA==",
       "dependencies": {

-        "bytes": "3.1.2",
-        "http-errors": "2.0.0",
-        "iconv-lite": "0.6.3",
-        "unpipe": "1.0.0"

*        "bytes": "~3.1.2",
*        "http-errors": "~2.0.1",
*        "iconv-lite": "~0.7.0",
*        "unpipe": "~1.0.0"
       },
       "engines": {

-        "node": ">= 0.8"

*        "node": ">= 0.10"
         }
       },
       "node_modules/readdirp": {
  @@ -2905,7 +2874,6 @@
  "resolved": "https://registry.npmjs.org/readdirp/-/readdirp-3.6.0.tgz",
  "integrity": "sha512-hOS089on8RduqdbhvQ5Z37A0ESjsqz6qnRcffsMU3495FuTdqSm+7bhJ29JvIOsBDEEnan5DPu9t3To9VRlMzA==",
  "dev": true,

-      "license": "MIT",
         "dependencies": {
           "picomatch": "^2.2.1"
         },
  @@ -2913,12 +2881,19 @@
  "node": ">=8.10.0"
  }
  },

* "node_modules/require-from-string": {
*      "version": "2.0.2",
*      "resolved": "https://registry.npmjs.org/require-from-string/-/require-from-string-2.0.2.tgz",
*      "integrity": "sha512-Xf0nWe6RseziFMu+Ap9biiUbmplq6S9/p+7w7YXP/JBHhrUDDUhwa+vANyubuqfZWTveU//DYVGsDG7RKL/vEw==",
*      "engines": {
*        "node": ">=0.10.0"
*      }
* },
  "node_modules/resolve-pkg-maps": {
  "version": "1.0.0",
  "resolved": "https://registry.npmjs.org/resolve-pkg-maps/-/resolve-pkg-maps-1.0.0.tgz",
  "integrity": "sha512-seS2Tj26TBVOC2NIc2rOe2y2ZO7efxITtLZcGSOnHHNOQ7CkiUBfw0Iw2ck6xkIhPwLhKNLS8BO+hEpngQlqzw==",
  "dev": true,

-      "license": "MIT",
         "funding": {
           "url": "https://github.com/privatenumber/resolve-pkg-maps?sponsor=1"
         }
  @@ -2927,7 +2902,6 @@
  "version": "2.2.0",
  "resolved": "https://registry.npmjs.org/router/-/router-2.2.0.tgz",
  "integrity": "sha512-nLTrUKm2UyiL7rlhapu/Zl45FwNgkZGaCpZbIHajDYgwlJCOzLSk+cIPAnsEqV955GjILJnKbdQC1nVPz+gAYQ==",
-      "license": "MIT",
         "dependencies": {
           "debug": "^4.4.0",
           "depd": "^2.0.0",
  @@ -2939,38 +2913,16 @@
  "node": ">= 18"
  }
  },
- "node_modules/safe-buffer": {
-      "version": "5.2.1",
-      "resolved": "https://registry.npmjs.org/safe-buffer/-/safe-buffer-5.2.1.tgz",
-      "integrity": "sha512-rp3So07KcdmmKbGvgaNxQSJr7bGVSVk5S9Eq1F+ppbRo70+YeaDxkw5Dd8NPN+GD6bjnYm2VuPuCXmpuYvmCXQ==",
-      "funding": [
-        {
-          "type": "github",
-          "url": "https://github.com/sponsors/feross"
-        },
-        {
-          "type": "patreon",
-          "url": "https://www.patreon.com/feross"
-        },
-        {
-          "type": "consulting",
-          "url": "https://feross.org/support"
-        }
-      ],
-      "license": "MIT"
- },
  "node_modules/safer-buffer": {
  "version": "2.1.2",
  "resolved": "https://registry.npmjs.org/safer-buffer/-/safer-buffer-2.1.2.tgz",
-      "integrity": "sha512-YZo3K82SD7Riyi0E1EQPojLz7kpepnSQI9IyPbHHg1XXXevb5dJI7tpyN2ADxGcQbHG7vcyRHk0cbwqcQriUtg==",
-      "license": "MIT"

*      "integrity": "sha512-YZo3K82SD7Riyi0E1EQPojLz7kpepnSQI9IyPbHHg1XXXevb5dJI7tpyN2ADxGcQbHG7vcyRHk0cbwqcQriUtg=="
  },
  "node_modules/semver": {

-      "version": "7.7.2",
-      "resolved": "https://registry.npmjs.org/semver/-/semver-7.7.2.tgz",
-      "integrity": "sha512-RF0Fw+rO5AMf9MAyaRXI4AV0Ulj5lMHqVxxdSgiVbixSCXoEmmX/jk0CuJw4+3SqroYO9VoUh+HcuJivvtJemA==",

*      "version": "7.7.4",
*      "resolved": "https://registry.npmjs.org/semver/-/semver-7.7.4.tgz",
*      "integrity": "sha512-vFKC2IEtQnVhpT78h1Yp8wzwrf8CM+MzKMHGJZfBtzhZNycRFnXsHk6E5TxIkkMsgNS7mdX3AGB7x2QM2di4lA==",
       "dev": true,

-      "license": "ISC",
         "bin": {
           "semver": "bin/semver.js"
         },
  @@ -2979,32 +2931,34 @@
  }
  },
  "node_modules/send": {
-      "version": "1.2.0",
-      "resolved": "https://registry.npmjs.org/send/-/send-1.2.0.tgz",
-      "integrity": "sha512-uaW0WwXKpL9blXE2o0bRhoL2EGXIrZxQ2ZQ4mgcfoBxdFmQold+qWsD2jLrfZ0trjKL6vOw0j//eAwcALFjKSw==",
-      "license": "MIT",

*      "version": "1.2.1",
*      "resolved": "https://registry.npmjs.org/send/-/send-1.2.1.tgz",
*      "integrity": "sha512-1gnZf7DFcoIcajTjTwjwuDjzuz4PPcY2StKPlsGAQ1+YH20IRVrBaXSWmdjowTJ6u8Rc01PoYOGHXfP1mYcZNQ==",
       "dependencies": {

-        "debug": "^4.3.5",

*        "debug": "^4.4.3",
         "encodeurl": "^2.0.0",
         "escape-html": "^1.0.3",
         "etag": "^1.8.1",
         "fresh": "^2.0.0",

-        "http-errors": "^2.0.0",
-        "mime-types": "^3.0.1",

*        "http-errors": "^2.0.1",
*        "mime-types": "^3.0.2",
         "ms": "^2.1.3",
         "on-finished": "^2.4.1",
         "range-parser": "^1.2.1",

-        "statuses": "^2.0.1"

*        "statuses": "^2.0.2"
       },
       "engines": {
         "node": ">= 18"
*      },
*      "funding": {
*        "type": "opencollective",
*        "url": "https://opencollective.com/express"
       }
  },
  "node_modules/serve-static": {

-      "version": "2.2.0",
-      "resolved": "https://registry.npmjs.org/serve-static/-/serve-static-2.2.0.tgz",
-      "integrity": "sha512-61g9pCh0Vnh7IutZjtLGGpTA355+OPn2TyDv/6ivP2h/AdAVX9azsoxmg2/M6nZeQZNYBEwIcsne1mJd9oQItQ==",
-      "license": "MIT",

*      "version": "2.2.1",
*      "resolved": "https://registry.npmjs.org/serve-static/-/serve-static-2.2.1.tgz",
*      "integrity": "sha512-xRXBn0pPqQTVQiC8wyQrKs2MOlX24zQ0POGaj0kultvoOCstBQM5yvOhAVSUwOMjQtTvsPWoNCHfPGwaaQJhTw==",
         "dependencies": {
           "encodeurl": "^2.0.0",
           "escape-html": "^1.0.3",
  @@ -3013,19 +2967,21 @@
  },
  "engines": {
  "node": ">= 18"
*      },
*      "funding": {
*        "type": "opencollective",
*        "url": "https://opencollective.com/express"
       }
  },
  "node_modules/setprototypeof": {
  "version": "1.2.0",
  "resolved": "https://registry.npmjs.org/setprototypeof/-/setprototypeof-1.2.0.tgz",

-      "integrity": "sha512-E5LDX7Wrp85Kil5bhZv46j8jOeboKq5JMmYM3gVGdGH8xFpPWXUMsNrlODCrkoxMEeNi/XZIwuRvY4XNwYMJpw==",
-      "license": "ISC"

*      "integrity": "sha512-E5LDX7Wrp85Kil5bhZv46j8jOeboKq5JMmYM3gVGdGH8xFpPWXUMsNrlODCrkoxMEeNi/XZIwuRvY4XNwYMJpw=="
  },
  "node_modules/shebang-command": {
  "version": "2.0.0",
  "resolved": "https://registry.npmjs.org/shebang-command/-/shebang-command-2.0.0.tgz",
  "integrity": "sha512-kHxr2zZpYtdmrN1qDjrrX/Z1rR1kG8Dx+gkpK1G4eXmvXswmcE1hTWBWYUzlraYw1/yZp6YuDY77YtvbN0dmDA==",

-      "license": "MIT",
         "dependencies": {
           "shebang-regex": "^3.0.0"
         },
  @@ -3037,7 +2993,6 @@
  "version": "3.0.0",
  "resolved": "https://registry.npmjs.org/shebang-regex/-/shebang-regex-3.0.0.tgz",
  "integrity": "sha512-7++dFhtcx3353uBaq8DDR4NuxBetBzC7ZQOhmTQInHEd6bSrXdiEyzCvG07Z44UYdLShWUyXt5M/yhz8ekcb1A==",
-      "license": "MIT",
         "engines": {
           "node": ">=8"
         }
  @@ -3046,7 +3001,6 @@
  "version": "1.1.0",
  "resolved": "https://registry.npmjs.org/side-channel/-/side-channel-1.1.0.tgz",
  "integrity": "sha512-ZX99e6tRweoUXqR+VBrslhda51Nh5MTQwou5tnUDgbtyM0dBgmhEDtWGP/xbKn6hqfPRHujUNwz5fy/wbbhnpw==",
-      "license": "MIT",
         "dependencies": {
           "es-errors": "^1.3.0",
           "object-inspect": "^1.13.3",
  @@ -3062,13 +3016,12 @@
  }
  },
  "node_modules/side-channel-list": {
-      "version": "1.0.0",
-      "resolved": "https://registry.npmjs.org/side-channel-list/-/side-channel-list-1.0.0.tgz",
-      "integrity": "sha512-FCLHtRD/gnpCiCHEiJLOwdmFP+wzCmDEkc9y7NsYxeF4u7Btsn1ZuwgwJGxImImHicJArLP4R0yX4c2KCrMrTA==",
-      "license": "MIT",

*      "version": "1.0.1",
*      "resolved": "https://registry.npmjs.org/side-channel-list/-/side-channel-list-1.0.1.tgz",
*      "integrity": "sha512-mjn/0bi/oUURjc5Xl7IaWi/OJJJumuoJFQJfDDyO46+hBWsfaVM65TBHq2eoZBhzl9EchxOijpkbRC8SVBQU0w==",
       "dependencies": {
         "es-errors": "^1.3.0",

-        "object-inspect": "^1.13.3"

*        "object-inspect": "^1.13.4"
         },
         "engines": {
           "node": ">= 0.4"
  @@ -3081,7 +3034,6 @@
  "version": "1.0.1",
  "resolved": "https://registry.npmjs.org/side-channel-map/-/side-channel-map-1.0.1.tgz",
  "integrity": "sha512-VCjCNfgMsby3tTdo02nbjtM/ewra6jPHmpThenkTYh8pG9ucZ/1P8So4u4FGBek/BjpOVsDCMoLA/iuBKIFXRA==",

-      "license": "MIT",
         "dependencies": {
           "call-bound": "^1.0.2",
           "es-errors": "^1.3.0",
  @@ -3099,7 +3051,6 @@
  "version": "1.0.2",
  "resolved": "https://registry.npmjs.org/side-channel-weakmap/-/side-channel-weakmap-1.0.2.tgz",
  "integrity": "sha512-WPS/HvHQTYnHisLo9McqBHOJk2FkHO/tlpvldyrnem4aeQp4hai3gythswg6p01oSoTl58rcpiFAjF2br2Ak2A==",
-      "license": "MIT",
         "dependencies": {
           "call-bound": "^1.0.2",
           "es-errors": "^1.3.0",
  @@ -3119,7 +3070,6 @@
  "resolved": "https://registry.npmjs.org/simple-update-notifier/-/simple-update-notifier-2.0.0.tgz",
  "integrity": "sha512-a2B9Y0KlNXl9u/vsW6sTIu9vGEpfKu2wRV6l1H3XEas/0gUIzGzBoP/IouTcUQbm9JWZLH3COxyn03TYlFax6w==",
  "dev": true,
-      "license": "MIT",
         "dependencies": {
           "semver": "^7.5.3"
         },
  @@ -3131,29 +3081,26 @@
  "version": "2.0.2",
  "resolved": "https://registry.npmjs.org/statuses/-/statuses-2.0.2.tgz",
  "integrity": "sha512-DvEy55V3DB7uknRo+4iOGT5fP1slR8wQohVdknigZPMpMstaKJQWhwiYBACJE3Ul2pTnATihhBYnRhZQHGBiRw==",
-      "license": "MIT",
       "engines": {
         "node": ">= 0.8"
       }
  },
  "node_modules/strnum": {
-      "version": "2.1.1",
-      "resolved": "https://registry.npmjs.org/strnum/-/strnum-2.1.1.tgz",
-      "integrity": "sha512-7ZvoFTiCnGxBtDqJ//Cu6fWtZtc7Y3x+QOirG15wztbdngGSkht27o2pyGWrVy0b4WAy3jbKmnoK6g5VlVNUUw==",

*      "version": "2.2.3",
*      "resolved": "https://registry.npmjs.org/strnum/-/strnum-2.2.3.tgz",
*      "integrity": "sha512-oKx6RUCuHfT3oyVjtnrmn19H1SiCqgJSg+54XqURKp5aCMbrXrhLjRN9TjuwMjiYstZ0MzDrHqkGZ5dFTKd+zg==",
       "funding": [
         {
           "type": "github",
           "url": "https://github.com/sponsors/NaturalIntelligence"
         }

-      ],
-      "license": "MIT"

*      ]
  },
  "node_modules/supports-color": {
  "version": "5.5.0",
  "resolved": "https://registry.npmjs.org/supports-color/-/supports-color-5.5.0.tgz",
  "integrity": "sha512-QjVjwdXIt408MIiAqCX4oUKsgU2EqAGzs2Ppkm4aQYbjm+ZEWEcW4SfFNTr4uMNZma0ey4f5lgLrkB0aX0QMow==",
  "dev": true,

-      "license": "MIT",
         "dependencies": {
           "has-flag": "^3.0.0"
         },
  @@ -3166,7 +3113,6 @@
  "resolved": "https://registry.npmjs.org/to-regex-range/-/to-regex-range-5.0.1.tgz",
  "integrity": "sha512-65P7iz6X5yEr1cwcgvQxbbIw7Uk3gOy5dIdtZ4rDveLqhrdJP+Li/Hx6tyK0NEb+2GCyneCMJiGqrADCSNk8sQ==",
  "dev": true,
-      "license": "MIT",
         "dependencies": {
           "is-number": "^7.0.0"
         },
  @@ -3178,7 +3124,6 @@
  "version": "1.0.1",
  "resolved": "https://registry.npmjs.org/toidentifier/-/toidentifier-1.0.1.tgz",
  "integrity": "sha512-o5sSPKEkg/DIQNmH43V0/uerLrpzVedkUh8tGNvaeXpfpuwjKenlSox/2O/BTlZUtEe+JG7s5YhEz608PlAHRA==",
-      "license": "MIT",
         "engines": {
           "node": ">=0.6"
         }
  @@ -3188,7 +3133,6 @@
  "resolved": "https://registry.npmjs.org/touch/-/touch-3.1.1.tgz",
  "integrity": "sha512-r0eojU4bI8MnHr8c5bNo7lJDdI2qXlWWJk6a9EAFG7vbhTjElYhBVS3/miuE0uOuoLdb8Mc/rVfsmm6eo5o9GA==",
  "dev": true,
-      "license": "ISC",
         "bin": {
           "nodetouch": "bin/nodetouch.js"
         }
  @@ -3197,7 +3141,6 @@
  "version": "1.1.0",
  "resolved": "https://registry.npmjs.org/treeify/-/treeify-1.1.0.tgz",
  "integrity": "sha512-1m4RA7xVAJrSGrrXGs0L3YTwyvBs2S8PbRHaLZAkFw7JR8oIFwYtysxlBZhYIa7xSyiYJKZ3iGrrk55cGA3i9A==",
-      "license": "MIT",
         "engines": {
           "node": ">=0.6"
         }
  @@ -3205,17 +3148,15 @@
  "node_modules/tslib": {
  "version": "2.8.1",
  "resolved": "https://registry.npmjs.org/tslib/-/tslib-2.8.1.tgz",
-      "integrity": "sha512-oJFu94HQb+KVduSUQL7wnpmqnfmLsOA/nAh6b6EH0wCEoK0/mPeXU6c3wKDV83MkOuHPRHtSXKKU99IBazS/2w==",
-      "license": "0BSD"

*      "integrity": "sha512-oJFu94HQb+KVduSUQL7wnpmqnfmLsOA/nAh6b6EH0wCEoK0/mPeXU6c3wKDV83MkOuHPRHtSXKKU99IBazS/2w=="
  },
  "node_modules/tsx": {

-      "version": "4.20.3",
-      "resolved": "https://registry.npmjs.org/tsx/-/tsx-4.20.3.tgz",
-      "integrity": "sha512-qjbnuR9Tr+FJOMBqJCW5ehvIo/buZq7vH7qD7JziU98h6l3qGy0a/yPFjwO+y0/T7GFpNgNAvEcPPVfyT8rrPQ==",

*      "version": "4.21.0",
*      "resolved": "https://registry.npmjs.org/tsx/-/tsx-4.21.0.tgz",
*      "integrity": "sha512-5C1sg4USs1lfG0GFb2RLXsdpXqBSEhAaA/0kPL01wxzpMqLILNxIxIOKiILz+cdg/pLnOUxFYOR5yhHU666wbw==",
       "dev": true,

-      "license": "MIT",
       "dependencies": {
-        "esbuild": "~0.25.0",

*        "esbuild": "~0.27.0",
           "get-tsconfig": "^4.7.5"
         },
         "bin": {
  @@ -3232,7 +3173,6 @@
  "version": "2.0.1",
  "resolved": "https://registry.npmjs.org/type-is/-/type-is-2.0.1.tgz",
  "integrity": "sha512-OZs6gsjF4vMp32qrCbiVSkrFmXtG/AZhY3t0iAMrMBiAZyV9oALtXO8hsrHbMXF9x6L3grlFuwW2oAz7cav+Gw==",

-      "license": "MIT",
         "dependencies": {
           "content-type": "^1.0.5",
           "media-typer": "^1.1.0",
  @@ -3243,11 +3183,10 @@
  }
  },
  "node_modules/typescript": {
-      "version": "5.9.2",
-      "resolved": "https://registry.npmjs.org/typescript/-/typescript-5.9.2.tgz",
-      "integrity": "sha512-CWBzXQrc/qOkhidw1OzBTQuYRbfyxDXJMVJ1XNwUHGROVmuaeiEm3OslpZ1RV96d7SKKjZKrSJu3+t/xlw3R9A==",

*      "version": "6.0.3",
*      "resolved": "https://registry.npmjs.org/typescript/-/typescript-6.0.3.tgz",
*      "integrity": "sha512-y2TvuxSZPDyQakkFRPZHKFm+KKVqIisdg9/CZwm9ftvKXLP8NRWj38/ODjNbr43SsoXqNuAisEf1GdCxqWcdBw==",
       "dev": true,

-      "license": "Apache-2.0",
         "bin": {
           "tsc": "bin/tsc",
           "tsserver": "bin/tsserver"
  @@ -3260,52 +3199,26 @@
  "version": "2.0.5",
  "resolved": "https://registry.npmjs.org/undefsafe/-/undefsafe-2.0.5.tgz",
  "integrity": "sha512-WxONCrssBM8TSPRqN5EmsjVrsv4A8X12J4ArBiiayv3DyyG3ZlIg6yysuuSYdZsVz3TKcTg2fd//Ujd4CHV1iA==",
-      "dev": true,
-      "license": "MIT"

*      "dev": true
  },
  "node_modules/undici-types": {

-      "version": "7.10.0",
-      "resolved": "https://registry.npmjs.org/undici-types/-/undici-types-7.10.0.tgz",
-      "integrity": "sha512-t5Fy/nfn+14LuOc2KNYg75vZqClpAiqscVvMygNnlsHBFpSXdJaYtXMcdNLpl/Qvc3P2cB3s6lOV51nqsFq4ag==",
-      "dev": true,
-      "license": "MIT"

*      "version": "7.19.2",
*      "resolved": "https://registry.npmjs.org/undici-types/-/undici-types-7.19.2.tgz",
*      "integrity": "sha512-qYVnV5OEm2AW8cJMCpdV20CDyaN3g0AjDlOGf1OW4iaDEx8MwdtChUp4zu4H0VP3nDRF/8RKWH+IPp9uW0YGZg==",
*      "dev": true
  },
  "node_modules/unpipe": {
  "version": "1.0.0",
  "resolved": "https://registry.npmjs.org/unpipe/-/unpipe-1.0.0.tgz",
  "integrity": "sha512-pjy2bYhSsufwWlKwPc+l3cN7+wuJlK6uz0YdJEOlQDbl6jo/YlPi4mb8agUkVC8BF7V8NuzeyPNqRksA3hztKQ==",

-      "license": "MIT",
       "engines": {
         "node": ">= 0.8"
       }
  },
- "node_modules/uri-js": {
-      "version": "4.4.1",
-      "resolved": "https://registry.npmjs.org/uri-js/-/uri-js-4.4.1.tgz",
-      "integrity": "sha512-7rKUyy33Q1yc98pQ1DAmLtwX109F7TIfWlW1Ydo8Wl1ii1SeHieeh0HHfPeL2fMXK6z0s8ecKs9frCuLJvndBg==",
-      "license": "BSD-2-Clause",
-      "dependencies": {
-        "punycode": "^2.1.0"
-      }
- },
- "node_modules/uuid": {
-      "version": "9.0.1",
-      "resolved": "https://registry.npmjs.org/uuid/-/uuid-9.0.1.tgz",
-      "integrity": "sha512-b+1eJOlsR9K8HJpow9Ok3fiWOWSIcIzXodvv0rQjVoOVNpWMpxf1wZNpt4y9h10odCNrqnYp1OBzRktckBe3sA==",
-      "funding": [
-        "https://github.com/sponsors/broofa",
-        "https://github.com/sponsors/ctavan"
-      ],
-      "license": "MIT",
-      "bin": {
-        "uuid": "dist/bin/uuid"
-      }
- },
  "node_modules/vary": {
  "version": "1.1.2",
  "resolved": "https://registry.npmjs.org/vary/-/vary-1.1.2.tgz",
  "integrity": "sha512-BNGbWLfd0eUPabhkXUVm0j8uuvREyTh5ovRa/dyow/BqAbZJyC+5fU+IzQOzmAKzYqYRAISoRhdQr3eIZ/PXqg==",
-      "license": "MIT",
         "engines": {
           "node": ">= 0.8"
         }
  @@ -3314,7 +3227,6 @@
  "version": "2.0.2",
  "resolved": "https://registry.npmjs.org/which/-/which-2.0.2.tgz",
  "integrity": "sha512-BLI3Tl1TW3Pvl70l3yq3Y64i+awpwXqsGBYWkkqMtnbXgrMD+yj7rhW0kuEDxzJaYXGjEW5ogapKNMEKNMjibA==",
-      "license": "ISC",
         "dependencies": {
           "isexe": "^2.0.0"
         },
  @@ -3328,25 +3240,22 @@
  "node_modules/wrappy": {
  "version": "1.0.2",
  "resolved": "https://registry.npmjs.org/wrappy/-/wrappy-1.0.2.tgz",
-      "integrity": "sha512-l4Sp/DRseor9wL6EvV2+TuQn63dMkPjZ/sp9XkghTEbV9KlPS1xUsZ3u7/IQO4wxtcFB4bgpQPRcR3QCvezPcQ==",
-      "license": "ISC"

*      "integrity": "sha512-l4Sp/DRseor9wL6EvV2+TuQn63dMkPjZ/sp9XkghTEbV9KlPS1xUsZ3u7/IQO4wxtcFB4bgpQPRcR3QCvezPcQ=="
  },
  "node_modules/zod": {

-      "version": "3.25.76",
-      "resolved": "https://registry.npmjs.org/zod/-/zod-3.25.76.tgz",
-      "integrity": "sha512-gzUt/qt81nXsFGKIFcC3YnfEAx5NkunCfnDlvuBSSFS02bcXu4Lmea0AFIUwbLWxWPx3d9p8S5QoaujKcNQxcQ==",
-      "license": "MIT",

*      "version": "4.3.6",
*      "resolved": "https://registry.npmjs.org/zod/-/zod-4.3.6.tgz",
*      "integrity": "sha512-rftlrkhHZOcjDwkGlnUtZZkvaPHCsDATp4pGpuOOMDaTdDDXF91wuVDJoWoPsKX/3YPQ5fHuF3STjcYyKr+Qhg==",
       "funding": {
         "url": "https://github.com/sponsors/colinhacks"
       }
  },
  "node_modules/zod-to-json-schema": {

-      "version": "3.24.6",
-      "resolved": "https://registry.npmjs.org/zod-to-json-schema/-/zod-to-json-schema-3.24.6.tgz",
-      "integrity": "sha512-h/z3PKvcTcTetyjl1fkj79MHNEjm+HpD6NXheWjzOekY7kV+lwDYnHw+ivHkijnCSMz1yJaWBD9vu/Fcmk+vEg==",
-      "license": "ISC",

*      "version": "3.25.2",
*      "resolved": "https://registry.npmjs.org/zod-to-json-schema/-/zod-to-json-schema-3.25.2.tgz",
*      "integrity": "sha512-O/PgfnpT1xKSDeQYSCfRI5Gy3hPf91mKVDuYLUHZJMiDFptvP41MSnWofm8dnCm0256ZNfZIM7DSzuSMAFnjHA==",
       "peerDependencies": {

-        "zod": "^3.24.1"

*        "zod": "^3.25.28 || ^4"
         }
       }
  }
  diff --git a/package.json b/package.json
  index 1a7ba6d..8045017 100644
  --- a/package.json
  +++ b/package.json
  @@ -29,22 +29,21 @@
  "author": "Teja",
  "license": "MIT",
  "devDependencies": {

- "@types/node": "^24.2.1",
- "nodemon": "^3.1.10",
- "tsx": "^4.20.3",
- "typescript": "^5.9.2"

* "@types/node": "^25.6.0",
* "@types/treeify": "^1.0.3",
* "nodemon": "^3.1.14",
* "tsx": "^4.21.0",
* "typescript": "^6.0.3"
  },
  "dependencies": {

- "@aws-sdk/client-codecommit": "^3.864.0",
- "@aws-sdk/credential-providers": "^3.864.0",
- "@modelcontextprotocol/sdk": "^1.17.2",
- "@types/diff": "^7.0.2",
- "@types/treeify": "^1.0.3",
- "diff": "^8.0.2",

* "@aws-sdk/client-codecommit": "^3.1038.0",
* "@aws-sdk/credential-providers": "^3.1038.0",
* "@modelcontextprotocol/sdk": "^1.29.0",
* "diff": "^9.0.0",
  "treeify": "^1.1.0"
  },
  "engines": {

- "node": ">=18.0.0"

* "node": ">=20.0.0"
  },
  "files": [
  "dist",
  diff --git a/tsconfig.json b/tsconfig.json
  index 49dc5c4..c7ca615 100644
  --- a/tsconfig.json
  +++ b/tsconfig.json
  @@ -3,6 +3,7 @@
  "target": "ES2022",
  "module": "ES2022",
  "lib": ["ES2022"],
* "types": ["node"],
  "outDir": "./dist",
  "rootDir": "./src",
  "strict": true,
  PS C:\Users\sanik_unwtxkj\MyProjects\MCP servers\aws-code-commit-pr-mcp>

Total impact: **14 files changed, ~1640 insertions / ~2450 deletions** (net ~810 lines removed, mostly dead code).

---

## Epic 1 — Dependency Modernization

### Task 1.1 — Bump core dependencies to April 2026 latest

**Description**: Upgrade TypeScript 5.9 → 6.0, AWS SDK 3.864 → 3.1038, MCP SDK 1.17 → 1.29, diff 8 → 9, plus dev tooling (`@types/node`, `nodemon`, `tsx`).
**Acceptance**:

- [x] `npm run build` passes with new versions
- [x] No new TS 6 strict-mode errors
- [x] Bundled types used for `diff` (drop `@types/diff`)
      **Files**: `package.json`, `package-lock.json`
      **Effort**: S
      **Commit**: `fc5cf99`

### Task 1.2 — Adjust tsconfig for TypeScript 6

**Description**: TS 6 changed default `types` from "all installed `@types/*`" to `[]`. Add `"types": ["node"]` so global Node types (`process`, `Buffer`, `NodeJS.Timeout`) keep resolving. Other defaults preserved by explicit settings.
**Acceptance**:

- [x] `npm run build` resolves Node globals
- [x] `target`, `module`, `rootDir`, `strict`, `moduleResolution` remain explicitly set
      **Files**: `tsconfig.json`
      **Effort**: XS
      **Commit**: `fc5cf99`

### Task 1.3 — Bump engines to Node 20 + clean up packaging

**Description**: Node 18 EOL'd April 2025; TS 6 requires Node 20+. Move `@types/treeify` from `dependencies` to `devDependencies` (was misplaced).
**Acceptance**:

- [x] `engines.node` is `>=20.0.0`
- [x] `@types/treeify` is under `devDependencies`
      **Files**: `package.json`
      **Effort**: XS
      **Commit**: `fc5cf99`

---

## Epic 2 — IAM-Role / Cross-Environment Authentication

### Task 2.1 — Replace fromIni/fromEnv with fromNodeProviderChain

**Description**: Use the AWS SDK's standard Node.js credential provider chain so the server picks up credentials from env vars, SSO, ini profiles, `credential_process`, EKS IRSA web-identity tokens, ECS / Fargate task-role metadata, and EC2 instance profile metadata — all without code changes.
**Acceptance**:

- [x] Local laptop with profile still works
- [x] Local laptop with env vars still works
- [x] Fargate task role would resolve credentials with no env vars set (verified via chain order in code review)
- [x] EKS IRSA / EC2 IMDS resolution paths exist in chain
      **Files**: `src/auth/aws-auth.ts`
      **Effort**: M
      **Commit**: `d8d7efc`

### Task 2.2 — Pass credential provider directly to CodeCommitClient

**Description**: The previous code resolved credentials once into a static object and handed that to the client, then refreshed manually on a 6-min `setInterval`. Now the provider function is passed to the SDK, which auto-refreshes when expiration nears. Removes ~150 lines of manual-refresh plumbing.
**Acceptance**:

- [x] Token rotation works without manual `aws_creds_refresh` calls
- [x] No `setInterval` timers running in the auth manager
- [x] `_isRefresh` parameter no longer in code
      **Files**: `src/auth/aws-auth.ts`
      **Effort**: M
      **Commit**: `d8d7efc`

### Task 2.3 — Preserve WSL credential discovery without process.env mutation

**Description**: Old code mutated `AWS_SHARED_CREDENTIALS_FILE` / `AWS_CONFIG_FILE` / `AWS_PROFILE` in `process.env` permanently, polluting the host process. Now those paths are passed as `{filepath, configFilepath, profile}` options to `fromNodeProviderChain`.
**Acceptance**:

- [x] WSL → Windows-side `~/.aws/credentials` still discovered automatically
- [x] `process.env` is not mutated by `loadCredentials`
      **Files**: `src/auth/aws-auth.ts`
      **Effort**: S (within Task 2.1 scope)
      **Commit**: `d8d7efc`

### Task 2.4 — Make getCredentials / isCredentialsValid async

**Description**: Now that credentials are resolved on-demand from the provider, both methods become async. Update the only caller (`aws_creds_status` tool handler) to await them.
**Acceptance**:

- [x] `getCredentials()` returns `Promise<AWSCredentials | null>`
- [x] `isCredentialsValid()` returns `Promise<boolean>`
- [x] `aws_creds_status` tool handler awaits both
      **Files**: `src/auth/aws-auth.ts`, `src/index.ts`
      **Effort**: S
      **Commit**: `d8d7efc`

---

## Epic 3 — Security Fixes

### Task 3.1 — Stop logging secret access keys to stderr

**Description**: `console.error("Resolved credentials:" + JSON.stringify(resolvedCredentials))` was writing the full secret access key + session token to stderr, which lands in MCP host logs. Removed.
**Acceptance**:

- [x] No stderr output contains `accessKeyId`/`secretAccessKey` values
- [x] Diagnostic info uses redacted form (first-8 + last-6 chars)
      **Files**: `src/auth/aws-auth.ts`
      **Effort**: XS
      **Commit**: `d8d7efc`

### Task 3.2 — Cap regex pattern length in code_search (ReDoS mitigation)

**Description**: Untrusted MCP clients could send regex patterns that hang Node's regex engine (catastrophic backtracking). Pattern length now capped at 200 chars; non-string patterns rejected.
**Acceptance**:

- [x] Patterns >200 chars throw `MCPValidationError`
- [x] Non-string patterns throw `MCPValidationError`
      **Files**: `src/index.ts`
      **Effort**: S
      **Commit**: `159f18b`
      **Future work**: Full ReDoS mitigation requires `safe-regex2` or worker-thread sandbox (left as a follow-up — see proposed-tools doc).

### Task 3.3 — Stop globally mutating process.env for credential paths

**Description**: Covered by Task 2.3; tracked separately because it's a security/isolation concern (other SDK consumers in the same process were inheriting the override).
**Acceptance**: Same as Task 2.3.
**Files**: `src/auth/aws-auth.ts`
**Effort**: S (within Task 2.1)
**Commit**: `d8d7efc`

---

## Epic 4 — Audit-Bug Fixes (High Severity)

### Task 4.1 — Fix retryWithBackoff swallow-and-mangle error path

**Description**: An outer try/catch in `retryWithBackoff` was swallowing all errors and returning a fabricated MCP-shaped object with `content[0].error` (wrong field — should be `text`). This violated MCP protocol AND hid real failures. Removed.
**Acceptance**:

- [x] AWS errors propagate through `handleAWSError`
- [x] No `{content:[{error}]}` shapes returned
      **Files**: `src/utils/error-handler.ts`
      **Effort**: S
      **Commit**: `159f18b`

### Task 4.2 — Add credentials-error classifications

**Description**: `handleAWSError` only matched legacy names (`CredentialsError`, `UnauthorizedOperation`). AWS SDK v3 throws `CredentialsProviderError`, `ExpiredTokenException`, `ExpiredToken` — none of which were classified, so credential failures fell through to generic 500.
**Acceptance**:

- [x] All known credential-error names map to `CREDENTIALS_ERROR` code
- [x] User-facing message mentions running `aws_creds_refresh`
      **Files**: `src/utils/error-handler.ts`
      **Effort**: XS
      **Commit**: `159f18b`

### Task 4.3 — Fix comment_reply schema vs handler mismatch

**Description**: The MCP `comment_reply` tool schema declared `pullRequestId`, `repositoryName`, `beforeCommitId`, `afterCommitId` as required parameters, but AWS's `PostCommentReply` API only needs `inReplyTo` + `content`. Service signature also took the four phantom params and ignored them. MCP clients were forced to provide unused values.
**Acceptance**:

- [x] Tool schema requires only `inReplyTo` + `content`
- [x] Service `replyToComment(inReplyTo, content, clientRequestToken?)` signature
- [x] README example matches new shape
      **Files**: `src/index.ts`, `src/services/pull-request-service.ts`, `README.md`
      **Effort**: S
      **Commit**: `159f18b`, `42df9a8`

### Task 4.4 — Fix .js ESM import in pull-request-service.ts

**Description**: `import {...} from "../types"` was missing the `.js` extension while the rest of the codebase used `.js`-suffixed ESM specifiers. Strict NodeNext / ESM resolution would fail at runtime.
**Acceptance**:

- [x] All ESM imports include `.js` extension
      **Files**: `src/services/pull-request-service.ts`
      **Effort**: XS
      **Commit**: `159f18b`

### Task 4.5 — Fix getFolder root path ("/" → "")

**Description**: `GetFolderCommand` rejects `folderPath: "/"` with `FolderDoesNotExist`. AWS expects `""` for the repo root. Fix passes the path through verbatim and never substitutes `"/"`.
**Acceptance**:

- [x] `folder_get` with empty path or `"/"` returns the root folder contents
- [x] `code_search` tree mode at root works
      **Files**: `src/services/repository-service.ts`
      **Effort**: XS
      **Commit**: `159f18b`

### Task 4.6 — Move SIGINT/SIGTERM handlers after server init

**Description**: Signal handlers were registered before `server.run()` resolved. A SIGINT during init would call `server.shutdown()` on a half-initialized auth manager. Now registered inside `main()` after `await server.run()`.
**Acceptance**:

- [x] `server.run()` is awaited
- [x] Signal handlers register after init succeeds
- [x] Init failures exit via `main().catch`
      **Files**: `src/index.ts`
      **Effort**: XS
      **Commit**: `159f18b`

### Task 4.7 — Fix path.replace bug in WSL credential-path discovery

**Description**: `credentialsPath.replace("credentials", "config")` replaces only the FIRST occurrence; for paths like `/mnt/c/Users/credentials_admin/.aws/credentials` it produced `/mnt/c/Users/config_admin/.aws/credentials`. Switched to `path.join(path.dirname(credentialsPath), "config")`.
**Acceptance**:

- [x] Username substrings containing "credentials" don't break path resolution
      **Files**: `src/auth/aws-auth.ts`
      **Effort**: XS
      **Commit**: `d8d7efc`

### Task 4.8 — Read ~/.aws/config in getAvailableProfiles

**Description**: AWS profiles defined in `~/.aws/config` use `[profile NAME]` syntax for non-default profiles. Old code only read `~/.aws/credentials`, missing every config-only profile (common when SSO is configured).
**Acceptance**:

- [x] Both files read; `profile ` prefix stripped from config entries
- [x] Profiles deduplicated across both files
      **Files**: `src/auth/aws-auth.ts`
      **Effort**: S
      **Commit**: `d8d7efc`

---

## Epic 5 — Audit-Bug Fixes (Medium Severity)

### Task 5.1 — Add MCPValidationError for 400-class input validation

**Description**: Tool handlers were throwing plain `new Error(...)` for invalid input, which fell through `handleAWSError`'s catch-all and became 500-class. Added `MCPValidationError` class; classified to 400 with `code: "VALIDATION_ERROR"`.
**Acceptance**:

- [x] All input-validation throws use `MCPValidationError`
- [x] `handleAWSError` maps it to 400 status
      **Files**: `src/utils/error-handler.ts`, `src/index.ts`
      **Effort**: S
      **Commit**: `159f18b`

### Task 5.2 — Add input validation to comment_post

**Description**: When `filePath` was provided but `filePosition` was missing, the location object had `filePosition: undefined`, which AWS rejected with an opaque error. Now validates: if `filePath` present, `filePosition` must be a number AND `relativeFileVersion` must be `"BEFORE"` or `"AFTER"`.
**Acceptance**:

- [x] Missing `filePosition` with `filePath` throws `MCPValidationError`
- [x] Invalid `relativeFileVersion` throws `MCPValidationError`
      **Files**: `src/index.ts`
      **Effort**: XS
      **Commit**: `159f18b`

### Task 5.3 — Validate batch_diff_analyze.fileDifferences is an array

**Description**: Handler threw `Cannot read properties of undefined` when `fileDifferences` was missing. Now throws `MCPValidationError`.
**Files**: `src/index.ts`
**Effort**: XS
**Commit**: `159f18b`

### Task 5.4 — Allow empty-args MCP requests

**Description**: `if (!args) throw new Error("No arguments provided")` rejected legitimate empty-args calls (`aws_creds_refresh`, `aws_profiles_list`, `aws_creds_status`). Replaced with `args = request.params.arguments ?? {}`.
**Files**: `src/index.ts`
**Effort**: XS
**Commit**: `159f18b`

### Task 5.5 — Fix chunkGitDiff no-hunks edge case

**Description**: When a diff had no `@@` markers (binary file, deletion, empty), the response was a header-only chunk with confusing metadata. Now detects and returns `{chunk, totalHunks: 0, hasMore: false}` explicitly.
**Files**: `src/index.ts`
**Effort**: S
**Commit**: `159f18b`

### Task 5.6 — Fix aws_creds_status accessKeyId display

**Description**: `credentials?.accessKeyId?.slice(0,8) + "..." + credentials?.accessKeyId?.slice(-6) || "Not set"` — the `||` only applied to the last slice, so an undefined `accessKeyId` rendered as `"undefined...undefined"`. Replaced with explicit ternary.
**Files**: `src/index.ts`
**Effort**: XS
**Commit**: `159f18b`

### Task 5.7 — Paginate searchRepositories across all pages

**Description**: `searchRepositories` filtered only the first page returned by `ListRepositories`. Misleading name. Now paginates with `MAX_PAGES = 20` cap (≈2k repos) and aggregates matches.
**Acceptance**:

- [x] Search finds matches in pages beyond the first
- [x] Loop terminates on `!nextToken` or `pages >= MAX_PAGES`
      **Files**: `src/services/repository-service.ts`
      **Effort**: S
      **Commit**: `159f18b`

### Task 5.8 — Stop fabricating undefined fields in listRepositories

**Description**: AWS `ListRepositories` only returns `name` + `id`. Old code set every other Repository field to `undefined` explicitly, claiming completeness it didn't have. Now only populates the fields AWS actually returns; consumers needing description/defaultBranch/etc. should call `repo_get`.
**Files**: `src/services/repository-service.ts`
**Effort**: XS
**Commit**: `159f18b`

### Task 5.9 — Use SHA1 for git diff index hash

**Description**: `generateHashPlaceholder()` used `Math.random()`, producing different "git index" hashes on every call. Two consecutive analyses of the same diff produced different output, defeating downstream caching. Replaced with `crypto.createHash('sha1').update(content).digest('hex').slice(0,7)`.
**Files**: `src/utils/intelligent-diff-analyzer.ts`
**Effort**: XS
**Commit**: `159f18b`

### Task 5.10 — Fix lines.pop() trailing-newline edge case

**Description**: `performLineDiffWithLibrary` was popping the trailing empty string from `value.split('\n')` regardless of whether the value ended with `\n`. For content without trailing newline, this dropped the real last line and threw line counts off by one. Now only pops when the value actually ends with `\n`.
**Files**: `src/utils/intelligent-diff-analyzer.ts`
**Effort**: XS
**Commit**: `159f18b`

### Task 5.11 — Read server version from package.json

**Description**: `Server({ name: "aws-pr-reviewer", version: "1.0.0" })` was hardcoded; package.json was at 1.3.0. MCP clients saw the stale version. Now read at startup from `package.json` via `import.meta.url`.
**Files**: `src/index.ts`
**Effort**: XS
**Commit**: `159f18b`

---

## Epic 6 — Dead Code Removal

### Task 6.1 — Remove dead methods from intelligent-diff-analyzer.ts (~380 lines)

**Description**: Removed unused private methods: `performLineDiff`, `addContextToChunks`, `longestCommonSubsequence`, `calculateSummary`, `determineContextSize`, `getContextLines`, the legacy `generateGitDiffFormat`. Removed unused interface `FileAnalysisContext`. Verified zero callers in `src/` via grep.
**Acceptance**:

- [x] `npm run build` passes
- [x] grep confirms no references
      **Files**: `src/utils/intelligent-diff-analyzer.ts`
      **Effort**: S
      **Commit**: `159f18b`

### Task 6.2 — Remove dead methods from line-position-calculator.ts (~250 lines)

**Description**: Only `validateAndAdjustLinePosition` was being called (by `pull-request-service.ts:postComment`). Removed `mapLineBetweenVersions`, `findBestLinePosition`, `mapAILineToCodeCommitPosition`, `getFileContentSummary`. Verified zero callers.
**Files**: `src/utils/line-position-calculator.ts`
**Effort**: XS
**Commit**: `159f18b`

### Task 6.3 — Remove dead exports from pagination.ts (~50 lines)

**Description**: `getAllPages` and `formatPaginationInfo` were exported but had zero callers. Only `createPaginationOptions` is used.
**Files**: `src/utils/pagination.ts`
**Effort**: XS
**Commit**: `159f18b`

---

## Epic 7 — Documentation

### Task 7.1 — Rewrite README AWS Authentication section

**Description**: Document the new credential provider chain (env, SSO, ini, IRSA, ECS, IMDS); add Fargate / ECS / EKS / EC2 / SSO setup paths; remove the stale "automatic credential refresh (7.5-hour intervals)" claim.
**Files**: `README.md`
**Effort**: S
**Commit**: `42df9a8`

### Task 7.2 — Bump README prerequisites and component descriptions

**Description**: Node 18 → Node 20; rewrite the `AWSAuthManager` description in the Architecture section to mention SDK-managed rotation.
**Files**: `README.md`
**Effort**: XS
**Commit**: `42df9a8`

### Task 7.3 — Trim comment_reply README example to two-arg shape

**Description**: README example showed 6 fields; the real tool now takes 2 (matching AWS API).
**Files**: `README.md`
**Effort**: XS
**Commit**: `42df9a8`

### Task 7.4 — Sync CLAUDE-AI-OPTIMIZATION.md and .env.example

**Description**: Drop "Auto-refresh every 7.5 hours" from CLAUDE-AI-OPTIMIZATION.md. Drop the `CREDENTIAL_REFRESH_INTERVAL` hint from `.env.example`; document that Fargate / ECS / EKS / EC2 don't need any of the env vars.
**Files**: `CLAUDE-AI-OPTIMIZATION.md`, `.env.example`
**Effort**: XS
**Commit**: `42df9a8`

---

## Open Items / Deferred (NOT done — candidates for follow-up tasks)

These were surfaced by the audit but consciously deferred. Each is a candidate Azure DevOps task in its own right.

| #   | Item                                                                                                    | Reason deferred                                                               |
| --- | ------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------- |
| D-1 | Full ReDoS mitigation in `repository-service.ts:performSearch` (worker-thread sandbox or `safe-regex2`) | Wider change; current 200-char cap reduces but doesn't eliminate blast radius |
| D-2 | `listBranches` N+1 (calls `getBranch` per branch)                                                       | Behavior change (some callers depend on commit IDs)                           |
| D-3 | Service methods throw plain `new Error(...)` instead of typed errors                                    | Wider design refactor                                                         |
| D-4 | `File`/`Folder` discriminated union in types                                                            | Wider design refactor                                                         |
| D-5 | `getComments` could auto-fill commit IDs from PR record                                                 | UX improvement; not a bug                                                     |
| D-6 | `aws_creds_refresh` calls `reinitializeServices()` redundantly                                          | Harmless; removing has subtle reference-equality risk                         |
| D-7 | `isCredentialsValid()` is now diagnostic-only after SDK auto-rotation                                   | Rename / document; not a bug                                                  |
| D-8 | WSL path PII in logs (`/mnt/c/Users/<name>/...`)                                                        | Low-impact, low-risk                                                          |
