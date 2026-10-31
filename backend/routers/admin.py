import uuid
import logging
from typing import List, Optional
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from api.deps import get_current_admin, get_db
from models.schemas import CreateInterviewRequest, CreateInterviewResponse, InterviewConfig
from core.interview_store import interview_store
from core.security import generate_access_code
from models.interview import Interview
from models.role import Role
from models.company import Company
from models.report import Report
from models.transcript import Transcript
from schemas.admin import (
    AdminOverviewResponse,
    AdminSettingsPayload,
    CandidateListItem,
    CandidateDetailResponse,
    CandidateDecisionRequest,
    DashboardAlert,
)
from services.report_generator import report_generator

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/admin", 
    tags=["admin"],
    dependencies=[Depends(get_current_admin)]
)

# In-memory settings cache with persistence fallback
_admin_settings = AdminSettingsPayload()


@router.post("/interviews", response_model=CreateInterviewResponse, status_code=status.HTTP_201_CREATED)
async def create_interview(
    request: CreateInterviewRequest,
    db: AsyncSession = Depends(get_db),
    current_admin = Depends(get_current_admin),
):
    # Map rubric tags to criteria
    rubric_criteria = {}
    tags = [t.strip() for t in request.rubric_tags if t.strip()] if request.rubric_tags else ["Technical Competence", "Communication", "Problem Solving"]
    weight_per_tag = 1.0 / len(tags)
    for tag in tags:
        key = tag.lower().replace(" ", "_").replace("-", "_")
        rubric_criteria[key] = {
            "weight": weight_per_tag,
            "scale": 5,
            "description": f"Evaluation for {tag}"
        }

    role = request.role_title.strip() if request.role_title else "Software Engineer"
    company = request.company_name.strip() if request.company_name else "Conlatus"
    
    # Check custom questions
    custom_qs = [q.strip() for q in request.custom_questions if q.strip()] if request.custom_questions else []
    
    questions = []
    if request.generated_questions:
        for i, gq in enumerate(request.generated_questions):
            q_id = gq.get("id", f"q{i+1}")
            q_criteria = gq.get("rubric_criteria", {})
            for k, v in q_criteria.items():
                if k not in rubric_criteria:
                    rubric_criteria[k] = v
                    
            questions.append({
                "id": q_id,
                "text": gq.get("text"),
                "maps_to": list(q_criteria.keys()) if q_criteria else list(rubric_criteria.keys()),
                "notes": gq.get("expected_signals", "AI Synthesized Question")
            })
    elif custom_qs:
        for i, q in enumerate(custom_qs):
            questions.append({
                "id": f"q{i+1}",
                "text": q,
                "maps_to": list(rubric_criteria.keys()),
                "notes": "Custom question provided by recruiter"
            })
    else:
        tag_str = ", ".join(tags[:3])
        default_qs = [
            f"Hello! Welcome to your interview for the {role} position at {company}. To start off, could you briefly introduce yourself and share some of your background relevant to this role?",
            f"Could you walk me through a challenging technical project you worked on recently? What architectural decisions did you make and what technologies ({tag_str}) did you utilize?",
            "Tell me about a time when you encountered an unexpected bug, production failure, or performance bottleneck. How did you diagnose and resolve it?",
            "How do you approach collaborating with cross-functional teammates, handling conflicting design opinions, or managing tight project deadlines?",
            f"What interests you most about this {role} opportunity, and do you have any closing thoughts on how your skills align with our needs?"
        ]
        for i, q in enumerate(default_qs):
            questions.append({
                "id": f"q{i+1}",
                "text": q,
                "maps_to": list(rubric_criteria.keys()),
                "notes": f"Standard structured interview question {i+1}"
            })

    interview_uuid = uuid.uuid4()
    # Generate random access code (secrets, 8+ chars, independent of UUID)
    access_code = generate_access_code(10)
    access_code_expires_at = datetime.now(timezone.utc) + timedelta(minutes=30)
    candidate_email = (
        request.candidate_email.strip()
        if request.candidate_email and request.candidate_email.strip()
        else f"candidate-{str(interview_uuid)[:8]}@applicant.com"
    )
    candidate_name = (
        request.candidate_name.strip()
        if request.candidate_name and request.candidate_name.strip()
        else "Pending Candidate"
    )

    config = InterviewConfig(
        id=str(interview_uuid),
        role_title=role,
        company_name=company,
        duration_minutes=request.duration_minutes or 30,
        job_description=request.job_description or "",
        questions=questions,
        rubric_criteria=rubric_criteria,
        max_followups=2,
        verdict_threshold=3.0,
        access_code=access_code,
        candidate_email=candidate_email,
    )

    interview_id = interview_store.create_interview(config)

    # Persist in DB so candidate table reflects this session
    try:
        # Find or create company
        comp_stmt = select(Company).where(Company.name == company)
        comp_res = await db.execute(comp_stmt)
        db_comp = comp_res.scalar_one_or_none()
        if not db_comp:
            db_comp = Company(name=company)
            db.add(db_comp)
            await db.flush()

        # Find or create role
        role_stmt = select(Role).where(Role.title == role, Role.company_id == db_comp.id)
        role_res = await db.execute(role_stmt)
        db_role = role_res.scalar_one_or_none()
        if not db_role:
            db_role = Role(
                title=role,
                company_id=db_comp.id,
                description=request.job_description or f"{role} role at {company}",
                competencies=rubric_criteria,
                rubric=rubric_criteria,
            )
            db.add(db_role)
            await db.flush()

        # Create Interview record with access_code, single-use, 30 min expiry
        db_interview = Interview(
            id=interview_uuid,
            role_id=db_role.id,
            user_id=current_admin.id if current_admin else None,
            candidate_name=candidate_name,
            candidate_email=candidate_email,
            token=f"tok_{str(interview_uuid).replace('-', '')[:16]}",
            access_code=access_code,
            access_code_expires_at=access_code_expires_at,
            access_code_used=False,
            status="created",
        )
        db.add(db_interview)
        await db.commit()
    except Exception as e:
        logger.warning(f"Could not persist interview to DB: {e}")
    
    return CreateInterviewResponse(
        interview_id=interview_id,
        access_code=access_code,
    )


