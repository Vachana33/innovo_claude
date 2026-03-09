# Company Preprocessing Observability - Logging Implementation

## Overview
Added structured logging throughout the company preprocessing pipeline to enable real-time debugging and verification of preprocessing status.

## Files Modified

### Backend Files
1. **`backend/app/routers/companies.py`** - Enhanced logging in background task and task enqueue
2. **`backend/app/preprocessing.py`** - Enhanced logging in website crawling and audio transcription

---

## Log Messages Added

### 1. Task Enqueue (Company Creation)
**Location**: `create_company_in_program()` function
**Message**: 
```
INFO Company preprocessing task enqueued for company_id=<id>
```
**When**: Background task is scheduled after company creation

---

### 2. Preprocessing Start
**Location**: `process_company_background()` function
**Message**:
```
INFO Starting preprocessing for company_id=<id>
```
**When**: Background task begins execution

---

### 3. Website Data Extraction
**Location**: `process_company_background()` function
**Messages**:
```
INFO Extracting website data for company_id=<id> (url=<url>)
INFO Website data extraction completed for company_id=<id> (extracted <N> characters)
```
**When**: 
- Before website crawling starts
- After website crawling completes successfully

**Additional logging in `crawl_website()`**:
```
INFO Starting website crawl: url=<url>, max_pages=<N>
INFO Website crawl completed: url=<url>, pages_crawled=<N>, text_length=<N>
WARNING Website crawl completed but no text extracted: url=<url>
ERROR Website crawl error: url=<url>, error=<error>
```

---

### 4. Audio Transcription
**Location**: `process_company_background()` function
**Messages**:
```
INFO Transcribing audio for company_id=<id> (audio_path=<path>)
INFO Audio transcription completed for company_id=<id> (transcript length: <N> characters)
```
**When**:
- Before audio transcription starts
- After audio transcription completes successfully

**Additional logging in `transcribe_audio()`**:
```
INFO Starting audio transcription: audio_path=<path>
INFO Audio transcription completed: audio_path=<path>, transcript_length=<N>
ERROR Audio transcription error: audio_path=<path>, error=<error>
```

---

### 5. Preprocessing Completion
**Location**: `process_company_background()` function
**Message**:
```
INFO Finished preprocessing for company_id=<id>
```
**When**: All preprocessing steps complete successfully, status set to "done"

---

### 6. Preprocessing Failure
**Location**: `process_company_background()` function
**Messages**:
```
ERROR Preprocessing failed for company_id=<id>: <error>
ERROR Failed to update error status for company_id=<id>: <error>
```
**When**: 
- Exception occurs during preprocessing
- Failed to update database with error status

**Individual step failures**:
```
ERROR Website data extraction failed for company_id=<id>: <error>
ERROR Audio transcription failed for company_id=<id>: <error>
```

---

## Example Log Output

### Successful Preprocessing Flow

```
INFO Company preprocessing task enqueued for company_id=3
INFO Starting preprocessing for company_id=3
INFO Extracting website data for company_id=3 (url=https://example.com)
INFO Starting website crawl: url=https://example.com, max_pages=20
INFO Website crawl completed: url=https://example.com, pages_crawled=5, text_length=12345
INFO Website data extraction completed for company_id=3 (extracted 12345 characters)
INFO Transcribing audio for company_id=3 (audio_path=uploads/audio/abc123.mp3)
INFO Starting audio transcription: audio_path=uploads/audio/abc123.mp3
INFO Audio transcription completed: audio_path=uploads/audio/abc123.mp3, transcript_length=5678
INFO Audio transcription completed for company_id=3 (transcript length: 5678 characters)
INFO Finished preprocessing for company_id=3
```

### Failed Preprocessing Flow

```
INFO Company preprocessing task enqueued for company_id=4
INFO Starting preprocessing for company_id=4
INFO Extracting website data for company_id=4 (url=https://invalid-url.com)
ERROR Website crawl error: url=https://invalid-url.com, error=Connection timeout
ERROR Website data extraction failed for company_id=4: Website crawl failed: Connection timeout
INFO Transcribing audio for company_id=4 (audio_path=uploads/audio/xyz789.mp3)
ERROR Audio transcription error: audio_path=uploads/audio/xyz789.mp3, error=File not found
ERROR Audio transcription failed for company_id=4: Audio transcription failed: File not found
ERROR Preprocessing failed for company_id=4: Background processing error: <error>
```

