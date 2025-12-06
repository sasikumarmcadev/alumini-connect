from django.core.exceptions import ValidationError

from .models import Alumni, Category, Job, Higherstudies
from base.models import Document

from django.contrib.auth.models import User
from django.contrib.auth.models import Group
from django import forms


class AlumniCreationForm(forms.ModelForm):
    
    def clean_user(self):
        email = self.cleaned_data['email']
        usn = self.cleaned_data.get('usn', '')
        
        # Use USN as username (consistent with bulk upload)
        username = usn if usn else email
            
        user, created = User.objects.get_or_create(
            username=username,
            defaults={"email": email},
        )

        alumni_group, _ = Group.objects.get_or_create(name="alumni")

        if created:
            user.set_password("changeme123")  # Changed to match bulk upload

        if user.email != email:
            user.email = email

        user.groups.add(alumni_group)
        user.save()
        return user

    user = forms.ModelChoiceField(queryset=User.objects.all(), required=False)

    class Meta:
        model = Alumni
        fields = ['name', 'usn', 'phone', 'rv_email', 'email', 'branch', 'year_joined', 'year_passed', 'user']
        widgets = {
            'name': forms.TextInput(attrs={"class": "form-control", "placeholder": "Enter the name"}),
            'usn': forms.TextInput(attrs={"class": "form-control", "placeholder": "Enter the USN"}),
            'phone': forms.TextInput(attrs={"class": "form-control", "placeholder": "Enter the phone number"}),
            'rv_email': forms.EmailInput(attrs={"class": "form-control", "placeholder": "Enter the RTC email"}),
            'email': forms.EmailInput(attrs={"class": "form-control", "placeholder": "Enter the email"}),
            'branch': forms.TextInput(attrs={"class": "form-control", "placeholder": "Enter the branch"}),
            'year_joined': forms.DateInput(attrs={'type': 'date', "class": "form-control"}),
            'year_passed': forms.DateInput(attrs={'type': 'date', "class": "form-control"}),
        }


class AlumniUploadForm(forms.ModelForm):
    def validate_file(file):
        if not file.name.lower().endswith(('.csv', '.xls', '.xlsx')):
            raise ValidationError("Only csv/xls/xlsx file formats supported!")
        return file

    file = forms.FileField(validators=[validate_file], widget=forms.FileInput(
        attrs={"class": "form-control"}))

    class Meta:
        model = Document
        fields = ["name", "file"]


class Catform(forms.ModelForm):
    class Meta:
        model = Category
        fields = '__all__'
        widgets = {
            'Category': forms.Select(attrs={"class": "form-control"}),
            'description': forms.Textarea(attrs={"class": "form-control", "placeholder": "Enter short description of your present status"}),
        }


class Jobform(forms.ModelForm):
    class Meta:
        model = Job
        fields = '__all__'
        widgets = {
            'company_name': forms.TextInput(attrs={"class": "form-control", "placeholder": "Enter the company name"}),
            'role': forms.Select(attrs={"class": "form-control", "placeholder": "Enter the role"}),
            'salary': forms.NumberInput(attrs={"class": "form-control", "placeholder": "Enter the salary"}),
            'location': forms.TextInput(attrs={"class": "form-control", "placeholder": "Enter the Job location"}),
        }


class Highform(forms.ModelForm):
    class Meta:
        model = Higherstudies
        fields = '__all__'
        widgets = {
            'college_name': forms.TextInput(attrs={"class": "form-control", "placeholder": "Enter the college name"}),
            'location': forms.TextInput(attrs={"class": "form-control", "placeholder": "Enter the Institute country"}),
            'specialization': forms.Select(attrs={"class": "form-control", "placeholder": "Enter the specialization"}),
            'degree': forms.Select(attrs={"class": "form-control", "placeholder": "Enter the degree"}),
            'yearofgrad': forms.DateInput(attrs={"type": 'date', "class": "form-control", "placeholder": "select date of graduation (expected)"}),
        }