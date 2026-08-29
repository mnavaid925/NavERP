"""Procurement 6.10 Purchase Order Management URL package — change orders, generation, tracking."""
from .Changes import urlpatterns as _pom_changes
from .Generation import urlpatterns as _pom_generation
from .LineTracking import urlpatterns as _pom_tracking

urlpatterns = [
    *_pom_changes,      # 6.10 change orders: file from a PO, list/detail/approve/reject
    *_pom_generation,   # 6.10 generation console: approved requisitions -> draft POs
    *_pom_tracking,     # 6.10 per-line delivery tracking board
]