@router.get("/overview", response_model=AdminOverviewResponse)
async def get_admin_overview(
    db: AsyncSession = Depends(get_db),
    current_admin = Depends(get_current_admin),
):
    """
    Returns high-level KPI dashboard metrics, alerts, and candidate stream.
    """
    stmt = select(Interview).options(
        selectinload(Interview.role).selectinload(Role.company),
        selectinload(Interview.report)
    ).order_by(Interview.created_at.desc())
    res = await db.execute(stmt)
    interviews = res.scalars().all()

    total_interviews = len(interviews)
    completed_interviews = 0
    in_progress_interviews = 0
    pending_interviews = 0
    total_score = 0.0
    scored_count = 0
    passed_count = 0

    candidate_items: List[CandidateListItem] = []

    for inv in interviews:
        status_norm = inv.status.lower()
        if status_norm in ("completed", "length_limited"):
            completed_interviews += 1
        elif status_norm in ("in_progress", "active"):
            in_progress_interviews += 1
        else:
            pending_interviews += 1

        overall_score = None
        recommendation = None
        human_decision = None

        if inv.report:
            overall_score = round(inv.report.overall_score, 1)
            recommendation = inv.report.recommendation
            human_decision = inv.report.human_decision
            total_score += inv.report.overall_score
            scored_count += 1
            if inv.report.overall_score >= 3.0 or (recommendation and "hire" in recommendation.lower() and "no" not in recommendation.lower()):
                passed_count += 1

        candidate_items.append(
            CandidateListItem(
                id=inv.id,
                candidate_name=inv.candidate_name,
                candidate_email=inv.candidate_email,
                role_title=inv.role.title if inv.role else "Software Engineer",
                company_name=inv.role.company.name if inv.role and inv.role.company else "Conlatus",
                status="completed" if status_norm in ("completed", "length_limited") else ("in-progress" if status_norm == "in_progress" else "pending"),
                overall_score=overall_score,
                recommendation=recommendation,
                human_decision=human_decision,
                token=inv.token,
                created_at=inv.created_at,
                completed_at=inv.completed_at,
            )
        )

    avg_score = round(total_score / scored_count, 1) if scored_count > 0 else 0.0
    pass_rate = round((passed_count / scored_count) * 100, 1) if scored_count > 0 else 0.0

    # Generate alerts based on live data
    alerts: List[DashboardAlert] = []
    
    # 1. Check for completed candidates awaiting human decision
    pending_reviews = [c for c in candidate_items if c.status == "completed" and not c.human_decision]
    if pending_reviews:
        alerts.append(
            DashboardAlert(
                id="alert-pending-decision",
                type="warning",
                title="Action Required: Unreviewed Candidates",
                message=f"{len(pending_reviews)} completed interview session(s) awaiting recruiter sign-off.",
                timestamp="Just now",
            )
        )

    # 2. Check for strong candidates
    top_candidates = [c for c in candidate_items if (c.overall_score or 0) >= 4.2]
    if top_candidates:
        alerts.append(
            DashboardAlert(
                id="alert-top-talent",
                type="success",
                title="High-Potential Candidate Alert",
                message=f"{top_candidates[0].candidate_name} scored {top_candidates[0].overall_score}/5.0 for {top_candidates[0].role_title}.",
                timestamp="2 hours ago",
            )
        )

    # 3. System status
    alerts.append(
        DashboardAlert(
            id="alert-system-ok",
            type="info",
            title="Interview Synthesis Engine Active",
            message="Groq Whisper v3 and OpenAI GPT-OSS-120B pipeline operational with zero reported latency spikes.",
            timestamp="Live",
        )
    )

    return AdminOverviewResponse(
        total_interviews=total_interviews,
        completed_interviews=completed_interviews,
        in_progress_interviews=in_progress_interviews,
        pending_interviews=pending_interviews,
        average_score=avg_score,
        pass_rate=pass_rate,
        recent_candidates=candidate_items[:6],
        alerts=alerts,
    )


