from django.forms import ValidationError
from django.http import HttpResponse
from django.urls import reverse
from django.shortcuts import render, redirect, HttpResponseRedirect
from .models import Alumni, Job, Higherstudies, Category
from admin.models import Event
from student.models import Student
from posts.models import Post
from django.contrib.auth.models import User, Group
import csv

from .forms import AlumniCreationForm, AlumniUploadForm, Catform, Jobform, Highform

from django.views.generic import ListView
from django.views.generic.base import TemplateView, View
from django.views.generic.edit import CreateView, FormView, DeleteView, UpdateView
from django.db.models import Q
from base.file_handlers import handle_alumni_file
from .parsers import parse_query
from django.contrib import messages
import pandas as pd
from django.views.decorators.http import require_http_methods
from datetime import datetime
from django.db import IntegrityError
import os


def response(request):
    return HttpResponse('Hello')

# -----------------------------
# Helper: get RTC email column
# -----------------------------
def _get_rtc_email_value(row):
    """
    Safely get the RTC email value from a DataFrame row.
    Supports both legacy 'RV_Email' and new 'RTC_Email' headers,
    without breaking existing uploads.
    """
    if 'RTC_Email' in row and pd.notna(row['RTC_Email']):
        return row['RTC_Email']
    return row.get('RV_Email', None)


class AlumniHomeView(View):
    def get(self, request):
        data = Event.objects.all().order_by('-time_posted')[:2]
        posts = Post.objects.all().order_by('-time_posted')[:2]
        context = {'event': data, 'posts': posts}
        return render(request, "alumni/home.html", context)


def AlumniListView(request):
    # Check if there's upload summary in session
    upload_summary = request.session.pop('upload_summary', None)
    
    if 'q' in request.GET:
        q = request.GET['q']
        multiple_q = Q(Q(usn__icontains=q) | Q(name__icontains=q) | Q(branch__icontains=q) | 
                      Q(job__company_name__icontains=q) | Q(job__role__icontains=q) | 
                      Q(higherstudies__specialization__icontains=q) | Q(higherstudies__degree__icontains=q) | 
                      Q(higherstudies__college_name__icontains=q))
        data = Alumni.objects.filter(multiple_q).order_by('-usn')
    else:
        data = Alumni.objects.all().order_by('-usn')
    
    context = {
        'alumni': data,
        'upload_summary': upload_summary
    }
    return render(request, "alumni/list.html", context)


class AlumniSearchView(ListView):
    model = Alumni
    template_name = 'alumni/list.html'
    context_object_name = 'alumni'
    arg = {}

    def get(self, request):
        self.__class__.arg = parse_query(request.GET['query'])
        return super().get(self, request)

    ordering = ['user']

    def get_queryset(self):
        return Alumni.objects.filter(**self.__class__.arg)


class AlumniPostView(ListView):
    model = Post
    template_name = 'posts/list.html'
    context_object_name = 'posts'
    ordering = ['author']

    def get_queryset(self):
        return Post.objects.filter(author=self.request.user.alumnus_details)


class AlumniCreateView(CreateView):
    model = Alumni
    form_class = AlumniCreationForm
    template_name = 'alumni/new.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Check if there's uploaded data to pre-fill
        uploaded_data = self.request.session.pop('uploaded_alumni_data', None)
        if uploaded_data and not self.request.POST:
            initial = {}
            for key, value in uploaded_data.items():
                if key in context['form'].fields:
                    initial[key] = value
            context['form'].initial = initial
        return context

    def get_success_url(self):
        return reverse('list_alumni')


class AlumniUploadView(FormView):
    form_class = AlumniUploadForm
    template_name = 'alumni/upload.html'

    def form_valid(self, form):
        summary = handle_alumni_file(self.request.FILES["file"])
        if not summary:
            raise ValidationError('Invalid File Structure!')
        messages.success(self.request, f"Processed {summary['processed']} rows — created {summary['created']}, updated {summary['updated']}.")
        if summary['errors']:
            for r, msg in summary['errors']:
                messages.error(self.request, f"Row {r}: {msg}")
        return super().form_valid(form)
    
    def get_success_url(self):
        return reverse('list_alumni')


class AlumniDeleteView(DeleteView):
    model = User

    def get_success_url(self):
        return reverse('list_alumni')


