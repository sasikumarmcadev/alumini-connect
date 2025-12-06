from django.http import HttpResponse
from django.shortcuts import render, redirect
from django.urls import reverse
from django.contrib.sessions.models import Session

from .models import Student, skills
from comments.models import Comment
from django.contrib.auth.models import User

from .forms import StudentCreationForm, StudentUploadForm, skillform

from django.views.generic import ListView
from django.views.generic.base import TemplateView, View
from django.views.generic.edit import CreateView, FormView, DeleteView, UpdateView
from django.shortcuts import render, redirect, HttpResponseRedirect
from base.file_handlers import handle_student_file
from django.contrib import messages
from .parsers import parse_query
from django.db.models import Q, Count
from posts.models import Post
from alumni.models import Alumni, Job, Higherstudies, Category
import pandas as pd
from django.views.decorators.http import require_http_methods
from datetime import datetime
from django.db import IntegrityError
import json

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

class StudentHomeView(View):
    def get(self,request):
        
        posts=Post.objects.all().order_by('-time_posted')[:2]
        context={'posts':posts}
        return render(request,"student/home.html",context)

def StudentListView(request):
    # Check if there's upload summary in session
    upload_summary = request.session.pop('upload_summary', None)
    
    if 'q' in request.GET:
        q=request.GET['q']
        multiple_q=Q(Q(usn__icontains=q)|Q(name__icontains=q)|Q(branch__icontains=q))
        data=Student.objects.filter(multiple_q).order_by('-usn')
    else:
        data=Student.objects.all().order_by('-usn')    
    
    context = {
        'students': data,
        'upload_summary': upload_summary
    }
    return render(request,"student/list.html",context)

class StudentSearchView(ListView):
    model = Student
    template_name = 'student/list.html'
    context_object_name = 'students'
    arg = {}

    def get(self, request):
        self.__class__.arg = parse_query(request.GET['query'])
        return super().get(self, request)

    ordering = ['user']

    def get_queryset(self):
        return Student.objects.filter(**self.__class__.arg)

class StudentCommentView(ListView):
    model = Comment
    template_name = 'comments/list.html'
    context_object_name = 'posts'
    ordering = ['posted_by']

    def get_queryset(self):
        return Comment.objects.filter(posted_by=self.request.user)

class StudentCreateView(CreateView):
    model = Student
    form_class = StudentCreationForm
    template_name = 'student/new.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Check if there's uploaded data to pre-fill
        uploaded_data = self.request.session.pop('uploaded_student_data', None)
        if uploaded_data and not self.request.POST:
            initial = {}
            for key, value in uploaded_data.items():
                if key in context['form'].fields:
                    initial[key] = value
            context['form'].initial = initial
        return context

    def get_success_url(self):
        return reverse('list_student')

class StudentUploadView(FormView):
    form_class = StudentUploadForm
    template_name = 'student/upload.html'

    def form_valid(self, form):
        summary = handle_student_file(self.request.FILES["file"])
        messages.success(self.request, f"Processed {summary['processed']} rows — created {summary['created']}, updated {summary['updated']}.")
        if summary['errors']:
            for r, msg in summary['errors']:
                messages.error(self.request, f"Row {r}: {msg}")
        return super().form_valid(form)
    
    def get_success_url(self):
        return reverse('list_student')

class StudentDeleteView(DeleteView):
    model = User

    def get_success_url(self):
        return reverse('list_student')

class StudentUpdateView(UpdateView):
    model=Student
    form_class = StudentCreationForm
    template_name = 'student/update.html'

    def get_success_url(self):
        return reverse('list_student')

def SkillView(request):
    if request.method == 'POST':
        form=skillform(request.POST)
        if form.is_valid():
            instance=form.save(commit=False)
            instance.stud=Student.objects.get(user = request.user)
            instance.save()
            return redirect('/students/sprofile')
    else:        
        form=skillform()
    return render(request,'student/skillform.html',{'form':form})        

def sprofile(request):
    data=Student.objects.get(user=request.user)
    item=skills.objects.filter(stud=data)
    
    return render(request,'student/profile.html',{'data':data,'item':item})    

