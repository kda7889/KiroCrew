"""Single-owner authorization and operator-issued, ephemeral pairing codes."""

import asyncio
import hashlib
import hmac
import secrets
import time

PAIR_TTL = 300
PAIR_ATTEMPTS = 5


class OwnerAccess:
    def __init__(self, ids, save, *, clock=time.monotonic):
        self.owner = self.numeric_owner(ids)
        self._configured = not (isinstance(ids, list) and ids == [])
        self._save = save
        self._clock = clock
        self._digest = None
        self._expires = 0
        self._attempts = 0
        self._lock = asyncio.Lock()

    @staticmethod
    def numeric_owner(ids):
        return (
            ids[0]
            if isinstance(ids, list) and len(ids) == 1 and type(ids[0]) is int and ids[0] > 0
            else None
        )

    def reload(self, ids, *, enabled):
        self.owner = self.numeric_owner(ids) if enabled else None
        self._configured = not (enabled and isinstance(ids, list) and ids == [])
        if self._configured:
            self._digest = None

    def allowed(self, uid):
        return type(uid) is int and uid > 0 and uid == self.owner

    def issue(self):
        if self._configured or self.owner is not None:
            raise ValueError("Remove the configured owner before pairing")
        code = secrets.token_urlsafe(24)
        self._digest = hashlib.sha256(code.encode()).digest()
        self._expires = self._clock() + PAIR_TTL
        self._attempts = 0
        return code

    async def claim(self, uid, code):
        async with self._lock:
            if (
                self.owner is not None
                or self._digest is None
                or type(uid) is not int
                or uid <= 0
                or not isinstance(code, str)
            ):
                return False
            self._attempts += 1
            valid = (
                self._clock() < self._expires
                and self._attempts <= PAIR_ATTEMPTS
                and hmac.compare_digest(self._digest, hashlib.sha256(code.encode()).digest())
            )
            if valid or self._attempts >= PAIR_ATTEMPTS or self._clock() >= self._expires:
                self._digest = None
            if not valid:
                return False
            # Consume before persistence; a failed save must never grant access.
            self._save(uid)
            self.owner = uid
            self._configured = True
            return True
