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
} from '@aws-sdk/client-codecommit';
import { AWSAuthManager } from '../auth/aws-auth';
import { PullRequest, PullRequestComment, Comment, PaginatedResult, PaginationOptions, ApprovalState } from '../types';

export class PullRequestService {
  constructor(private authManager: AWSAuthManager) {}

  async listPullRequests(
    repositoryName: string,
    pullRequestStatus: 'OPEN' | 'CLOSED' = 'OPEN',
    options: PaginationOptions = {}
  ): Promise<PaginatedResult<string>> {
    const client = this.authManager.getClient();
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
    const client = this.authManager.getClient();
    const command = new GetPullRequestCommand({ pullRequestId });

    const response = await client.send(command);
    const pr = response.pullRequest;

    if (!pr) {
      throw new Error(`Pull request ${pullRequestId} not found`);
    }

    return {
      pullRequestId: pr.pullRequestId || '',
      title: pr.title || '',
      description: pr.description,
      lastActivityDate: pr.lastActivityDate,
      creationDate: pr.creationDate,
      pullRequestStatus: pr.pullRequestStatus as 'OPEN' | 'CLOSED',
      authorArn: pr.authorArn || '',
      revisionId: pr.revisionId || '',
      clientRequestToken: pr.clientRequestToken,
      targets: (pr.pullRequestTargets || []).map(target => ({
        repositoryName: target.repositoryName || '',
        sourceReference: target.sourceReference || '',
        destinationReference: target.destinationReference,
        destinationCommit: target.destinationCommit,
        sourceCommit: target.sourceCommit,
        mergeBase: target.mergeBase,
        mergeMetadata: target.mergeMetadata ? {
          isMerged: target.mergeMetadata.isMerged || false,
          mergedBy: target.mergeMetadata.mergedBy,
          mergeCommitId: target.mergeMetadata.mergeCommitId,
          mergeOption: target.mergeMetadata.mergeOption,
        } : undefined,
      })),
      approvalRules: (pr.approvalRules || []).map(rule => ({
        approvalRuleId: rule.approvalRuleId || '',
        approvalRuleName: rule.approvalRuleName || '',
        approvalRuleContent: rule.approvalRuleContent || '',
        ruleContentSha256: rule.ruleContentSha256 || '',
        lastModifiedDate: rule.lastModifiedDate,
        creationDate: rule.creationDate,
        lastModifiedUser: rule.lastModifiedUser,
      })),
    };
  }

  async createPullRequest(
    repositoryName: string,
    title: string,
    description: string,
    sourceReference: string,
    destinationReference: string,
    clientRequestToken?: string
  ): Promise<PullRequest> {
    const client = this.authManager.getClient();
    const command = new CreatePullRequestCommand({
      title,
      description,
      targets: [{
        repositoryName,
        sourceReference,
        destinationReference,
      }],
      clientRequestToken,
    });

    const response = await client.send(command);
    
    if (!response.pullRequest) {
      throw new Error('Failed to create pull request');
    }

    return await this.getPullRequest(response.pullRequest.pullRequestId!);
  }

  async updatePullRequestTitle(pullRequestId: string, title: string): Promise<PullRequest> {
    const client = this.authManager.getClient();
    const command = new UpdatePullRequestTitleCommand({
      pullRequestId,
      title,
    });

    await client.send(command);
    return await this.getPullRequest(pullRequestId);
  }

  async updatePullRequestDescription(pullRequestId: string, description: string): Promise<PullRequest> {
    const client = this.authManager.getClient();
    const command = new UpdatePullRequestDescriptionCommand({
      pullRequestId,
      description,
    });

    await client.send(command);
    return await this.getPullRequest(pullRequestId);
  }

  async closePullRequest(pullRequestId: string): Promise<PullRequest> {
    const client = this.authManager.getClient();
    const command = new UpdatePullRequestStatusCommand({
      pullRequestId,
      pullRequestStatus: 'CLOSED',
    });

    await client.send(command);
    return await this.getPullRequest(pullRequestId);
  }

  async reopenPullRequest(pullRequestId: string): Promise<PullRequest> {
    const client = this.authManager.getClient();
    const command = new UpdatePullRequestStatusCommand({
      pullRequestId,
      pullRequestStatus: 'OPEN',
    });

    await client.send(command);
    return await this.getPullRequest(pullRequestId);
  }

