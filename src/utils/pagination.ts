import { PaginatedResult, PaginationOptions } from '../types';

export function createPaginationOptions(
  nextToken?: string,
  maxResults?: number
): PaginationOptions {
  return {
    nextToken,
    maxResults: Math.min(maxResults || 100, 1000), // AWS CodeCommit max is 1000
  };
}

export async function getAllPages<T>(
  fetchPage: (options: PaginationOptions) => Promise<PaginatedResult<T>>,
  maxItems?: number
): Promise<T[]> {
  const results: T[] = [];
  let nextToken: string | undefined;
  let totalFetched = 0;

  do {
    const maxResults = maxItems 
      ? Math.min(100, maxItems - totalFetched)
      : 100;

    if (maxResults <= 0) break;

    const page = await fetchPage({ nextToken, maxResults });
    results.push(...page.items);
    nextToken = page.nextToken;
    totalFetched += page.items.length;

    if (maxItems && totalFetched >= maxItems) {
      break;
    }
  } while (nextToken);

  return maxItems ? results.slice(0, maxItems) : results;
}

export function formatPaginationInfo(
  currentPage: number,
  itemsPerPage: number,
  totalItems: number,
  hasNextPage: boolean
): string {
  const startItem = (currentPage - 1) * itemsPerPage + 1;
  const endItem = Math.min(currentPage * itemsPerPage, totalItems);
  
  let info = `Showing ${startItem}-${endItem}`;
  if (totalItems > 0) {
    info += ` of ${totalItems} items`;
  }
  
  if (hasNextPage) {
    info += ' (more available)';
  }
  
  return info;
}