from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.utils import timezone
from django.urls import reverse
from django.http import JsonResponse
from .models import Course, Certificate, Enrollment, Payment, Module
from .quiz_models import Module, Quiz, Question, Answer, QuizAttempt, QuestionResponse
from accounts.models import User, Activity
import uuid
import json
import requests
from django.conf import settings

from django.template.loader import get_template
from xhtml2pdf import pisa
from io import BytesIO

import os
from django.http import HttpResponse, Http404
from django.template.loader import render_to_string
# from weasyprint import HTML
from .models import Certificate
from django.utils.text import slugify
from django.core.files.storage import default_storage
from django.shortcuts import render, redirect


# Add these imports at the top of your accounts/views.py
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Count, Sum
from datetime import timedelta
from blog.models import BlogPost
from django.db.models import Q
from accounts.views import admin_login_required  # Import the custom decorator
from django.db.models import Max

from django.views.decorators.http import require_POST, require_GET
from django.db import transaction
from django.core.exceptions import PermissionDenied
from .forms import QuizForm  # We'll create this form class


@login_required(login_url='accounts:login')
def enrolled_courses(request):
    enrollments = Enrollment.objects.filter(
        student=request.user
    ).select_related('course')
    return render(request, 'courses/enrolled_courses.html', {'enrollments': enrollments})


@login_required(login_url='accounts:login')
def certificate_list(request):
    # Get the user's certificates
    certificates = Certificate.objects.filter(student=request.user)
    return render(request, 'courses/certificate_list.html', {'certificates': certificates})


@login_required(login_url='accounts:login')
def certificate_detail(request, certificate_id):
    certificate = get_object_or_404(
        Certificate,
        id=certificate_id,
        student=request.user
    )
    return render(request, 'courses/certificate_detail.html', {'certificate': certificate})


@login_required(login_url='accounts:login')
def course_list(request):
    courses = Course.objects.all()
    return render(request, 'courses/list.html', {'courses': courses})


@login_required(login_url='accounts:login')
def course_detail(request, course_slug):
    course = get_object_or_404(Course, slug=course_slug)
    modules = Module.objects.filter(course=course).order_by('order')

    # Check if user is enrolled
    try:
        enrollment = Enrollment.objects.get(student=request.user, course=course)
        is_enrolled = True
        completed_modules = enrollment.completed_modules.split(',') if enrollment.completed_modules else []
        progress = enrollment.progress
    except Enrollment.DoesNotExist:
        enrollment = None
        is_enrolled = False
        completed_modules = []
        progress = 0

    context = {
        'course': course,
        'modules': modules,
        'enrollment': enrollment,
        'is_enrolled': is_enrolled,
        'completed_modules': completed_modules,
        'progress': progress
    }

    return render(request, 'courses/detail.html', context)


