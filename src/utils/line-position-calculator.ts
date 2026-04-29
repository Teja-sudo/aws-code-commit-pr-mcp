import { RepositoryService } from '../services/repository-service.js';

/**
 * Validates that a line number falls within the bounds of a file at a given commit.
 * AWS CodeCommit comment positions are 1-based and relative to the specific file version
 * (BEFORE = destination commit, AFTER = source commit).
 */
export class LinePositionCalculator {
  constructor(private repositoryService: RepositoryService) {}

  /**
   * Returns the line number, clamped to [1, totalLines]. Throws if the file
   * cannot be retrieved (so the caller can fall back to the original position).
   */
  async validateAndAdjustLinePosition(
    repositoryName: string,
    filePath: string,
    lineNumber: number,
    commitSpecifier: string,
    relativeFileVersion: 'BEFORE' | 'AFTER'
  ): Promise<number> {
    const fileData = await this.repositoryService.getFile(
      repositoryName,
      commitSpecifier,
      filePath
    );

    const lines = fileData.content.split('\n');
    const totalLines = lines.length;

    console.error(`Line validation for ${filePath}:`, {
      requestedLine: lineNumber,
      totalLines,
      commitSpecifier: commitSpecifier.substring(0, 8),
      relativeFileVersion,
    });

    if (lineNumber < 1) {
      console.error(`Line number ${lineNumber} is too low, adjusting to 1`);
      return 1;
    }

    if (lineNumber > totalLines) {
      console.error(
        `Line number ${lineNumber} exceeds file length (${totalLines}), adjusting to ${totalLines}`
      );
      return totalLines;
    }

    return lineNumber;
  }
}