def AlumniList(request):
    if'q'in request.GET:
        q=request.GET['q']
        
        multiple_q=Q(Q(usn__icontains=q)|Q(name__icontains=q)|Q(branch__icontains=q)|Q(job__company_name__icontains=q)|Q(job__role__icontains=q)|Q(higherstudies__specialization__icontains=q)|Q(higherstudies__degree__icontains=q)|Q(higherstudies__college_name__icontains=q))
        data=Alumni.objects.filter(multiple_q).order_by('-usn')
        context={'alumni':data}
        return render(request,"student/alsearch.html",context)
    else:
        return render(request,"student/alsearch.html",)    

def chatbot(request):
    com=Job.objects.all().values('company_name').annotate(total=Count('id')).order_by('-total','company_name')[:1]
    alumni=Alumni.objects.all().count()
    uni=Higherstudies.objects.all().values('college_name').annotate(total=Count('id')).order_by('-total','college_name')[:1]
    context={
        'com':com,
        'uni':uni,
        'alumni':alumni,
    }
    return render(request,'student/chatbot.html',context)

@require_http_methods(["POST"])
def bulk_upload_students(request):
    if request.method == 'POST' and request.FILES.get('excel_file'):
        excel_file = request.FILES['excel_file']
        redirect_to = request.POST.get('redirect_to', 'new')  # 'new' or 'list'
        
        try:
            # Read Excel file
            # ✨ Only change needed: force pandas to use openpyxl
            df = pd.read_excel(excel_file, engine="openpyxl")
            
            # Expected columns (supporting both legacy RV and new RTC mail headers)
            base_required_columns = ['Name', 'USN', 'Phone', 'Email', 'Branch', 'Year_Joined']
            if not all(col in df.columns for col in base_required_columns):
                messages.error(request, f'Excel file must contain columns: {", ".join(base_required_columns + ["RTC_Email or RV_Email"])}')
                return redirect('new_student' if redirect_to == 'new' else 'list_student')
            
            # Determine which institutional email header is present
            has_rtc_email = 'RTC_Email' in df.columns
            has_rv_email = 'RV_Email' in df.columns
            if not (has_rtc_email or has_rv_email):
                messages.error(request, 'Excel file must contain either "RTC_Email" (preferred) or legacy "RV_Email" column.')
                return redirect('new_student' if redirect_to == 'new' else 'list_student')
            
            created_count = 0
            updated_count = 0
            error_count = 0
            error_details = []
            
            # Store last successful student data for form pre-filling
            last_successful_student = None
            
            # Iterate through rows and create/update Student objects
            for index, row in df.iterrows():
                try:
                    # Convert year_joined to proper date format
                    year_joined = row['Year_Joined']
                    if pd.notna(year_joined):
                        if isinstance(year_joined, (pd.Timestamp, datetime)):
                            year_joined = year_joined.date()
                        elif isinstance(year_joined, str):
                            year_joined = pd.to_datetime(year_joined).date()
                    else:
                        error_count += 1
                        error_details.append(f"Row {index + 2}: Year_Joined is missing")
                        continue
                    
                    rtc_email_value = _get_rtc_email_value(row)
                    if not rtc_email_value or pd.isna(rtc_email_value):
                        error_count += 1
                        error_details.append(f"Row {index + 2}: RTC college email (RTC_Email / RV_Email) is missing")
                        continue
                    
                    # Check if RTC (institutional) email already exists with a different USN
                    existing_student_by_email = Student.objects.filter(rv_email=rtc_email_value).first()
                    if existing_student_by_email and existing_student_by_email.usn != str(row['USN']):
                        error_count += 1
                        error_details.append(f"Row {index + 2}: RTC mail '{rtc_email_value}' already belongs to USN {existing_student_by_email.usn}")
                        continue
                    
                    # Check if personal Email already exists with a different USN
                    existing_student_by_personal_email = Student.objects.filter(email=row['Email']).first()
                    if existing_student_by_personal_email and existing_student_by_personal_email.usn != str(row['USN']):
                        error_count += 1
                        error_details.append(f"Row {index + 2}: Email '{row['Email']}' already belongs to USN {existing_student_by_personal_email.usn}")
                        continue
                    
                    # Check if user already exists with this USN
                    user_exists = User.objects.filter(username=row['USN']).first()
                    
                    if user_exists:
                        # UPDATE existing student
                        try:
                            student = Student.objects.get(user=user_exists)
                            student.name = row['Name']
                            student.usn = row['USN']
                            student.phone = row['Phone']
                            student.rv_email = rtc_email_value
                            student.email = row['Email']
                            student.branch = row['Branch']
                            student.year_joined = year_joined
                            student.save()
                            
                            # Also update user email
                            user_exists.email = row['Email']
                            user_exists.save()
                            
                            updated_count += 1
                            last_successful_student = {
                                'name': row['Name'],
                                'usn': row['USN'],
                                'phone': row['Phone'],
                                'rv_email': rtc_email_value,
                                'email': row['Email'],
                                'branch': row['Branch'],
                                'year_joined': year_joined.strftime('%Y-%m-%d') if hasattr(year_joined, 'strftime') else str(year_joined)
                            }
                        except Student.DoesNotExist:
                            # User exists but no Student profile
                            Student.objects.create(
                                user=user_exists,
                                name=row['Name'],
                                usn=row['USN'],
                                phone=row['Phone'],
                                rv_email=rtc_email_value,
                                email=row['Email'],
                                branch=row['Branch'],
                                year_joined=year_joined
                            )
                            created_count += 1
                            last_successful_student = {
                                'name': row['Name'],
                                'usn': row['USN'],
                                'phone': row['Phone'],
                                'rv_email': rtc_email_value,
                                'email': row['Email'],
                                'branch': row['Branch'],
                                'year_joined': year_joined.strftime('%Y-%m-%d') if hasattr(year_joined, 'strftime') else str(year_joined)
                            }
                    else:
                        # CREATE new user and student
                        user = User.objects.create_user(
                            username=row['USN'],
                            email=row['Email'],
                            password='changeme123'  # Default password
                        )
                        
                        Student.objects.create(
                            user=user,
                            name=row['Name'],
                            usn=row['USN'],
                            phone=row['Phone'],
                            rv_email=rtc_email_value,
                            email=row['Email'],
                            branch=row['Branch'],
                            year_joined=year_joined
                        )
                        created_count += 1
                        last_successful_student = {
                            'name': row['Name'],
                            'usn': row['USN'],
                            'phone': row['Phone'],
                            'rv_email': rtc_email_value,
                            'email': row['Email'],
                            'branch': row['Branch'],
                            'year_joined': year_joined.strftime('%Y-%m-%d') if hasattr(year_joined, 'strftime') else str(year_joined)
                        }
                        
                except IntegrityError as e:
                    error_count += 1
                    error_details.append(f"Row {index + 2}: Database constraint error - {str(e)}")
                except Exception as e:
                    error_count += 1
                    error_details.append(f"Row {index + 2}: {str(e)}")
            
            # Store upload summary in session
            upload_summary = {
                'total': len(df),
                'created': created_count,
                'updated': updated_count,
                'errors': error_count
            }
            
            # Store last successful student data in session for form pre-filling
            if last_successful_student and redirect_to == 'new':
                request.session['uploaded_student_data'] = last_successful_student
            
            # Success messages
            if created_count > 0:
                messages.success(request, f'Successfully created {created_count} new student records.')
            if updated_count > 0:
                messages.success(request, f'Successfully updated {updated_count} existing student records.')
            
            # Error messages
            if error_count > 0:
                messages.warning(request, f'{error_count} records failed to process.')
                for error_msg in error_details[:10]:  # Show first 10 errors
                    messages.error(request, error_msg)
                if len(error_details) > 10:
                    messages.error(request, f'... and {len(error_details) - 10} more errors.')
            
            # If nothing happened
            if created_count == 0 and updated_count == 0 and error_count == 0:
                messages.info(request, 'No records were processed.')
            
            # Store summary in session for list page display
            if redirect_to == 'list':
                request.session['upload_summary'] = upload_summary
                return redirect('list_student')
            else:
                return redirect('new_student')
            
        except Exception as e:
            messages.error(request, f'Error processing file: {str(e)}')
            return redirect('new_student' if redirect_to == 'new' else 'list_student')
    else:
        messages.error(request, 'No file uploaded.')
        return redirect('new_student')
