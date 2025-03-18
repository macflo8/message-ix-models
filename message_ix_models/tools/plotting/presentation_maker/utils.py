from typing import List


def common_starting_substring(strings: List[str]):
    if not strings:
        return ""

    # Find the minimum length among all strings
    min_length = min(len(s) for s in strings)

    # Iterate through characters at each position
    for i in range(min_length):
        # Check if all characters at position i are the same
        if len(set(s[i] for s in strings)) > 1:
            return strings[0][:i]  # Return the common prefix
    # If all characters match up to min_length, return any string (they're all the same)
    return strings[0][:min_length]
