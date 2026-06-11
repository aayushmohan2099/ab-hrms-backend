from django.urls import path
from . import views

urlpatterns = [
    # 1) List departments (Paginated)
    path('list/', views.DepartmentListView.as_view(), name='department-list'),
    
    # 3) Create department
    path('create/', views.DepartmentCreateView.as_view(), name='department-create'),
    
    # 2) Retrieve department details
    path('<int:id>/', views.DepartmentDetailView.as_view(), name='department-detail'),
    
    # 6) Update department (PATCH)
    path('<int:id>/update/', views.DepartmentUpdateView.as_view(), name='department-update'),
    
    # 5) Delete department (Soft Delete)
    path('<int:id>/delete/', views.DepartmentDeleteView.as_view(), name='department-delete'),
]