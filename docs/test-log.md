# SEB & Interview Pipeline Verification Log

**Date:** 2026-11-01  
**Environment:** Windows 11, FastAPI (Python 3.13), Next.js 16 (Turbopack), Safe Exam Browser 3.10.2  

---

## 1. Chrome / Standard Browser Verification (403 Forbidden)

### Objective
Ensure that standard browsers (such as Google Chrome, Edge, Safari) cannot directly access protected interview endpoints when Safe Exam Browser enforcement is active (`DEV_SKIP_SEB=false`).

### Test Execution
```bash
# 1. Protected endpoint without SEB headers
curl -s -i -X POST http://localhost:8000/interview/start \
  -H "Origin: http://localhost:3000" \
  -H "Content-Type: application/json" \
  -d "{\"interview_id\": \"demo\", \"candidate_id\": \"candidate-test\"}"
```

### Result
- **HTTP Status:** `403 Forbidden`
- **Response Body:** `{"detail":"Safe Exam Browser required"}`
- **CORS Headers:** `access-control-allow-origin: http://localhost:3000` present on response
- **Server Log:** `WARNING: [seb] SEB check failed url=http://localhost:8000/interview/start header_present=False`
- **Status:** **PASS**

---

## 2. Public Endpoints Verification (200 OK)

### Objective
Ensure public assets required for SEB onboarding (launch page, configuration file download, pre-flight code validation) remain accessible without SEB headers.

### Test Execution
```bash
# Pre-flight interview details check
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8000/interview/details/demo

# SEB Configuration download (GET and HEAD)
curl -s -o /dev/null -w "%{http_code}\n" -X GET http://localhost:8000/seb/config.seb
curl -s -o /dev/null -w "%{http_code}\n" -X HEAD http://localhost:8000/seb/config.seb
```

### Result
- `GET /interview/details/demo` -> `200 OK`
- `GET /seb/config.seb` -> `200 OK` (Content-Type: `application/octet-stream`)
- `HEAD /seb/config.seb` -> `200 OK`
- **Status:** **PASS**

---

## 3. Safe Exam Browser Verification (SEB Pass)

### Objective
Verify that requests sent from within Safe Exam Browser (carrying `x-safeexambrowser-configkeyhash`) pass the SEB security check via dual candidate URL matching (`request_url` and `referer`).

### Test Execution (Candidate Referer Matching)
```bash
# Simulating SEB fetch call originating from http://localhost:3000/interview/demo
# Hash = SHA256("http://localhost:3000/interview/demo" + SEB_CONFIG_KEY)
curl -s -i -X POST http://localhost:8000/interview/join \
  -H "Origin: http://localhost:3000" \
  -H "Referer: http://localhost:3000/interview/demo#instructions" \
  -H "x-safeexambrowser-configkeyhash: <valid_hash_matching_referer>" \
  -H "Content-Type: application/json" \
  -d "{\"interview_code\":\"demo\",\"candidate_name\":\"Candidate Test\",\"candidate_email\":\"cand@test.com\"}"
```

### Result
- **HTTP Status:** `200 OK` (Returns session access token)
- **Server Log:** `INFO: [seb] SEB check PASSED matched=referer`
- **Status:** **PASS**

---

## 4. End-to-End Interview Audio Loop Inside SEB

### Objective
Verify that an active interview session inside SEB can record microphone audio, submit audio payloads to `POST /interview/{session_id}/audio-message`, transcribe via Whisper, and progress through multi-turn questions.

### Test Sequence
1. Candidate launches `conlatus.seb` file in Windows.
2. Safe Exam Browser opens into fullscreen locked-down kiosk mode at `http://localhost:3000/interview/demo`.
3. Candidate enters name and email, then clicks **Join Interview Room**.
4. Browser requests microphone permissions; candidate completes audio input check.
5. Interviewer voice speaks initial question via TTS; waveform activates.
6. Candidate answers via microphone; `MediaRecorder` captures audio with `referrerPolicy: "unsafe-url"`.
7. Client submits `FormData` audio message to `POST /interview/{session_id}/audio-message`.
8. Backend receives audio payload:
   - SEB check succeeds (`matched=referer`).
   - Groq Whisper Large v3 successfully transcribes speech to text.
   - Dialogue engine scores turn and generates relevant contextual follow-up question.
9. Interview completes smoothly and final verdict is saved.

### Result
- **Audio Message Status:** `200 OK`
- **Transcript Generated:** Accurate text captured from candidate voice
- **SEB Bypass:** No bypass detected; strict kiosk lock maintained
- **Status:** **PASS**
