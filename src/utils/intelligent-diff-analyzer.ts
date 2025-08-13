import { RepositoryService } from "../services/repository-service";
import { FileDifference } from "../types";
import * as Diff from "diff";

export interface DiffChunk {
  type: "added" | "removed" | "modified" | "context";
  beforeLineStart: number;
  beforeLineEnd: number;
  afterLineStart: number;
  afterLineEnd: number;
  content: string[];
  contextBefore?: string[];
  contextAfter?: string[];
}

export interface IntelligentDiff {
  filePath: string;
  changeType: "A" | "D" | "M";
  chunks: DiffChunk[];
  gitDiffFormat: string;
  summary: {
    linesAdded: number;
    linesRemoved: number;
    linesModified: number;
    totalChanges: number;
  };
  analysisRecommendation: {
    needsFullFile: boolean;
    reason: string;
    contextLines: number;
    complexity: "low" | "medium" | "high";
  };
  lineNumberMapping: {
    beforeLineCount: number;
    afterLineCount: number;
    exactLineNumbers: boolean;
    awsConsoleCompatible: boolean;
  };
}

export interface FileAnalysisContext {
  isNewFile: boolean;
  isDeletedFile: boolean;
  isLargeFile: boolean;
  hasStructuralChanges: boolean;
  changeComplexity: "low" | "medium" | "high";
  recommendedApproach: "diff_only" | "diff_with_context" | "full_file";
}

export class IntelligentDiffAnalyzer {
  constructor(private repositoryService: RepositoryService) {}

  /**
   * Analyzes file differences and provides intelligent recommendations
   * for the best approach to understand the changes
   */
  async analyzeFileDiff(
    repositoryName: string,
    beforeCommitId: string,
    afterCommitId: string,
    filePath: string,
    changeType: "A" | "D" | "M"
  ): Promise<IntelligentDiff> {
    let beforeContent = "";
    let afterContent = "";

    try {
      // Get file contents based on change type
      if (changeType !== "A") {
        const beforeFile = await this.repositoryService.getFile(
          repositoryName,
          beforeCommitId,
          filePath
        );
        beforeContent = beforeFile.content;
      }

      if (changeType !== "D") {
        const afterFile = await this.repositoryService.getFile(
          repositoryName,
          afterCommitId,
          filePath
        );
        afterContent = afterFile.content;
      }

      // Perform line-by-line diff analysis using proper diff library
      const diffResult = this.performLineDiffWithLibrary(beforeContent, afterContent);
      const chunks = diffResult.chunks;
      const summary = diffResult.summary;
      const recommendation = this.analyzeComplexity(
        chunks,
        beforeContent,
        afterContent,
        changeType
      );
      
      // Generate git diff format using the diff library directly
      const gitDiffFormat = this.generateProperGitDiff(
        filePath,
        beforeContent,
        afterContent,
        changeType
      );
      
      // Create line number mapping
      const beforeLines = beforeContent.split('\n');
      const afterLines = afterContent.split('\n');
      const lineNumberMapping = {
        beforeLineCount: beforeLines.length,
        afterLineCount: afterLines.length,
        exactLineNumbers: true,
        awsConsoleCompatible: true
      };

      return {
        filePath,
        changeType,
        chunks,
        gitDiffFormat,
        summary,
        analysisRecommendation: recommendation,
        lineNumberMapping,
      };
    } catch (error) {
      // Fallback analysis for files that couldn't be retrieved
      return this.createFallbackAnalysis(filePath, changeType, error);
    }
  }

