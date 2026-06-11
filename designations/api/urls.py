from django.urls import path
from . import views

urlpatterns = [
    # All routes are scoped to a specific department
    path('<int:dept_id>/list/', views.DesignationListView.as_view(), name='designation-list'),
    path('<int:dept_id>/create/', views.DesignationCreateView.as_view(), name='designation-create'),
    path('<int:dept_id>/<int:id>/update/', views.DesignationUpdateView.as_view(), name='designation-update'),
    path('<int:dept_id>/<int:id>/delete/', views.DesignationDeleteView.as_view(), name='designation-delete'),
]