from .models import ResourceCategory, Resource
from blog.models import BlogPost  # Import the blog Post model if you have it
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.utils.text import slugify
from accounts.decorators import admin_login_required
import os




def resource_list(request):
    # Get all resources with filters
    resources_list = Resource.objects.all().order_by('-updated_date')

    # Apply search filter
    search_query = request.GET.get('search', '')
    if search_query:
        resources_list = resources_list.filter(
            Q(title__icontains=search_query) |
            Q(description__icontains=search_query)
        )

    # Get category filter from URL
    category_filter = request.GET.get('category', '')
    if category_filter:
        resources_list = resources_list.filter(category__category_type=category_filter)

    # Apply file type filter
    file_type_filter = request.GET.get('file_type', '')
    if file_type_filter:
        resources_list = resources_list.filter(file_type=file_type_filter)

    # Get all categories
    categories = ResourceCategory.objects.all()

    # Get category types for the filter
    resource_category_types = ResourceCategory._meta.get_field('category_type').choices

    # Get file types for filter
    file_types = Resource._meta.get_field('file_type').choices

    # Split resources by category type for the featured sections
    technical_resources = resources_list.filter(category__category_type='technical')[:3]
    career_resources = resources_list.filter(category__category_type='career')[:3]
    research_resources = resources_list.filter(category__category_type='research')[:3]

    # Pagination for the main resources list
    paginator = Paginator(resources_list, 9)  # Show 9 resources per page
    page = request.GET.get('page', 1)
    resources = paginator.get_page(page)

    # Get latest blog posts if you have a blog app
    try:
        blog_posts = BlogPost.objects.filter(status='published').order_by('-created_at')[:3]
    except:
        blog_posts = []

    context = {
        'categories': categories,
        'technical_resources': technical_resources,
        'career_resources': career_resources,
        'research_resources': research_resources,
        'blog_posts': blog_posts,
        'category_filter': category_filter,
        'resource_category_types': resource_category_types,
        'file_types': file_types,
        'search_query': search_query,
        'file_type_filter': file_type_filter,
        'resources': resources,  # Paginated resources
        'total_resources': resources_list.count(),  # Total count for showing in template
    }

    return render(request, 'resources.html', context)

def category_detail(request, slug=None, category_slug=None):
    # Handle both URL patterns
    if category_slug:
        slug = category_slug

    category = get_object_or_404(ResourceCategory, slug=slug)
    resources = Resource.objects.filter(category=category)

    # Get other categories for the related categories section
    related_categories = ResourceCategory.objects.exclude(id=category.id)[:3]

    context = {
        'resource_category': category,  # Match the template variable name
        'resources': resources,
        'related_categories': related_categories
    }

    return render(request, 'resources/category_detail.html', context)

def resource_detail(request, slug):
    resource = get_object_or_404(Resource, slug=slug)
    # Get related resources from the same category
    related_resources = Resource.objects.filter(category=resource.category).exclude(id=resource.id)[:3]

    context = {
        'resource': resource,
        'related_resources': related_resources
    }

    return render(request, 'resource_detail.html', context)



# Admin views
@login_required
@admin_login_required
def admin_resources(request):
    # Get all resources with filters
    resources_list = Resource.objects.all().order_by('-updated_date')

    # Apply search filter
    search_query = request.GET.get('search', '')
    if search_query:
        resources_list = resources_list.filter(
            Q(title__icontains=search_query) |
            Q(description__icontains=search_query)
        )

    # Apply category filter
    category_filter = request.GET.get('category', '')
    if category_filter:
        resources_list = resources_list.filter(category_id=category_filter)

    # Apply file type filter
    file_type_filter = request.GET.get('file_type', '')
    if file_type_filter:
        resources_list = resources_list.filter(file_type=file_type_filter)

    # Pagination
    paginator = Paginator(resources_list, 10)  # Show 10 resources per page
    page = request.GET.get('page', 1)
    resources = paginator.get_page(page)

    # Get all categories for filter dropdown
    categories = ResourceCategory.objects.all()

    # Get file types for filter dropdown
    file_types = Resource._meta.get_field('file_type').choices

    context = {
        'resources': resources,
        'categories': categories,
        'file_types': file_types,
    }

    return render(request, 'digievolveadmin/admin_resources.html', context)

@login_required
@admin_login_required
def admin_add_resource(request):
    categories = ResourceCategory.objects.all()
    file_types = Resource._meta.get_field('file_type').choices

    if request.method == 'POST':
        title = request.POST.get('title')
        slug = request.POST.get('slug')
        description = request.POST.get('description')
        category_id = request.POST.get('category')
        file_type = request.POST.get('file_type')
        file = request.FILES.get('file')
        file_size = request.POST.get('file_size')

        # Generate slug if not provided
        if not slug:
            slug = slugify(title)

        # Check if slug is unique
        if Resource.objects.filter(slug=slug).exists():
            messages.error(request, 'A resource with this slug already exists. Please choose a different one.')
            return render(request, 'digievolveadmin/admin_resource_form.html', {
                'categories': categories,
                'file_types': file_types,
            })

        # Create resource
        try:
            category = ResourceCategory.objects.get(id=category_id)
            resource = Resource.objects.create(
                title=title,
                slug=slug,
                description=description,
                category=category,
                file_type=file_type,
                file=file,
            )

            # Set file size if provided, otherwise calculate it
            if file_size:
                resource.file_size = file_size
            else:
                # Calculate file size in MB
                if file:
                    size_bytes = file.size
                    size_mb = round(size_bytes / (1024 * 1024), 2)
                    resource.file_size = f"{size_mb} MB"

            resource.save()
            messages.success(request, 'Resource added successfully!')
            return redirect('resources:admin_resources')

        except Exception as e:
            messages.error(request, f'Error adding resource: {str(e)}')

    context = {
        'categories': categories,
        'file_types': file_types,
    }

    return render(request, 'digievolveadmin/admin_resource_form.html', context)

