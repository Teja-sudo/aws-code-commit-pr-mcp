export class AWSCodeCommitError extends Error {
  constructor(
    message: string,
    public readonly code?: string,
    public readonly statusCode?: number,
    public readonly originalError?: any
  ) {
    super(message);
    this.name = "AWSCodeCommitError";
  }
}

export function handleAWSError(error: any): never {
  if (error.name === "RepositoryDoesNotExistException") {
    throw new AWSCodeCommitError(
      `Repository does not exist: ${error.message}`,
      "REPOSITORY_NOT_FOUND",
      404,
      error
    );
  }

  if (error.name === "PullRequestDoesNotExistException") {
    throw new AWSCodeCommitError(
      `Pull request does not exist: ${error.message}`,
      "PULL_REQUEST_NOT_FOUND",
      404,
      error
    );
  }

  if (error.name === "BranchDoesNotExistException") {
    throw new AWSCodeCommitError(
      `Branch does not exist: ${error.message}`,
      "BRANCH_NOT_FOUND",
      404,
      error
    );
  }

  if (error.name === "CommitDoesNotExistException") {
    throw new AWSCodeCommitError(
      `Commit does not exist: ${error.message}`,
      "COMMIT_NOT_FOUND",
      404,
      error
    );
  }

  if (error.name === "FileDoesNotExistException") {
    throw new AWSCodeCommitError(
      `File does not exist: ${error.message}`,
      "FILE_NOT_FOUND",
      404,
      error
    );
  }

  if (error.name === "AccessDeniedException") {
    throw new AWSCodeCommitError(
      `Access denied: ${error.message}`,
      "ACCESS_DENIED",
      403,
      error
    );
  }

  if (error.name === "InvalidParameterException") {
    throw new AWSCodeCommitError(
      `Invalid parameter: ${error.message}`,
      "INVALID_PARAMETER",
      400,
      error
    );
  }

  if (
    error.name === "CredentialsError" ||
    error.name === "UnauthorizedOperation" ||
    error.name === "TokenRefreshRequired" ||
    error.message?.includes("security token included in the request is expired")
  ) {
    throw new AWSCodeCommitError(
      `AWS credentials error (possibly expired): ${error.message}. Please run aws_creds_refresh to update credentials.`,
      "CREDENTIALS_ERROR",
      401,
      error
    );
  }

  // Generic error handling
  throw new AWSCodeCommitError(
    error.message || "An unknown AWS CodeCommit error occurred",
    error.name || "UNKNOWN_ERROR",
    error.$metadata?.httpStatusCode || 500,
    error
  );
}

export function isRetryableError(error: any): boolean {
  // AWS SDK errors that should be retried
  const retryableCodes = [
    "ThrottlingException",
    "TooManyRequestsException",
    "ServiceUnavailableException",
    "InternalServerError",
    "RequestTimeout",
  ];

  return (
    retryableCodes.includes(error.name) ||
    (error.$metadata?.httpStatusCode >= 500 &&
      error.$metadata?.httpStatusCode < 600)
  );
}

export async function retryWithBackoff<T>(
  operation: () => Promise<T>,
  maxRetries: number = 3,
  baseDelayMs: number = 1000
): Promise<T> {
  try {
    let lastError: any;

    for (let attempt = 0; attempt <= maxRetries; attempt++) {
      try {
        return await operation();
      } catch (error) {
        lastError = error;

        if (attempt === maxRetries || !isRetryableError(error)) {
          break;
        }

        const delay = baseDelayMs * Math.pow(2, attempt) + Math.random() * 1000;
        await new Promise((resolve) => setTimeout(resolve, delay));
      }
    }

    throw lastError;
  } catch (e) {
    return {
      content: [
        { type: "text", error: `**Error :** ${JSON.stringify(e, null, 2)}` },
      ],
    } as T;
  }
}
