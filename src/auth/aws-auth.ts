import { CodeCommitClient } from '@aws-sdk/client-codecommit';
import { fromIni, fromEnv } from '@aws-sdk/credential-providers';
import { AWSCredentials, MCPConfig } from '../types';
import * as fs from 'fs';
import * as path from 'path';
import * as os from 'os';

export class AWSAuthManager {
  private client: CodeCommitClient | null = null;
  private credentials: AWSCredentials | null = null;
  private config: MCPConfig;
  private refreshTimer: NodeJS.Timeout | null = null;

  constructor(config: MCPConfig) {
    this.config = config;
  }

  async initialize(): Promise<void> {
    await this.loadCredentials();
    this.setupCredentialRefresh();
  }

  private async loadCredentials(): Promise<void> {
    try {
      let credentialProvider;

      if (this.config.awsAccessKeyId && this.config.awsSecretAccessKey) {
        credentialProvider = {
          accessKeyId: this.config.awsAccessKeyId,
          secretAccessKey: this.config.awsSecretAccessKey,
          sessionToken: this.config.awsSessionToken,
        };
      } else if (this.config.awsProfile) {
        credentialProvider = fromIni({ profile: this.config.awsProfile });
      } else {
        credentialProvider = fromEnv();
      }

      this.client = new CodeCommitClient({
        region: this.config.region || 'us-east-1',
        credentials: credentialProvider,
      });

      if (typeof credentialProvider === 'function') {
        const resolvedCredentials = await credentialProvider();
        this.credentials = {
          accessKeyId: resolvedCredentials.accessKeyId,
          secretAccessKey: resolvedCredentials.secretAccessKey,
          sessionToken: resolvedCredentials.sessionToken,
          expiration: resolvedCredentials.expiration,
        };
      } else {
        this.credentials = credentialProvider as AWSCredentials;
      }

      console.log(`AWS credentials loaded successfully${this.config.awsProfile ? ` for profile: ${this.config.awsProfile}` : ''}`);
    } catch (error) {
      throw new Error(`Failed to load AWS credentials: ${error instanceof Error ? error.message : 'Unknown error'}`);
    }
  }

  private setupCredentialRefresh(): void {
    const refreshInterval = 7.5 * 60 * 60 * 1000; // 7.5 hours

    this.refreshTimer = setInterval(async () => {
      try {
        console.log('Refreshing AWS credentials...');
        await this.loadCredentials();
        console.log('AWS credentials refreshed successfully');
      } catch (error) {
        console.error('Failed to refresh AWS credentials:', error);
      }
    }, refreshInterval);
  }

  async refreshCredentials(): Promise<void> {
    await this.loadCredentials();
  }

  async switchProfile(profileName: string): Promise<void> {
    this.config.awsProfile = profileName;
    this.config.awsAccessKeyId = undefined;
    this.config.awsSecretAccessKey = undefined;
    this.config.awsSessionToken = undefined;
    await this.loadCredentials();
  }

  getClient(): CodeCommitClient {
    if (!this.client) {
      throw new Error('AWS client not initialized. Call initialize() first.');
    }
    return this.client;
  }

  getCredentials(): AWSCredentials | null {
    return this.credentials;
  }

  isCredentialsValid(): boolean {
    if (!this.credentials) return false;
    
    if (this.credentials.expiration) {
      const now = new Date();
      const buffer = 5 * 60 * 1000; // 5 minutes buffer
      return this.credentials.expiration.getTime() > now.getTime() + buffer;
    }
    
    return true;
  }

  getAvailableProfiles(): string[] {
    try {
      const credentialsPath = path.join(os.homedir(), '.aws', 'credentials');
      if (!fs.existsSync(credentialsPath)) {
        return [];
      }

      const content = fs.readFileSync(credentialsPath, 'utf8');
      const profiles = content.match(/^\[([^\]]+)\]/gm);
      
      if (!profiles) return [];
      
      return profiles.map(profile => profile.slice(1, -1)).filter(profile => profile !== 'default');
    } catch (error) {
      console.error('Failed to read AWS profiles:', error);
      return [];
    }
  }

  cleanup(): void {
    if (this.refreshTimer) {
      clearInterval(this.refreshTimer);
      this.refreshTimer = null;
    }
  }
}