class AlumniUpdateView(UpdateView):
    model = Alumni
    form_class = AlumniCreationForm
    template_name = 'alumni/update.html'

    def get_success_url(self):
        return reverse('list_alumni')


def CategoryView(request):
    if request.method == 'POST':
        form1 = Catform(request.POST)
        form2 = Jobform(request.POST)
        if form1.is_valid():
            instance = form1.save(commit=False)
            instance.alumnus = Alumni.objects.get(user=request.user)
            instance.save()
            messages.success(request, 'added Successfully.')
        if form2.is_valid():
            instanc = form2.save(commit=False)
            instanc.alumnus = Alumni.objects.get(user=request.user)
            instanc.save()
            messages.success(request, 'added Successfully.')
    else:
        form1 = Catform()
        form2 = Jobform()

    return render(request, 'alumni/job.html', {'form1': form1, 'form2': form2})


def HigherView(request):
    if request.method == 'POST':
        form = Highform(request.POST)
        if form.is_valid():
            instance = form.save(commit=False)
            instance.alumnus = Alumni.objects.get(user=request.user)
            instance.save()
            messages.success(request, 'added Successfully.')
    else:
        form = Highform()

    return render(request, 'alumni/higher.html', {'form': form})


def Profile(request):
    data = Alumni.objects.get(user=request.user)
    return render(request, 'alumni/profile.html', {'data': data})


def update(request):
    Al = Alumni.objects.get(user=request.user)
    if request.method == 'POST':
        try:
            H = Job.objects.get(alumnus=Al)
            form2 = Jobform(request.POST, instance=H)
            if form2.is_valid():
                instance = form2.save(commit=False)
                instance.alumnus = Alumni.objects.get(user=request.user)
                instance.save()
                return redirect('/alumni/profile')
        except:
            form2 = Jobform(request.POST)
            if form2.is_valid():
                instance = form2.save(commit=False)
                instance.alumnus = Alumni.objects.get(user=request.user)
                instance.save()
                return redirect('/alumni/profile')
    else:
        try:
            H = Job.objects.get(alumnus=Al)
            form2 = Jobform(instance=H)
            return render(request, "alumni/job.html", {'form2': form2})
        except:
            form2 = Jobform()
            return render(request, "alumni/job.html", {'form2': form2})


def update2(request):
    Al = Alumni.objects.get(user=request.user)
    if request.method == 'POST':
        try:
            H = Higherstudies.objects.get(alumnus=Al)
            form = Highform(request.POST, instance=H)
            if form.is_valid():
                instance = form.save(commit=False)
                instance.alumnus = Alumni.objects.get(user=request.user)
                instance.save()
                return redirect('/alumni/profile')
        except:
            form = Highform(request.POST)
            if form.is_valid():
                instance = form.save(commit=False)
                instance.alumnus = Alumni.objects.get(user=request.user)
                instance.save()
                return redirect('/alumni/profile')
    else:
        try:
            H = Higherstudies.objects.get(alumnus=Al)
            form = Highform(instance=H)
            return render(request, "alumni/higher.html", {'form': form})
        except:
            form = Highform()
            return render(request, "alumni/higher.html", {'form': form})


def update3(request):
    Al = Alumni.objects.get(user=request.user)
    if request.method == 'POST':
        try:
            H = Category.objects.get(alumnus=Al)
            form = Catform(request.POST, instance=H)
            if form.is_valid():
                instance = form.save(commit=False)
                instance.alumnus = Alumni.objects.get(user=request.user)
                instance.save()
                return redirect('/alumni/profile')
        except:
            form = Catform(request.POST)
            if form.is_valid():
                instance = form.save(commit=False)
                instance.alumnus = Alumni.objects.get(user=request.user)
                instance.save()
                return redirect('/alumni/profile')
    else:
        try:
            H = Category.objects.get(alumnus=Al)
            form = Catform(instance=H)
            return render(request, "alumni/current_status.html", {'form': form})
        except:
            form = Catform()
            return render(request, "alumni/current_status.html", {'form': form})


