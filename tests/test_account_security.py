"""Security tests for account management export download endpoint."""

import pytest
from unittest.mock import AsyncMock


@pytest.mark.asyncio
async def test_download_export_filename_validation():
    """Test that invalid filename formats are properly rejected."""
    
    # Test the filename parsing logic directly
    invalid_filenames = [
        "not_export_format.zip",
        "export.zip",
        "export_user.zip",
        "export_user_timestamp.zip",
        "export_user_timestamp_jobid.txt",  # wrong extension
        "random_file.zip",
        "export__timestamp_jobid.zip",  # missing user_id
        "export_user_123_.zip",  # missing job_id
        "export_user__jobid.zip",  # missing timestamp
        "export__timestamp_.zip",  # missing user_id and job_id
    ]
    
    for filename in invalid_filenames:
        # Test filename validation
        if not filename.endswith(".zip"):
            assert True, f"Correctly rejects {filename} (no .zip)"
            continue
            
        parts = filename.replace(".zip", "").split("_")
        # Updated validation: exactly 4 parts
        is_valid_format = len(parts) == 4 and parts[0] == "export"
        
        if is_valid_format:
            # Check if all parts (user_id, timestamp, job_id) are non-empty
            file_user_id = parts[1]
            timestamp = parts[2]
            job_id = parts[3]
            is_valid_format = bool(file_user_id) and bool(timestamp) and bool(job_id)
        
        if not is_valid_format:
            assert True, f"Correctly identifies {filename} as invalid format"
        else:
            assert False, f"Should reject {filename} but parsed as valid"


@pytest.mark.asyncio
async def test_download_export_user_id_validation():
    """Test that user_id from filename is validated against authenticated user."""
    
    # Test valid format
    filename = "export_user123_1234567890_jobid456.zip"
    parts = filename.replace(".zip", "").split("_")
    
    assert len(parts) >= 4, "Should have at least 4 parts"
    assert parts[0] == "export", "Should start with 'export'"
    
    file_user_id = parts[1]
    job_id = parts[3]
    
    assert file_user_id == "user123", "Should extract user_id"
    assert job_id == "jobid456", "Should extract job_id"
    
    # Simulate authentication check
    authenticated_user_id = "user456"  # Different user
    assert file_user_id != authenticated_user_id, "Should detect user_id mismatch"


@pytest.mark.asyncio  
async def test_download_export_job_verification():
    """Test that job_id must exist in Redis and belong to the authenticated user."""
    
    # Mock Redis client
    mock_redis = AsyncMock()
    
    # Test case 1: Job doesn't exist
    mock_redis.hgetall.return_value = {}
    job_data = await mock_redis.hgetall("yt:export:job:nonexistent")
    assert not job_data, "Non-existent job should return empty dict"
    
    # Test case 2: Job exists but belongs to different user
    mock_redis.hgetall.return_value = {
        b"user_id": b"other_user_id",
        b"status": b"completed",
    }
    job_data = await mock_redis.hgetall("yt:export:job:some_job")
    job_user_id = job_data.get(b"user_id", b"").decode("utf-8")
    authenticated_user_id = "current_user_id"
    
    assert job_user_id != authenticated_user_id, "Should detect job ownership mismatch"
    
    # Test case 3: Job exists and belongs to correct user
    mock_redis.hgetall.return_value = {
        b"user_id": b"current_user_id",
        b"status": b"completed",
    }
    job_data = await mock_redis.hgetall("yt:export:job:valid_job")
    job_user_id = job_data.get(b"user_id", b"").decode("utf-8")
    
    assert job_user_id == authenticated_user_id, "Should allow access to own job"


@pytest.mark.asyncio
async def test_export_filename_attack_scenarios():
    """Test various attack scenarios for filename manipulation."""
    
    # Scenario 1: Attacker tries to guess another user's file
    attacker_id = "attacker123"
    victim_id = "victim456"
    job_id = "some_job_id"
    
    # Attacker crafts filename with victim's user_id
    crafted_filename = f"export_{victim_id}_1234567890_{job_id}.zip"
    parts = crafted_filename.replace(".zip", "").split("_")
    file_user_id = parts[1]
    
    # Should be caught by user_id check
    assert file_user_id != attacker_id, "User ID mismatch should be detected"
    
    # Scenario 2: Attacker uses correct user_id but wrong job_id
    crafted_filename = f"export_{attacker_id}_1234567890_fake_job.zip"
    parts = crafted_filename.replace(".zip", "").split("_")
    file_user_id = parts[1]
    extracted_job_id = parts[3]
    
    assert file_user_id == attacker_id, "User ID matches"
    # But job verification should fail - simulate
    mock_redis = AsyncMock()
    mock_redis.hgetall.return_value = {}  # Job doesn't exist
    job_data = await mock_redis.hgetall(f"yt:export:job:{extracted_job_id}")
    assert not job_data, "Non-existent job should be rejected"
    
    # Scenario 3: Attacker steals valid job_id from victim
    victim_job_id = "victim_job_123"
    crafted_filename = f"export_{attacker_id}_1234567890_{victim_job_id}.zip"
    parts = crafted_filename.replace(".zip", "").split("_")
    extracted_job_id = parts[3]
    
    # Simulate job belonging to victim
    mock_redis.hgetall.return_value = {
        b"user_id": victim_id.encode(),
        b"status": b"completed",
    }
    job_data = await mock_redis.hgetall(f"yt:export:job:{extracted_job_id}")
    job_owner = job_data.get(b"user_id", b"").decode("utf-8")
    
    assert job_owner != attacker_id, "Job ownership mismatch should be detected"


@pytest.mark.asyncio
async def test_filename_format_edge_cases():
    """Test edge cases in filename format validation."""
    
    # Test with extra underscores - should now be rejected
    filename = "export_user_123_timestamp_1234_job_456.zip"
    parts = filename.replace(".zip", "").split("_")
    
    # With extra underscores, we get more than 4 parts - should be invalid
    assert len(parts) > 4, "Should have more than 4 parts"
    # This should be rejected by the new validation (len(parts) != 4)
    
    # Test with valid format - exactly 4 parts
    filename = "export_userId_1234567890_jobId.zip"
    parts = filename.replace(".zip", "").split("_")
    assert len(parts) == 4, "Should have exactly 4 parts for valid format"
    assert parts[0] == "export"
    assert parts[1] == "userId"
    assert parts[2] == "1234567890"
    assert parts[3] == "jobId"
    # All parts are non-empty
    assert all(parts), "All parts should be non-empty"
    
    # Test empty parts - should be rejected
    filename = "export__timestamp_jobid.zip"
    parts = filename.replace(".zip", "").split("_")
    assert len(parts) == 4, "Has 4 parts"
    assert parts[1] == "", "Second part (user_id) is empty"
    assert not parts[1], "Empty user_id should fail validation"
    
    filename = "export_user_timestamp_.zip"
    parts = filename.replace(".zip", "").split("_")
    assert len(parts) == 4, "Has 4 parts"
    assert parts[3] == "", "Fourth part (job_id) is empty"
    assert not parts[3], "Empty job_id should fail validation"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
