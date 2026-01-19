from django.contrib import admin
from .models import Workspace, Folder, Report


@admin.register(Workspace)
class WorkspaceAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "created_at")
    search_fields = ("id", "user__username", "user__email")
    list_filter = ("created_at",)


@admin.register(Folder)
class FolderAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "workspace", "created_at", "updated_at")
    search_fields = ("name", "workspace__id")
    list_filter = ("created_at", "updated_at")


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "report_type", "status", "workspace", "folder", "created_at", "updated_at")
    search_fields = ("title", "report_type", "workspace__id")
    list_filter = ("status", "report_type", "created_at", "updated_at")
