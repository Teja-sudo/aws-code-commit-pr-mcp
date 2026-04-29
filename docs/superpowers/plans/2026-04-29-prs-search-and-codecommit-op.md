# prs_search + codecommit_op Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add two MCP tools — `prs_search` (multi-field PR search with match modes) and `codecommit_op` (scoped SDK-backed dispatcher for CodeCommit ops, merges excluded) — without requiring a host AWS CLI install.

**Architecture:**
- `prs_search` issues server-side filters via `ListPullRequestsCommand` (status, authorArn) then fans out parallel `GetPullRequestCommand` calls in batches of 5, applying client-side string/date filters with three match modes (exact / substring / regex).
- `codecommit_op` is a dispatcher backed by the existing `CodeCommitClient` (same auth chain). An allowlist maps kebab-case operation names → SDK Command classes. Merge ops + cross-service ops are structurally absent from the allowlist, so they cannot be invoked.
- A companion `codecommit_op_list` tool enumerates available ops so Claude can discover what's permitted without trial-and-error.

**Tech Stack:** TypeScript 6.0, AWS SDK v3 (`@aws-sdk/client-codecommit`), MCP SDK 1.29, Node 20+. No new dependencies.

**Verification approach:** This project has no test framework (per repo convention). Each task is verified by `npm run build` (TypeScript strict-mode + bundler resolution) and a dedicated audit loop using parallel `superpowers:code-reviewer` agents at the end of each phase. We avoid scope creep into adding test infrastructure.

---

## File Structure

| File | Status | Responsibility |
|---|---|---|
| `src/types/index.ts` | modify | Add `MatchSpec`, `PullRequestFilters`, `PullRequestSearchOptions`, `PullRequestSearchResult` types |
| `src/utils/matching.ts` | **create** | `matchString()` helper for exact/substring/regex matching with length cap |
| `src/services/pull-request-service.ts` | modify | Add `searchPullRequests()` method using existing `client.send()` patterns |
| `src/services/codecommit-op-dispatcher.ts` | **create** | Allowlist + dispatcher for `codecommit_op` |
| `src/index.ts` | modify | Add `prs_search`, `codecommit_op`, `codecommit_op_list` tool definitions and case handlers |

Two new files; three existing files modified. No tests directory (project convention).

---

## Phase 1 — `prs_search`

### Task 1: Add types

**Files:**
- Modify: `src/types/index.ts` — append new interfaces at end

- [ ] **Step 1: Add the types**

```typescript
// Append to src/types/index.ts

export type MatchMode = "exact" | "substring" | "regex";

export interface MatchSpec {
  value: string;
  mode?: MatchMode; // default "substring"
  caseSensitive?: boolean; // default false; ignored for "regex" (use inline /flags/)
}

export interface PullRequestFilters {
  status?: "OPEN" | "CLOSED";
  authorArn?: string; // exact ARN — server-side filter
  authorArnContains?: string; // substring of ARN — client-side
  title?: MatchSpec;
  description?: MatchSpec;
  sourceBranch?: MatchSpec;
  destinationBranch?: MatchSpec;
  createdAfter?: string; // ISO 8601
  createdBefore?: string; // ISO 8601
  lastActivityAfter?: string; // ISO 8601
  lastActivityBefore?: string; // ISO 8601
}

export interface PullRequestSearchOptions {
  maxResults?: number; // matches collected, default 25
  maxScanned?: number; // PRs fetched before stopping, default 500
}

export interface PullRequestSearchResult {
  matches: PullRequest[];
  scanned: number;
  truncated: boolean; // true if maxScanned hit before exhausting AWS pagination
}
```

- [ ] **Step 2: Build to verify types compile**

Run: `npm run build`
Expected: clean exit (0), no errors.

- [ ] **Step 3: Commit**

```bash
git add src/types/index.ts
git commit -m "Add types for PR search filters and results"
```

---

### Task 2: Create matching utility

**Files:**
- Create: `src/utils/matching.ts`

- [ ] **Step 1: Write the matching helper**