  async getComments(
    pullRequestId: string,
    repositoryName: string,
    beforeCommitId?: string,
    afterCommitId?: string,
    options: PaginationOptions = {}
  ): Promise<PaginatedResult<PullRequestComment>> {
    const client = this.authManager.getClient();
    const command = new GetCommentsForPullRequestCommand({
      pullRequestId,
      repositoryName,
      beforeCommitId,
      afterCommitId,
      nextToken: options.nextToken,
      maxResults: options.maxResults || 100,
    });

    const response = await client.send(command);
    
    const comments: PullRequestComment[] = (response.commentsForPullRequestData || [])
      .flatMap(data => (data.comments || []))
      .map(comment => ({
        commentId: comment.commentId || '',
        content: comment.content || '',
        inReplyTo: comment.inReplyTo,
        creationDate: comment.creationDate,
        lastModifiedDate: comment.lastModifiedDate,
        authorArn: comment.authorArn || '',
        deleted: comment.deleted || false,
        clientRequestToken: comment.clientRequestToken,
        pullRequestId,
        repositoryName,
        beforeCommitId,
        afterCommitId,
        location: undefined,
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
      relativeFileVersion: 'BEFORE' | 'AFTER';
    },
    clientRequestToken?: string
  ): Promise<PullRequestComment> {
    const client = this.authManager.getClient();
    const command = new PostCommentForPullRequestCommand({
      pullRequestId,
      repositoryName,
      beforeCommitId,
      afterCommitId,
      content,
      location,
      clientRequestToken,
    });

    const response = await client.send(command);
    
    if (!response.comment) {
      throw new Error('Failed to post comment');
    }

    const comment = response.comment;
    return {
      commentId: comment.commentId || '',
      content: comment.content || '',
      inReplyTo: comment.inReplyTo,
      creationDate: comment.creationDate,
      lastModifiedDate: comment.lastModifiedDate,
      authorArn: comment.authorArn || '',
      deleted: comment.deleted || false,
      clientRequestToken: comment.clientRequestToken,
      pullRequestId,
      repositoryName,
      beforeCommitId,
      afterCommitId,
      location: undefined,
    };
  }

  async updateComment(commentId: string, content: string): Promise<Comment> {
    const client = this.authManager.getClient();
    const command = new UpdateCommentCommand({
      commentId,
      content,
    });

    const response = await client.send(command);
    
    if (!response.comment) {
      throw new Error('Failed to update comment');
    }

    const comment = response.comment;
    return {
      commentId: comment.commentId || '',
      content: comment.content || '',
      inReplyTo: comment.inReplyTo,
      creationDate: comment.creationDate,
      lastModifiedDate: comment.lastModifiedDate,
      authorArn: comment.authorArn || '',
      deleted: comment.deleted || false,
      clientRequestToken: comment.clientRequestToken,
    };
  }

  async deleteComment(commentId: string): Promise<Comment> {
    const client = this.authManager.getClient();
    const command = new DeleteCommentContentCommand({ commentId });

    const response = await client.send(command);
    
    if (!response.comment) {
      throw new Error('Failed to delete comment');
    }

    const comment = response.comment;
    return {
      commentId: comment.commentId || '',
      content: comment.content || '',
      inReplyTo: comment.inReplyTo,
      creationDate: comment.creationDate,
      lastModifiedDate: comment.lastModifiedDate,
      authorArn: comment.authorArn || '',
      deleted: comment.deleted || false,
      clientRequestToken: comment.clientRequestToken,
    };
  }

  async replyToComment(
    pullRequestId: string,
    repositoryName: string,
    beforeCommitId: string,
    afterCommitId: string,
    inReplyTo: string,
    content: string,
    clientRequestToken?: string
  ): Promise<Comment> {
    const client = this.authManager.getClient();
    const command = new PostCommentReplyCommand({
      inReplyTo,
      content,
      clientRequestToken,
    });

    const response = await client.send(command);
    
    if (!response.comment) {
      throw new Error('Failed to post reply');
    }

    const comment = response.comment;
    return {
      commentId: comment.commentId || '',
      content: comment.content || '',
      inReplyTo: comment.inReplyTo,
      creationDate: comment.creationDate,
      lastModifiedDate: comment.lastModifiedDate,
      authorArn: comment.authorArn || '',
      deleted: comment.deleted || false,
      clientRequestToken: comment.clientRequestToken,
    };
  }

  async getApprovalStates(pullRequestId: string, revisionId: string): Promise<ApprovalState[]> {
    const client = this.authManager.getClient();
    const command = new GetPullRequestApprovalStatesCommand({
      pullRequestId,
      revisionId,
    });

    const response = await client.send(command);
    
    return (response.approvals || []).map(approval => ({
      revisionId: revisionId,
      approvalStatus: approval.approvalState as 'APPROVE' | 'REVOKE',
    }));
  }

  async updateApprovalState(
    pullRequestId: string,
    revisionId: string,
    approvalStatus: 'APPROVE' | 'REVOKE'
  ): Promise<void> {
    const client = this.authManager.getClient();
    const command = new UpdatePullRequestApprovalStateCommand({
      pullRequestId,
      revisionId,
      approvalState: approvalStatus,
    });

    await client.send(command);
  }

  async evaluateApprovalRules(pullRequestId: string, revisionId: string): Promise<any> {
    const client = this.authManager.getClient();
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
    mergeOption: 'FAST_FORWARD_MERGE' | 'SQUASH_MERGE' | 'THREE_WAY_MERGE'
  ): Promise<any> {
    const client = this.authManager.getClient();
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
    const client = this.authManager.getClient();
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
    mergeOption: 'FAST_FORWARD_MERGE' | 'SQUASH_MERGE' | 'THREE_WAY_MERGE',
    commitMessage?: string,
    authorName?: string,
    email?: string
  ): Promise<any> {
    const client = this.authManager.getClient();
    
    let command;
    const baseParams = {
      pullRequestId,
      repositoryName,
    };

    switch (mergeOption) {
      case 'FAST_FORWARD_MERGE':
        command = new MergePullRequestByFastForwardCommand(baseParams);
        break;
      case 'SQUASH_MERGE':
        command = new MergePullRequestBySquashCommand({
          ...baseParams,
          commitMessage,
          authorName,
          email,
        });
        break;
      case 'THREE_WAY_MERGE':
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