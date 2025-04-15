# Python standard library imports
from datetime import timedelta
from django.utils import timezone

# Django imports
from django.contrib import messages
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.shortcuts import get_object_or_404, render, redirect
from django.urls import reverse
import requests
from functools import wraps

from contact.models import Contact
from digievolve import settings
from django.contrib.auth.models import User


# Local application imports
from .models import Activity, User
from courses.models import Certificate, Course, Enrollment, Payment # Import from courses app
from django.db import IntegrityError, models, transaction  # Add this import for aggregation
from .forms import StudentRegistrationForm, CustomLoginForm  # Add
import logging
from django.contrib.admin.views.decorators import staff_member_required
from blog.models import BlogPost
from django.db.models.functions import Cast, Coalesce, TruncDate
from django.db.models import Count, Sum, Q, F, FloatField, Avg, DecimalField
from .decorators import admin_login_required
from django.http import JsonResponse
import json


logger = logging.getLogger(__name__)


def register_view(request):
    if request.user.is_authenticated:
        return redirect('accounts:dashboard')

    if request.method == 'POST':
        # Create a copy of POST data that we can modify
        post_data = request.POST.copy()

        # Get the Turnstile token
        token = request.POST.get('cf-turnstile-response')

        # Add the token to the form data with the correct field name
        if token:
            post_data['cf_turnstile_response'] = token

        # Initialize the form with the modified POST data
        form = StudentRegistrationForm(post_data)

        # Validate Cloudflare Turnstile separately from form validation
        if not token:
            messages.error(request, "Please complete the security check.")
            return render(request, 'accounts/register.html', {'form': form})

        # Verify the token with Cloudflare
        secret_key = settings.CLOUDFLARE_TURNSTILE_SECRET_KEY
        data = {
            'secret': secret_key,
            'response': token,
            'remoteip': request.META.get('REMOTE_ADDR')
        }

        try:
            response = requests.post('https://challenges.cloudflare.com/turnstile/v0/siteverify', data=data)
            result = response.json()

            if not result.get('success', False):
                logger.error(f"Turnstile verification failed: {result}")
                messages.error(request, "Security check failed. Please try again.")
                return render(request, 'accounts/register.html', {'form': form})
        except Exception as e:
            logger.error(f"Turnstile verification error: {e}")
            messages.error(request, "Error verifying security check. Please try again.")
            return render(request, 'accounts/register.html', {'form': form})

        # If Turnstile validation passed, proceed with form validation
        if form.is_valid():
            try:
                # Save the user and log them in
                user = form.save()
                # Set user as student
                user.is_student = True
                user.user_type = 'student'
                user.save()

                login(request, user)
                messages.success(request, "Welcome to DigiEvolve! Your account has been created successfully.")
                return redirect('accounts:profile')
            except Exception as e:
                logger.error(f"Registration error: {e}")
                messages.error(request, f"An error occurred during registration: {e}")
        else:
            # Display form errors as messages
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field.capitalize()}: {error}")
    else:
        # Initialize an empty form for GET requests
        form = StudentRegistrationForm()

    return render(request, 'accounts/register.html', {
        'form': form,
        'page_title': 'Create Your Student Account'
    })