```typescript
// src/utils/matching.ts
import { MatchSpec } from "../types/index.js";
import { MCPValidationError } from "./error-handler.js";

const MAX_PATTERN_LEN = 200;

/**
 * Matches a target string against a MatchSpec.
 * - exact: value === target (or case-insensitive variant)
 * - substring: target.includes(value) with case-insensitivity by default
 * - regex: new RegExp(value), with the same 200-char cap as code_search
 *
 * Returns false if target is undefined/null. Throws MCPValidationError for
 * invalid regex or oversized patterns.
 */
export function matchString(target: string | undefined, spec: MatchSpec): boolean {
  if (target === undefined || target === null) return false;
  if (typeof spec.value !== "string") {
    throw new MCPValidationError("MatchSpec.value must be a string");
  }
  if (spec.value.length > MAX_PATTERN_LEN) {
    throw new MCPValidationError(
      `MatchSpec.value exceeds ${MAX_PATTERN_LEN} chars; refine the search`
    );
  }

  const mode = spec.mode ?? "substring";
  const caseSensitive = spec.caseSensitive ?? false;

  switch (mode) {
    case "exact": {
      return caseSensitive
        ? target === spec.value
        : target.toLowerCase() === spec.value.toLowerCase();
    }
    case "substring": {
      return caseSensitive
        ? target.includes(spec.value)
        : target.toLowerCase().includes(spec.value.toLowerCase());
    }
    case "regex": {
      let re: RegExp;
      try {
        re = new RegExp(spec.value, caseSensitive ? "" : "i");
      } catch (err) {
        throw new MCPValidationError(
          `Invalid regex in MatchSpec.value: ${err instanceof Error ? err.message : err}`
        );
      }
      return re.test(target);
    }
    default: {
      throw new MCPValidationError(
        `MatchSpec.mode must be one of: exact, substring, regex`
      );
    }
  }
}
```

- [ ] **Step 2: Build**

Run: `npm run build`
Expected: clean exit.

- [ ] **Step 3: Commit**

```bash
git add src/utils/matching.ts
git commit -m "Add matchString helper for exact/substring/regex matching"
```

---

### Task 3: Add `searchPullRequests` service method

**Files:**
- Modify: `src/services/pull-request-service.ts` — add new method after `getPullRequest`

- [ ] **Step 1: Add the search method**

Add this method to `PullRequestService`:

```typescript
async searchPullRequests(
  repositoryName: string,
  filters: PullRequestFilters,
  options: PullRequestSearchOptions = {}
): Promise<PullRequestSearchResult> {
  const maxResults = options.maxResults ?? 25;
  const maxScanned = options.maxScanned ?? 500;
  const concurrency = 5;

  // Validate ISO date strings up-front so we don't fail mid-scan.
  const createdAfter = parseIsoDate(filters.createdAfter, "createdAfter");
  const createdBefore = parseIsoDate(filters.createdBefore, "createdBefore");
  const lastActivityAfter = parseIsoDate(filters.lastActivityAfter, "lastActivityAfter");
  const lastActivityBefore = parseIsoDate(filters.lastActivityBefore, "lastActivityBefore");

  const matches: PullRequest[] = [];
  let scanned = 0;
  let nextToken: string | undefined;

  const client = await this.authManager.getClient();

  outer: while (scanned < maxScanned && matches.length < maxResults) {
    const listResp = await client.send(
      new ListPullRequestsCommand({
        repositoryName,
        pullRequestStatus: filters.status,
        authorArn: filters.authorArn,
        nextToken,
        maxResults: 100,
      })
    );
    const ids = listResp.pullRequestIds ?? [];

    // Fan out GetPullRequest in concurrency-bounded batches.
    for (let i = 0; i < ids.length; i += concurrency) {
      if (scanned >= maxScanned || matches.length >= maxResults) break outer;
      const batch = ids.slice(i, i + concurrency);
      const prs = await Promise.all(
        batch.map((id) => this.getPullRequest(id))
      );
      scanned += prs.length;

      for (const pr of prs) {
        if (this.matchesFilters(pr, filters, {
          createdAfter, createdBefore, lastActivityAfter, lastActivityBefore,
        })) {
          matches.push(pr);
          if (matches.length >= maxResults) break;
        }
      }
    }

    if (!listResp.nextToken) break;
    nextToken = listResp.nextToken;
  }

  return {
    matches,
    scanned,
    truncated: scanned >= maxScanned && matches.length < maxResults,
  };
}

private matchesFilters(
  pr: PullRequest,
  filters: PullRequestFilters,
  dates: {
    createdAfter?: number;
    createdBefore?: number;
    lastActivityAfter?: number;
    lastActivityBefore?: number;
  }
): boolean {
  if (filters.authorArnContains && !pr.authorArn.toLowerCase().includes(filters.authorArnContains.toLowerCase())) {
    return false;
  }
  if (filters.title && !matchString(pr.title, filters.title)) return false;
  if (filters.description && !matchString(pr.description, filters.description)) return false;

  const target = pr.targets[0];
  if (filters.sourceBranch && !matchString(target?.sourceReference, filters.sourceBranch)) return false;
  if (filters.destinationBranch && !matchString(target?.destinationReference, filters.destinationBranch)) return false;

  const created = pr.creationDate?.getTime();
  if (dates.createdAfter !== undefined && (created === undefined || created < dates.createdAfter)) return false;
  if (dates.createdBefore !== undefined && (created === undefined || created > dates.createdBefore)) return false;

  const activity = pr.lastActivityDate?.getTime();
  if (dates.lastActivityAfter !== undefined && (activity === undefined || activity < dates.lastActivityAfter)) return false;
  if (dates.lastActivityBefore !== undefined && (activity === undefined || activity > dates.lastActivityBefore)) return false;

  return true;
}
```

