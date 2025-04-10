# accounts/urls.py
from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

app_name = 'accounts'

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('register/', views.register_view, name='register'),
    path('logout/', views.logout_view, name='logout'),
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('profile/', views.profile_view, name='profile'),
    path('settings/', views.settings_view, name='settings'),
    path('dashboard/courses/', views.courses_view, name='courses'),
    path('dashboard/certificates/', views.certificates_view, name='certificates'),


    # Password Reset URLs
    path('password-reset/',
         auth_views.PasswordResetView.as_view(
             template_name='accounts/password_reset.html',
             email_template_name='accounts/password_reset_email.html',
             subject_template_name='accounts/password_reset_subject.txt',
             success_url='/accounts/password-reset/done/'
         ),
         name='password_reset'),

    path('password-reset/done/',
         auth_views.PasswordResetDoneView.as_view(
             template_name='accounts/password_reset_done.html'
         ),
         name='password_reset_done'),

    path('password-reset-confirm/<uidb64>/<token>/',
         auth_views.PasswordResetConfirmView.as_view(
             template_name='accounts/password_reset_confirm.html',
             success_url='/accounts/password-reset-complete/'
         ),
         name='password_reset_confirm'),

    path('password-reset-complete/',
         auth_views.PasswordResetCompleteView.as_view(
             template_name='accounts/password_reset_complete.html'
         ),
         name='password_reset_complete'),

    # Add these to your existing accounts/urls.py
    path('digievolveadmin/login/', views.admin_login_view, name='admin_login'),
    path('digievolveadmin/dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('digievolveadmin/users/', views.admin_users, name='admin_users'),
    path('digievolveadmin/enrollments/', views.admin_enrollments, name='admin_enrollments'),
    path('digievolveadmin/reports/', views.admin_reports, name='admin_reports'),
    path('digievolveadmin/revenue/', views.admin_revenue, name='admin_revenue'),
    path('digievolveadmin/settings/', views.admin_settings, name='admin_settings'),


    # Student Management URLs
    path('digievolveadmin/users/', views.admin_users, name='admin_users'),
    path('digievolveadmin/users/add/', views.admin_add_student, name='admin_add_student'),
    path('digievolveadmin/users/<int:student_id>/view/',
         views.admin_view_student, name='admin_view_student'),
    path('digievolveadmin/users/<int:student_id>/edit/',
         views.admin_edit_student, name='admin_edit_student'),
    path('digievolveadmin/users/<int:student_id>/delete/',
         views.admin_delete_student, name='admin_delete_student'),


    path('digievolveadmin/enrollments/add/',
         views.admin_add_enrollment, name='admin_add_enrollment'),
    path('digievolveadmin/enrollments/<int:enrollment_id>/unenroll/',
         views.admin_unenroll_student, name='admin_unenroll_student'),


     path('contact-management/', views.contact_queries, name='contact_management'),
]