def login_view(request):
    if request.method == 'POST':
        # Create a copy of POST data that we can modify
        post_data = request.POST.copy()

        # Get the Turnstile token
        token = request.POST.get('cf-turnstile-response')

        # Add the token to the form data with the correct field name
        if token:
            post_data['cf_turnstile_response'] = token

        # Initialize form with request and modified POST data
        form = CustomLoginForm(request=request, data=post_data)

        # Validate Cloudflare Turnstile separately from form validation
        if not token:
            messages.error(request, "Please complete the security check.")
            return render(request, 'accounts/login.html', {'form': form})

        # Verify the token with Cloudflare
        secret_key = settings.CLOUDFLARE_TURNSTILE_SECRET_KEY
        data = {
            'secret': secret_key,
            'response': token,
            'remoteip': request.META.get('REMOTE_ADDR')
        }

        try:
            response = requests.post('https://challenges.cloudflare.com/turnstile/v0/siteverify', data=data)
            result = response.json()

            if not result.get('success', False):
                logger.error(f"Turnstile verification failed: {result}")
                messages.error(request, "Security check failed. Please try again.")
                return render(request, 'accounts/login.html', {'form': form})
        except Exception as e:
            logger.error(f"Turnstile verification error: {e}")
            messages.error(request, "Error verifying security check. Please try again.")
            return render(request, 'accounts/login.html', {'form': form})

        # If Turnstile validation passed, proceed with form validation
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            remember_me = request.POST.get('remember_me')

            user = authenticate(request, username=username, password=password)
            if user is not None:
                login(request, user)

                if not remember_me:
                    request.session.set_expiry(0)

                # Record login activity
                try:
                    Activity.objects.create(
                        user=user,
                        activity_type='login',
                        description=f"Logged in at {timezone.now().strftime('%Y-%m-%d %H:%M')}"
                    )
                except Exception as e:
                    # Just log the error, don't interrupt the login process
                    logger.error(f"Error recording login activity: {e}")

                return redirect('accounts:dashboard')
            else:
                messages.error(request, "Invalid username or password.")
        else:
            # Display form errors as messages
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field.capitalize()}: {error}")
    else:
        form = CustomLoginForm()

    return render(request, 'accounts/login.html', {'form': form})


@login_required(login_url='accounts:login')
def dashboard_view(request):
    # Get enrolled courses with related course data
    enrollments = Enrollment.objects.filter(
        student=request.user,
        is_active=True
    ).select_related('course')

    # Get certificates
    certificates = Certificate.objects.filter(
        student=request.user
    ).select_related('course')

    # Calculate overall progress
    total_progress = 0
    completed_courses = 0
    total_courses = enrollments.count()

    if total_courses > 0:
        for enrollment in enrollments:
            # Get all modules for the course
            total_modules = enrollment.course.modules.count()
            if total_modules > 0:
                # Get completed modules
                completed_modules = len([m for m in enrollment.completed_modules.split(',') if m])
                # Calculate progress for this course
                course_progress = (completed_modules / total_modules) * 100
                total_progress += course_progress

                if enrollment.is_completed:
                    completed_courses += 1

        # Calculate average progress across all courses
        progress_percentage = total_progress / total_courses
    else:
        progress_percentage = 0

    # Get recent activities
    recent_activities = []

    # Add module completions
    for enrollment in enrollments:
        if enrollment.completed_modules:
            completed_module_ids = [int(m) for m in enrollment.completed_modules.split(',') if m]
            completed_modules = enrollment.course.modules.filter(id__in=completed_module_ids)

            for module in completed_modules:
                recent_activities.append({
                    'activity_type': 'completion',
                    'description': f'Completed module: {module.title}',
                    'timestamp': enrollment.last_accessed,
                    'course': enrollment.course
                })

    # Add course enrollments
    for enrollment in enrollments:
        recent_activities.append({
            'activity_type': 'enrollment',
            'description': f'Enrolled in course: {enrollment.course.title}',
            'timestamp': enrollment.enrollment_date,
            'course': enrollment.course
        })

    # Add certificate earnings
    for certificate in certificates:
        recent_activities.append({
            'activity_type': 'certificate',
            'description': f'Earned certificate for {certificate.course.title}',
            'timestamp': certificate.issued_date,
            'course': certificate.course
        })

    # Sort activities by timestamp and get the 5 most recent
    recent_activities.sort(key=lambda x: x['timestamp'], reverse=True)
    recent_activities = recent_activities[:5]

    # Get recommended courses
    enrolled_course_ids = enrollments.values_list('course_id', flat=True)
    recommended_courses = Course.objects.exclude(
        id__in=enrolled_course_ids
    ).order_by('?')[:3]  # Random selection of 3 courses

    # Get course progress details
    course_progress_details = []
    for enrollment in enrollments:
        total_modules = enrollment.course.modules.count()
        completed_modules = len([m for m in enrollment.completed_modules.split(',') if m])

        if total_modules > 0:
            progress = (completed_modules / total_modules) * 100
        else:
            progress = 0

        course_progress_details.append({
            'course': enrollment.course,
            'progress': progress,
            'completed_modules': completed_modules,
            'total_modules': total_modules,
            'last_accessed': enrollment.last_accessed
        })

    context = {
        'student': request.user,
        'enrolled_courses': enrollments,
        'course_progress_details': course_progress_details,
        'certificates': certificates,
        'certificates_count': certificates.count(),
        'progress_percentage': round(progress_percentage, 1),
        'completed_courses': completed_courses,
        'total_courses': total_courses,
        'recent_activities': recent_activities,
        'recommended_courses': recommended_courses,
    }

    return render(request, 'accounts/dashboard.html', context)



    
