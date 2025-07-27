#!/usr/bin/env python3

import re

# Test the line tracking logic
sample_diff = [
    "--- a/test.py",
    "+++ b/test.py", 
    "@@ -1,4 +1,5 @@",
    " def hello():",
    "-    print('old')",
    "+    print('new')",
    "+    print('added')",
    " return True"
]

before_line_num = 0
after_line_num = 0
changed_after_lines = []
changed_before_lines = []

print("=== Line Tracking Debug ===")

for line in sample_diff:
    print(f"Processing line: '{line}' | before_num: {before_line_num}, after_num: {after_line_num}")
    if line.startswith("@@"):
        match = re.search(r"-(\d+)(?:,\d+)? \+(\d+)(?:,\d+)?", line)
        if match:
            before_line_num = int(match.group(1)) - 1  # Line 1 becomes 0
            after_line_num = int(match.group(2)) - 1   # Line 1 becomes 0
            print(f"  Hunk header: before_num reset to {before_line_num}, after_num reset to {after_line_num}")
    elif line.startswith("-") and not line.startswith("---"):
        before_line_num += 1
        changed_before_lines.append(before_line_num)
        print(f"  Deletion: before_line {before_line_num} added to changed_before_lines")
    elif line.startswith("+") and not line.startswith("+++"):
        after_line_num += 1
        changed_after_lines.append(after_line_num)
        print(f"  Addition: after_line {after_line_num} added to changed_after_lines")
    elif line and not line.startswith("\\") and not line.startswith("---") and not line.startswith("+++") and not line.startswith("@@"):
        before_line_num += 1
        after_line_num += 1
        print(f"  Context: both counters incremented to before={before_line_num}, after={after_line_num}")

print(f"\nFinal results:")
print(f"  changed_after_lines={changed_after_lines}")
print(f"  changed_before_lines={changed_before_lines}")

print(f"\nExpected:")
print(f"  changed_after_lines should be [2, 3] (print('new') at line 2, print('added') at line 3)")
print(f"  changed_before_lines should be [2] (print('old') at line 2)")