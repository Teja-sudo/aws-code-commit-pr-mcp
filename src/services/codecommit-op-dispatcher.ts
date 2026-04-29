import {
  // Reads
  ListPullRequestsCommand,
  GetPullRequestCommand,
  DescribePullRequestEventsCommand,
  GetCommentsForPullRequestCommand,
  GetCommentReactionsCommand,
  GetCommentCommand,
  GetPullRequestApprovalStatesCommand,
  EvaluatePullRequestApprovalRulesCommand,
  GetMergeConflictsCommand,
  GetMergeOptionsCommand,
  DescribeMergeConflictsCommand,
  BatchGetCommitsCommand,
  BatchGetRepositoriesCommand,
  // Writes (non-merge, PR/comment-scoped only)
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
 *
 * Excluded by design:
 * - Any merge operation (use the dedicated pr_merge tool if a real merge is intended)
 * - Any operation that mutates repository contents (PutFile, DeleteFile, CreateCommit)
 * - Anything outside the CodeCommit service
 * - Approval-rule-template management (admin)
 * - OverridePullRequestApprovalRules (lets a user bypass approval requirements)
 */
export const ALLOWED_OPS: Record<string, OpDescriptor> = {
  // ---------- READ ----------
  "list-pull-requests":                   { command: ListPullRequestsCommand,                 mode: "read",  description: "List PR IDs in a repository, filterable by status / author ARN." },
  "get-pull-request":                     { command: GetPullRequestCommand,                   mode: "read",  description: "Get full PR metadata including targets and approval rules." },
  "describe-pull-request-events":         { command: DescribePullRequestEventsCommand,        mode: "read",  description: "Audit trail for a PR (creation, comments, status changes, approvals)." },
  "get-comments-for-pull-request":        { command: GetCommentsForPullRequestCommand,        mode: "read",  description: "List all comments on a PR (with optional commit-range filtering)." },
  "get-comment":                          { command: GetCommentCommand,                       mode: "read",  description: "Get a single comment by its ID." },
  "get-comment-reactions":                { command: GetCommentReactionsCommand,              mode: "read",  description: "List reactions on a comment." },
  "get-pull-request-approval-states":     { command: GetPullRequestApprovalStatesCommand,     mode: "read",  description: "Approval states for a PR revision." },
  "evaluate-pull-request-approval-rules": { command: EvaluatePullRequestApprovalRulesCommand, mode: "read",  description: "Evaluate whether approval rules are satisfied for a PR revision." },
  "get-merge-conflicts":                  { command: GetMergeConflictsCommand,                mode: "read",  description: "Check whether a merge would conflict (summary)." },
  "describe-merge-conflicts":             { command: DescribeMergeConflictsCommand,           mode: "read",  description: "Detailed merge conflict info per file." },
  "get-merge-options":                    { command: GetMergeOptionsCommand,                  mode: "read",  description: "Available merge strategies for a source/destination pair." },
  "batch-get-commits":                    { command: BatchGetCommitsCommand,                  mode: "read",  description: "Bulk fetch commit metadata by ID." },
  "batch-get-repositories":               { command: BatchGetRepositoriesCommand,             mode: "read",  description: "Bulk fetch repository metadata by name." },

  // ---------- WRITE (non-merge, PR/comment-scoped only) ----------
  "create-pull-request":                  { command: CreatePullRequestCommand,                mode: "write", description: "Open a new PR." },
  "update-pull-request-title":            { command: UpdatePullRequestTitleCommand,           mode: "write", description: "Edit a PR's title." },
  "update-pull-request-description":      { command: UpdatePullRequestDescriptionCommand,     mode: "write", description: "Edit a PR's description." },
  "update-pull-request-status":           { command: UpdatePullRequestStatusCommand,          mode: "write", description: "Open or close a PR. Cannot merge through this op." },
  "post-comment-for-pull-request":        { command: PostCommentForPullRequestCommand,        mode: "write", description: "Add a comment (general or line-specific) to a PR." },
  "post-comment-reply":                   { command: PostCommentReplyCommand,                 mode: "write", description: "Reply to an existing comment." },
  "put-comment-reaction":                 { command: PutCommentReactionCommand,               mode: "write", description: "Add or remove an emoji reaction on a comment." },
  "update-comment":                       { command: UpdateCommentCommand,                    mode: "write", description: "Edit a comment's content." },
  "delete-comment-content":               { command: DeleteCommentContentCommand,             mode: "write", description: "Soft-delete a comment (marks as deleted; preserves thread)." },
  "update-pull-request-approval-state":   { command: UpdatePullRequestApprovalStateCommand,   mode: "write", description: "Approve or revoke approval on a PR revision." },
};

export class CodeCommitOpDispatcher {
  constructor(private authManager: AWSAuthManager) {}

  async run(command: string, input?: Record<string, unknown> | null): Promise<unknown> {
    if (typeof command !== "string" || !command) {
      throw new MCPValidationError("command is required and must be a non-empty string");
    }
    // Use hasOwn to avoid prototype-chain lookups (e.g., "constructor", "toString").
    if (!Object.prototype.hasOwnProperty.call(ALLOWED_OPS, command)) {
      throw new MCPValidationError(
        `Operation '${command}' is not in the allowlist. Use codecommit_op_list to see available operations.`
      );
    }
    const descriptor = ALLOWED_OPS[command];
    if (
      input !== undefined &&
      input !== null &&
      (typeof input !== "object" || Array.isArray(input))
    ) {
      throw new MCPValidationError("input must be an object");
    }

    console.error(`[codecommit_op] dispatching ${command} (${descriptor.mode})`);

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