@login_required(login_url='accounts:login')
def initiate_payment(request, course_slug):
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid request method'}, status=400)

    try:
        course = get_object_or_404(Course, slug=course_slug)

        # Check if already enrolled
        if Enrollment.objects.filter(student=request.user, course=course).exists():
            return JsonResponse({'error': 'Already enrolled in this course'}, status=400)

        # For free courses, enroll directly
        if course.is_free:
            enrollment = Enrollment.objects.create(
                student=request.user,
                course=course
            )

            # Create activity record
            Activity.objects.create(
                user=request.user,
                activity_type='enrollment',
                description=f"Enrolled in course: {course.title}",
                course=course
            )

            return JsonResponse({
                'success': True,
                'redirect_url': reverse('courses:detail', kwargs={'course_slug': course.slug})
            })

        # Generate unique reference
        reference = f"DIGI-{uuid.uuid4().hex[:8].upper()}"

        # Create pending payment record
        payment = Payment.objects.create(
            student=request.user,
            course=course,
            amount=course.price,
            reference=reference,
            status='pending'
        )

        # Prepare Paystack API request
        url = "https://api.paystack.co/transaction/initialize"
        headers = {
            "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
            "Content-Type": "application/json"
        }

        callback_url = request.build_absolute_uri(
            reverse('courses:verify_payment', kwargs={'reference': reference})
        )

        data = {
            "email": request.user.email,
            "amount": int(course.price * 100),  # Paystack expects amount in kobo
            "currency": "NGN",
            "reference": reference,
            "callback_url": callback_url,
            "metadata": {
                "course_id": course.id,
                "course_title": course.title,
                "student_id": request.user.id
            }
        }

        # Print debug information
        print(f"Paystack Request URL: {url}")
        print(f"Paystack Request Headers: {headers}")
        print(f"Paystack Request Data: {data}")

        response = requests.post(url, headers=headers, data=json.dumps(data))
        response_data = response.json()

        # Print response for debugging
        print(f"Paystack Response Status: {response.status_code}")
        print(f"Paystack Response Data: {response_data}")

        if response.status_code == 200 and response_data['status']:
            # Update payment with authorization URL
            payment.transaction_id = response_data['data']['reference']
            payment.save()

            return JsonResponse({
                'success': True,
                'authorization_url': response_data['data']['authorization_url']
            })
        else:
            payment.status = 'failed'
            payment.save()
            error_message = response_data.get('message', 'Payment initialization failed')
            print(f"Paystack Error: {error_message}")
            return JsonResponse({'error': error_message}, status=400)

    except Exception as e:
        print(f"Exception in initiate_payment: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)


@login_required(login_url='accounts:login')
def verify_payment(request, reference):
    try:
        # Get the payment
        payment = get_object_or_404(Payment, reference=reference)

        # If already processed, redirect to course
        if payment.status == 'completed':
            return redirect('courses:detail', course_slug=payment.course.slug)

        # Verify with Paystack
        url = f"https://api.paystack.co/transaction/verify/{reference}"
        headers = {
            "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}"
        }

        # Print debug information
        print(f"Verify Payment URL: {url}")
        print(f"Verify Payment Headers: {headers}")

        response = requests.get(url, headers=headers)
        response_data = response.json()

        # Print response for debugging
        print(f"Verify Payment Response Status: {response.status_code}")
        print(f"Verify Payment Response Data: {response_data}")

        if response.status_code == 200 and response_data['status'] and response_data['data']['status'] == 'success':
            # Update payment status
            payment.status = 'completed'
            payment.payment_method = response_data['data'].get('channel', 'unknown')
            payment.save()

            # Create enrollment
            student = payment.student
            course = payment.course

            enrollment, created = Enrollment.objects.get_or_create(
                student=student,
                course=course,
                defaults={
                    'enrollment_date': timezone.now()
                }
            )

            if created:
                # Create activity record
                Activity.objects.create(
                    user=student,
                    activity_type='enrollment',
                    description=f"Enrolled in course: {course.title}",
                    course=course
                )

            messages.success(request, f"Payment successful! You are now enrolled in {course.title}.")
            return redirect('courses:detail', course_slug=course.slug)
        else:
            payment.status = 'failed'
            payment.save()
            messages.error(request, "Payment verification failed. Please contact support.")
            return redirect('courses:detail', course_slug=payment.course.slug)

    except Exception as e:
        print(f"Exception in verify_payment: {str(e)}")
        if 'payment' in locals():
            payment.status = 'failed'
            payment.save()
            messages.error(request, f"An error occurred: {str(e)}")
            return redirect('courses:detail', course_slug=payment.course.slug)
        else:
            messages.error(request, f"An error occurred: {str(e)}")
            return redirect('courses:course_list')


@login_required(login_url='accounts:login')
def module_detail(request, course_slug, module_id):
    course = get_object_or_404(Course, slug=course_slug)
    module = get_object_or_404(Module, id=module_id, course=course)
    enrollment = get_object_or_404(Enrollment, student=request.user, course=course)

    # Get quizzes for this module
    quizzes = Quiz.objects.filter(module=module)
    has_quiz = quizzes.exists()

    # Check quiz completion if module has quizzes
    quiz_completed = False
    if has_quiz:
        quiz_completed = QuizAttempt.objects.filter(
            student=request.user,
            quiz__module=module,
            is_passed=True
        ).exists()

    # Get completion status
    completed_modules = enrollment.completed_modules.split(',') if enrollment.completed_modules else []
    is_completed = str(module.id) in completed_modules

    if request.method == 'POST' and request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        if request.POST.get('mark_complete'):
            # Check if module can be marked as complete
            can_complete = not has_quiz or quiz_completed

            if can_complete and not is_completed:
                # Mark module as completed
                if enrollment.completed_modules:
                    completed_modules = enrollment.completed_modules.split(',')
                    if str(module.id) not in completed_modules:
                        completed_modules.append(str(module.id))
                        enrollment.completed_modules = ','.join(completed_modules)
                else:
                    enrollment.completed_modules = str(module.id)

                enrollment.last_accessed = timezone.now()
                enrollment.save()

                # Create activity record
                Activity.objects.create(
                    user=request.user,
                    activity_type='completion',
                    description=f"Completed module: {module.title}",
                    course=course
                )

                # Check if course is completed
                all_modules = set(str(m.id) for m in Module.objects.filter(course=course))
                completed_set = set(enrollment.completed_modules.split(','))

                if all_modules.issubset(completed_set) and not enrollment.is_completed:
                    enrollment.is_completed = True
                    enrollment.completion_date = timezone.now()
                    enrollment.save()

                    # Generate certificate
                    Certificate.objects.create(
                        student=request.user,
                        course=course,
                        issued_date=timezone.now()
                    )

                    # Create certificate activity
                    Activity.objects.create(
                        user=request.user,
                        activity_type='certificate',
                        description=f"Earned certificate for: {course.title}",
                        course=course
                    )

                return JsonResponse({
                    'success': True,
                    'is_completed': True
                })

        return JsonResponse({'success': False})

    # Get next and previous modules
    next_module = Module.objects.filter(course=course, order__gt=module.order).first()
    prev_module = Module.objects.filter(course=course, order__lt=module.order).last()

    context = {
        'course': course,
        'module': module,
        'is_completed': is_completed,
        'quizzes': quizzes,
        'has_quiz': has_quiz,
        'quiz_completed': quiz_completed,
        'next_module': next_module,
        'prev_module': prev_module,
    }

    return render(request, 'courses/module_detail.html', context)

    


@login_required(login_url='accounts:login')
def quiz_list(request, course_slug, module_id):
    course = get_object_or_404(Course, slug=course_slug)
    module = get_object_or_404(Module, id=module_id, course=course)
    quizzes = Quiz.objects.filter(module=module)

    quiz_attempts = {
        quiz.id: QuizAttempt.objects.filter(
            student=request.user,
            quiz=quiz
        ).order_by('-started_at').first()
        for quiz in quizzes
    }

    context = {
        'course': course,
        'module': module,
        'quizzes': quizzes,
        'quiz_attempts': quiz_attempts,
    }

    return render(request, 'courses/quiz_list.html', context)


@login_required(login_url='accounts:login')
def take_quiz(request, quiz_id):
    quiz = get_object_or_404(Quiz, id=quiz_id)

    # Check if there's an incomplete attempt
    attempt = QuizAttempt.objects.filter(
        student=request.user,
        quiz=quiz,
        completed_at__isnull=True
    ).first()

    if not attempt:
        # Create a new attempt
        attempt = QuizAttempt.objects.create(
            student=request.user,
            quiz=quiz
        )

    if request.method == 'POST':
        # Process quiz submission
        questions = Question.objects.filter(quiz=quiz)
        score = 0
        total_points = sum(q.points for q in questions)

        for question in questions:
            if question.question_type == 'multiple_choice':
                answer_id = request.POST.get(f'question_{question.id}')
                if answer_id:
                    selected_answer = Answer.objects.get(id=answer_id)
                    is_correct = selected_answer.is_correct

                    QuestionResponse.objects.create(
                        attempt=attempt,
                        question=question,
                        selected_answer=selected_answer,
                        is_correct=is_correct
                    )

                    if is_correct:
                        score += question.points

            elif question.question_type == 'true_false':
                answer_id = request.POST.get(f'question_{question.id}')
                if answer_id:
                    selected_answer = Answer.objects.get(id=answer_id)
                    is_correct = selected_answer.is_correct

                    QuestionResponse.objects.create(
                        attempt=attempt,
                        question=question,
                        selected_answer=selected_answer,
                        is_correct=is_correct
                    )

                    if is_correct:
                        score += question.points

            elif question.question_type == 'short_answer':
                text_response = request.POST.get(f'question_{question.id}')
                # For short answers, instructor will need to grade manually
                QuestionResponse.objects.create(
                    attempt=attempt,
                    question=question,
                    text_response=text_response
                )

        # Calculate percentage score
        percentage_score = (score / total_points) * 100 if total_points > 0 else 0

        # Update attempt
        attempt.score = percentage_score
        attempt.is_passed = percentage_score >= quiz.passing_score
        attempt.completed_at = timezone.now()
        attempt.save()

        # Update module completion if passed
        if attempt.is_passed:
            enrollment = Enrollment.objects.get(
                student=request.user,
                course=quiz.module.course
            )

            # Add this module to completed modules if not already there
            if str(quiz.module.id) not in enrollment.completed_modules.split(',') if enrollment.completed_modules else []:
                if enrollment.completed_modules:
                    enrollment.completed_modules += f",{quiz.module.id}"
                else:
                    enrollment.completed_modules = str(quiz.module.id)

                enrollment.save()

                # Create activity record
                Activity.objects.create(
                    user=request.user,
                    activity_type='completion',
                    description=f"Completed module: {quiz.module.title}",
                    course=quiz.module.course
                )

                # Check if all modules are completed
                all_modules = Module.objects.filter(course=quiz.module.course)
                completed_modules = enrollment.completed_modules.split(',') if enrollment.completed_modules else []
                all_completed = all(str(m.id) in completed_modules for m in all_modules)

                if all_completed and not enrollment.is_completed:
                    enrollment.is_completed = True
                    enrollment.completion_date = timezone.now()
                    enrollment.save()

                    # Generate certificate
                    Certificate.objects.create(
                        student=request.user,
                        course=quiz.module.course,
                        issued_date=timezone.now()
                    )

                    # Create activity record
                    Activity.objects.create(
                        user=request.user,
                        activity_type='certificate',
                        description=f"Earned certificate for: {quiz.module.course.title}",
                        course=quiz.module.course
                    )

        return redirect('courses:quiz_result', attempt_id=attempt.id)

    questions = Question.objects.filter(quiz=quiz).order_by('order')

    context = {
        'quiz': quiz,
        'questions': questions,
        'attempt': attempt,
    }

    return render(request, 'courses/take_quiz.html', context)


@login_required(login_url='accounts:login')
def quiz_result(request, attempt_id):
    attempt = get_object_or_404(QuizAttempt, id=attempt_id)

    # Ensure the user can only see their own results
    if attempt.student != request.user:
        return redirect('accounts:dashboard')

    responses = QuestionResponse.objects.filter(attempt=attempt)

    context = {
        'attempt': attempt,
        'responses': responses,
        'quiz': attempt.quiz,
        'module': attempt.quiz.module,
        'course': attempt.quiz.module.course,
    }

    return render(request, 'courses/quiz_result.html', context)


def public_certificate_view(request, uuid):
    """View for publicly sharing certificates"""
    certificate = get_object_or_404(Certificate, uuid=uuid)

    # Handle download request
    if request.GET.get('download') == 'true':
        # Get the template
        template = get_template('courses/pdf_certificate.html')

        # Create context with certificate and additional data
        context = {
            'certificate': certificate,
            'verification_url': request.build_absolute_uri(),
            'logo_url': request.build_absolute_uri('/static/img/logo.png'),  # Adjust path as needed
        }

        # Render the template
        html = template.render(context)

        # Create a PDF
        result = BytesIO()
        pdf = pisa.pisaDocument(
            BytesIO(html.encode("UTF-8")),
            result,
            encoding='UTF-8'
        )

        # Check if PDF generation was successful
        if not pdf.err:
            # Create HTTP response with PDF
            response = HttpResponse(result.getvalue(), content_type='application/pdf')
            filename = f"certificate_{certificate.certificate_number}.pdf"
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            return response
        else:
            # If PDF generation failed, return an error page
            return HttpResponse("Error generating PDF", status=500)

    # If not a download request, render the normal certificate page
    return render(request, 'courses/public_certificate.html', {
        'certificate': certificate
    })


# Replace the WeasyPrint-based function with one that uses xhtml2pdf
def download_certificate_pdf(request, uuid):
    """Generate and download a PDF version of the certificate using xhtml2pdf."""
    certificate = get_object_or_404(Certificate, uuid=uuid)

    # Get the absolute URL for verification
    verification_url = request.build_absolute_uri(
        reverse('courses:public_certificate', kwargs={'uuid': certificate.uuid})
    )

    # Get the logo URL
    logo_url = request.build_absolute_uri('/static/img/logo.png')  # Adjust the path as necessary

    # Get the template
    template = get_template('courses/pdf_certificate.html')

    # Create context with certificate and additional data
    context = {
        'certificate': certificate,
        'verification_url': verification_url,
        'logo_url': logo_url,
    }

    # Render the template
    html = template.render(context)

    # Create a PDF
    result = BytesIO()
    pdf = pisa.pisaDocument(
        BytesIO(html.encode("UTF-8")),
        result,
        encoding='UTF-8'
    )

    # Check if PDF generation was successful
    if not pdf.err:
        # Create HTTP response with PDF
        response = HttpResponse(result.getvalue(), content_type='application/pdf')
        filename = f"certificate_{certificate.certificate_number}.pdf"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response
    else:
        # If PDF generation failed, return an error page
        return HttpResponse("Error generating PDF", status=500)


# Add these to your existing courses/views.py

# courses/views.py

@admin_login_required
def admin_course_list(request):
    try:
        # Get all courses ordered by creation date
        courses = Course.objects.all().order_by('-created_at')

        # Debug print
        print(f"Number of courses found: {courses.count()}")

        # Calculate student count for each course
        for course in courses:
            course.student_count = Enrollment.objects.filter(course=course).count()
            print(f"Course: {course.title}, Students: {course.student_count}")

        context = {
            'courses': courses,
            'page_title': 'Course Management'
        }
        return render(request, 'digievolveadmin/courses/list.html', context)
    except Exception as e:
        print(f"Error in admin_course_list: {str(e)}")
        messages.error(request, f'Error loading courses: {str(e)}')
        context = {
            'courses': [],
            'page_title': 'Course Management'
        }
        return render(request, 'digievolveadmin/courses/list.html', context)


@admin_login_required
def admin_add_course(request):
    if request.method == 'POST':
        try:
            # Get form data
            title = request.POST.get('title')
            description = request.POST.get('description')
            short_description = request.POST.get('short_description')
            price = request.POST.get('price', 0)
            duration = request.POST.get('duration')
            is_free = request.POST.get('is_free') == 'on'
            is_published = request.POST.get('is_published') == 'on'
            level = request.POST.get('level', 'beginner')

            # Generate slug
            base_slug = slugify(title)
            slug = base_slug
            counter = 1

            # Ensure slug uniqueness
            while Course.objects.filter(slug=slug).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1

            # Create course
            course = Course.objects.create(
                title=title,
                slug=slug,
                description=description,
                short_description=short_description,
                price=0 if is_free else price,
                duration=duration,
                is_free=is_free,
                level=level  # Now this will work
            )

            # Handle image upload
            if 'thumbnail' in request.FILES:
                image_file = request.FILES['thumbnail']
                # Generate unique filename
                ext = image_file.name.split('.')[-1]
                filename = f"courses/{uuid.uuid4()}.{ext}"
                # Save file
                course.image.save(filename, image_file, save=True)

            messages.success(request, 'Course created successfully.')
            return redirect('courses:admin_course_list')

        except Exception as e:
            messages.error(request, f'Error creating course: {str(e)}')
            return redirect('courses:admin_add_course')

    context = {
        'page_title': 'Add New Course',
        'levels': ['beginner', 'intermediate', 'advanced']
    }
    return render(request, 'digievolveadmin/courses/add.html', context)


@admin_login_required
def admin_modules(request):
    # Get all modules grouped by course
    modules = Module.objects.select_related('course').all().order_by('course', 'order')

    # Group modules by course
    courses_modules = {}
    for module in modules:
        if module.course not in courses_modules:
            courses_modules[module.course] = []
        courses_modules[module.course].append(module)

    context = {
        'courses_modules': courses_modules,
        'page_title': 'Module Management'
    }
    return render(request, 'digievolveadmin/courses/modules.html', context)


@admin_login_required
def admin_quizzes(request):
    # Get all quizzes with related modules and courses
    quizzes = Quiz.objects.select_related('module', 'module__course').all()

    context = {
        'quizzes': quizzes,
        'page_title': 'Quiz Management'
    }
    return render(request, 'digievolveadmin/courses/quizzes.html', context)


# courses/views.py

# courses/views.py

@admin_login_required
def admin_course_edit(request, course_id):
    try:
        course = Course.objects.get(id=course_id)
    except Course.DoesNotExist:
        messages.error(request, 'Course not found.')
        return redirect('courses:admin_course_list')

    if request.method == 'POST':
        try:
            # Get form data
            course.title = request.POST.get('title')
            course.description = request.POST.get('description')
            course.short_description = request.POST.get('short_description')
            course.price = request.POST.get('price', 0)
            course.duration = request.POST.get('duration')
            course.is_free = request.POST.get('is_free') == 'on'
            course.level = request.POST.get('level', 'beginner')

            # Handle image upload
            if 'thumbnail' in request.FILES:
                image_file = request.FILES['thumbnail']
                # Generate unique filename
                ext = image_file.name.split('.')[-1]
                filename = f"courses/{uuid.uuid4()}.{ext}"
                # Save file
                course.image.save(filename, image_file, save=True)

            course.save()
            messages.success(request, 'Course updated successfully.')
            return redirect('courses:admin_course_list')

        except Exception as e:
            messages.error(request, f'Error updating course: {str(e)}')
            return redirect('courses:admin_course_edit', course_id=course_id)

    context = {
        'page_title': 'Edit Course',
        'course': course,
        'levels': ['beginner', 'intermediate', 'advanced']
    }
    return render(request, 'digievolveadmin/courses/edit.html', context)


@admin_login_required
def admin_course_modules(request, course_id):  # This parameter name must match the URL pattern
    course = get_object_or_404(Course, id=course_id)
    modules = Module.objects.filter(course=course).order_by('order')

    context = {
        'course': course,
        'modules': modules,
        'page_title': f'Modules - {course.title}'
    }
    return render(request, 'digievolveadmin/courses/modules/list.html', context)


@admin_login_required
def admin_add_module(request, course_id):
    course = get_object_or_404(Course, id=course_id)

    if request.method == 'POST':
        try:
            max_order = Module.objects.filter(course=course).aggregate(Max('order'))['order__max'] or 0

            module = Module.objects.create(
                course=course,
                title=request.POST.get('title'),
                description=request.POST.get('description'),
                content=request.POST.get('content', ''),
                video_url=request.POST.get('video_url'),
                duration=request.POST.get('duration', 0),
                order=max_order + 1,
                has_quiz=request.POST.get('has_quiz') == 'on'
            )

            messages.success(request, 'Module added successfully.')
            return redirect('courses:admin_course_modules', course_id=course.id)

        except Exception as e:
            messages.error(request, f'Error adding module: {str(e)}')

    context = {
        'course': course,
        'page_title': f'Add Module - {course.title}'
    }
    return render(request, 'digievolveadmin/courses/modules/add.html', context)


@admin_login_required
def admin_edit_module(request, course_id, module_id):
    course = get_object_or_404(Course, id=course_id)
    module = get_object_or_404(Module, id=module_id, course=course)

    if request.method == 'POST':
        try:
            module.title = request.POST.get('title')
            module.description = request.POST.get('description')
            module.content = request.POST.get('content', '')
            module.video_url = request.POST.get('video_url')
            module.duration = request.POST.get('duration', 0)
            module.has_quiz = request.POST.get('has_quiz') == 'on'
            module.save()

            messages.success(request, 'Module updated successfully.')
            return redirect('courses:admin_course_modules', course_id=course.id)

        except Exception as e:
            messages.error(request, f'Error updating module: {str(e)}')

    context = {
        'course': course,
        'module': module,
        'page_title': f'Edit Module - {module.title}'
    }
    return render(request, 'digievolveadmin/courses/modules/edit.html', context)


@admin_login_required
def admin_delete_module(request, course_id, module_id):
    course = get_object_or_404(Course, id=course_id)
    module = get_object_or_404(Module, id=module_id, course=course)

    if request.method == 'POST':
        try:
            module.delete()
            messages.success(request, 'Module deleted successfully.')
        except Exception as e:
            messages.error(request, f'Error deleting module: {str(e)}')

    return redirect('courses:admin_course_modules', course_id=course.id)


@admin_login_required
def admin_course_delete(request, course_id):  # Changed from slug to course_id
    if request.method == 'POST':
        course = get_object_or_404(Course, id=course_id)  # Changed from slug to id
        try:
            course.delete()
            messages.success(request, 'Course deleted successfully.')
        except Exception as e:
            messages.error(request, f'Error deleting course: {str(e)}')
    return redirect('courses:admin_course_list')


@admin_login_required
def admin_module_quiz(request, course_id, module_id):
    course = get_object_or_404(Course, id=course_id)
    module = get_object_or_404(Module, id=module_id, course=course)

    # Get or create quiz for the module
    quiz, created = Quiz.objects.get_or_create(
        module=module,
        defaults={
            'title': f'Quiz for {module.title}',
            'description': f'Assessment for {module.title}',
        }
    )

    questions = quiz.questions.all().prefetch_related('answers')

    context = {
        'course': course,
        'module': module,
        'quiz': quiz,
        'questions': questions,
        'page_title': f'Quiz - {module.title}'
    }
    return render(request, 'digievolveadmin/courses/modules/quiz.html', context)


@admin_login_required
def admin_reorder_modules(request, course_id):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid method'})

    try:
        data = json.loads(request.body)
        module_order = data.get('module_order', [])

        # Update module orders
        with transaction.atomic():
            for index, module_id in enumerate(module_order, start=1):
                Module.objects.filter(
                    id=module_id,
                    course_id=course_id
                ).update(order=index)

        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@admin_login_required
@require_POST
def admin_add_question(request, course_id, module_id):
    course = get_object_or_404(Course, id=course_id)
    module = get_object_or_404(Module, id=module_id, course=course)
    quiz = get_object_or_404(Quiz, module=module)

    try:
        with transaction.atomic():
            # Create question
            question = Question.objects.create(
                quiz=quiz,
                text=request.POST.get('question_text'),
                question_type='multiple_choice',
                order=quiz.questions.count() + 1
            )

            # Create options
            options = request.POST.getlist('options[]')
            correct_option = int(request.POST.get('correct_option', 0))

            for i, option_text in enumerate(options):
                Answer.objects.create(
                    question=question,
                    text=option_text,
                    is_correct=(i == correct_option)
                )

        messages.success(request, 'Question added successfully.')
        return redirect('courses:admin_module_quiz', course_id=course_id, module_id=module_id)

    except Exception as e:
        messages.error(request, f'Error adding question: {str(e)}')
        return redirect('courses:admin_module_quiz', course_id=course_id, module_id=module_id)


@admin_login_required
@require_POST
def admin_edit_question(request, course_id=None, module_id=None, quiz_id=None, question_id=None):
    """
    Universal view that handles question editing for both module-based and direct quiz-based questions
    """
    print(f"Edit question request received with params: course_id={course_id}, module_id={module_id}, quiz_id={quiz_id}, question_id={question_id}")
    print(f"POST data: {request.POST}")

    try:
        with transaction.atomic():
            # Handle module-based questions (existing functionality)
            if course_id and module_id:
                course = get_object_or_404(Course, id=course_id)
                module = get_object_or_404(Module, id=module_id, course=course)
                question_id = request.POST.get('question_id')
                print(f"Looking for question with ID: {question_id} in module: {module.id}")
                question = get_object_or_404(Question, id=question_id, quiz__module=module)

                # Update question text
                question.text = request.POST.get('question_text')
                question.save()

                # Update options
                question.answers.all().delete()
                options = request.POST.getlist('options[]')
                correct_option = int(request.POST.get('correct_option', 0))

                print(f"Options: {options}, Correct option: {correct_option}")

                for i, option_text in enumerate(options):
                    Answer.objects.create(
                        question=question,
                        text=option_text,
                        is_correct=(i == correct_option)
                    )

                messages.success(request, 'Question updated successfully.')
                return redirect('courses:admin_module_quiz', course_id=course_id, module_id=module_id)

            # Handle direct quiz-based questions (new functionality)
            elif quiz_id and question_id:
                print(f"Processing direct quiz-based question edit")
                quiz = get_object_or_404(Quiz, id=quiz_id)
                question = get_object_or_404(Question, id=question_id, quiz=quiz)

                # Update question details - FIXED: Use question_text instead of text
                question.text = request.POST.get('question_text')
                question.question_type = 'multiple_choice'  # Default to multiple choice
                question.points = 1  # Default to 1 point
                question.save()

                # Update answers - FIXED: Use options[] instead of answers[]
                question.answers.all().delete()
                options = request.POST.getlist('options[]')
                correct_option = int(request.POST.get('correct_option', 0))

                print(f"Options: {options}, Correct option: {correct_option}")

                for i, option_text in enumerate(options):
                    if option_text.strip():
                        Answer.objects.create(
                            question=question,
                            text=option_text.strip(),
                            is_correct=(i == correct_option)
                        )

                return JsonResponse({
                    'success': True,
                    'message': 'Question updated successfully'
                })

            else:
                raise ValueError("Invalid parameters provided")

    except Exception as e:
        print(f"Error in admin_edit_question: {str(e)}")
        if course_id and module_id:
            messages.error(request, f'Error updating question: {str(e)}')
            return redirect('courses:admin_module_quiz', course_id=course_id, module_id=module_id)
        else:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=400)




