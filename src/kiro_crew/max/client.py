"""MAX HTTPS API and durable, post-handler polling checkpoints."""

import asyncio
import hashlib
import json
from pathlib import Path

API_ORIGIN = "https://platform-api2.max.ru"


class MaxClient:
    def __init__(self, token, cursor, receive):
        self._token = token
        self.cursor = Path(cursor)
        self.receive = receive
        self._http = None
        self._task = None
        self.on_close = None
        self._state = {"marker": None, "seen": []}
        if self.cursor.exists():
            self._state = json.loads(self.cursor.read_text(encoding="utf-8"))
        self.marker = self._state["marker"]

    def _checkpoint(self, state):
        self.cursor.parent.mkdir(parents=True, exist_ok=True)
        staged = self.cursor.with_suffix(".new")
        staged.write_text(json.dumps(state), encoding="utf-8")
        staged.replace(self.cursor)
        self._state = state
        self.marker = state["marker"]

    async def handle_page(self, page):
        for update in page.get("updates", []):
            # Fingerprints retain no message content, pairing codes or callbacks.
            key = hashlib.sha256(
                json.dumps(update, sort_keys=True).encode()
            ).hexdigest()
            if key in self._state["seen"]:
                continue
            await self.receive(update)
            self._checkpoint(
                {"marker": self.marker, "seen": (self._state["seen"] + [key])[-4096:]}
            )
        self._checkpoint({"marker": page["marker"], "seen": self._state["seen"]})

    async def request(self, method, path, *, params=None, body=None):
        if self._http is None:
            import aiohttp

            self._http = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=100))
        # Never put credentials in URLs, exceptions, reprs or logs.
        try:
            async with self._http.request(
                method,
                API_ORIGIN + path,
                params=params,
                json=body,
                headers={"Authorization": self._token},
                allow_redirects=False,
            ) as response:
                if response.status != 200:
                    raise RuntimeError(f"MAX API status {response.status}")
                return await response.json()
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001 -- never expose a vendor body or credential in an error
            raise RuntimeError("MAX request failed") from None

    async def send(self, uid, text, **kwargs):
        result = await self.request(
            "POST", "/messages", params={"user_id": uid}, body={"text": text}
        )
        return result["message"]["body"]["mid"]

    async def answer(self, cid, text):
        await self.request(
            "POST", "/answers", params={"callback_id": cid}, body={"notification": text}
        )

    async def chat_type(self, cid):
        result = await self.request("GET", f"/chats/{int(cid)}")
        return result.get("type")

    async def poll(self):
        while True:
            try:
                params = {
                    "timeout": 30,
                    "limit": 100,
                    "types": "message_created,message_callback,bot_started",
                }
                if self.marker is not None:
                    params["marker"] = self.marker
                await self.handle_page(
                    await self.request("GET", "/updates", params=params)
                )
            except asyncio.CancelledError:
                raise
            except Exception:  # noqa: BLE001 -- retain the checkpoint and retry a failed page
                await asyncio.sleep(5)

    async def close(self):
        if self._task:
            self._task.cancel()
            await asyncio.gather(self._task, return_exceptions=True)
        if self._http:
            await self._http.close()
        if getattr(self, "dispatcher", None):
            await self.dispatcher.close()
        if self.on_close:
            self.on_close()
