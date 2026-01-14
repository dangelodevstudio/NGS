import uuid
from .models import Workspace


class WorkspaceMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        workspace_id = request.session.get("workspace_id") or request.COOKIES.get("workspace_id")
        workspace = None
        if workspace_id:
            workspace = Workspace.objects.filter(id=workspace_id).first()
        if not workspace:
            workspace = Workspace.objects.create()
            request.session["workspace_id"] = str(workspace.id)
            request._set_workspace_cookie = True
        else:
            request.session["workspace_id"] = str(workspace.id)
        request.workspace = workspace

        response = self.get_response(request)

        if getattr(request, "_set_workspace_cookie", False):
            response.set_cookie(
                "workspace_id",
                str(workspace.id),
                max_age=31536000,
                samesite="Lax",
            )
        return response
