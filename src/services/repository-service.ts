import {
  ListRepositoriesCommand,
  GetRepositoryCommand,
  ListBranchesCommand,
  GetBranchCommand,
  GetCommitCommand,
  GetDifferencesCommand,
  GetFileCommand,
  GetFolderCommand,
} from '@aws-sdk/client-codecommit';
import { AWSAuthManager } from '../auth/aws-auth';
import { Repository, Branch, Commit, FileDifference, File, PaginatedResult, PaginationOptions } from '../types';
import * as treeify from 'treeify';

export class RepositoryService {
  constructor(private authManager: AWSAuthManager) {}

  async listRepositories(options: PaginationOptions = {}): Promise<PaginatedResult<Repository>> {
    const client = await this.authManager.getClient();
    const command = new ListRepositoriesCommand({
      nextToken: options.nextToken,
    });

    const response = await client.send(command);
    
    const repositories: Repository[] = (response.repositories || []).map(repo => ({
      repositoryName: repo.repositoryName || '',
      repositoryId: repo.repositoryId || '',
      repositoryDescription: undefined,
      defaultBranch: undefined,
      lastModifiedDate: undefined,
      creationDate: undefined,
      cloneUrlHttp: undefined,
      cloneUrlSsh: undefined,
      arn: undefined,
    }));

    return {
      items: repositories,
      nextToken: response.nextToken,
    };
  }

  async getRepository(repositoryName: string): Promise<Repository> {
    const client = await this.authManager.getClient();
    const command = new GetRepositoryCommand({ repositoryName });

    const response = await client.send(command);
    const repo = response.repositoryMetadata;

    if (!repo) {
      throw new Error(`Repository ${repositoryName} not found`);
    }

    return {
      repositoryName: repo.repositoryName || '',
      repositoryId: repo.repositoryId || '',
      repositoryDescription: repo.repositoryDescription,
      defaultBranch: repo.defaultBranch,
      lastModifiedDate: repo.lastModifiedDate,
      creationDate: repo.creationDate,
      cloneUrlHttp: repo.cloneUrlHttp,
      cloneUrlSsh: repo.cloneUrlSsh,
      arn: repo.Arn,
    };
  }

  async listBranches(repositoryName: string, options: PaginationOptions = {}): Promise<PaginatedResult<Branch>> {
    const client = await this.authManager.getClient();
    const command = new ListBranchesCommand({
      repositoryName,
      nextToken: options.nextToken,
    });

    const response = await client.send(command);
    
    const branches: Branch[] = (response.branches || []).map(branch => ({
      branchName: branch || '',
      commitId: '', // Will need to get commit ID separately
    }));

    // Get commit IDs for each branch
    const branchesWithCommits = await Promise.all(
      branches.map(async (branch) => {
        try {
          const branchDetails = await this.getBranch(repositoryName, branch.branchName);
          return branchDetails;
        } catch (error) {
          console.error(`Failed to get details for branch ${branch.branchName}:`, error);
          return branch;
        }
      })
    );

    return {
      items: branchesWithCommits,
      nextToken: response.nextToken,
    };
  }

  async getBranch(repositoryName: string, branchName: string): Promise<Branch> {
    const client = await this.authManager.getClient();
    const command = new GetBranchCommand({
      repositoryName,
      branchName,
    });

    const response = await client.send(command);
    
    return {
      branchName: response.branch?.branchName || branchName,
      commitId: response.branch?.commitId || '',
    };
  }

  async getCommit(repositoryName: string, commitId: string): Promise<Commit> {
    const client = await this.authManager.getClient();
    const command = new GetCommitCommand({
      repositoryName,
      commitId,
    });

    const response = await client.send(command);
    const commit = response.commit;

    if (!commit) {
      throw new Error(`Commit ${commitId} not found in repository ${repositoryName}`);
    }

    return {
      commitId: commit.commitId || '',
      treeId: commit.treeId || '',
      parents: commit.parents,
      message: commit.message,
      author: commit.author ? {
        name: commit.author.name || '',
        email: commit.author.email || '',
        date: commit.author.date || '',
      } : undefined,
      committer: commit.committer ? {
        name: commit.committer.name || '',
        email: commit.committer.email || '',
        date: commit.committer.date || '',
      } : undefined,
      additionalData: commit.additionalData,
    };
  }

