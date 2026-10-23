from CTFd.constants.options import (
    AccountVisibilityTypes,
    ChallengeVisibilityTypes,
    RegistrationVisibilityTypes,
    ScoreVisibilityTypes,
    UserModeTypes,
)
from CTFd.constants.themes import DEFAULT_THEME

DEFAULTS = {
    # General Settings
    "ctf_name": "CTFd",
    "user_mode": UserModeTypes.USERS,
    # Visual/Style Settings
    "ctf_theme": DEFAULT_THEME,
    # Visibility Settings
    "challenge_visibility": ChallengeVisibilityTypes.PRIVATE,
    "registration_visibility": RegistrationVisibilityTypes.PUBLIC,
    "score_visibility": ScoreVisibilityTypes.PUBLIC,
    "account_visibility": AccountVisibilityTypes.PUBLIC,
    # Hint penalization
    # at_solve: hint costs are deducted from the challenge points when it is solved
    # at_unlock: hint costs are deducted from the account score when it is unlocked
    "hint_penalty_mode": "at_solve",
}