### Partial Success Flow

```
INFO Company preprocessing task enqueued for company_id=5
INFO Starting preprocessing for company_id=5
INFO Extracting website data for company_id=5 (url=https://example.com)
INFO Starting website crawl: url=https://example.com, max_pages=20
INFO Website crawl completed: url=https://example.com, pages_crawled=3, text_length=8901
INFO Website data extraction completed for company_id=5 (extracted 8901 characters)
INFO Transcribing audio for company_id=5 (audio_path=uploads/audio/def456.mp3)
ERROR Audio transcription error: audio_path=uploads/audio/def456.mp3, error=Invalid audio format
ERROR Audio transcription failed for company_id=5: Audio transcription failed: Invalid audio format
INFO Finished preprocessing for company_id=5
```

---

## Where Logs Appear

### Development (uvicorn)
Logs appear in the **backend console/terminal** where uvicorn is running:
```bash
cd backend
uvicorn main:app --reload --port 8000
```

### Production
Logs appear in:
- **Standard output** (stdout) if running directly
- **Application logs** if using a process manager (systemd, supervisor, etc.)
- **Container logs** if running in Docker

---

## Log Format

All logs use Python's `logging` module with:
- **Level**: `INFO` for normal operations, `ERROR` for failures, `WARNING` for non-critical issues
- **Format**: Structured messages with `company_id=<id>` for easy filtering
- **No sensitive data**: Passwords, tokens, or raw transcripts are never logged

---

## Security Considerations

✅ **No sensitive data logged**:
- No passwords
- No API keys
- No raw transcripts (only length)
- No full website content (only character count)

✅ **Structured format**:
- Consistent `company_id=<id>` format for easy filtering
- Clear error messages without exposing internals

---

## Verification Checklist

To verify preprocessing is working:

1. **Check task enqueue**:
   ```bash
   # Look for this when creating a company
   grep "Company preprocessing task enqueued" <log_file>
   ```

2. **Check preprocessing start**:
   ```bash
   grep "Starting preprocessing for company_id" <log_file>
   ```

3. **Check individual steps**:
   ```bash
   grep "Extracting website data for company_id" <log_file>
   grep "Transcribing audio for company_id" <log_file>
   ```

4. **Check completion**:
   ```bash
   grep "Finished preprocessing for company_id" <log_file>
   ```

5. **Check failures**:
   ```bash
   grep "Preprocessing failed for company_id" <log_file>
   ```

---

## Troubleshooting

### No "task enqueued" log
- **Issue**: Background task not being scheduled
- **Check**: Company creation endpoint, verify `background_tasks.add_task()` is called

### No "Starting preprocessing" log
- **Issue**: Background task not executing
- **Check**: FastAPI BackgroundTasks configuration, verify task is actually running

### Preprocessing starts but never completes
- **Issue**: Task hanging or crashing silently
- **Check**: Look for error logs, verify database connection in background task

### Status stuck in "processing"
- **Issue**: Task crashed before updating status
- **Check**: Error logs for exceptions, verify exception handling in `process_company_background()`

---

## Code Changes Summary

### `backend/app/routers/companies.py`
- Enhanced `process_company_background()` with structured logging
- Added "Starting preprocessing" log at function entry
- Enhanced step-by-step logging with company_id
- Improved error logging with company_id context
- Changed "Scheduled" to "enqueued" for clarity

### `backend/app/preprocessing.py`
- Added logging at start of `crawl_website()`
- Added completion logging with metrics (pages_crawled, text_length)
- Added logging at start of `transcribe_audio()`
- Added completion logging with transcript_length
- Improved error logging with structured format

---

## No Breaking Changes

✅ Business logic unchanged
✅ Database schema unchanged
✅ API contracts unchanged
✅ Error handling unchanged
✅ Only logging added







