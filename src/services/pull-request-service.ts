import {
  ListPullRequestsCommand,
  GetPullRequestCommand,
  CreatePullRequestCommand,
  UpdatePullRequestTitleCommand,
  UpdatePullRequestDescriptionCommand,
  UpdatePullRequestStatusCommand,
  GetCommentsForPullRequestCommand,
  PostCommentForPullRequestCommand,
  UpdateCommentCommand,
  DeleteCommentContentCommand,
  PostCommentReplyCommand,
  GetPullRequestApprovalStatesCommand,
  UpdatePullRequestApprovalStateCommand,
  EvaluatePullRequestApprovalRulesCommand,
  GetMergeConflictsCommand,
  GetMergeOptionsCommand,
  MergePullRequestByFastForwardCommand,
  MergePullRequestBySquashCommand,
  MergePullRequestByThreeWayCommand,
} from "@aws-sdk/client-codecommit";
import { AWSAuthManager } from "../auth/aws-auth.js";
import { RepositoryService } from "./repository-service.js";
import { LinePositionCalculator } from "../utils/line-position-calculator.js";
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

// Strict ISO 8601: yyyy-mm-dd, optionally with Thh:mm:ss(.fraction)?(Z|+hh:mm|-hh:mm)?
const ISO_8601 = /^\d{4}-\d{2}-\d{2}(T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+\-]\d{2}:?\d{2})?)?$/;

function parseIsoDate(value: string | undefined, fieldName: string): number | undefined {
  if (value === undefined) return undefined;
  if (typeof value !== "string") {
    throw new MCPValidationError(`${fieldName} must be a string`);
  }
  if (!ISO_8601.test(value)) {
    throw new MCPValidationError(
      `${fieldName} must be ISO 8601 (e.g., 2026-01-15 or 2026-01-15T00:00:00Z)`
    );
  }
  const ms = Date.parse(value);
  if (Number.isNaN(ms)) {
    throw new MCPValidationError(`${fieldName} could not be parsed as a date`);
  }
  return ms;
}

export class PullRequestService {
  private repositoryService: RepositoryService;
  private linePositionCalculator: LinePositionCalculator;

  constructor(private authManager: AWSAuthManager) {
    this.repositoryService = new RepositoryService(authManager);
    this.linePositionCalculator = new LinePositionCalculator(
      this.repositoryService
    );
  }

  async listPullRequests(
    repositoryName: string,
    pullRequestStatus: "OPEN" | "CLOSED" = "OPEN",
    options: PaginationOptions = {}
  ): Promise<PaginatedResult<string>> {
    const client = await this.authManager.getClient();
    const command = new ListPullRequestsCommand({
      repositoryName,
      pullRequestStatus,
      nextToken: options.nextToken,
      maxResults: options.maxResults || 100,
    });

    const response = await client.send(command);

    return {
      items: response.pullRequestIds || [],
      nextToken: response.nextToken,
    };
  }

  async getPullRequest(pullRequestId: string): Promise<PullRequest> {
    const client = await this.authManager.getClient();
    const command = new GetPullRequestCommand({ pullRequestId });

    const response = await client.send(command);
    const pr = response.pullRequest;

    if (!pr) {
      throw new Error(`Pull request ${pullRequestId} not found`);
    }

    return {
      pullRequestId: pr.pullRequestId || "",
      title: pr.title || "",
      description: pr.description,
      lastActivityDate: pr.lastActivityDate,
      creationDate: pr.creationDate,
      pullRequestStatus: pr.pullRequestStatus as "OPEN" | "CLOSED",
      authorArn: pr.authorArn || "",
      revisionId: pr.revisionId || "",
      clientRequestToken: pr.clientRequestToken,
      targets: (pr.pullRequestTargets || []).map((target) => ({
        repositoryName: target.repositoryName || "",
        sourceReference: target.sourceReference || "",
        destinationReference: target.destinationReference,
        destinationCommit: target.destinationCommit,
        sourceCommit: target.sourceCommit,
        mergeBase: target.mergeBase,
        mergeMetadata: target.mergeMetadata
          ? {
              isMerged: target.mergeMetadata.isMerged || false,
              mergedBy: target.mergeMetadata.mergedBy,
              mergeCommitId: target.mergeMetadata.mergeCommitId,
              mergeOption: target.mergeMetadata.mergeOption,
            }
          : undefined,
      })),
      approvalRules: (pr.approvalRules || []).map((rule) => ({
        approvalRuleId: rule.approvalRuleId || "",
        approvalRuleName: rule.approvalRuleName || "",
        approvalRuleContent: rule.approvalRuleContent || "",
        ruleContentSha256: rule.ruleContentSha256 || "",
        lastModifiedDate: rule.lastModifiedDate,
        creationDate: rule.creationDate,
        lastModifiedUser: rule.lastModifiedUser,
      })),
    };
  }

