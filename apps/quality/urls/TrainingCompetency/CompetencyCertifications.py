from django.urls import path

from apps.quality.views.TrainingCompetency import CompetencyCertifications as views

urlpatterns = [
    # Dashboard & Dossier
    path("training/dashboard/", views.training_compliance_dashboard, name="training_compliance_dashboard"),
    path("training/dossier/", views.employee_training_dossier, name="employee_training_dossier"),

    # Competency Certification CRUD
    path("training/certifications/", views.competency_certification_list, name="competency_certification_list"),
    path("training/certifications/create/", views.competency_certification_create, name="competency_certification_create"),
    path("training/certifications/export/", views.competency_certification_export_csv, name="competency_certification_export_csv"),
    path("training/certifications/<int:pk>/", views.competency_certification_detail, name="competency_certification_detail"),
    path("training/certifications/<int:pk>/edit/", views.competency_certification_edit, name="competency_certification_edit"),
    path("training/certifications/<int:pk>/delete/", views.competency_certification_delete, name="competency_certification_delete"),
    path("training/certifications/<int:pk>/renew/", views.competency_certification_renew, name="competency_certification_renew"),
    path("training/certifications/<int:pk>/suspend/", views.competency_certification_suspend, name="competency_certification_suspend"),
]