@require_http_methods(["POST"])
def bulk_upload_alumni(request):
    if request.method == 'POST' and request.FILES.get('excel_file'):
        excel_file = request.FILES['excel_file']
        redirect_to = request.POST.get('redirect_to', 'new')  # 'new' or 'list'
        
        # File validation
        ext = os.path.splitext(excel_file.name)[1].lower()
        if ext not in ['.xls', '.xlsx', '.xlsm']:
            messages.error(request, 'Only Excel files (.xls, .xlsx, .xlsm) are allowed')
            return redirect('new_alumni' if redirect_to == 'new' else 'list_alumni')
        
        # File size validation (10MB max)
        if excel_file.size > 10 * 1024 * 1024:
            messages.error(request, 'File size must be less than 10MB')
            return redirect('new_alumni' if redirect_to == 'new' else 'list_alumni')
        
        try:
            # Read Excel file
            df = pd.read_excel(excel_file)
            
            # Expected columns (supporting both legacy RV and new RTC mail headers)
            base_required_columns = ['Name', 'USN', 'Phone', 'Email', 'Branch', 'Year_Joined', 'Year_Passed']
            if not all(col in df.columns for col in base_required_columns):
                messages.error(request, f'Excel file must contain columns: {", ".join(base_required_columns + ["RTC_Email or RV_Email"])}')
                return redirect('new_alumni' if redirect_to == 'new' else 'list_alumni')
            
            # Determine which institutional email header is present
            has_rtc_email = 'RTC_Email' in df.columns
            has_rv_email = 'RV_Email' in df.columns
            if not (has_rtc_email or has_rv_email):
                messages.error(request, 'Excel file must contain either "RTC_Email" (preferred) or legacy "RV_Email" column.')
                return redirect('new_alumni' if redirect_to == 'new' else 'list_alumni')
            
            created_count = 0
            updated_count = 0
            error_count = 0
            error_details = []
            
            # Store last successful alumni data for form pre-filling
            last_successful_alumni = None
            
            # Iterate through rows and create/update Alumni objects
            for index, row in df.iterrows():
                try:
                    # Get values directly
                    name = str(row['Name']).strip()
                    usn = str(row['USN']).strip().upper()
                    phone = str(row['Phone']).strip()
                    rtc_email_value = _get_rtc_email_value(row)
                    rv_email = str(rtc_email_value).strip().lower() if rtc_email_value else ''
                    email = str(row['Email']).strip().lower()
                    branch = str(row['Branch']).strip() if pd.notna(row['Branch']) else ''
                    
                    # Simple validation
                    if not name or not usn or not phone or not rv_email or not email:
                        error_count += 1
                        error_details.append(f"Row {index + 2}: Missing required fields")
                        continue
                    
                    if '@' not in rv_email or '@' not in email:
                        error_count += 1
                        error_details.append(f"Row {index + 2}: Invalid email format")
                        continue
                    
                    # Handle dates - just convert to string first
                    year_joined = None
                    year_passed = None
                    
                    try:
                        if pd.notna(row['Year_Joined']):
                            # Convert to string first, then try to parse
                            date_str = str(row['Year_Joined'])
                            # Try to parse with pandas
                            year_joined = pd.to_datetime(date_str).date()
                    except:
                        year_joined = None
                    
                    try:
                        if pd.notna(row['Year_Passed']):
                            # Convert to string first, then try to parse
                            date_str = str(row['Year_Passed'])
                            # Try to parse with pandas
                            year_passed = pd.to_datetime(date_str).date()
                    except:
                        year_passed = None
                    
                    # Check if USN already exists in Student table
                    if Student.objects.filter(usn=usn).exists():
                        error_count += 1
                        error_details.append(f"Row {index + 2}: USN '{usn}' already exists as a Student")
                        continue
                    
                    # Check if user already exists with this USN
                    user_exists = User.objects.filter(username=usn).first()
                    
                    if user_exists:
                        # UPDATE existing alumni
                        try:
                            alumni = Alumni.objects.get(user=user_exists)
                            alumni.name = name
                            alumni.usn = usn
                            alumni.phone = phone
                            alumni.rv_email = rv_email
                            alumni.email = email
                            alumni.branch = branch
                            if year_joined:
                                alumni.year_joined = year_joined
                            if year_passed:
                                alumni.year_passed = year_passed
                            alumni.save()
                            
                            # Also update user email
                            user_exists.email = email
                            user_exists.save()
                            
                            # Ensure user is in alumni group
                            alumni_group, _ = Group.objects.get_or_create(name="alumni")
                            if not user_exists.groups.filter(name="alumni").exists():
                                user_exists.groups.add(alumni_group)
                                user_exists.save()
                            
                            updated_count += 1
                            last_successful_alumni = {
                                'name': name,
                                'usn': usn,
                                'phone': phone,
                                'rv_email': rv_email,
                                'email': email,
                                'branch': branch,
                            }
                            
                        except Alumni.DoesNotExist:
                            # User exists but no Alumni profile
                            Alumni.objects.create(
                                user=user_exists,
                                name=name,
                                usn=usn,
                                phone=phone,
                                rv_email=rv_email,
                                email=email,
                                branch=branch,
                                year_joined=year_joined,
                                year_passed=year_passed
                            )
                            # Ensure user is in alumni group
                            alumni_group, _ = Group.objects.get_or_create(name="alumni")
                            if not user_exists.groups.filter(name="alumni").exists():
                                user_exists.groups.add(alumni_group)
                                user_exists.save()
                            
                            created_count += 1
                            last_successful_alumni = {
                                'name': name,
                                'usn': usn,
                                'phone': phone,
                                'rv_email': rv_email,
                                'email': email,
                                'branch': branch,
                            }
                    else:
                        # CREATE new user and alumni
                        try:
                            user = User.objects.create_user(
                                username=usn,
                                email=email,
                                password='changeme123'  # Default password
                            )
                            
                            # Add to alumni group
                            alumni_group, _ = Group.objects.get_or_create(name="alumni")
                            user.groups.add(alumni_group)
                            user.save()
                            
                            Alumni.objects.create(
                                user=user,
                                name=name,
                                usn=usn,
                                phone=phone,
                                rv_email=rv_email,
                                email=email,
                                branch=branch,
                                year_joined=year_joined,
                                year_passed=year_passed
                            )
                            created_count += 1
                            last_successful_alumni = {
                                'name': name,
                                'usn': usn,
                                'phone': phone,
                                'rv_email': rv_email,
                                'email': email,
                                'branch': branch,
                            }
                            
                        except IntegrityError:
                            error_count += 1
                            error_details.append(f"Row {index + 2}: User with username '{usn}' already exists")
                            continue
                        
                except IntegrityError as e:
                    error_count += 1
                    error_details.append(f"Row {index + 2}: Database error - {str(e)}")
                except Exception as e:
                    error_count += 1
                    error_details.append(f"Row {index + 2}: Error - {str(e)}")
            
            # Store upload summary in session
            upload_summary = {
                'total': len(df),
                'created': created_count,
                'updated': updated_count,
                'errors': error_count
            }
            
            # Store last successful alumni data in session for form pre-filling
            if last_successful_alumni and redirect_to == 'new':
                request.session['uploaded_alumni_data'] = last_successful_alumni
            
            # Store summary in session for list page display
            request.session['upload_summary'] = upload_summary
            
            # Overall success message
            if created_count > 0 or updated_count > 0:
                success_msg = f"Bulk upload completed successfully! {created_count} created, {updated_count} updated"
                messages.success(request, success_msg)
            
            # Error messages (show first 5 errors)
            if error_count > 0:
                messages.warning(request, f'{error_count} records had errors')
                for error_msg in error_details[:5]:
                    messages.error(request, error_msg)
                if len(error_details) > 5:
                    messages.error(request, f'... and {len(error_details) - 5} more errors.')
            
            # If nothing happened
            if created_count == 0 and updated_count == 0 and error_count == 0:
                messages.info(request, 'No records were processed from the Excel file.')
            
            # Redirect based on source
            if redirect_to == 'list':
                return redirect('list_alumni')
            else:
                return redirect('new_alumni')
            
        except pd.errors.EmptyDataError:
            messages.error(request, 'The uploaded Excel file is empty')
            return redirect('new_alumni' if redirect_to == 'new' else 'list_alumni')
        except Exception as e:
            messages.error(request, f'Error processing file: {str(e)}')
            return redirect('new_alumni' if redirect_to == 'new' else 'list_alumni')
    else:
        messages.error(request, 'No file uploaded.')
        return redirect('new_alumni')