import { CodeCommitClient } from "@aws-sdk/client-codecommit";
import { fromNodeProviderChain } from "@aws-sdk/credential-providers";
import type { AwsCredentialIdentity, AwsCredentialIdentityProvider } from "@aws-sdk/types";
import { AWSCredentials, MCPConfig } from "../types/index.js";
import * as fs from "fs";
import * as path from "path";
import * as os from "os";

export class AWSAuthManager {
  private client: CodeCommitClient | null = null;
  private credentialProvider: AwsCredentialIdentityProvider | null = null;
  private config: MCPConfig;

  constructor(config: MCPConfig) {
    this.config = config;
  }

  async initialize(): Promise<void> {
    this.buildClient();
  }

  /**
   * Build the credential provider and CodeCommit client.
   * The provider is passed directly to the SDK so token rotation
   * (Fargate task role, EKS IRSA, EC2 IMDS, SSO) is handled automatically.
   */
  private buildClient(): void {
    if (this.config.awsAccessKeyId && this.config.awsSecretAccessKey) {
      // Static credentials forced via constructor config — return them as a provider.
      const accessKeyId = this.config.awsAccessKeyId;
      const secretAccessKey = this.config.awsSecretAccessKey;
      const sessionToken = this.config.awsSessionToken;
      this.credentialProvider = async () => ({
        accessKeyId,
        secretAccessKey,
        sessionToken,
      });
    } else {
      // Default chain: env → SSO → ini → process → web identity (IRSA) → ECS metadata → EC2 IMDS.
      // For WSL cross-mount, we pass an explicit ini filepath rather than mutating process.env.
      const credentialsPath = this.getCredentialsPath();
      const defaultCredPath = path.join(os.homedir(), ".aws", "credentials");

      const init: Parameters<typeof fromNodeProviderChain>[0] = {};
      if (this.config.awsProfile) {
        init.profile = this.config.awsProfile;
      }
      if (credentialsPath && credentialsPath !== defaultCredPath) {
        init.filepath = credentialsPath;
        init.configFilepath = path.join(path.dirname(credentialsPath), "config");
        console.error(`Using credentials from: ${credentialsPath}`);
      }

      this.credentialProvider = fromNodeProviderChain(init);
    }

    this.client = new CodeCommitClient({
      region: this.config.region || "us-east-1",
      credentials: this.credentialProvider,
    });

    console.error(
      `AWS client initialized${
        this.config.awsProfile ? ` for profile: ${this.config.awsProfile}` : ""
      }`
    );
  }

  async refreshCredentials(): Promise<void> {
    console.error("Rebuilding credential provider and client...");
    this.buildClient();
  }

  async switchProfile(profileName: string): Promise<void> {
    this.config.awsProfile = profileName;
    this.config.awsAccessKeyId = undefined;
    this.config.awsSecretAccessKey = undefined;
    this.config.awsSessionToken = undefined;
    this.buildClient();
  }

  async getClient(): Promise<CodeCommitClient> {
    if (!this.client) this.buildClient();
    return this.client!;
  }

  /**
   * Resolve current credentials by invoking the provider.
   * The SDK caches and refreshes internally; this just peeks at the current state.
   */
  async getCredentials(): Promise<AWSCredentials | null> {
    if (!this.credentialProvider) return null;
    try {
      const resolved: AwsCredentialIdentity = await this.credentialProvider();
      return {
        accessKeyId: resolved.accessKeyId,
        secretAccessKey: resolved.secretAccessKey,
        sessionToken: resolved.sessionToken,
        expiration: resolved.expiration,
      };
    } catch (error) {
      console.error("Failed to resolve credentials:", error);
      return null;
    }
  }

  async isCredentialsValid(): Promise<boolean> {
    const creds = await this.getCredentials();
    if (!creds) return false;
    if (!creds.accessKeyId || !creds.secretAccessKey) return false;
    if (creds.expiration) {
      const buffer = 5 * 60 * 1000;
      return creds.expiration.getTime() > Date.now() + buffer;
    }
    return true;
  }

  private getCredentialsPath(): string | null {
    const candidates = [path.join(os.homedir(), ".aws", "credentials")];

    if (this.isWSL()) {
      this.getWindowsUserPaths().forEach((userPath) => {
        candidates.push(path.join(userPath, ".aws", "credentials"));
      });
    }

    for (const credPath of candidates) {
      if (fs.existsSync(credPath)) {
        console.error(`Found AWS credentials at: ${credPath}`);
        return credPath;
      }
    }

    console.error(`AWS credentials not found. Searched: ${candidates.join(", ")}`);
    return null;
  }

  private isWSL(): boolean {
    try {
      if (process.platform !== "linux") return false;
      if (fs.existsSync("/proc/version")) {
        const procVersion = fs.readFileSync("/proc/version", "utf8").toLowerCase();
        return procVersion.includes("microsoft") || procVersion.includes("wsl");
      }
    } catch {
      // ignore
    }
    return false;
  }

  private getWindowsUserPaths(): string[] {
    const paths: string[] = [];
    try {
      const usersDir = "/mnt/c/Users";
      if (fs.existsSync(usersDir)) {
        const skip = new Set(["Public", "Default", "All Users", "Default User"]);
        for (const dir of fs.readdirSync(usersDir, { withFileTypes: true })) {
          if (dir.isDirectory() && !skip.has(dir.name)) {
            paths.push(path.join(usersDir, dir.name));
          }
        }
      }
    } catch (error) {
      console.error("Failed to enumerate Windows user directories:", error);
    }
    return paths;
  }

  /**
   * Reads profile names from BOTH ~/.aws/credentials and ~/.aws/config.
   * Config file uses [profile NAME] syntax for non-default profiles; we strip the prefix.
   */
  getAvailableProfiles(): string[] {
    const profiles = new Set<string>();
    const credPath = this.getCredentialsPath();
    if (!credPath) return [];

    const sectionRegex = /^\[([^\]]+)\]/gm;

    try {
      const content = fs.readFileSync(credPath, "utf8");
      let match: RegExpExecArray | null;
      while ((match = sectionRegex.exec(content)) !== null) {
        profiles.add(match[1]);
      }
    } catch (error) {
      console.error("Failed to read credentials file:", error);
    }

    const configPath = path.join(path.dirname(credPath), "config");
    try {
      if (fs.existsSync(configPath)) {
        const content = fs.readFileSync(configPath, "utf8");
        sectionRegex.lastIndex = 0;
        let match: RegExpExecArray | null;
        while ((match = sectionRegex.exec(content)) !== null) {
          const name = match[1];
          profiles.add(name.startsWith("profile ") ? name.slice(8) : name);
        }
      }
    } catch (error) {
      console.error("Failed to read config file:", error);
    }

    return Array.from(profiles).filter((p) => p !== "default");
  }

  cleanup(): void {
    // No timers or background work to release. The SDK's internal credential
    // cache is GC'd with the client when the auth manager is discarded.
  }
}