@admin_login_required
def admin_delete_question(request, course_id, module_id, question_id):
    course = get_object_or_404(Course, id=course_id)
    module = get_object_or_404(Module, id=module_id, course=course)
    question = get_object_or_404(Question, id=question_id, quiz__module=module)

    try:
        question.delete()
        messages.success(request, 'Question deleted successfully.')
    except Exception as e:
        messages.error(request, f'Error deleting question: {str(e)}')

    return redirect('courses:admin_module_quiz', course_id=course_id, module_id=module_id)


@admin_login_required
def admin_get_question(request, course_id=None, module_id=None):
    """
    Flexible view that handles question retrieval for both module-based
    and direct quiz-based questions
    """
    # If course_id and module_id are provided, use the module-based approach
    if course_id and module_id:
        course = get_object_or_404(Course, id=course_id)
        module = get_object_or_404(Module, id=module_id, course=course)
        question = get_object_or_404(Question,
                                   id=request.GET.get('question_id'),
                                   quiz__module=module)
    # Otherwise, use direct quiz-based approach
    else:
        question_id = request.GET.get('id') or request.GET.get('question_id')
        question = get_object_or_404(Question, id=question_id)

    # Common response data structure that includes all necessary fields
    data = {
        'id': question.id,
        'text': question.text,
        'question_type': question.question_type,
        # Include both 'options' and 'answers' keys for backward compatibility
        'options': [
            {
                'text': answer.text,
                'is_correct': answer.is_correct
            }
            for answer in question.answers.all()
        ],
        'answers': [
            {
                'id': answer.id,
                'text': answer.text,
                'is_correct': answer.is_correct
            }
            for answer in question.answers.all()
        ]
    }

    return JsonResponse(data)


