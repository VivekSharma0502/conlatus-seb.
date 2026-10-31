from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class Turn(BaseModel):
    role: str = Field(..., description="'interviewer' or 'candidate'")
    content: str = Field(..., description="Text content of the turn")
    timestamp: str = Field(..., description="ISO timestamp string")


class RubricEvidenceItem(BaseModel):
    criterion: str
    score: float = Field(..., ge=1.0, le=5.0)
    evidence: str = Field(..., description="Direct quote or specific detail observed")
    reasoning: str = Field(..., description="Explanation of why this score was assigned")


class VerdictResult(BaseModel):
    overall_score: float
    verdict: str = Field(..., description="'PASS' or 'FAIL'")
    threshold: float
    criteria_breakdown: Dict[str, dict]


class StartInterviewRequest(BaseModel):
    interview_id: Optional[str] = None
    candidate_id: str = "candidate-1"


class StartInterviewResponse(BaseModel):
    session_id: str
    status: str
    question: str
    current_question_index: int
    role_title: Optional[str] = None
    company_name: Optional[str] = None


class CandidateMessageRequest(BaseModel):
    message: str = Field(..., min_length=1)


class CandidateMessageResponse(BaseModel):
    session_id: str
    status: str  # 'in_progress', 'completed', 'length_limited'
    next_question: Optional[str] = None
    is_followup: bool = False
    verdict: Optional[VerdictResult] = None
    transcript: Optional[str] = None


class SessionStatusResponse(BaseModel):
    session_id: str
    candidate_id: str
    status: str
    role_title: str
    current_question_index: int
    current_question_followup_count: int
    total_turns: int
    conversation_history: List[Turn]
    rubric_evidence: Dict[str, RubricEvidenceItem]
    verdict: Optional[VerdictResult] = None


class InterviewConfig(BaseModel):
    id: str
    role_title: str
    company_name: str
    duration_minutes: int
    job_description: Optional[str] = None
    questions: List[Dict]
    rubric_criteria: Dict[str, dict]
    verdict_threshold: float = 3.0
    max_followups: int = 2
    access_code: Optional[str] = None
    candidate_email: Optional[str] = None


class CreateInterviewRequest(BaseModel):
    role_title: str
    company_name: str
    duration_minutes: int
    job_description: str
    rubric_tags: List[str]
    custom_questions: List[str]
    generated_questions: Optional[List[Dict]] = None
    candidate_email: Optional[str] = None
    candidate_name: Optional[str] = None


class CreateInterviewResponse(BaseModel):
    interview_id: str
    access_code: Optional[str] = None


class InterviewDetailsResponse(BaseModel):
    interview_id: str
    role_title: str
    company_name: str
    duration_minutes: int
    is_valid: bool = True


class JoinInterviewRequest(BaseModel):
    interview_code: str = Field(..., min_length=1)
    candidate_name: str = Field(..., min_length=1)
    candidate_email: str = Field(..., min_length=3)


class JoinInterviewResponse(BaseModel):
    interview_id: str
    access_token: str
    token_type: str = "bearer"
    role_title: str
    company_name: str
    duration_minutes: int
    candidate_name: str
    candidate_email: str