@login_required
def courses_view(request):
    enrolled_courses = Enrollment.objects.filter(student=request.user).select_related('course')

    context = {
        'enrolled_courses': enrolled_courses,
    }

    return render(request, 'accounts/courses.html', context)


@login_required
def certificates_view(request):
    certificates = Certificate.objects.filter(student=request.user).select_related('course')

    context = {
        'certificates': certificates,
    }

    return render(request, 'accounts/certificates.html', context)


@login_required
def profile_view(request):
    # Get enrolled courses
    enrolled_courses = Enrollment.objects.filter(student=request.user).select_related('course')

    # Calculate completed courses count
    completed_courses_count = enrolled_courses.filter(is_completed=True).count()

    # Get certificates
    certificates = Certificate.objects.filter(student=request.user)

    context = {
        'student': request.user,
        'enrolled_courses': enrolled_courses,
        'enrolled_courses_count': enrolled_courses.count(),
        'completed_courses_count': completed_courses_count,
        'certificates': certificates,
        'certificates_count': certificates.count(),
    }

    return render(request, 'accounts/profile.html', context)


@login_required
def settings_view(request):
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
            request.user.phone = phone
            request.user.bio = bio
            request.user.save()

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
        'student': request.user,
        'page_title': 'Account Settings'
    })

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
    
def is_digievolve_admin(user):
    """Check if user is a DigiEvolve admin"""
    try:
        return user.admin_type != 'none' and user.is_active_admin
    except:
        return False



# accounts/views.py

@admin_login_required
def admin_users(request):
    """
    View for managing users in the admin panel.
    Shows only users marked as students.
    """
    # Get all users who are marked as students
    users = User.objects.filter(is_student=True)

    # Handle search functionality
    search_query = request.GET.get('search', '')
    if search_query:
        users = users.filter(
            Q(first_name__icontains=search_query) |
            Q(last_name__icontains=search_query) |
            Q(email__icontains=search_query)
        )

    # Annotate with enrollment count
    users = users.annotate(
        enrollment_count=models.Count('enrollment')
    ).order_by('-date_joined')

    context = {
        'users': users,
        'search_query': search_query,
        'page_title': 'Student Management'
    }

    return render(request, 'digievolveadmin/users.html', context)





@admin_login_required
def admin_view_student(request, student_id):
    user = get_object_or_404(User, id=student_id)
    enrollments = Enrollment.objects.filter(student=user).select_related('course')
    activities = Activity.objects.filter(user=user).order_by('-timestamp')[:10]

    context = {
        'student': user,
        'enrollments': enrollments,
        'activities': activities,
        'total_enrollments': enrollments.count(),
        'completed_courses': enrollments.filter(is_completed=True).count(),
    }
    return render(request, 'digievolveadmin/student_detail.html', context)




