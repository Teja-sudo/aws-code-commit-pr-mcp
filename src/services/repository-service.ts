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

export class RepositoryService {
  constructor(private authManager: AWSAuthManager) {}

  async listRepositories(options: PaginationOptions = {}): Promise<PaginatedResult<Repository>> {
    const client = this.authManager.getClient();
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
    const client = this.authManager.getClient();
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
    const client = this.authManager.getClient();
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
          console.warn(`Failed to get details for branch ${branch.branchName}:`, error);
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
    const client = this.authManager.getClient();
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
    const client = this.authManager.getClient();
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
    const client = this.authManager.getClient();
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
    const client = this.authManager.getClient();
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
    const client = this.authManager.getClient();
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
}