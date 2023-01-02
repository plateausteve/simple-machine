# Drawing Test - Django-based comparative judgement for art assessment
# Copyright (C) 2021  Steve and Ray Heil

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

from django.conf import settings
from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone
from django import forms
import datetime
from datetime import date, timedelta
from django_random_id_model import RandomIDModel


class Group(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True, verbose_name="the user who uploaded the items of this group")
    judges = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name='judges', verbose_name="the users with comparing capabilities for this group", blank=True)
    name = models.CharField(max_length=100)
    greater_statement = models.CharField(default="Greater", max_length=50, verbose_name="the adjective posed in the question for judges comparing the items")
    override_end = models.PositiveSmallIntegerField(editable = True, blank = True, null = True, verbose_name = "end after so many comparisons override")
  
    def __str__(self):
        return str(self.pk)

class Student(RandomIDModel):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True, verbose_name="the user who uploaded item(s) for this student")
    dob = models.DateField(verbose_name="birth date of student")
    class Gender(models.TextChoices):
        FEMALE = 'F'
        MALE = 'M'
        NONBINARY = 'N'
    gender = models.CharField(max_length=1, choices=Gender.choices, default='F')
    class Race(models.TextChoices):
        ASIAN = 'A'
        BLACK = 'B'
        MULTIRACIAL = 'M'
        NATIVE_AMERICAN = 'N'
        PACIFIC_ISLANDER = 'P'
        WHITE = 'W'
        OTHER_RACE = 'X'
    race = models.CharField(max_length=1, choices=Race.choices, default='W')
    class Ethnicity(models.TextChoices):
        HISPANIC = 'H'
        NOT_HISPANIC = 'N'
    ethnicity = models.CharField(max_length=1,choices=Ethnicity.choices, default='N')
    def race_ethnicity(self):
        if self.race == 'W' and self.ethnicity == 'H':
            return 'H'
        else:
            return self.race
    class Lunch(models.TextChoices):
        FREE = 'F'
        REDUCED = 'R'
        PAID = 'P'
        NO_INFORMATION = 'N'
    lunch = models.CharField(max_length=1, choices=Lunch.choices, default='P')
    class Elstatus(models.TextChoices):
        YES = 'Y'
        NO = 'N'
    el = models.CharField(max_length=1, choices=Elstatus.choices, default='N')

    def idcode(self):
        f = self.pk
        return '%06d' % (f)

    def __str__(self):
        return str(self.idcode())

class Item(RandomIDModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, blank=True, null=True, verbose_name="user who uploaded the item")
    group = models.ForeignKey(Group, on_delete=models.CASCADE, blank=True, null=True, verbose_name="one group to which the item belongs")
    pdf = models.FileField(upload_to="items/pdfs", null=True, blank=True)
    idcode = models.PositiveIntegerField(editable = True, blank=True, null=True, verbose_name="item ID code")
    student = models.ForeignKey(Student, on_delete=models.CASCADE, editable = True, blank = True, null = False, verbose_name="student who created this item")
    testdate = models.DateField(default=date.today, editable = True, verbose_name="test date")
    grade = models.SmallIntegerField(editable = True, blank=False, null=True, verbose_name="grade in school of student on test date")
  
    def testage(self):
        delta = self.testdate - self.student.dob
        age = round(delta.days/365,1)
        return age
      
    def idcode_f(self):
        f = self.idcode
        return '%06d' % (f)

    def __str__(self):
        return str(self.pk)

class Comparison(models.Model):
    group = models.ForeignKey(Group, on_delete=models.CASCADE, verbose_name="group to which this comparison belongs")
    judge = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name="user judging the pair")
    itemi = models.ForeignKey(Item, on_delete=models.CASCADE, related_name="+", verbose_name="left item in the comparison")
    itemj = models.ForeignKey(Item, on_delete=models.CASCADE, related_name="+", verbose_name="right item in the comparison")
    wini = models.PositiveSmallIntegerField(blank=True, null=True, verbose_name="is left lesser or greater?")
    form_start_variable = models.FloatField(blank=True, null=True)
    decision_start = models.DateTimeField(editable = False, blank=True, null=True)
    decision_end = models.DateTimeField(editable = False, blank=True, null=True)
    duration = models.DurationField(blank=True, null=True)

    def duration_HHmm(self):
        seconds = round(self.duration.total_seconds(),0)
        return datetime.timedelta(seconds=seconds)

    def __str__(self):
        return str(self.pk)

class WinForm(forms.ModelForm):
    class Meta:
        model = Comparison
        fields = ['group','wini','itemi','itemj', 'form_start_variable']
        widgets = {
            'group': forms.HiddenInput(),
            'wini': forms.HiddenInput(),
            'itemi': forms.HiddenInput(),
            'itemj': forms.HiddenInput(),
            'form_start_variable': forms.HiddenInput(),
        }