from enum import Enum


class UserStatus(str, Enum):
    ACTIVE = "active"
    BLOCKED = "blocked"
    DELETED = "deleted"


class SystemRole(str, Enum):
    USER = "user"
    ADMIN = "admin"


class AuthTokenType(str, Enum):
    EMAIL_VERIFICATION = "email_verification"
    PASSWORD_RESET = "password_reset"


def enum_values(enum_class: type[Enum]) -> list[str]:
    return [item.value for item in enum_class]
