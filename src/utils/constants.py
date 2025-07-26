"""
Constants used throughout the AWS CodeCommit PR MCP Server
"""

# Constants for huge PR handling
MAX_FILE_SIZE_FOR_DIFF = (
    100 * 1024
)  # 100KB - Files larger than this won't have diffs generated
MAX_LINES_FOR_PREVIEW = 100  # Maximum lines to show in file previews
MAX_RETRIES = 3  # Maximum number of retry attempts for AWS API calls
RETRY_DELAY = 1.0  # Initial delay in seconds for retry backoff

# Pagination constants
MAX_FILES_PER_PAGE = 100  # AWS API limit for get_differences
DEFAULT_CHUNK_SIZE = 500  # Default lines per chunk for file content
MAX_CHUNK_SIZE = 500  # Maximum lines per chunk to prevent memory issues

# Streaming constants
STREAM_CHUNK_SIZE = 50  # Number of files to process in streaming chunks
ASYNC_YIELD_INTERVAL = 10  # Yield control every N files for responsiveness

# Binary file detection
BINARY_EXTENSIONS = {
    ".exe",
    ".dll",
    ".so",
    ".bin",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".bmp",
    ".ico",
    ".zip",
    ".tar",
    ".gz",
    ".pdf",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".ppt",
    ".pptx",
    ".mp3",
    ".mp4",
    ".avi",
    ".mov",
    ".wmv",
}
