from django.urls import path
from . import views

app_name = 'resources'

urlpatterns = [
    path('', views.resource_list, name='list'),
    # This matches your ResourceCategory.get_absolute_url
    path('category/<slug:slug>/', views.category_detail, name='category_detail'),
    # Add this to match what's in your template
    path('category/<slug:category_slug>/', views.category_detail, name='category'),
    # Add this for individual resources
    path('resource/<slug:slug>/', views.resource_detail, name='detail'),


    # Admin URLs
    path('digievolveadmin/resources/', views.admin_resources, name='admin_resources'),
    path('digievolveadmin/resources/add/', views.admin_add_resource, name='admin_add_resource'),
    path('digievolveadmin/resources/edit/<int:resource_id>/', views.admin_edit_resource, name='admin_edit_resource'),
    path('digievolveadmin/resources/delete/<int:resource_id>/', views.admin_delete_resource, name='admin_delete_resource'),
    path('digievolveadmin/resources/categories/', views.admin_categories, name='admin_categories'),
]