  async getDifferences(
    repositoryName: string,
    beforeCommitSpecifier: string,
    afterCommitSpecifier: string,
    beforePath?: string,
    afterPath?: string,
    options: PaginationOptions = {}
  ): Promise<PaginatedResult<FileDifference>> {
    const client = await this.authManager.getClient();
    const command = new GetDifferencesCommand({
      repositoryName,
      beforeCommitSpecifier,
      afterCommitSpecifier,
      beforePath,
      afterPath,
      NextToken: options.nextToken,
      MaxResults: options.maxResults || 100,
    });

    const response = await client.send(command);
    
    const differences: FileDifference[] = (response.differences || []).map(diff => ({
      changeType: diff.changeType as 'A' | 'D' | 'M',
      beforeBlob: diff.beforeBlob ? {
        blobId: diff.beforeBlob.blobId || '',
        path: diff.beforeBlob.path || '',
        mode: diff.beforeBlob.mode || '',
      } : undefined,
      afterBlob: diff.afterBlob ? {
        blobId: diff.afterBlob.blobId || '',
        path: diff.afterBlob.path || '',
        mode: diff.afterBlob.mode || '',
      } : undefined,
    }));

    return {
      items: differences,
      nextToken: response.NextToken,
    };
  }

  async getFile(repositoryName: string, commitSpecifier: string, filePath: string): Promise<{ content: string; blobId: string }> {
    const client = await this.authManager.getClient();
    const command = new GetFileCommand({
      repositoryName,
      commitSpecifier,
      filePath,
    });

    const response = await client.send(command);
    
    if (!response.fileContent) {
      throw new Error(`File ${filePath} not found at commit ${commitSpecifier}`);
    }

    const content = Buffer.from(response.fileContent).toString('utf8');
    
    return {
      content,
      blobId: response.blobId || '',
    };
  }

  async getFolder(repositoryName: string, commitSpecifier: string, folderPath: string): Promise<File[]> {
    const client = await this.authManager.getClient();
    const command = new GetFolderCommand({
      repositoryName,
      commitSpecifier,
      folderPath,
    });

    const response = await client.send(command);
    
    const files: File[] = [];
    
    if (response.files) {
      files.push(...response.files.map(file => ({
        absolutePath: file.absolutePath || '',
        blobId: file.blobId || '',
        fileMode: file.fileMode || '',
      })));
    }

    if (response.subFolders) {
      files.push(...response.subFolders.map(folder => ({
        absolutePath: folder.absolutePath || '',
        blobId: folder.treeId || '',
        fileMode: 'folder',
      })));
    }

    return files;
  }

  async searchRepositories(searchTerm: string, options: PaginationOptions = {}): Promise<PaginatedResult<Repository>> {
    const allRepos = await this.listRepositories(options);
    
    const filteredRepos = allRepos.items.filter(repo => 
      repo.repositoryName.toLowerCase().includes(searchTerm.toLowerCase()) ||
      (repo.repositoryDescription && repo.repositoryDescription.toLowerCase().includes(searchTerm.toLowerCase()))
    );

    return {
      items: filteredRepos,
      nextToken: allRepos.nextToken,
    };
  }

  async getRepositoryTree(
    repositoryName: string, 
    commitSpecifier: string, 
    treePath: string = "/", 
    maxDepth?: number
  ): Promise<any> {
    try {
      // Build tree structure recursively using GetFolderCommand
      const tree = await this.buildTreeRecursively(
        repositoryName, 
        commitSpecifier, 
        treePath === "/" ? "" : treePath, 
        0, 
        maxDepth || 10
      );
      
      // Format with treeify
      const treeFormatted = treeify.asTree(tree, true, true);
      
      // Count files and folders
      const counts = this.countFilesAndFolders(tree);
      
      return {
        repositoryName,
        commitSpecifier,
        treePath,
        maxDepth,
        totalFiles: counts.files,
        totalFolders: counts.folders,
        treeFormatted,
        rawStructure: tree
      };
    } catch (error) {
      console.error(`Error getting repository tree:`, error);
      throw new Error(`Could not retrieve tree for repository '${repositoryName}': ${error}`);
    }
  }

  async searchInFile(
    repositoryName: string,
    commitSpecifier: string,
    filePath: string,
    searchPatterns: Array<{
      pattern: string;
      type: 'regex' | 'literal' | 'function' | 'class' | 'import' | 'variable';
      caseSensitive?: boolean;
    }>,
    options: {
      maxResults?: number;
      includeContext?: boolean;
      contextLines?: number;
    } = {}
  ): Promise<any> {
    const { maxResults = 50, includeContext = true, contextLines = 3 } = options;
    
    try {
      // Get the specific file content
      const fileContent = await this.getFile(repositoryName, commitSpecifier, filePath);
      const lines = fileContent.content.split('\n');
      
      const searchResults = [];
      
      for (const searchPattern of searchPatterns) {
        const patternResults = {
          pattern: searchPattern.pattern,
          type: searchPattern.type,
          matches: [] as any[],
          totalMatches: 0
        };
        
        const matches = this.performSearch(
          lines, 
          searchPattern, 
          includeContext, 
          contextLines,
          maxResults
        );
        
        patternResults.matches = matches;
        patternResults.totalMatches = matches.length;
        searchResults.push(patternResults);
      }
      
      return {
        repositoryName,
        commitSpecifier,
        filePath,
        fileSize: fileContent.content.length,
        totalLines: lines.length,
        searchPatterns,
        results: searchResults,
        summary: {
          totalPatterns: searchPatterns.length,
          totalMatches: searchResults.reduce((sum, r) => sum + r.totalMatches, 0)
        }
      };
    } catch (error) {
      console.error(`Error searching in file ${filePath}:`, error);
      throw new Error(`Could not search in file '${filePath}' in repository '${repositoryName}': ${error}`);
    }
  }

