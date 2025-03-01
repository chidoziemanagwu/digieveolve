# Python standard library imports
from datetime import timedelta

# Django imports
from django.contrib import messages
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.db.models import Sum
from django.shortcuts import render, redirect
from django.urls import reverse
import requests

from digievolve import settings


# Local application imports
from .models import Activity, StudentProfile
from courses.models import Certificate, Course, Enrollment  # Import from courses app
from django.db import models  # Add this import for aggregation
from .forms import StudentRegistrationForm, CustomLoginForm  # Add


def login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        remember_me = request.POST.get('remember_me')

        # Initialize form before Turnstile validation
        form = AuthenticationForm(request, data=request.POST)

        # Validate Cloudflare Turnstile
        token = request.POST.get('cf-turnstile-response')
        if not token:
            messages.error(request, "Please complete the security check.")
            return render(request, 'accounts/login.html', {'form': form})

        # Verify the token with Cloudflare
        secret_key = "0x4AAAAAAA_PrYbgupT5euhBSvuwBQzu0h0"  # Replace with your actual secret key
        data = {
            'secret': secret_key,
            'response': token,
            'remoteip': request.META.get('REMOTE_ADDR')
        }

        try:
            response = requests.post('https://challenges.cloudflare.com/turnstile/v0/siteverify', data=data)
            result = response.json()

            if not result.get('success', False):
                messages.error(request, "Security check failed. Please try again.")
                return render(request, 'accounts/login.html', {'form': form})
        except Exception as e:
            # Log the exception
            print(f"Turnstile verification error: {e}")
            messages.error(request, "Error verifying security check. Please try again.")
            return render(request, 'accounts/login.html', {'form': form})

        # Continue with your existing login logic
        if form.is_valid():
            user = authenticate(request, username=username, password=password)
            if user is not None:
                login(request, user)

                if not remember_me:
                    request.session.set_expiry(0)

                # Record login activity
                try:
                    profile = StudentProfile.objects.get(user=user)
                    Activity.objects.create(
                        student=profile,
                        activity_type='login',
                        description=f"Logged in at {timezone.now().strftime('%Y-%m-%d %H:%M')}"
                    )
                except Exception as e:
                    # Just log the error, don't interrupt the login process
                    print(f"Error recording login activity: {e}")

                return redirect('core:dashboard')
            else:
                messages.error(request, "Invalid username or password.")
        else:
            messages.error(request, "Invalid form submission. Please check your inputs.")
    else:
        form = AuthenticationForm()

    return render(request, 'accounts/login.html', {'form': form})

def register_view(request):
    if request.user.is_authenticated:
        return redirect('accounts:dashboard')

    if request.method == 'POST':
        if not validate_turnstile(request):
            messages.error(request, "Please complete the security check.")
            return render(request, 'accounts/login.html', {'form': form})
        
        form = StudentRegistrationForm(request.POST)
        try:
            if form.is_valid():
                user = form.save()
                login(request, user)
                messages.success(request, "Welcome to DigiEvolve! Your account has been created successfully.")
                return redirect('accounts:profile')
            else:
                # Improve error display
                for field, errors in form.errors.items():
                    for error in errors:
                        messages.error(request, f"{field.capitalize()}: {error}")
        except Exception as e:
            # Log the error for debugging
            print(f"Registration error: {str(e)}")
            messages.error(request, f"An error occurred during registration: {str(e)}")
    else:
        form = StudentRegistrationForm()

    return render(request, 'accounts/register.html', {
        'form': form,
        'page_title': 'Create Your Student Account'
    })



@login_required(login_url='accounts:login')
def dashboard_view(request):
    # Get student profile
    student_profile = StudentProfile.objects.get(user=request.user)

    # Get enrolled courses
    enrolled_courses = Enrollment.objects.filter(
        student=student_profile
    ).select_related('course')

    # Get certificates
    certificates = Certificate.objects.filter(
        student=student_profile
    ).select_related('course')

    # Calculate progress percentage
    total_courses = enrolled_courses.count()
    completed_courses = enrolled_courses.filter(is_completed=True).count()
    progress_percentage = (completed_courses / total_courses * 100) if total_courses > 0 else 0

    # Get recent activities
    recent_activities = Activity.objects.filter(
        student=student_profile
    ).select_related('course').order_by('-timestamp')[:5]

    # Get recommended courses
    enrolled_course_ids = enrolled_courses.values_list('course_id', flat=True)
    recommended_courses = Course.objects.exclude(
        id__in=enrolled_course_ids
    ).order_by('?')[:3]  # Random selection of 3 courses

    context = {
        'student': student_profile,
        'enrolled_courses': enrolled_courses,
        'certificates': certificates,
        'progress_percentage': round(progress_percentage, 1),
        'recent_activities': recent_activities,
        'recommended_courses': recommended_courses,
    }

    return render(request, 'accounts/dashboard.html', context)