Add at top of file (after existing imports):

```typescript
import { matchString } from "../utils/matching.js";
import { MCPValidationError } from "../utils/error-handler.js";
import {
  PullRequest,
  PullRequestComment,
  Comment,
  PaginatedResult,
  PaginationOptions,
  ApprovalState,
  PullRequestFilters,
  PullRequestSearchOptions,
  PullRequestSearchResult,
} from "../types/index.js";
```

Add a top-level helper (file-scope) above the class:

```typescript
function parseIsoDate(value: string | undefined, fieldName: string): number | undefined {
  if (value === undefined) return undefined;
  const ms = Date.parse(value);
  if (Number.isNaN(ms)) {
    throw new MCPValidationError(`${fieldName} must be ISO 8601 (e.g., 2026-01-15T00:00:00Z)`);
  }
  return ms;
}
```

- [ ] **Step 2: Build**

Run: `npm run build`
Expected: clean exit.

- [ ] **Step 3: Commit**

```bash
git add src/services/pull-request-service.ts
git commit -m "Add searchPullRequests with parallel batching and field filters"
```

---

### Task 4: Add `prs_search` MCP tool definition

**Files:**
- Modify: `src/index.ts` — add tool definition at end of `prs_list` group (after `pr_reopen`)

- [ ] **Step 1: Add the tool to the tool list**

Insert after the `pr_reopen` tool definition (around line 626):

```typescript
{
  name: "prs_search",
  description:
    "Search PRs across a repository with rich client-side filters. Server-side filters: status, authorArn (exact ARN). Client-side: title, description, sourceBranch, destinationBranch, authorArnContains (substring), date ranges. Each string filter takes a MatchSpec with mode (exact / substring / regex; default substring) and optional caseSensitive flag. Use when prs_list is too coarse — e.g., 'find all open PRs with title matching auth' or 'PRs by jane@ from the past month'. Performance: scans up to 500 PRs by default; raise maxScanned for larger repos but expect higher latency. Stops once maxResults matches are collected.",
  inputSchema: {
    type: "object",
    properties: {
      repositoryName: {
        type: "string",
        description: "Repository to search.",
      },
      filters: {
        type: "object",
        description: "Filter criteria. Combine multiple — all must match.",
        properties: {
          status: { type: "string", enum: ["OPEN", "CLOSED"] },
          authorArn: { type: "string", description: "Exact author IAM ARN — server-side filter, fastest." },
          authorArnContains: { type: "string", description: "Case-insensitive substring of author ARN — client-side filter." },
          title: { $ref: "#/definitions/matchSpec" },
          description: { $ref: "#/definitions/matchSpec" },
          sourceBranch: { $ref: "#/definitions/matchSpec" },
          destinationBranch: { $ref: "#/definitions/matchSpec" },
          createdAfter: { type: "string", description: "ISO 8601 timestamp." },
          createdBefore: { type: "string", description: "ISO 8601 timestamp." },
          lastActivityAfter: { type: "string", description: "ISO 8601 timestamp." },
          lastActivityBefore: { type: "string", description: "ISO 8601 timestamp." },
        },
      },
      maxResults: {
        type: "number",
        description: "Maximum matches to return. Default 25.",
      },
      maxScanned: {
        type: "number",
        description: "Maximum PRs to fetch before stopping (cost cap). Default 500.",
      },
    },
    required: ["repositoryName"],
    definitions: {
      matchSpec: {
        type: "object",
        description: "Match specification: a value plus how to compare it.",
        properties: {
          value: { type: "string", description: "Value or pattern. Capped at 200 chars." },
          mode: {
            type: "string",
            enum: ["exact", "substring", "regex"],
            description: "Comparison mode (default substring).",
          },
          caseSensitive: { type: "boolean", description: "Default false. Ignored for regex (use inline flags)." },
        },
        required: ["value"],
      },
    },
  },
},
```

