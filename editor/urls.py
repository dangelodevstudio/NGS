from django.urls import path
from . import views

urlpatterns = [
    path('', views.editor_home, name='editor_home'),
    path('preview/', views.preview_laudo, name='preview_laudo'),
    path('pdf/', views.export_pdf, name='export_pdf'),
]