  /**
   * Multi-field PR search. Server-side filters: status, authorArn (exact ARN).
   * Everything else is filtered client-side after fetching each PR. Bounded by
   * maxScanned (default 500) so large repos can't run unbounded.
   */
  async searchPullRequests(
    repositoryName: string,
    filters: PullRequestFilters,
    options: PullRequestSearchOptions = {}
  ): Promise<PullRequestSearchResult> {
    if (!repositoryName || typeof repositoryName !== "string") {
      throw new MCPValidationError("repositoryName is required");
    }
    if (filters.status !== undefined && filters.status !== "OPEN" && filters.status !== "CLOSED") {
      throw new MCPValidationError("filters.status must be 'OPEN' or 'CLOSED'");
    }
    if (
      filters.authorArnContains !== undefined &&
      typeof filters.authorArnContains !== "string"
    ) {
      throw new MCPValidationError("filters.authorArnContains must be a string");
    }
    if (options.maxResults !== undefined) {
      if (!Number.isInteger(options.maxResults) || options.maxResults < 1) {
        throw new MCPValidationError("maxResults must be a positive integer");
      }
    }
    if (options.maxScanned !== undefined) {
      if (!Number.isInteger(options.maxScanned) || options.maxScanned < 1) {
        throw new MCPValidationError("maxScanned must be a positive integer");
      }
    }

    const maxResults = options.maxResults ?? 25;
    const maxScanned = options.maxScanned ?? 500;
    const concurrency = 5;

    const dateBounds = {
      createdAfter: parseIsoDate(filters.createdAfter, "createdAfter"),
      createdBefore: parseIsoDate(filters.createdBefore, "createdBefore"),
      lastActivityAfter: parseIsoDate(filters.lastActivityAfter, "lastActivityAfter"),
      lastActivityBefore: parseIsoDate(filters.lastActivityBefore, "lastActivityBefore"),
    };

    const matches: PullRequest[] = [];
    let scanned = 0;
    let nextToken: string | undefined;
    const client = await this.authManager.getClient();

    outer: while (scanned < maxScanned && matches.length < maxResults) {
      const listResp = await client.send(
        new ListPullRequestsCommand({
          repositoryName,
          pullRequestStatus: filters.status,
          // Coerce empty string to undefined so AWS doesn't reject it.
          authorArn: filters.authorArn || undefined,
          nextToken,
          maxResults: 100,
        })
      );
      const ids = listResp.pullRequestIds ?? [];
      if (ids.length === 0 && !listResp.nextToken) break;

      for (let i = 0; i < ids.length; i += concurrency) {
        if (scanned >= maxScanned || matches.length >= maxResults) break outer;
        const batch = ids.slice(i, i + concurrency);
        const prs = await Promise.all(batch.map((id) => this.getPullRequest(id)));
        scanned += prs.length;

        for (const pr of prs) {
          if (this.matchesFilters(pr, filters, dateBounds)) {
            matches.push(pr);
            if (matches.length >= maxResults) break;
          }
        }
      }

      // Stop if AWS exhausted the list or echoed the same token (defensive).
      const newToken = listResp.nextToken;
      if (!newToken || newToken === nextToken) break;
      nextToken = newToken;
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
    if (
      filters.authorArnContains &&
      !pr.authorArn.toLowerCase().includes(filters.authorArnContains.toLowerCase())
    ) {
      return false;
    }
    if (filters.title && !matchString(pr.title, filters.title)) return false;
    if (filters.description && !matchString(pr.description, filters.description)) return false;

    const target = pr.targets[0];
    if (filters.sourceBranch && !matchString(target?.sourceReference, filters.sourceBranch)) {
      return false;
    }
    if (
      filters.destinationBranch &&
      !matchString(target?.destinationReference, filters.destinationBranch)
    ) {
      return false;
    }

    const created = pr.creationDate?.getTime();
    if (dates.createdAfter !== undefined && (created === undefined || created < dates.createdAfter)) {
      return false;
    }
    if (dates.createdBefore !== undefined && (created === undefined || created > dates.createdBefore)) {
      return false;
    }

    const activity = pr.lastActivityDate?.getTime();
    if (
      dates.lastActivityAfter !== undefined &&
      (activity === undefined || activity < dates.lastActivityAfter)
    ) {
      return false;
    }
    if (
      dates.lastActivityBefore !== undefined &&
      (activity === undefined || activity > dates.lastActivityBefore)
    ) {
      return false;
    }

    return true;
  }

  async createPullRequest(
    repositoryName: string,
    title: string,
    description: string,
    sourceReference: string,
    destinationReference: string,
    clientRequestToken?: string
  ): Promise<PullRequest> {
    const client = await this.authManager.getClient();
    const command = new CreatePullRequestCommand({
      title,
      description,
      targets: [
        {
          repositoryName,
          sourceReference,
          destinationReference,
        },
      ],
      clientRequestToken,
    });

    const response = await client.send(command);

    if (!response.pullRequest) {
      throw new Error("Failed to create pull request");
    }

    return await this.getPullRequest(response.pullRequest.pullRequestId!);
  }

  async updatePullRequestTitle(
    pullRequestId: string,
    title: string
  ): Promise<PullRequest> {
    const client = await this.authManager.getClient();
    const command = new UpdatePullRequestTitleCommand({
      pullRequestId,
      title,
    });

    await client.send(command);
    return await this.getPullRequest(pullRequestId);
  }

  async updatePullRequestDescription(
    pullRequestId: string,
    description: string
  ): Promise<PullRequest> {
    const client = await this.authManager.getClient();
    const command = new UpdatePullRequestDescriptionCommand({
      pullRequestId,
      description,
    });

    await client.send(command);
    return await this.getPullRequest(pullRequestId);
  }

  async closePullRequest(pullRequestId: string): Promise<PullRequest> {
    const client = await this.authManager.getClient();
    const command = new UpdatePullRequestStatusCommand({
      pullRequestId,
      pullRequestStatus: "CLOSED",
    });

    await client.send(command);
    return await this.getPullRequest(pullRequestId);
  }

  async reopenPullRequest(pullRequestId: string): Promise<PullRequest> {
    const client = await this.authManager.getClient();
    const command = new UpdatePullRequestStatusCommand({
      pullRequestId,
      pullRequestStatus: "OPEN",
    });

    await client.send(command);
    return await this.getPullRequest(pullRequestId);
  }

  async getComments(
    pullRequestId: string,
    repositoryName?: string,
    beforeCommitId?: string,
    afterCommitId?: string,
    options: PaginationOptions = {}
  ): Promise<PaginatedResult<PullRequestComment>> {
    const client = await this.authManager.getClient();

    // AWS API has conditional requirements:
    // 1. Simple usage: Only pullRequestId (gets all comments)
    // 2. Filtered usage: pullRequestId + repositoryName + beforeCommitId + afterCommitId (filtered by commit range)
    const commandParams: any = {
      pullRequestId,
      nextToken: options.nextToken,
      maxResults: options.maxResults || 100,
    };

    // If repositoryName is provided, we MUST also have both commit IDs for filtered usage
    if (repositoryName && beforeCommitId && afterCommitId) {
      commandParams.repositoryName = repositoryName;
      commandParams.beforeCommitId = beforeCommitId;
      commandParams.afterCommitId = afterCommitId;
    }
    // If repositoryName is provided but commit IDs are missing, that's an error
    else if (repositoryName && (!beforeCommitId || !afterCommitId)) {
      throw new Error("When repositoryName is provided, both beforeCommitId and afterCommitId are required for AWS CodeCommit API");
    }
    // Otherwise, use simple mode with only pullRequestId

    const command = new GetCommentsForPullRequestCommand(commandParams);

    const response = await client.send(command);

    const comments: PullRequestComment[] = (
      response.commentsForPullRequestData || []
    )
      .flatMap((data) => data.comments || [])
      .map((comment) => ({
        commentId: comment.commentId || "",
        content: comment.content || "",
        inReplyTo: comment.inReplyTo,
        creationDate: comment.creationDate,
        lastModifiedDate: comment.lastModifiedDate,
        authorArn: comment.authorArn || "",
        deleted: comment.deleted || false,
        clientRequestToken: comment.clientRequestToken,
        pullRequestId,
        repositoryName,
        beforeCommitId,
        afterCommitId,
        location: (comment as any).location
          ? {
              filePath: (comment as any).location.filePath || "",
              filePosition: (comment as any).location.filePosition,
              relativeFileVersion: (comment as any).location
                .relativeFileVersion as "BEFORE" | "AFTER",
            }
          : undefined,
      }));

    return {
      items: comments,
      nextToken: response.nextToken,
    };
  }

  async postComment(
    pullRequestId: string,
    repositoryName: string,
    beforeCommitId: string,
    afterCommitId: string,
    content: string,
    location?: {
      filePath: string;
      filePosition?: number;
      relativeFileVersion: "BEFORE" | "AFTER";
    },
    clientRequestToken?: string
  ): Promise<PullRequestComment> {
    const client = await this.authManager.getClient();

    let validatedLocation = location;

    // Validate and adjust line position using proper diff-based calculation
    if (location && location.filePosition) {
      try {
        const adjustedLinePosition =
          await this.linePositionCalculator.validateAndAdjustLinePosition(
            repositoryName,
            location.filePath,
            location.filePosition,
            location.relativeFileVersion === "BEFORE"
              ? beforeCommitId
              : afterCommitId,
            location.relativeFileVersion
          );

        validatedLocation = {
          ...location,
          filePosition: adjustedLinePosition,
        };

        console.error("Line position validated and adjusted:", {
          originalPosition: location.filePosition,
          adjustedPosition: adjustedLinePosition,
          filePath: location.filePath,
          relativeFileVersion: location.relativeFileVersion,
        });
      } catch (error) {
        console.error(
          "Failed to validate line position, using original:",
          error
        );
        // Keep original location if validation fails
      }
    }

    const command = new PostCommentForPullRequestCommand({
      pullRequestId,
      repositoryName,
      beforeCommitId,
      afterCommitId,
      content,
      location: validatedLocation,
      clientRequestToken,
    });

    console.error("Posting comment with validated location:", {
      filePath: validatedLocation?.filePath,
      filePosition: validatedLocation?.filePosition,
      relativeFileVersion: validatedLocation?.relativeFileVersion,
    });

    const response = await client.send(command);

    if (!response.comment) {
      throw new Error("Failed to post comment");
    }

    const comment = response.comment;
    return {
      commentId: comment.commentId || "",
      content: comment.content || "",
      inReplyTo: comment.inReplyTo,
      creationDate: comment.creationDate,
      lastModifiedDate: comment.lastModifiedDate,
      authorArn: comment.authorArn || "",
      deleted: comment.deleted || false,
      clientRequestToken: comment.clientRequestToken,
      pullRequestId,
      repositoryName,
      beforeCommitId,
      afterCommitId,
      location: validatedLocation
        ? {
            filePath: validatedLocation.filePath,
            filePosition: validatedLocation.filePosition,
            relativeFileVersion: validatedLocation.relativeFileVersion,
          }
        : undefined,
    };
  }

  async updateComment(commentId: string, content: string): Promise<Comment> {
    const client = await this.authManager.getClient();
    const command = new UpdateCommentCommand({
      commentId,
      content,
    });

    const response = await client.send(command);

    if (!response.comment) {
      throw new Error("Failed to update comment");
    }

    const comment = response.comment;
    return {
      commentId: comment.commentId || "",
      content: comment.content || "",
      inReplyTo: comment.inReplyTo,
      creationDate: comment.creationDate,
      lastModifiedDate: comment.lastModifiedDate,
      authorArn: comment.authorArn || "",
      deleted: comment.deleted || false,
      clientRequestToken: comment.clientRequestToken,
    };
  }

  async deleteComment(commentId: string): Promise<Comment> {
    const client = await this.authManager.getClient();
    const command = new DeleteCommentContentCommand({ commentId });

    const response = await client.send(command);

    if (!response.comment) {
      throw new Error("Failed to delete comment");
    }

    const comment = response.comment;
    return {
      commentId: comment.commentId || "",
      content: comment.content || "",
      inReplyTo: comment.inReplyTo,
      creationDate: comment.creationDate,
      lastModifiedDate: comment.lastModifiedDate,
      authorArn: comment.authorArn || "",
      deleted: comment.deleted || false,
      clientRequestToken: comment.clientRequestToken,
    };
  }

  async replyToComment(
    inReplyTo: string,
    content: string,
    clientRequestToken?: string
  ): Promise<Comment> {
    const client = await this.authManager.getClient();
    const command = new PostCommentReplyCommand({
      inReplyTo,
      content,
      clientRequestToken,
    });

    const response = await client.send(command);

    if (!response.comment) {
      throw new Error("Failed to post reply");
    }

    const comment = response.comment;
    return {
      commentId: comment.commentId || "",
      content: comment.content || "",
      inReplyTo: comment.inReplyTo,
      creationDate: comment.creationDate,
      lastModifiedDate: comment.lastModifiedDate,
      authorArn: comment.authorArn || "",
      deleted: comment.deleted || false,
      clientRequestToken: comment.clientRequestToken,
    };
  }

  async getApprovalStates(
    pullRequestId: string,
    revisionId: string
  ): Promise<ApprovalState[]> {
    const client = await this.authManager.getClient();
    const command = new GetPullRequestApprovalStatesCommand({
      pullRequestId,
      revisionId,
    });

    const response = await client.send(command);

    return (response.approvals || []).map((approval) => ({
      revisionId: revisionId,
      approvalStatus: approval.approvalState as "APPROVE" | "REVOKE",
    }));
  }

  async updateApprovalState(
    pullRequestId: string,
    revisionId: string,
    approvalStatus: "APPROVE" | "REVOKE"
  ): Promise<void> {
    const client = await this.authManager.getClient();
    const command = new UpdatePullRequestApprovalStateCommand({
      pullRequestId,
      revisionId,
      approvalState: approvalStatus,
    });

    await client.send(command);
  }

  async evaluateApprovalRules(
    pullRequestId: string,
    revisionId: string
  ): Promise<any> {
    const client = await this.authManager.getClient();
    const command = new EvaluatePullRequestApprovalRulesCommand({
      pullRequestId,
      revisionId,
    });

    const response = await client.send(command);
    return response.evaluation;
  }

  async getMergeConflicts(
    repositoryName: string,
    destinationCommitSpecifier: string,
    sourceCommitSpecifier: string,
    mergeOption: "FAST_FORWARD_MERGE" | "SQUASH_MERGE" | "THREE_WAY_MERGE"
  ): Promise<any> {
    const client = await this.authManager.getClient();
    const command = new GetMergeConflictsCommand({
      repositoryName,
      destinationCommitSpecifier,
      sourceCommitSpecifier,
      mergeOption,
    });

    const response = await client.send(command);
    return {
      mergeable: response.mergeable,
      destinationCommitId: response.destinationCommitId,
      sourceCommitId: response.sourceCommitId,
      baseCommitId: response.baseCommitId,
      conflictMetadataList: response.conflictMetadataList,
    };
  }

  async getMergeOptions(
    repositoryName: string,
    sourceCommitSpecifier: string,
    destinationCommitSpecifier: string
  ): Promise<string[]> {
    const client = await this.authManager.getClient();
    const command = new GetMergeOptionsCommand({
      repositoryName,
      sourceCommitSpecifier,
      destinationCommitSpecifier,
    });

    const response = await client.send(command);
    return response.mergeOptions || [];
  }

  async mergePullRequest(
    pullRequestId: string,
    repositoryName: string,
    mergeOption: "FAST_FORWARD_MERGE" | "SQUASH_MERGE" | "THREE_WAY_MERGE",
    commitMessage?: string,
    authorName?: string,
    email?: string
  ): Promise<any> {
    const client = await this.authManager.getClient();

    let command;
    const baseParams = {
      pullRequestId,
      repositoryName,
    };

    switch (mergeOption) {
      case "FAST_FORWARD_MERGE":
        command = new MergePullRequestByFastForwardCommand(baseParams);
        break;
      case "SQUASH_MERGE":
        command = new MergePullRequestBySquashCommand({
          ...baseParams,
          commitMessage,
          authorName,
          email,
        });
        break;
      case "THREE_WAY_MERGE":
        command = new MergePullRequestByThreeWayCommand({
          ...baseParams,
          commitMessage,
          authorName,
          email,
        });
        break;
      default:
        throw new Error(`Unsupported merge option: ${mergeOption}`);
    }

    const response = await client.send(command);
    return {
      pullRequest: response.pullRequest,
      commitId: (response as any).commitId,
    };
  }
}
