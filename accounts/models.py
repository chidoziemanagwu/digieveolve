# accounts/models.py
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
from django.urls import reverse
from django.db import transaction

class User(AbstractUser):
    """
    Custom User model that combines student and admin functionality
    """
    # User type choices
    USER_TYPES = (
        ('student', 'Student'),
        ('admin', 'Admin'),
        ('both', 'Both'),  # For users who are both students and admins
    )

    # Admin type choices
    ADMIN_TYPES = (
        ('super_admin', 'Super Admin'),
        ('content_admin', 'Content Admin'),
        ('support_admin', 'Support Admin'),
        ('none', 'Not Admin'),
    )

    # Profile fields
    first_name = models.CharField(max_length=255)
    last_name = models.CharField(max_length=255)
    phone = models.CharField(max_length=15, blank=True)
    bio = models.TextField(blank=True, null=True)
    profile_image = models.ImageField(upload_to='profile_images/', blank=True, null=True)

    # User type fields
    user_type = models.CharField(max_length=10, choices=USER_TYPES, default='student')
    is_student = models.BooleanField(default=True)

    # Admin specific fields
    admin_type = models.CharField(max_length=50, choices=ADMIN_TYPES, default='none')
    is_active_admin = models.BooleanField(default=False)
    last_admin_login = models.DateTimeField(null=True, blank=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'accounts_user'
        ordering = ['-date_joined']
        indexes = [
            models.Index(fields=['first_name', 'last_name']),
            models.Index(fields=['created_at']),
            models.Index(fields=['is_student']),
            models.Index(fields=['user_type']),
        ]

    def __str__(self):
        return f"{self.username} - {self.get_user_type_display()}"

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"

    @property
    def enrollment_count(self):
        """Get the number of courses the user is enrolled in."""
        from courses.models import Enrollment
        return Enrollment.objects.filter(student=self).count()

    @enrollment_count.setter
    def enrollment_count(self, value):
        """Dummy setter for Django's ORM."""
        pass  # This is needed for Django's ORM but doesn't need to do anything

    @property
    def active_enrollments(self):
        if not self.is_student:
            return []
        from courses.models import Enrollment
        return Enrollment.objects.filter(student=self, is_active=True)

    @property
    def completed_courses(self):
        if not self.is_student:
            return []
        from courses.models import Enrollment
        return Enrollment.objects.filter(student=self, is_completed=True)

    @property
    def completion_rate(self):
        if not self.is_student:
            return 0
        total = self.enrollment_count
        completed = self.completed_courses.count()
        return (completed / total * 100) if total > 0 else 0

    def get_recent_activities(self, limit=5):
        return self.activity_set.all().order_by('-timestamp')[:limit]

    def enroll_in_course(self, course):
        if not self.is_student:
            raise ValueError("Only students can enroll in courses")

        from courses.models import Enrollment
        enrollment, created = Enrollment.objects.get_or_create(
            student=self,
            course=course
        )
        if created:
            Activity.objects.create(
                user=self,
                activity_type='enrollment',
                description=f'Enrolled in {course.title}',
                course=course
            )
        return enrollment

    def update_profile(self, **kwargs):
        """
        Update profile fields
        Usage: user.update_profile(first_name='John', email='john@example.com')
        """
        allowed_fields = [
            'first_name', 'last_name', 'email', 'phone', 'bio',
            'profile_image', 'is_student', 'admin_type', 'is_active_admin'
        ]

        with transaction.atomic():
            for key, value in kwargs.items():
                if key in allowed_fields:
                    setattr(self, key, value)

            # Update user_type based on is_student and admin_type
            if self.is_student and self.admin_type != 'none':
                self.user_type = 'both'
            elif self.is_student:
                self.user_type = 'student'
            elif self.admin_type != 'none':
                self.user_type = 'admin'

            self.save()

    def record_admin_login(self):
        """Update the last admin login time"""
        if self.admin_type == 'none':
            raise ValueError("This user is not an admin")

        self.last_admin_login = timezone.now()
        self.save(update_fields=['last_admin_login'])

    def get_admin_dashboard_url(self):
        """Get the URL for the admin dashboard"""
        if self.admin_type == 'none':
            return None
        return reverse('accounts:admin_dashboard')


class Activity(models.Model):
    """
    Activity model to track user actions
    """
    ACTIVITY_TYPES = (
        ('enrollment', 'Course Enrollment'),
        ('completion', 'Module Completion'),
        ('certificate', 'Certificate Earned'),
        ('login', 'User Login'),
        ('other', 'Other Activity'),
    )

    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True,  # Add this
        blank=True  )
    activity_type = models.CharField(max_length=20, choices=ACTIVITY_TYPES)
    description = models.CharField(max_length=255)
    course = models.ForeignKey('courses.Course', on_delete=models.CASCADE, blank=True, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = 'Activities'
        ordering = ['-timestamp']
        db_table = 'accounts_activity'

    def __str__(self):
        return f"{self.user.username} - {self.activity_type} - {self.timestamp.strftime('%Y-%m-%d')}"