@admin_login_required
def admin_edit_student(request, student_id):
    user = get_object_or_404(User, id=student_id)  # Changed to 'user' to match template

    if request.method == 'POST':
        try:
            # Update user information
            user.first_name = request.POST.get('first_name')
            user.last_name = request.POST.get('last_name')
            user.email = request.POST.get('email')
            user.username = request.POST.get('username')
            user.phone = request.POST.get('phone')
            user.bio = request.POST.get('bio')
            user.admin_type = request.POST.get('admin_type')
            
            # Handle boolean fields
            user.is_active = 'is_active' in request.POST
            user.is_active_admin = 'is_active_admin' in request.POST
            user.is_student = 'is_student' in request.POST

            # Update user_type based on is_student and admin_type
            if user.is_student and user.admin_type != 'none':
                user.user_type = 'both'
            elif user.is_student:
                user.user_type = 'student'
            elif user.admin_type != 'none':
                user.user_type = 'admin'
            else:
                user.user_type = 'none'

            # Handle profile image
            if 'profile_image' in request.FILES:
                user.profile_image = request.FILES['profile_image']

            # Validate email uniqueness
            if User.objects.filter(email=user.email).exclude(id=user.id).exists():
                messages.error(request, 'Email already exists')
                return render(request, 'digievolveadmin/user_edit.html', {'user': user})

            # Validate username uniqueness
            if User.objects.filter(username=user.username).exclude(id=user.id).exists():
                messages.error(request, 'Username already exists')
                return render(request, 'digievolveadmin/user_edit.html', {'user': user})

            user.save()
            messages.success(request, 'User information updated successfully')
            return redirect('accounts:admin_view_student', student_id=user.id)

        except Exception as e:
            messages.error(request, f'Error updating user: {str(e)}')
            return render(request, 'digievolveadmin/user_edit.html', {'user': user})

    return render(request, 'digievolveadmin/student_edit.html', {'user': user})

@admin_login_required
def admin_delete_student(request, student_id):
    """
    View for deleting a student
    """
    if request.method == 'POST':
        user = get_object_or_404(User, id=student_id)
        try:
            # Delete the user
            user.delete()
            messages.success(request, 'User deleted successfully')
        except Exception as e:
            messages.error(request, f'Error deleting user: {str(e)}')

        return redirect('accounts:admin_users')

    return redirect('accounts:admin_users')


@admin_login_required
def admin_add_student(request):
    if request.method == 'POST':
        try:
            # Get form data
            email = request.POST.get('email')
            password = request.POST.get('password')
            confirm_password = request.POST.get('confirm_password')
            first_name = request.POST.get('first_name')
            last_name = request.POST.get('last_name')
            phone = request.POST.get('phone', '')
            bio = request.POST.get('bio', '')

            # Basic validation
            if not all([email, password, confirm_password, first_name, last_name]):
                messages.error(request, 'Please fill in all required fields')
                return render(request, 'digievolveadmin/student_add.html')

            # Validate password match
            if password != confirm_password:
                messages.error(request, 'Passwords do not match')
                return render(request, 'digievolveadmin/student_add.html')

            # Check if user already exists
            if User.objects.filter(Q(email=email) | Q(username=email)).exists():
                messages.error(request, 'A user with this email already exists')
                return render(request, 'digievolveadmin/student_add.html')

            # Create user in a transaction
            with transaction.atomic():
                # Create the User with student role
                user = User.objects.create_user(
                    username=email,
                    email=email,
                    password=password,
                    first_name=first_name,
                    last_name=last_name,
                    phone=phone,
                    bio=bio,
                    is_student=True,
                    user_type='student'
                )

                # Handle profile image
                if 'profile_image' in request.FILES:
                    user.profile_image = request.FILES['profile_image']
                    user.save()

                # Create activity record
                Activity.objects.create(
                    user=user,
                    activity_type='other',
                    description='Account created'
                )

            messages.success(request, f'Student {first_name} {last_name} added successfully')
            return redirect('accounts:admin_users')

        except IntegrityError as e:
            logger.error(f"IntegrityError in admin_add_student: {str(e)}")
            messages.error(request, 'Error: Unable to create student account. Please try again.')
            return render(request, 'digievolveadmin/student_add.html')

        except Exception as e:
            logger.error(f"Error in admin_add_student: {str(e)}")
            messages.error(request, f'Error adding student: {str(e)}')
            return render(request, 'digievolveadmin/student_add.html')

    return render(request, 'digievolveadmin/student_add.html')


