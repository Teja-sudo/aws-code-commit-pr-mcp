import { createHash } from "node:crypto";
import { RepositoryService } from "../services/repository-service.js";
import { FileDifference } from "../types/index.js";
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

export class IntelligentDiffAnalyzer {
  constructor(private repositoryService: RepositoryService) {}

  /**
   * Analyzes file differences and provides intelligent recommendations
   * for the best approach to understand the changes.
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

      const diffResult = this.performLineDiffWithLibrary(beforeContent, afterContent);
      const chunks = diffResult.chunks;
      const summary = diffResult.summary;
      const recommendation = this.analyzeComplexity(
        chunks,
        beforeContent,
        afterContent,
        changeType
      );

      const gitDiffFormat = this.generateProperGitDiff(
        filePath,
        beforeContent,
        afterContent,
        changeType
      );

      const beforeLines = beforeContent.split("\n");
      const afterLines = afterContent.split("\n");
      const lineNumberMapping = {
        beforeLineCount: beforeLines.length,
        afterLineCount: afterLines.length,
        exactLineNumbers: true,
        awsConsoleCompatible: true,
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
      return this.createFallbackAnalysis(filePath, changeType, error);
    }
  }

  /**
   * Performs line-by-line diff analysis using the diff library.
   * Tracks before/after line numbers correctly even when content lacks a
   * trailing newline (otherwise the last real line gets dropped).
   */
  private performLineDiffWithLibrary(
    beforeContent: string,
    afterContent: string
  ): {
    chunks: DiffChunk[];
    summary: {
      linesAdded: number;
      linesRemoved: number;
      linesModified: number;
      totalChanges: number;
    };
  } {
    const diff = Diff.diffLines(beforeContent, afterContent);

    const chunks: DiffChunk[] = [];
    let beforeLineNum = 1;
    let afterLineNum = 1;
    let linesAdded = 0;
    let linesRemoved = 0;

    for (const part of diff) {
      const lines = part.value.split("\n");
      // split('\n') leaves a trailing "" only when the value ends with \n.
      // If it doesn't, the last element is a real (un-newlined) line we must keep.
      if (lines.length > 0 && part.value.endsWith("\n") && lines[lines.length - 1] === "") {
        lines.pop();
      }

      if (part.added) {
        linesAdded += lines.length;
        chunks.push({
          type: "added",
          beforeLineStart: beforeLineNum,
          beforeLineEnd: beforeLineNum - 1,
          afterLineStart: afterLineNum,
          afterLineEnd: afterLineNum + lines.length - 1,
          content: lines,
        });
        afterLineNum += lines.length;
      } else if (part.removed) {
        linesRemoved += lines.length;
        chunks.push({
          type: "removed",
          beforeLineStart: beforeLineNum,
          beforeLineEnd: beforeLineNum + lines.length - 1,
          afterLineStart: afterLineNum,
          afterLineEnd: afterLineNum - 1,
          content: lines,
        });
        beforeLineNum += lines.length;
      } else if (lines.length > 0) {
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

    return {
      chunks,
      summary: {
        linesAdded,
        linesRemoved,
        linesModified: 0,
        totalChanges: linesAdded + linesRemoved,
      },
    };
  }

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

    const needsFullFile = this.shouldRecommendFullFile(
      chunks,
      beforeContent,
      afterContent,
      changeType
    );

    let complexity: "low" | "medium" | "high" = "low";
    if (changeRatio > 0.5 || totalChanges > 20) {
      complexity = "high";
    } else if (changeRatio > 0.2 || totalChanges > 10) {
      complexity = "medium";
    }

    return {
      needsFullFile,
      reason: this.getRecommendationReason(needsFullFile, complexity, changeType),
      contextLines: this.getRecommendedContextLines(complexity),
      complexity,
    };
  }

  private shouldRecommendFullFile(
    chunks: DiffChunk[],
    beforeContent: string,
    afterContent: string,
    changeType: "A" | "D" | "M"
  ): boolean {
    if (changeType === "A" || changeType === "D") return true;

    const beforeLines = beforeContent.split("\n").length;
    const afterLines = afterContent.split("\n").length;

    if (Math.max(beforeLines, afterLines) <= 500) return true;

    const totalChanges = chunks.filter((c) => c.type !== "context").length;
    const changeRatio = totalChanges / Math.max(beforeLines, afterLines);
    if (changeRatio > 0.3) return true;

    const hasStructuralChanges = chunks.some((chunk) =>
      chunk.content.some((line) =>
        /^(import|export|class|interface|function|def|from|package)/.test(line.trim())
      )
    );
    return hasStructuralChanges;
  }

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
   * Generates a unified diff in git's format. For new/deleted files we synthesize
   * the appropriate header lines; for modified files we delegate to Diff.createPatch.
   */
  private generateProperGitDiff(
    filePath: string,
    beforeContent: string,
    afterContent: string,
    changeType: "A" | "D" | "M"
  ): string {
    if (changeType === "A") {
      const unifiedDiff = Diff.createPatch(
        filePath,
        "",
        afterContent,
        "/dev/null",
        "b/" + filePath,
        { context: 3 }
      );
      const body = unifiedDiff.split("\n").slice(4);
      return [
        `diff --git a/${filePath} b/${filePath}`,
        `new file mode 100644`,
        `index 0000000..${this.shortHash(afterContent)}`,
        `--- /dev/null`,
        `+++ b/${filePath}`,
        ...body,
      ].join("\n");
    }

    if (changeType === "D") {
      const unifiedDiff = Diff.createPatch(
        filePath,
        beforeContent,
        "",
        "a/" + filePath,
        "/dev/null",
        { context: 3 }
      );
      const body = unifiedDiff.split("\n").slice(4);
      return [
        `diff --git a/${filePath} b/${filePath}`,
        `deleted file mode 100644`,
        `index ${this.shortHash(beforeContent)}..0000000`,
        `--- a/${filePath}`,
        `+++ /dev/null`,
        ...body,
      ].join("\n");
    }

    const unifiedDiff = Diff.createPatch(
      filePath,
      beforeContent,
      afterContent,
      "a/" + filePath,
      "b/" + filePath,
      { context: 3 }
    );
    const body = unifiedDiff.split("\n").slice(4);
    return [
      `diff --git a/${filePath} b/${filePath}`,
      `index ${this.shortHash(beforeContent)}..${this.shortHash(afterContent)} 100644`,
      `--- a/${filePath}`,
      `+++ b/${filePath}`,
      ...body,
    ].join("\n");
  }

  private shortHash(content: string): string {
    return createHash("sha1").update(content).digest("hex").slice(0, 7);
  }

  private createFallbackAnalysis(
    filePath: string,
    changeType: "A" | "D" | "M",
    error: any
  ): IntelligentDiff {
    return {
      filePath,
      changeType,
      chunks: [],
      gitDiffFormat: `# Diff analysis failed for ${filePath}\n# Error: ${error?.message ?? error}\n# Recommend using file_get for manual analysis`,
      summary: {
        linesAdded: 0,
        linesRemoved: 0,
        linesModified: 0,
        totalChanges: 0,
      },
      analysisRecommendation: {
        needsFullFile: changeType === "A" || changeType === "D",
        reason: `File analysis failed (${error?.message ?? error}). Recommend using file_get for manual analysis.`,
        contextLines: 3,
        complexity: "medium",
      },
      lineNumberMapping: {
        beforeLineCount: 0,
        afterLineCount: 0,
        exactLineNumbers: false,
        awsConsoleCompatible: false,
      },
    };
  }

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

    if (totalFiles > 5) {
      summary += `. NOTE: Processed ${totalFiles} files (recommended maximum: 3-5 files per batch for optimal performance)`;
    } else {
      summary += `. Batch size: ${totalFiles} files (optimal for analysis)`;
    }

    return summary;
  }
}
