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

      if (typeof credentialProvider === 'function') {
        console.error('Resolving credentials from provider function...');
        const resolvedCredentials = await credentialProvider();
        
        if (!resolvedCredentials.accessKeyId || !resolvedCredentials.secretAccessKey) {
          throw new Error('Credential provider returned incomplete credentials');
        }
        
        this.credentials = {
          accessKeyId: resolvedCredentials.accessKeyId,
          secretAccessKey: resolvedCredentials.secretAccessKey,
          sessionToken: resolvedCredentials.sessionToken,
          expiration: resolvedCredentials.expiration,
        };
        
        console.error(`Resolved credentials: accessKeyId=${resolvedCredentials.accessKeyId.substring(0, 8)}..., hasSessionToken=${!!resolvedCredentials.sessionToken}, expiration=${resolvedCredentials.expiration ? resolvedCredentials.expiration.toISOString() : 'none'}`);
      } else {
        console.error('Using static credentials...');
        this.credentials = credentialProvider as AWSCredentials;
        
        if (!this.credentials.accessKeyId || !this.credentials.secretAccessKey) {
          throw new Error('Static credentials are incomplete');
        }
      }

      // CRITICAL: Always recreate the client with fresh credentials
      // This ensures expired credentials are replaced
      this.client = new CodeCommitClient({
        region: this.config.region || 'us-east-1',
        credentials: this.credentials,
      });

      console.error(`AWS credentials loaded successfully${this.config.awsProfile ? ` for profile: ${this.config.awsProfile}` : ''}`);
      console.error(`Credentials expire: ${this.credentials.expiration ? this.credentials.expiration.toISOString() : 'no expiration'}`);
    } catch (error) {
      throw new Error(`Failed to load AWS credentials: ${error instanceof Error ? error.message : 'Unknown error'}`);
    }
  }

  private setupCredentialRefresh(): void {
    const refreshInterval = 7.5 * 60 * 60 * 1000; // 7.5 hours

    this.refreshTimer = setInterval(async () => {
      try {
        console.error('Refreshing AWS credentials...');
        await this.loadCredentials();
        console.error('AWS credentials refreshed successfully');
      } catch (error) {
        console.error('Failed to refresh AWS credentials:', error);
      }
    }, refreshInterval);
  }

  async refreshCredentials(): Promise<void> {
    console.error('Manual credential refresh requested...');
    
    // Store old expiration for comparison
    const oldExpiration = this.credentials?.expiration?.toISOString() || 'no expiration';
    
    await this.loadCredentials();
    
    const newExpiration = this.credentials?.expiration?.toISOString() || 'no expiration';
    console.error(`Manual credential refresh completed. Old expiration: ${oldExpiration}, New expiration: ${newExpiration}`);
    
    // Verify the client was recreated
    if (this.client) {
      console.error('AWS client recreated with fresh credentials');
    } else {
      console.error('WARNING: AWS client not properly recreated');
    }
  }

  async switchProfile(profileName: string): Promise<void> {
    this.config.awsProfile = profileName;
    this.config.awsAccessKeyId = undefined;
    this.config.awsSecretAccessKey = undefined;
    this.config.awsSessionToken = undefined;
    await this.loadCredentials();
  }

  async getClient(): Promise<CodeCommitClient> {
    if (!this.client) {
      console.error('AWS client not initialized, initializing now...');
      await this.initialize();
    }
    
    // Check if credentials are expired and refresh if needed
    if (!this.isCredentialsValid()) {
      console.error('Credentials expired or invalid, refreshing...');
      try {
        await this.refreshCredentials();
        console.error('Credentials refreshed successfully');
      } catch (error) {
        console.error('Failed to refresh credentials:', error);
        throw new Error(`Credential refresh failed: ${error instanceof Error ? error.message : 'Unknown error'}`);
      }
    }
    
    return this.client!;
  }

  getCredentials(): AWSCredentials | null {
    return this.credentials;
  }

  isCredentialsValid(): boolean {
    if (!this.credentials) {
      console.error('No credentials available');
      return false;
    }
    
    // Check if required credentials fields are present
    if (!this.credentials.accessKeyId || !this.credentials.secretAccessKey) {
      console.error('Credentials missing required fields (accessKeyId or secretAccessKey)');
      return false;
    }
    
    // Check expiration if present
    if (this.credentials.expiration) {
      const now = new Date();
      const buffer = 5 * 60 * 1000; // 5 minutes buffer
      const isValid = this.credentials.expiration.getTime() > now.getTime() + buffer;
      
      if (!isValid) {
        console.error(`Credentials expired. Expiration: ${this.credentials.expiration.toISOString()}, Now: ${now.toISOString()}, Buffer: 5 minutes`);
      } else {
        const timeUntilExpiry = this.credentials.expiration.getTime() - now.getTime();
        console.error(`Credentials valid. Time until expiry: ${Math.round(timeUntilExpiry / 1000 / 60)} minutes`);
      }
      
      return isValid;
    }
    
    // If no expiration, assume credentials are long-lived (IAM user keys)
    console.error('Credentials have no expiration (long-lived credentials)');
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