  /**
   * Performs intelligent line-by-line diff analysis using the diff library
   */
  private performLineDiffWithLibrary(
    beforeContent: string,
    afterContent: string
  ): { chunks: DiffChunk[], summary: { linesAdded: number, linesRemoved: number, linesModified: number, totalChanges: number } } {
    // Use the diff library for accurate line-by-line comparison
    const diff = Diff.diffLines(beforeContent, afterContent);
    
    const chunks: DiffChunk[] = [];
    let beforeLineNum = 1;
    let afterLineNum = 1;
    let linesAdded = 0;
    let linesRemoved = 0;
    // let linesModified = 0; // Currently not used
    
    for (const part of diff) {
      const lines = part.value.split('\n');
      // Remove empty last line if it exists (common with split)
      if (lines[lines.length - 1] === '') {
        lines.pop();
      }
      
      if (part.added) {
        // Lines added
        linesAdded += lines.length;
        chunks.push({
          type: "added",
          beforeLineStart: beforeLineNum,
          beforeLineEnd: beforeLineNum - 1, // No lines in before
          afterLineStart: afterLineNum,
          afterLineEnd: afterLineNum + lines.length - 1,
          content: lines,
        });
        afterLineNum += lines.length;
      } else if (part.removed) {
        // Lines removed
        linesRemoved += lines.length;
        chunks.push({
          type: "removed",
          beforeLineStart: beforeLineNum,
          beforeLineEnd: beforeLineNum + lines.length - 1,
          afterLineStart: afterLineNum,
          afterLineEnd: afterLineNum - 1, // No lines in after
          content: lines,
        });
        beforeLineNum += lines.length;
      } else {
        // Unchanged lines (context)
        if (lines.length > 0) {
          chunks.push({
            type: "context",
            beforeLineStart: beforeLineNum,
            beforeLineEnd: beforeLineNum + lines.length - 1,
            afterLineStart: afterLineNum,
            afterLineEnd: afterLineNum + lines.length - 1,
            content: lines,
          });
          beforeLineNum += lines.length;
          afterLineNum += lines.length;
        }
      }
    }
    
    return {
      chunks,
      summary: {
        linesAdded,
        linesRemoved,
        linesModified: 0, // We'll calculate this differently if needed
        totalChanges: linesAdded + linesRemoved
      }
    };
  }

  /**
   * Legacy method - kept for compatibility, now uses the library method
   */
  private performLineDiff(
    beforeContent: string,
    afterContent: string
  ): DiffChunk[] {
    const beforeLines = beforeContent.split("\n");
    const afterLines = afterContent.split("\n");

    const chunks: DiffChunk[] = [];
    let beforeIndex = 0;
    let afterIndex = 0;

    // Simple LCS-based diff algorithm with context awareness
    const lcs = this.longestCommonSubsequence(beforeLines, afterLines);

    for (const change of lcs) {
      if (change.type === "equal") {
        // Context lines - include selectively
        if (chunks.length > 0 || beforeIndex < beforeLines.length - 1) {
          chunks.push({
            type: "context",
            beforeLineStart: beforeIndex + 1,
            beforeLineEnd: beforeIndex + change.count,
            afterLineStart: afterIndex + 1,
            afterLineEnd: afterIndex + change.count,
            content: beforeLines.slice(beforeIndex, beforeIndex + change.count),
          });
        }
        beforeIndex += change.count;
        afterIndex += change.count;
      } else if (change.type === "delete") {
        chunks.push({
          type: "removed",
          beforeLineStart: beforeIndex + 1,
          beforeLineEnd: beforeIndex + change.count,
          afterLineStart: afterIndex + 1,
          afterLineEnd: afterIndex,
          content: beforeLines.slice(beforeIndex, beforeIndex + change.count),
        });
        beforeIndex += change.count;
      } else if (change.type === "insert") {
        chunks.push({
          type: "added",
          beforeLineStart: beforeIndex + 1,
          beforeLineEnd: beforeIndex,
          afterLineStart: afterIndex + 1,
          afterLineEnd: afterIndex + change.count,
          content: afterLines.slice(afterIndex, afterIndex + change.count),
        });
        afterIndex += change.count;
      }
    }

    return this.addContextToChunks(chunks, beforeLines, afterLines);
  }

  /**
   * Adds intelligent context around changes
   */
  private addContextToChunks(
    chunks: DiffChunk[],
    beforeLines: string[],
    afterLines: string[]
  ): DiffChunk[] {
    return chunks.map((chunk) => {
      if (chunk.type === "context") return chunk;

      const contextSize = this.determineContextSize(chunk);

      // Add context before the change
      const contextBefore = this.getContextLines(
        chunk.type === "removed" ? beforeLines : afterLines,
        chunk.type === "removed"
          ? chunk.beforeLineStart - 1
          : chunk.afterLineStart - 1,
        contextSize,
        "before"
      );

      // Add context after the change
      const contextAfter = this.getContextLines(
        chunk.type === "removed" ? beforeLines : afterLines,
        chunk.type === "removed" ? chunk.beforeLineEnd : chunk.afterLineEnd,
        contextSize,
        "after"
      );

      return {
        ...chunk,
        contextBefore,
        contextAfter,
      };
    });
  }

  /**
   * Determines appropriate context size based on change complexity
   */
  private determineContextSize(chunk: DiffChunk): number {
    const changeSize = chunk.content.length;

    // Look for structural indicators
    const hasClassOrFunction = chunk.content.some((line) =>
      /^(class|function|def|public|private|protected|async|export)/.test(
        line.trim()
      )
    );

    if (hasClassOrFunction) return 5;
    if (changeSize > 10) return 4;
    if (changeSize > 5) return 3;
    return 2;
  }

