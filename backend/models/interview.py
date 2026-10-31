import uuid
from datetime import datetime
from typing import TYPE_CHECKING, List, Optional
from sqlalchemy import Boolean, ForeignKey, String, DateTime, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from models.role import Role
    from models.user import User
    from models.transcript import Transcript
    from models.report import Report


class Interview(Base, UUIDMixin, TimestampMixin):
    """
    Interview entity representing an interview instance, access tokens, and status lifecycle.
    """
    __tablename__ = "interviews"

    role_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("roles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    candidate_name: Mapped[str] = mapped_column(String(255), nullable=False)
    candidate_email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    token: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="created", nullable=False)  # created, in_progress, completed, expired

    # Independent, cryptographically random single-use access code (expires in 30 min if unused)
    access_code: Mapped[Optional[str]] = mapped_column(String(64), unique=True, index=True, nullable=True)
    access_code_expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    access_code_used: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    access_code_used_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    role: Mapped["Role"] = relationship("Role", back_populates="interviews")
    user: Mapped[Optional["User"]] = relationship("User", back_populates="interviews")
    transcripts: Mapped[List["Transcript"]] = relationship(
        "Transcript",
        back_populates="interview",
        cascade="all, delete-orphan",
        order_by="Transcript.timestamp",
        lazy="selectin",
    )
    report: Mapped[Optional["Report"]] = relationship(
        "Report",
        back_populates="interview",
        uselist=False,
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Interview id={self.id} candidate='{self.candidate_name}' status='{self.status}' access_code='{self.access_code}'>"
