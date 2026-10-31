import logging
import os
import sys
import uuid
from datetime import datetime, timezone
from typing import Dict, Optional
from fastapi import APIRouter, File, HTTPException, UploadFile, status, Depends, Request, Response, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

# Ensure backend root is always on sys.path for absolute imports
_backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)

logger = logging.getLogger(__name__)

try:
    from routers.auth import limiter
    from api.deps import verify_interview_token, get_db
    from core.security import create_interview_token
    from core.llm import llm_evaluator
    from services.rubric_scoring import calculate_verdict
    from core.session import session_store
    from core.stt import stt_transcriber
    from core.interview_store import interview_store
    from models.interview import Interview
    from models.role import Role
    from models.company import Company
    from models.schemas import (
        CandidateMessageRequest,
        CandidateMessageResponse,
        RubricEvidenceItem,
        SessionStatusResponse,
        StartInterviewRequest,
        StartInterviewResponse,
        VerdictResult,
        InterviewConfig,
        InterviewDetailsResponse,
        JoinInterviewRequest,
        JoinInterviewResponse,
    )
    import rubric_config
except ImportError:
    from backend.routers.auth import limiter
    from backend.api.deps import verify_interview_token, get_db
    from backend.core.security import create_interview_token
    from backend.core.llm import llm_evaluator
    from backend.services.rubric_scoring import calculate_verdict
    from backend.core.session import session_store
    from backend.core.stt import stt_transcriber
    from backend.core.interview_store import interview_store
    from backend.models.interview import Interview
    from backend.models.role import Role
    from backend.models.company import Company
    from backend.models.schemas import (
        CandidateMessageRequest,
        CandidateMessageResponse,
        RubricEvidenceItem,
        SessionStatusResponse,
        StartInterviewRequest,
        StartInterviewResponse,
        VerdictResult,
        InterviewConfig,
        InterviewDetailsResponse,
        JoinInterviewRequest,
        JoinInterviewResponse,
    )
    import backend.rubric_config as rubric_config

router = APIRouter(prefix="/interview", tags=["interview"])


async def _resolve_interview_metadata(code: str, db: AsyncSession) -> Optional[dict]:
    """Helper to find interview config in memory store or database by UUID, access_code, or token."""
    clean_code = code.strip()

    # 1. Check in-memory store
    config = interview_store.get_interview(clean_code)
    if config:
        return {
            "id": config.id,
            "role_title": config.role_title,
            "company_name": config.company_name,
            "duration_minutes": config.duration_minutes,
            "config": config,
        }

    # 2. Check DEMO code
    if clean_code.lower() in ("demo", "demo-interview"):
        demo_id = "demo-session"
        demo_config = InterviewConfig(
            id=demo_id,
            role_title="Junior Web Developer — Fundamentals",
            company_name="Conlatus AI",
            duration_minutes=15,
            job_description="Introductory technical assessment on basic web and programming fundamentals (HTML, CSS, variables, languages).",
            questions=[{"id": q["id"], "text": q["text"], "maps_to": list(rubric_config.RUBRIC_CRITERIA.keys())} for q in rubric_config.QUESTIONS],
            rubric_criteria=rubric_config.RUBRIC_CRITERIA,
        )
        interview_store.create_interview(demo_config)
        return {
            "id": demo_id,
            "role_title": demo_config.role_title,
            "company_name": demo_config.company_name,
            "duration_minutes": demo_config.duration_minutes,
            "config": demo_config,
        }

    # 3. Check database (supports UUID, access_code, or token)
    try:
        query = select(Interview).options(selectinload(Interview.role).selectinload(Role.company))
        try:
            target_uuid = uuid.UUID(clean_code)
            stmt = query.where(Interview.id == target_uuid)
        except ValueError:
            stmt = query.where(
                (Interview.access_code == clean_code.upper())
                | (Interview.access_code == clean_code)
                | (Interview.token == clean_code)
            )

        res = await db.execute(stmt)
        interview_record = res.scalar_one_or_none()

        if interview_record:
            role_title = interview_record.role.title if interview_record.role else "Software Engineer"
            company_name = interview_record.role.company.name if (interview_record.role and interview_record.role.company) else "Conlatus Partner"
            
            # If not in memory store, rebuild config
            record_id = str(interview_record.id)
            cached_config = interview_store.get_interview(record_id)
            if not cached_config:
                rubric = interview_record.role.rubric if (interview_record.role and interview_record.role.rubric) else rubric_config.RUBRIC_CRITERIA
                cached_config = InterviewConfig(
                    id=record_id,
                    role_title=role_title,
                    company_name=company_name,
                    duration_minutes=30,
                    job_description=interview_record.role.description if interview_record.role else "",
                    questions=[{"id": f"q{i+1}", "text": q["text"], "maps_to": list(rubric.keys())} for i, q in enumerate(rubric_config.QUESTIONS)],
                    rubric_criteria=rubric,
                    access_code=interview_record.access_code,
                    candidate_email=interview_record.candidate_email,
                )
                interview_store.create_interview(cached_config)

            return {
                "id": record_id,
                "role_title": role_title,
                "company_name": company_name,
                "duration_minutes": cached_config.duration_minutes if cached_config else 30,
                "config": cached_config,
                "db_record": interview_record,
            }
    except Exception as e:
        logger.warning(f"Error querying interview from DB for code '{clean_code}': {e}")

    return None