  /**
   * Gets contextual lines around a change
   */
  private getContextLines(
    lines: string[],
    fromIndex: number,
    count: number,
    direction: "before" | "after"
  ): string[] {
    if (direction === "before") {
      const start = Math.max(0, fromIndex - count);
      return lines.slice(start, fromIndex);
    } else {
      const end = Math.min(lines.length, fromIndex + count);
      return lines.slice(fromIndex, end);
    }
  }

  /**
   * Simple LCS implementation for diff calculation
   */
  private longestCommonSubsequence(
    before: string[],
    after: string[]
  ): Array<{ type: string; count: number }> {
    // Simplified diff algorithm - in production, consider using a more robust library
    const result: Array<{ type: string; count: number }> = [];
    let i = 0,
      j = 0;

    while (i < before.length || j < after.length) {
      if (i < before.length && j < after.length && before[i] === after[j]) {
        let count = 0;
        while (
          i < before.length &&
          j < after.length &&
          before[i] === after[j]
        ) {
          count++;
          i++;
          j++;
        }
        result.push({ type: "equal", count });
      } else if (
        i < before.length &&
        (j >= after.length || before[i] !== after[j])
      ) {
        let count = 0;
        while (
          i < before.length &&
          (j >= after.length || before[i] !== after[j])
        ) {
          count++;
          i++;
        }
        result.push({ type: "delete", count });
      } else {
        let count = 0;
        while (
          j < after.length &&
          (i >= before.length || before[i] !== after[j])
        ) {
          count++;
          j++;
        }
        result.push({ type: "insert", count });
      }
    }

    return result;
  }

  /**
   * Calculates summary statistics for the diff
   */
  private calculateSummary(chunks: DiffChunk[]) {
    let linesAdded = 0;
    let linesRemoved = 0;
    let linesModified = 0;

    chunks.forEach((chunk) => {
      switch (chunk.type) {
        case "added":
          linesAdded += chunk.content.length;
          break;
        case "removed":
          linesRemoved += chunk.content.length;
          break;
        case "modified":
          linesModified += chunk.content.length;
          break;
      }
    });

    return {
      linesAdded,
      linesRemoved,
      linesModified,
      totalChanges: linesAdded + linesRemoved + linesModified,
    };
  }

  /**
   * Analyzes change complexity and provides recommendations
   */
  private analyzeComplexity(
    chunks: DiffChunk[],
    beforeContent: string,
    afterContent: string,
    changeType: "A" | "D" | "M"
  ) {
    const beforeLines = beforeContent.split("\n").length;
    const afterLines = afterContent.split("\n").length;
    const totalChanges = chunks.filter((c) => c.type !== "context").length;
    const changeRatio = totalChanges / Math.max(beforeLines, afterLines, 1);

    // Determine if full file context is needed
    const needsFullFile = this.shouldRecommendFullFile(
      chunks,
      beforeContent,
      afterContent,
      changeType
    );

    // Determine complexity
    let complexity: "low" | "medium" | "high" = "low";
    if (changeRatio > 0.5 || totalChanges > 20) {
      complexity = "high";
    } else if (changeRatio > 0.2 || totalChanges > 10) {
      complexity = "medium";
    }

    // Determine reason and context lines needed
    const reason = this.getRecommendationReason(
      needsFullFile,
      complexity,
      changeType
    );
    const contextLines = this.getRecommendedContextLines(complexity);

    return {
      needsFullFile,
      reason,
      contextLines,
      complexity,
    };
  }

  /**
   * Determines if full file context is recommended
   */
  private shouldRecommendFullFile(
    chunks: DiffChunk[],
    beforeContent: string,
    afterContent: string,
    changeType: "A" | "D" | "M"
  ): boolean {
    // New or deleted files always need full context
    if (changeType === "A" || changeType === "D") return true;

    const beforeLines = beforeContent.split("\n").length;
    const afterLines = afterContent.split("\n").length;

    // Small files - show full content
    if (Math.max(beforeLines, afterLines) <= 500) return true;

    // High change ratio
    const totalChanges = chunks.filter((c) => c.type !== "context").length;
    const changeRatio = totalChanges / Math.max(beforeLines, afterLines);
    if (changeRatio > 0.3) return true;

    // Structural changes (imports, exports, class definitions)
    const hasStructuralChanges = chunks.some((chunk) =>
      chunk.content.some((line) =>
        /^(import|export|class|interface|function|def|from|package)/.test(
          line.trim()
        )
      )
    );
    if (hasStructuralChanges) return true;

    return false;
  }

