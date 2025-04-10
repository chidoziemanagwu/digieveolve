# blog/urls.py
from django.urls import path
from . import views

app_name = 'blog'

urlpatterns = [
    path('', views.blog_list, name='list'),
    path('category/<slug:category_slug>/', views.blog_list, name='category'),
    path('<slug:slug>/', views.blog_detail, name='detail'),

    # Admin URLs
    path('digievolveadmin/posts/', views.admin_posts, name='admin_posts'),
    path('digievolveadmin/posts/add/', views.admin_add_post, name='admin_add_post'),
    path('digievolveadmin/posts/<slug:slug>/edit/',
         views.admin_edit_post, name='admin_edit_post'),
    path('digievolveadmin/posts/<int:post_id>/delete/',
         views.admin_delete_post, name='admin_delete_post'),
    path('digievolveadmin/posts/<int:post_id>/toggle-status/',
         views.admin_toggle_post_status, name='admin_toggle_post_status'),

    # Category Management URLs
    path('digievolveadmin/categories/add/',
         views.admin_add_category, name='admin_add_category'),
    path('digievolveadmin/categories/<int:category_id>/edit/',
         views.admin_edit_category, name='admin_edit_category'),
    path('digievolveadmin/categories/<int:category_id>/delete/',
         views.admin_delete_category, name='admin_delete_category'),
]