def admin_login_view(request):
    if request.user.is_authenticated:
        # Check if user is an admin
        if request.user.admin_type != 'none' and request.user.is_active_admin:
            return redirect('accounts:admin_dashboard')
        return redirect('accounts:dashboard')

    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        turnstile_response = request.POST.get('cf-turnstile-response')

        # Verify Turnstile response
        if not turnstile_response:
            messages.error(request, "Please complete the security check.")
            return render(request, 'digievolveadmin/login.html')

        # Verify the token with Cloudflare
        data = {
            'secret': settings.CLOUDFLARE_TURNSTILE_SECRET_KEY,
            'response': turnstile_response,
        }
        response = requests.post('https://challenges.cloudflare.com/turnstile/v0/siteverify', data=data)
        result = response.json()

        if not result.get('success'):
            messages.error(request, "Security check failed. Please try again.")
            return render(request, 'digievolveadmin/login.html')

        try:
            # Find user by email
            user = User.objects.get(email=email)

            # Authenticate user
            authenticated_user = authenticate(username=user.username, password=password)

            if authenticated_user is not None:
                # Check if user is an admin
                if authenticated_user.admin_type != 'none' and authenticated_user.is_active_admin:
                    login(request, authenticated_user)
                    # Record login time
                    authenticated_user.record_admin_login()
                    messages.success(request, f"Welcome back, {authenticated_user.first_name}!")
                    return redirect('accounts:admin_dashboard')
                else:
                    messages.error(request, "You don't have admin privileges or your admin account is inactive.")
            else:
                messages.error(request, "Invalid credentials.")
        except User.DoesNotExist:
            messages.error(request, "No account found with this email.")

    return render(request, 'digievolveadmin/login.html')


@admin_login_required
def admin_dashboard(request):
    # Get counts and statistics
    total_students = User.objects.filter(is_student=True).count()
    total_courses = Course.objects.count()
    total_enrollments = Enrollment.objects.count()

    # Calculate revenue for last 30 days
    thirty_days_ago = timezone.now() - timedelta(days=30)
    recent_revenue = Payment.objects.filter(
        status='completed',
        created_at__gte=thirty_days_ago
    ).aggregate(Sum('amount'))['amount__sum'] or 0

    # Get recent enrollments
    recent_enrollments = Enrollment.objects.select_related(
        'student', 'course'
    ).order_by('-enrollment_date')[:5]

    # Get popular courses
    popular_courses = Course.objects.annotate(
        student_count=Count('Course_enrollments'),
        revenue=Sum('Course_payment_enrollments__amount',
                   filter=Q(Course_payment_enrollments__status='completed'))
    ).order_by('-student_count')[:5]

    # Get recent blog posts
    recent_posts = BlogPost.objects.order_by('-published_date')[:5]

    # Calculate monthly statistics
    current_month = timezone.now().month
    current_year = timezone.now().year
    monthly_enrollments = Enrollment.objects.filter(
        enrollment_date__month=current_month,
        enrollment_date__year=current_year
    ).count()

    monthly_revenue = Payment.objects.filter(
        status='completed',
        created_at__month=current_month,
        created_at__year=current_year
    ).aggregate(Sum('amount'))['amount__sum'] or 0

    context = {
        'total_students': total_students,
        'total_courses': total_courses,
        'total_enrollments': total_enrollments,
        'recent_revenue': recent_revenue,
        'recent_enrollments': recent_enrollments,
        'popular_courses': popular_courses,
        'recent_posts': recent_posts,
        'monthly_enrollments': monthly_enrollments,
        'monthly_revenue': monthly_revenue,
    }

    return render(request, 'digievolveadmin/dashboard.html', context)




@admin_login_required
def admin_users(request):
    """
    View for managing users in the admin panel.
    Shows only users marked as students.
    """
    # Get all users who are marked as students
    users = User.objects.filter(is_student=True)

    # Handle search functionality
    search_query = request.GET.get('search', '')
    if search_query:
        users = users.filter(
            Q(first_name__icontains=search_query) |
            Q(last_name__icontains=search_query) |
            Q(email__icontains=search_query)
        )

    # Annotate each user with their enrollment count
    users = users.annotate(
        enrollment_count=Count('enrollment')
    )

    context = {
        'users': users,
        'search_query': search_query,
        'total_students': users.count()
    }

    return render(request, 'digievolveadmin/users.html', context)


