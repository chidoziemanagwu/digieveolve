# Generated by Django 5.1.6 on 2025-04-10 09:07

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('courses', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='enrollment',
            options={'ordering': ['-enrollment_date']},
        ),
        migrations.AddField(
            model_name='enrollment',
            name='is_active',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='enrollment',
            name='last_accessed',
            field=models.DateTimeField(auto_now=True),
        ),
        migrations.AlterField(
            model_name='enrollment',
            name='course',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='enrollments', to='courses.course'),
        ),
        migrations.AlterField(
            model_name='enrollment',
            name='student',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='enrollments', to=settings.AUTH_USER_MODEL),
        ),
    ]
