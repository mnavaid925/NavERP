"""Inventory AlertsNotifications forms package (Sub-module 5.16).

Alerts are raised only by the detection engine and deliveries are an append-only log,
so the rule catalog is the one editable entity in this sub-module.
"""
from .AlertRules import AlertRuleForm

__all__ = [
    "AlertRuleForm",
]
