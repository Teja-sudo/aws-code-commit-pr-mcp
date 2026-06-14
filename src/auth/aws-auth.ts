import { CodeCommitClient } from "@aws-sdk/client-codecommit";
import { fromNodeProviderChain, fromIni } from "@aws-sdk/credential-providers";
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
   *
   * @param ignoreCache When true, the ini-file provider bypasses the AWS SDK's
   *   module-level shared-config cache and re-reads the credentials file from
   *   disk. This is REQUIRED for aws_creds_refresh to pick up a rotated profile:
   *   the SDK caches parsed credentials/config files for the life of the process,
   *   so simply rebuilding the provider would otherwise resolve the stale parse.
   */
  private buildClient(ignoreCache = false): void {
    if (this.config.awsProfile) {
      // An explicit profile wins over ambient env access keys: if AWS_PROFILE is
      // set, the user means "use this profile". We call fromIni directly rather
      // than the full chain (whose fromEnv step would let stale env keys shadow
      // the profile), and pass ignoreCache so a refresh re-reads the rotated file.
      const init: NonNullable<Parameters<typeof fromIni>[0]> = {
        profile: this.config.awsProfile,
        ignoreCache,
      };
      const credentialsPath = this.getCredentialsPath();
      const defaultCredPath = path.join(os.homedir(), ".aws", "credentials");
      if (credentialsPath && credentialsPath !== defaultCredPath) {
        init.filepath = credentialsPath;
        init.configFilepath = path.join(path.dirname(credentialsPath), "config");
        console.error(`Using credentials from: ${credentialsPath}`);
      }
      this.credentialProvider = fromIni(init);
    } else if (this.config.awsAccessKeyId && this.config.awsSecretAccessKey) {
      // Static credentials from env / constructor config. NOTE: this is a frozen
      // snapshot — if these are temporary (STS) credentials they cannot be
      // refreshed in-process. Use a profile if you need aws_creds_refresh to work.
      const accessKeyId = this.config.awsAccessKeyId;
      const secretAccessKey = this.config.awsSecretAccessKey;
      const sessionToken = this.config.awsSessionToken;
      this.credentialProvider = async () => ({
        accessKeyId,
        secretAccessKey,
        sessionToken,
      });
    } else {
      // No profile, no static creds: full chain for Fargate / ECS task roles,
      // EKS IRSA, EC2 IMDS, and SSO. These rotate automatically via the SDK.
      this.credentialProvider = fromNodeProviderChain({ ignoreCache });
    }

    this.client = new CodeCommitClient({
      region: this.config.region || "us-east-1",
      credentials: this.credentialProvider,
    });

    console.error(
      `AWS client initialized${
        this.config.awsProfile ? ` for profile: ${this.config.awsProfile}` : ""
      }${ignoreCache ? " (file cache bypassed)" : ""}`
    );
  }

  async refreshCredentials(): Promise<void> {
    console.error("Rebuilding credential provider and client (bypassing file cache)...");
    this.buildClient(true);
  }

  async switchProfile(profileName: string): Promise<void> {
    this.config.awsProfile = profileName;
    this.config.awsAccessKeyId = undefined;
    this.config.awsSecretAccessKey = undefined;
    this.config.awsSessionToken = undefined;
    this.buildClient(true);
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
