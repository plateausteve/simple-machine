# Generated by Django 3.1 on 2020-12-24 18:10

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('pairwise', '0025_auto_20201223_2106'),
    ]

    operations = [
        migrations.AlterField(
            model_name='comparison',
            name='select_method',
            field=models.FloatField(default=0.1, verbose_name='method of selecting next comparison'),
        ),
    ]