import { MatchSpec } from "../types/index.js";
import { MCPValidationError } from "./error-handler.js";

const MAX_PATTERN_LEN = 200;

/**
 * Matches a target string against a MatchSpec.
 * - exact: value === target (case-insensitive by default)
 * - substring: target.includes(value) (case-insensitive by default)
 * - regex: new RegExp(value), with the same 200-char cap as code_search
 *
 * Returns false if target is undefined / null. Throws MCPValidationError for
 * invalid regex, oversized patterns, or unknown mode.
 */
export function matchString(target: string | undefined | null, spec: MatchSpec): boolean {
  if (target === undefined || target === null) return false;
  if (typeof spec.value !== "string") {
    throw new MCPValidationError("MatchSpec.value must be a string");
  }
  if (spec.value.length > MAX_PATTERN_LEN) {
    throw new MCPValidationError(
      `MatchSpec.value exceeds ${MAX_PATTERN_LEN} chars; refine the search`
    );
  }

  const mode = spec.mode ?? "substring";
  const caseSensitive = spec.caseSensitive ?? false;

  switch (mode) {
    case "exact":
      return caseSensitive
        ? target === spec.value
        : target.toLowerCase() === spec.value.toLowerCase();
    case "substring":
      return caseSensitive
        ? target.includes(spec.value)
        : target.toLowerCase().includes(spec.value.toLowerCase());
    case "regex": {
      let re: RegExp;
      try {
        re = new RegExp(spec.value, caseSensitive ? "" : "i");
      } catch (err) {
        throw new MCPValidationError(
          `Invalid regex in MatchSpec.value: ${err instanceof Error ? err.message : String(err)}`
        );
      }
      return re.test(target);
    }
    default:
      throw new MCPValidationError(
        `MatchSpec.mode must be one of: exact, substring, regex`
      );
  }
}
