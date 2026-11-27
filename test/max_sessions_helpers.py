"""Small session-map port for MAX navigation; no Telegram suite imports."""

from contextlib import contextmanager

from off_loop_helpers import off_loop

from kiro_crew.history import ConversationLog, transcript_stem
from kiro_crew.session_map import ConversationOwnershipConflict


class Sessions:
    def __init__(self):
        self.mirror_links = {}
        self.inbound_keys = set()
        self.origin_links = {}
        self.reserved_generations = set()
        self.last_key = ""

    def get_origin_link(self, key):
        return self.origin_links.get(key)

    def get_mirror_link(self, key):
        return self.mirror_links.get(key)

    def has_mirror_row(self, key):
        return key in self.mirror_links

    def find_mirror_sessions(self, link, *, inbound_only=False):
        return [
            key
            for key, value in self.mirror_links.items()
            if value == link and (not inbound_only or key in self.inbound_keys)
        ]

    def set_mirror_link(self, key, link, *, accepts_inbound=False, reason=None):
        rivals = [k for k in self.find_mirror_sessions(link) if k != key]
        if rivals and (accepts_inbound or any(k in self.inbound_keys for k in rivals)):
            raise ConversationOwnershipConflict("conversation already held")
        self.mirror_links[key] = link
        if accepts_inbound:
            self.inbound_keys.add(key)
        else:
            self.inbound_keys.discard(key)

    def clear_mirror_link(self, key, *, reason=None):
        self.inbound_keys.discard(key)
        return self.mirror_links.pop(key, None) is not None

    def clear_mirror_links_at(self, link, *, reason=None):
        keys = self.find_mirror_sessions(link)
        for key in keys:
            self.clear_mirror_link(key, reason=reason)
        return keys

    @contextmanager
    def batched_save(self):
        yield

    async def aflush(self):
        pass

    def reserve_generation(self, key):
        self.reserved_generations.add(key)

    def max_generation(self, bucket):
        prefix = bucket + ":gen"
        return max(
            (
                int(k[len(prefix) :])
                for k in self.reserved_generations
                if k.startswith(prefix) and k[len(prefix) :].isdigit()
            ),
            default=0,
        )

    def channel_key_for_stem(self, stem):
        return next(
            (
                k
                for k in self.reserved_generations | set(self.mirror_links)
                if transcript_stem(k) == stem
            ),
            "",
        )

    def is_busy(self, key):
        return False

    def has_session(self, key):
        return True

    def get_pid(self, key):
        return None


def conversation_log(tmp_path, *, agent=""):
    log = ConversationLog(base_dir=tmp_path / "sessions")

    def seed():
        log.append("dashboard:chat-1", "assistant", "prior work")
        log.set_title("dashboard:chat-1", "Launch plan")
        if agent:
            log.update_metadata("dashboard:chat-1", {"agent": agent})

    off_loop(seed)
    return log