@admin_login_required
def admin_enrollments(request):
    # Get all enrollments with related student and course data
    enrollments = Enrollment.objects.select_related('student', 'course').order_by('-enrollment_date')

    # Handle course filter
    course_id = request.GET.get('course')
    if course_id:
        enrollments = enrollments.filter(course_id=course_id)

    # Handle search
    search_query = request.GET.get('search')
    if search_query:
        enrollments = enrollments.filter(
            Q(student__first_name__icontains=search_query) |
            Q(student__last_name__icontains=search_query) |
            Q(student__email__icontains=search_query) |
            Q(course__title__icontains=search_query)
        )

    # Get all courses for the filter dropdown
    courses = Course.objects.all().order_by('title')

    # Calculate statistics
    total_enrollments = enrollments.count()
    completed_enrollments = enrollments.filter(is_completed=True).count()
    completion_rate = (completed_enrollments / total_enrollments * 100) if total_enrollments > 0 else 0

    # Calculate progress for each enrollment
    for enrollment in enrollments:
        if enrollment.is_completed:
            enrollment.progress = 100
        else:
            # Add your progress calculation logic here
            # This is a placeholder - implement your actual progress calculation
            enrollment.progress = 0  # Replace with actual progress calculation

    context = {
        'enrollments': enrollments,
        'courses': courses,
        'total_enrollments': total_enrollments,
        'completed_enrollments': completed_enrollments,
        'completion_rate': round(completion_rate, 1),
        'selected_course': course_id,
        'search_query': search_query
    }

    return render(request, 'digievolveadmin/enrollments.html', context)




@admin_login_required
def admin_reports(request):
    # Calculate total statistics
    total_students = User.objects.filter(is_student=True).count()
    total_courses = Course.objects.count()
    total_enrollments = Enrollment.objects.count()
    total_revenue = Payment.objects.filter(status='completed').aggregate(
        Sum('amount'))['amount__sum'] or 0

    # Get enrollment statistics for the last 30 days
    thirty_days_ago = timezone.now() - timedelta(days=30)
    enrollment_stats = Enrollment.objects.filter(
        enrollment_date__gte=thirty_days_ago
    ).annotate(
        date=TruncDate('enrollment_date')
    ).values('date').annotate(
        count=Count('id')
    ).order_by('date')

    # Format enrollment data for Chart.js
    enrollment_dates = [stat['date'].strftime('%Y-%m-%d') for stat in enrollment_stats]
    enrollment_counts = [stat['count'] for stat in enrollment_stats]

    # Get revenue statistics for the last 30 days
    revenue_stats = Payment.objects.filter(
        status='completed',
        created_at__gte=thirty_days_ago
    ).annotate(
        date=TruncDate('created_at')
    ).values('date').annotate(
        total=Sum('amount')
    ).order_by('date')

    # Format revenue data for Chart.js
    revenue_dates = [stat['date'].strftime('%Y-%m-%d') for stat in revenue_stats]
    revenue_amounts = [float(stat['total']) for stat in revenue_stats]

    # Get course performance data
    courses = Course.objects.annotate(
        enrollment_count=Count('Course_enrollments'),
        completion_rate=models.ExpressionWrapper(
            100.0 * Count('Course_enrollments', filter=Q(Course_enrollments__is_completed=True)) /
            Cast(Count('Course_enrollments'), models.FloatField()),
            output_field=models.FloatField()
        ),
        revenue=Coalesce(
            Sum('Course_payment_enrollments__amount',
                filter=Q(Course_payment_enrollments__status='completed')),
            0,
            output_field=models.DecimalField()
        )
    ).filter(
        enrollment_count__gt=0
    )

    # Get user statistics
    active_users = User.objects.filter(
        is_student=True,
        is_active=True,
        last_login__gte=thirty_days_ago
    ).count()

    inactive_users = User.objects.filter(
        is_student=True,
        is_active=True,
        last_login__lt=thirty_days_ago
    ).count()

    new_users = User.objects.filter(
        is_student=True,
        date_joined__gte=thirty_days_ago
    ).count()

    # Calculate average completion rate
    avg_completion_rate = Enrollment.objects.filter(
        is_completed=True
    ).count() / total_enrollments * 100 if total_enrollments > 0 else 0

    context = {
        # Summary statistics
        'total_students': total_students,
        'total_courses': total_courses,
        'total_enrollments': total_enrollments,
        'total_revenue': total_revenue,
        'avg_completion_rate': round(avg_completion_rate, 1),

        # Enrollment chart data
        'enrollment_dates': enrollment_dates,
        'enrollment_counts': enrollment_counts,

        # Revenue chart data
        'revenue_dates': revenue_dates,
        'revenue_amounts': revenue_amounts,

        # Course performance data
        'courses': courses,

        # User statistics
        'active_users': active_users,
        'inactive_users': inactive_users,
        'new_users': new_users,
    }

    return render(request, 'digievolveadmin/reports.html', context)




