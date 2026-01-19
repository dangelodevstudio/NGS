from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    path('login/', auth_views.LoginView.as_view(template_name='registration/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('users/', views.user_manage, name='user_manage'),
    path('users/<int:user_id>/toggle/', views.user_toggle_active, name='user_toggle_active'),
    path('', views.dashboard, name='dashboard'),
    path('folders/new/', views.create_folder, name='folder_create'),
    path('folders/<int:folder_id>/', views.folder_detail, name='folder_detail'),
    path('reports/new/', views.report_new, name='report_new'),
    path('reports/<uuid:report_id>/', views.report_editor, name='report_editor'),
    path('reports/<uuid:report_id>/delete/', views.report_delete, name='report_delete'),
    path('reports/<uuid:report_id>/duplicate/', views.report_duplicate, name='report_duplicate'),
    path('preview/', views.preview_laudo, name='preview_laudo'),
    path('pdf/', views.export_pdf, name='export_pdf'),
]