- [ ] **Step 2: Build**

Run: `npm run build`
Expected: clean exit.

- [ ] **Step 3: Commit**

```bash
git add src/index.ts
git commit -m "Add prs_search MCP tool definition"
```

---

### Task 5: Add `prs_search` case handler

**Files:**
- Modify: `src/index.ts` — add case before the `comments_get` case (around line 1846, near other PR cases)

- [ ] **Step 1: Add the handler**

Insert after the `pr_reopen` handler (and before `comments_get`):

```typescript
case "prs_search":
  return await retryWithBackoff(async () => {
    const repositoryName = args.repositoryName as string;
    if (typeof repositoryName !== "string" || !repositoryName) {
      throw new MCPValidationError("repositoryName is required");
    }
    const filters = (args.filters as Record<string, any>) ?? {};
    const result = await this.pullRequestService.searchPullRequests(
      repositoryName,
      filters,
      {
        maxResults: typeof args.maxResults === "number" ? args.maxResults : undefined,
        maxScanned: typeof args.maxScanned === "number" ? args.maxScanned : undefined,
      }
    );
    return {
      content: [
        { type: "text", text: JSON.stringify(result, null, 2) },
      ],
    };
  });
```

- [ ] **Step 2: Build**

Run: `npm run build`
Expected: clean exit.

- [ ] **Step 3: Commit**

```bash
git add src/index.ts
git commit -m "Wire prs_search tool handler"
```

---

### Task 6: Phase 1 audit loop

- [ ] **Step 1: Dispatch a code-reviewer subagent**

Use `Agent` tool with `subagent_type: superpowers:code-reviewer`. Prompt focuses on:
- Did the search method correctly bound API costs (maxScanned cap, parallel batching)?
- Are server-side filters (status, authorArn) actually passed to ListPullRequestsCommand?
- Does matchString fail-closed on undefined targets?
- Are date filters validated before the scan begins?
- Any way the `outer:` loop fails to terminate?
- ReDoS surface in regex mode (already capped at 200 chars; verify)
- Tool description accurate?

- [ ] **Step 2: Triage findings**

For each finding: severity (CRITICAL / HIGH / MEDIUM / LOW), apply fixes for HIGH+ in the main thread.

- [ ] **Step 3: Build after fixes**

Run: `npm run build`

- [ ] **Step 4: Commit fixes**

```bash
git add -A
git commit -m "Fix prs_search audit findings"
```

---

## Phase 2 — `codecommit_op`

### Task 7: Create dispatcher with allowlist

**Files:**
- Create: `src/services/codecommit-op-dispatcher.ts`

- [ ] **Step 1: Write the dispatcher**

