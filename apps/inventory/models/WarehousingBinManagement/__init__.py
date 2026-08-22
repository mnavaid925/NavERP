"""Inventory 5.5 Warehousing & Bin Management — models.

Two entities, both layered ON the location spine SCM 4.3 owns (L36 — extend, never
re-declare): ``BinCapacity`` is the per-bin capacity envelope the generic one-number
``Location.capacity`` cannot express (weight AND volume AND quantity limits), and
``CrossDockOrder`` is the bypass-storage document whose two ledger legs post through
the append-only ``scm.StockMove`` book exactly like every other stock movement.
"""
from .BinCapacities import BinCapacity
from .CrossDockOrders import CrossDockOrder

__all__ = ["BinCapacity", "CrossDockOrder"]
