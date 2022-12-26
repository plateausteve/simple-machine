from django.contrib import admin
from .models import Item, Comparison, Group
from import_export import resources
from import_export.admin import ImportExportModelAdmin

class ComparisonResource(resources.ModelResource):
    class Meta:
        model = Comparison

class ScriptResource(resources.ModelResource):
    class Meta:
        model = Item

class ComparisonAdmin(ImportExportModelAdmin):
    resource_class = ComparisonResource

class ScriptAdmin(ImportExportModelAdmin):
    resource_class = ScriptResource

admin.site.register(Comparison, ComparisonAdmin)
admin.site.register(Item, ScriptAdmin)
admin.site.register(Group)
