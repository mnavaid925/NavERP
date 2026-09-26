"""URL patterns for CPQ operational workflows."""
from django.urls import path
from apps.sales.views.QuoteProposalCPQ import QuoteOperations as views

urlpatterns = [
    # Approval governance
    path("quotes/approval-queue/", views.quote_approval_queue, name="quote_approval_queue"),
    path("quotes/<int:pk>/submit-approval/", views.quote_submit_approval, name="quote_submit_approval"),
    path("quotes/<int:pk>/approval-action/", views.quote_approval_action, name="quote_approval_action"),

    # Versioning & diff
    path("quotes/versions/", views.quote_version_list, name="quote_version_list"),
    path("quotes/<int:pk>/create-revision/", views.quote_create_revision, name="quote_create_revision"),
    path("quotes/compare/<int:pk_a>/<int:pk_b>/", views.quote_compare_versions, name="quote_compare_versions"),

    # Proposal templating & board
    path("quotes/proposals/", views.quote_proposal_board, name="quote_proposal_board"),
    path("quotes/<int:pk>/generate-proposal/", views.quote_generate_proposal, name="quote_generate_proposal"),

    # Public e-signature portal
    path("quotes/portal/<str:token>/", views.quote_portal_view, name="quote_portal_view"),
    path("quotes/portal/<str:token>/sign/", views.quote_portal_sign, name="quote_portal_sign"),
    path("quotes/portal/<str:token>/toggle/<int:line_id>/", views.quote_portal_toggle_line, name="quote_portal_toggle_line"),

    # Order conversion
    path("quotes/conversions/", views.quote_conversion_board, name="quote_conversion_board"),
    path("quotes/<int:pk>/convert-order/", views.quote_convert_to_order, name="quote_convert_to_order"),

    # Guided selling wizard
    path("quotes/guided-selling/", views.cpq_guided_selling, name="cpq_guided_selling"),
]