@router.get("/details/{code}", response_model=InterviewDetailsResponse)
async def get_interview_details(code: str, db: AsyncSession = Depends(get_db)):
    """Retrieves public metadata for candidate onboarding before interview starts."""
    meta = await _resolve_interview_metadata(code, db)
    if not meta:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Interview access code is invalid or expired. Please check your invitation.",
        )

    return InterviewDetailsResponse(
        interview_id=meta["id"],
        role_title=meta["role_title"],
        company_name=meta["company_name"],
        duration_minutes=meta["duration_minutes"],
        is_valid=True,
    )


@router.post("/join", response_model=JoinInterviewResponse)
async def join_interview(
    req_data: JoinInterviewRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """
    Verifies candidate credentials, validates single-use access code and expiration,
    records usage in DB, and issues candidate session token with 'seb': true and client IP.
    """
    meta = await _resolve_interview_metadata(req_data.interview_code, db)
    if not meta:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invalid interview code. Please verify the code or link provided by your recruiter.",
        )

    db_record: Optional[Interview] = meta.get("db_record")
    now_utc = datetime.now(timezone.utc)

    # Validate single-use, expiration, and candidate email if DB record is present
    if db_record:
        # Check single-use
        if db_record.access_code_used or db_record.status in ("completed", "length_limited"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This access code has already been used. Each interview link or code is single-use.",
            )

        # Check expiration (30 min after issue if unused)
        if db_record.access_code_expires_at:
            expires_at = db_record.access_code_expires_at
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            if now_utc > expires_at:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="This access code has expired. Access codes expire 30 minutes after issue if unused.",
                )

        # Check candidate email tie
        if db_record.candidate_email and not db_record.candidate_email.endswith("@applicant.com"):
            if db_record.candidate_email.strip().lower() != req_data.candidate_email.strip().lower():
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"This access code was issued specifically for a different candidate email ({db_record.candidate_email}).",
                )

    interview_id = meta["id"]
    duration_minutes = meta.get("duration_minutes", 30)

    # Extract client IP
    client_ip = request.headers.get("x-forwarded-for")
    if client_ip:
        client_ip = client_ip.split(",")[0].strip()
    elif request.client:
        client_ip = request.client.host
    else:
        client_ip = "127.0.0.1"

    # Generate token with "seb": true, request IP, and duration + buffer
    token = create_interview_token(
        interview_id=interview_id,
        candidate_email=req_data.candidate_email.strip(),
        duration_minutes=duration_minutes,
        buffer_minutes=15,
        client_ip=client_ip,
        seb=True,
    )

    # If linked to a DB record, update candidate details and mark access_code used
    if db_record:
        try:
            db_record.access_code_used = True
            db_record.access_code_used_at = now_utc
            db_record.started_at = now_utc
            db_record.candidate_name = req_data.candidate_name.strip()
            db_record.candidate_email = req_data.candidate_email.strip()
            if db_record.status == "created":
                db_record.status = "in_progress"
            await db.commit()
        except Exception as e:
            logger.warning(f"Failed to update candidate DB info on join: {e}")

    # Set candidate auth cookie for seamless browser calls with httponly=True
    cookie_max_age = (duration_minutes + 15) * 60
    response.set_cookie(
        key="candidate_token",
        value=token,
        httponly=True,
        samesite="lax",
        max_age=cookie_max_age,
        path="/",
    )

    return JoinInterviewResponse(
        interview_id=interview_id,
        access_token=token,
        token_type="bearer",
        role_title=meta["role_title"],
        company_name=meta["company_name"],
        duration_minutes=duration_minutes,
        candidate_name=req_data.candidate_name,
        candidate_email=req_data.candidate_email,
    )