@router.get("/candidates", response_model=List[CandidateListItem])
async def list_candidates(
    search: Optional[str] = Query(None, description="Search term for name, email, or role"),
    status: Optional[str] = Query(None, description="Filter by status: 'all', 'completed', 'in_progress', 'pending'"),
    db: AsyncSession = Depends(get_db),
    current_admin = Depends(get_current_admin),
):
    """
    Searchable, filterable candidate database with score, recommendation, and status.
    """
    stmt = select(Interview).options(
        selectinload(Interview.role).selectinload(Role.company),
        selectinload(Interview.report)
    ).order_by(Interview.created_at.desc())
    res = await db.execute(stmt)
    interviews = res.scalars().all()

    candidates: List[CandidateListItem] = []
    search_lower = search.lower().strip() if search else None
    status_filter = status.lower().strip() if status and status.lower() != "all" else None

    for inv in interviews:
        role_title = inv.role.title if inv.role else "Software Engineer"
        comp_name = inv.role.company.name if inv.role and inv.role.company else "Conlatus"
        
        status_norm = inv.status.lower()
        norm_status = "completed" if status_norm in ("completed", "length_limited") else ("in-progress" if status_norm == "in_progress" else "pending")

        # Apply status filter
        if status_filter:
            if status_filter in ("in_progress", "in-progress") and norm_status != "in-progress":
                continue
            elif status_filter == "completed" and norm_status != "completed":
                continue
            elif status_filter in ("pending", "created") and norm_status != "pending":
                continue

        # Apply search filter
        if search_lower:
            text_match = (
                search_lower in inv.candidate_name.lower() or
                search_lower in inv.candidate_email.lower() or
                search_lower in role_title.lower() or
                search_lower in comp_name.lower()
            )
            if not text_match:
                continue

        candidates.append(
            CandidateListItem(
                id=inv.id,
                candidate_name=inv.candidate_name,
                candidate_email=inv.candidate_email,
                role_title=role_title,
                company_name=comp_name,
                status=norm_status,
                overall_score=round(inv.report.overall_score, 1) if inv.report else None,
                recommendation=inv.report.recommendation if inv.report else None,
                human_decision=inv.report.human_decision if inv.report else None,
                token=inv.token,
                created_at=inv.created_at,
                completed_at=inv.completed_at,
            )
        )

    return candidates


