import uuid
from typing import Dict, Optional
try:
    from models.schemas import InterviewConfig
except ImportError:
    from backend.models.schemas import InterviewConfig

class InterviewStore:
    def __init__(self):
        self._interviews: Dict[str, InterviewConfig] = {}
        self._access_codes: Dict[str, str] = {}

    def create_interview(self, config: InterviewConfig) -> str:
        self._interviews[config.id] = config
        if config.access_code:
            self._access_codes[config.access_code.strip().upper()] = config.id
            self._access_codes[config.access_code.strip()] = config.id
        return config.id

    def get_interview(self, interview_id_or_code: str) -> Optional[InterviewConfig]:
        if not interview_id_or_code:
            return None
        # 1. Direct ID lookup
        config = self._interviews.get(interview_id_or_code)
        if config:
            return config
        # 2. Access code lookup
        target_id = self._access_codes.get(interview_id_or_code.strip().upper()) or self._access_codes.get(interview_id_or_code.strip())
        if target_id:
            return self._interviews.get(target_id)
        return None

    def clear(self):
        self._interviews.clear()
        self._access_codes.clear()

# Global in-process store instance
interview_store = InterviewStore()
