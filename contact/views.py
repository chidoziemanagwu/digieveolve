import json
from django.shortcuts import render
from django.contrib import messages
from .models import Contact
from django.utils import timezone
from datetime import timedelta
from django.db.models import Count
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail
from django.conf import settings
from django.views.decorators.http import require_http_methods
from django.shortcuts import get_object_or_404



def contact_view(request):
    """Contact form view"""
    print(f"\n\n==== CONTACT VIEW: {request.method} ====")
    print(f"Path: {request.path}")

    if request.method == 'POST':
        print("POST Data received:", request.POST)
        
        try:
            # Get form data
            first_name = request.POST.get('first_name', '').strip()
            last_name = request.POST.get('last_name', '').strip()
            email = request.POST.get('email', '').strip()
            subject = request.POST.get('subject', '').strip()
            message = request.POST.get('message', '').strip()

            print(f"Processing form data: {first_name=}, {last_name=}, {email=}, {subject=}")

            # Validate required fields
            if not all([first_name, last_name, email, subject, message]):
                missing = []
                if not first_name: missing.append("First name")
                if not last_name: missing.append("Last name")
                if not email: missing.append("Email")
                if not subject: missing.append("Subject")
                if not message: missing.append("Message")
                
                messages.error(request, f"Please fill in all required fields: {', '.join(missing)}")
                return render(request, 'contact/contact.html')

            # Save to database
            contact = Contact.objects.create(
                first_name=first_name,
                last_name=last_name,
                email=email,
                subject=subject,
                message=message,
                status='pending'
            )

            print(f"Contact saved successfully with ID: {contact.id}")

            # Send email notification (optional)
            try:
                admin_email = getattr(settings, 'ADMIN_EMAIL', 'admin@example.com')
                email_body = f"""
                New Contact Form Submission:
                
                Name: {first_name} {last_name}
                Email: {email}
                Subject: {subject}
                Message: {message}
                """
                
                send_mail(
                    f"New Contact Form: {subject}",
                    email_body,
                    email,
                    [admin_email],
                    fail_silently=True,
                )
            except Exception as email_error:
                print(f"Email sending failed: {email_error}")
                # Continue even if email fails

            # Add success message
            messages.success(request, "Thank you! Your message has been sent successfully.")
            
            # Render the same page with success message
            return render(request, 'contact/contact.html')

        except Exception as e:
            print(f"Error saving contact: {str(e)}")
            messages.error(request, f"An error occurred: {str(e)}")
            return render(request, 'contact/contact.html')

    # For GET requests
    return render(request, 'contact/contact.html')

# Your other views remain unchanged
def debug_contacts(request):
    """View to check if contacts are being saved correctly"""
    contacts = Contact.objects.all().order_by('-created_at')[:20]
    return render(request, 'digievolveadmin/contact/debug_contacts.html', {'contacts': contacts})

@login_required
def contact_management(request):
    # Get all queries ordered by creation date (newest first)
    queries = Contact.objects.all().order_by('-created_at')

    # Calculate statistics
    total_queries = queries.count()
    pending_queries = queries.filter(status='pending').count()
    in_progress_queries = queries.filter(status='in_progress').count()
    resolved_queries = queries.filter(status='resolved').count()
    spam_queries = queries.filter(status='spam').count()

    # Get timeline data (last 30 days)
    thirty_days_ago = timezone.now() - timedelta(days=30)
    timeline_query = (
        Contact.objects
        .filter(created_at__gte=thirty_days_ago)
        .extra({'date': "DATE(created_at)"})
        .values('date')
        .annotate(count=Count('id'))
        .order_by('date')
    )

    # Format timeline data for Chart.js
    timeline_data = [
        {
            'date': item['date'].strftime('%Y-%m-%d') if isinstance(item['date'], timezone.datetime) else item['date'],
            'count': item['count']
        }
        for item in timeline_query
    ]

    # Get status distribution
    status_query = (
        Contact.objects
        .values('status')
        .annotate(count=Count('id'))
        .order_by('status')
    )

    # Format status data for Chart.js
    status_mapping = {
        'pending': 'Pending',
        'in_progress': 'In Progress',
        'resolved': 'Resolved',
        'spam': 'Spam'
    }

    status_data = [
        {
            'status': status_mapping.get(item['status'], item['status'].capitalize()),
            'count': item['count']
        }
        for item in status_query
    ]

    # Fill in missing dates in timeline data
    if timeline_data:
        date_range = []
        start_date = thirty_days_ago.date()
        end_date = timezone.now().date()
        current_date = start_date

        while current_date <= end_date:
            date_str = current_date.strftime('%Y-%m-%d')
            # Find if we have data for this date
            existing_data = next(
                (item for item in timeline_data if item['date'] == date_str),
                None
            )

            if existing_data:
                date_range.append(existing_data)
            else:
                date_range.append({
                    'date': date_str,
                    'count': 0
                })

            current_date += timedelta(days=1)

        timeline_data = date_range

    # Prepare table data
    table_data = []
    for query in queries:
        table_data.append({
            'id': query.id,
            'created_at': query.created_at.strftime('%b %d, %Y'),
            'name': f"{query.first_name} {query.last_name}",
            'email': query.email,
            'subject': query.subject,
            'status': query.get_status_display(),
            'status_class': {
                'pending': 'bg-yellow-100 text-yellow-800',
                'in_progress': 'bg-blue-100 text-blue-800',
                'resolved': 'bg-green-100 text-green-800',
                'spam': 'bg-red-100 text-red-800'
            }.get(query.status, '')
        })

    context = {
        'queries': queries,
        'total_queries': total_queries,
        'pending_queries': pending_queries,
        'in_progress_queries': in_progress_queries,
        'resolved_queries': resolved_queries,
        'spam_queries': spam_queries,
        'timeline_data': timeline_data,
        'status_data': status_data,
        'table_data': table_data
    }

    return render(request, 'digievolveadmin/contact/contact_management.html', context)


@login_required
@require_http_methods(["GET"])
def get_query_details(request, query_id):
    try:
        query = Contact.objects.get(id=query_id)
        data = {
            'id': query.id,
            'first_name': query.first_name,
            'last_name': query.last_name,
            'email': query.email,
            'subject': query.subject,
            'message': query.message,
            'status': query.status,
            'admin_notes': query.admin_notes,
            'created_at': query.created_at.strftime('%Y-%m-%d %H:%M:%S')
        }
        return JsonResponse(data)
    except Contact.DoesNotExist:
        return JsonResponse({'error': 'Query not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)




@login_required
@require_http_methods(["POST"])
def update_query_status(request, query_id):
    try:
        query = get_object_or_404(Contact, id=query_id)
        data = json.loads(request.body)

        query.status = data.get('status', query.status)
        query.admin_notes = data.get('admin_notes', query.admin_notes)
        query.save()

        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)
    

