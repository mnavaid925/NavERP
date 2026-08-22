"""Inventory 5.4 Receiving & Putaway — model re-exports."""
from .PutawayRules import PutawayRule, resolve_putaway_suggestion

__all__ = ["PutawayRule", "resolve_putaway_suggestion"]
