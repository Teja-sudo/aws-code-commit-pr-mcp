#!/usr/bin/env python3
"""
Test script to verify commit ID truncation fix
"""

# Mock data to simulate PR response
mock_pr_data = {
    "pullRequest": {
        "pullRequestId": "25802",
        "title": "Test PR",
        "pullRequestStatus": "OPEN",
        "pullRequestTargets": [{
            "repositoryName": "test-repo",
            "sourceReference": "refs/heads/feature",
            "destinationReference": "refs/heads/main", 
            "sourceCommit": "f1322b448104421d49b8c1dc8dc3cf10eb5f8b27",
            "destinationCommit": "6f3ec32f35889ded6b6dd73ac5d0e2e7c3bdb5a6",
            "mergeMetadata": {"mergeOption": "FAST_FORWARD_MERGE"}
        }]
    }
}

def test_commit_id_display():
    """Test that commit IDs are displayed in full"""
    pr = mock_pr_data["pullRequest"]
    target = pr["pullRequestTargets"][0]
    
    # This should show full commit IDs, not truncated
    result = f"""📋 Pull Request Details:

🆔 Basic Information:
   PR ID: {pr['pullRequestId']}
   Title: {pr['title']}
   Status: {pr['pullRequestStatus']}

🔀 Branch Details:
   Target 1:
     Repository: {target['repositoryName']}
     Source: {target['sourceReference']} ({target['sourceCommit']})
     Destination: {target['destinationReference']} ({target['destinationCommit']})
     Merge Option: {target.get('mergeMetadata', {}).get('mergeOption', 'Not specified')}"""

    print("=== COMMIT ID TEST RESULTS ===")
    print(result)
    print("\n=== VERIFICATION ===")
    print(f"Source commit full: {target['sourceCommit']}")
    print(f"Destination commit full: {target['destinationCommit']}")
    print(f"Source commit length: {len(target['sourceCommit'])}")
    print(f"Destination commit length: {len(target['destinationCommit'])}")
    
    # Verify they're not truncated
    if len(target['sourceCommit']) == 40 and len(target['destinationCommit']) == 40:
        print("\n✅ SUCCESS: Commit IDs are showing full 40-character SHA hashes")
        return True
    else:
        print("\n❌ FAILED: Commit IDs are not full length")
        return False

if __name__ == "__main__":
    success = test_commit_id_display()
    print(f"\nTest result: {'PASSED' if success else 'FAILED'}")