  /**
   * Gets recommendation reason text
   */
  private getRecommendationReason(
    needsFullFile: boolean,
    complexity: "low" | "medium" | "high",
    changeType: "A" | "D" | "M"
  ): string {
    if (changeType === "A")
      return "New file requires full context to understand structure and purpose";
    if (changeType === "D")
      return "Deleted file should be reviewed in full to understand impact";

    if (needsFullFile) {
      if (complexity === "high")
        return "Extensive changes require full file context for proper understanding";
      return "Structural changes or small file size makes full context beneficial";
    }

    return "Focused diff with context should be sufficient for understanding changes";
  }

  /**
   * Gets recommended context lines based on complexity
   */
  private getRecommendedContextLines(
    complexity: "low" | "medium" | "high"
  ): number {
    switch (complexity) {
      case "high":
        return 8;
      case "medium":
        return 5;
      case "low":
        return 3;
    }
  }

  /**
   * Generates proper git diff format using only the diff library
   * This creates unified diff format exactly like git diff command
   */
  private generateProperGitDiff(
    filePath: string,
    beforeContent: string,
    afterContent: string,
    changeType: "A" | "D" | "M"
  ): string {
    // For new files (A) - show all content as added
    if (changeType === "A") {
      const unifiedDiff = Diff.createPatch(
        filePath,
        "", // Empty before content
        afterContent,
        "/dev/null",
        "b/" + filePath,
        { context: 3 }
      );
      
      // Replace the header to match git format
      const lines = unifiedDiff.split('\n');
      const result = [
        `diff --git a/${filePath} b/${filePath}`,
        `new file mode 100644`,
        `index 0000000..${this.generateHashPlaceholder()}`,
        `--- /dev/null`,
        `+++ b/${filePath}`,
        ...lines.slice(4) // Skip the createPatch header
      ];
      
      return result.join('\n');
    }
    
    // For deleted files (D) - show all content as removed
    if (changeType === "D") {
      const unifiedDiff = Diff.createPatch(
        filePath,
        beforeContent,
        "", // Empty after content
        "a/" + filePath,
        "/dev/null",
        { context: 3 }
      );
      
      // Replace the header to match git format
      const lines = unifiedDiff.split('\n');
      const result = [
        `diff --git a/${filePath} b/${filePath}`,
        `deleted file mode 100644`,
        `index ${this.generateHashPlaceholder()}..0000000`,
        `--- a/${filePath}`,
        `+++ /dev/null`,
        ...lines.slice(4) // Skip the createPatch header
      ];
      
      return result.join('\n');
    }
    
    // For modified files (M) - show the actual diff
    const unifiedDiff = Diff.createPatch(
      filePath,
      beforeContent,
      afterContent,
      "a/" + filePath,
      "b/" + filePath,
      { context: 3 }
    );
    
    // Replace the header to match git format
    const lines = unifiedDiff.split('\n');
    const result = [
      `diff --git a/${filePath} b/${filePath}`,
      `index ${this.generateHashPlaceholder()}..${this.generateHashPlaceholder()} 100644`,
      `--- a/${filePath}`,
      `+++ b/${filePath}`,
      ...lines.slice(4) // Skip the createPatch header
    ];
    
    return result.join('\n');
  }

  /**
   * Generates a placeholder hash for git diff (simplified)
   */
  private generateHashPlaceholder(): string {
    return Math.random().toString(36).substring(2, 9);
  }

  /**
   * Legacy method - generates proper git diff format using the diff library
   * This creates unified diff format exactly like git diff command
   */
  private generateGitDiffFormat(
    filePath: string,
    beforeContent: string,
    afterContent: string,
    chunks: DiffChunk[],
    changeType: "A" | "D" | "M"
  ): string {
    const diffOutput: string[] = [];
    
    // Generate proper git hash placeholders (simplified)
    const beforeHash = "a".repeat(7) + (Math.random().toString(36).substring(2, 9));
    const afterHash = "b".repeat(7) + (Math.random().toString(36).substring(2, 9));
    
    // Add git diff header
    diffOutput.push(`diff --git a/${filePath} b/${filePath}`);
    
    if (changeType === "A") {
      diffOutput.push(`new file mode 100644`);
      diffOutput.push(`index 0000000..${afterHash.substring(0, 7)}`);
      diffOutput.push(`--- /dev/null`);
      diffOutput.push(`+++ b/${filePath}`);
    } else if (changeType === "D") {
      diffOutput.push(`deleted file mode 100644`);
      diffOutput.push(`index ${beforeHash.substring(0, 7)}..0000000`);
      diffOutput.push(`--- a/${filePath}`);
      diffOutput.push(`+++ /dev/null`);
    } else {
      diffOutput.push(`index ${beforeHash.substring(0, 7)}..${afterHash.substring(0, 7)} 100644`);
      diffOutput.push(`--- a/${filePath}`);
      diffOutput.push(`+++ b/${filePath}`);
    }
    
    // Use the diff library to generate proper unified diff
    const unifiedDiff = Diff.createPatch(
      filePath,
      beforeContent,
      afterContent,
      "a/" + filePath,
      "b/" + filePath,
      { 
        context: 3  // 3 lines of context like git default
      }
    );
    
    // Parse the unified diff and extract the hunks (skip the header lines)
    const lines = unifiedDiff.split('\n');
    let inHunk = false;
    
    for (const line of lines) {
      if (line.startsWith('@@')) {
        inHunk = true;
        diffOutput.push(line);
      } else if (inHunk && (line.startsWith(' ') || line.startsWith('+') || line.startsWith('-'))) {
        diffOutput.push(line);
      } else if (inHunk && line === '') {
        // Empty line in diff
        diffOutput.push(line);
      }
    }
    
    return diffOutput.join('\n');
  }

