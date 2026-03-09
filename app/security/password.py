"""Password hashing/verify helpers.

- Argon2id — рекомендуемый вариант для паролей (устойчив к GPU, без утечек по времени).
- Параметры берём из конфигурации (.env), чтобы их можно было тюнить под железо без правки кода.
- Хеширование/проверка отправляем в threadpool, чтобы не блокировать event loop.
- Ограничиваем максимальную длину пароля как простую защиту от DoS сверхдлинными строками.
"""

import logging

from opentelemetry import trace
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHash, VerificationError, VerifyMismatchError
from argon2.low_level import Type
from fastapi.concurrency import run_in_threadpool

from app.config import settings

log = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)

pwd_hasher = PasswordHasher(
    time_cost=settings.ARGON_TIME_COST,
    memory_cost=settings.ARGON_MEMORY_COST,
    parallelism=settings.ARGON_PARALLELISM,
    hash_len=settings.ARGON_HASH_LEN,
    salt_len=settings.ARGON_SALT_LEN,
    type=Type.ID,  # гарантия Argon2id
)

# Фейковый хэш для защиты от тайминг-атаки на email enumeration.
# Генерируется один раз при старте с теми же параметрами что и боевые хэши,
# чтобы verify против него занимал столько же времени (~300мс).
_DUMMY_HASH: str = pwd_hasher.hash("__dummy_sentinel__")


def get_dummy_hash() -> str:
    """Возвращает фейковый хэш для защиты от тайминг-атаки."""
    return _DUMMY_HASH


async def hash_password(*, password: str) -> str:
    with tracer.start_as_current_span("security.password.hash_argon2"):
        if len(password) > settings.ARGON_MAX_PASSWORD_LEN:
            raise ValueError("Пароль слишком длинный")
        return await run_in_threadpool(pwd_hasher.hash, password)


async def verify_password(*, password: str, hashed_password: str) -> bool:
    with tracer.start_as_current_span("security.password.verify_argon2"):
        def _verify() -> bool:
            if len(password) > settings.ARGON_MAX_PASSWORD_LEN:
                return False
            try:
                return pwd_hasher.verify(hashed_password, password)
            except VerifyMismatchError:
                return False
            except (VerificationError, InvalidHash) as exc:
                log.warning("Argon2 verify failed (%s)", exc.__class__.__name__)
                return False

        return await run_in_threadpool(_verify)