@router.post("/start", response_model=StartInterviewResponse)
@limiter.limit("5/minute")
def start_interview(
    request: Request,
    req_data: StartInterviewRequest,
    token_payload: dict = Depends(verify_interview_token),
):
    """Starts a new interview session."""
    target_interview_id = req_data.interview_id or token_payload.get("sub")
    candidate_id = req_data.candidate_id
    if candidate_id == "candidate-1" and token_payload.get("email"):
        candidate_id = token_payload.get("email")

    config = None
    if target_interview_id:
        config = interview_store.get_interview(target_interview_id)
        if not config:
            # Fall back to default rubric config if not explicitly found
            logger.info(f"Custom interview {target_interview_id} not in memory, using default rubric config.")

    session = session_store.create_session(candidate_id=candidate_id, config=config)

    if config and config.questions:
        first_question = config.questions[0]["text"]
        role_title = config.role_title
        company_name = config.company_name
    else:
        first_question = rubric_config.QUESTIONS[0]["text"]
        role_title = rubric_config.ROLE_TITLE
        company_name = None

    session.add_turn(role="interviewer", content=first_question)

    return StartInterviewResponse(
        session_id=session.session_id,
        status=session.status,
        question=first_question,
        current_question_index=session.current_question_index,
        role_title=role_title,
        company_name=company_name,
    )


def _process_candidate_turn(
    session_id: str, candidate_text: str, transcript: Optional[str] = None
) -> CandidateMessageResponse:
    """Core interview turn handler shared by typed text and transcribed audio messages."""
    session = session_store.get_session(session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Interview session '{session_id}' not found.",
        )

    if session.status in ("completed", "length_limited"):
        return CandidateMessageResponse(
            session_id=session.session_id,
            status=session.status,
            next_question=None,
            is_followup=False,
            verdict=session.verdict,
            transcript=transcript or candidate_text,
        )

    # 1. Record candidate response turn
    session.add_turn(role="candidate", content=candidate_text)

    # 2. Delegate to dialogue manager
    try:
        from services.dialogue_manager import dialogue_manager
    except ImportError:
        from backend.services.dialogue_manager import dialogue_manager

    try:
        is_followup, next_question_text = dialogue_manager.process_turn(session_id, candidate_text)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process dialogue turn: {str(e)}"
        )

    verdict_res = None
    if session.status in ("completed", "length_limited"):
        active_rubric_criteria = session.interview_config.rubric_criteria if session.interview_config else rubric_config.RUBRIC_CRITERIA
        active_verdict_threshold = session.interview_config.verdict_threshold if session.interview_config else rubric_config.VERDICT_THRESHOLD
        verdict_dict = calculate_verdict(
            rubric_evidence=session.rubric_evidence,
            rubric_criteria=active_rubric_criteria,
            verdict_threshold=active_verdict_threshold,
        )
        verdict_res = VerdictResult(**verdict_dict)
        session.verdict = verdict_res
        next_question_text = None

    return CandidateMessageResponse(
        session_id=session.session_id,
        status=session.status,
        next_question=next_question_text,
        is_followup=is_followup,
        verdict=verdict_res,
        transcript=transcript,
    )


