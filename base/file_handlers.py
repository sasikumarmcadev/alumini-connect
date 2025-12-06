from django.forms import ValidationError
import io
import pandas as pd
from datetime import datetime
from django.contrib.auth.models import User, Group


def _read_table_from_upload(uploaded_file):
    name = uploaded_file.name.lower()
    # pandas accepts file-like objects for CSV; for Excel we must read bytes
    if name.endswith('.csv'):
        # uploaded_file may be InMemoryUploadedFile or TemporaryUploadedFile
        try:
            df = pd.read_csv(uploaded_file)
        except Exception:
            # try reading bytes (some upload types require this)
            content = uploaded_file.read()
            df = pd.read_csv(io.BytesIO(content))
    elif name.endswith(('.xls', '.xlsx')):
        content = uploaded_file.read()
        # prefer openpyxl for xlsx
        df = pd.read_excel(io.BytesIO(content), engine='openpyxl')
    else:
        raise ValidationError(f"Unsupported file type: {uploaded_file.name}")
    return df


def handle_student_file(uploaded_file):
    # import models locally to avoid circular import during module import
    from student.models import Student

    df = _read_table_from_upload(uploaded_file)
    processed = 0
    created = 0
    updated = 0
    errors = []
    for idx, row in df.iterrows():
        processed += 1
        try:
            usn = str(row.get('USN')).strip()
            name = str(row.get('FULL NAME')).strip()
            phone = str(row.get('PHONE')).strip()
            rv_email = row.get('RVCE Mail ID')
            email = row.get('EMAIL')
            branch = row.get('BRANCH')
            year_joined = row.get('YEAR JOIN')

            if not usn or not name or not email:
                errors.append((idx + 1, 'Missing required fields'))
                continue

            username = str(email).strip()
            user, user_created = User.objects.get_or_create(
                username=username,
                defaults={'email': email},
            )
            if user_created:
                user.set_password('anteater')
                user.save()
            students_group, _ = Group.objects.get_or_create(name='students')
            students_group.user_set.add(user)

            obj, was_created = Student.objects.get_or_create(
                usn=usn,
                defaults={
                    'name': name,
                    'phone': phone,
                    'rv_email': rv_email,
                    'email': email,
                    'year_joined': year_joined,
                    'branch': branch,
                    'user': user,
                },
            )
            if was_created:
                created += 1
            else:
                obj.name = name
                obj.phone = phone
                obj.rv_email = rv_email
                obj.email = email
                obj.year_joined = year_joined
                obj.branch = branch
                obj.user = user
                obj.save()
                updated += 1
        except Exception as e:
            errors.append((idx + 1, str(e)))

    return {'processed': processed, 'created': created, 'updated': updated, 'errors': errors}


def handle_alumni_file(uploaded_file):
    # import models locally to avoid circular import during module import
    from alumni.models import Alumni

    df = _read_table_from_upload(uploaded_file)
    processed = 0
    created = 0
    updated = 0
    errors = []
    for idx, row in df.iterrows():
        processed += 1
        try:
            usn = str(row.get('USN')).strip()
            name = str(row.get('Name')).strip()
            phone = str(row.get('Phone')).strip()
            email = row.get('RV Email') or row.get('Email')
            branch = row.get('Department')
            year_join = row.get('Year Join') or row.get('Year Join')
            year_pass = row.get('Year Pass') or row.get('Year Pass')
            personal_email = row.get('Personal Email')
            company_name = row.get('Company Name')
            ctc = row.get('CTC')
            type_ = row.get('Type')
            job_profile = row.get('Job Profile')

            if not usn or not name or not email:
                errors.append((idx + 1, 'Missing required fields'))
                continue

            username = str(email).strip()
            user, user_created = User.objects.get_or_create(
                username=username,
                defaults={'email': email},
            )
            if user_created:
                user.set_password('anteater')
                user.save()
            alumni_group, _ = Group.objects.get_or_create(name='alumni')
            alumni_group.user_set.add(user)

            # parse years if present
            try:
                if year_join:
                    year_joined = pd.to_datetime(year_join).date()
                else:
                    year_joined = None
            except Exception:
                year_joined = None
            try:
                if year_pass:
                    year_passed = pd.to_datetime(year_pass).date()
                else:
                    year_passed = None
            except Exception:
                year_passed = None

            obj, was_created = Alumni.objects.get_or_create(
                usn=usn,
                defaults={
                    'name': name,
                    'phone': phone,
                    'email': email,
                    'personal_email': personal_email,
                    'job_profile': job_profile,
                    'type': type_,
                    'ctc': ctc,
                    'company_name': company_name,
                    'year_joined': year_joined,
                    'year_passed': year_passed,
                    'branch': branch,
                    'user': user,
                },
            )
            if was_created:
                created += 1
            else:
                obj.user = user
                obj.name = name
                obj.phone = phone
                obj.email = email
                obj.personal_email = personal_email
                obj.job_profile = job_profile
                obj.type = type_
                obj.ctc = ctc
                obj.company_name = company_name
                obj.year_joined = year_joined
                obj.year_passed = year_passed
                obj.branch = branch
                obj.save()
                updated += 1
        except Exception as e:
            errors.append((idx + 1, str(e)))

    return {'processed': processed, 'created': created, 'updated': updated, 'errors': errors}


# Backwards-compatible wrappers for older imports
def handle_student_csv(uploaded_file):
    return handle_student_file(uploaded_file)


def handle_alumni_csv(uploaded_file):
    return handle_alumni_file(uploaded_file)