```typescript
// src/services/codecommit-op-dispatcher.ts
import {
  // Reads
  ListPullRequestsCommand,
  GetPullRequestCommand,
  DescribePullRequestEventsCommand,
  GetCommentsForPullRequestCommand,
  GetCommentReactionsCommand,
  GetPullRequestApprovalStatesCommand,
  EvaluatePullRequestApprovalRulesCommand,
  GetMergeConflictsCommand,
  GetMergeOptionsCommand,
  DescribeMergeConflictsCommand,
  BatchGetCommitsCommand,
  BatchGetRepositoriesCommand,
  GetCommentCommand,
  // Writes (non-merge)
  CreatePullRequestCommand,
  UpdatePullRequestTitleCommand,
  UpdatePullRequestDescriptionCommand,
  UpdatePullRequestStatusCommand,
  PostCommentForPullRequestCommand,
  PostCommentReplyCommand,
  PutCommentReactionCommand,
  UpdateCommentCommand,
  DeleteCommentContentCommand,
  UpdatePullRequestApprovalStateCommand,
} from "@aws-sdk/client-codecommit";
import { AWSAuthManager } from "../auth/aws-auth.js";
import { MCPValidationError } from "../utils/error-handler.js";

type Ctor = new (input: any) => any;

export interface OpDescriptor {
  command: Ctor;
  mode: "read" | "write";
  description: string;
}

/**
 * Allowlist of CodeCommit operations exposed via codecommit_op.
 * Excludes: any merge operation, any operation that mutates repository contents
 * (PutFile, DeleteFile, CreateCommit), any operation outside CodeCommit, any
 * approval-rule-template management (admin), any override-pull-request-approval-rules.
 */
export const ALLOWED_OPS: Record<string, OpDescriptor> = {
  // ---------- READ ----------
  "list-pull-requests":                     { command: ListPullRequestsCommand,             mode: "read",  description: "List PR IDs in a repository, filterable by status / author ARN." },
  "get-pull-request":                       { command: GetPullRequestCommand,               mode: "read",  description: "Get full PR metadata including targets and approval rules." },
  "describe-pull-request-events":           { command: DescribePullRequestEventsCommand,    mode: "read",  description: "Audit trail for a PR (creation, comments, status changes, approvals)." },
  "get-comments-for-pull-request":          { command: GetCommentsForPullRequestCommand,    mode: "read",  description: "List all comments on a PR." },
  "get-comment":                            { command: GetCommentCommand,                   mode: "read",  description: "Get a single comment by ID." },
  "get-comment-reactions":                  { command: GetCommentReactionsCommand,          mode: "read",  description: "List reactions on a comment." },
  "get-pull-request-approval-states":       { command: GetPullRequestApprovalStatesCommand, mode: "read",  description: "Approval states for a PR revision." },
  "evaluate-pull-request-approval-rules":   { command: EvaluatePullRequestApprovalRulesCommand, mode: "read", description: "Evaluate whether approval rules are satisfied." },
  "get-merge-conflicts":                    { command: GetMergeConflictsCommand,            mode: "read",  description: "Check whether a merge would conflict." },
  "describe-merge-conflicts":               { command: DescribeMergeConflictsCommand,       mode: "read",  description: "Detailed merge conflict info per file." },
  "get-merge-options":                      { command: GetMergeOptionsCommand,              mode: "read",  description: "Available merge strategies for a source/destination pair." },
  "batch-get-commits":                      { command: BatchGetCommitsCommand,              mode: "read",  description: "Bulk fetch commit metadata by ID." },
  "batch-get-repositories":                 { command: BatchGetRepositoriesCommand,         mode: "read",  description: "Bulk fetch repository metadata by name." },

  // ---------- WRITE (non-merge, PR/comment-scoped only) ----------
  "create-pull-request":                    { command: CreatePullRequestCommand,                mode: "write", description: "Open a new PR." },
  "update-pull-request-title":              { command: UpdatePullRequestTitleCommand,           mode: "write", description: "Edit a PR's title." },
  "update-pull-request-description":        { command: UpdatePullRequestDescriptionCommand,     mode: "write", description: "Edit a PR's description." },
  "update-pull-request-status":             { command: UpdatePullRequestStatusCommand,          mode: "write", description: "Open or close a PR (cannot merge via this op)." },
  "post-comment-for-pull-request":          { command: PostCommentForPullRequestCommand,        mode: "write", description: "Add a comment (general or line-specific) to a PR." },
  "post-comment-reply":                     { command: PostCommentReplyCommand,                 mode: "write", description: "Reply to an existing comment." },
  "put-comment-reaction":                   { command: PutCommentReactionCommand,               mode: "write", description: "Add or remove an emoji reaction on a comment." },
  "update-comment":                         { command: UpdateCommentCommand,                    mode: "write", description: "Edit a comment's content." },
  "delete-comment-content":                 { command: DeleteCommentContentCommand,             mode: "write", description: "Soft-delete a comment (marks as deleted)." },
  "update-pull-request-approval-state":     { command: UpdatePullRequestApprovalStateCommand,   mode: "write", description: "Approve or revoke approval on a PR revision." },
};

export class CodeCommitOpDispatcher {
  constructor(private authManager: AWSAuthManager) {}

  async run(command: string, input: Record<string, unknown>): Promise<unknown> {
    if (typeof command !== "string" || !command) {
      throw new MCPValidationError("command is required and must be a string");
    }
    const descriptor = ALLOWED_OPS[command];
    if (!descriptor) {
      throw new MCPValidationError(
        `Operation '${command}' is not in the allowlist. Use codecommit_op_list to see available operations.`
      );
    }
    if (input !== undefined && (typeof input !== "object" || Array.isArray(input) || input === null)) {
      throw new MCPValidationError("input must be an object");
    }

    const client = await this.authManager.getClient();
    const cmd = new descriptor.command(input ?? {});
    return await client.send(cmd);
  }

  list(filter?: "read" | "write"): Array<{ command: string; mode: "read" | "write"; description: string }> {
    return Object.entries(ALLOWED_OPS)
      .filter(([, d]) => !filter || d.mode === filter)
      .map(([command, d]) => ({ command, mode: d.mode, description: d.description }));
  }
}
```

