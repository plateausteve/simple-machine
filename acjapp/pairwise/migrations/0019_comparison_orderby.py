# Generated by Django 3.1 on 2020-09-06 22:33

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('pairwise', '0018_auto_20200905_1946'),
    ]

    operations = [
        migrations.AddField(
            model_name='comparison',
            name='orderby',
            field=models.TextField(blank=True, null=True),
        ),
    ]