  private async buildTreeRecursively(
    repositoryName: string,
    commitSpecifier: string,
    folderPath: string,
    currentDepth: number,
    maxDepth: number
  ): Promise<any> {
    const client = await this.authManager.getClient();
    const tree: any = {};
    
    if (currentDepth >= maxDepth) {
      return tree;
    }
    
    try {
      const command = new GetFolderCommand({
        repositoryName,
        commitSpecifier,
        folderPath: folderPath || "/",
      });
      
      const response = await client.send(command);
      
      // Add files
      if (response.files) {
        for (const file of response.files) {
          if (file.absolutePath) {
            const fileName = file.absolutePath.split('/').pop() || file.absolutePath;
            tree[fileName] = null; // null indicates it's a file for treeify
          }
        }
      }
      
      // Add subfolders recursively
      if (response.subFolders) {
        for (const folder of response.subFolders) {
          if (folder.absolutePath) {
            const folderName = folder.absolutePath.split('/').pop() || folder.absolutePath;
            tree[folderName] = await this.buildTreeRecursively(
              repositoryName,
              commitSpecifier,
              folder.absolutePath,
              currentDepth + 1,
              maxDepth
            );
          }
        }
      }
    } catch (error) {
      console.error(`Error getting folder ${folderPath}:`, error);
      // If we can't access this folder, return empty tree
    }
    
    return tree;
  }

  private countFilesAndFolders(tree: any): { files: number, folders: number } {
    let files = 0;
    let folders = 0;
    
    for (const [_key, value] of Object.entries(tree)) {
      if (value === null) {
        files++;
      } else if (typeof value === 'object') {
        folders++;
        const subCounts = this.countFilesAndFolders(value);
        files += subCounts.files;
        folders += subCounts.folders;
      }
    }
    
    return { files, folders };
  }

  private performSearch(
    lines: string[],
    searchPattern: any,
    includeContext: boolean,
    contextLines: number,
    maxResults: number
  ): any[] {
    const matches: any[] = [];
    const { pattern, type, caseSensitive = false } = searchPattern;
    
    let searchRegex: RegExp;
    
    try {
      switch (type) {
        case 'regex':
          // Handle regex patterns
          if (pattern.startsWith('/') && pattern.includes('/', 1)) {
            const lastSlash = pattern.lastIndexOf('/');
            const regexPattern = pattern.slice(1, lastSlash);
            const flags = pattern.slice(lastSlash + 1);
            searchRegex = new RegExp(regexPattern, flags);
          } else {
            searchRegex = new RegExp(pattern, caseSensitive ? 'g' : 'gi');
          }
          break;
        case 'function':
          searchRegex = new RegExp(`(function\\s+${pattern}\\s*\\(|${pattern}\\s*[:=]\\s*function|${pattern}\\s*\\([^)]*\\)\\s*=>)`, caseSensitive ? 'g' : 'gi');
          break;
        case 'class':
          searchRegex = new RegExp(`class\\s+${pattern}\\b`, caseSensitive ? 'g' : 'gi');
          break;
        case 'import':
          searchRegex = new RegExp(`(import.*${pattern}|from\\s+['"].*${pattern})`, caseSensitive ? 'g' : 'gi');
          break;
        case 'variable':
          searchRegex = new RegExp(`\\b${pattern}\\b`, caseSensitive ? 'g' : 'gi');
          break;
        case 'literal':
        default:
          searchRegex = new RegExp(pattern.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), caseSensitive ? 'g' : 'gi');
          break;
      }
      
      lines.forEach((line, lineIndex) => {
        if (matches.length >= maxResults) return;
        
        const lineMatches = line.match(searchRegex);
        if (lineMatches) {
          const contextStart = Math.max(0, lineIndex - contextLines);
          const contextEnd = Math.min(lines.length - 1, lineIndex + contextLines);
          
          const context = includeContext ? {
            before: lines.slice(contextStart, lineIndex),
            after: lines.slice(lineIndex + 1, contextEnd + 1)
          } : null;
          
          matches.push({
            lineNumber: lineIndex + 1,
            line: line.trim(),
            matchCount: lineMatches.length,
            context
          });
        }
      });
    } catch (error) {
      console.error(`Error creating search regex for pattern '${pattern}':`, error);
    }
    
    return matches;
  }
}