import { PaginationOptions } from '../types/index.js';

export function createPaginationOptions(
  nextToken?: string,
  maxResults?: number
): PaginationOptions {
  return {
    nextToken,
    maxResults: Math.min(maxResults || 100, 1000), // AWS CodeCommit max is 1000
  };
}
