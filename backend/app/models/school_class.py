from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.school import School
from app.models.teacher import Teacher


class SchoolClass(Base):
    __tablename__ = "school_classes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    school_id: Mapped[int] = mapped_column(ForeignKey("schools.id"), nullable=False, index=True)
    teacher_id: Mapped[int] = mapped_column(ForeignKey("teachers.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    grade_level: Mapped[int] = mapped_column(Integer, nullable=False)

    school: Mapped["School"] = relationship()
    teacher: Mapped["Teacher"] = relationship()
