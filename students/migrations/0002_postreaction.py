# students app migrations/0002_postreaction.py


from django.db import migrations, models
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('students', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='PostReaction',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('post', models.ForeignKey(on_delete=models.deletion.CASCADE, related_name='reactions', to='students.post')),
                ('user', models.ForeignKey(on_delete=models.deletion.CASCADE, related_name='student_post_reactions', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Post Reaction',
                'verbose_name_plural': 'Post Reactions',
            },
        ),
        migrations.AlterUniqueTogether(
            name='postreaction',
            unique_together={('post', 'user')},
        ),
    ]

