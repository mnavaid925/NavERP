"""Procurement 6.4 Vendor Management — urls package."""
from .Portal import urlpatterns as _vm_portal
from .VendorInvoiceSubmissions import urlpatterns as _vm_submissions
from .VendorPortalAccess import urlpatterns as _vm_vpa
from .VendorSuspensions import urlpatterns as _vm_suspensions

urlpatterns = [
    *_vm_vpa,          # portal-access console (staff-managed bindings)
    *_vm_suspensions,  # blacklist/suspension register (request → decide → lift)
    *_vm_submissions,  # supplier-filed invoice review register
    *_vm_portal,       # login-gated supplier portal (home + invoice submit)
]
