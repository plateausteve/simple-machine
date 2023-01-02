from django.contrib import admin
from .models import Item, Comparison, Group, Student
from import_export import resources
from import_export.admin import ImportExportModelAdmin

class ComparisonResource(resources.ModelResource):
    class Meta:
        model = Comparison

class ItemResource(resources.ModelResource):
    class Meta:
        model = Item

class StudentResource(resources.ModelResource):
    class Meta:
        model = Student

class ComparisonAdmin(ImportExportModelAdmin):
    resource_class = ComparisonResource

class ItemAdmin(ImportExportModelAdmin):
    resource_class = ItemResource
    exclude = ['id']

class StudentAdmin(ImportExportModelAdmin):
    resource_class = StudentResource
    exclude = ['id']

admin.site.register(Comparison, ComparisonAdmin)
admin.site.register(Item, ItemAdmin)
admin.site.register(Group)
admin.site.register(Student, StudentAdmin)
