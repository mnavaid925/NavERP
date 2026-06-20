from django.contrib import admin

from .models import Campaign, Case, CrmTask, KnowledgeArticle, Lead, Opportunity


@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    list_display = ("number", "name", "company", "status", "rating", "score", "owner", "tenant")
    list_filter = ("status", "rating", "source", "tenant")
    search_fields = ("number", "name", "company", "email")
    readonly_fields = ("number", "created_at", "updated_at")


@admin.register(Opportunity)
class OpportunityAdmin(admin.ModelAdmin):
    list_display = ("number", "name", "account", "stage", "amount", "probability", "owner", "tenant")
    list_filter = ("stage", "tenant")
    search_fields = ("number", "name")
    readonly_fields = ("number", "created_at", "updated_at")


@admin.register(Campaign)
class CampaignAdmin(admin.ModelAdmin):
    list_display = ("number", "name", "type", "status", "budget_actual", "owner", "tenant")
    list_filter = ("type", "status", "tenant")
    search_fields = ("number", "name")
    readonly_fields = ("number", "created_at", "updated_at")


@admin.register(Case)
class CaseAdmin(admin.ModelAdmin):
    list_display = ("number", "subject", "account", "priority", "status", "owner", "tenant")
    list_filter = ("status", "priority", "type", "tenant")
    search_fields = ("number", "subject")
    readonly_fields = ("number", "resolved_at", "created_at", "updated_at")


@admin.register(KnowledgeArticle)
class KnowledgeArticleAdmin(admin.ModelAdmin):
    list_display = ("number", "title", "category", "visibility", "status", "views_count", "tenant")
    list_filter = ("status", "visibility", "tenant")
    search_fields = ("number", "title", "category")
    readonly_fields = ("number", "views_count", "created_at", "updated_at")


@admin.register(CrmTask)
class CrmTaskAdmin(admin.ModelAdmin):
    list_display = ("number", "subject", "type", "priority", "status", "due_date", "owner", "tenant")
    list_filter = ("status", "priority", "type", "tenant")
    search_fields = ("number", "subject")
    readonly_fields = ("number", "completed_at", "created_at", "updated_at")
