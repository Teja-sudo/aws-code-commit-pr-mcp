import { CodeCommitClient } from "@aws-sdk/client-codecommit";
import { fromIni, fromEnv } from "@aws-sdk/credential-providers";
import { AWSCredentials, MCPConfig } from "../types";
import * as fs from "fs";
import * as path from "path";
import * as os from "os";

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

  private async loadCredentials(isRefresh?: boolean): Promise<void> {
    try {
      let credentialProvider;

      if (this.config.awsAccessKeyId && this.config.awsSecretAccessKey) {
        credentialProvider = {
          accessKeyId: this.config.awsAccessKeyId,
          secretAccessKey: this.config.awsSecretAccessKey,
          sessionToken: this.config.awsSessionToken,
        };
      } else if (this.config.awsProfile) {
        const credentialsPath = this.getCredentialsPath();
        const defaultCredPath = path.join(os.homedir(), ".aws", "credentials");

        // Only specify custom paths if credentials are in a non-default location
        if (credentialsPath && credentialsPath !== defaultCredPath) {
          const configPath = credentialsPath.replace("credentials", "config");
          console.error(`Using credentials from: ${credentialsPath}`);

          credentialProvider = fromIni({
            profile: this.config.awsProfile,
            ignoreCache: Boolean(isRefresh),
            filepath: credentialsPath,
            configFilepath: configPath,
          });
        } else {
          // Use default AWS SDK path resolution
          credentialProvider = fromIni({
            profile: this.config.awsProfile,
            ignoreCache: Boolean(isRefresh),
          });
        }
      } else {
        credentialProvider = fromEnv();
      }

      if (typeof credentialProvider === "function") {
        console.error("Resolving credentials from provider function...");
        const resolvedCredentials = await credentialProvider();
        console.error(
          "Resolved credentials:" + JSON.stringify(resolvedCredentials)
        );

        if (
          !resolvedCredentials.accessKeyId ||
          !resolvedCredentials.secretAccessKey
        ) {
          throw new Error(
            "Credential provider returned incomplete credentials"
          );
        }

        this.credentials = {
          accessKeyId: resolvedCredentials.accessKeyId,
          secretAccessKey: resolvedCredentials.secretAccessKey,
          sessionToken: resolvedCredentials.sessionToken,
          expiration: resolvedCredentials.expiration,
        };

        console.error(
          `Resolved credentials: accessKeyId=${resolvedCredentials.accessKeyId.substring(
            0,
            8
          )}..., hasSessionToken=${!!resolvedCredentials.sessionToken}, expiration=${
            resolvedCredentials.expiration
              ? resolvedCredentials.expiration.toISOString()
              : "none"
          }`
        );
      } else {
        console.error("Using static credentials...");
        this.credentials = credentialProvider as AWSCredentials;

        if (
          !this.credentials.accessKeyId ||
          !this.credentials.secretAccessKey
        ) {
          throw new Error("Static credentials are incomplete");
        }
      }

      // CRITICAL: Always recreate the client with fresh credentials
      // This ensures expired credentials are replaced
      this.client = new CodeCommitClient({
        region: this.config.region || "us-east-1",
        credentials: this.credentials,
      });

      console.error(
        `AWS credentials loaded successfully${
          this.config.awsProfile
            ? ` for profile: ${this.config.awsProfile}`
            : ""
        }`
      );
      console.error(
        `Credentials expire: ${
          this.credentials.expiration
            ? this.credentials.expiration.toISOString()
            : "no expiration"
        }`
      );
    } catch (error) {
      throw new Error(
        `Failed to load AWS credentials: ${
          error instanceof Error ? error.message : "Unknown error"
        }`
      );
    }
  }

  private setupCredentialRefresh(): void {
    const refreshInterval = 0.1 * 60 * 60 * 1000; // 6 minutes

    this.refreshTimer = setInterval(async () => {
      try {
        console.error("Refreshing AWS credentials...");
        await this.loadCredentials(true);
        console.error("AWS credentials refreshed successfully");
      } catch (error) {
        console.error("Failed to refresh AWS credentials:", error);
      }
    }, refreshInterval);
  }

  async refreshCredentials(): Promise<void> {
    console.error("Manual credential refresh requested...");

    // Store old expiration for comparison
    const oldExpiration =
      this.credentials?.expiration?.toISOString() || "no expiration";

    await this.loadCredentials(true);

    const newExpiration =
      this.credentials?.expiration?.toISOString() || "no expiration";
    console.error(
      `Manual credential refresh completed. Old expiration: ${oldExpiration}, New expiration: ${newExpiration}`
    );

    // Verify the client was recreated
    if (this.client) {
      console.error("AWS client recreated with fresh credentials");
    } else {
      console.error("WARNING: AWS client not properly recreated");
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
      console.error("AWS client not initialized, initializing now...");
      await this.initialize();
    }

    // Check if credentials are expired and refresh if needed
    if (!this.isCredentialsValid()) {
      console.error("Credentials expired or invalid, refreshing...");
      try {
        await this.refreshCredentials();
        console.error("Credentials refreshed successfully");
      } catch (error) {
        console.error("Failed to refresh credentials:", error);
        throw new Error(
          `Credential refresh failed: ${
            error instanceof Error ? error.message : "Unknown error"
          }`
        );
      }
    }

    return this.client!;
  }

  getCredentials(): AWSCredentials | null {
    return this.credentials;
  }

  isCredentialsValid(): boolean {
    if (!this.credentials) {
      console.error("No credentials available");
      return false;
    }

    // Check if required credentials fields are present
    if (!this.credentials.accessKeyId || !this.credentials.secretAccessKey) {
      console.error(
        "Credentials missing required fields (accessKeyId or secretAccessKey)"
      );
      return false;
    }

    // Check expiration if present
    if (this.credentials.expiration) {
      const now = new Date();
      const buffer = 5 * 60 * 1000; // 5 minutes buffer
      const isValid =
        this.credentials.expiration.getTime() > now.getTime() + buffer;

      if (!isValid) {
        console.error(
          `Credentials expired. Expiration: ${this.credentials.expiration.toISOString()}, Now: ${now.toISOString()}, Buffer: 5 minutes`
        );
      } else {
        const timeUntilExpiry =
          this.credentials.expiration.getTime() - now.getTime();
        console.error(
          `Credentials valid. Time until expiry: ${Math.round(
            timeUntilExpiry / 1000 / 60
          )} minutes`
        );
      }

      return isValid;
    }

    // If no expiration, assume credentials are long-lived (IAM user keys)
    console.error("Credentials have no expiration (long-lived credentials)");
    return true;
  }

  private getCredentialsPath(): string | null {
    // Try multiple paths in order of preference
    const pathsToTry = [
      // 1. Standard WSL/Linux home directory
      path.join(os.homedir(), ".aws", "credentials"),
    ];

    // 2. If running in WSL, also check Windows user directories
    if (this.isWSL()) {
      const windowsUsers = this.getWindowsUserPaths();
      windowsUsers.forEach((userPath) => {
        pathsToTry.push(path.join(userPath, ".aws", "credentials"));
      });
    }

    // Return the first path that exists
    for (const credPath of pathsToTry) {
      if (fs.existsSync(credPath)) {
        console.error(`Found AWS credentials at: ${credPath}`);
        return credPath;
      }
    }

    console.error(
      `AWS credentials not found. Searched paths: ${pathsToTry.join(", ")}`
    );
    return null;
  }

  private isWSL(): boolean {
    try {
      if (process.platform !== "linux") return false;

      // Check /proc/version for WSL indicators
      if (fs.existsSync("/proc/version")) {
        const procVersion = fs.readFileSync("/proc/version", "utf8");
        return (
          procVersion.toLowerCase().includes("microsoft") ||
          procVersion.toLowerCase().includes("wsl")
        );
      }
    } catch (error) {
      // Ignore errors, assume not WSL
    }
    return false;
  }

  private getWindowsUserPaths(): string[] {
    const paths: string[] = [];

    try {
      // Try to find Windows user directories in /mnt/c/Users/
      const usersDir = "/mnt/c/Users";
      if (fs.existsSync(usersDir)) {
        const userDirs = fs.readdirSync(usersDir, { withFileTypes: true });
        for (const dir of userDirs) {
          if (
            dir.isDirectory() &&
            !["Public", "Default", "All Users", "Default User"].includes(
              dir.name
            )
          ) {
            paths.push(path.join(usersDir, dir.name));
          }
        }
      }
    } catch (error) {
      console.error("Failed to enumerate Windows user directories:", error);
    }

    return paths;
  }

  getAvailableProfiles(): string[] {
    try {
      const credentialsPath = this.getCredentialsPath();
      if (!credentialsPath) {
        return [];
      }

      const content = fs.readFileSync(credentialsPath, "utf8");
      const profiles = content.match(/^\[([^\]]+)\]/gm);

      if (!profiles) return [];

      return profiles
        .map((profile) => profile.slice(1, -1))
        .filter((profile) => profile !== "default");
    } catch (error) {
      console.error("Failed to read AWS profiles:", error);
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
