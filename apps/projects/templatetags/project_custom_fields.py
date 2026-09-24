from django import template

from apps.projects.forms.MasterDataConfiguration.CustomFieldMixin import custom_values_for_object

register = template.Library()


@register.simple_tag
def project_custom_values(obj):
    return custom_values_for_object(obj)
