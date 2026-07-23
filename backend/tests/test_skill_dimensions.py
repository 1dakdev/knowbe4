from app.models.skill_dimension import SkillDimension
from app.seed.skill_dimensions import SKILL_DIMENSIONS


def test_seed_list_has_eleven_dimensions():
    assert len(SKILL_DIMENSIONS) == 11
    keys = [d["key"] for d in SKILL_DIMENSIONS]
    assert len(keys) == len(set(keys))  # all unique
    assert "math_reasoning" in keys
    assert "reading_fluency" in keys
    assert "emotional_intelligence" in keys


def test_create_skill_dimension(db_session):
    dim = SkillDimension(
        key="math_reasoning",
        name="Mathematical Reasoning",
        rubric_description="0-100 scale: ...",
    )
    db_session.add(dim)
    db_session.flush()
    assert dim.id is not None