@admin_login_required
def admin_revenue(request):
    # Get current date and time
    today = timezone.now()
    current_month = today.strftime('%B %Y')

    # Get all completed payments
    payments = Payment.objects.filter(
        status='completed'
    ).select_related(
        'student', 'course'
    ).order_by('-created_at')

    # Calculate total revenue
    total_revenue = payments.aggregate(
        total=Coalesce(
            Sum(Cast('amount', DecimalField(max_digits=10, decimal_places=2))),
            0,
            output_field=DecimalField(max_digits=10, decimal_places=2)
        )
    )['total']

    # Calculate monthly revenue
    monthly_revenue = payments.filter(
        created_at__month=today.month,
        created_at__year=today.year
    ).aggregate(
        total=Coalesce(
            Sum(Cast('amount', DecimalField(max_digits=10, decimal_places=2))),
            0,
            output_field=DecimalField(max_digits=10, decimal_places=2)
        )
    )['total']

    # Calculate daily revenue
    daily_revenue = payments.filter(
        created_at__date=today.date()
    ).aggregate(
        total=Coalesce(
            Sum(Cast('amount', DecimalField(max_digits=10, decimal_places=2))),
            0,
            output_field=DecimalField(max_digits=10, decimal_places=2)
        )
    )['total']

    # Calculate average transaction amount
    avg_transaction = payments.aggregate(
        avg=Coalesce(
            Avg(Cast('amount', DecimalField(max_digits=10, decimal_places=2))),
            0,
            output_field=DecimalField(max_digits=10, decimal_places=2)
        )
    )['avg']

    # Get monthly revenue trend data
    monthly_stats = payments.annotate(
        month=TruncDate('created_at')
    ).values('month').annotate(
        total=Sum(
            Cast('amount', DecimalField(max_digits=10, decimal_places=2)),
            output_field=DecimalField(max_digits=10, decimal_places=2)
        )
    ).order_by('month')

    monthly_labels = [stat['month'].strftime('%Y-%m-%d') for stat in monthly_stats]
    monthly_data = [float(stat['total']) for stat in monthly_stats]

    # Get revenue by course data
    course_stats = payments.values(
        'course__title'
    ).annotate(
        total=Sum(
            Cast('amount', DecimalField(max_digits=10, decimal_places=2)),
            output_field=DecimalField(max_digits=10, decimal_places=2)
        )
    ).order_by('-total')

    course_labels = [stat['course__title'] for stat in course_stats]
    course_data = [float(stat['total']) for stat in course_stats]

    context = {
        # Summary cards data
        'total_revenue': total_revenue,
        'monthly_revenue': monthly_revenue,
        'daily_revenue': daily_revenue,
        'avg_transaction': avg_transaction,
        'current_month': current_month,
        'today': today,

        # Chart data
        'monthly_labels': json.dumps(monthly_labels),
        'monthly_data': json.dumps(monthly_data),
        'course_labels': json.dumps(course_labels),
        'course_data': json.dumps(course_data),

        # Table data
        'payments': payments,
    }

    return render(request, 'digievolveadmin/revenue.html', context)



