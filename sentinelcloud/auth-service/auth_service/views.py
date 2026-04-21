from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest


@login_required
def me(request: HttpRequest) -> JsonResponse:
    user = request.user
    return JsonResponse(
        {
            "username": user.username,
            "email": user.email,
            "groups": [g.name for g in user.groups.all()],
        }
    )


@csrf_exempt
def health(_: HttpRequest) -> JsonResponse:
    return JsonResponse({"status": "ok"})


@csrf_exempt
def metrics(_: HttpRequest) -> HttpResponse:
    return HttpResponse(generate_latest(), content_type=CONTENT_TYPE_LATEST)
