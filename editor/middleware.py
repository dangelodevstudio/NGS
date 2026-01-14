import uuid
from .models import Workspace


class WorkspaceMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        workspace = None
        workspace_id = request.session.get("workspace_id") or request.COOKIES.get("workspace_id")

        if request.user.is_authenticated:
            workspace = Workspace.objects.filter(user=request.user).first()
            if not workspace and workspace_id:
                candidate = Workspace.objects.filter(id=workspace_id, user__isnull=True).first()
                if candidate:
                    candidate.user = request.user
                    candidate.save(update_fields=["user"])
                    workspace = candidate
            if not workspace:
                workspace = Workspace.objects.create(user=request.user)
            request.session["workspace_id"] = str(workspace.id)
        else:
            request.session.pop("workspace_id", None)

        request.workspace = workspace

        response = self.get_response(request)

        return response