@admin_login_required
def payment_detail_api(request, payment_id):
    try:
        payment = Payment.objects.select_related('student', 'course').get(id=payment_id)
        data = {
            'reference': payment.reference,
            'student_name': f"{payment.student.first_name} {payment.student.last_name}",
            'course_title': payment.course.title,
            'amount': float(payment.amount),
            'created_at': payment.created_at.strftime('%B %d, %Y'),
            'status': payment.status
        }
        return JsonResponse(data)
    except Payment.DoesNotExist:
        return JsonResponse({'error': 'Payment not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


        


@admin_login_required
def admin_settings(request):
    if request.method == 'POST':
        # Handle settings update
        # Add your settings update logic here
        messages.success(request, 'Settings updated successfully.')
        return redirect('accounts:admin_settings')

    context = {
        # Add your settings context here
    }
    return render(request, 'digievolveadmin/settings.html', context)



# Add these new views to accounts/views.py

@admin_login_required
def admin_unenroll_student(request, enrollment_id):
    if request.method == 'POST':
        try:
            enrollment = get_object_or_404(Enrollment, id=enrollment_id)
            student_name = enrollment.student.get_full_name()
            course_title = enrollment.course.title

            # Record activity before deletion
            Activity.objects.create(
                user=enrollment.student,
                activity_type='unenrollment',
                description=f"Unenrolled from {course_title}",
                course=enrollment.course
            )

            # Delete the enrollment
            enrollment.delete()

            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': True,
                    'message': f'Successfully unenrolled {student_name} from {course_title}'
                })

            messages.success(request, f'Successfully unenrolled {student_name} from {course_title}')
            return redirect('accounts:admin_enrollments')

        except Exception as e:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': False,
                    'message': f'Error: {str(e)}'
                })

            messages.error(request, f'Error unenrolling student: {str(e)}')
            return redirect('accounts:admin_enrollments')

    return JsonResponse({'success': False, 'message': 'Invalid request method'})




@admin_login_required
def admin_enrollments(request):
    # Get all enrollments with related student and course data
    enrollments = Enrollment.objects.select_related('student', 'course').order_by('-enrollment_date')

    # Handle course filter
    course_id = request.GET.get('course')
    if course_id:
        enrollments = enrollments.filter(course_id=course_id)

    # Handle search
    search_query = request.GET.get('search')
    if search_query:
        enrollments = enrollments.filter(
            Q(student__first_name__icontains=search_query) |
            Q(student__last_name__icontains=search_query) |
            Q(student__email__icontains=search_query) |
            Q(course__title__icontains=search_query)
        )

    # Get all courses for the filter dropdown
    courses = Course.objects.all().order_by('title')

    # Calculate statistics
    total_enrollments = enrollments.count()
    completed_enrollments = enrollments.filter(is_completed=True).count()
    completion_rate = (completed_enrollments / total_enrollments * 100) if total_enrollments > 0 else 0

    context = {
        'enrollments': enrollments,
        'courses': courses,
        'total_enrollments': total_enrollments,
        'completed_enrollments': completed_enrollments,
        'completion_rate': round(completion_rate, 1),
        'selected_course': course_id,
        'search_query': search_query
    }

    return render(request, 'digievolveadmin/enrollments.html', context)


@admin_login_required
def admin_add_enrollment(request):
    if request.method == 'POST':
        student_id = request.POST.get('student')
        course_id = request.POST.get('course')

        try:
            student = User.objects.get(id=student_id, is_student=True)
            course = Course.objects.get(id=course_id)

            # Check if enrollment already exists
            if Enrollment.objects.filter(student=student, course=course).exists():
                messages.error(request, f'{student.full_name} is already enrolled in {course.title}')
                return redirect('accounts:admin_enrollments')

            # Create new enrollment
            enrollment = Enrollment.objects.create(
                student=student,
                course=course,
                enrollment_date=timezone.now()
            )

            # Record activity
            Activity.objects.create(
                user=student,
                activity_type='enrollment',
                description=f"Enrolled in {course.title}",
                course=course
            )

            messages.success(request, f'Successfully enrolled {student.full_name} in {course.title}')

        except (User.DoesNotExist, Course.DoesNotExist) as e:
            messages.error(request, 'Invalid student or course selected')
        except Exception as e:
            messages.error(request, f'Error creating enrollment: {str(e)}')

    # Get all students and courses for the form
    students = User.objects.filter(is_student=True)
    courses = Course.objects.all()

    context = {
        'students': students,
        'courses': courses
    }

    return render(request, 'admin/add_enrollment.html', context)



@login_required
def contact_queries(request):
    # Get your contact queries data
    # Replace with your actual implementation
    contact_queries = Contact.objects.all().order_by('-created_at')

    context = {
        'contact_queries': contact_queries,
    }

    return render(request, 'digievolveadmin/contact/contact_management.html', context)