@admin_login_required
@require_POST
def admin_update_quiz_settings(request, course_id, module_id):
    course = get_object_or_404(Course, id=course_id)
    module = get_object_or_404(Module, id=module_id, course=course)
    quiz = get_object_or_404(Quiz, module=module)

    try:
        quiz.passing_score = int(request.POST.get('passing_score', 70))
        quiz.time_limit = int(request.POST.get('time_limit', 30))
        quiz.save()

        messages.success(request, 'Quiz settings updated successfully.')
    except Exception as e:
        messages.error(request, f'Error updating quiz settings: {str(e)}')

    return redirect('courses:admin_module_quiz', course_id=course_id, module_id=module_id)


@admin_login_required
def admin_course_quizzes(request):
    courses = Course.objects.all()
    quizzes = Quiz.objects.select_related('module__course').all()

    context = {
        'courses': courses,
        'quizzes': quizzes,
        'page_title': 'Course Quizzes'
    }
    return render(request, 'digievolveadmin/courses/quizzes.html', context)


@admin_login_required
def admin_quiz_settings(request, quiz_id):
    quiz = get_object_or_404(Quiz, id=quiz_id)

    if request.method == 'POST':
        try:
            passing_score = int(request.POST.get('passing_score', 0))
            time_limit = int(request.POST.get('time_limit', 0))

            quiz.passing_score = passing_score
            quiz.time_limit = time_limit
            quiz.save()

            messages.success(request, 'Quiz settings updated successfully.')
        except Exception as e:
            messages.error(request, f'Error updating quiz settings: {str(e)}')

        return redirect('courses:admin_quiz_settings', quiz_id=quiz.id)

    context = {
        'quiz': quiz,
        'page_title': f'Quiz Settings - {quiz.title}'
    }
    return render(request, 'digievolveadmin/courses/quiz_settings.html', context)


