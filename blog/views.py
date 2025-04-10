import json
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404
from .models import BlogPost, Category
from django.core.paginator import Paginator


# Add these imports at the top of your accounts/views.py
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Count, Sum
from datetime import timedelta
from blog.models import BlogPost
from django.db.models import Q
from django.contrib import messages
from django.shortcuts import render, redirect
from django.utils.text import slugify



def blog_list(request, category_slug=None):
    """View for listing all blog posts, optionally filtered by category"""
    # Start with all posts
    post_list = BlogPost.objects.all().order_by('-published_date')

    # Filter by category if provided
    category = None
    if category_slug:
        category = get_object_or_404(Category, slug=category_slug)
        post_list = post_list.filter(category=category)

    # Get featured post (most recent or marked as featured)
    featured_post = BlogPost.objects.all().order_by('-published_date').first()

    # Get all categories
    categories = Category.objects.all()

    # Pagination
    paginator = Paginator(post_list, 6)  # Show 6 posts per page
    page = request.GET.get('page')
    posts = paginator.get_page(page)

    context = {
        'posts': posts,
        'featured_post': featured_post,
        'categories': categories,
        'category': category,
        'title': f'Blog - {category.name}' if category else 'Blog'
    }

    return render(request, 'blog/blog_list.html', context)

def blog_detail(request, slug):
    """View for displaying a single blog post"""
    post = get_object_or_404(BlogPost, slug=slug)

    # Optional: Get related posts
    related_posts = BlogPost.objects.filter(category=post.category).exclude(id=post.id)[:2]

    context = {
        'post': post,
        'related_posts': related_posts,
        'title': post.title
    }

    return render(request, 'blog/blog_detail.html', context)



# blog/views.py

@staff_member_required
def admin_posts(request):
    # Get all posts ordered by published date
    posts = BlogPost.objects.select_related('author', 'category').order_by('-published_date')

    # Handle search
    search_query = request.GET.get('search', '')
    if search_query:
        posts = posts.filter(
            Q(title__icontains=search_query) |
            Q(content__icontains=search_query) |
            Q(author__username__icontains=search_query)
        )

    # Handle category filter
    category_id = request.GET.get('category')
    if category_id:
        posts = posts.filter(category_id=category_id)

    # Handle status filter
    status = request.GET.get('status')
    if status:
        posts = posts.filter(status=status)

    # Get categories for filter dropdown
    categories = Category.objects.all()

    context = {
        'posts': posts,
        'categories': categories,
        'search_query': search_query
    }
    return render(request, 'digievolveadmin/blog/posts.html', context)

@staff_member_required
def admin_add_post(request):
    if request.method == 'POST':
        try:
            # Get form data
            title = request.POST.get('title')
            content = request.POST.get('content')
            excerpt = request.POST.get('excerpt')
            category_id = request.POST.get('category')
            status = request.POST.get('status', 'draft')

            # Create slug from title
            slug = slugify(title)

            # Handle duplicate slugs
            if BlogPost.objects.filter(slug=slug).exists():
                base_slug = slug
                counter = 1
                while BlogPost.objects.filter(slug=slug).exists():
                    slug = f"{base_slug}-{counter}"
                    counter += 1

            # Create blog post
            post = BlogPost.objects.create(
                title=title,
                slug=slug,
                content=content,
                excerpt=excerpt,
                category_id=category_id,
                author=request.user,
                status=status
            )

            # Handle featured image
            if 'featured_image' in request.FILES:
                post.featured_image = request.FILES['featured_image']
                post.save()

            messages.success(request, 'Blog post created successfully.')
            return redirect('blog:admin_posts')

        except Exception as e:
            messages.error(request, f'Error creating blog post: {str(e)}')

    # Get categories for the form
    categories = Category.objects.all()
    context = {
        'categories': categories
    }
    return render(request, 'digievolveadmin/blog/add_post.html', context)

@staff_member_required
def admin_edit_post(request, slug):
    post = get_object_or_404(BlogPost, slug=slug)

    if request.method == 'POST':
        try:
            # Update post data
            post.title = request.POST.get('title')
            post.content = request.POST.get('content')
            post.excerpt = request.POST.get('excerpt')
            post.category_id = request.POST.get('category')
            post.status = request.POST.get('status', 'draft')

            # Handle featured image
            if 'featured_image' in request.FILES:
                post.featured_image = request.FILES['featured_image']

            post.save()
            messages.success(request, 'Blog post updated successfully.')
            return redirect('blog:admin_posts')

        except Exception as e:
            messages.error(request, f'Error updating blog post: {str(e)}')

    categories = Category.objects.all()
    context = {
        'post': post,
        'categories': categories
    }
    return render(request, 'digievolveadmin/blog/edit_post.html', context)

@staff_member_required
def admin_delete_post(request, post_id):
    if request.method == 'POST':
        post = get_object_or_404(BlogPost, id=post_id)
        try:
            post.delete()
            messages.success(request, 'Blog post deleted successfully.')
        except Exception as e:
            messages.error(request, f'Error deleting blog post: {str(e)}')
    return redirect('blog:admin_posts')

@staff_member_required
def admin_toggle_post_status(request, post_id):
    if request.method == 'POST':
        post = get_object_or_404(BlogPost, id=post_id)
        try:
            post.status = 'published' if post.status == 'draft' else 'draft'
            post.save()
            messages.success(request, f'Post status changed to {post.status}.')
        except Exception as e:
            messages.error(request, f'Error changing post status: {str(e)}')
    return redirect('blog:admin_posts')




@staff_member_required
def admin_add_category(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            name = data.get('name')
            slug = slugify(name)

            # Handle duplicate slugs
            if Category.objects.filter(slug=slug).exists():
                base_slug = slug
                counter = 1
                while Category.objects.filter(slug=slug).exists():
                    slug = f"{base_slug}-{counter}"
                    counter += 1

            Category.objects.create(name=name, slug=slug)
            return JsonResponse({'status': 'success'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    return JsonResponse({'status': 'error', 'message': 'Invalid request'}, status=400)

@staff_member_required
def admin_edit_category(request, category_id):
    if request.method == 'POST':
        try:
            category = get_object_or_404(Category, id=category_id)
            data = json.loads(request.body)
            category.name = data.get('name')
            category.slug = slugify(category.name)
            category.save()
            return JsonResponse({'status': 'success'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    return JsonResponse({'status': 'error', 'message': 'Invalid request'}, status=400)

@staff_member_required
def admin_delete_category(request, category_id):
    if request.method == 'POST':
        try:
            category = get_object_or_404(Category, id=category_id)
            category.delete()
            return JsonResponse({'status': 'success'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    return JsonResponse({'status': 'error', 'message': 'Invalid request'}, status=400)