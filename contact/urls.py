from django.urls import path
from . import views

app_name = 'contact'

urlpatterns = [
    path('', views.contact_view, name='contact'),
    path('management/', views.contact_management, name='contact_management'),
    path('api/queries/<int:query_id>/', views.get_query_details, name='get_query_details'),
    path('api/queries/<int:query_id>/update/', views.update_query_status, name='update_query_status'),
    path('debug/', views.debug_contacts, name='debug_contacts'),
]