@admin_login_required
def admin_quiz_questions(request, quiz_id):
    quiz = get_object_or_404(Quiz, id=quiz_id)
    questions = quiz.questions.all().prefetch_related('answers')

    context = {
        'quiz': quiz,
        'questions': questions,
        'page_title': f'Quiz Questions - {quiz.title}'
    }
    return render(request, 'digievolveadmin/courses/quizzes.html', context)


@admin_login_required
def admin_quiz_results(request, quiz_id):
    quiz = get_object_or_404(Quiz, id=quiz_id)
    attempts = QuizAttempt.objects.filter(quiz=quiz)

    # Calculate statistics
    total_attempts = attempts.count()
    passed_attempts = attempts.filter(is_passed=True).count()
    failed_attempts = attempts.filter(is_passed=False, completed_at__isnull=False).count()

    context = {
        'quiz': quiz,
        'attempts': attempts,
        'total_attempts': total_attempts,
        'passed_attempts': passed_attempts,
        'failed_attempts': failed_attempts,
    }

    return render(request, 'digievolveadmin/courses/quiz_results.html', context)


@admin_login_required
def admin_quiz_attempt_detail(request, quiz_id, attempt_id):
    quiz = get_object_or_404(Quiz, id=quiz_id)
    attempt = get_object_or_404(QuizAttempt, id=attempt_id, quiz=quiz)
    responses = attempt.responses.select_related('question', 'selected_answer').all()

    context = {
        'quiz': quiz,
        'attempt': attempt,
        'responses': responses,
        'page_title': f'Attempt Details - {quiz.title}'
    }
    return render(request, 'digievolveadmin/courses/quiz_attempt_detail.html', context)


