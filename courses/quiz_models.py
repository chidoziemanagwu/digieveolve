from django.db import models
from .models import Course, Module
from accounts.models import User
import uuid


class Quiz(models.Model):
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    module = models.ForeignKey(Module, on_delete=models.CASCADE, related_name='quizzes')
    time_limit = models.IntegerField(help_text="Time limit in minutes", default=30)
    passing_score = models.IntegerField(default=70, help_text="Passing score percentage")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Quizzes"

    def __str__(self):
        return self.title


class Question(models.Model):
    QUESTION_TYPES = (
        ('multiple_choice', 'Multiple Choice'),
        ('true_false', 'True/False'),
        ('short_answer', 'Short Answer'),
    )

    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name='questions')
    text = models.TextField()
    question_type = models.CharField(max_length=20, choices=QUESTION_TYPES)
    points = models.IntegerField(default=1)
    order = models.IntegerField(default=0)

    def __str__(self):
        return f"{self.text[:50]}..."

    def get_correct_answer(self):
        """Get the correct answer for this question"""
        return self.answers.filter(is_correct=True).first()

class Answer(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='answers')
    text = models.CharField(max_length=255)
    is_correct = models.BooleanField(default=False)

    def __str__(self):
        return self.text


class QuizAttempt(models.Model):
    student = models.ForeignKey(User, on_delete=models.CASCADE)
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE)
    score = models.FloatField(null=True, blank=True)
    is_passed = models.BooleanField(default=False)
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.student.username} - {self.quiz.title}"

    @property
    def is_completed(self):
        return self.completed_at is not None


class QuestionResponse(models.Model):
    attempt = models.ForeignKey(QuizAttempt, on_delete=models.CASCADE, related_name='responses')
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    selected_answer = models.ForeignKey(Answer, on_delete=models.CASCADE, null=True, blank=True)
    text_response = models.TextField(blank=True, null=True)
    is_correct = models.BooleanField(default=False)

    def __str__(self):
        return f"Response to {self.question.text[:30]}..."