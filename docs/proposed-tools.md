# Proposed New Tools — Feasibility & Design

This doc evaluates two proposed MCP tools, with an honest take on what's possible, what's tricky, and what to watch out for. Each section ends with a recommended path.

---

## Tool 1 — `prs_search`

### Goal

Find PRs by **title**, **author**, **repository**, **branch** (and other useful fields), with selectable **match modes**: exact, similar (substring), or regex.

### Verdict

**Fully feasible. Mostly client-side filtering. Performance is the only real constraint** — there's no AWS-server-side full-text index for PRs.

### What AWS lets us filter server-side

The CodeCommit `ListPullRequests` API has only **three** server-side filters:

| Filter | Server-side? | Notes |
|---|---|---|
| `repositoryName` | Required | We always pass it |
| `pullRequestStatus` | Yes — `OPEN` or `CLOSED` | One value at a time |
| `authorArn` | Yes | Must be a full ARN, not a partial name/email |

Everything else the user wants — title, branches, description, etc. — has to be fetched per-PR (`GetPullRequest`) and filtered in our process.

### What we can support

| Search field | How | Cost |
|---|---|---|
| Repository | Required input | Free (one filter) |
| Status (OPEN/CLOSED) | Server-side | Free |
| Author by exact ARN | Server-side via `authorArn` | Free |
| Author by name / email substring | Client-side (read `authorArn` and string-match) | Per-PR fetch needed |
| Title | Client-side (`pullRequest.title`) | Per-PR fetch needed |
| Description | Client-side (`pullRequest.description`) | Per-PR fetch needed |
| Source branch | Client-side (`targets[0].sourceReference`) | Per-PR fetch needed |
| Destination branch | Client-side (`targets[0].destinationReference`) | Per-PR fetch needed |
| Creation date / last activity range | Client-side | Per-PR fetch needed |
| Has unresolved comments | Client-side, requires extra `GetCommentsForPullRequest` per PR | 2× per-PR fetches |
| Approval state from specific user | Client-side, requires extra `GetPullRequestApprovalStates` per PR | 2× per-PR fetches |

### Match modes (per-field)

```ts
type MatchMode = "exact" | "substring" | "regex";
```

- **exact** — `value === target` (or case-insensitive variant via flag)
- **substring** — `target.toLowerCase().includes(value.toLowerCase())` (this is what most people mean by "similar")
- **regex** — `new RegExp(pattern, flags).test(target)`, with a length cap (200 chars, same as `code_search`)

A separate "fuzzy" mode (Levenshtein, n-gram) is possible but rarely worth the complexity for PR titles. Skip unless you have a clear use case.

### Performance reality

- Repos with **<100 PRs** total: search is fast (~1-2 seconds, all PRs scanned).
- Repos with **1k PRs**: ~1k `GetPullRequest` calls. At ~100 req/s with a 5-batch parallel fan-out, ~10 seconds.
- Repos with **10k PRs**: prohibitively slow without server-side filters.

Mitigation:
- **Cap `maxScanned`** with a sane default (e.g., 500). User can override.
- **Parallelize `GetPullRequest`** in batches of 5-10. AWS has request-rate limits; small concurrency is safe.
- **Apply server-side filters first** (`status`, `authorArn`) to shrink the scan set before the per-PR fan-out.
- **Stream / early-exit**: stop once `maxResults` matches collected.

### Proposed input schema

```json
{
  "repositoryName": "my-repo",
  "filters": {
    "status": "OPEN",
    "authorArn": "arn:aws:iam::123:user/jane",
    "title":           { "value": "auth", "mode": "substring" },
    "description":     { "value": "/security/i", "mode": "regex" },
    "sourceBranch":    { "value": "feature/", "mode": "substring" },
    "destinationBranch":{ "value": "main", "mode": "exact" },
    "authorContains":  "jane@",
    "createdAfter":    "2026-01-01T00:00:00Z",
    "createdBefore":   "2026-06-01T00:00:00Z"
  },
  "maxResults": 25,
  "maxScanned": 500
}
```

