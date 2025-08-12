import { RepositoryService } from "../services/repository-service";
import { FileDifference } from "../types";

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

      // Perform line-by-line diff analysis
      const chunks = this.performLineDiff(beforeContent, afterContent);
      const summary = this.calculateSummary(chunks);
      const recommendation = this.analyzeComplexity(
        chunks,
        beforeContent,
        afterContent,
        changeType
      );

      return {
        filePath,
        changeType,
        chunks,
        summary,
        analysisRecommendation: recommendation,
      };
    } catch (error) {
      // Fallback analysis for files that couldn't be retrieved
      return this.createFallbackAnalysis(filePath, changeType, error);
    }
  }

  /**
   * Performs intelligent line-by-line diff analysis
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

    if (fullFileCount === totalFiles) {
      return "All files require full context - significant changes detected";
    } else if (fullFileCount > totalFiles / 2) {
      return "Most files need full context - moderate to extensive changes";
    } else if (fullFileCount > 0) {
      return "Mixed approach needed - some files require full context, others can use focused diff";
    } else {
      return "Focused diff analysis sufficient for all files - targeted changes detected";
    }
  }
}
