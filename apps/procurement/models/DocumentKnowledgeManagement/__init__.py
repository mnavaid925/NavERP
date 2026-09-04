"""Procurement 6.19 Document & Knowledge Management — sub-package init (docstring-only).

Re-exports live in ``apps/procurement/models/__init__.py`` — the app-level package is the single
re-export point (6.13/6.14/6.15 precedent). Entity modules: ``Documents`` (the repository row
``ProcurementDocument`` plus the expiry/review reminder engine), ``Revisions`` (the immutable
``ProcurementDocumentRevision`` chain and the text-extraction helpers), ``Policies``
(``ProcurementPolicy``, the policy library) and ``KnowledgeResources`` (``KnowledgeResource``,
the best-practices/templates library).

Sibling entity modules of THIS sub-module import each other by MODULE
(``from apps.procurement.models.DocumentKnowledgeManagement.Documents import ProcurementDocument``)
and never through ``apps.procurement.models`` — the package-level re-export does not exist until
the Integrate phase lands it, and reaching for it here would be a star-import cycle at URLconf
import time.
"""