- [ ] **Step 2: Build**

Run: `npm run build`
Expected: clean exit (validates that all SDK Command names exist in v3.1038).

- [ ] **Step 3: Commit**

```bash
git add src/services/codecommit-op-dispatcher.ts
git commit -m "Add CodeCommitOpDispatcher with allowlist excluding merges"
```

---

### Task 8: Wire dispatcher into the server

**Files:**
- Modify: `src/index.ts`

- [ ] **Step 1: Import + instantiate**

At the top of `src/index.ts` add to the import block:

```typescript
import { CodeCommitOpDispatcher } from "./services/codecommit-op-dispatcher.js";
```

In `AWSPRReviewerServer` class, add a private field and initialize it in the constructor next to the other services:

```typescript
private opDispatcher: CodeCommitOpDispatcher;

// in constructor, after this.diffAnalyzer = ...
this.opDispatcher = new CodeCommitOpDispatcher(this.authManager);
```

In `reinitializeServices`, also recreate the dispatcher:

```typescript
this.opDispatcher = new CodeCommitOpDispatcher(this.authManager);
```

- [ ] **Step 2: Build**

Run: `npm run build`
Expected: clean exit.

- [ ] **Step 3: Commit**

```bash
git add src/index.ts
git commit -m "Instantiate CodeCommitOpDispatcher in server"
```

---

### Task 9: Add `codecommit_op` tool definition + handler

**Files:**
- Modify: `src/index.ts`

- [ ] **Step 1: Add tool definition**

Add at the end of the tools array (just before the closing `] as Tool[]`):

```typescript
{
  name: "codecommit_op",
  description:
    "Escape-hatch dispatcher for CodeCommit operations not exposed as a dedicated tool. SCOPED: only the CodeCommit service, only the allowlist returned by codecommit_op_list. Merge operations are structurally excluded (use pr_merge if a real merge is intended). Same credentials and permissions as every other tool here. Returns the raw AWS response as JSON. Use codecommit_op_list first if you don't know the exact operation name or its input schema.",
  inputSchema: {
    type: "object",
    properties: {
      command: {
        type: "string",
        description: "Kebab-case operation name from the allowlist (e.g., 'describe-pull-request-events').",
      },
      input: {
        type: "object",
        description: "Operation input — same field names AWS CodeCommit's API expects (e.g., { pullRequestId: '123' }).",
      },
    },
    required: ["command"],
  },
},
{
  name: "codecommit_op_list",
  description: "Lists all operations available via codecommit_op, with mode (read/write) and a one-line description. Use to discover what's permitted before invoking codecommit_op. Optionally filter by mode.",
  inputSchema: {
    type: "object",
    properties: {
      mode: {
        type: "string",
        enum: ["read", "write"],
        description: "Optional filter: 'read' for read-only ops, 'write' for mutating ops (merges still excluded).",
      },
    },
  },
},
```

- [ ] **Step 2: Add case handlers**

Insert before the `default:` case in the request handler switch:

```typescript
case "codecommit_op":
  return await retryWithBackoff(async () => {
    const command = args.command as string;
    const input = (args.input as Record<string, unknown>) ?? {};
    const result = await this.opDispatcher.run(command, input);
    // Strip the SDK's $metadata noise to keep responses focused.
    const { $metadata, ...rest } = (result as any) ?? {};
    return {
      content: [
        { type: "text", text: JSON.stringify(rest, null, 2) },
      ],
    };
  });

case "codecommit_op_list": {
  const mode = args.mode as "read" | "write" | undefined;
  if (mode !== undefined && mode !== "read" && mode !== "write") {
    throw new MCPValidationError("mode must be 'read' or 'write' if provided");
  }
  const ops = this.opDispatcher.list(mode);
  return {
    content: [
      { type: "text", text: JSON.stringify(ops, null, 2) },
    ],
  };
}
```

