# courses/models.py
from time import timezone
import uuid
from django.db import models
from django.urls import reverse
from accounts.models import User

# courses/models.py
class Course(models.Model):
    LEVEL_CHOICES = (
        ('beginner', 'Beginner'),
        ('intermediate', 'Intermediate'),
        ('advanced', 'Advanced'),
    )

    title = models.CharField(max_length=200)
    slug = models.SlugField(unique=True)
    short_description = models.TextField(max_length=200)
    description = models.TextField()
    image = models.ImageField(upload_to='courses/', null=True, blank=True)
    duration = models.IntegerField(help_text="Duration in hours")
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    is_free = models.BooleanField(default=False)
    level = models.CharField(max_length=20, choices=LEVEL_CHOICES, default='beginner')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title

class Enrollment(models.Model):
    student = models.ForeignKey('accounts.User', on_delete=models.CASCADE, related_name='enrollment')
    course = models.ForeignKey('courses.Course', on_delete=models.CASCADE, related_name='Course_enrollments')
    enrollment_date = models.DateTimeField(auto_now_add=True)
    completed_modules = models.CharField(max_length=255, blank=True, default="")  # Store as comma-separated IDs
    is_completed = models.BooleanField(default=False)
    completion_date = models.DateTimeField(blank=True, null=True)
    is_active = models.BooleanField(default=True)  # Added this field
    last_accessed = models.DateTimeField(auto_now=True)  # Added this field

    class Meta:
        unique_together = ('student', 'course')
        ordering = ['-enrollment_date']  # Added ordering

    def __str__(self):
        return f"{self.student.username} - {self.course.title}"

    @property
    def progress(self):
        """Calculate progress percentage based on completed modules"""
        total_modules = self.course.modules.count()
        if total_modules == 0:
            return 0

        if not self.completed_modules:
            return 0

        completed_count = len([m for m in self.completed_modules.split(',') if m])
        return int((completed_count / total_modules) * 100)

    def mark_module_completed(self, module_id):
        """Mark a specific module as completed"""
        completed = set(filter(None, self.completed_modules.split(',')))
        completed.add(str(module_id))
        self.completed_modules = ','.join(sorted(completed))

        # Check if all modules are completed
        total_modules = self.course.modules.count()
        if len(completed) == total_modules:
            self.is_completed = True
            self.completion_date = timezone.now()

        self.save()

    def is_module_completed(self, module_id):
        """Check if a specific module is completed"""
        completed = set(filter(None, self.completed_modules.split(',')))
        return str(module_id) in completed

    @property
    def completed_modules_list(self):
        """Return list of completed module IDs"""
        return [int(m) for m in self.completed_modules.split(',') if m]

    @property
    def remaining_modules(self):
        """Return QuerySet of uncompleted modules"""
        completed = self.completed_modules_list
        return self.course.modules.exclude(id__in=completed)

    def get_next_module(self):
        """Get the next uncompleted module"""
        return self.remaining_modules.first()

class Certificate(models.Model):
    student = models.ForeignKey(User, on_delete=models.CASCADE)
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    issued_date = models.DateTimeField(auto_now_add=True)
    certificate_number = models.CharField(max_length=50, unique=True)
    uuid = models.UUIDField(unique=True, editable=False, null=True)

    def save(self, *args, **kwargs):
        if not self.uuid:
            self.uuid = uuid.uuid4()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.student.username} - {self.course.title}"

    def get_public_url(self):
        """Return a shareable URL for the certificate"""
        return reverse('courses:public_certificate', kwargs={'uuid': self.uuid})

# courses/models.py
class Payment(models.Model):
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='payments')
    course = models.ForeignKey('courses.Course', on_delete=models.CASCADE, related_name='Course_payment_enrollments')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    reference = models.CharField(max_length=100, unique=True)
    transaction_id = models.CharField(max_length=100, blank=True, null=True)
    status = models.CharField(max_length=20, choices=[
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed')
    ], default='pending')
    payment_method = models.CharField(max_length=50, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Payment {self.reference} - {self.status}"

class Module(models.Model):
    """Module model to organize course content"""
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='modules')
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    content = models.TextField(blank=True)
    video_url = models.URLField(blank=True, null=True, help_text="URL to the video content")
    duration = models.IntegerField(help_text="Duration in minutes", default=0)
    order = models.PositiveIntegerField(default=0)
    has_quiz = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"{self.course.title} - {self.title}"