  /**
   * Creates fallback analysis when file retrieval fails
   */
  private createFallbackAnalysis(
    filePath: string,
    changeType: "A" | "D" | "M",
    error: any
  ): IntelligentDiff {
    return {
      filePath,
      changeType,
      chunks: [],
      gitDiffFormat: `# Diff analysis failed for ${filePath}\n# Error: ${error.message}\n# Recommend using file_get for manual analysis`,
      summary: {
        linesAdded: 0,
        linesRemoved: 0,
        linesModified: 0,
        totalChanges: 0,
      },
      analysisRecommendation: {
        needsFullFile: changeType === "A" || changeType === "D",
        reason: `File analysis failed (${error.message}). Recommend using file_get for manual analysis.`,
        contextLines: 3,
        complexity: "medium",
      },
      lineNumberMapping: {
        beforeLineCount: 0,
        afterLineCount: 0,
        exactLineNumbers: false,
        awsConsoleCompatible: false
      },
    };
  }

  /**
   * Analyzes multiple files and provides batch recommendations
   */
  async analyzeBatchDiffs(
    repositoryName: string,
    beforeCommitId: string,
    afterCommitId: string,
    fileDifferences: FileDifference[]
  ): Promise<{
    analyses: IntelligentDiff[];
    batchRecommendations: {
      totalFiles: number;
      fullFileNeeded: number;
      complexFiles: string[];
      simpleFiles: string[];
      approachSummary: string;
    };
  }> {
    const analyses = await Promise.all(
      fileDifferences.map((diff) =>
        this.analyzeFileDiff(
          repositoryName,
          beforeCommitId,
          afterCommitId,
          diff.afterBlob?.path || diff.beforeBlob?.path || "unknown",
          diff.changeType
        )
      )
    );

    const batchRecommendations = {
      totalFiles: analyses.length,
      fullFileNeeded: analyses.filter(
        (a) => a.analysisRecommendation.needsFullFile
      ).length,
      complexFiles: analyses
        .filter((a) => a.analysisRecommendation.complexity === "high")
        .map((a) => a.filePath),
      simpleFiles: analyses
        .filter((a) => a.analysisRecommendation.complexity === "low")
        .map((a) => a.filePath),
      approachSummary: this.generateBatchApproachSummary(analyses),
    };

    return { analyses, batchRecommendations };
  }

  /**
   * Generates a summary of recommended approaches for the batch
   */
  private generateBatchApproachSummary(analyses: IntelligentDiff[]): string {
    const fullFileCount = analyses.filter(
      (a) => a.analysisRecommendation.needsFullFile
    ).length;
    const totalFiles = analyses.length;
    
    let summary = "";
    
    if (fullFileCount === totalFiles) {
      summary = "All files require full context - significant changes detected";
    } else if (fullFileCount > totalFiles / 2) {
      summary = "Most files need full context - moderate to extensive changes";
    } else if (fullFileCount > 0) {
      summary = "Mixed approach needed - some files require full context, others can use focused diff";
    } else {
      summary = "Focused diff analysis sufficient for all files - targeted changes detected";
    }
    
    // Add batch size guidance
    if (totalFiles > 5) {
      summary += `. NOTE: Processed ${totalFiles} files (recommended maximum: 3-5 files per batch for optimal performance)`;
    } else {
      summary += `. Batch size: ${totalFiles} files (optimal for analysis)`;
    }
    
    return summary;
  }
}
