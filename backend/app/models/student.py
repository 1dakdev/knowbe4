from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.school import School
from app.models.school_class import SchoolClass


class Student(Base):
    __tablename__ = "students"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    school_id: Mapped[int] = mapped_column(ForeignKey("schools.id"), nullable=False, index=True)
    class_id: Mapped[int] = mapped_column(ForeignKey("school_classes.id"), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    grade_level: Mapped[int] = mapped_column(Integer, nullable=False)
    pin_hash: Mapped[str] = mapped_column(String(255), nullable=False)

    school: Mapped["School"] = relationship()
    school_class: Mapped["SchoolClass"] = relationship()


def grade_tier(grade_level: int) -> str:
    return "early" if grade_level <= 5 else "late"
