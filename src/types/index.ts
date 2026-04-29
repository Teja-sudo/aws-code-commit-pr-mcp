export interface MCPConfig {
  awsProfile?: string;
  awsAccessKeyId?: string;
  awsSecretAccessKey?: string;
  awsSessionToken?: string;
  region?: string;
}

export interface AWSCredentials {
  accessKeyId: string;
  secretAccessKey: string;
  sessionToken?: string;
  expiration?: Date;
}

export interface Repository {
  repositoryName: string;
  repositoryId: string;
  repositoryDescription?: string;
  defaultBranch?: string;
  lastModifiedDate?: Date;
  creationDate?: Date;
  cloneUrlHttp?: string;
  cloneUrlSsh?: string;
  arn?: string;
}

export interface PullRequest {
  pullRequestId: string;
  title: string;
  description?: string;
  lastActivityDate?: Date;
  creationDate?: Date;
  pullRequestStatus: "OPEN" | "CLOSED";
  authorArn: string;
  revisionId: string;
  clientRequestToken?: string;
  targets: PullRequestTarget[];
  approvalRules?: ApprovalRule[];
  approvalStateOverride?: ApprovalState;
}

export interface PullRequestTarget {
  repositoryName: string;
  sourceReference: string;
  destinationReference?: string;
  destinationCommit?: string;
  sourceCommit?: string;
  mergeBase?: string;
  mergeMetadata?: MergeMetadata;
}

export interface ApprovalRule {
  approvalRuleId: string;
  approvalRuleName: string;
  approvalRuleContent: string;
  ruleContentSha256: string;
  lastModifiedDate?: Date;
  creationDate?: Date;
  lastModifiedUser?: string;
}

export interface ApprovalState {
  revisionId: string;
  approvalStatus: "APPROVE" | "REVOKE";
}

export interface MergeMetadata {
  isMerged: boolean;
  mergedBy?: string;
  mergeCommitId?: string;
  mergeOption?: string;
}

export interface Comment {
  commentId: string;
  content: string;
  inReplyTo?: string;
  creationDate?: Date;
  lastModifiedDate?: Date;
  authorArn: string;
  deleted: boolean;
  clientRequestToken?: string;
}

export interface PullRequestComment extends Comment {
  pullRequestId: string;
  repositoryName?: string;
  beforeCommitId?: string;
  afterCommitId?: string;
  location?: CommentLocation;
}

export interface CommentLocation {
  filePath: string;
  filePosition?: number;
  relativeFileVersion: "BEFORE" | "AFTER";
}

export interface Difference {
  beforeBlob?: BlobMetadata;
  afterBlob?: BlobMetadata;
  changeType: "A" | "D" | "M";
}

export interface BlobMetadata {
  blobId: string;
  path: string;
  mode: string;
}

export interface FileDifference {
  changeType: "A" | "D" | "M";
  beforeBlob?: BlobMetadata;
  afterBlob?: BlobMetadata;
}

export interface Branch {
  branchName: string;
  commitId: string;
}

export interface Commit {
  commitId: string;
  treeId: string;
  parents?: string[];
  message?: string;
  author?: UserInfo;
  committer?: UserInfo;
  additionalData?: string;
}

export interface UserInfo {
  name: string;
  email: string;
  date: string;
}

export interface File {
  absolutePath: string;
  blobId: string;
  fileMode: string;
}

export interface PaginationOptions {
  nextToken?: string;
  maxResults?: number;
}

export interface PaginatedResult<T> {
  items: T[];
  nextToken?: string;
}

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
