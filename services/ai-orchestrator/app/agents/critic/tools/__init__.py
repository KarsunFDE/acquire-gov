"""Critic tool surface (design ref §18.5 + §18.12.2 rename)."""
from app.agents.critic.tools.lm_consistency import verify_l_m_consistency
from app.agents.critic.tools.set_aside import check_set_aside_consistency
from app.agents.critic.tools.clin_coverage import check_clin_coverage

__all__ = [
    "verify_l_m_consistency",
    "check_set_aside_consistency",
    "check_clin_coverage",
]
