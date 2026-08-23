"""Inventory 5.12 Multi-Location Management — model re-exports.

One entity: ``LocationNetwork`` [LNW-], the org-tier tree (company › region › dc ›
store) whose nodes OPTIONALLY map to one stocked ``scm.Location`` — configuration
nothing else records, deliberately separate from scm's bin/zone hierarchy (L36).
Zero writes outside its own row; the global stock picture is DERIVED on the views
side, never stored here.
"""
from .LocationNetworks import LocationNetwork

__all__ = ["LocationNetwork"]
