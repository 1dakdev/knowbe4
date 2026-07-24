from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, Session, mapped_column, relationship

from app.database import Base
from app.models.skill_dimension import SkillDimension
from app.models.student import Student


class AssessmentItem(Base):
    __tablename__ = "assessment_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), nullable=False, index=True)
    skill_dimension_id: Mapped[int] = mapped_column(ForeignKey("skill_dimensions.id"), nullable=False)
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    correct_answer: Mapped[str] = mapped_column(String(255), nullable=False)
    student_answer: Mapped[str | None] = mapped_column(String(255), nullable=True)
    score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    feedback: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    answered_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    student: Mapped["Student"] = relationship()
    skill_dimension: Mapped["SkillDimension"] = relationship()


def latest_score_for_student(student_id: int, db: Session) -> int | None:
    item = (
        db.query(AssessmentItem)
        .filter(AssessmentItem.student_id == student_id, AssessmentItem.score.isnot(None))
        .order_by(AssessmentItem.created_at.desc())
        .first()
    )
    return item.score if item else None