@login_required
@admin_login_required
def admin_edit_resource(request, resource_id):
    resource = get_object_or_404(Resource, id=resource_id)
    categories = ResourceCategory.objects.all()
    file_types = Resource._meta.get_field('file_type').choices

    if request.method == 'POST':
        title = request.POST.get('title')
        slug = request.POST.get('slug')
        description = request.POST.get('description')
        category_id = request.POST.get('category')
        file_type = request.POST.get('file_type')
        file = request.FILES.get('file')
        file_size = request.POST.get('file_size')

        # Generate slug if not provided
        if not slug:
            slug = slugify(title)

        # Check if slug is unique (excluding this resource)
        if Resource.objects.filter(slug=slug).exclude(id=resource_id).exists():
            messages.error(request, 'A resource with this slug already exists. Please choose a different one.')
            return render(request, 'admin_resource_form.html', {
                'resource': resource,
                'categories': categories,
                'file_types': file_types,
            })

        # Update resource
        try:
            resource.title = title
            resource.slug = slug
            resource.description = description
            resource.category = ResourceCategory.objects.get(id=category_id)
            resource.file_type = file_type

            # Update file if provided
            if file:
                resource.file = file

                # Calculate file size
                size_bytes = file.size
                size_mb = round(size_bytes / (1024 * 1024), 2)
                resource.file_size = f"{size_mb} MB"

            # Update file size if provided
            if file_size:
                resource.file_size = file_size

            resource.save()
            messages.success(request, 'Resource updated successfully!')
            return redirect('resources:admin_resources')

        except Exception as e:
            messages.error(request, f'Error updating resource: {str(e)}')

    context = {
        'resource': resource,
        'categories': categories,
        'file_types': file_types,
    }

    return render(request, 'digievolveadmin/admin_resource_form.html', context)

@login_required
@admin_login_required
def admin_delete_resource(request, resource_id):
    resource = get_object_or_404(Resource, id=resource_id)

    if request.method == 'POST':
        try:
            # Delete the file from storage
            if resource.file:
                if os.path.isfile(resource.file.path):
                    os.remove(resource.file.path)

            # Delete the resource
            resource.delete()
            messages.success(request, 'Resource deleted successfully!')
        except Exception as e:
            messages.error(request, f'Error deleting resource: {str(e)}')

    return redirect('resources:admin_resources')

@login_required
@admin_login_required
def admin_categories(request):
    categories = ResourceCategory.objects.all().order_by('title')
    category_types = ResourceCategory._meta.get_field('category_type').choices
    edit_category = None

    # Handle edit request
    if request.GET.get('edit'):
        edit_category = get_object_or_404(ResourceCategory, id=request.GET.get('edit'))

    # Handle form submission
    if request.method == 'POST':
        # Delete category
        if request.POST.get('delete_category'):
            category_id = request.POST.get('delete_category')
            category = get_object_or_404(ResourceCategory, id=category_id)
            try:
                # Delete the category image from storage
                if category.image:
                    if os.path.isfile(category.image.path):
                        os.remove(category.image.path)

                # Delete the category (resources will be deleted by CASCADE)
                category.delete()
                messages.success(request, 'Category deleted successfully!')
            except Exception as e:
                messages.error(request, f'Error deleting category: {str(e)}')

            return redirect('resources:admin_categories')

        # Add/Edit category
        title = request.POST.get('title')
        slug = request.POST.get('slug')
        description = request.POST.get('description')
        category_type = request.POST.get('category_type')
        image = request.FILES.get('image')

        # Generate slug if not provided
        if not slug:
            slug = slugify(title)

        # Edit existing category
        if request.POST.get('category_id'):
            category = get_object_or_404(ResourceCategory, id=request.POST.get('category_id'))

            # Check if slug is unique (excluding this category)
            if ResourceCategory.objects.filter(slug=slug).exclude(id=category.id).exists():
                messages.error(request, 'A category with this slug already exists. Please choose a different one.')
                return redirect(f'resources:admin_categories?edit={category.id}')

            try:
                category.title = title
                category.slug = slug
                category.description = description
                category.category_type = category_type

                # Update image if provided
                if image:
                    # Delete old image if exists
                    if category.image:
                        if os.path.isfile(category.image.path):
                            os.remove(category.image.path)

                    category.image = image

                category.save()
                messages.success(request, 'Category updated successfully!')
                return redirect('resources:admin_categories')

            except Exception as e:
                messages.error(request, f'Error updating category: {str(e)}')

        # Add new category
        else:
            # Check if slug is unique
            if ResourceCategory.objects.filter(slug=slug).exists():
                messages.error(request, 'A category with this slug already exists. Please choose a different one.')
                return redirect('resources:admin_categories')

            try:
                ResourceCategory.objects.create(
                    title=title,
                    slug=slug,
                    description=description,
                    category_type=category_type,
                    image=image,
                )
                messages.success(request, 'Category added successfully!')
                return redirect('resources:admin_categories')

            except Exception as e:
                messages.error(request, f'Error adding category: {str(e)}')

    context = {
        'categories': categories,
        'category_types': category_types,
        'edit_category': edit_category,
    }

    return render(request, 'digievolveadmin/admin_categories.html', context)