@router.post("/{session_id}/message", response_model=CandidateMessageResponse)
@limiter.limit("20/minute")
def submit_candidate_message(request: Request, session_id: str, req_data: CandidateMessageRequest, bg_tasks: BackgroundTasks, token_payload: dict = Depends(verify_interview_token)):
    """Processes candidate typed text response through interview loop."""
    response = _process_candidate_turn(session_id, candidate_text=req_data.message)
    if response.status in ("completed", "length_limited"):
        try:
            try:
                from services.report_generator import report_generator
            except ImportError:
                from backend.services.report_generator import report_generator
            interview_uuid = uuid.UUID(session_id)
            bg_tasks.add_task(report_generator.generate_report_background, interview_uuid)
        except (ValueError, TypeError, AttributeError):
            logger.debug(f"Session {session_id} is not a valid UUID; skipping background report generation.")
    return response


@router.post("/{session_id}/audio-message", response_model=CandidateMessageResponse)
@limiter.limit("20/minute")
async def submit_candidate_audio_message(request: Request, session_id: str, bg_tasks: BackgroundTasks, file: UploadFile = File(...), token_payload: dict = Depends(verify_interview_token)):
    """Transcribes audio message via Groq Whisper v3 and feeds transcript through interview loop."""
    session = session_store.get_session(session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Interview session '{session_id}' not found.",
        )
    
    if session.status in ("completed", "length_limited"):
        return CandidateMessageResponse(
            session_id=session.session_id,
            status=session.status,
            next_question=None,
            is_followup=False,
            verdict=session.verdict,
            transcript="(Interview is already completed)",
        )

    audio_bytes = await file.read()
    if not audio_bytes or len(audio_bytes) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Empty audio payload or audio recording was too short. Please speak clearly into the mic and try again.",
        )
    
    filename = file.filename or "audio.webm"
    try:
        transcript = stt_transcriber.transcribe_audio(audio_bytes, filename=filename)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Audio transcription error: {str(e)}. Please try speaking again.",
        )

    if not transcript or not transcript.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not detect clear speech in the recording. Please speak clearly and try again.",
        )

    response = _process_candidate_turn(
        session_id, candidate_text=transcript.strip(), transcript=transcript.strip()
    )
    if response.status in ("completed", "length_limited"):
        try:
            try:
                from services.report_generator import report_generator
            except ImportError:
                from backend.services.report_generator import report_generator
            interview_uuid = uuid.UUID(session_id)
            bg_tasks.add_task(report_generator.generate_report_background, interview_uuid)
        except (ValueError, TypeError, AttributeError):
            logger.debug(f"Session {session_id} is not a valid UUID; skipping background report generation.")
    return response


@router.get("/{session_id}/status", response_model=SessionStatusResponse)
def get_session_status(session_id: str, token_payload: dict = Depends(verify_interview_token)):
    """Returns current status and evidence of an interview session."""
    session = session_store.get_session(session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Interview session '{session_id}' not found.",
        )

    return SessionStatusResponse(
        session_id=session.session_id,
        candidate_id=session.candidate_id,
        status=session.status,
        role_title=session.role_title,
        current_question_index=session.current_question_index,
        current_question_followup_count=session.current_question_followup_count,
        total_turns=session.total_turns,
        conversation_history=session.conversation_history,
        rubric_evidence=session.rubric_evidence,
        verdict=session.verdict,
    )
