import { RepositoryService } from '../services/repository-service';

/**
 * Utility for calculating and validating line positions for AWS CodeCommit comments
 */
export class LinePositionCalculator {
  constructor(private repositoryService: RepositoryService) {}

  /**
   * Validates and adjusts line position for a file comment
   * AWS CodeCommit line positions are 1-based and relative to the specific file version
   * @param repositoryName Repository name
   * @param filePath Path to the file
   * @param lineNumber Requested line number (1-based)
   * @param commitSpecifier Commit ID or branch name
   * @param relativeFileVersion BEFORE or AFTER version
   * @returns Valid line position or throws error
   */
  async validateAndAdjustLinePosition(
    repositoryName: string,
    filePath: string,
    lineNumber: number,
    commitSpecifier: string,
    relativeFileVersion: 'BEFORE' | 'AFTER'
  ): Promise<number> {
    try {
      // Get the file content for the specified version
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
        relativeFileVersion
      });

      // Validate line number bounds - AWS CodeCommit uses 1-based indexing
      if (lineNumber < 1) {
        console.error(`Line number ${lineNumber} is too low, adjusting to 1`);
        return 1;
      }

      if (lineNumber > totalLines) {
        console.error(`Line number ${lineNumber} exceeds file length (${totalLines}), adjusting to ${totalLines}`);
        return totalLines;
      }