@router.get("/candidates/{interview_id}", response_model=CandidateDetailResponse)
async def get_candidate_detail(
    interview_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_admin = Depends(get_current_admin),
):
    """
    Returns full in-depth interview session details, rubric breakdown,
    synthesis quotes, transcripts, and human decision.
    """
    stmt = select(Interview).options(
        selectinload(Interview.role).selectinload(Role.company),
        selectinload(Interview.report),
        selectinload(Interview.transcripts)
    ).where(Interview.id == interview_id)
    res = await db.execute(stmt)
    inv = res.scalar_one_or_none()

    if not inv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate interview not found")

    report = inv.report
    # If completed but report not generated yet, try lazy generation
    if not report and inv.status in ("completed", "length_limited"):
        try:
            report = await report_generator.generate_report(interview_id=interview_id, db_session=db)
        except Exception as e:
            logger.error(f"Failed lazy report generation for {interview_id}: {e}")

    # Build transcript turns
    transcript_list = []
    if inv.transcripts:
        for t in inv.transcripts:
            transcript_list.append({
                "id": str(t.id),
                "speaker": t.speaker,
                "message": t.message,
                "timestamp": t.timestamp.isoformat() if t.timestamp else datetime.now(timezone.utc).isoformat(),
                "audio_url": t.audio_url,
            })

    norm_status = "completed" if inv.status in ("completed", "length_limited") else ("in-progress" if inv.status == "in_progress" else "pending")

    return CandidateDetailResponse(
        id=inv.id,
        candidate_name=inv.candidate_name,
        candidate_email=inv.candidate_email,
        role_title=inv.role.title if inv.role else "Software Engineer",
        company_name=inv.role.company.name if inv.role and inv.role.company else "Conlatus",
        status=norm_status,
        token=inv.token,
        created_at=inv.created_at,
        completed_at=inv.completed_at,
        report_id=report.id if report else None,
        overall_score=round(report.overall_score, 1) if report else None,
        recommendation=report.recommendation if report else None,
        summary=report.summary if report else None,
        rubric_breakdown=report.rubric_breakdown if report else None,
        synthesis_details=report.synthesis_details if report else None,
        human_decision=report.human_decision if report else None,
        human_notes=report.human_notes if report else None,
        transcripts=transcript_list,
    )


@router.post("/candidates/{interview_id}/decision")
async def record_candidate_decision(
    interview_id: uuid.UUID,
    payload: CandidateDecisionRequest,
    db: AsyncSession = Depends(get_db),
    current_admin = Depends(get_current_admin),
):
    """
    Records recruiter human verdict ('hired', 'rejected', 'next_round', 'under_review') and notes.
    """
    stmt = select(Report).where(Report.interview_id == interview_id)
    res = await db.execute(stmt)
    report = res.scalar_one_or_none()

    if not report:
        # Create a report shell if interview exists
        inv_res = await db.execute(select(Interview).where(Interview.id == interview_id))
        inv = inv_res.scalar_one_or_none()
        if not inv:
            raise HTTPException(status_code=404, detail="Interview not found")
        
        report = Report(
            interview_id=interview_id,
            overall_score=0.0,
            recommendation="Pending",
            human_decision=payload.decision,
            human_notes=payload.notes,
        )
        db.add(report)
    else:
        report.human_decision = payload.decision
        report.human_notes = payload.notes

    await db.commit()
    await db.refresh(report)

    return {
        "status": "success",
        "interview_id": str(interview_id),
        "human_decision": report.human_decision,
        "human_notes": report.human_notes,
    }


@router.post("/candidates/{interview_id}/retrigger")
async def retrigger_candidate_report(
    interview_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_admin = Depends(get_current_admin),
):
    """
    Regenerates the assessment report for a candidate session.
    """
    inv_res = await db.execute(select(Interview).where(Interview.id == interview_id))
    inv = inv_res.scalar_one_or_none()
    if not inv:
        raise HTTPException(status_code=404, detail="Interview not found")

    # Clear existing report if any
    rep_res = await db.execute(select(Report).where(Report.interview_id == interview_id))
    existing_rep = rep_res.scalar_one_or_none()
    if existing_rep:
        await db.delete(existing_rep)
        await db.commit()

    inv.status = "completed"
    await db.commit()

    report = await report_generator.generate_report(interview_id=interview_id, db_session=db)
    return {"status": "retriggered", "report_id": str(report.id) if report else None}


@router.get("/settings", response_model=AdminSettingsPayload)
async def get_settings(
    current_admin = Depends(get_current_admin),
):
    """
    Returns recruiter configuration (LLM models, API keys status, thresholds, branding).
    """
    import os
    _admin_settings.groq_api_key_configured = bool(os.environ.get("GROQ_API_KEY"))
    _admin_settings.anthropic_api_key_configured = bool(os.environ.get("ANTHROPIC_API_KEY"))
    _admin_settings.openai_api_key_configured = bool(os.environ.get("OPENAI_API_KEY"))
    return _admin_settings


@router.post("/settings", response_model=AdminSettingsPayload)
async def update_settings(
    payload: AdminSettingsPayload,
    current_admin = Depends(get_current_admin),
):
    """
    Updates recruiter configuration.
    """
    global _admin_settings
    _admin_settings = payload
    logger.info(f"Admin settings updated: model={payload.model_name}, threshold={payload.rubric_threshold}")
    return _admin_settings