@admin_login_required
def admin_edit_quiz(request, quiz_id):
    quiz = get_object_or_404(Quiz, id=quiz_id)

    if request.method == 'POST':
        form = QuizForm(request.POST, instance=quiz)
        if form.is_valid():
            try:
                form.save()
                messages.success(request, 'Quiz updated successfully.')
                return redirect('courses:admin_quizzes')
            except Exception as e:
                messages.error(request, f'Error updating quiz: {str(e)}')
    else:
        form = QuizForm(instance=quiz)

    context = {
        'form': form,
        'quiz': quiz,
        'page_title': f'Edit Quiz - {quiz.title}'
    }
    return render(request, 'digievolveadmin/courses/quiz_form.html', context)


@admin_login_required
def admin_delete_quiz(request, quiz_id):
    quiz = get_object_or_404(Quiz, id=quiz_id)

    if request.method == 'POST':
        try:
            module = quiz.module  # Store the module reference before deletion
            quiz.delete()
            messages.success(request, 'Quiz deleted successfully.')

            # Redirect back to the module's quiz section
            return redirect(reverse('courses:admin_module_quiz', kwargs={
                'course_id': module.course.id,
                'module_id': module.id
            }))
        except Exception as e:
            messages.error(request, f'Error deleting quiz: {str(e)}')
            return redirect('courses:admin_quizzes')

    # If it's a GET request, show confirmation page
    context = {
        'quiz': quiz,
        'page_title': f'Delete Quiz - {quiz.title}'
    }
    return render(request, 'digievolveadmin/courses/quiz_delete.html', context)


    