      // Line number is valid for this specific file version
      console.error(`Line ${lineNumber} is valid for ${relativeFileVersion} version (total: ${totalLines})`);
      return lineNumber;
    } catch (error) {
      console.error(`Error validating line position for ${filePath}:${lineNumber}`, error);
      
      // If file doesn't exist or can't be read, return a safe default
      throw new Error(`Cannot validate line position: ${error instanceof Error ? error.message : 'Unknown error'}`);
    }
  }

  /**
   * Maps line numbers between BEFORE and AFTER versions of a file using diff information
   * @param repositoryName Repository name
   * @param filePath Path to the file
   * @param lineNumber Line number in the source version
   * @param fromVersion Source version (BEFORE or AFTER)
   * @param toVersion Target version (BEFORE or AFTER)
   * @param beforeCommit Before commit ID
   * @param afterCommit After commit ID
   * @returns Mapped line number or null if not mappable
   */
  async mapLineBetweenVersions(
    repositoryName: string,
    filePath: string,
    lineNumber: number,
    fromVersion: 'BEFORE' | 'AFTER',
    toVersion: 'BEFORE' | 'AFTER',
    beforeCommit: string,
    afterCommit: string
  ): Promise<number | null> {
    if (fromVersion === toVersion) {
      return lineNumber;
    }

    try {
      // Get both file versions
      const beforeFile = await this.repositoryService.getFile(repositoryName, beforeCommit, filePath);
      const afterFile = await this.repositoryService.getFile(repositoryName, afterCommit, filePath);

      const beforeLines = beforeFile.content.split('\n');
      const afterLines = afterFile.content.split('\n');

      console.error(`Mapping line ${lineNumber} from ${fromVersion} to ${toVersion}:`, {
        beforeLines: beforeLines.length,
        afterLines: afterLines.length
      });

      // Simple heuristic: if the line content matches, use that line number
      if (fromVersion === 'BEFORE' && toVersion === 'AFTER') {
        const beforeLineContent = beforeLines[lineNumber - 1]?.trim();
        if (beforeLineContent) {
          // Find the same content in the after version
          const afterLineIndex = afterLines.findIndex(line => line.trim() === beforeLineContent);
          if (afterLineIndex !== -1) {
            return afterLineIndex + 1; // Convert to 1-based
          }
        }
      } else if (fromVersion === 'AFTER' && toVersion === 'BEFORE') {
        const afterLineContent = afterLines[lineNumber - 1]?.trim();
        if (afterLineContent) {
          // Find the same content in the before version
          const beforeLineIndex = beforeLines.findIndex(line => line.trim() === afterLineContent);
          if (beforeLineIndex !== -1) {
            return beforeLineIndex + 1; // Convert to 1-based
          }
        }
      }

      // If exact match not found, return approximate position
      if (fromVersion === 'BEFORE' && toVersion === 'AFTER') {
        const ratio = afterLines.length / beforeLines.length;
        return Math.min(Math.ceil(lineNumber * ratio), afterLines.length);
      } else {
        const ratio = beforeLines.length / afterLines.length;
        return Math.min(Math.ceil(lineNumber * ratio), beforeLines.length);
      }
    } catch (error) {
      console.error(`Error mapping line between versions:`, error);
      return null;
    }
  }

  /**
   * Finds the best line position for a comment based on content analysis
   * @param repositoryName Repository name
   * @param filePath Path to the file
   * @param searchContent Content to search for (partial match)
   * @param commitSpecifier Commit ID or branch name
   * @param relativeFileVersion BEFORE or AFTER version
   * @returns Best matching line number or null if not found
   */
  async findBestLinePosition(
    repositoryName: string,
    filePath: string,
    searchContent: string,
    commitSpecifier: string,
    relativeFileVersion: 'BEFORE' | 'AFTER'
  ): Promise<number | null> {
    try {
      const fileData = await this.repositoryService.getFile(
        repositoryName,
        commitSpecifier,
        filePath
      );

      const lines = fileData.content.split('\n');
      
      // Search for exact match first
      for (let i = 0; i < lines.length; i++) {
        if (lines[i].includes(searchContent.trim())) {
          console.error(`Found exact match for "${searchContent}" at line ${i + 1}`);
          return i + 1; // Convert to 1-based
        }
      }

      // Search for partial matches with fuzzy matching
      const searchTerms = searchContent.toLowerCase().split(/\s+/).filter(term => term.length > 2);
      let bestMatch = { line: -1, score: 0 };

      for (let i = 0; i < lines.length; i++) {
        const lineContent = lines[i].toLowerCase();
        let score = 0;
        
        for (const term of searchTerms) {
          if (lineContent.includes(term)) {
            score++;
          }
        }

        if (score > bestMatch.score) {
          bestMatch = { line: i + 1, score };
        }
      }

      if (bestMatch.score > 0) {
        console.error(`Found best match for "${searchContent}" at line ${bestMatch.line} (score: ${bestMatch.score})`);
        return bestMatch.line;
      }

      console.error(`No match found for "${searchContent}" in ${filePath}`);
      return null;
    } catch (error) {
      console.error(`Error finding best line position:`, error);
      return null;
    }
  }

  /**
   * Maps line position from AI analysis context to AWS CodeCommit PR context
   * This handles the specific case where AI analyzes full files but comments need
   * to be positioned relative to the PR diff context
   * @param repositoryName Repository name
   * @param filePath Path to the file
   * @param aiLineNumber Line number from AI analysis (1-based)
   * @param beforeCommitId Before commit ID for PR
   * @param afterCommitId After commit ID for PR
   * @param relativeFileVersion BEFORE or AFTER version for comment
   * @returns Correctly positioned line number for AWS CodeCommit
   */
  async mapAILineToCodeCommitPosition(
    repositoryName: string,
    filePath: string,
    aiLineNumber: number,
    beforeCommitId: string,
    afterCommitId: string,
    relativeFileVersion: 'BEFORE' | 'AFTER'
  ): Promise<number> {
    try {
      // Get the file content for the target version
      const targetCommit = relativeFileVersion === 'BEFORE' ? beforeCommitId : afterCommitId;
      const fileData = await this.repositoryService.getFile(
        repositoryName,
        targetCommit,
        filePath
      );

      const lines = fileData.content.split('\n');
      const totalLines = lines.length;

      console.error(`Mapping AI line ${aiLineNumber} to CodeCommit position:`, {
        filePath,
        aiLineNumber,
        targetCommit: targetCommit.substring(0, 8),
        relativeFileVersion,
        totalLines
      });

      // Validate that the AI line number is within bounds
      if (aiLineNumber < 1) {
        console.error(`AI line number ${aiLineNumber} is too low, using line 1`);
        return 1;
      }

      if (aiLineNumber > totalLines) {
        console.error(`AI line number ${aiLineNumber} exceeds file length (${totalLines}), using last line`);
        return totalLines;
      }

      // For now, return the AI line number as-is since it should be relative to the correct file version
      // Future enhancement: implement more sophisticated diff-based mapping if needed
      console.error(`Mapped AI line ${aiLineNumber} to CodeCommit position ${aiLineNumber}`);
      return aiLineNumber;
    } catch (error) {
      console.error(`Error mapping AI line to CodeCommit position:`, error);
      // Return the original line number as fallback
      return aiLineNumber;
    }
  }

  /**
   * Gets file content summary for debugging
   * @param repositoryName Repository name
   * @param filePath Path to the file
   * @param commitSpecifier Commit ID or branch name
   * @returns Summary with line count and sample lines
   */
  async getFileContentSummary(
    repositoryName: string,
    filePath: string,
    commitSpecifier: string
  ): Promise<{ totalLines: number; sampleLines: string[]; }> {
    try {
      const fileData = await this.repositoryService.getFile(
        repositoryName,
        commitSpecifier,
        filePath
      );

      const lines = fileData.content.split('\n');
      const sampleLines = lines.slice(0, 20).map((line, index) => 
        `${index + 1}: ${line.substring(0, 100)}${line.length > 100 ? '...' : ''}`
      );

      return {
        totalLines: lines.length,
        sampleLines
      };
    } catch (error) {
      console.error(`Error getting file content summary:`, error);
      return { totalLines: 0, sampleLines: [] };
    }
  }
}