@login_required
def courses_view(request):
    student_profile = StudentProfile.objects.get(user=request.user)
    enrolled_courses = Enrollment.objects.filter(student=student_profile).select_related('course')

    context = {
        'enrolled_courses': enrolled_courses,
    }

    return render(request, 'accounts/courses.html', context)

@login_required
def certificates_view(request):
    student_profile = StudentProfile.objects.get(user=request.user)
    certificates = Certificate.objects.filter(student=student_profile).select_related('course')

    context = {
        'certificates': certificates,
    }

    return render(request, 'accounts/certificates.html', context)


@login_required
def profile_view(request):
    try:
        student = StudentProfile.objects.get(user=request.user)

        # Get enrolled courses
        enrolled_courses = Enrollment.objects.filter(student=student).select_related('course')

        # Calculate completed courses count
        completed_courses_count = enrolled_courses.filter(is_completed=True).count()  # Change is_completed to completed

        # Get certificates
        certificates = Certificate.objects.filter(student=student)

        context = {
            'student': student,
            'enrolled_courses': enrolled_courses,
            'enrolled_courses_count': enrolled_courses.count(),
            'completed_courses_count': completed_courses_count,
            'certificates': certificates,
            'certificates_count': certificates.count(),
        }

        return render(request, 'accounts/profile.html', context)

    except StudentProfile.DoesNotExist:
        messages.error(request, "Student profile not found. Please contact support.")
        return redirect('accounts:login')


@login_required
def settings_view(request):
    try:
        student = StudentProfile.objects.get(user=request.user)

        if request.method == 'POST':
            form_type = request.POST.get('form_type')

            if form_type == 'profile_info':
                # Handle profile information update
                first_name = request.POST.get('first_name')
                last_name = request.POST.get('last_name')
                email = request.POST.get('email')
                phone = request.POST.get('phone')
                bio = request.POST.get('bio')

                # Update user information
                request.user.first_name = first_name
                request.user.last_name = last_name
                request.user.email = email
                request.user.save()

                # Update student profile information
                student.phone = phone
                student.bio = bio
                student.save()

                messages.success(request, "Your profile information has been updated successfully.")

            elif form_type == 'password_change':
                # Handle password change
                password1 = request.POST.get('password1')
                password2 = request.POST.get('password2')

                if password1 and password2:
                    if password1 == password2:
                        request.user.set_password(password1)
                        request.user.save()
                        # Re-authenticate user to prevent logout after password change
                        login(request, request.user)
                        messages.success(request, "Your password has been changed successfully.")
                    else:
                        messages.error(request, "Passwords do not match.")
                else:
                    messages.error(request, "Please enter both password fields.")

            return redirect('accounts:settings')

        return render(request, 'accounts/settings.html', {
            'student': student,
            'page_title': 'Account Settings'
        })

    except StudentProfile.DoesNotExist:
        messages.error(request, "Student profile not found. Please contact support.")
        return redirect('accounts:dashboard')



def logout_view(request):
    logout(request)
    messages.success(request, "You have been successfully logged out.")
    return redirect('core:home')


# For development/testing
def validate_turnstile(request):
    """Validate the Cloudflare Turnstile token"""
    # Get the token from the request
    token = request.POST.get('cf-turnstile-response')

    # If using test key, accept any response
    if settings.DEBUG:
        return True

    # For production, verify with Cloudflare
    if not token:
        return False

    # Verify the token with Cloudflare
    secret_key = "YOUR_SECRET_KEY"  # Add to settings.py
    data = {
        'secret': secret_key,
        'response': token,
        'remoteip': request.META.get('REMOTE_ADDR')
    }

    try:
        response = requests.post('https://challenges.cloudflare.com/turnstile/v0/siteverify', data=data)
        result = response.json()
        return result.get('success', False)
    except Exception:
        # Log the exception
        return False