### Output shape

Returns an array of PR records (same shape as `pr_get`) plus scan metadata:

```json
{
  "matches": [ /* full PR objects */ ],
  "scanned": 87,
  "totalAvailable": 213,
  "truncated": false
}
```

### Effort & risk

- **Effort**: M (3-4 hours dev + tests). Reuses `listPullRequests` pagination + `getPullRequest` from existing service.
- **Risk**: Low. No new AWS APIs, no auth changes. Worst case is slow responses on huge repos — bounded by `maxScanned`.

### Recommendation

**Build it.** No design surprises. The interesting question is just *how rich the filter object should be on day one* — start with: `status`, `authorArn`, `title`, `sourceBranch`, `destinationBranch`, plus date range. Add description / approval / comment filters in a second pass if real users want them.

---

## Tool 2 — `aws_cli_run`

### Goal

A tool the AI can call with arbitrary AWS CLI args (e.g., `["sts", "get-caller-identity"]`), executed on the host using the same credentials the SDK uses. Lets Claude do AWS things this MCP server doesn't expose natively.

### Verdict

**Technically simple (~80 lines). Operationally and security-wise, this is the riskiest thing you could add to this server.** Build it, but gate it carefully.

### How it would work

Use Node's `child_process.spawn("aws", argsArray, { shell: false, env })`. Capture stdout / stderr, enforce a timeout, return `{exitCode, stdout, stderr}`. The `shell: false` part is critical — passing args as an array (not a string) means we never invoke a shell, so command injection from the AI's input is structurally impossible.

```ts
{
  name: "aws_cli_run",
  description: "Execute an AWS CLI command. Inherits the same credentials as other tools.",
  inputSchema: {
    type: "object",
    properties: {
      args: {
        type: "array",
        items: { type: "string" },
        description:
          "Argv array passed to `aws`. E.g., [\"sts\", \"get-caller-identity\"]. Do NOT include the leading \"aws\". No shell parsing — quote / escape handled automatically."
      },
      timeoutSeconds: { type: "number", description: "Max execution time (default 60)." }
    },
    required: ["args"]
  }
}
```

### Credential alignment with the SDK

Since we just refactored `aws-auth.ts` to NOT mutate `process.env`, the subprocess will inherit only what was in env at server startup. To make sure the CLI uses the same identity as the SDK:

- If `MCPConfig.awsProfile` was set: pass `--profile <name>` flag (or set `AWS_PROFILE` only on the spawn `env`, not globally).
- If `MCPConfig.region` was set: pass `--region <name>` flag (or set `AWS_REGION` on spawn env).
- If `MCPConfig.awsAccessKeyId/...` were set as static creds: set `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` / `AWS_SESSION_TOKEN` on the spawn env.
- If running on Fargate / ECS / EKS / EC2 with task role / IRSA / IMDS: the CLI auto-discovers via the same metadata endpoints. **Nothing to do.**

This gives identical-by-construction credential alignment between SDK calls and CLI calls.

### Host requirements

- **AWS CLI v2** must be installed on the machine running the MCP server.
- On Windows: `aws.exe` on PATH. On Linux/macOS: `aws` on PATH.
- In Fargate / ECS / EKS containers: add `aws-cli` to the container image (extra ~100 MB layer).

We should detect missing-CLI at server startup and log a clear warning, so the tool fails fast rather than during a request.

### Output limits

A single `aws s3 ls --recursive` on a huge bucket can produce gigabytes. We need:
- **Cap stdout to ~1 MB** (with `truncated: true` flag in response)
- **Cap stderr to ~256 KB**
- Default **60-second timeout**, max 600 seconds

### The actual concern: blast radius

**This is the part that needs explicit thought before merging the tool.**

Today the README publishes a tight CodeCommit-only IAM policy. If your deployment uses that exact policy, `aws_cli_run` is bounded — the AI can only successfully run CodeCommit commands.

But:

