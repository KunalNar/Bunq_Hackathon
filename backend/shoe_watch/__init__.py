"""Shoe-watch feature for GuardianAI.

Lets a user say "watch this shoe and buy it if it drops below X" and have the
agent monitor multiple retailers, narrate the buy in real time, and execute it
within a pre-authorized grace window.

Public surface (kept small on purpose):

    from backend.shoe_watch import models, store, scheduler, purchase

The Claude-facing tool wrappers live in `backend.agent.tools.shoe_watch_tools`
and call into this package. Keeping the agent layer thin means the same
business logic is callable from a CLI, from tests, and from the avatar UI
without re-plumbing.
"""

from backend.shoe_watch import models, purchase, scheduler, store  # noqa: F401

__all__ = ["models", "purchase", "scheduler", "store"]
