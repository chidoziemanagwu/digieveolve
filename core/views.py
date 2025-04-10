from django.http import Http404
from django.shortcuts import redirect, render

from blog.models import BlogPost
from resources.models import Resource, ResourceCategory
from .forms import ContactForm
from django.contrib import messages  # Add this import
from .services_data import services_data
from .training_programs_data import training_programs_data
from .models import NewsletterSubscriber
from contact.models import Contact  # Import the Contact model from your contact app




def home(request):
    return render(request, 'pages/home.html')


def about(request):
    tools = [
        "Python",
        "BigML",
        "Tableau",
        "Power Platforms",
        "PowerBI",
        "Microsoft Fabrics",
        "Alteryx",
        "SQL",
        "SaS Enterprise Miner",
        "SaS Enterprise Guide",
        "Microsoft Office",
        "SaS Vidya",
        "Looker Studio"
    ]
    return render(request, 'pages/about.html', {'tools': tools})

def contact(request):
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
                return render(request, 'pages/contact.html')

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

            # Add success message
            messages.success(request, "Thank you! Your message has been sent successfully.")

            # Render the same page with success message
            return render(request, 'pages/contact.html')

        except Exception as e:
            print(f"Error saving contact: {str(e)}")
            messages.error(request, f"An error occurred: {str(e)}")
            return render(request, 'pages/contact.html')

    # For GET requests, just render the template
    return render(request, 'pages/contact.html')


def services_page(request):
    context = {
        'services': services_data
    }
    return render(request, 'pages/services.html', context)

def service_detail(request, slug):
    # Get the service data or return 404 if not found
    service = services_data.get(slug)
    if not service:
        raise Http404("Service not found")

    context = {
        'service': service,
        'slug': slug
    }
    return render(request, 'pages/service_detail.html', context)

def training_programs(request):
    context = {
        'training_programs': training_programs_data
    }
    return render(request, 'pages/training_programs.html', context)

def training_detail(request, slug):
    program = training_programs_data.get(slug)
    if not program:
        return render(request, 'pages/404.html')

    context = {
        'program': program,
        'slug': slug
    }
    return render(request, 'pages/training_detail.html', context)

def resources(request):
    """View for the hybrid resources & blog home page"""
    # Try to get blog posts if the blog app is set up
    try:
        blog_posts = BlogPost.objects.all().order_by('-published_date')[:3]
    except:
        # Create dummy blog posts for testing
        class DummyPost:
            def __init__(self, title, slug, category, date, excerpt):
                self.title = title
                self.slug = slug
                self.category = category
                self.published_date = date
                self.excerpt = excerpt

        class DummyCategory:
            def __init__(self, name):
                self.name = name

        from datetime import datetime

        # Create dummy blog posts
        blog_posts = [
            DummyPost(
                "Getting Started with Python for Data Analytics",
                "getting-started-with-python",
                DummyCategory("Python"),
                datetime(2024, 10, 15),
                "Learn how to leverage Python's powerful libraries for data analysis and visualization."
            ),
            DummyPost(
                "5 Steps to Transition into a Data Science Career",
                "transition-to-data-science",
                DummyCategory("Career"),
                datetime(2024, 10, 10),
                "Practical advice for professionals looking to make the switch to data science."
            ),
            DummyPost(
                "Ethical Considerations in AI Development",
                "ethical-ai-development",
                DummyCategory("AI"),
                datetime(2024, 10, 5),
                "Understanding the ethical implications and responsibilities when developing AI systems."
            )
        ]

    # Get resource categories from the database if available
    try:
        resource_categories = ResourceCategory.objects.all()

        # Get a sample of resources for each category
        resource_samples = {}
        for category in resource_categories:
            resource_samples[category.slug] = Resource.objects.filter(
                category=category
            )[:2]  # Get 2 resources per category
    except:
        # Use your existing hardcoded data if models aren't set up yet
        resource_categories = {
            'learning_materials': {
                'title': "Learning Materials",
                'icon': "fa-book",
                'items': [
                    {
                        'title': "Technical Documentation",
                        'description': "Comprehensive guides for data analytics, science, engineering, and AI tools",
                        'links': ["Python", "BigML", "Tableau", "Power Platforms", "PowerBI", "Microsoft Fabrics"]
                    },
                    # other items...
                ]
            },
            # other categories...
        }
        resource_samples = {}

    context = {
        'blog_posts': blog_posts,
        'resource_categories': resource_categories,
        'resource_samples': resource_samples,
    }

    return render(request, 'pages/resources.html', context)

def newsletter_signup(request):
    if request.method == 'POST':
        email = request.POST.get('email')

        # Check if email already exists
        if NewsletterSubscriber.objects.filter(email=email).exists():
            messages.info(request, "You're already subscribed to our newsletter!")
        else:
            # Create new subscriber
            NewsletterSubscriber.objects.create(email=email)
            messages.success(request, "Thank you for subscribing to our newsletter!")

        return redirect('core:resources')

    return redirect('core:resources')