- [ ] **Step 3: Build**

Run: `npm run build`
Expected: clean exit.

- [ ] **Step 4: Commit**

```bash
git add src/index.ts
git commit -m "Add codecommit_op and codecommit_op_list tools"
```

---

### Task 10: Phase 2 audit loop

- [ ] **Step 1: Dispatch a code-reviewer subagent**

Use `Agent` with `subagent_type: superpowers:code-reviewer`. Prompt focuses on:
- Allowlist correctness: does every Command class actually exist in `@aws-sdk/client-codecommit` v3.1038? (Build catches this, but reviewer should re-verify.)
- Are any merge / repo-content / cross-service ops accidentally in the allowlist?
- Does the dispatcher handle non-string `command`, non-object `input`, missing `command` cleanly?
- Does the `$metadata` strip leak anything important to callers?
- Tool description fits Claude's discovery flow (does it tell Claude to run codecommit_op_list first)?
- `reinitializeServices` correctly rebuilds the dispatcher after `aws_creds_refresh` / `aws_profile_switch`?

- [ ] **Step 2: Triage findings**

Apply HIGH+ fixes in main thread.

- [ ] **Step 3: Build after fixes**

Run: `npm run build`

- [ ] **Step 4: Commit fixes**

```bash
git add -A
git commit -m "Fix codecommit_op audit findings"
```

---

## Phase 3 — Documentation

### Task 11: Update README with new tools

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Add `prs_search` to the Pull Request Management Tools section**

```markdown
#### `prs_search`
Multi-field PR search across a repository. Server-side filters: status, authorArn. Client-side: title, description, source/destination branch, author ARN substring, date ranges. Each string filter accepts a MatchSpec with `mode` (exact / substring / regex; default substring) and `caseSensitive` (default false).
```json
{
  "repositoryName": "my-repo",
  "filters": {
    "status": "OPEN",
    "title": { "value": "auth", "mode": "substring" },
    "sourceBranch": { "value": "feature/", "mode": "substring" },
    "createdAfter": "2026-01-01T00:00:00Z"
  },
  "maxResults": 25,
  "maxScanned": 500
}
```
```

- [ ] **Step 2: Add `codecommit_op` + `codecommit_op_list` after the merge tools**

Add a new subsection:

```markdown
### Generic CodeCommit Operations

For operations not covered by a dedicated tool, the server exposes a scoped dispatcher backed by the AWS SDK (no host CLI install required). The allowlist excludes all merge operations and anything outside CodeCommit.

#### `codecommit_op_list`
Lists every operation the dispatcher will accept, with mode (read / write) and a description. Filter by mode optionally.
```json
{ "mode": "read" }
```

#### `codecommit_op`
Invokes a CodeCommit API operation by kebab-case name. Returns the raw AWS response.
```json
{
  "command": "describe-pull-request-events",
  "input": { "pullRequestId": "123" }
}
```
```

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "Document prs_search and codecommit_op tools"
```

---

## Self-Review Checklist (run after writing the plan)

- [x] Each spec requirement (`prs_search` filters, match modes, `codecommit_op` allowlist with merges excluded, `codecommit_op_list` companion) maps to a task above.
- [x] No "TBD" / "implement appropriate validation" / "handle edge cases" placeholders.
- [x] Type names and method signatures used in later tasks match earlier definitions (`MatchSpec`, `PullRequestFilters`, `searchPullRequests`, `CodeCommitOpDispatcher.run/.list`).
- [x] Each task is self-contained (small enough to commit separately).
- [x] No reliance on a non-existent test framework — verification is `npm run build` plus the explicit phase-end audit loops.

---

## Execution Handoff

**Plan complete and saved to `docs/superpowers/plans/2026-04-29-prs-search-and-codecommit-op.md`.**

Two execution options:

1. **Subagent-Driven (recommended by skill)** — I dispatch a fresh subagent per task, review between tasks. Best for keeping main context lean.
2. **Inline Execution** — Execute tasks in this session with checkpoints between phases. Faster iteration, more main-context use.

Given the small scope (11 tasks, ~6 of them trivial 5-line edits) and the shared codebase context already loaded, **inline execution** is more efficient. I'll proceed inline unless you redirect.
