from django.core.exceptions import ValidationError

from .models import Student,skills
from base.models import Document

from django.contrib.auth.models import User
from django.contrib.auth.models import Group
from django import forms


class StudentCreationForm(forms.ModelForm):

    def clean_user(self):
        email = self.cleaned_data['email']
        # Ensure we create/get a User with a unique username (use email)
        # and ensure the 'students' group exists.
        username = email
        user, created = User.objects.get_or_create(
            username=username,
            defaults={"email": email},
        )

        students_group, _ = Group.objects.get_or_create(name="students")

        # If the user was just created, set a default password.
        if created:
            user.set_password("anteater")

        # Always ensure email and group membership are up-to-date.
        if user.email != email:
            user.email = email

        user.groups.add(students_group)
        user.save()
        return user

    user = forms.ModelChoiceField(queryset=User.objects.all(), required=False)

    class Meta:
        model = Student
        fields = ['name', 'usn', 'phone', 'rv_email',
                  'email', 'branch', 'year_joined', 'user']
        widgets = {
            'name': forms.TextInput(attrs={"class": "form-control", "placeholder": "Enter the name"}),
            'usn': forms.TextInput(attrs={"class": "form-control", "placeholder": "Enter the USN"}),
            
            'phone': forms.TextInput(attrs={"class": "form-control", "placeholder": "Enter the phone number"}),
            'rv_email': forms.EmailInput(attrs={"class": "form-control", "placeholder": "Enter the RTC email"}),
            'email': forms.EmailInput(attrs={"class": "form-control", "placeholder": "Enter the email"}),
            'branch': forms.TextInput(attrs={"class": "form-control", "placeholder": "Enter the branch"}),
            'year_joined': forms.DateInput(attrs={'type': 'date',"class": "form-control"})
        }


class StudentUploadForm(forms.ModelForm):

    def clean_file(self):
        file = self.cleaned_data['file']
        if not file.name.lower().endswith(('.csv', '.xls', '.xlsx')):
            raise ValidationError(
                "Only csv/xls/xlsx file formats supported!", code='invalid')
        return file

    class Meta:
        model = Document
        fields = (
            "name",
            "file",
        )
        widgets = {'file': forms.FileInput(attrs={"class": "form-control"})}

class skillform(forms.ModelForm):
    class Meta:
        model=skills
        fields= '__all__'
        widgets = {
            'skill': forms.TextInput(attrs={"class": "form-control", "placeholder": "Enter the skill"}),
        }