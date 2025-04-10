from django.contrib import admin
from .models import Course, Enrollment, Certificate
from .quiz_models import Module, Quiz, Question, Answer, QuizAttempt, QuestionResponse

@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    list_display = ('student', 'course', 'enrollment_date', 'is_completed', 'progress', 'is_active')
    list_filter = ('is_completed', 'is_active', 'enrollment_date')
    search_fields = ('student__username', 'student__email', 'course__title')
    raw_id_fields = ('student', 'course')
    date_hierarchy = 'enrollment_date'


# Register your models here.
admin.site.register(Course)
admin.site.register(Certificate)
admin.site.register(Module)
admin.site.register(Quiz)
admin.site.register(Question)
admin.site.register(Answer)
admin.site.register(QuizAttempt)
admin.site.register(QuestionResponse)