- On a developer laptop with `AdministratorAccess` profile, the AI can run `aws iam delete-user`, `aws s3 rm s3://bucket --recursive`, `aws lambda delete-function`, `aws ec2 terminate-instances`, etc.
- On a CI/CD machine with a wide deployment role, similar story.
- The MCP host (Claude Desktop / Claude Code) doesn't currently have a "ask user to confirm before running this tool" UX for unbounded commands.

The MCP server author has no way to enforce least privilege from inside the process — that's the IAM role's job. The honest framing: **`aws_cli_run` makes the tool only as safe as the IAM identity it runs under.**

### Mitigation options (non-exclusive)

1. **Opt-in env var.** Don't expose the tool unless `MCP_ENABLE_AWS_CLI=true` is set at server startup. Default off. Cheap, effective.

2. **Read-only allowlist.** Refuse args where `argv[0]` isn't in a whitelist (`["sts", "iam list-*", "s3 ls", ...]`). Hard to maintain — every AWS service has its own verbs.

3. **Read-only verb prefix.** Only allow subcommands starting with `list-`, `get-`, `describe-`, `head-`, `download-` (S3 special case). Easier to maintain than a full allowlist; rejects obvious mutations. Imperfect (e.g., `aws sts assume-role` is read-only-ish but not prefixed).

4. **Explicit confirmation in tool description.** Make the tool description tell the AI: "this can run any AWS command including destructive ones; only use it when the user has explicitly asked."

5. **Logging.** Append every invocation (with full argv) to a per-session audit log so the user can see what the AI ran. Cheap visibility.

My take: **#1 + #4 + #5 give you 90% of the safety with 10% of the complexity.** Start there.

### Effort & risk

- **Effort**: S-M (4-5 hours dev + the security framing). Subprocess plumbing is well-trodden; the time goes into env-var handling, output caps, and writing the security-warning docs.
- **Risk**: HIGH on the trust dimension; LOW on the implementation dimension. The code itself is simple. The blast radius is what you're signing up for.

### Recommendation

**Build it, but:**
1. Default to **disabled** behind `MCP_ENABLE_AWS_CLI=true` env var.
2. Big stark warning in the README + tool description: "this tool inherits the AWS identity of the MCP server and can run any AWS command those credentials allow, including destructive ones."
3. Log every invocation's argv to stderr so the user has a paper trail.
4. **Check at startup** whether `aws` is on PATH; if not, don't register the tool (don't fail the whole server).

Skip the read-only allowlist complexity for v1 unless your specific deployment context calls for it.

### Strong alternative to consider first

Before adding a generic CLI passthrough, check whether the actual gaps in our current tool set could be filled by **specific named tools** (e.g., `pr_search`, `pr_activity_log`, `repo_create`). Most "I wish Claude could do X with AWS" use cases turn out to be 3-5 specific operations, not "the entire AWS API". Specific tools have:

- Known input validation
- Known output shapes the AI can rely on
- Bounded IAM permission requirements
- Better tool-discovery (descriptions explain what they do)

A generic `aws_cli_run` is the right answer **after** you've added the specific tools you need and discovered there's still a long tail of one-offs.

---

## Recommended sequencing

1. **`prs_search` first.** Concrete, low-risk, fills a real gap.
2. **Inventory specific AWS operations you actually need** that aren't in the current tool set. Pick the top 3-5 and propose them as tools. (Happy to enumerate likely ones.)
3. **`aws_cli_run` only if** the long-tail of one-offs justifies it. Gate it as described above.

---

## Open questions to confirm before implementation

- **`prs_search`**: do you want approvals / comment filters in v1 (slower, more API calls), or just title/branch/author/date for v1 and approvals later?
- **`aws_cli_run`**: what's the deployment target where this tool would live — your laptop with broad access, Fargate with scoped role, or both? That changes the safety story.
- **Generic tools we should add instead?** e.g., `pr_activity_recent` (PRs with activity in last N days), `pr_diff_summary` (PR's full diff in one call), `repo_recent_commits`?
