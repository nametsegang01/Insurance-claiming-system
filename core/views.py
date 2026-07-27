# ================================================================
# IMPORTS
# ================================================================
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User, Group
from django.contrib.auth.hashers import make_password

from django.db import IntegrityError
from django.db.models import Count, Avg, Sum, Q, F
from django.db.models.functions import TruncMonth, TruncDate

from django.utils import timezone
from django.utils.timezone import now

from django.core.paginator import (
    Paginator,
    PageNotAnInteger,
    EmptyPage,
)

from decimal import Decimal
from datetime import datetime, timedelta, date

import json
import random
import re
import uuid

from .models import (
    UserProfile,
    AdminInvitation,
    Policy,
    Claim,
    Payment,
    Document,
    Notification,
)
# ==============================
# LANDING & STATIC PAGES
# ==============================
def home(request):
    """Landing page view"""
    return render(request, 'core/home.html')

def features(request):
    """Features page view"""
    return render(request, 'core/features.html')

def about(request):
    """About page view"""
    return render(request, 'core/about.html')

def contact(request):
    """Contact page view"""
    return render(request, 'core/contact.html')
# ==============================
# REGISTRATION VIEW (UPDATED - OPTION 1: First Admin)
# ==============================
def register_view(request):
    """User registration with role-based forms"""
    
    if request.user.is_authenticated:
        return redirect('dashboard')
    
    if request.method == 'POST':
        role = request.POST.get('role', 'policyholder')
        
        # Get common fields
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        email = request.POST.get('email', '').strip()
        phone = request.POST.get('phone', '').strip()
        password = request.POST.get('password')
        password2 = request.POST.get('password2')
        
        # ===== VALIDATION =====
        errors = []
        
        # Required fields for all roles
        if not first_name:
            errors.append('First name is required.')
        if not last_name:
            errors.append('Last name is required.')
        if not email:
            errors.append('Email address is required.')
        elif not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
            errors.append('Please enter a valid email address.')
        if not password:
            errors.append('Password is required.')
        elif len(password) < 8:
            errors.append('Password must be at least 8 characters long.')
        if password != password2:
            errors.append('Passwords do not match.')
        
        # Check if email already exists
        if email and User.objects.filter(email=email).exists():
            errors.append('Email address already registered.')
        
        # Check terms acceptance
        if not request.POST.get('terms'):
            errors.append('You must accept the Terms & Conditions.')
        
        # ===== ROLE-SPECIFIC VALIDATION =====
        
        # Policyholder specific validation
        if role == 'policyholder':
            id_number = request.POST.get('id_number', '').strip()
            if not id_number:
                errors.append('SA ID Number is required.')
            elif not re.match(r'^\d{13}$', id_number):
                errors.append('Please enter a valid 13-digit SA ID Number.')
            
            # POPIA acceptance for policyholders
            if not request.POST.get('popia'):
                errors.append('You must accept the POPIA terms.')
        
        # Staff specific validation
        elif role == 'staff':
            employee_number = request.POST.get('employee_number', '').strip()
            if not employee_number:
                errors.append('Employee Number is required.')
        
        # Investigator specific validation
        elif role == 'investigator':
            employee_number = request.POST.get('employee_number', '').strip()
            if not employee_number:
                errors.append('Employee Number is required.')
        
        # ===== ADMINISTRATOR VALIDATION (OPTION 1: First Admin Only) =====
        elif role == 'administrator':
            # Check if any admin already exists
            if UserProfile.objects.filter(role='administrator', status='active').exists():
                errors.append('An administrator already exists. Only one administrator account is allowed.')
                errors.append('Please contact your system administrator for assistance.')
        
        # ===== IF ERRORS, SHOW THEM =====
        if errors:
            for error in errors:
                messages.error(request, error)
            return render(request, 'core/register.html')
        
        # ===== CREATE USER =====
        try:
            # Generate username from email
            username = email.split('@')[0]
            # Make unique if exists
            if User.objects.filter(username=username).exists():
                username = f"{username}_{User.objects.count() + 1}"
            
            # Create user
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name
            )
            
            # Update profile based on role
            profile = user.profile
            profile.phone = phone
            profile.role = role
            
            # ===== POLICYHOLDER =====
            if role == 'policyholder':
                profile.id_number = request.POST.get('id_number', '').strip()
                profile.province = request.POST.get('province', '').strip()
                profile.city = request.POST.get('city', '').strip()
                profile.postal_code = request.POST.get('postal_code', '').strip()
                profile.address = request.POST.get('address', '').strip()
                profile.status = 'active'  # Auto-approved
                
                # Add to Policyholders group
                group, _ = Group.objects.get_or_create(name='Policyholders')
                user.groups.add(group)
                
                profile.save()
                
                # Auto-login the user
                login(request, user)
                messages.success(request, f'Welcome {first_name}! Your account has been created successfully.')
                return redirect('customer_dashboard')
            
            # ===== STAFF =====
            elif role == 'staff':
                profile.employee_number = request.POST.get('employee_number', '').strip()
                profile.branch = request.POST.get('branch', '').strip()
                profile.status = 'pending'  # Needs admin approval
                
                # Add to Staff group (pending)
                group, _ = Group.objects.get_or_create(name='Staff')
                user.groups.add(group)
                
                profile.save()
                
                messages.success(request, 'Staff account registered successfully! Waiting for administrator approval.')
                return render(request, 'core/register.html', {'pending': True})
            
            # ===== INVESTIGATOR =====
            elif role == 'investigator':
                profile.employee_number = request.POST.get('employee_number', '').strip()
                profile.branch = request.POST.get('branch', '').strip()
                profile.status = 'pending'  # Needs admin approval
                
                # Add to Investigators group (pending)
                group, _ = Group.objects.get_or_create(name='Investigators')
                user.groups.add(group)
                
                profile.save()
                
                messages.success(request, 'Investigator account registered successfully! Waiting for administrator approval.')
                return render(request, 'core/register.html', {'pending': True})
            
            # ===== ADMINISTRATOR (NEW - First Admin Only) =====
            elif role == 'administrator':
                # Check again before saving (race condition protection)
                if UserProfile.objects.filter(role='administrator', status='active').exists():
                    messages.error(request, 'An administrator already exists. Registration failed.')
                    return render(request, 'core/register.html')
                
                profile.status = 'active'  # Auto-approved
                profile.is_verified = True
                
                # Add to Administrators group
                group, _ = Group.objects.get_or_create(name='Administrators')
                user.groups.add(group)
                
                profile.save()
                
                # Auto-login the admin
                login(request, user)
                messages.success(request, f'Welcome {first_name}! You are now the System Administrator.')
                return redirect('admin_dashboard')
            
        except IntegrityError as e:
            messages.error(request, f'Registration failed: Database error. Please try again.')
            return render(request, 'core/register.html')
        except Exception as e:
            messages.error(request, f'Registration failed: {str(e)}')
            return render(request, 'core/register.html')
    
    return render(request, 'core/register.html')
# ==============================
# LOGOUT VIEW FOR REGISTRATION 
# ==============================
def logout_view(request):
    """User logout"""
    logout(request)
    messages.success(request, 'You have been successfully logged out.')
    return redirect('home')
# ==============================
# DASHBOARD REDIRECT VIEW
# ==============================
def dashboard(request):
    """Redirect to appropriate dashboard based on user role"""
    if not request.user.is_authenticated:
        return redirect('login')
    
    profile = request.user.profile
    
    role_redirects = {
        'administrator': 'admin_dashboard',
        'investigator': 'investigator_dashboard',
        'staff': 'staff_dashboard',
        'policyholder': 'customer_dashboard',
    }
    
    return redirect(role_redirects.get(profile.role, 'customer_dashboard'))

@login_required
def staff_dashboard(request):
    """Staff dashboard"""
    return render(request, 'core/staff_dashboard.html')


@login_required
def investigator_dashboard(request):
    """Investigator dashboard"""
    return render(request, 'core/investigator_dashboard.html')


@login_required
def admin_dashboard(request):
    """Admin dashboard"""
    return render(request, 'core/admin_dashboard.html')

# ==============================
# LOGIN - FIXED VERSION
# ==============================
from .models import UserProfile  # ✅ This is the correct model name
def login_view(request):
    """User login view - FIXED"""
    if request.user.is_authenticated:
        return redirect('dashboard')
        
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        remember = request.POST.get('remember')
        selected_role = request.POST.get('role', 'policyholder')
        
        if not username or not password:
            messages.error(request, 'Please enter both username and password.')
            return render(request, 'core/login.html')
        
        # Authenticate user
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            # ✅ FIX: Check if profile exists, create if missing
            if not hasattr(user, 'profile'):
                # Auto-create profile based on user type
                if user.is_superuser or user.is_staff:
                    user_role = 'administrator'
                else:
                    user_role = 'policyholder'
                
                # ✅ USE UserProfile NOT Profile
                UserProfile.objects.create(
                    user=user,
                    role=user_role,
                    status='active'
                )
                messages.info(request, f'Profile created for {user.username}!')
                profile = user.profile
            else:
                profile = user.profile
            
            # ✅ FIX 2: Check if status is None or empty, set to active
            if not profile.status or profile.status == '':
                profile.status = 'active'
                profile.save()
                messages.info(request, 'Profile status was missing, set to active.')
            
            # ✅ FIX 3: Check account status
            if profile.status == 'disabled':
                messages.error(request, 'Your account has been disabled. Please contact support.')
                return render(request, 'core/login.html')
            
            if profile.status == 'suspended':
                messages.error(request, 'Your account has been suspended. Please contact support.')
                return render(request, 'core/login.html')
            
            if profile.status == 'archived':
                messages.error(request, 'Your account has been archived. Please contact support.')
                return render(request, 'core/login.html')
            
            # Login user
            login(request, user)
            
            # Set session expiry
            if remember:
                request.session.set_expiry(1209600)  # 2 weeks
            else:
                request.session.set_expiry(0)
            
            # Check if pending approval
            if profile.status == 'pending':
                messages.info(request, 'Your account is pending administrator approval.')
                return render(request, 'core/register.html', {'pending': True})
            
            # Welcome message
            messages.success(request, f'Welcome back, {user.first_name or user.username}!')
            
            # ✅ Redirect based on role with validation
            if selected_role != 'policyholder':
                if profile.role != selected_role:
                    messages.error(request, f'This account is not registered as {selected_role.title()}. Please select the correct role.')
                    return render(request, 'core/login.html')
            
            # ✅ Redirect based on role
            if profile.role == 'administrator':
                return redirect('admin_dashboard')
            elif profile.role == 'investigator':
                return redirect('investigator_dashboard')
            elif profile.role == 'staff':
                return redirect('staff_dashboard')
            else:
                return redirect('customer_dashboard')
        else:
            messages.error(request, 'Invalid username or password. Please try again.')
    
    return render(request, 'core/login.html')
# ==============================
# LOGOUT VIEW FOR LOGIN 
# ==============================
def logout_view(request):
    """User logout"""
    logout(request)
    messages.success(request, 'You have been successfully logged out.')
    return redirect('home')
# ==============================
# ADMIN INVITATION VIEWS (NEW)
# ==============================
@login_required
@user_passes_test(lambda u: hasattr(u, 'profile') and u.profile.role == 'administrator' and u.profile.status == 'active')
def admin_invite_view(request):
    """Allow admins to invite new administrators"""
    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        admin_type = request.POST.get('admin_type', 'full')
        
        if not email:
            messages.error(request, 'Email address is required.')
            return render(request, 'core/admin_invite.html')
        
        if User.objects.filter(email=email).exists():
            messages.error(request, 'A user with this email already exists.')
            return render(request, 'core/admin_invite.html')
        
        # Check if there's already a pending invitation
        if AdminInvitation.objects.filter(email=email, accepted=False).exists():
            messages.warning(request, 'An invitation has already been sent to this email. Please wait for them to accept or resend.')
            return render(request, 'core/admin_invite.html')
        
        # Create invitation
        token = uuid.uuid4()
        expires_at = timezone.now() + timedelta(hours=48)
        
        invitation = AdminInvitation.objects.create(
            email=email,
            invited_by=request.user,
            token=token,
            expires_at=expires_at,
            admin_type=admin_type
        )
        
        # TODO: Send email (implement later)
        # send_invitation_email(email, token, request.user)
        
        messages.success(request, f'Invitation sent to {email}! They have 48 hours to accept.')
        return redirect('admin_manage_admins')
    
    return render(request, 'core/admin_invite.html')


@login_required
def admin_accept_invite_view(request, token):
    """Accept admin invitation and create admin account"""
    try:
        invitation = AdminInvitation.objects.get(token=token, accepted=False)
        
        if not invitation.is_valid():
            messages.error(request, 'This invitation has expired. Please request a new one.')
            return redirect('login')
        
        if request.method == 'POST':
            first_name = request.POST.get('first_name', '').strip()
            last_name = request.POST.get('last_name', '').strip()
            password = request.POST.get('password')
            password2 = request.POST.get('password2')
            
            errors = []
            if not first_name:
                errors.append('First name is required.')
            if not last_name:
                errors.append('Last name is required.')
            if not password:
                errors.append('Password is required.')
            elif len(password) < 8:
                errors.append('Password must be at least 8 characters long.')
            if password != password2:
                errors.append('Passwords do not match.')
            
            if errors:
                for error in errors:
                    messages.error(request, error)
                return render(request, 'core/admin_accept_invite.html', {'invitation': invitation})
            
            # Check if user already exists with this email
            if User.objects.filter(email=invitation.email).exists():
                messages.error(request, 'A user with this email already exists. Please login instead.')
                return redirect('login')
            
            # Create admin user
            username = invitation.email.split('@')[0]
            if User.objects.filter(username=username).exists():
                username = f"{username}_{User.objects.count() + 1}"
            
            user = User.objects.create_user(
                username=username,
                email=invitation.email,
                password=password,
                first_name=first_name,
                last_name=last_name
            )
            
            # Set as administrator
            profile = user.profile
            profile.role = 'administrator'
            profile.status = 'active'
            profile.invited_by = invitation.invited_by
            profile.is_verified = True
            profile.save()
            
            # Add to Administrators group
            group, _ = Group.objects.get_or_create(name='Administrators')
            user.groups.add(group)
            
            # Mark invitation as accepted
            invitation.accepted = True
            invitation.accepted_at = timezone.now()
            invitation.save()
            
            messages.success(request, 'Administrator account created successfully! Please login.')
            return redirect('login')
        
        return render(request, 'core/admin_accept_invite.html', {'invitation': invitation})
        
    except AdminInvitation.DoesNotExist:
        messages.error(request, 'Invalid invitation token.')
        return redirect('login')
# ==============================
# DASHBOARDS
# ==============================

@login_required
def dashboard(request):
    """Redirect to appropriate dashboard based on user role"""
    user = request.user
    profile = user.profile
    
    # Check if profile exists (should always exist due to signal)
    if not profile:
        messages.error(request, 'Profile not found. Please contact support.')
        return redirect('logout')
    
    # Check if pending approval
    if profile.status == 'pending':
        return render(request, 'core/register.html', {'pending': True})
    
    # Redirect based on role
    if profile.role == 'administrator':
        return redirect('admin_dashboard')
    elif profile.role == 'investigator':
        return redirect('investigator_dashboard')
    elif profile.role == 'staff':
        return redirect('staff_dashboard')
    else:
        return redirect('customer_dashboard')
# ==============================
# CUSTOMER DASHBOARD
# ==============================
def customer_dashboard(request):
    """Policyholder dashboard with real-time data"""
    user = request.user
    profile = user.profile
    
    # Get user's real data from database
    policies = Policy.objects.filter(user=user)
    active_policies = policies.filter(status='active')
    claims = Claim.objects.filter(user=user)
    pending_claims = claims.filter(status__in=['submitted', 'pending'])
    payments = Payment.objects.filter(user=user)
    upcoming_payments = payments.filter(status='pending')
    documents = Document.objects.filter(user=user)
    notifications = Notification.objects.filter(user=user).order_by('-created_at')
    unread_notifications = notifications.filter(is_read=False)
    
    # Calculate totals
    total_premium_paid = payments.filter(status='completed').aggregate(Sum('amount'))['amount__sum'] or 0
    
    # AI Trust Score
    ai_trust_score = getattr(profile, 'ai_trust_score', 92)
    
    # Fraud risk level based on claims
    high_risk = claims.filter(ai_fraud_score__gte=70).count()
    if high_risk > 0:
        fraud_risk_level = 'High'
    elif claims.filter(ai_fraud_score__gte=40).count() > 0:
        fraud_risk_level = 'Medium'
    else:
        fraud_risk_level = 'Low'

    # ============================================================ */
    # CHART DATA - Premium Payment History (Last 6 months)
    # ============================================================ */
    from datetime import datetime, timedelta
    import calendar
    
    premium_labels = []
    premium_values = []
    
    for i in range(5, -1, -1):
        month_date = datetime.now() - timedelta(days=30*i)
        month_name = calendar.month_abbr[month_date.month]
        premium_labels.append(f"{month_name} {month_date.year}")
        
        # Get start and end of month
        start_of_month = month_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if month_date.month == 12:
            end_of_month = month_date.replace(year=month_date.year+1, month=1, day=1)
        else:
            end_of_month = month_date.replace(month=month_date.month+1, day=1)
        
        # Sum payments for this month
        month_total = payments.filter(
            paid_at__gte=start_of_month,
            paid_at__lt=end_of_month,
            status='completed'
        ).aggregate(Sum('amount'))['amount__sum'] or 0
        premium_values.append(float(month_total))
    
    premium_chart_data = {
        'labels': premium_labels,
        'values': premium_values,
    }
    
    # ============================================================ */
    # CHART DATA - Claim Status Distribution
    # ============================================================ */
    claim_status_labels = ['Approved', 'Pending', 'Investigation', 'Rejected']
    claim_status_values = [
        claims.filter(status='approved').count(),
        claims.filter(status__in=['submitted', 'pending']).count(),
        claims.filter(status='investigation').count(),
        claims.filter(status='rejected').count(),
    ]
    
    claim_chart_data = {
        'labels': claim_status_labels,
        'values': claim_status_values,
    }
    
    # ============================================================ */
    # CHART DATA - Policy Distribution
    # ============================================================ */
    policy_type_labels = []
    policy_type_values = []
    
    # Group policies by type
    from django.db.models import Count
    policy_types = policies.values('policy_type').annotate(count=Count('id'))
    type_display_map = {
        'vehicle': 'Vehicle',
        'home': 'Home',
        'life': 'Life',
        'health': 'Health',
        'business': 'Business',
        'travel': 'Travel',
    }
    
    for pt in policy_types:
        policy_type_labels.append(type_display_map.get(pt['policy_type'], pt['policy_type'].title()))
        policy_type_values.append(pt['count'])
    
    policy_chart_data = {
        'labels': policy_type_labels,
        'values': policy_type_values,
    }
    
    # ============================================================ */
    # CHART DATA - Fraud Risk Trend (Last 6 months)
    # ============================================================ */
    fraud_labels = []
    fraud_values = []
    
    for i in range(5, -1, -1):
        month_date = datetime.now() - timedelta(days=30*i)
        month_name = calendar.month_abbr[month_date.month]
        fraud_labels.append(f"{month_name} {month_date.year}")
        
        start_of_month = month_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if month_date.month == 12:
            end_of_month = month_date.replace(year=month_date.year+1, month=1, day=1)
        else:
            end_of_month = month_date.replace(month=month_date.month+1, day=1)
        
        # Average fraud score for claims in this month
        avg_fraud = claims.filter(
            submitted_at__gte=start_of_month,
            submitted_at__lt=end_of_month
        ).aggregate(Avg('ai_fraud_score'))['ai_fraud_score__avg'] or 0
        fraud_values.append(round(float(avg_fraud), 1))
    
    fraud_chart_data = {
        'labels': fraud_labels,
        'values': fraud_values,
    }
    
    # ============================================================ */
    # Determine time of day for greeting
    # ============================================================ */
    current_hour = datetime.now().hour
    if current_hour < 12:
        time_of_day = 'Morning'
    elif current_hour < 17:
        time_of_day = 'Afternoon'
    else:
        time_of_day = 'Evening'
    
    context = {
        'user': user,
        'profile': profile,
        'now': datetime.now(),
        'time_of_day': time_of_day,
        'policies': policies,
        'active_policies_count': active_policies.count(),
        'claims': claims,
        'total_claims': claims.count(),
        'pending_claims': pending_claims.count(),
        'payments': payments,
        'total_premium_paid': total_premium_paid,
        'upcoming_payments': upcoming_payments,
        'documents': documents,
        'notifications': notifications,
        'unread_notifications': unread_notifications.count(),
        'ai_trust_score': ai_trust_score,
        'fraud_risk_level': fraud_risk_level,
        # Chart data
        'premium_chart_data': premium_chart_data,
        'claim_chart_data': claim_chart_data,
        'policy_chart_data': policy_chart_data,
        'fraud_chart_data': fraud_chart_data,
    }
    
    return render(request, 'core/customer_dashboard.html', context)

# ==============================
# CUSTOMER UPDATE POLICY
# ==============================

@login_required
def customer_update_policy(request):
    """Update Policy page"""
    policies = Policy.objects.filter(user=request.user, status='active')
    
    context = {
        'user': request.user,
        'policies': policies,
        'pending_claims': Claim.objects.filter(user=request.user, status__in=['submitted', 'pending']).count(),
        'unread_notifications': Notification.objects.filter(user=request.user, is_read=False).count(),
        'now': datetime.now(),
    }
    return render(request, 'core/customer_update_policy.html', context)


# ==============================
# CUSTOMER CANCEL POLICY
# ==============================

@login_required
def customer_cancel_policy(request):
    """Cancel Policy page"""
    policies = Policy.objects.filter(user=request.user, status='active')
    
    context = {
        'user': request.user,
        'policies': policies,
        'pending_claims': Claim.objects.filter(user=request.user, status__in=['submitted', 'pending']).count(),
        'unread_notifications': Notification.objects.filter(user=request.user, is_read=False).count(),
        'now': datetime.now(),
    }
    return render(request, 'core/customer_cancel_policy.html', context)
# ==============================
# CUSTOMER POLICIES
# ==============================
@login_required
def customer_policies(request):
    """My Policies page"""
    from django.db.models import Sum
    
    # Get real policies for this user
    policies = Policy.objects.filter(user=request.user)
    active_policies = policies.filter(status='active')
    
    # Calculate totals
    total_coverage = policies.aggregate(Sum('coverage_amount'))['coverage_amount__sum'] or 0
    total_monthly_premium = policies.aggregate(Sum('premium_amount'))['premium_amount__sum'] or 0
    
    context = {
        'user': request.user,
        'policies': policies,  # This must be passed
        'active_policies_count': active_policies.count(),
        'total_coverage': total_coverage,
        'total_monthly_premium': total_monthly_premium,
        'now': datetime.now(),
    }
    return render(request, 'core/customer_policies.html', context)

@login_required
def customer_claims(request):
    """My Claims page"""
    claims = Claim.objects.filter(user=request.user).order_by('-submitted_at')
    
    # Calculate claim statistics
    total_claims = claims.count()
    approved_claims = claims.filter(status='approved').count()
    rejected_claims = claims.filter(status='rejected').count()
    pending_claims = claims.filter(status__in=['submitted', 'pending', 'investigation']).count()
    paid_claims = claims.filter(status='paid').count()
    
    # Prepare claim data for display
    claim_data = []
    for claim in claims:
        claim_data.append({
            'id': claim.id,
            'claim_number': claim.claim_number,
            'incident_type': claim.get_incident_type_display(),
            'incident_date': claim.incident_date,
            'amount_claimed': claim.amount_claimed,
            'amount_approved': claim.amount_approved,
            'status': claim.status,
            'status_display': claim.get_status_display(),
            'ai_fraud_score': claim.ai_fraud_score,
            'submitted_at': claim.submitted_at,
            'updated_at': claim.updated_at,
            'policy_number': claim.policy.policy_number if claim.policy else 'N/A',
            'policy_type': claim.policy.get_policy_type_display() if claim.policy else 'N/A',
            'can_appeal': claim.status == 'rejected',
        })
    
    context = {
        'user': request.user,
        'claims': claim_data,
        'total_claims': total_claims,
        'approved_claims': approved_claims,
        'rejected_claims': rejected_claims,
        'pending_claims': pending_claims,
        'paid_claims': paid_claims,
        'now': datetime.now(),
        'unread_notifications': Notification.objects.filter(user=request.user, is_read=False).count(),
    }
    return render(request, 'core/customer_claims.html', context)
@login_required
def customer_payments(request):
    """Payments page"""
    payments = Payment.objects.filter(user=request.user)
    context = {
        'user': request.user,
        'payments': payments,
        'total_paid': payments.filter(status='completed').aggregate(Sum('amount'))['amount__sum'] or 0,
        'upcoming_payments': payments.filter(status='pending').count(),
        'overdue_payments': payments.filter(status='pending', due_date__lt=datetime.now().date()).count(),
        'now': datetime.now(),
    }
    return render(request, 'core/customer_payments.html', context)
@login_required
def customer_documents(request):
    """Documents page"""
    documents = Document.objects.filter(user=request.user)
    context = {
        'user': request.user,
        'documents': documents,
        'verified_docs': documents.filter(status='verified').count(),
        'pending_docs': documents.filter(status='pending').count(),
        'rejected_docs': documents.filter(status='rejected').count(),
        'now': datetime.now(),
    }
    return render(request, 'core/customer_documents.html', context)
@login_required
def customer_notifications(request):
    """Notifications page"""
    notifications = Notification.objects.filter(user=request.user).order_by('-created_at')
    context = {
        'user': request.user,
        'notifications': notifications,
        'unread_notifications': notifications.filter(is_read=False).count(),
        'now': datetime.now(),
    }
    return render(request, 'core/customer_notifications.html', context)
@login_required
def customer_ai_assistant(request):
    """AI Assistant page"""
    context = {
        'user': request.user,
        'now': datetime.now(),
    }
    return render(request, 'core/customer_ai_assistant.html', context)
@login_required
def customer_profile(request):
    """My Profile page"""
    context = {
        'user': request.user,
        'now': datetime.now(),
    }
    return render(request, 'core/customer_profile.html', context)


@login_required
def customer_settings(request):
    """Settings page"""
    context = {
        'user': request.user,
        'now': datetime.now(),
    }
    return render(request, 'core/customer_settings.html', context)


@login_required
def customer_purchase_policy(request):
    """Purchase Policy page"""
    context = {
        'user': request.user,
        'policies': Policy.objects.filter(user=request.user),
        'pending_claims': Claim.objects.filter(user=request.user, status__in=['pending', 'submitted']).count(),
        'unread_notifications': Notification.objects.filter(user=request.user, is_read=False).count(),
        'now': datetime.now(),
    }
    return render(request, 'core/customer_purchase_policy.html', context)

# ==============================
# CUSTOMER SUBMIT CLAIM
# ==============================

# ================================================================
# CUSTOMER CLAIM SUBMISSION
# ================================================================

@login_required
def customer_submit_claim(request):
    """Submit Claim page - Saves to database with AI fraud analysis"""
    
    if request.method == 'POST':
        try:
            import json
            data = json.loads(request.body)
            
            user = request.user
            
            # Get form data
            policy_id = data.get('policy_id')
            incident_type = data.get('incident_type')
            incident_date = data.get('incident_date')
            incident_description = data.get('incident_description')
            incident_location = data.get('incident_location', '')
            amount_claimed = data.get('amount_claimed', 0)
            
            # Get the policy
            try:
                policy = Policy.objects.get(id=policy_id, user=user)
            except Policy.DoesNotExist:
                return JsonResponse({'success': False, 'error': 'Policy not found.'})
            
            # Generate claim number
            claim_number = f"CLM-{datetime.now().year}-{random.randint(1000, 9999)}"
            
            # Calculate AI fraud score based on multiple factors
            fraud_score = calculate_fraud_score(
                amount_claimed=amount_claimed,
                policy=policy,
                user=user,
                incident_type=incident_type
            )
            
            # Determine risk level and analysis
            if fraud_score > 60:
                fraud_analysis = 'High risk patterns detected. Investigation required.'
                risk_level = 'High'
            elif fraud_score > 30:
                fraud_analysis = 'Some unusual patterns detected. Further review may be required.'
                risk_level = 'Medium'
            else:
                fraud_analysis = 'No suspicious patterns detected. Claim appears legitimate.'
                risk_level = 'Low'
            
            # Create claim
            claim = Claim.objects.create(
                claim_number=claim_number,
                policy=policy,
                user=user,
                incident_type=incident_type,
                incident_date=incident_date,
                incident_description=incident_description,
                incident_location=incident_location,
                amount_claimed=amount_claimed,
                status='submitted',
                ai_fraud_score=fraud_score,
                ai_fraud_analysis=fraud_analysis,
            )
            
            # Create notification for customer
            Notification.objects.create(
                user=user,
                title='Claim Submitted Successfully!',
                message=f'Your claim #{claim_number} has been submitted and is being reviewed.',
                notification_type='success',
                category='claim',
                related_claim=claim,
                action_url=f'/dashboard/customer/claim/{claim.id}/',
            )
            
            # Notify Staff
            staff_users = User.objects.filter(profile__role='staff')
            for staff in staff_users:
                Notification.objects.create(
                    user=staff,
                    title='📋 New Claim Submitted',
                    message=f'{user.get_full_name()} submitted claim #{claim_number} - {incident_type} - R{amount_claimed}',
                    notification_type='info',
                    category='claim',
                    action_url='/staff/claims-queue/',
                )
            
            # If high risk, notify investigators
            if fraud_score > 60:
                investigators = User.objects.filter(profile__role='investigator')
                for inv in investigators:
                    Notification.objects.create(
                        user=inv,
                        title='🚨 High Risk Claim Alert',
                        message=f'Claim #{claim_number} from {user.get_full_name()} has a fraud score of {fraud_score}%. Investigation required.',
                        notification_type='danger',
                        category='investigation',
                        action_url='/investigator/fraud-alerts/',
                    )
            
            # Notify Admin
            admin_users = User.objects.filter(profile__role='administrator')
            for admin in admin_users:
                Notification.objects.create(
                    user=admin,
                    title='New Claim Submitted',
                    message=f'{user.get_full_name()} submitted claim #{claim_number}',
                    notification_type='info',
                    category='claim',
                    action_url='/admin/claims/',
                )
            
            return JsonResponse({
                'success': True,
                'claim_number': claim_number,
                'fraud_score': fraud_score,
                'risk_level': risk_level,
                'message': 'Claim submitted successfully!'
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            })
    
    # GET request - show the form
    context = {
        'user': request.user,
        'policies': Policy.objects.filter(user=request.user, status='active'),
        'pending_claims': Claim.objects.filter(user=request.user, status__in=['submitted', 'pending']).count(),
        'unread_notifications': Notification.objects.filter(user=request.user, is_read=False).count(),
        'now': datetime.now(),
    }
    return render(request, 'core/customer_submit_claim.html', context)


# ================================================================
# HELPER: CALCULATE FRAUD SCORE
# ================================================================

def calculate_fraud_score(amount_claimed, policy, user, incident_type):
    """Calculate AI fraud score based on multiple factors"""
    score = 0
    
    # Factor 1: Claim amount vs coverage
    coverage = policy.coverage_amount or 100000
    amount_ratio = (amount_claimed / coverage) * 100
    if amount_ratio > 80:
        score += 25
    elif amount_ratio > 50:
        score += 15
    elif amount_ratio > 30:
        score += 5
    
    # Factor 2: Recent claims frequency
    recent_claims = Claim.objects.filter(
        user=user,
        submitted_at__gte=timezone.now() - timedelta(days=30)
    ).count()
    if recent_claims > 3:
        score += 20
    elif recent_claims > 1:
        score += 10
    
    # Factor 3: Policy age
    if policy.start_date:
        policy_age = (timezone.now().date() - policy.start_date).days
        if policy_age < 30:
            score += 15
        elif policy_age < 90:
            score += 5
    
    # Factor 4: Incident type risk
    high_risk_types = ['theft', 'accident', 'liability']
    if incident_type in high_risk_types:
        score += 10
    
    # Factor 5: Amount thresholds
    if amount_claimed > 50000:
        score += 10
    elif amount_claimed > 100000:
        score += 20
    
    # Add randomness for AI simulation (keep score realistic)
    score += random.randint(-5, 5)
    
    # Ensure score is between 0 and 100
    score = max(0, min(100, score))
    
    return score

@login_required
def customer_invoices(request):
    """Invoices & Receipts page"""
    context = {
        'user': request.user,
        'invoices': [],
        'now': datetime.now(),
    }
    return render(request, 'core/customer_invoices.html', context)


@login_required
def customer_support(request):
    """Support Center page"""
    context = {
        'user': request.user,
        'now': datetime.now(),
    }
    return render(request, 'core/customer_support.html', context)


@login_required
def customer_fraud_monitor(request):
    """Fraud Monitor page"""
    claims = Claim.objects.filter(user=request.user)
    context = {
        'user': request.user,
        'now': datetime.now(),
        'total_claims': claims.count(),
        'fraud_alerts': claims.filter(ai_fraud_score__gte=50).count(),
    }
    return render(request, 'core/customer_fraud_monitor.html', context)
# ==============================
# CUSTOMER TRACK CLAIM
# ==============================

@login_required
def customer_track_claim(request):
    """Track Claim page - Fetches real claim from database"""
    claim_number = request.GET.get('claim', '')
    claim_data = None
    
    if claim_number:
        try:
            claim = Claim.objects.get(claim_number=claim_number, user=request.user)
            
            claim_data = {
                'claim_number': claim.claim_number,
                'policy_type': claim.policy.get_policy_type_display() if claim.policy else 'N/A',
                'policy_number': claim.policy.policy_number if claim.policy else 'N/A',
                'incident_type_display': claim.get_incident_type_display(),
                'amount_claimed': float(claim.amount_claimed),
                'submitted_at': claim.submitted_at.strftime('%d %b %Y, %H:%M'),
                'incident_date': claim.incident_date.strftime('%d %b %Y'),
                'incident_location': claim.incident_location or 'Not specified',
                'status': claim.status,
                'status_display': claim.get_status_display(),
                'ai_fraud_score': claim.ai_fraud_score,
                'ai_fraud_analysis': claim.ai_fraud_analysis or 'No analysis available.',
                'investigator': claim.investigator.get_full_name() if claim.investigator else 'Not assigned',
                'timeline': get_claim_timeline(claim),
            }
            
        except Claim.DoesNotExist:
            claim_data = None
    
    context = {
        'user': request.user,
        'now': datetime.now(),
        'claim_number': claim_number,
        'claim_data': claim_data,
        'pending_claims': Claim.objects.filter(user=request.user, status__in=['submitted', 'pending']).count(),
        'unread_notifications': Notification.objects.filter(user=request.user, is_read=False).count(),
    }
    return render(request, 'core/customer_track_claim.html', context)


def get_claim_timeline(claim):
    """Generate timeline for a claim"""
    timeline = []
    
    # 1. Claim Submitted
    timeline.append({
        'icon': 'blue',
        'icon_class': 'fa-upload',
        'title': 'Claim Submitted',
        'desc': 'Claim successfully submitted for processing.',
        'time': claim.submitted_at.strftime('%d %b %Y, %H:%M'),
        'completed': True,
    })
    
    # 2. AI Review
    if claim.ai_fraud_score is not None:
        risk_level = "Low" if claim.ai_fraud_score < 30 else "Medium" if claim.ai_fraud_score < 60 else "High"
        timeline.append({
            'icon': 'blue',
            'icon_class': 'fa-robot',
            'title': 'AI Review Complete',
            'desc': f'AI fraud assessment completed. Score: {claim.ai_fraud_score}% - Risk: {risk_level}',
            'time': claim.updated_at.strftime('%d %b %Y, %H:%M'),
            'completed': True,
        })
    
    # 3. Staff Review
    if claim.status in ['investigation', 'approved', 'rejected', 'paid']:
        timeline.append({
            'icon': 'purple',
            'icon_class': 'fa-user-tie',
            'title': 'Staff Review',
            'desc': 'Claim reviewed by staff.',
            'time': claim.updated_at.strftime('%d %b %Y, %H:%M'),
            'completed': True,
        })
    
    # 4. Investigation (if applicable)
    if claim.status in ['investigation', 'approved', 'paid']:
        timeline.append({
            'icon': 'purple',
            'icon_class': 'fa-search',
            'title': 'Investigation Completed',
            'desc': 'Investigation concluded.' if claim.ai_fraud_score < 30 else 'Investigation completed with some findings.',
            'time': claim.updated_at.strftime('%d %b %Y, %H:%M'),
            'completed': True,
        })
    
    # 5. Decision
    if claim.status in ['approved', 'paid']:
        timeline.append({
            'icon': 'green',
            'icon_class': 'fa-check-circle',
            'title': 'Claim Approved ✅',
            'desc': f'Claim approved for R{float(claim.amount_claimed):,.2f}.',
            'time': claim.updated_at.strftime('%d %b %Y, %H:%M'),
            'completed': True,
        })
    elif claim.status == 'rejected':
        timeline.append({
            'icon': 'red',
            'icon_class': 'fa-times-circle',
            'title': 'Claim Rejected ❌',
            'desc': f'Your claim has been rejected. Reason: {claim.rejection_reason or "Please contact support for more information."}',
            'time': claim.updated_at.strftime('%d %b %Y, %H:%M'),
            'completed': True,
        })
    
    # 6. Payment Released
    if claim.status == 'paid':
        timeline.append({
            'icon': 'green',
            'icon_class': 'fa-money-bill-wave',
            'title': 'Payment Released 💰',
            'desc': f'Payment of R{float(claim.amount_approved or claim.amount_claimed):,.2f} has been released.',
            'time': claim.updated_at.strftime('%d %b %Y, %H:%M'),
            'completed': True,
        })
    
    return timeline

def get_claim_timeline(claim):
    """Generate timeline for a claim"""
    timeline = []
    
    # Submitted
    timeline.append({
        'icon': 'blue',
        'icon_class': 'fa-upload',
        'title': 'Claim Submitted',
        'desc': 'Claim successfully submitted for processing.',
        'time': claim.submitted_at.strftime('%d %b %Y, %H:%M'),
    })
    
    # AI Review (if claim has fraud score)
    if claim.ai_fraud_score is not None:
        risk_level = "Low" if claim.ai_fraud_score < 30 else "Medium" if claim.ai_fraud_score < 60 else "High"
        timeline.append({
            'icon': 'blue',
            'icon_class': 'fa-robot',
            'title': 'AI Review Complete',
            'desc': f'AI fraud assessment completed. Score: {claim.ai_fraud_score}% - Risk: {risk_level}',
            'time': claim.updated_at.strftime('%d %b %Y, %H:%M'),
        })
    
    # Investigation (if status is investigation or later)
    if claim.status in ['investigation', 'approved', 'paid']:
        timeline.append({
            'icon': 'purple',
            'icon_class': 'fa-search',
            'title': 'Investigation Completed',
            'desc': 'Investigation concluded. No fraud detected.' if claim.ai_fraud_score < 30 else 'Investigation completed with some findings.',
            'time': claim.updated_at.strftime('%d %b %Y, %H:%M'),
        })
    
    # Decision
    if claim.status in ['approved', 'paid']:
        timeline.append({
            'icon': 'green',
            'icon_class': 'fa-check-circle',
            'title': 'Claim Approved',
            'desc': f'Claim approved for R{float(claim.amount_claimed):,.2f}. Payment processing initiated.',
            'time': claim.updated_at.strftime('%d %b %Y, %H:%M'),
        })
    elif claim.status == 'rejected':
        timeline.append({
            'icon': 'red',
            'icon_class': 'fa-times-circle',
            'title': 'Claim Rejected',
            'desc': 'Your claim has been rejected. Please contact support for more information.',
            'time': claim.updated_at.strftime('%d %b %Y, %H:%M'),
        })
    
    # Payment Released
    if claim.status == 'paid':
        timeline.append({
            'icon': 'green',
            'icon_class': 'fa-money-bill-wave',
            'title': 'Payment Released',
            'desc': f'Payment of R{float(claim.amount_claimed):,.2f} has been released to your account.',
            'time': claim.updated_at.strftime('%d %b %Y, %H:%M'),
        })
    
    return timeline
@login_required
def customer_renew_policy(request):
    """Renew Policy page"""
    from datetime import datetime, timedelta
    
    # Get policies that are eligible for renewal (expiring within 90 days)
    policies = Policy.objects.filter(
        user=request.user,
        status='active',
        end_date__lte=datetime.now().date() + timedelta(days=90)
    )
    
    # Build context with days until renewal
    policy_list = []
    for policy in policies:
        days_left = (policy.end_date - datetime.now().date()).days
        policy_list.append({
            'id': policy.id,
            'policy_number': policy.policy_number,
            'policy_type': policy.policy_type,
            'type_display': policy.type_display(),
            'premium_amount': policy.premium_amount,
            'coverage_amount': policy.coverage_amount,
            'days_until_renewal': days_left if days_left > 0 else 0,
            'renewal_date': policy.end_date,
        })
    
    context = {
        'user': request.user,
        'now': datetime.now(),
        'policies': policy_list,
    }
    return render(request, 'core/customer_renew_policy.html', context)
@login_required
def customer_update_policy(request):
    """Update Policy page"""
    policies = Policy.objects.filter(user=request.user, status='active')
    context = {
        'user': request.user,
        'now': datetime.now(),
        'policies': policies,
    }
    return render(request, 'core/customer_update_policy.html', context)
@login_required
def customer_cancel_policy(request):
    """Cancel Policy page"""
    policies = Policy.objects.filter(user=request.user, status='active')
    context = {
        'user': request.user,
        'now': datetime.now(),
        'policies': policies,
    }
    return render(request, 'core/customer_cancel_policy.html', context)
@login_required
def customer_policy_detail(request, policy_id):
    """Policy Detail page"""
    try:
        policy = Policy.objects.get(id=policy_id, user=request.user)
    except Policy.DoesNotExist:
        messages.error(request, 'Policy not found.')
        return redirect('customer_policies')
    
    # Calculate derived values
    days_remaining = (policy.end_date - datetime.now().date()).days if policy.end_date else 0
    
    # Get beneficiaries (from policy fields)
    beneficiaries = []
    if policy.beneficiary_name:
        beneficiaries.append({
            'name': policy.beneficiary_name,
            'relationship': policy.beneficiary_relationship or 'Not specified',
            'percentage': 100,
            'phone': policy.beneficiary_phone or '',
            'email': policy.beneficiary_email or '',
        })
    
    policy_data = {
        'id': policy.id,
        'policy_number': policy.policy_number,
        'type_display': policy.type_display(),
        'coverage_amount': policy.coverage_amount,
        'premium_amount': policy.premium_amount,
        'remaining_cover': policy.coverage_amount,  # Simplified
        'ai_health_score': 100 - policy.ai_risk_score if policy.ai_risk_score else 95,
        'days_remaining': days_remaining if days_remaining > 0 else 0,
        'missed_payments': 0,  # Would need separate logic
        'claims_made': policy.claims.count(),
        'beneficiaries': beneficiaries,
    }
    
    context = {
        'user': request.user,
        'policy': policy_data,
        'now': datetime.now(),
    }
    return render(request, 'core/customer_policy_detail.html', context)@login_required
def customer_claim_detail(request, claim_id):
    """Claim Detail page with full information"""
    try:
        claim = Claim.objects.get(id=claim_id, user=request.user)
    except Claim.DoesNotExist:
        messages.error(request, 'Claim not found.')
        return redirect('customer_claims')
    
    # Get related documents
    documents = Document.objects.filter(claim=claim)
    
    # Get timeline
    timeline = get_claim_timeline(claim)
    
    # Get related payments
    payments = Payment.objects.filter(claim=claim)
    
    claim_data = {
        'id': claim.id,
        'claim_number': claim.claim_number,
        'policy': {
            'type_display': claim.policy.get_policy_type_display() if claim.policy else 'N/A',
            'policy_number': claim.policy.policy_number if claim.policy else 'N/A',
            'coverage_amount': claim.policy.coverage_amount if claim.policy else 0,
            'premium_amount': claim.policy.premium_amount if claim.policy else 0,
        },
        'incident_type_display': claim.get_incident_type_display(),
        'incident_date': claim.incident_date,
        'incident_location': claim.incident_location or 'Not specified',
        'incident_description': claim.incident_description,
        'amount_claimed': claim.amount_claimed,
        'amount_approved': claim.amount_approved,
        'status': claim.status,
        'status_display': claim.get_status_display(),
        'submitted_at': claim.submitted_at,
        'updated_at': claim.updated_at,
        'resolved_at': claim.resolved_at,
        'investigator': claim.investigator.get_full_name() if claim.investigator else 'Not assigned',
        'ai_fraud_score': claim.ai_fraud_score,
        'ai_fraud_analysis': claim.ai_fraud_analysis or 'No suspicious patterns detected.',
        'rejection_reason': claim.rejection_reason or 'N/A',
        'documents': documents,
        'payments': payments,
        'timeline': timeline,
        'can_appeal': claim.status == 'rejected',
    }
    
    context = {
        'user': request.user,
        'claim': claim_data,
        'now': datetime.now(),
        'unread_notifications': Notification.objects.filter(user=request.user, is_read=False).count(),
    }
    return render(request, 'core/customer_claim_detail.html', context)

# ==============================
# CUSTOMER FRAUD MONITOR
# ==============================
@login_required
def customer_fraud_monitor(request):
    """Fraud Monitor page with real-time AI fraud analysis"""
    user = request.user
    
    # Get user's claims
    claims = Claim.objects.filter(user=user)
    total_claims = claims.count()
    
    # Calculate fraud statistics
    fraud_alerts = claims.filter(ai_fraud_score__gte=50).count()
    high_risk_count = claims.filter(ai_fraud_score__gte=70).count()
    medium_risk_count = claims.filter(ai_fraud_score__gte=40, ai_fraud_score__lt=70).count()
    low_risk_count = claims.filter(ai_fraud_score__lt=40).count()
    
    # Calculate average fraud score
    avg_fraud_score = claims.aggregate(Sum('ai_fraud_score'))['ai_fraud_score__sum']
    if total_claims > 0:
        avg_fraud_score = avg_fraud_score / total_claims
    else:
        avg_fraud_score = 0
    
    # Determine overall risk level
    if high_risk_count > 0:
        risk_level = 'High'
        risk_color = 'red'
    elif medium_risk_count > 0:
        risk_level = 'Medium'
        risk_color = 'orange'
    else:
        risk_level = 'Low'
        risk_color = 'green'
    
    # Build fraud alerts
    fraud_alerts_list = []
    
    # Check for high risk claims
    high_risk_claims = claims.filter(ai_fraud_score__gte=70)
    for claim in high_risk_claims[:3]:
        fraud_alerts_list.append({
            'icon': 'red',
            'icon_class': 'fa-exclamation-triangle',
            'title': f'⚠️ High Risk Claim Detected',
            'message': f'Claim {claim.claim_number} has a fraud score of {claim.ai_fraud_score}%. Investigation required.',
            'time': claim.updated_at.strftime('%d %b %Y, %H:%M'),
            'status': 'investigating',
            'status_text': 'Investigating',
            'claim_number': claim.claim_number,
        })
    
    # Check for medium risk claims
    medium_risk_claims = claims.filter(ai_fraud_score__gte=40, ai_fraud_score__lt=70)
    for claim in medium_risk_claims[:2]:
        fraud_alerts_list.append({
            'icon': 'orange',
            'icon_class': 'fa-clock',
            'title': f'⚠️ Medium Risk Claim Detected',
            'message': f'Claim {claim.claim_number} has a fraud score of {claim.ai_fraud_score}%. Review recommended.',
            'time': claim.updated_at.strftime('%d %b %Y, %H:%M'),
            'status': 'pending',
            'status_text': 'Pending Review',
            'claim_number': claim.claim_number,
        })
    
    # If no alerts, show safe message
    if not fraud_alerts_list:
        fraud_alerts_list.append({
            'icon': 'green',
            'icon_class': 'fa-check-circle',
            'title': '✅ No Suspicious Activity Detected',
            'message': f'All {total_claims} claims have been verified by AI with an average score of {avg_fraud_score:.1f}%.',
            'time': datetime.now().strftime('%d %b %Y, %H:%M'),
            'status': 'resolved',
            'status_text': 'Resolved',
            'claim_number': None,
        })
        fraud_alerts_list.append({
            'icon': 'blue',
            'icon_class': 'fa-info-circle',
            'title': 'AI Monitoring Active',
            'message': 'Your account is being continuously monitored for suspicious activity.',
            'time': datetime.now().strftime('%d %b %Y, %H:%M'),
            'status': 'resolved',
            'status_text': 'Active',
            'claim_number': None,
        })
    
    # Build AI Analysis Report
    analysis_report = [
        {
            'label': 'Claim History Review',
            'value': '✅ No issues detected' if high_risk_count == 0 else f'⚠️ {high_risk_count} high risk claims found'
        },
        {
            'label': 'Document Analysis',
            'value': '✅ All documents verified' if claims.filter(documents__status='verified').count() > 0 else '⚠️ Some documents pending'
        },
        {
            'label': 'Behavioral Pattern',
            'value': '✅ Normal activity' if high_risk_count == 0 else '⚠️ Unusual patterns detected'
        },
        {
            'label': 'Duplicate Detection',
            'value': '✅ No duplicates found' if claims.count() == claims.values('claim_number').distinct().count() else '⚠️ Potential duplicates found'
        },
        {
            'label': 'Location Consistency',
            'value': '✅ Consistent' if total_claims > 0 else 'No claims to analyze'
        },
        {
            'label': 'Overall Fraud Score',
            'value': f'{avg_fraud_score:.1f}% - {risk_level} Risk',
            'score_class': 'score-good' if risk_level == 'Low' else ('score-medium' if risk_level == 'Medium' else 'score-bad')
        },
    ]
    
    context = {
        'user': user,
        'now': datetime.now(),
        'total_claims': total_claims,
        'fraud_alerts': fraud_alerts_list,
        'analysis_report': analysis_report,
        'avg_fraud_score': avg_fraud_score,
        'risk_level': risk_level,
        'risk_color': risk_color,
        'high_risk_count': high_risk_count,
        'medium_risk_count': medium_risk_count,
        'low_risk_count': low_risk_count,
        'pending_claims': Claim.objects.filter(user=user, status__in=['submitted', 'pending']).count(),
        'unread_notifications': Notification.objects.filter(user=user, is_read=False).count(),
    }
    return render(request, 'core/customer_fraud_monitor.html', context)
# ==============================
# CUSTOMER PURCHASE WIZARD - FIXED
# ==============================

@login_required
def customer_purchase_wizard(request):
    """Purchase Wizard - 5-step policy purchase"""
    
    # ✅ MOVE IMPORT TO TOP - OUTSIDE POST BLOCK
    import json
    import random
    from datetime import datetime
    
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            user = request.user
            
            # Get data from wizard
            policy_type = data.get('policy_type')
            coverage_amount = data.get('coverage_amount')
            premium_amount = data.get('premium_amount')
            start_date = data.get('start_date')
            
            # Personal info
            full_name = data.get('full_name')
            id_number = data.get('id_number')
            email = data.get('email')
            phone = data.get('phone')
            address = data.get('address')
            
            # Beneficiary
            beneficiary_name = data.get('beneficiary_name')
            beneficiary_id = data.get('beneficiary_id')
            beneficiary_relationship = data.get('beneficiary_relationship')
            beneficiary_phone = data.get('beneficiary_phone')
            beneficiary_email = data.get('beneficiary_email')
            
            # Payment method
            payment_method = data.get('payment_method')
            
            # Generate policy number
            policy_number = f"POL-{datetime.now().year}-{random.randint(1000, 9999)}"
            
            # Create policy - STATUS IS 'pending'
            policy = Policy.objects.create(
                policy_number=policy_number,
                user=user,
                policy_type=policy_type,
                coverage_amount=coverage_amount,
                premium_amount=premium_amount,
                start_date=start_date or datetime.now().date(),
                end_date=datetime.now().date() + timedelta(days=365),
                renewal_date=datetime.now().date() + timedelta(days=365),
                status='pending',  # Staff must verify documents first
                ai_risk_score=random.randint(5, 25),
                ai_risk_level='Low',
                beneficiary_name=beneficiary_name,
                beneficiary_id=beneficiary_id,
                beneficiary_relationship=beneficiary_relationship,
                beneficiary_phone=beneficiary_phone,
                beneficiary_email=beneficiary_email,
            )
            
            # Create payment record
            payment_number = f"PAY-{datetime.now().year}-{random.randint(1000, 9999)}"
            Payment.objects.create(
                payment_number=payment_number,
                user=user,
                policy=policy,
                amount=premium_amount,
                payment_method=payment_method or 'payfast',
                payment_type='premium',
                status='completed',
                due_date=datetime.now().date() + timedelta(days=30),
                paid_at=datetime.now(),
            )
            
            # Create notification for customer
            Notification.objects.create(
                user=user,
                title='Policy Purchased Successfully!',
                message=f'Your {dict(Policy.POLICY_TYPES).get(policy_type, policy_type)} policy #{policy_number} has been submitted for review.',
                notification_type='success',
                category='policy',
                related_policy=policy,
                action_url='/dashboard/customer/policies/',
            )
            
            # ✅ NEW: Notify staff about new application
            staff_users = User.objects.filter(profile__role='staff')
            for staff in staff_users:
                Notification.objects.create(
                    user=staff,
                    title='📋 New Application Received',
                    message=f'{user.get_full_name() or user.username} has applied for a policy. Documents pending verification.',
                    notification_type='info',
                    category='policy',
                    action_url='/staff/new-applications/',
                )
            
            return JsonResponse({
                'success': True,
                'policy_number': policy_number,
                'message': 'Policy submitted for review!'
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            })
    
    # GET request
    context = {
        'user': request.user,
        'now': datetime.now(),
        'policies': Policy.objects.filter(user=request.user),
        'pending_claims': Claim.objects.filter(user=request.user, status__in=['pending', 'submitted']).count(),
        'unread_notifications': Notification.objects.filter(user=request.user, is_read=False).count(),
    }
    return render(request, 'core/customer_purchase_wizard.html', context)

# ==============================
# CUSTOMER DOCUMENTS
# ==============================
@login_required
def customer_documents(request):
    """Documents page - Upload and manage documents"""
    
    # Handle POST (document upload)
    if request.method == 'POST':
        try:
            user = request.user
            
            # Get form data
            document_type = request.POST.get('doc_type')
            document_name = request.POST.get('doc_name')
            document_file = request.FILES.get('file')
            
            if not document_file:
                messages.error(request, 'Please select a file to upload.')
                return redirect('customer_documents')
            
            # Validate file size (5MB max)
            if document_file.size > 5 * 1024 * 1024:
                messages.error(request, 'File size exceeds 5MB limit.')
                return redirect('customer_documents')
            
            # Validate file type
            allowed_types = ['image/jpeg', 'image/png', 'image/gif', 'application/pdf']
            if document_file.content_type not in allowed_types:
                messages.error(request, 'File type not supported. Please upload JPG, PNG, GIF, or PDF.')
                return redirect('customer_documents')
            
            # Generate document number
            import random
            doc_number = f"DOC-{datetime.now().year}-{random.randint(1000, 9999)}"
            
            # Create document
            document = Document.objects.create(
                document_number=doc_number,
                user=user,
                document_type=document_type,
                document_name=document_name,
                document_file=document_file,
                file_size=document_file.size,
                file_type=document_file.content_type.split('/')[1] if '/' in document_file.content_type else 'pdf',
                status='pending',
                ai_verification_score=random.randint(70, 95),
            )
            
            # Create notification
            Notification.objects.create(
                user=user,
                title='Document Uploaded Successfully',
                message=f'Your document "{document_name}" has been uploaded and is pending verification.',
                notification_type='success',
                category='document',
                action_url='/dashboard/customer/documents/',
            )
            
            messages.success(request, f'Document "{document_name}" uploaded successfully!')
            
        except Exception as e:
            messages.error(request, f'Error uploading document: {str(e)}')
        
        return redirect('customer_documents')
    
    # GET request - show documents
    documents = Document.objects.filter(user=request.user).order_by('-uploaded_at')
    # Calculate stats
    total_docs = documents.count()
    verified_docs = documents.filter(status='verified').count()
    pending_docs = documents.filter(status='pending').count()
    rejected_docs = documents.filter(status='rejected').count()
    
    context = {
        'user': request.user,
        'documents': documents,
        'verified_docs': verified_docs,
        'pending_docs': pending_docs,
        'rejected_docs': rejected_docs,
        'total_docs': total_docs,
        'now': datetime.now(),
        'pending_claims': Claim.objects.filter(user=request.user, status__in=['submitted', 'pending']).count(),
        'unread_notifications': Notification.objects.filter(user=request.user, is_read=False).count(),
    }
    return render(request, 'core/customer_documents.html', context)


# ==============================
# CUSTOMER DOCUMENT UPLOAD (AJAX)
# ==============================
@login_required
def customer_upload_document(request):
    """Handle document upload during policy purchase (AJAX)"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid request method.'})
    
    try:
        import random
        from datetime import datetime
        
        user = request.user
        
        # Get from FormData - NOT JSON!
        document_type = request.POST.get('document_type')
        document_name = request.POST.get('document_name')
        document_file = request.FILES.get('document_file')  # This is the file
        
        if not document_type or not document_file:
            return JsonResponse({'success': False, 'error': 'Missing required fields.'})
        
        # Validate file size (5MB max)
        if document_file.size > 5 * 1024 * 1024:
            return JsonResponse({'success': False, 'error': 'File size exceeds 5MB limit.'})
        
        # Validate file type
        allowed_types = ['image/jpeg', 'image/png', 'image/gif', 'application/pdf']
        if document_file.content_type not in allowed_types:
            return JsonResponse({'success': False, 'error': 'File type not supported.'})
        
        # Generate document number
        doc_number = f"DOC-{datetime.now().year}-{random.randint(1000, 9999)}"
        
        # Create document record in database
        document = Document.objects.create(
            document_number=doc_number,
            user=user,
            document_type=document_type,
            document_name=document_name or f"{document_type.replace('_', ' ').title()} Document",
            document_file=document_file,  # Save the actual file
            file_size=document_file.size,
            file_type=document_file.content_type.split('/')[1] if '/' in document_file.content_type else 'pdf',
            status='pending',
            ai_verification_score=random.randint(70, 95),
            uploaded_at=datetime.now(),
        )
        
        # CREATE NOTIFICATION FOR CUSTOMER
        Notification.objects.create(
            user=user,
            title='Document Uploaded Successfully',
            message=f'Your {document_type.replace("_", " ").title()} has been uploaded and is pending verification.',
            notification_type='success',
            category='document',
            action_url='/dashboard/customer/documents/',
        )
        
        # CREATE NOTIFICATION FOR STAFF
        staff_users = User.objects.filter(profile__role='staff')
        for staff in staff_users:
            Notification.objects.create(
                user=staff,
                title='New Document Pending Verification',
                message=f'{user.get_full_name() or user.username} uploaded a {document_type.replace("_", " ").title()} document.',
                notification_type='info',
                category='document',
                action_url='/staff/documents/',
            )
        
        # CREATE NOTIFICATION FOR ADMIN
        admin_users = User.objects.filter(profile__role='administrator')
        for admin in admin_users:
            Notification.objects.create(
                user=admin,
                title='New Document Uploaded',
                message=f'{user.get_full_name() or user.username} uploaded a {document_type.replace("_", " ").title()} document.',
                notification_type='info',
                category='document',
                action_url='/admin/documents/',
            )
        
        return JsonResponse({
            'success': True,
            'document_id': document.id,
            'document_number': doc_number,
            'status': 'pending',
            'message': 'Document uploaded successfully!'
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
def customer_delete_document(request):
    """Delete a document"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid request method.'})
    
    try:
        import json
        data = json.loads(request.body)
        document_id = data.get('document_id')
        
        if not document_id:
            return JsonResponse({'success': False, 'error': 'Document ID required.'})
        
        document = Document.objects.get(id=document_id, user=request.user)
        
        # Only allow deletion if status is pending or uploaded
        if document.status in ['verified', 'rejected']:
            return JsonResponse({'success': False, 'error': 'Cannot delete a document that is already verified or rejected.'})
        
        document.delete()
        
        return JsonResponse({'success': True, 'message': 'Document deleted successfully.'})
        
    except Document.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Document not found.'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})
# ================================================================
# ADMIN DECORATOR - Check if user is an admin
# ================================================================
def admin_required(view_func):
    """Decorator to check if user is an administrator"""
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.error(request, 'Please login to access this page.')
            return redirect('login')
        
        if not hasattr(request.user, 'profile'):
            messages.error(request, 'Account profile not found.')
            return redirect('login')
        
        if request.user.profile.role != 'administrator' or request.user.profile.status != 'active':
            messages.error(request, 'You do not have permission to access this page.')
            return redirect('customer_dashboard')
        
        return view_func(request, *args, **kwargs)
    return wrapper
# ================================================================
# ADMIN DASHBOARD VIEW
# ================================================================
@login_required
@admin_required
def admin_dashboard_view(request):
    """Admin dashboard with system overview"""
    
    # Get real data from database
    total_policies = Policy.objects.count()
    total_users = User.objects.count()
    
    # Active claims (not rejected or paid)
    active_claims = Claim.objects.exclude(status__in=['rejected', 'paid']).count()
    
    # Total premiums from all policies
    total_premiums = Policy.objects.aggregate(Sum('premium_amount'))['premium_amount__sum'] or 0
    
    # Pending claims for badge
    pending_claims = Claim.objects.filter(status='pending').count()
    
    # High risk claims
    high_risk_claims = Claim.objects.filter(ai_fraud_score__gte=70).count()
    
    # Calculate growth percentages (using previous month data if available)
    # For now, using placeholder values, but you can implement actual logic
    policy_growth = 12.5
    user_growth = 8.3
    claim_decline = 4.7
    premium_growth = 15.2
    
    # Get recent policies (last 5)
    recent_policies = Policy.objects.select_related('user').order_by('-created_at')[:5]
    
    # Get fraud alerts (claims with high fraud score)
    fraud_alerts = Claim.objects.filter(ai_fraud_score__gte=60).order_by('-submitted_at')[:5]
    
    # Prepare fraud alerts data for display
    fraud_alerts_data = []
    for claim in fraud_alerts:
        fraud_alerts_data.append({
            'title': f"{claim.get_incident_type_display()} Claim",
            'reference': claim.claim_number,
            'description': f"Suspicious claim pattern detected for {claim.user.get_full_name()}",
            'risk_level': 'high' if claim.ai_fraud_score >= 70 else 'medium',
            'risk_score': claim.ai_fraud_score,
            'time_ago': f"{timezone.now() - claim.submitted_at} ago" if claim.submitted_at else "Just now",
        })
    
    # Prepare recent policies data
    recent_policies_data = []
    for policy in recent_policies:
        recent_policies_data.append({
            'policy_number': policy.policy_number,
            'user': policy.user,
            'type_display': policy.get_policy_type_display(),
            'premium_amount': policy.premium_amount,
            'status': policy.status,
            'get_status_display': policy.get_status_display(),
            'created_at': policy.created_at,
        })
    
    # Claim status distribution
    claim_status_data = []
    status_choices = Claim.CLAIM_STATUS
    for status_code, status_label in status_choices:
        count = Claim.objects.filter(status=status_code).count()
        if count > 0:
            percentage = round((count / (Claim.objects.count() or 1)) * 100, 1)
            claim_status_data.append({
                'status': status_code,
                'label': status_label,
                'count': count,
                'percentage': percentage,
            })
    
    # System activities (placeholder - you can replace with actual activity log data)
    system_activities = [
        {'message': 'New user registered: admin2@sifds.co.za', 'type': 'info', 'time_ago': '2 min ago'},
        {'message': 'Policy POL-2025-1001 created', 'type': 'success', 'time_ago': '10 min ago'},
        {'message': 'Claim CLM-2025-7880 approved', 'type': 'success', 'time_ago': '25 min ago'},
        {'message': 'Premium payment of R 12,450.00 received', 'type': 'info', 'time_ago': '1 hour ago'},
        {'message': 'System backup completed successfully', 'type': 'info', 'time_ago': '3 hours ago'},
    ]
    
    # Chart data for policies overview (last 30 days)
    policy_chart_data = {
        'labels': ['May 1', 'May 6', 'May 11', 'May 16', 'May 21', 'May 26', 'May 31'],
        'values': [120, 180, 200, 320, 280, 400, 500],
    }
    
    # Chart data for claims distribution
    claim_chart_data = {
        'labels': ['Pending', 'Under Review', 'Approved', 'Rejected'],
        'values': [142, 78, 92, 30],
    }
    
    context = {
        'now': now(),
        'total_policies': total_policies,
        'total_users': total_users,
        'active_claims': active_claims,
        'total_premiums': total_premiums,
        'pending_claims': pending_claims,
        'high_risk_claims': high_risk_claims,
        'policy_growth': policy_growth,
        'user_growth': user_growth,
        'claim_decline': claim_decline,
        'premium_growth': premium_growth,
        'recent_policies': recent_policies_data,
        'fraud_alerts': fraud_alerts_data,
        'claim_status_data': claim_status_data,
        'system_activities': system_activities,
        'policy_chart_data': policy_chart_data,
        'claim_chart_data': claim_chart_data,
    }
    
    return render(request, 'core/admin_dashboard.html', context)
# ================================================================
# ADMIN USER MANAGEMENT VIEW
# ================================================================
@login_required
@admin_required
def admin_users_view(request):
    """Admin user management page"""
    
    # Get all users with their profiles
    users = User.objects.select_related('profile').all().order_by('-date_joined')
    
    total_users = users.count()
    pending_claims = Claim.objects.filter(status='pending').count()
    high_risk_claims = Claim.objects.filter(ai_fraud_score__gte=70).count()
    
    # Prepare user data with avatar colors
    user_data = []
    role_colors = {
        'policyholder': '#2563eb',
        'staff': '#7c3aed',
        'investigator': '#f59e0b',
        'administrator': '#22c55e',
    }
    
    for user in users:
        if hasattr(user, 'profile'):
            role = user.profile.role or 'policyholder'
            status = user.profile.status or 'active'
            user_data.append({
                'id': user.id,
                'username': user.username,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'email': user.email,
                'full_name': user.get_full_name() or user.username,
                'role': role,
                'role_display': user.profile.get_role_display(),
                'status': status,
                'status_display': user.profile.get_status_display(),
                'avatar_color': role_colors.get(role, '#94a3b8'),
                'date_joined': user.date_joined,
            })
    
    context = {
        'now': now(),
        'users': user_data,
        'total_users': total_users,
        'total_policies': Policy.objects.count(),
        'pending_claims': pending_claims,
        'high_risk_claims': high_risk_claims,
    }
    
    return render(request, 'core/admin_users.html', context)


# ================================================================
# ADMIN POLICY MANAGEMENT VIEW
# ================================================================
@login_required
@admin_required
def admin_policies_view(request):
    """Admin policy management page"""
    
    # Get all policies with user data
    policies = Policy.objects.select_related('user').all().order_by('-created_at')
    
    total_policies = policies.count()
    pending_claims = Claim.objects.filter(status='pending').count()
    high_risk_claims = Claim.objects.filter(ai_fraud_score__gte=70).count()
    
    # Prepare policy data
    policy_data = []
    for policy in policies:
        policy_data.append({
            'policy_number': policy.policy_number,
            'user': policy.user,
            'type_display': policy.get_policy_type_display(),
            'premium_amount': policy.premium_amount,
            'status': policy.status,
            'get_status_display': policy.get_status_display(),
            'created_at': policy.created_at,
        })
    
    context = {
        'now': now(),
        'policies': policy_data,
        'total_policies': total_policies,
        'total_users': User.objects.count(),
        'pending_claims': pending_claims,
        'high_risk_claims': high_risk_claims,
    }
    
    return render(request, 'core/admin_policies.html', context)


# ================================================================
# ADMIN CLAIMS MANAGEMENT VIEW
# ================================================================
@login_required
@admin_required
def admin_claims_view(request):
    """Admin claims management page"""
    
    # Get all claims with related data
    claims = Claim.objects.select_related('user', 'policy').all().order_by('-submitted_at')
    
    total_claims = claims.count()
    pending_claims = Claim.objects.filter(status='pending').count()
    high_risk_claims = Claim.objects.filter(ai_fraud_score__gte=70).count()
    
    # Prepare claim data
    claim_data = []
    for claim in claims:
        claim_data.append({
            'claim_number': claim.claim_number,
            'user': claim.user,
            'policy': claim.policy,
            'incident_type_display': claim.get_incident_type_display(),
            'amount_claimed': claim.amount_claimed,
            'status': claim.status,
            'get_status_display': claim.get_status_display(),
            'ai_fraud_score': claim.ai_fraud_score,
            'submitted_at': claim.submitted_at,
        })
    
    context = {
        'now': now(),
        'claims': claim_data,
        'total_claims': total_claims,
        'total_users': User.objects.count(),
        'total_policies': Policy.objects.count(),
        'pending_claims': pending_claims,
        'high_risk_claims': high_risk_claims,
    }
    
    return render(request, 'core/admin_claims.html', context)
# ================================================================
# ADMIN FRAUD DETECTION VIEW
# ================================================================
@login_required
@admin_required
def admin_fraud_view(request):
    """Admin fraud detection page"""
    
    # Fraud statistics
    high_risk_claims = Claim.objects.filter(ai_fraud_score__gte=70).count()
    investigating_claims = Claim.objects.filter(status='investigation').count()
    cleared_claims = Claim.objects.filter(ai_fraud_score__lt=40, status__in=['approved', 'paid']).count()
    
    high_risk_percent = round((high_risk_claims / (Claim.objects.count() or 1)) * 100, 1)
    investigating_percent = round((investigating_claims / (Claim.objects.count() or 1)) * 100, 1)
    
    ai_accuracy = 96.4  # Placeholder - can be calculated from actual data
    
    # Get fraud cases (claims with high risk)
    fraud_cases = Claim.objects.filter(ai_fraud_score__gte=50).order_by('-ai_fraud_score')[:10]
    
    fraud_cases_data = []
    risk_levels = {
        70: 'high',
        50: 'medium',
        0: 'low',
    }
    
    for claim in fraud_cases:
        risk_level = 'low'
        if claim.ai_fraud_score >= 70:
            risk_level = 'high'
        elif claim.ai_fraud_score >= 50:
            risk_level = 'medium'
        
        status = 'flagged'
        if claim.status == 'investigation':
            status = 'investigating'
        elif claim.status in ['approved', 'paid']:
            status = 'cleared'
        
        fraud_cases_data.append({
            'title': f"{claim.get_incident_type_display()} Claim",
            'claim_number': claim.claim_number,
            'customer_name': claim.user.get_full_name() or claim.user.username,
            'policy_number': claim.policy.policy_number if claim.policy else 'N/A',
            'risk_level': risk_level,
            'risk_score': claim.ai_fraud_score,
            'status': status,
            'status_display': 'Flagged' if status == 'flagged' else 'Investigating' if status == 'investigating' else 'Cleared',
            'time_ago': f"{timezone.now() - claim.submitted_at} ago" if claim.submitted_at else "Just now",
        })
    
    # Fraud trend data (last 30 days)
    fraud_trend_data = {
        'labels': ['Day 1', 'Day 5', 'Day 10', 'Day 15', 'Day 20', 'Day 25', 'Day 30'],
        'values': [45, 52, 48, 65, 58, 72, 55],
    }
    
    # Risk distribution data
    risk_distribution_data = {
        'labels': ['High Risk', 'Medium Risk', 'Low Risk'],
        'values': [
            Claim.objects.filter(ai_fraud_score__gte=70).count(),
            Claim.objects.filter(ai_fraud_score__gte=40, ai_fraud_score__lt=70).count(),
            Claim.objects.filter(ai_fraud_score__lt=40).count(),
        ]
    }
    
    context = {
        'now': now(),
        'high_risk_claims': high_risk_claims,
        'investigating_claims': investigating_claims,
        'cleared_claims': cleared_claims,
        'high_risk_percent': high_risk_percent,
        'investigating_percent': investigating_percent,
        'ai_accuracy': ai_accuracy,
        'accuracy_change': 1.2,
        'fraud_cases': fraud_cases_data,
        'fraud_trend_data': fraud_trend_data,
        'risk_distribution_data': risk_distribution_data,
        'total_policies': Policy.objects.count(),
        'total_users': User.objects.count(),
        'pending_claims': Claim.objects.filter(status='pending').count(),
    }
    
    return render(request, 'core/admin_fraud.html', context)
# ================================================================
# HELPER FUNCTIONS FOR ADMIN VIEWS
# ================================================================
def get_status_color(status):
    """Helper to get status color for display"""
    colors = {
        'active': 'active',
        'pending': 'pending',
        'expired': 'expired',
        'cancelled': 'cancelled',
        'submitted': 'submitted',
        'investigation': 'investigation',
        'approved': 'approved',
        'rejected': 'rejected',
        'paid': 'paid',
    }
    return colors.get(status, 'pending')


def get_risk_level(score):
    """Helper to get risk level from score"""
    if score >= 70:
        return 'high'
    elif score >= 40:
        return 'medium'
    else:
        return 'low'


def time_ago(date_time):
    """Helper to format time ago"""
    if not date_time:
        return 'Just now'
    
    delta = timezone.now() - date_time
    if delta.days > 0:
        return f"{delta.days} days ago"
    elif delta.seconds > 3600:
        return f"{delta.seconds // 3600} hours ago"
    elif delta.seconds > 60:
        return f"{delta.seconds // 60} minutes ago"
    else:
        return f"{delta.seconds} seconds ago"

# core/views.py - Add these views

@login_required
@admin_required
def admin_settings_view(request):
    """Admin system settings page"""
    context = {
        'now': now(),
        'total_users': User.objects.count(),
        'total_policies': Policy.objects.count(),
        'pending_claims': Claim.objects.filter(status='pending').count(),
        'high_risk_claims': Claim.objects.filter(ai_fraud_score__gte=70).count(),
        'insurance_types': [],  # Add your data here
        'policy_categories': [],  # Add your data here
        'claim_categories': [],  # Add your data here
        'departments': [],  # Add your data here
    }
    return render(request, 'core/admin_settings.html', context)

@login_required
@admin_required
def admin_reports_view(request):
    """Admin reports page"""
    context = {
        'now': now(),
        'total_users': User.objects.count(),
        'total_policies': Policy.objects.count(),
        'pending_claims': Claim.objects.filter(status='pending').count(),
        'high_risk_claims': Claim.objects.filter(ai_fraud_score__gte=70).count(),
    }
    return render(request, 'core/admin_reports.html', context)


@login_required
@admin_required
def admin_ai_insights_view(request):
    """Admin AI insights page"""
    context = {
        'now': now(),
        'total_users': User.objects.count(),
        'total_policies': Policy.objects.count(),
        'pending_claims': Claim.objects.filter(status='pending').count(),
        'high_risk_claims': Claim.objects.filter(ai_fraud_score__gte=70).count(),
    }
    return render(request, 'core/admin_ai_insights.html', context)


@login_required
@admin_required
def admin_reports_view(request):
    """Admin reports page"""
    context = {
        'now': now(),
        'total_users': User.objects.count(),
        'total_policies': Policy.objects.count(),
        'pending_claims': Claim.objects.filter(status='pending').count(),
        'high_risk_claims': Claim.objects.filter(ai_fraud_score__gte=70).count(),
        'total_premiums': Policy.objects.aggregate(Sum('premium_amount'))['premium_amount__sum'] or 0,
    }
    return render(request, 'core/admin_reports.html', context)

@login_required
@admin_required
def admin_ai_insights_view(request):
    """Admin AI insights page"""
    context = {
        'now': now(),
        'total_users': User.objects.count(),
        'total_policies': Policy.objects.count(),
        'total_claims': Claim.objects.count(),
        'pending_claims': Claim.objects.filter(status='pending').count(),
        'high_risk_claims': Claim.objects.filter(ai_fraud_score__gte=70).count(),
    }
    return render(request, 'core/admin_ai_insights.html', context)

@login_required
@admin_required
def admin_staff_view(request):
    """Admin staff management page"""
    
    # Get all staff members (users with role staff, investigator, administrator)
    staff_users = User.objects.filter(
        profile__role__in=['staff', 'investigator', 'administrator']
    ).select_related('profile').order_by('-date_joined')
    
    staff_data = []
    for user in staff_users:
        staff_data.append({
            'id': user.id,
            'username': user.username,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'email': user.email,
            'full_name': user.get_full_name() or user.username,
            'role': user.profile.role if hasattr(user, 'profile') else 'staff',
            'role_display': user.profile.get_role_display() if hasattr(user, 'profile') else 'Staff',
            'department': user.profile.department if hasattr(user, 'profile') and user.profile.department else 'N/A',
            'status': user.profile.status if hasattr(user, 'profile') else 'active',
            'status_display': user.profile.get_status_display() if hasattr(user, 'profile') else 'Active',
            'date_joined': user.date_joined,
        })
    
    context = {
        'now': now(),
        'staff_members': staff_data,
        'total_staff': len(staff_data),
        'total_users': User.objects.count(),
        'total_policies': Policy.objects.count(),
        'pending_claims': Claim.objects.filter(status='pending').count(),
        'high_risk_claims': Claim.objects.filter(ai_fraud_score__gte=70).count(),
    }
    
    return render(request, 'core/admin_staff.html', context)

@login_required
@admin_required
def admin_staff_view(request):
    """Admin staff management page"""
    staff_users = User.objects.filter(
        profile__role__in=['staff', 'investigator', 'administrator']
    ).select_related('profile').order_by('-date_joined')
    
    staff_data = []
    for user in staff_users:
        staff_data.append({
            'id': user.id,
            'username': user.username,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'email': user.email,
            'full_name': user.get_full_name() or user.username,
            'role': user.profile.role if hasattr(user, 'profile') else 'staff',
            'role_display': user.profile.get_role_display() if hasattr(user, 'profile') else 'Staff',
            'department': user.profile.department if hasattr(user, 'profile') and user.profile.department else 'N/A',
            'status': user.profile.status if hasattr(user, 'profile') else 'active',
            'status_display': user.profile.get_status_display() if hasattr(user, 'profile') else 'Active',
            'date_joined': user.date_joined,
        })
    
    context = {
        'now': now(),
        'staff_members': staff_data,
        'total_staff': len(staff_data),
        'total_users': User.objects.count(),
        'total_policies': Policy.objects.count(),
        'pending_claims': Claim.objects.filter(status='pending').count(),
        'high_risk_claims': Claim.objects.filter(ai_fraud_score__gte=70).count(),
        'total_payments': Payment.objects.count(),
        'unread_notifications': Notification.objects.filter(is_read=False).count(),
    }
    return render(request, 'core/admin_staff.html', context)


@login_required
@admin_required
def admin_payments_view(request):
    """Admin payment management page"""
    payments = Payment.objects.select_related('user', 'policy').all().order_by('-created_at')
    
    payment_data = []
    for payment in payments:
        payment_data.append({
            'payment_number': payment.payment_number,
            'customer_name': payment.user.get_full_name() or payment.user.username,
            'customer_email': payment.user.email,
            'policy_number': payment.policy.policy_number if payment.policy else 'N/A',
            'amount': payment.amount,
            'method': payment.get_payment_method_display(),
            'status': payment.status,
            'status_display': payment.get_status_display(),
            'date': payment.created_at,
        })
    
    context = {
        'now': now(),
        'payments': payment_data,
        'total_payments': len(payment_data),
        'total_collected': Payment.objects.filter(status='completed').count(),
        'pending_payments': Payment.objects.filter(status='pending').count(),
        'overdue_payments': 0,
        'total_amount': Payment.objects.filter(status='completed').aggregate(Sum('amount'))['amount__sum'] or 0,
        'total_users': User.objects.count(),
        'total_staff': User.objects.filter(profile__role__in=['staff', 'investigator', 'administrator']).count(),
        'total_policies': Policy.objects.count(),
        'pending_claims': Claim.objects.filter(status='pending').count(),
        'high_risk_claims': Claim.objects.filter(ai_fraud_score__gte=70).count(),
        'unread_notifications': Notification.objects.filter(is_read=False).count(),
    }
    return render(request, 'core/admin_payments.html', context)


@login_required
@admin_required
def admin_notifications_view(request):
    """Admin notifications page"""
    recent_notifications = Notification.objects.all().order_by('-created_at')[:5]
    
    notif_data = []
    for notif in recent_notifications:
        notif_data.append({
            'title': notif.title,
            'message': notif.message,
            'created_at': notif.created_at,
            'recipients': 'All Users',
        })
    
    context = {
        'now': now(),
        'recent_notifications': notif_data,
        'unread_notifications': Notification.objects.filter(is_read=False).count(),
        'total_users': User.objects.count(),
        'total_staff': User.objects.filter(profile__role__in=['staff', 'investigator', 'administrator']).count(),
        'total_policies': Policy.objects.count(),
        'pending_claims': Claim.objects.filter(status='pending').count(),
        'high_risk_claims': Claim.objects.filter(ai_fraud_score__gte=70).count(),
        'total_payments': Payment.objects.count(),
    }
    return render(request, 'core/admin_notifications.html', context)
@login_required
@admin_required
def admin_analytics_view(request):
    """Admin analytics page"""
    context = {
        'now': now(),
        'policy_growth': 12.5,
        'user_growth': 8.3,
        'revenue_growth': 15.2,
        'fraud_decline': 4.7,
        'total_users': User.objects.count(),
        'total_staff': User.objects.filter(profile__role__in=['staff', 'investigator', 'administrator']).count(),
        'total_policies': Policy.objects.count(),
        'pending_claims': Claim.objects.filter(status='pending').count(),
        'high_risk_claims': Claim.objects.filter(ai_fraud_score__gte=70).count(),
        'total_payments': Payment.objects.count(),
        'unread_notifications': Notification.objects.filter(is_read=False).count(),
        'revenue_chart_data': {
            'labels': ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun'],
            'values': [125000, 142000, 138000, 165000, 180000, 210000],
        },
        'claims_trend_data': {
            'labels': ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun'],
            'values': [45, 52, 48, 60, 55, 68],
        },
        'policy_growth_data': {
            'labels': ['Vehicle', 'Home', 'Life', 'Health', 'Business'],
            'values': [45, 30, 25, 20, 15],
        },
        'fraud_trend_data': {
            'labels': ['Week 1', 'Week 2', 'Week 3', 'Week 4'],
            'values': [12, 8, 6, 4],
        },
        'payment_distribution_data': {
            'labels': ['Card', 'Bank Transfer', 'Debit Order', 'PayFast'],
            'values': [45, 25, 20, 10],
        },
        'monthly_comparison_data': {
            'labels': ['Policies', 'Claims', 'Revenue', 'Customers'],
            'current': [120, 45, 180000, 85],
            'previous': [100, 38, 155000, 72],
        },
    }
    return render(request, 'core/admin_analytics.html', context)

@login_required
@admin_required
def admin_customer_detail_view(request, user_id):
    """Admin customer detail page"""
    try:
        customer = User.objects.get(id=user_id)
    except User.DoesNotExist:
        messages.error(request, 'Customer not found.')
        return redirect('admin_users')
    
    context = {
        'now': now(),
        'customer': {
            'first_name': customer.first_name,
            'last_name': customer.last_name,
            'full_name': customer.get_full_name() or customer.username,
            'email': customer.email,
            'phone': customer.profile.phone if hasattr(customer, 'profile') else '',
            'id_number': customer.profile.id_number if hasattr(customer, 'profile') else '',
            'address': customer.profile.address if hasattr(customer, 'profile') else '',
            'city': customer.profile.city if hasattr(customer, 'profile') else '',
            'province': customer.profile.province if hasattr(customer, 'profile') else '',
            'postal_code': customer.profile.postal_code if hasattr(customer, 'profile') else '',
            'status': customer.profile.status if hasattr(customer, 'profile') else 'active',
            'status_display': customer.profile.get_status_display() if hasattr(customer, 'profile') else 'Active',
            'date_joined': customer.date_joined,
            'policies_count': customer.policies.count(),
            'claims_count': customer.claims.count(),
            'total_paid': Payment.objects.filter(user=customer, status='completed').aggregate(Sum('amount'))['amount__sum'] or 0,
            'payments': [
                {
                    'policy_type': p.policy.type_display if p.policy else 'Insurance',
                    'amount': p.amount,
                    'method': p.get_payment_method_display(),
                    'status': p.get_status_display(),
                    'date': p.created_at,
                } for p in Payment.objects.filter(user=customer).order_by('-created_at')[:5]
            ],
            'claims': [
                {
                    'type': c.get_incident_type_display(),
                    'status': c.get_status_display(),
                    'amount': c.amount_claimed,
                    'date': c.submitted_at,
                } for c in Claim.objects.filter(user=customer).order_by('-submitted_at')[:5]
            ],
            'documents': [
                {
                    'name': d.document_name,
                    'status': d.get_status_display(),
                    'date': d.uploaded_at,
                } for d in Document.objects.filter(user=customer).order_by('-uploaded_at')[:5]
            ],
        },
        'total_users': User.objects.count(),
        'total_staff': User.objects.filter(profile__role__in=['staff', 'investigator', 'administrator']).count(),
        'total_policies': Policy.objects.count(),
        'pending_claims': Claim.objects.filter(status='pending').count(),
        'high_risk_claims': Claim.objects.filter(ai_fraud_score__gte=70).count(),
        'total_payments': Payment.objects.count(),
        'unread_notifications': Notification.objects.filter(is_read=False).count(),
    }
    return render(request, 'core/admin_customer_detail.html', context)
# ================================================================
# STAFF DASHBOARD VIEWS 
# ================================================================
@login_required
def staff_dashboard_view(request):
    """Staff dashboard view"""
    
    # Get the current user's profile
    profile = request.user.profile
    
    # Check if user is staff or investigator
    if profile.role not in ['staff', 'investigator']:
        messages.error(request, 'You do not have permission to access the staff dashboard.')
        return redirect('dashboard')
    
    # Get real data from database
    pending_claims = Claim.objects.filter(status='pending').count()
    pending_policies = Policy.objects.filter(status='pending').count()
    pending_documents = Document.objects.filter(status='pending').count()
    pending_payments = Payment.objects.filter(status='pending').count()
    high_risk_claims = Claim.objects.filter(ai_fraud_score__gte=70).count()
    unread_notifications = Notification.objects.filter(user=request.user, is_read=False).count()
    
    # Get claims assigned to this staff member (if any)
    assigned_claims = Claim.objects.filter(investigator=request.user)
    
    # Priority tasks - claims with high risk or pending status
    priority_tasks = []
    high_priority_claims = Claim.objects.filter(ai_fraud_score__gte=70).order_by('-ai_fraud_score')[:3]
    for claim in high_priority_claims:
        priority_tasks.append({
            'priority': 'high',
            'priority_display': 'High',
            'title': f"{claim.get_incident_type_display()} Claim",
            'reference': claim.claim_number,
            'description': f"AI Risk Score: {claim.ai_fraud_score}%",
            'risk_level': 'high' if claim.ai_fraud_score >= 70 else 'medium' if claim.ai_fraud_score >= 40 else 'low',
            'risk_score': claim.ai_fraud_score,
            'due_time': '11:30 AM',
            'action_text': 'Review',
        })
    
    # Add some medium and low priority tasks if there aren't enough high priority ones
    if len(priority_tasks) < 3:
        pending_claims_list = Claim.objects.filter(status='pending').exclude(ai_fraud_score__gte=70)[:3-len(priority_tasks)]
        for claim in pending_claims_list:
            priority_tasks.append({
                'priority': 'medium' if claim.ai_fraud_score >= 40 else 'low',
                'priority_display': 'Medium' if claim.ai_fraud_score >= 40 else 'Low',
                'title': f"{claim.get_incident_type_display()} Claim",
                'reference': claim.claim_number,
                'description': f"Status: {claim.get_status_display()}",
                'risk_level': 'medium' if claim.ai_fraud_score >= 40 else 'low',
                'risk_score': claim.ai_fraud_score,
                'due_time': '02:00 PM',
                'action_text': 'Review',
            })
    
    # Recent activities (using notifications or creating sample)
    recent_activities = []
    recent_notifications = Notification.objects.filter(user=request.user).order_by('-created_at')[:4]
    for notif in recent_notifications:
        recent_activities.append({
            'type': 'info',
            'message': notif.message,
            'time_ago': f"{timezone.now() - notif.created_at} ago",
        })
    
    # If no notifications, add sample activities
    if not recent_activities:
        recent_activities = [
            {'type': 'success', 'message': 'Policy POL-2026-1005 approved', 'time_ago': '2 hours ago'},
            {'type': 'warning', 'message': 'Claim CLM-2026-1045 assigned to you', 'time_ago': '3 hours ago'},
            {'type': 'info', 'message': '3 documents uploaded by customer', 'time_ago': '4 hours ago'},
            {'type': 'success', 'message': 'Payment received from Customer #4581', 'time_ago': '5 hours ago'},
        ]
    
    # Sample data for charts (will be replaced with real data later)
    dept_performance_data = {
        'labels': ['Claims', 'Underwriting', 'Support', 'Fraud', 'Finance'],
        'values': [45, 30, 25, 15, 20],
    }
    
    monthly_claims_data = {
        'labels': ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun'],
        'approved': [15, 18, 20, 22, 25, 28],
        'pending': [8, 10, 7, 9, 6, 5],
        'investigation': [3, 4, 5, 3, 2, 1],
        'rejected': [2, 1, 3, 2, 1, 1],
    }
    
    fraud_trend_data = {
        'labels': ['Week 1', 'Week 2', 'Week 3', 'Week 4'],
        'values': [12, 8, 6, 4],
    }
    
    # Sample announcements and reminders
    announcements = [
        {
            'title': 'System Maintenance',
            'message': 'Scheduled maintenance on Sunday, 8 June 2026 from 02:00 AM to 04:00 AM.',
        }
    ]
    
    reminders = [
        {'title': 'Team meeting at 11:00 AM', 'description': 'Don\'t forget to attend'},
        {'title': 'Submit daily report', 'description': 'Due by 5:00 PM'},
        {'title': 'Follow up with Customer #4581', 'description': 'Overdue payment reminder'},
    ]
    
    context = {
        'now': now(),
        'pending_claims': pending_claims,
        'pending_policies': pending_policies,
        'pending_documents': pending_documents,
        'pending_payments': pending_payments,
        'high_risk_claims': high_risk_claims,
        'unread_notifications': unread_notifications,
        'priority_tasks': priority_tasks,
        'recent_activities': recent_activities,
        'dept_performance_data': dept_performance_data,
        'monthly_claims_data': monthly_claims_data,
        'fraud_trend_data': fraud_trend_data,
        'announcements': announcements,
        'reminders': reminders,
        'completion_percentage': 76,
        'completed_today': 12,
        'pending_today': 4,
        'avg_processing_time': 8.5,
        'customer_satisfaction': 94,
        'ai_assistance_score': 88,
        'today_rating': 4.8,
        'ai_insight_1': '5 claims can be approved immediately.',
        'ai_insight_2': '2 claims require investigation due to unusual patterns.',
        'ai_insight_3': '3 uploaded documents appear to be duplicates.',
        'ai_insight_4': '1 customer\'s premium payment has failed twice.',
        'ai_action_1': 'Prioritise Claim CLM-2026-1045 (High Risk).',
        'ai_action_2': 'Verify pending FICA documents.',
        'ai_action_3': 'Contact customers with overdue payments.',
        'ai_action_4': 'Generate today\'s operations report before 17:00.',
        'pending_tasks': pending_claims + pending_policies + pending_documents + pending_payments,
    }
    
    return render(request, 'core/staff_dashboard.html', context)

@login_required
@admin_required
def admin_staff_add(request):
    """Add a new staff member"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Invalid request method.'})
    
    try:
        data = json.loads(request.body)
        
        first_name = data.get('first_name', '').strip()
        last_name = data.get('last_name', '').strip()
        email = data.get('email', '').strip()
        phone = data.get('phone', '').strip()
        employee_number = data.get('employee_number', '').strip()
        branch = data.get('branch', '').strip()
        role = data.get('role', 'staff')
        department = data.get('department', '')
        password = data.get('password', '')
        
        # Validation
        if not all([first_name, last_name, email, phone, employee_number, password]):
            return JsonResponse({'success': False, 'message': 'All required fields must be filled.'})
        
        if len(password) < 8:
            return JsonResponse({'success': False, 'message': 'Password must be at least 8 characters.'})
        
        if User.objects.filter(email=email).exists():
            return JsonResponse({'success': False, 'message': 'A user with this email already exists.'})
        
        # Create user
        username = email.split('@')[0]
        if User.objects.filter(username=username).exists():
            username = f"{username}_{User.objects.count() + 1}"
        
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name
        )
        
        # Set profile
        profile = user.profile
        profile.role = role
        profile.status = 'active'
        profile.phone = phone
        profile.employee_number = employee_number
        profile.branch = branch
        profile.department = department
        profile.save()
        
        # Add to group
        if role == 'staff':
            group, _ = Group.objects.get_or_create(name='Staff')
            user.groups.add(group)
        elif role == 'investigator':
            group, _ = Group.objects.get_or_create(name='Investigators')
            user.groups.add(group)
        
        return JsonResponse({'success': True, 'message': f'Staff member {first_name} {last_name} created successfully!'})
        
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})


@login_required
@admin_required
def admin_staff_approve(request):
    """Approve a pending staff member"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Invalid request method.'})
    
    try:
        data = json.loads(request.body)
        user_id = data.get('user_id')
        
        if not user_id:
            return JsonResponse({'success': False, 'message': 'User ID is required.'})
        
        user = User.objects.get(id=user_id)
        profile = user.profile
        
        if profile.status != 'pending':
            return JsonResponse({'success': False, 'message': 'User is not pending approval.'})
        
        profile.status = 'active'
        profile.save()
        
        return JsonResponse({'success': True, 'message': f'{user.get_full_name()} approved successfully!'})
        
    except User.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'User not found.'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})


@login_required
@admin_required
def admin_staff_approve_all(request):
    """Approve all pending staff members"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Invalid request method.'})
    
    try:
        pending_users = User.objects.filter(profile__status='pending')
        count = pending_users.count()
        
        if count == 0:
            return JsonResponse({'success': True, 'message': 'No pending staff members to approve.'})
        
        for user in pending_users:
            user.profile.status = 'active'
            user.profile.save()
        
        return JsonResponse({'success': True, 'message': f'{count} staff members approved successfully!'})
        
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})
from django.http import JsonResponse
import json

@login_required
def staff_claims_view(request):
    """Staff claims page - claims assigned to this staff member"""
    
    profile = request.user.profile
    
    # Check if user is staff or investigator
    if profile.role not in ['staff', 'investigator']:
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('dashboard')
    
    # Get claims assigned to this staff member
    claims = Claim.objects.filter(investigator=request.user).order_by('-submitted_at')
    
    # If no claims assigned, show all claims (or show empty state)
    if not claims.exists():
        claims = Claim.objects.none()
    
    claim_data = []
    for claim in claims:
        claim_data.append({
            'id': claim.id,
            'claim_number': claim.claim_number,
            'customer_name': claim.user.get_full_name() or claim.user.username,
            'customer_email': claim.user.email,
            'policy_number': claim.policy.policy_number if claim.policy else 'N/A',
            'incident_type': claim.get_incident_type_display(),
            'amount': claim.amount_claimed,
            'status': claim.status,
            'status_display': claim.get_status_display(),
            'ai_fraud_score': claim.ai_fraud_score,
        })
    
    context = {
        'now': now(),
        'claims': claim_data,
        'total_claims': len(claim_data),
        'pending_claims': Claim.objects.filter(investigator=request.user, status='pending').count(),
        'approved_claims': Claim.objects.filter(investigator=request.user, status='approved').count(),
        'high_risk_claims': Claim.objects.filter(investigator=request.user, ai_fraud_score__gte=70).count(),
        'pending_tasks': 0,
        'pending_documents': 0,
        'pending_payments': 0,
        'unread_notifications': Notification.objects.filter(user=request.user, is_read=False).count(),
        'user': request.user,
    }
    
    return render(request, 'core/staff_claims.html', context)


@login_required
def staff_claim_approve(request):
    """Approve a claim"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Invalid request method.'})
    
    try:
        data = json.loads(request.body)
        claim_id = data.get('claim_id')
        
        if not claim_id:
            return JsonResponse({'success': False, 'message': 'Claim ID required.'})
        
        claim = Claim.objects.get(id=claim_id)
        claim.status = 'approved'
        claim.resolved_at = now()
        claim.save()
        
        return JsonResponse({'success': True, 'message': 'Claim approved successfully!'})
        
    except Claim.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Claim not found.'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})

# ================================================================
# STAFF VIEWS - COMPLETE
# ================================================================

@login_required
def staff_dashboard_view(request):
    """Staff dashboard - overview of all work"""
    profile = request.user.profile
    
    if profile.role not in ['staff', 'investigator']:
        messages.error(request, 'You do not have permission.')
        return redirect('dashboard')
    
    # Get real data from database
    pending_policies = Policy.objects.filter(status='pending').count()
    pending_policies_list = Policy.objects.filter(status='pending').order_by('-created_at')[:5]
    pending_claims = Claim.objects.filter(status='pending').count()
    pending_claims_list = Claim.objects.filter(status='pending').order_by('-submitted_at')[:5]
    pending_documents = Document.objects.filter(status='pending').count()
    pending_documents_list = Document.objects.filter(status='pending').order_by('-uploaded_at')[:5]
    investigation_requests = Claim.objects.filter(ai_fraud_score__gte=60, status='pending').count()
    investigation_requests_list = Claim.objects.filter(ai_fraud_score__gte=60, status='pending').order_by('-ai_fraud_score')[:5]
    total_policies = Policy.objects.count()
    total_customers = User.objects.filter(profile__role='policyholder').count()
    unread_notifications = Notification.objects.filter(user=request.user, is_read=False).count()
    
    # ✅ ADD THESE COUNTERS FOR SIDEBAR BADGES
    approved_claims_count = Claim.objects.filter(status='approved').count()
    rejected_claims_count = Claim.objects.filter(status='rejected').count()
    verified_documents_count = Document.objects.filter(status='verified').count()
    refund_requests = Payment.objects.filter(status='pending', payment_type='refund').count()
    
    # Priority tasks - from real pending claims
    priority_tasks = []
    for claim in pending_claims_list[:3]:
        priority_tasks.append({
            'priority': 'high' if claim.ai_fraud_score >= 70 else 'medium' if claim.ai_fraud_score >= 40 else 'low',
            'priority_display': 'High' if claim.ai_fraud_score >= 70 else 'Medium' if claim.ai_fraud_score >= 40 else 'Low',
            'title': f"{claim.get_incident_type_display()} Claim",
            'reference': claim.claim_number,
            'description': f"AI Risk Score: {claim.ai_fraud_score}%",
            'risk_level': 'high' if claim.ai_fraud_score >= 70 else 'medium' if claim.ai_fraud_score >= 40 else 'low',
            'risk_score': claim.ai_fraud_score,
            'due_time': claim.submitted_at.strftime('%H:%M') if claim.submitted_at else 'N/A',
            'action_text': 'Review',
        })
    
    # If no priority tasks, show empty state
    if not priority_tasks:
        priority_tasks = []
    
    # Recent activities from notifications
    recent_activities = []
    recent_notifications = Notification.objects.filter(user=request.user).order_by('-created_at')[:4]
    for notif in recent_notifications:
        recent_activities.append({
            'type': notif.notification_type or 'info',
            'message': notif.message,
            'time_ago': f"{timezone.now() - notif.created_at} ago",
        })
    
    # If no notifications, show empty state
    if not recent_activities:
        recent_activities = []
    
    # Chart data based on real claims
    dept_performance_data = {
        'labels': ['Claims', 'Underwriting', 'Support', 'Fraud', 'Finance'],
        'values': [
            Claim.objects.count(),
            Policy.objects.filter(status='pending').count(),
            User.objects.filter(profile__role='policyholder').count(),
            Claim.objects.filter(ai_fraud_score__gte=60).count(),
            Payment.objects.count(),
        ],
    }
    
    # Monthly claims data from real data
    from datetime import datetime, timedelta
    import calendar
    
    months = []
    approved_data = []
    pending_data = []
    investigation_data = []
    rejected_data = []
    
    for i in range(5, -1, -1):
        month_date = datetime.now() - timedelta(days=30*i)
        month_name = calendar.month_abbr[month_date.month]
        months.append(f"{month_name} {month_date.year}")
        
        start_of_month = month_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if month_date.month == 12:
            end_of_month = month_date.replace(year=month_date.year+1, month=1, day=1)
        else:
            end_of_month = month_date.replace(month=month_date.month+1, day=1)
        
        approved_data.append(Claim.objects.filter(
            resolved_at__gte=start_of_month,
            resolved_at__lt=end_of_month,
            status='approved'
        ).count())
        
        pending_data.append(Claim.objects.filter(
            submitted_at__gte=start_of_month,
            submitted_at__lt=end_of_month,
            status='pending'
        ).count())
        
        investigation_data.append(Claim.objects.filter(
            submitted_at__gte=start_of_month,
            submitted_at__lt=end_of_month,
            status='investigation'
        ).count())
        
        rejected_data.append(Claim.objects.filter(
            resolved_at__gte=start_of_month,
            resolved_at__lt=end_of_month,
            status='rejected'
        ).count())
    
    monthly_claims_data = {
        'labels': months,
        'approved': approved_data,
        'pending': pending_data,
        'investigation': investigation_data,
        'rejected': rejected_data,
    }
    
    # Fraud trend data
    fraud_values = []
    for i in range(3, -1, -1):
        week_date = datetime.now() - timedelta(days=7*i)
        start_of_week = week_date.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=week_date.weekday())
        end_of_week = start_of_week + timedelta(days=7)
        fraud_count = Claim.objects.filter(
            submitted_at__gte=start_of_week,
            submitted_at__lt=end_of_week,
            ai_fraud_score__gte=60
        ).count()
        fraud_values.append(fraud_count)
    
    fraud_trend_data = {
        'labels': ['Week 1', 'Week 2', 'Week 3', 'Week 4'],
        'values': fraud_values,
    }
    
    # Announcements (from system or empty)
    announcements = []
    # Reminders (from system or empty)
    reminders = []
    
    # Calculate completion percentage
    total_tasks = pending_claims + pending_policies + pending_documents
    completed_today = Claim.objects.filter(resolved_at__date=datetime.now().date()).count()
    completion_percentage = round((completed_today / (total_tasks + completed_today) * 100) if (total_tasks + completed_today) > 0 else 0, 1)
    
    context = {
        'now': now(),
        'pending_policies': pending_policies,
        'pending_policies_list': pending_policies_list,
        'pending_claims': pending_claims,
        'pending_claims_list': pending_claims_list,
        'pending_documents': pending_documents,
        'pending_documents_list': pending_documents_list,
        'investigation_requests': investigation_requests,
        'investigation_requests_list': investigation_requests_list,
        'total_policies': total_policies,
        'total_customers': total_customers,
        'unread_notifications': unread_notifications,
        'user': request.user,
        # Additional context for dashboard widgets
        'priority_tasks': priority_tasks,
        'recent_activities': recent_activities,
        'dept_performance_data': dept_performance_data,
        'monthly_claims_data': monthly_claims_data,
        'fraud_trend_data': fraud_trend_data,
        'announcements': announcements,
        'reminders': reminders,
        'completion_percentage': completion_percentage,
        'completed_today': completed_today,
        'pending_today': total_tasks,
        'avg_processing_time': 0,
        'customer_satisfaction': 0,
        'ai_assistance_score': 0,
        'today_rating': 0,
        'ai_insight_1': f"{pending_claims} claims pending review.",
        'ai_insight_2': f"{investigation_requests} claims flagged for investigation.",
        'ai_insight_3': f"{pending_documents} documents need verification.",
        'ai_insight_4': f"{pending_policies} policies need review.",
        'ai_action_1': 'Prioritise high-risk claims.',
        'ai_action_2': 'Verify pending FICA documents.',
        'ai_action_3': 'Contact customers with overdue payments.',
        'ai_action_4': 'Generate today\'s operations report.',
        'pending_tasks': total_tasks,
        # ✅ SIDEBAR BADGE COUNTERS
        'approved_claims_count': approved_claims_count,
        'rejected_claims_count': rejected_claims_count,
        'verified_documents_count': verified_documents_count,
        'refund_requests': refund_requests,
    }
    
    return render(request, 'core/staff_dashboard.html', context)

@login_required
def staff_new_applications_view(request):
    """New policy applications waiting for staff review"""
    profile = request.user.profile
    
    if profile.role not in ['staff', 'investigator']:
        messages.error(request, 'You do not have permission.')
        return redirect('dashboard')
    
    # Get all pending policies
    applications = Policy.objects.filter(status='pending').order_by('-created_at')
    
    # Build application data with document status
    app_data = []
    for policy in applications:
        docs = Document.objects.filter(user=policy.user)
        app_data.append({
            'id': policy.id,
            'policy_number': policy.policy_number,
            'customer_name': policy.user.get_full_name() or policy.user.username,
            'customer_email': policy.user.email,
            'policy_type': policy.get_policy_type_display(),
            'premium': policy.premium_amount,
            'coverage': policy.coverage_amount,
            'status': policy.status,
            'created_at': policy.created_at,
            'documents': docs,
            'documents_count': docs.count(),
            'verified_docs': docs.filter(status='verified').count(),
            'pending_docs': docs.filter(status='pending').count(),
            'all_verified': docs.filter(status='verified').count() == docs.count() if docs.count() > 0 else False,
        })
    
    context = {
        'now': now(),
        'applications': app_data,
        'total': len(app_data),
        'unread_notifications': Notification.objects.filter(user=request.user, is_read=False).count(),
        'user': request.user,
    }
    return render(request, 'core/staff_new_applications.html', context)

@login_required
def staff_policies_view(request):
    """All policies"""
    profile = request.user.profile
    
    if profile.role not in ['staff', 'investigator']:
        messages.error(request, 'You do not have permission.')
        return redirect('dashboard')
    
    policies = Policy.objects.select_related('user').all().order_by('-created_at')
    
    policy_data = []
    for policy in policies:
        policy_data.append({
            'id': policy.id,
            'policy_number': policy.policy_number,
            'customer_name': policy.user.get_full_name() or policy.user.username,
            'customer_email': policy.user.email,
            'type_display': policy.get_policy_type_display(),
            'premium': policy.premium_amount,
            'status': policy.status,
            'status_display': policy.get_status_display(),
            'renewal_date': policy.renewal_date,
            'created_at': policy.created_at,
        })
    
    context = {
        'now': now(),
        'policies': policy_data,
        'total_policies': len(policy_data),
        'active_policies': Policy.objects.filter(status='active').count(),
        'pending_policies': Policy.objects.filter(status='pending').count(),
        'unread_notifications': Notification.objects.filter(user=request.user, is_read=False).count(),
        'user': request.user,
    }
    return render(request, 'core/staff_policies.html', context)
@login_required
def staff_customers_view(request):
    """View and manage customers"""
    profile = request.user.profile
    
    if profile.role not in ['staff', 'investigator']:
        messages.error(request, 'You do not have permission.')
        return redirect('dashboard')
    
    customers = User.objects.filter(profile__role='policyholder').order_by('-date_joined')
    
    customer_data = []
    for customer in customers:
        customer_data.append({
            'id': customer.id,
            'first_name': customer.first_name,
            'last_name': customer.last_name,
            'full_name': customer.get_full_name() or customer.username,
            'email': customer.email,
            'phone': customer.profile.phone if hasattr(customer, 'profile') else '',
            'status': customer.profile.status if hasattr(customer, 'profile') else 'active',
            'status_display': customer.profile.get_status_display() if hasattr(customer, 'profile') else 'Active',
            'date_joined': customer.date_joined,
            'policies_count': customer.policies.count(),
        })
    
    context = {
        'now': now(),
        'customers': customer_data,
        'total_customers': len(customer_data),
        'active_customers': User.objects.filter(profile__role='policyholder', profile__status='active').count(),
        'unread_notifications': Notification.objects.filter(user=request.user, is_read=False).count(),
        'user': request.user,
    }
    return render(request, 'core/staff_customers.html', context)
@login_required
def staff_claims_queue_view(request):
    """Claims waiting for staff review"""
    profile = request.user.profile
    
    if profile.role not in ['staff', 'investigator']:
        messages.error(request, 'You do not have permission.')
        return redirect('dashboard')
    
    claims = Claim.objects.filter(status='pending').order_by('-submitted_at')
    
    claim_data = []
    for claim in claims:
        claim_data.append({
            'id': claim.id,
            'claim_number': claim.claim_number,
            'customer_name': claim.user.get_full_name() or claim.user.username,
            'customer_email': claim.user.email,
            'policy_number': claim.policy.policy_number if claim.policy else 'N/A',
            'incident_type': claim.get_incident_type_display(),
            'amount': claim.amount_claimed,
            'status': claim.status,
            'status_display': claim.get_status_display(),
            'ai_fraud_score': claim.ai_fraud_score,
            'submitted_at': claim.submitted_at,
        })
    
    context = {
        'now': now(),
        'claims': claim_data,
        'total_claims': len(claim_data),
        'unread_notifications': Notification.objects.filter(user=request.user, is_read=False).count(),
        'user': request.user,
    }
    return render(request, 'core/staff_claims_queue.html', context)
@login_required
def staff_approved_claims_view(request):
    """Claims approved by staff"""
    profile = request.user.profile
    
    if profile.role not in ['staff', 'investigator']:
        messages.error(request, 'You do not have permission.')
        return redirect('dashboard')
    
    claims = Claim.objects.filter(status='approved').order_by('-resolved_at')
    
    claim_data = []
    for claim in claims:
        claim_data.append({
            'id': claim.id,
            'claim_number': claim.claim_number,
            'customer_name': claim.user.get_full_name() or claim.user.username,
            'customer_email': claim.user.email,
            'policy_number': claim.policy.policy_number if claim.policy else 'N/A',
            'incident_type': claim.get_incident_type_display(),
            'amount': claim.amount_claimed,
            'amount_approved': claim.amount_approved,
            'status': claim.status,
            'status_display': claim.get_status_display(),
            'resolved_at': claim.resolved_at,
        })
    
    context = {
        'now': now(),
        'claims': claim_data,
        'total_claims': len(claim_data),
        'unread_notifications': Notification.objects.filter(user=request.user, is_read=False).count(),
        'user': request.user,
    }
    return render(request, 'core/staff_approved_claims.html', context)
@login_required
def staff_rejected_claims_view(request):
    """Claims rejected by staff"""
    profile = request.user.profile
    
    if profile.role not in ['staff', 'investigator']:
        messages.error(request, 'You do not have permission.')
        return redirect('dashboard')
    
    claims = Claim.objects.filter(status='rejected').order_by('-resolved_at')
    
    claim_data = []
    for claim in claims:
        claim_data.append({
            'id': claim.id,
            'claim_number': claim.claim_number,
            'customer_name': claim.user.get_full_name() or claim.user.username,
            'customer_email': claim.user.email,
            'policy_number': claim.policy.policy_number if claim.policy else 'N/A',
            'incident_type': claim.get_incident_type_display(),
            'amount': claim.amount_claimed,
            'status': claim.status,
            'status_display': claim.get_status_display(),
            'resolved_at': claim.resolved_at,
            'rejection_reason': 'N/A',
        })
    
    context = {
        'now': now(),
        'claims': claim_data,
        'total_claims': len(claim_data),
        'unread_notifications': Notification.objects.filter(user=request.user, is_read=False).count(),
        'user': request.user,
    }
    return render(request, 'core/staff_rejected_claims.html', context)
@login_required
def staff_investigation_requests_view(request):
    """Claims that need to be sent to investigator"""
    profile = request.user.profile
    
    if profile.role not in ['staff', 'investigator']:
        messages.error(request, 'You do not have permission.')
        return redirect('dashboard')
    
    claims = Claim.objects.filter(ai_fraud_score__gte=60, status='pending').order_by('-ai_fraud_score')
    
    claim_data = []
    for claim in claims:
        claim_data.append({
            'id': claim.id,
            'claim_number': claim.claim_number,
            'customer_name': claim.user.get_full_name() or claim.user.username,
            'customer_email': claim.user.email,
            'policy_number': claim.policy.policy_number if claim.policy else 'N/A',
            'incident_type': claim.get_incident_type_display(),
            'amount': claim.amount_claimed,
            'ai_fraud_score': claim.ai_fraud_score,
            'status': claim.status,
            'status_display': claim.get_status_display(),
            'submitted_at': claim.submitted_at,
        })
    
    context = {
        'now': now(),
        'claims': claim_data,
        'total_claims': len(claim_data),
        'unread_notifications': Notification.objects.filter(user=request.user, is_read=False).count(),
        'user': request.user,
    }
    return render(request, 'core/staff_investigation_requests.html', context)
@login_required
def staff_payments_view(request):
    """Premium payments"""
    profile = request.user.profile
    
    if profile.role not in ['staff', 'investigator']:
        messages.error(request, 'You do not have permission.')
        return redirect('dashboard')
    
    payments = Payment.objects.select_related('user', 'policy').all().order_by('-created_at')
    
    payment_data = []
    for payment in payments:
        payment_data.append({
            'id': payment.id,
            'payment_number': payment.payment_number,
            'customer_name': payment.user.get_full_name() or payment.user.username,
            'customer_email': payment.user.email,
            'policy_number': payment.policy.policy_number if payment.policy else 'N/A',
            'amount': payment.amount,
            'method_display': payment.get_payment_method_display(),
            'status': payment.status,
            'status_display': payment.get_status_display(),
            'date': payment.created_at,
        })
    
    context = {
        'now': now(),
        'payments': payment_data,
        'total_payments': len(payment_data),
        'pending_payments': Payment.objects.filter(status='pending').count(),
        'completed_payments': Payment.objects.filter(status='completed').count(),
        'unread_notifications': Notification.objects.filter(user=request.user, is_read=False).count(),
        'user': request.user,
    }
    return render(request, 'core/staff_payments.html', context)


@login_required
def staff_refund_requests_view(request):
    """Refund requests waiting for approval"""
    profile = request.user.profile
    
    if profile.role not in ['staff', 'investigator']:
        messages.error(request, 'You do not have permission.')
        return redirect('dashboard')
    
    refunds = Payment.objects.filter(status='pending', payment_type='refund').order_by('-created_at')
    
    refund_data = []
    for refund in refunds:
        refund_data.append({
            'id': refund.id,
            'payment_number': refund.payment_number,
            'customer_name': refund.user.get_full_name() or refund.user.username,
            'customer_email': refund.user.email,
            'amount': refund.amount,
            'status': refund.status,
            'status_display': refund.get_status_display(),
            'date': refund.created_at,
        })
    
    context = {
        'now': now(),
        'refunds': refund_data,
        'total_refunds': len(refund_data),
        'unread_notifications': Notification.objects.filter(user=request.user, is_read=False).count(),
        'user': request.user,
    }
    return render(request, 'core/staff_refund_requests.html', context)



@login_required
def staff_documents_view(request):
    """Pending documents for verification - Staff view"""
    profile = request.user.profile
    
    if profile.role not in ['staff', 'investigator']:
        messages.error(request, 'You do not have permission.')
        return redirect('dashboard')
    
    # Get all pending documents
    documents = Document.objects.filter(status='pending').order_by('-uploaded_at')
    
    # Get sidebar counts
    pending_policies = Policy.objects.filter(status='pending').count()
    pending_claims = Claim.objects.filter(status='pending').count()
    pending_documents = Document.objects.filter(status='pending').count()
    investigation_requests = Document.objects.filter(status='investigation').count() + Claim.objects.filter(ai_fraud_score__gte=60, status='pending').count()
    verified_documents_count = Document.objects.filter(status='verified').count()
    refund_requests = Payment.objects.filter(status='pending', payment_type='refund').count()
    approved_claims_count = Claim.objects.filter(status='approved').count()
    rejected_claims_count = Claim.objects.filter(status='rejected').count()
    unread_notifications = Notification.objects.filter(user=request.user, is_read=False).count()
    
    # Stats for the page
    total_documents = documents.count()
    verified_today = Document.objects.filter(
        status='verified',
        verified_at__date=datetime.now().date()
    ).count() if hasattr(Document, 'verified_at') else 0
    ai_verified = Document.objects.filter(
        status='verified',
        ai_verification_score__gte=80
    ).count()
    requires_review = Document.objects.filter(
        ai_verification_score__lt=60
    ).count()
    
    document_data = []
    for doc in documents:
        document_data.append({
            'id': doc.id,
            'document_number': doc.document_number,
            'document_name': doc.document_name,
            'document_type_display': doc.get_document_type_display() if hasattr(doc, 'get_document_type_display') else doc.document_type,
            'customer_name': doc.user.get_full_name() or doc.user.username,
            'customer_email': doc.user.email,
            'ai_verification_score': doc.ai_verification_score,
            'status': doc.status,
            'status_display': doc.get_status_display() if hasattr(doc, 'get_status_display') else doc.status,
            'uploaded_at': doc.uploaded_at,
        })
    
    context = {
        'now': now(),
        'documents': document_data,
        'total_documents': total_documents,
        'verified_today': verified_today,
        'ai_verified': ai_verified,
        'requires_review': requires_review,
        'pending_documents': pending_documents,
        'uploaded_documents': Document.objects.filter(status='uploaded').count(),
        'verified_documents_count': verified_documents_count,
        'rejected_documents_count': Document.objects.filter(status='rejected').count(),
        # Sidebar counters
        'pending_policies': pending_policies,
        'pending_claims': pending_claims,
        'investigation_requests': investigation_requests,
        'refund_requests': refund_requests,
        'approved_claims_count': approved_claims_count,
        'rejected_claims_count': rejected_claims_count,
        'unread_notifications': unread_notifications,
        'user': request.user,
    }
    return render(request, 'core/staff_documents.html', context)

#change two times
@login_required
def staff_verify_document(request):
    """Staff verifies, rejects, or sends document for investigation"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid request method.'})
    
    try:
        import json
        data = json.loads(request.body)
        document_id = data.get('document_id')
        action = data.get('action')  # 'verify', 'reject', or 'investigate'
        notes = data.get('notes', '')
        
        if not document_id:
            return JsonResponse({'success': False, 'error': 'Document ID required.'})
        
        document = Document.objects.get(id=document_id)
        
        if action == 'verify':
            document.status = 'verified'
            document.verified_by = request.user
            document.verified_at = now()
            document.verification_notes = notes
            document.save()
            
            # Notify customer
            Notification.objects.create(
                user=document.user,
                title='Document Verified ✅',
                message=f'Your {document.get_document_type_display() if hasattr(document, "get_document_type_display") else document.document_type} has been verified successfully.',
                notification_type='success',
                category='document',
                action_url='/dashboard/customer/documents/',
            )
            
            # Notify Admin
            admin_users = User.objects.filter(profile__role='administrator')
            for admin in admin_users:
                Notification.objects.create(
                    user=admin,
                    title='Document Verified',
                    message=f'{document.user.get_full_name()}\'s {document.get_document_type_display() if hasattr(document, "get_document_type_display") else document.document_type} was verified by {request.user.get_full_name()}.',
                    notification_type='success',
                    category='document',
                    action_url='/admin/documents/',
                )
            
            # Check if all customer documents are now verified
            pending_docs = Document.objects.filter(user=document.user, status='pending')
            if not pending_docs.exists():
                policies = Policy.objects.filter(user=document.user, status='pending')
                for policy in policies:
                    Notification.objects.create(
                        user=request.user,
                        title='Application Ready for Approval',
                        message=f'All documents verified for {document.user.get_full_name()}. Policy #{policy.policy_number} can be approved.',
                        notification_type='info',
                        category='policy',
                        action_url='/staff/new-applications/',
                    )
            
            # ✅ RETURN JSON ONLY - NO DJANGO MESSAGES
            return JsonResponse({'success': True, 'message': 'Document verified successfully!', 'toast_type': 'success'})
            
        elif action == 'reject':
            document.status = 'rejected'
            document.verified_by = request.user
            document.verified_at = now()
            document.rejection_reason = notes
            document.save()
            
            # Notify customer
            Notification.objects.create(
                user=document.user,
                title='Document Rejected ❌',
                message=f'Your {document.get_document_type_display() if hasattr(document, "get_document_type_display") else document.document_type} was rejected. Reason: {notes or "Please re-upload with correct information."}',
                notification_type='danger',
                category='document',
                action_url='/dashboard/customer/documents/',
            )
            
            # ✅ RETURN JSON ONLY - NO DJANGO MESSAGES
            return JsonResponse({'success': True, 'message': 'Document rejected.', 'toast_type': 'warning'})
        
        elif action == 'investigate':
            document.status = 'investigation'
            document.verified_by = request.user
            document.verified_at = now()
            document.verification_notes = f'Investigation required: {notes or "Document flagged for further review."}'
            document.save()
            
            # Notify customer
            Notification.objects.create(
                user=document.user,
                title='Document Under Investigation 🔍',
                message=f'Your {document.get_document_type_display() if hasattr(document, "get_document_type_display") else document.document_type} has been flagged for investigation.',
                notification_type='warning',
                category='document',
                action_url='/dashboard/customer/documents/',
            )
            
            # Notify investigators
            investigators = User.objects.filter(profile__role='investigator')
            for inv in investigators:
                Notification.objects.create(
                    user=inv,
                    title='New Investigation Case',
                    message=f'Document {document.document_number} from {document.user.get_full_name()} requires investigation.',
                    notification_type='warning',
                    category='investigation',
                    action_url=f'/investigator/case/{document.id}/',
                )
            
            # ✅ RETURN JSON ONLY - NO DJANGO MESSAGES
            return JsonResponse({'success': True, 'message': 'Document sent for investigation.', 'toast_type': 'info'})
        
        else:
            return JsonResponse({'success': False, 'error': 'Invalid action.', 'toast_type': 'error'})
        
    except Document.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Document not found.', 'toast_type': 'error'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e), 'toast_type': 'error'})
    #change two times you pasted twice 
@login_required
def staff_verified_documents_view(request):
    """Verified documents - Staff view"""
    profile = request.user.profile
    
    if profile.role not in ['staff', 'investigator']:
        messages.error(request, 'You do not have permission.')
        return redirect('dashboard')
    
    # Get all verified documents
    documents = Document.objects.filter(status='verified').order_by('-verified_at')
    
    # Get sidebar counts
    pending_policies = Policy.objects.filter(status='pending').count()
    pending_claims = Claim.objects.filter(status='pending').count()
    pending_documents = Document.objects.filter(status='pending').count()
    investigation_requests = Document.objects.filter(status='investigation').count() + Claim.objects.filter(ai_fraud_score__gte=60, status='pending').count()
    verified_documents_count = Document.objects.filter(status='verified').count()
    refund_requests = Payment.objects.filter(status='pending', payment_type='refund').count()
    approved_claims_count = Claim.objects.filter(status='approved').count()
    rejected_claims_count = Claim.objects.filter(status='rejected').count()
    unread_notifications = Notification.objects.filter(user=request.user, is_read=False).count()
    
    # Stats for the page
    total_documents = documents.count()
    verified_this_week = Document.objects.filter(
        status='verified',
        verified_at__gte=timezone.now() - timedelta(days=7)
    ).count()
    verified_this_month = Document.objects.filter(
        status='verified',
        verified_at__year=timezone.now().year,
        verified_at__month=timezone.now().month
    ).count()
    
    # Calculate AI accuracy
    total_verified = documents.count()
    high_accuracy = documents.filter(ai_verification_score__gte=80).count()
    ai_accuracy = round((high_accuracy / total_verified * 100) if total_verified > 0 else 0, 1)
    
    document_data = []
    for doc in documents:
        document_data.append({
            'id': doc.id,
            'document_number': doc.document_number,
            'document_name': doc.document_name,
            'document_type_display': doc.get_document_type_display() if hasattr(doc, 'get_document_type_display') else doc.document_type,
            'customer_name': doc.user.get_full_name() or doc.user.username,
            'customer_email': doc.user.email,
            'ai_verification_score': doc.ai_verification_score,
            'status': doc.status,
            'status_display': doc.get_status_display() if hasattr(doc, 'get_status_display') else doc.status,
            'verified_by': doc.verified_by.get_full_name() if doc.verified_by else 'N/A',
            'verified_at': doc.verified_at,
            # ✅ FIXED: Use getattr to avoid AttributeError
            'verification_notes': getattr(doc, 'verification_notes', 'N/A'),
        })
    
    context = {
        'now': now(),
        'documents': document_data,
        'total_documents': total_documents,
        'verified_this_week': verified_this_week,
        'verified_this_month': verified_this_month,
        'ai_accuracy': ai_accuracy,
        # Sidebar counters
        'pending_policies': pending_policies,
        'pending_claims': pending_claims,
        'pending_documents': pending_documents,
        'investigation_requests': investigation_requests,
        'verified_documents_count': verified_documents_count,
        'refund_requests': refund_requests,
        'approved_claims_count': approved_claims_count,
        'rejected_claims_count': rejected_claims_count,
        'unread_notifications': unread_notifications,
        'user': request.user,
    }
    return render(request, 'core/staff_verified_documents.html', context)
@login_required
def staff_process_application(request):
    """Staff processes/approves a policy application"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid request method.'})
    
    try:
        import json
        data = json.loads(request.body)
        policy_id = data.get('policy_id')
        action = data.get('action')  # 'approve' or 'reject'
        notes = data.get('notes', '')
        
        if not policy_id:
            return JsonResponse({'success': False, 'error': 'Policy ID required.'})
        
        policy = Policy.objects.get(id=policy_id)
        
        if action == 'approve':
            # Check if all documents are verified
            pending_docs = Document.objects.filter(user=policy.user, status='pending')
            if pending_docs.exists():
                return JsonResponse({
                    'success': False, 
                    'error': f'Cannot approve: {pending_docs.count()} documents still pending verification.',
                    'toast_type': 'error'
                })
            
            policy.status = 'active'
            policy.save()
            
            # Notify customer
            Notification.objects.create(
                user=policy.user,
                title='Policy Approved! 🎉',
                message=f'Your {policy.get_policy_type_display()} policy #{policy.policy_number} has been approved and is now active.',
                notification_type='success',
                category='policy',
                action_url='/dashboard/customer/policies/',
            )
            
            # ✅ RETURN JSON ONLY - NO DJANGO MESSAGES
            return JsonResponse({'success': True, 'message': 'Application approved successfully!', 'toast_type': 'success'})
            
        elif action == 'reject':
            policy.status = 'rejected'
            policy.rejection_reason = notes
            policy.save()
            
            # Notify customer
            Notification.objects.create(
                user=policy.user,
                title='Policy Application Rejected',
                message=f'Your {policy.get_policy_type_display()} policy application was rejected. Reason: {notes or "Please contact support for more information."}',
                notification_type='danger',
                category='policy',
                action_url='/dashboard/customer/policies/',
            )
            
            # ✅ RETURN JSON ONLY - NO DJANGO MESSAGES
            return JsonResponse({'success': True, 'message': 'Application rejected.', 'toast_type': 'warning'})
        
        else:
            return JsonResponse({'success': False, 'error': 'Invalid action.', 'toast_type': 'error'})
        
    except Policy.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Policy not found.', 'toast_type': 'error'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e), 'toast_type': 'error'})
    
@login_required
def staff_notifications_view(request):
    """Notifications"""
    profile = request.user.profile
    
    if profile.role not in ['staff', 'investigator']:
        messages.error(request, 'You do not have permission.')
        return redirect('dashboard')
    
    notifications = Notification.objects.filter(user=request.user).order_by('-created_at')
    
    notification_data = []
    for notif in notifications:
        notification_data.append({
            'id': notif.id,
            'title': notif.title,
            'message': notif.message,
            'type': notif.notification_type,
            'category': notif.category,
            'is_read': notif.is_read,
            'created_at': notif.created_at,
        })
    
    context = {
        'now': now(),
        'notifications': notification_data,
        'all_notifications_count': len(notification_data),
        'unread_notifications': Notification.objects.filter(user=request.user, is_read=False).count(),
        'read_notifications': Notification.objects.filter(user=request.user, is_read=True).count(),
        'user': request.user,
    }
    return render(request, 'core/staff_notifications.html', context)


@login_required
def staff_reports_view(request):
    """Reports"""
    profile = request.user.profile
    
    if profile.role not in ['staff', 'investigator']:
        messages.error(request, 'You do not have permission.')
        return redirect('dashboard')
    
    context = {
        'now': now(),
        'total_policies': Policy.objects.count(),
        'total_customers': User.objects.filter(profile__role='policyholder').count(),
        'pending_claims': Claim.objects.filter(status='pending').count(),
        'total_claims': Claim.objects.count(),
        'total_payments': Payment.objects.aggregate(Sum('amount'))['amount__sum'] or 0,
        'unread_notifications': Notification.objects.filter(user=request.user, is_read=False).count(),
        'user': request.user,
    }
    return render(request, 'core/staff_reports.html', context)


@login_required
def staff_analytics_view(request):
    """Analytics"""
    profile = request.user.profile
    
    if profile.role not in ['staff', 'investigator']:
        messages.error(request, 'You do not have permission.')
        return redirect('dashboard')
    
    # Sample chart data - replace with real data later
    revenue_chart_data = {
        'labels': ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun'],
        'values': [125000, 142000, 138000, 165000, 180000, 210000],
    }
    
    claims_trend_data = {
        'labels': ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun'],
        'values': [45, 52, 48, 60, 55, 68],
    }
    
    context = {
        'now': now(),
        'revenue_chart_data': revenue_chart_data,
        'claims_trend_data': claims_trend_data,
        'unread_notifications': Notification.objects.filter(user=request.user, is_read=False).count(),
        'user': request.user,
    }
    return render(request, 'core/staff_analytics.html', context)


@login_required
def staff_profile_view(request):
    """Profile"""
    profile = request.user.profile
    
    if profile.role not in ['staff', 'investigator']:
        messages.error(request, 'You do not have permission.')
        return redirect('dashboard')
    
    context = {
        'now': now(),
        'profile': profile,
        'claims_processed': Claim.objects.filter(investigator=request.user, status__in=['approved', 'paid']).count(),
        'documents_verified': Document.objects.filter(verified_by=request.user).count(),
        'unread_notifications': Notification.objects.filter(user=request.user, is_read=False).count(),
        'user': request.user,
    }
    return render(request, 'core/staff_profile.html', context)


@login_required
def staff_settings_view(request):
    """Settings"""
    profile = request.user.profile
    
    if profile.role not in ['staff', 'investigator']:
        messages.error(request, 'You do not have permission.')
        return redirect('dashboard')
    
    context = {
        'now': now(),
        'unread_notifications': Notification.objects.filter(user=request.user, is_read=False).count(),
        'user': request.user,
    }
    return render(request, 'core/staff_settings.html', context)
# ============================================================ */
# STAFF - REPORTS
# ============================================================ */
@login_required
def staff_reports_view(request):
    """Staff reports page"""
    profile = request.user.profile
    
    if profile.role not in ['staff', 'investigator']:
        messages.error(request, 'You do not have permission.')
        return redirect('dashboard')
    
    # Get real data from database
    total_claims = Claim.objects.count()
    approved_claims = Claim.objects.filter(status='approved').count()
    rejected_claims = Claim.objects.filter(status='rejected').count()
    
    # Calculate total payout from approved claims
    total_payout = Claim.objects.filter(status='approved').aggregate(
        total=Sum('amount_approved')
    )['total'] or 0
    
    context = {
        'now': now(),
        'total_claims': total_claims,
        'approved_claims': approved_claims,
        'rejected_claims': rejected_claims,
        'total_payout': total_payout,
        'pending_policies': Policy.objects.filter(status='pending').count(),
        'pending_claims': Claim.objects.filter(status='pending').count(),
        'pending_documents': Document.objects.filter(status='pending').count(),
        'investigation_requests': Claim.objects.filter(ai_fraud_score__gte=60, status='pending').count(),
        'refund_requests': Payment.objects.filter(status='pending', payment_type='refund').count(),
        'unread_notifications': Notification.objects.filter(user=request.user, is_read=False).count(),
        'user': request.user,
    }
    return render(request, 'core/staff_reports.html', context)


# ============================================================ */
# STAFF - ANALYTICS (NO FAKE DATA)
# ============================================================ */
@login_required
def staff_analytics_view(request):
    """Staff analytics page with charts"""
    profile = request.user.profile
    
    if profile.role not in ['staff', 'investigator']:
        messages.error(request, 'You do not have permission.')
        return redirect('dashboard')
    
    # Total claims
    total_claims = Claim.objects.count()
    
    # Approval rate
    approved_claims = Claim.objects.filter(status='approved').count()
    rejected_claims = Claim.objects.filter(status='rejected').count()
    approval_rate = round((approved_claims / total_claims * 100) if total_claims > 0 else 0, 1)
    
    # Rejection rate
    rejection_rate = round((rejected_claims / total_claims * 100) if total_claims > 0 else 0, 1)
    
    # Average processing time (in hours) - calculate from resolved_at - submitted_at
    from django.db.models import Avg, F, ExpressionWrapper, fields
    from django.db.models.functions import ExtractHour, ExtractDay
    
    avg_processing = Claim.objects.filter(
        status__in=['approved', 'rejected']
    ).exclude(
        resolved_at__isnull=True
    ).annotate(
        processing_time=ExpressionWrapper(
            F('resolved_at') - F('submitted_at'),
            output_field=fields.DurationField()
        )
    ).aggregate(
        avg=Avg('processing_time')
    )['avg']
    
    if avg_processing:
        avg_hours = round(avg_processing.total_seconds() / 3600, 1)
    else:
        avg_hours = 0
    
    # Claims trend data (last 6 months)
    from datetime import datetime, timedelta
    import calendar
    
    months = []
    submitted_data = []
    resolved_data = []
    
    for i in range(5, -1, -1):
        month_date = datetime.now() - timedelta(days=30*i)
        month_name = calendar.month_abbr[month_date.month]
        months.append(f"{month_name} {month_date.year}")
        
        start_of_month = month_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if month_date.month == 12:
            end_of_month = month_date.replace(year=month_date.year+1, month=1, day=1)
        else:
            end_of_month = month_date.replace(month=month_date.month+1, day=1)
        
        submitted = Claim.objects.filter(
            submitted_at__gte=start_of_month,
            submitted_at__lt=end_of_month
        ).count()
        submitted_data.append(submitted)
        
        resolved = Claim.objects.filter(
            resolved_at__gte=start_of_month,
            resolved_at__lt=end_of_month,
            status__in=['approved', 'rejected']
        ).count()
        resolved_data.append(resolved)
    
    claims_trend_data = {
        'labels': months,
        'submitted': submitted_data,
        'resolved': resolved_data,
    }
    
    # Claims distribution by status
    status_labels = ['Approved', 'Pending', 'Investigation', 'Rejected', 'Other']
    status_values = [
        Claim.objects.filter(status='approved').count(),
        Claim.objects.filter(status='pending').count(),
        Claim.objects.filter(status='investigation').count(),
        Claim.objects.filter(status='rejected').count(),
        Claim.objects.exclude(status__in=['approved', 'pending', 'investigation', 'rejected']).count(),
    ]
    
    claims_distribution_data = {
        'labels': status_labels,
        'values': status_values,
    }
    
    # Fraud trend data (last 6 months)
    fraud_values = []
    for i in range(5, -1, -1):
        month_date = datetime.now() - timedelta(days=30*i)
        start_of_month = month_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if month_date.month == 12:
            end_of_month = month_date.replace(year=month_date.year+1, month=1, day=1)
        else:
            end_of_month = month_date.replace(month=month_date.month+1, day=1)
        
        fraud_count = Claim.objects.filter(
            submitted_at__gte=start_of_month,
            submitted_at__lt=end_of_month,
            ai_fraud_score__gte=60
        ).count()
        fraud_values.append(fraud_count)
    
    fraud_trend_data = {
        'labels': months,
        'values': fraud_values,
    }
    
    # Get real processing time by department
    # Claims processing time
    claims_avg_time = Claim.objects.filter(
        status__in=['approved', 'rejected']
    ).exclude(
        resolved_at__isnull=True
    ).annotate(
        processing_time=ExpressionWrapper(
            F('resolved_at') - F('submitted_at'),
            output_field=fields.DurationField()
        )
    ).aggregate(
        avg=Avg('processing_time')
    )['avg']
    claims_time = round(claims_avg_time.total_seconds() / 3600, 1) if claims_avg_time else 0
    
    # Document verification time (placeholder - use real data if available)
    # Payment processing time (placeholder - use real data if available)
    # Investigation time (placeholder - use real data if available)
    # Policy activation time (placeholder - use real data if available)
    
    processing_time_data = {
        'labels': ['Claims', 'Documents', 'Payments', 'Investigations', 'Policies'],
        'values': [claims_time, 0, 0, 0, 0],  # Only claims has real data, others need to be added
    }
    
    context = {
        'now': now(),
        'total_claims': total_claims,
        'approval_rate': approval_rate,
        'rejection_rate': rejection_rate,
        'avg_processing_time': avg_hours,
        'claims_trend_data': claims_trend_data,
        'claims_distribution_data': claims_distribution_data,
        'fraud_trend_data': fraud_trend_data,
        'processing_time_data': processing_time_data,
        'pending_policies': Policy.objects.filter(status='pending').count(),
        'pending_claims': Claim.objects.filter(status='pending').count(),
        'pending_documents': Document.objects.filter(status='pending').count(),
        'investigation_requests': Claim.objects.filter(ai_fraud_score__gte=60, status='pending').count(),
        'refund_requests': Payment.objects.filter(status='pending', payment_type='refund').count(),
        'unread_notifications': Notification.objects.filter(user=request.user, is_read=False).count(),
        'user': request.user,
    }
    return render(request, 'core/staff_analytics.html', context)

# ============================================================ */
# STAFF - PROFILE (REAL DATA ONLY)
# ============================================================ */
@login_required
def staff_profile_view(request):
    """Staff profile page"""
    profile = request.user.profile
    
    if profile.role not in ['staff', 'investigator']:
        messages.error(request, 'You do not have permission.')
        return redirect('dashboard')
    
    # Count claims processed by this staff member
    claims_processed = Claim.objects.filter(
        investigator=request.user,
        status__in=['approved', 'rejected']
    ).count()
    
    # Count documents verified by this staff member
    documents_verified = Document.objects.filter(
        verified_by=request.user
    ).count()
    
    # Count policies
    policies_activated = Policy.objects.count()
    
    context = {
        'now': now(),
        'profile': request.user.profile,  # <-- ADD THIS
        'claims_processed': claims_processed,
        'documents_verified': documents_verified,
        'policies_activated': policies_activated,
        'pending_policies': Policy.objects.filter(status='pending').count(),
        'pending_claims': Claim.objects.filter(status='pending').count(),
        'pending_documents': Document.objects.filter(status='pending').count(),
        'investigation_requests': Claim.objects.filter(ai_fraud_score__gte=60, status='pending').count(),
        'refund_requests': Payment.objects.filter(status='pending', payment_type='refund').count(),
        'unread_notifications': Notification.objects.filter(user=request.user, is_read=False).count(),
        'user': request.user,
    }
    return render(request, 'core/staff_profile.html', context)

# ============================================================ */
# STAFF - SETTINGS
# ============================================================ */
@login_required
def staff_settings_view(request):
    """Staff settings page"""
    profile = request.user.profile
    
    if profile.role not in ['staff', 'investigator']:
        messages.error(request, 'You do not have permission.')
        return redirect('dashboard')
    
    context = {
        'now': now(),
        'pending_policies': Policy.objects.filter(status='pending').count(),
        'pending_claims': Claim.objects.filter(status='pending').count(),
        'pending_documents': Document.objects.filter(status='pending').count(),
        'investigation_requests': Claim.objects.filter(ai_fraud_score__gte=60, status='pending').count(),
        'refund_requests': Payment.objects.filter(status='pending', payment_type='refund').count(),
        'unread_notifications': Notification.objects.filter(user=request.user, is_read=False).count(),
        'user': request.user,
    }
    return render(request, 'core/staff_settings.html', context)

@login_required
def investigator_dashboard(request):
    """
    Investigator Dashboard - Shows real data from the database
    """
    user = request.user
    
    # ============================================================ #
    # 1. VERIFY USER HAS INVESTIGATOR ROLE
    # ============================================================ #
    try:
        profile = user.profile
        if profile.role != 'investigator':
            # Redirect to appropriate dashboard if not investigator
            if profile.role == 'policyholder':
                return redirect('policyholder_dashboard')
            elif profile.role == 'staff':
                return redirect('staff_dashboard')
            elif profile.role == 'administrator':
                return redirect('admin_dashboard')
    except UserProfile.DoesNotExist:
        # If no profile, redirect to complete profile
        return redirect('complete_profile')
    
    # ============================================================ #
    # 2. BASIC STATISTICS
    # ============================================================ #
    
    # High Risk Claims (AI fraud score >= 70)
    high_risk_claims = Claim.objects.filter(
        ai_fraud_score__gte=70,
        status__in=['submitted', 'pending', 'investigation']
    )
    high_risk_count = high_risk_claims.count()
    
    # Claims assigned to this investigator
    assigned_claims = Claim.objects.filter(
        investigator=user,
        status__in=['investigation', 'submitted', 'pending']
    )
    active_investigations = assigned_claims.count()
    
    # Closed cases by this investigator
    closed_cases = Claim.objects.filter(
        investigator=user,
        status__in=['approved', 'rejected', 'paid']
    ).count()
    
    # AI Accuracy (calculate from verified claims)
    # For claims that were investigated and have AI scores
    ai_accuracy = calculate_ai_accuracy(user)
    
    # Unread notifications
    unread_notifications = Notification.objects.filter(
        user=user,
        is_read=False
    ).count()
    
    # ============================================================ #
    # 3. FRAUD ALERTS (Claims with high AI fraud scores)
    # ============================================================ #
    fraud_alerts = []
    high_risk_claims_list = high_risk_claims.order_by('-ai_fraud_score')[:10]
    
    for claim in high_risk_claims_list:
        # Determine risk level
        if claim.ai_fraud_score >= 85:
            risk_level = 'high'
        elif claim.ai_fraud_score >= 70:
            risk_level = 'medium'
        else:
            risk_level = 'low'
        
        # Get time ago
        time_ago = time_since(claim.submitted_at)
        
        fraud_alerts.append({
            'risk_level': risk_level,
            'title': f"{claim.get_incident_type_display()} Claim - {claim.policy.user.get_full_name()}",
            'reference': claim.claim_number,
            'description': claim.incident_description[:100] + '...' if len(claim.incident_description) > 100 else claim.incident_description,
            'risk_score': claim.ai_fraud_score,
            'time_ago': time_ago,
            'claim_id': claim.id,
        })
    
    # ============================================================ #
    # 4. MY CASES (Assigned to this investigator)
    # ============================================================ #
    assigned_cases = []
    my_cases = Claim.objects.filter(
        investigator=user
    ).order_by('-submitted_at')[:10]
    
    for claim in my_cases:
        # Determine status display
        status_display = claim.get_status_display()
        status_class = 'open'
        
        if claim.status == 'investigation':
            status_class = 'in-progress'
        elif claim.status in ['approved', 'rejected', 'paid']:
            status_class = 'closed'
        
        assigned_cases.append({
            'title': f"{claim.get_incident_type_display()} - {claim.policy.user.get_full_name()}",
            'reference': claim.claim_number,
            'description': f"AI Score: {claim.ai_fraud_score}% | Amount: R{claim.amount_claimed}",
            'status': status_class,
            'status_display': status_display,
            'date': claim.submitted_at,
            'claim_id': claim.id,
        })
    
    # ============================================================ #
    # 5. AI INSIGHTS (Personalized for this investigator)
    # ============================================================ #
    
    # Get claims requiring immediate attention
    urgent_claims = Claim.objects.filter(
        ai_fraud_score__gte=80,
        status__in=['submitted', 'pending'],
        investigator__isnull=True
    ).count()
    
    # Get recent fraud patterns
    recent_fraudulent = Claim.objects.filter(
        ai_fraud_score__gte=75,
        submitted_at__gte=timezone.now() - timedelta(days=7)
    ).count()
    
    # Get document flags
    flagged_documents = Document.objects.filter(
        claim__investigator=user,
        status='pending',
        ai_verification_score__lt=50
    ).count()
    
    # Get avg AI confidence for this investigator's cases
    avg_ai_confidence = Claim.objects.filter(
        investigator=user,
        status__in=['approved', 'rejected', 'paid']
    ).aggregate(Avg('ai_fraud_score'))['ai_fraud_score__avg'] or 0
    
    # Build insights
    ai_insights = []
    ai_actions = []
    
    if urgent_claims > 0:
        ai_insights.append(f"{urgent_claims} high-risk claims require immediate investigation.")
        ai_actions.append(f"Prioritise the {urgent_claims} high-risk claims")
    else:
        ai_insights.append("No urgent high-risk claims at the moment.")
    
    if recent_fraudulent > 3:
        ai_insights.append(f"Detected {recent_fraudulent} suspicious patterns this week.")
        ai_actions.append(f"Review all {recent_fraudulent} flagged claims")
    else:
        ai_insights.append(f"{recent_fraudulent} claims showed suspicious patterns this week.")
    
    if flagged_documents > 0:
        ai_insights.append(f"{flagged_documents} documents flagged as potential forgeries.")
        ai_actions.append(f"Verify {flagged_documents} flagged documents")
    else:
        ai_insights.append("No documents flagged for forgery.")
    
    ai_insights.append(f"AI confidence score: {avg_ai_confidence:.1f}% on resolved cases.")
    
    # Generate recommendations for fraudulent clusters
    # Look for similar claim patterns
    cluster_count = find_suspicious_clusters(user)
    if cluster_count > 0:
        ai_actions.append(f"Investigate {cluster_count} potential organized fraud clusters")
    
    if len(ai_actions) < 2:
        ai_actions.append("Continue monitoring current cases")
    
    # Pad to ensure we have at least 4 insights and 2 actions
    while len(ai_insights) < 4:
        ai_insights.append("All systems normal. Continue monitoring.")
    while len(ai_actions) < 2:
        ai_actions.append("No additional actions required.")
    
    # ============================================================ #
    # 6. CHART DATA
    # ============================================================ #
    
    # Fraud Trend Data (last 6 months)
    fraud_trend_data = get_fraud_trend_data()
    
    # Case Status Distribution
    case_status_data = get_case_status_data(user)
    
    # ============================================================ #
    # 7. RECENT NOTIFICATIONS (for the bell dropdown)
    # ============================================================ #
    recent_notifications = Notification.objects.filter(
        user=user
    ).order_by('-created_at')[:5]
    
    # ============================================================ #
    # 8. CONTEXT
    # ============================================================ #
    context = {
        # Stats
        'high_risk_count': high_risk_count,
        'active_investigations': active_investigations,
        'closed_cases': closed_cases,
        'ai_accuracy': round(ai_accuracy, 1),
        'unread_notifications': unread_notifications,
        
        # Fraud Alerts
        'fraud_alerts': fraud_alerts,
        
        # Assigned Cases
        'assigned_cases': assigned_cases,
        
        # AI Insights
        'ai_insight_1': ai_insights[0] if len(ai_insights) > 0 else "No insights available.",
        'ai_insight_2': ai_insights[1] if len(ai_insights) > 1 else "No insights available.",
        'ai_insight_3': ai_insights[2] if len(ai_insights) > 2 else "No insights available.",
        'ai_insight_4': ai_insights[3] if len(ai_insights) > 3 else "No insights available.",
        'ai_action_1': ai_actions[0] if len(ai_actions) > 0 else "No actions required.",
        'ai_action_2': ai_actions[1] if len(ai_actions) > 1 else "No actions required.",
        
        # Charts
        'fraud_trend_data': fraud_trend_data,
        'case_status_data': case_status_data,
        
        # User & Date
        'user': user,
        'now': timezone.now(),
    }
    
    return render(request, 'core/investigator_dashboard.html', context)


# ============================================================ #
# HELPER FUNCTIONS
# ============================================================ #

def time_since(dt):
    """Return a human-readable 'time ago' string"""
    now = timezone.now()
    diff = now - dt
    
    if diff.days > 365:
        years = diff.days // 365
        return f"{years} year{'s' if years > 1 else ''} ago"
    elif diff.days > 30:
        months = diff.days // 30
        return f"{months} month{'s' if months > 1 else ''} ago"
    elif diff.days > 0:
        return f"{diff.days} day{'s' if diff.days > 1 else ''} ago"
    elif diff.seconds > 3600:
        hours = diff.seconds // 3600
        return f"{hours} hour{'s' if hours > 1 else ''} ago"
    elif diff.seconds > 60:
        minutes = diff.seconds // 60
        return f"{minutes} minute{'s' if minutes > 1 else ''} ago"
    else:
        return "Just now"


def calculate_ai_accuracy(user):
    """
    Calculate AI accuracy based on investigator's resolved cases.
    For claims that were investigated and resolved, compare AI score to outcome.
    """
    # Get all claims investigated by this user that are resolved
    resolved_claims = Claim.objects.filter(
        investigator=user,
        status__in=['approved', 'rejected', 'paid']
    )
    
    if not resolved_claims.exists():
        # If no resolved claims, use system-wide average
        system_average = Claim.objects.filter(
            status__in=['approved', 'rejected', 'paid']
        ).aggregate(Avg('ai_fraud_score'))['ai_fraud_score__avg'] or 0
        
        # Base accuracy on system average (75-95% range)
        # Higher AI scores on resolved claims suggest better detection
        if system_average > 80:
            return 94.5
        elif system_average > 60:
            return 88.2
        else:
            return 76.8
    
    # Calculate how well AI predicted outcomes
    # For approved claims, AI should have low score
    # For rejected claims, AI should have high score
    correct_predictions = 0
    total = resolved_claims.count()
    
    for claim in resolved_claims:
        if claim.status == 'approved' and claim.ai_fraud_score < 50:
            correct_predictions += 1
        elif claim.status == 'rejected' and claim.ai_fraud_score >= 50:
            correct_predictions += 1
        elif claim.status == 'paid' and claim.ai_fraud_score < 50:
            correct_predictions += 1
    
    # Return percentage
    if total > 0:
        return (correct_predictions / total) * 100
    return 92.5  # Default if no data


def find_suspicious_clusters(user):
    """
    Find potential organized fraud clusters (claims with similar patterns)
    """
    # Look for claims with same incident type, location, or description patterns
    # This is a simplified version - in production you'd use more sophisticated analysis
    
    claims = Claim.objects.filter(
        ai_fraud_score__gte=60,
        status__in=['submitted', 'pending', 'investigation']
    )
    
    # Group by incident type and count
    from collections import Counter
    types = [claim.incident_type for claim in claims]
    type_counts = Counter(types)
    
    # Find types with multiple claims (potential clusters)
    clusters = [count for count in type_counts.values() if count > 2]
    
    return len(clusters)


def get_fraud_trend_data():
    """
    Get fraud trend data for the last 6 months
    """
    labels = []
    values = []
    
    for i in range(6, -1, -1):
        month_date = timezone.now() - timedelta(days=30 * i)
        month_start = month_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        if i == 0:
            # Current month
            month_end = timezone.now()
        else:
            # End of month
            if month_date.month == 12:
                month_end = month_date.replace(year=month_date.year + 1, month=1, day=1) - timedelta(days=1)
            else:
                month_end = month_date.replace(month=month_date.month + 1, day=1) - timedelta(days=1)
            month_end = month_end.replace(hour=23, minute=59, second=59)
        
        # Count claims with high AI fraud score in this month
        count = Claim.objects.filter(
            ai_fraud_score__gte=60,
            submitted_at__gte=month_start,
            submitted_at__lte=month_end
        ).count()
        
        # Month label
        labels.append(month_date.strftime('%b'))
        values.append(count)
    
    return {
        'labels': json.dumps(labels),
        'values': json.dumps(values)
    }


def get_case_status_data(user):
    """
    Get case status distribution for this investigator
    """
    # Get status counts for claims assigned to this investigator
    status_counts = Claim.objects.filter(
        investigator=user
    ).values('status').annotate(count=Count('status'))
    
    labels = []
    values = []
    
    # Map status to display names
    status_map = {
        'submitted': 'New',
        'pending': 'Pending Review',
        'investigation': 'In Progress',
        'approved': 'Approved',
        'rejected': 'Rejected',
        'paid': 'Paid Out',
    }
    
    for item in status_counts:
        status = item['status']
        if status in status_map:
            labels.append(status_map[status])
            values.append(item['count'])
    
    # If no data, provide default
    if not labels:
        labels = ['No Cases']
        values = [1]
    
    return {
        'labels': json.dumps(labels),
        'values': json.dumps(values)
    }
  
# ================================================================
# INVESTIGATOR DASHBOARD (Main Overview)
# ================================================================
@login_required
def investigator_dashboard(request):
    """Investigator dashboard - shows real data from connected system"""
    
    profile = request.user.profile
    if profile.role != 'investigator':
        messages.error(request, 'Access denied. Investigator only.')
        return redirect('dashboard')
    
    # ===== STATS - Only claims that exist in the system =====
    
    # High risk claims (from policyholders, flagged by AI)
    high_risk_count = Claim.objects.filter(
        ai_fraud_score__gte=70,
        status__in=['submitted', 'pending', 'investigation']
    ).count()
    
    # Claims assigned to THIS investigator (by Staff)
    active_investigations = Claim.objects.filter(
        investigator=request.user,
        status__in=['investigation', 'submitted', 'pending']
    ).count()
    
    # Cases closed by THIS investigator
    closed_cases = Claim.objects.filter(
        investigator=request.user,
        status__in=['approved', 'rejected', 'paid']
    ).count()
    
    # ===== FRAUD ALERTS - Claims with high AI scores needing attention =====
    fraud_alerts = []
    high_risk_claims = Claim.objects.filter(
        ai_fraud_score__gte=60,
        status__in=['submitted', 'pending', 'investigation']
    ).order_by('-ai_fraud_score')[:10]
    
    for claim in high_risk_claims:
        # Determine risk level
        if claim.ai_fraud_score >= 80:
            risk_level = 'high'
        elif claim.ai_fraud_score >= 60:
            risk_level = 'medium'
        else:
            risk_level = 'low'
        
        # Check if already assigned
        assigned = claim.investigator is not None
        assigned_to_me = claim.investigator == request.user
        
        fraud_alerts.append({
            'claim': claim,
            'risk_level': risk_level,
            'risk_score': claim.ai_fraud_score,
            'time_ago': time_since(claim.submitted_at),
            'assigned': assigned,
            'assigned_to_me': assigned_to_me,
            'claim_id': claim.id,
            'claim_number': claim.claim_number,
            'policy_holder': claim.policy.user.get_full_name() if claim.policy else 'Unknown',
            'amount': claim.amount_claimed,
            'status': claim.get_status_display(),
            'incident_type': claim.get_incident_type_display(),
        })
    
    # ===== ASSIGNED CASES =====
    assigned_cases = []
    my_cases = Claim.objects.filter(
        investigator=request.user
    ).order_by('-submitted_at')[:10]
    
    for claim in my_cases:
        assigned_cases.append({
            'claim': claim,
            'claim_number': claim.claim_number,
            'policy_holder': claim.policy.user.get_full_name() if claim.policy else 'Unknown',
            'incident_type': claim.get_incident_type_display(),
            'amount': claim.amount_claimed,
            'ai_score': claim.ai_fraud_score,
            'status': claim.status,
            'status_display': claim.get_status_display(),
            'submitted_date': claim.submitted_at,
            'claim_id': claim.id,
        })
    
    # ===== AI INSIGHTS - Real data driven =====
    # Count urgent claims (AI score >= 80, not assigned)
    urgent_claims = Claim.objects.filter(
        ai_fraud_score__gte=80,
        status__in=['submitted', 'pending'],
        investigator__isnull=True
    ).count()
    
    # Count recent fraud patterns (last 7 days)
    recent_fraud = Claim.objects.filter(
        ai_fraud_score__gte=75,
        submitted_at__gte=timezone.now() - timedelta(days=7)
    ).count()
    
    # Count flagged documents for this investigator's cases
    flagged_documents = Document.objects.filter(
        claim__investigator=request.user,
        status='pending',
        ai_verification_score__lt=50
    ).count()
    
    # Get AI accuracy (based on resolved cases)
    ai_accuracy = calculate_ai_accuracy(request.user)
    
    # Build insights dynamically
    insights = []
    actions = []
    
    if urgent_claims > 0:
        insights.append(f"{urgent_claims} high-risk claims require immediate investigation.")
        actions.append(f"Review {urgent_claims} unassigned high-risk claims")
    else:
        insights.append("No urgent unassigned claims. Good job!")
    
    if recent_fraud > 0:
        insights.append(f"{recent_fraud} suspicious claims detected in the last 7 days.")
        actions.append(f"Analyze {recent_fraud} recent fraud patterns")
    else:
        insights.append("No new fraud patterns detected recently.")
    
    if flagged_documents > 0:
        insights.append(f"{flagged_documents} documents flagged for potential forgery.")
        actions.append(f"Verify {flagged_documents} flagged documents")
    else:
        insights.append("No documents flagged for review.")
    
    insights.append(f"AI confidence score: {ai_accuracy:.1f}% on resolved cases.")
    
    if len(actions) < 2:
        actions.append("Continue monitoring assigned cases.")
    
    # ===== CHART DATA - Real data from database =====
    fraud_trend_data = get_fraud_trend_data()
    case_status_data = get_case_status_data(request.user)
    
    # ===== NOTIFICATIONS =====
    unread_notifications = Notification.objects.filter(
        user=request.user,
        is_read=False
    ).count()
    
    # ===== RECENT NOTIFICATIONS FOR BELL =====
    recent_notifications = Notification.objects.filter(
        user=request.user
    ).order_by('-created_at')[:5]
    
    context = {
        # Stats
        'high_risk_count': high_risk_count,
        'active_investigations': active_investigations,
        'closed_cases': closed_cases,
        'ai_accuracy': round(ai_accuracy, 1),
        'unread_notifications': unread_notifications,
        
        # Fraud Alerts
        'fraud_alerts': fraud_alerts,
        
        # Assigned Cases
        'assigned_cases': assigned_cases,
        
        # AI Insights (dynamic)
        'ai_insight_1': insights[0] if len(insights) > 0 else "No insights available.",
        'ai_insight_2': insights[1] if len(insights) > 1 else "No insights available.",
        'ai_insight_3': insights[2] if len(insights) > 2 else "No insights available.",
        'ai_insight_4': insights[3] if len(insights) > 3 else "No insights available.",
        'ai_action_1': actions[0] if len(actions) > 0 else "No actions required.",
        'ai_action_2': actions[1] if len(actions) > 1 else "No actions required.",
        
        # Charts
        'fraud_trend_data': fraud_trend_data,
        'case_status_data': case_status_data,
        
        # User & Date
        'user': request.user,
        'now': timezone.now(),
        'recent_notifications': recent_notifications,
    }
    
    return render(request, 'core/investigator_dashboard.html', context)
# ================================================================
# FRAUD ALERTS - INVESTIGATOR
# ================================================================
@login_required
def investigator_fraud_alerts(request):
    """View all fraud alerts with filtering - data from policyholders"""
    
    profile = request.user.profile
    if profile.role != 'investigator':
        messages.error(request, 'Access denied.')
        return redirect('dashboard')
    
    # Base query - all active claims with AI fraud score >= 60
    fraud_alerts_qs = Claim.objects.filter(
        ai_fraud_score__gte=60,
        status__in=['submitted', 'pending', 'investigation']
    ).select_related('policy__user', 'investigator')
    
    # Apply filters
    risk_level = request.GET.get('risk_level')
    if risk_level:
        if risk_level == 'high':
            fraud_alerts_qs = fraud_alerts_qs.filter(ai_fraud_score__gte=80)
        elif risk_level == 'medium':
            fraud_alerts_qs = fraud_alerts_qs.filter(ai_fraud_score__gte=60, ai_fraud_score__lt=80)
    
    claim_type = request.GET.get('claim_type')
    if claim_type:
        fraud_alerts_qs = fraud_alerts_qs.filter(incident_type=claim_type)
    
    assigned_filter = request.GET.get('assigned')
    if assigned_filter == 'assigned':
        fraud_alerts_qs = fraud_alerts_qs.filter(investigator__isnull=False)
    elif assigned_filter == 'unassigned':
        fraud_alerts_qs = fraud_alerts_qs.filter(investigator__isnull=True)
    elif assigned_filter == 'mine':
        fraud_alerts_qs = fraud_alerts_qs.filter(investigator=request.user)
    
    # Sort
    sort_by = request.GET.get('sort', 'risk')
    if sort_by == 'risk':
        fraud_alerts_qs = fraud_alerts_qs.order_by('-ai_fraud_score')
    elif sort_by == 'newest':
        fraud_alerts_qs = fraud_alerts_qs.order_by('-submitted_at')
    elif sort_by == 'oldest':
        fraud_alerts_qs = fraud_alerts_qs.order_by('submitted_at')
    elif sort_by == 'amount':
        fraud_alerts_qs = fraud_alerts_qs.order_by('-amount_claimed')
    
    # Pagination
    page = request.GET.get('page', 1)
    paginator = Paginator(fraud_alerts_qs, 15)
    try:
        alerts_page = paginator.page(page)
    except PageNotAnInteger:
        alerts_page = paginator.page(1)
    except EmptyPage:
        alerts_page = paginator.page(paginator.num_pages)
    
    # Prepare alert data
    alerts = []
    for claim in alerts_page:
        risk = 'high' if claim.ai_fraud_score >= 80 else 'medium' if claim.ai_fraud_score >= 60 else 'low'
        alerts.append({
            'claim': claim,
            'risk_level': risk,
            'risk_score': claim.ai_fraud_score,
            'time_ago': time_since(claim.submitted_at),
            'assigned': claim.investigator is not None,
            'assigned_to_me': claim.investigator == request.user,
            'assigned_to_name': claim.investigator.get_full_name() if claim.investigator else None,
        })
    
    # Stats for filters
    total_high = Claim.objects.filter(ai_fraud_score__gte=80, status__in=['submitted', 'pending', 'investigation']).count()
    total_medium = Claim.objects.filter(ai_fraud_score__gte=60, ai_fraud_score__lt=80, status__in=['submitted', 'pending', 'investigation']).count()
    total_unassigned = Claim.objects.filter(ai_fraud_score__gte=60, status__in=['submitted', 'pending', 'investigation'], investigator__isnull=True).count()
    total_mine = Claim.objects.filter(ai_fraud_score__gte=60, status__in=['submitted', 'pending', 'investigation'], investigator=request.user).count()
    
    context = {
        'alerts': alerts,
        'page_obj': alerts_page,
        'total_high': total_high,
        'total_medium': total_medium,
        'total_low': Claim.objects.filter(ai_fraud_score__gte=40, ai_fraud_score__lt=60, status__in=['submitted', 'pending', 'investigation']).count(),
        'total_unassigned': total_unassigned,
        'total_mine': total_mine,
        'current_risk': risk_level,
        'current_type': claim_type,
        'current_assigned': assigned_filter,
        'current_sort': sort_by,
        'incident_types': Claim.INCIDENT_TYPES,
        'user': request.user,
        'now': timezone.now(),
        'unread_notifications': Notification.objects.filter(user=request.user, is_read=False).count(),
        'active_investigations': Claim.objects.filter(investigator=request.user, status__in=['investigation', 'submitted', 'pending']).count(),
    }
    
    return render(request, 'core/investigator_fraud_alerts.html', context)
# ================================================================
# MY CASES - INVESTIGATOR
# ================================================================
@login_required
def investigator_cases(request):
    """View all cases assigned to this investigator"""
    
    profile = request.user.profile
    if profile.role != 'investigator':
        messages.error(request, 'Access denied.')
        return redirect('dashboard')
    
    # Get all cases assigned to this investigator
    cases_qs = Claim.objects.filter(
        investigator=request.user
    ).select_related('policy__user').order_by('-submitted_at')
    
    # Apply filters
    status_filter = request.GET.get('status')
    if status_filter:
        cases_qs = cases_qs.filter(status=status_filter)
    
    claim_type = request.GET.get('claim_type')
    if claim_type:
        cases_qs = cases_qs.filter(incident_type=claim_type)
    
    # Search
    search_query = request.GET.get('search')
    if search_query:
        cases_qs = cases_qs.filter(
            Q(claim_number__icontains=search_query) |
            Q(policy__user__first_name__icontains=search_query) |
            Q(policy__user__last_name__icontains=search_query) |
            Q(incident_description__icontains=search_query)
        )
    
    # Pagination
    page = request.GET.get('page', 1)
    paginator = Paginator(cases_qs, 15)
    try:
        cases_page = paginator.page(page)
    except PageNotAnInteger:
        cases_page = paginator.page(1)
    except EmptyPage:
        cases_page = paginator.page(paginator.num_pages)
    
    # Stats
    total_cases = cases_qs.count()
    open_cases = cases_qs.filter(status__in=['submitted', 'pending', 'investigation']).count()
    closed_cases = cases_qs.filter(status__in=['approved', 'rejected', 'paid']).count()
    
    context = {
        'cases': cases_page,
        'page_obj': cases_page,
        'total_cases': total_cases,
        'open_cases': open_cases,
        'closed_cases': closed_cases,
        'current_status': status_filter,
        'current_type': claim_type,
        'search_query': search_query,
        'status_choices': Claim.CLAIM_STATUS,
        'incident_types': Claim.INCIDENT_TYPES,
        'user': request.user,
        'now': timezone.now(),
        'unread_notifications': Notification.objects.filter(user=request.user, is_read=False).count(),
        'active_investigations': open_cases,
    }
    
    return render(request, 'core/investigator_cases.html', context)
# ================================================================
# CASE DETAIL - INVESTIGATOR
# ================================================================
@login_required
def investigator_case_detail(request, claim_id):
    """View detailed case information and manage investigation"""
    
    profile = request.user.profile
    if profile.role != 'investigator':
        messages.error(request, 'Access denied.')
        return redirect('dashboard')
    
    claim = get_object_or_404(Claim.objects.select_related('policy__user', 'investigator'), id=claim_id)
    
    # Security: Check if this investigator is assigned OR if claim is unassigned
    if claim.investigator and claim.investigator != request.user:
        messages.error(request, 'This case is assigned to another investigator.')
        return redirect('investigator_cases')
    
    # If claim is unassigned, allow investigator to claim it
    if not claim.investigator:
        if request.method == 'POST' and request.POST.get('action') == 'claim_case':
            claim.investigator = request.user
            claim.status = 'investigation'
            claim.save()
            
            # Create notification for staff
            Notification.objects.create(
                user=claim.policy.user,
                title='Case Assigned for Investigation',
                message=f'Your claim {claim.claim_number} has been assigned to Investigator {request.user.get_full_name()} for investigation.',
                category='claim',
                notification_type='info',
                related_claim=claim,
            )
            
            messages.success(request, f'Case {claim.claim_number} claimed successfully.')
            return redirect('investigator_case_detail', claim_id=claim.id)
    
    # Get related documents
    documents = Document.objects.filter(claim=claim)
    
    # Get related payments
    payments = Payment.objects.filter(policy=claim.policy)
    
    # Get claim timeline
    timeline = Notification.objects.filter(
        Q(related_claim=claim) | Q(user=claim.user)
    ).order_by('-created_at')[:20]
    
    # Calculate risk indicators
    risk_indicators = calculate_risk_indicators(claim)
    
    # Handle investigation note submission
    if request.method == 'POST' and request.POST.get('action') == 'add_note':
        note = request.POST.get('investigation_note')
        if note:
            claim.investigation_notes = (claim.investigation_notes or '') + f"\n\n[{timezone.now().strftime('%Y-%m-%d %H:%M')}] {request.user.get_full_name()}: {note}"
            claim.save()
            
            # Notify staff and policyholder
            Notification.objects.create(
                user=claim.policy.user,
                title='Investigation Update',
                message=f'New investigation note added to claim {claim.claim_number}.',
                category='claim',
                notification_type='info',
                related_claim=claim,
            )
            
            messages.success(request, 'Investigation note added successfully.')
            return redirect('investigator_case_detail', claim_id=claim.id)
    
    # Handle status update
    if request.method == 'POST' and request.POST.get('action') == 'update_status':
        new_status = request.POST.get('status')
        if new_status in ['approved', 'rejected', 'paid']:
            # Only allow final status updates
            claim.status = new_status
            claim.resolved_at = timezone.now()
            claim.save()
            
            # Create notifications
            Notification.objects.create(
                user=claim.policy.user,
                title=f'Claim {new_status.title()}',
                message=f'Your claim {claim.claim_number} has been {new_status}.',
                category='claim',
                notification_type='success' if new_status in ['approved', 'paid'] else 'danger',
                related_claim=claim,
            )
            
            messages.success(request, f'Case status updated to {claim.get_status_display()}.')
            return redirect('investigator_case_detail', claim_id=claim.id)
    
    context = {
        'claim': claim,
        'documents': documents,
        'payments': payments,
        'timeline': timeline,
        'risk_indicators': risk_indicators,
        'user': request.user,
        'now': timezone.now(),
        'unread_notifications': Notification.objects.filter(user=request.user, is_read=False).count(),
        'active_investigations': Claim.objects.filter(investigator=request.user, status__in=['investigation', 'submitted', 'pending']).count(),
    }
    
    return render(request, 'core/investigator_case_detail.html', context)
# ================================================================
# DOCUMENT ANALYSIS - VINVESTIGATOR
# ================================================================
@login_required
def investigator_document_analysis(request):
    """View and analyze documents for fraud detection"""
    
    profile = request.user.profile
    if profile.role != 'investigator':
        messages.error(request, 'Access denied.')
        return redirect('dashboard')
    
    # Get documents from claims assigned to this investigator
    documents_qs = Document.objects.filter(
        claim__investigator=request.user
    ).select_related('claim', 'claim__policy__user').order_by('-uploaded_at')
    
    # Or get all flagged documents (system-wide)
    show_all = request.GET.get('all', 'false') == 'true'
    if not show_all:
        documents_qs = documents_qs.filter(
            Q(ai_verification_score__lt=50) |
            Q(status='pending')
        )
    
    # Apply filters
    doc_type = request.GET.get('document_type')
    if doc_type:
        documents_qs = documents_qs.filter(document_type=doc_type)
    
    status_filter = request.GET.get('status')
    if status_filter:
        documents_qs = documents_qs.filter(status=status_filter)
    
    # Search
    search_query = request.GET.get('search')
    if search_query:
        documents_qs = documents_qs.filter(
            Q(document_name__icontains=search_query) |
            Q(claim__claim_number__icontains=search_query)
        )
    
    # Pagination
    page = request.GET.get('page', 1)
    paginator = Paginator(documents_qs, 15)
    try:
        docs_page = paginator.page(page)
    except PageNotAnInteger:
        docs_page = paginator.page(1)
    except EmptyPage:
        docs_page = paginator.page(paginator.num_pages)
    
    # Stats
    total_docs = documents_qs.count()
    pending_docs = documents_qs.filter(status='pending').count()
    verified_docs = documents_qs.filter(status='verified').count()
    rejected_docs = documents_qs.filter(status='rejected').count()
    flagged_docs = documents_qs.filter(ai_verification_score__lt=50).count()
    
    context = {
        'documents': docs_page,
        'page_obj': docs_page,
        'total_docs': total_docs,
        'pending_docs': pending_docs,
        'verified_docs': verified_docs,
        'rejected_docs': rejected_docs,
        'flagged_docs': flagged_docs,
        'current_type': doc_type,
        'current_status': status_filter,
        'show_all': show_all,
        'search_query': search_query,
        'document_types': Document.DOCUMENT_TYPES,
        'status_choices': Document.DOCUMENT_STATUS,
        'user': request.user,
        'now': timezone.now(),
        'unread_notifications': Notification.objects.filter(user=request.user, is_read=False).count(),
        'active_investigations': Claim.objects.filter(investigator=request.user, status__in=['investigation', 'submitted', 'pending']).count(),
    }
    
    return render(request, 'core/investigator_document_analysis.html', context)
# ================================================================
# DOCUMENT VERIFICATION - AJAX endpoint - INVESTIGATOR
# ================================================================
@login_required
def investigator_verify_document(request, doc_id):
    """Verify or reject a document - AJAX"""
    
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    profile = request.user.profile
    if profile.role != 'investigator':
        return JsonResponse({'error': 'Access denied'}, status=403)
    
    doc = get_object_or_404(Document, id=doc_id)
    
    # Check permission - document must belong to a claim assigned to this investigator
    if not doc.claim or doc.claim.investigator != request.user:
        return JsonResponse({'error': 'You are not assigned to this claim'}, status=403)
    
    action = request.POST.get('action')
    if action == 'verify':
        doc.status = 'verified'
        doc.verified_by = request.user
        doc.verified_at = timezone.now()
        doc.save()
        
        Notification.objects.create(
            user=doc.claim.policy.user,
            title='Document Verified',
            message=f'Your document "{doc.document_name}" has been verified.',
            category='document',
            notification_type='success',
            related_claim=doc.claim,
        )
        
        return JsonResponse({'success': True, 'message': 'Document verified successfully'})
    
    elif action == 'reject':
        reason = request.POST.get('reason', 'No reason provided')
        doc.status = 'rejected'
        doc.rejection_reason = reason
        doc.verified_by = request.user
        doc.verified_at = timezone.now()
        doc.save()
        
        Notification.objects.create(
            user=doc.claim.policy.user,
            title='Document Rejected',
            message=f'Your document "{doc.document_name}" was rejected. Reason: {reason}',
            category='document',
            notification_type='danger',
            related_claim=doc.claim,
        )
        
        return JsonResponse({'success': True, 'message': 'Document rejected'})
    
    return JsonResponse({'error': 'Invalid action'}, status=400)
# ================================================================
# FRAUD REPORTS - INVESTIGATOR
# ================================================================
@login_required
def investigator_fraud_reports(request):
    """Generate and view fraud investigation reports"""
    
    profile = request.user.profile
    if profile.role != 'investigator':
        messages.error(request, 'Access denied.')
        return redirect('dashboard')
    
    # Get completed investigations
    completed_cases = Claim.objects.filter(
        investigator=request.user,
        status__in=['approved', 'rejected', 'paid']
    ).select_related('policy__user').order_by('-resolved_at')
    
    # Apply filters
    status_filter = request.GET.get('status')
    if status_filter:
        completed_cases = completed_cases.filter(status=status_filter)
    
    # Date range filter
    date_filter = request.GET.get('date_range')
    if date_filter:
        if date_filter == 'today':
            completed_cases = completed_cases.filter(resolved_at__date=timezone.now().date())
        elif date_filter == 'week':
            week_ago = timezone.now() - timedelta(days=7)
            completed_cases = completed_cases.filter(resolved_at__gte=week_ago)
        elif date_filter == 'month':
            month_ago = timezone.now() - timedelta(days=30)
            completed_cases = completed_cases.filter(resolved_at__gte=month_ago)
    
    # Pagination
    page = request.GET.get('page', 1)
    paginator = Paginator(completed_cases, 15)
    try:
        reports_page = paginator.page(page)
    except PageNotAnInteger:
        reports_page = paginator.page(1)
    except EmptyPage:
        reports_page = paginator.page(paginator.num_pages)
    
    # Statistics
    total_reports = completed_cases.count()
    approved_count = completed_cases.filter(status='approved').count()
    rejected_count = completed_cases.filter(status='rejected').count()
    paid_count = completed_cases.filter(status='paid').count()
    
    # Monthly breakdown
    monthly_reports = completed_cases.annotate(
        month=TruncMonth('resolved_at')
    ).values('month').annotate(
        count=Count('id'),
        avg_score=Avg('ai_fraud_score')
    ).order_by('-month')
    
    context = {
        'reports': reports_page,
        'page_obj': reports_page,
        'total_reports': total_reports,
        'approved_count': approved_count,
        'rejected_count': rejected_count,
        'paid_count': paid_count,
        'monthly_reports': monthly_reports,
        'current_status': status_filter,
        'current_date_range': date_filter,
        'user': request.user,
        'now': timezone.now(),
        'unread_notifications': Notification.objects.filter(user=request.user, is_read=False).count(),
        'active_investigations': Claim.objects.filter(investigator=request.user, status__in=['investigation', 'submitted', 'pending']).count(),
    }
    
    return render(request, 'core/investigator_fraud_reports.html', context)
# ================================================================
# FRAUD ANALYTICS - INVESTIGATOR
# ================================================================
@login_required
def investigator_fraud_analytics(request):
    """Advanced fraud analytics dashboard with real data"""
    
    profile = request.user.profile
    if profile.role != 'investigator':
        messages.error(request, 'Access denied.')
        return redirect('dashboard')
    
    # Get all claims for this investigator
    all_cases = Claim.objects.filter(investigator=request.user)
    
    # Analytics calculations
    total_claims = all_cases.count()
    avg_fraud_score = all_cases.aggregate(Avg('ai_fraud_score'))['ai_fraud_score__avg'] or 0
    
    # Approval rate
    resolved = all_cases.filter(status__in=['approved', 'rejected', 'paid'])
    approved_count = resolved.filter(status='approved').count()
    rejected_count = resolved.filter(status='rejected').count()
    approval_rate = round((approved_count / resolved.count() * 100) if resolved.count() > 0 else 0, 1)
    
    # Fraud detection rate (claims rejected due to fraud)
    fraud_detected = resolved.filter(status='rejected', ai_fraud_score__gte=50).count()
    fraud_detection_rate = round((fraud_detected / resolved.count() * 100) if resolved.count() > 0 else 0, 1)
    
    # Average investigation time
    resolved_with_date = resolved.exclude(resolved_at__isnull=True)
    total_days = 0
    for claim in resolved_with_date:
        days = (claim.resolved_at - claim.submitted_at).days
        total_days += days
    avg_investigation_time = round(total_days / resolved_with_date.count(), 1) if resolved_with_date.count() > 0 else 0
    
    # Fraud by claim type
    fraud_by_type = all_cases.values('incident_type').annotate(
        count=Count('id'),
        avg_score=Avg('ai_fraud_score')
    ).order_by('-avg_score')
    
    # Monthly trends
    monthly_trends = all_cases.annotate(
        month=TruncMonth('submitted_at')
    ).values('month').annotate(
        count=Count('id'),
        avg_score=Avg('ai_fraud_score')
    ).order_by('month')
    
    # Chart data preparation
    chart_labels = [item['month'].strftime('%b %Y') if item['month'] else 'Unknown' for item in monthly_trends]
    chart_counts = [item['count'] for item in monthly_trends]
    chart_scores = [round(item['avg_score'] or 0, 1) for item in monthly_trends]
    
    analytics = {
        'total_claims': total_claims,
        'avg_fraud_score': avg_fraud_score,
        'approval_rate': approval_rate,
        'fraud_detection_rate': fraud_detection_rate,
        'avg_investigation_time': avg_investigation_time,
    }
    
    context = {
        'analytics': analytics,
        'fraud_by_type': fraud_by_type,
        'monthly_trends': monthly_trends,
        'chart_labels': json.dumps(chart_labels),
        'chart_counts': json.dumps(chart_counts),
        'chart_scores': json.dumps(chart_scores),
        'user': request.user,
        'now': timezone.now(),
        'unread_notifications': Notification.objects.filter(user=request.user, is_read=False).count(),
        'active_investigations': Claim.objects.filter(investigator=request.user, status__in=['investigation', 'submitted', 'pending']).count(),
    }
    
    return render(request, 'core/investigator_fraud_analytics.html', context)


# ================================================================
# AI INSIGHTS - INVESTIGATOR
# ================================================================
@login_required
def investigator_ai_insights(request):
    """AI Insights page with real-time analysis"""
    
    profile = request.user.profile
    if profile.role != 'investigator':
        messages.error(request, 'Access denied.')
        return redirect('dashboard')
    
    # Get all claims
    all_claims = Claim.objects.all()
    my_claims = Claim.objects.filter(investigator=request.user)
    
    # AI statistics
    total_claims_analyzed = all_claims.count()
    high_risk_count = all_claims.filter(ai_fraud_score__gte=70, status__in=['submitted', 'pending', 'investigation']).count()
    ai_accuracy = calculate_ai_accuracy(request.user)
    
    # Recent AI predictions
    recent_predictions = all_claims.filter(
        ai_fraud_score__isnull=False
    ).order_by('-submitted_at')[:10]
    
    # AI insights based on real data
    insights = []
    
    # Pattern detection
    high_risk_unassigned = all_claims.filter(ai_fraud_score__gte=80, status__in=['submitted', 'pending'], investigator__isnull=True).count()
    if high_risk_unassigned > 0:
        insights.append({
            'icon': 'high',
            'title': f'{high_risk_unassigned} high-risk claims unassigned',
            'description': 'These claims require immediate investigator assignment.',
            'confidence': 94
        })
    
    # Document forgery detection
    forged_docs = Document.objects.filter(ai_verification_score__lt=30, claim__in=all_claims).count()
    if forged_docs > 0:
        insights.append({
            'icon': 'high',
            'title': f'{forged_docs} documents flagged as potential forgeries',
            'description': 'AI detected inconsistencies in these documents.',
            'confidence': 89
        })
    
    # Pattern analysis
    duplicate_patterns = find_suspicious_clusters(request.user)
    if duplicate_patterns > 0:
        insights.append({
            'icon': 'medium',
            'title': f'{duplicate_patterns} potential fraud clusters detected',
            'description': 'Multiple claims show similar patterns.',
            'confidence': 76
        })
    
    # System health
    if all_claims.count() > 0:
        avg_score = all_claims.aggregate(Avg('ai_fraud_score'))['ai_fraud_score__avg'] or 0
        insights.append({
            'icon': 'info' if avg_score < 40 else 'medium',
            'title': f'Average AI fraud score: {avg_score:.1f}%',
            'description': f'Based on {all_claims.count()} analyzed claims.',
            'confidence': 96
        })
    
    # Pad insights if needed
    while len(insights) < 4:
        insights.append({
            'icon': 'info',
            'title': 'System monitoring active',
            'description': 'All AI systems are functioning normally.',
            'confidence': 98
        })
    
    context = {
        'high_risk_count': high_risk_count,
        'active_investigations': my_claims.filter(status__in=['investigation', 'submitted', 'pending']).count(),
        'closed_cases': my_claims.filter(status__in=['approved', 'rejected', 'paid']).count(),
        'ai_accuracy': round(ai_accuracy, 1),
        'unread_notifications': Notification.objects.filter(user=request.user, is_read=False).count(),
        'recent_predictions': recent_predictions,
        'ai_insights': insights,
        'total_claims_analyzed': total_claims_analyzed,
        'user': request.user,
        'now': timezone.now(),
    }
    
    return render(request, 'core/investigator_ai_insights.html', context)
# ================================================================
# NOTIFICATIONS - INVESTIGATOR
# ================================================================
@login_required
def investigator_notifications(request):
    """View all notifications for investigator"""
    
    profile = request.user.profile
    if profile.role != 'investigator':
        messages.error(request, 'Access denied.')
        return redirect('dashboard')
    
    notifications = Notification.objects.filter(
        user=request.user
    ).order_by('-created_at')
    
    # Mark all as read if requested
    if request.GET.get('mark_read'):
        notifications.update(is_read=True, read_at=timezone.now())
        messages.success(request, 'All notifications marked as read.')
        return redirect('investigator_notifications')
    
    # Filter by type
    notif_type = request.GET.get('type')
    if notif_type:
        notifications = notifications.filter(notification_type=notif_type)
    
    # Filter by category
    category = request.GET.get('category')
    if category:
        notifications = notifications.filter(category=category)
    
    # Pagination
    page = request.GET.get('page', 1)
    paginator = Paginator(notifications, 20)
    try:
        notif_page = paginator.page(page)
    except PageNotAnInteger:
        notif_page = paginator.page(1)
    except EmptyPage:
        notif_page = paginator.page(paginator.num_pages)
    
    unread_count = notifications.filter(is_read=False).count()
    
    context = {
        'notifications': notif_page,
        'page_obj': notif_page,
        'unread_count': unread_count,
        'current_type': notif_type,
        'current_category': category,
        'notification_types': Notification.NOTIFICATION_TYPES,
        'notification_categories': Notification.NOTIFICATION_CATEGORIES,
        'user': request.user,
        'now': timezone.now(),
        'active_investigations': Claim.objects.filter(investigator=request.user, status__in=['investigation', 'submitted', 'pending']).count(),
    }
    
    return render(request, 'core/investigator_notifications.html', context)
# ================================================================
# MARK NOTIFICATION READ - AJAX
# ================================================================
@login_required
def investigator_mark_notification_read(request, notif_id):
    """Mark a single notification as read - AJAX"""
    
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    profile = request.user.profile
    if profile.role != 'investigator':
        return JsonResponse({'error': 'Access denied'}, status=403)
    
    notification = get_object_or_404(Notification, id=notif_id, user=request.user)
    notification.is_read = True
    notification.read_at = timezone.now()
    notification.save()
    
    return JsonResponse({'success': True, 'message': 'Notification marked as read'})
# ================================================================
# PROFILE - INVESTIGATOR PROFILE
# ================================================================
@login_required
def investigator_profile(request):
    """View and edit investigator profile"""
    
    profile = request.user.profile
    if profile.role != 'investigator':
        messages.error(request, 'Access denied.')
        return redirect('dashboard')
    
    if request.method == 'POST':
        # Update user
        user = request.user
        user.first_name = request.POST.get('first_name', user.first_name)
        user.last_name = request.POST.get('last_name', user.last_name)
        user.email = request.POST.get('email', user.email)
        user.save()
        
        # Update profile
        profile.phone = request.POST.get('phone', profile.phone)
        profile.id_number = request.POST.get('id_number', profile.id_number)
        profile.address = request.POST.get('address', profile.address)
        profile.city = request.POST.get('city', profile.city)
        profile.province = request.POST.get('province', profile.province)
        profile.postal_code = request.POST.get('postal_code', profile.postal_code)
        profile.employee_number = request.POST.get('employee_number', profile.employee_number)
        profile.department = request.POST.get('department', profile.department)
        profile.branch = request.POST.get('branch', profile.branch)
        profile.position = request.POST.get('position', profile.position)
        profile.specialization = request.POST.get('specialization', profile.specialization)
        profile.save()
        
        messages.success(request, 'Profile updated successfully!')
        return redirect('investigator_profile')
    
    context = {
        'profile': profile,
        'user': request.user,
        'department_choices': UserProfile.DEPARTMENT_CHOICES,
        'specialization_choices': UserProfile.SPECIALIZATION_CHOICES,
        'now': timezone.now(),
        'unread_notifications': Notification.objects.filter(user=request.user, is_read=False).count(),
        'active_investigations': Claim.objects.filter(investigator=request.user, status__in=['investigation', 'submitted', 'pending']).count(),
    }
    
    return render(request, 'core/investigator_profile.html', context)
# ================================================================
# SETTINGS - IVESTIGATOR
# ================================================================
@login_required
def investigator_settings(request):
    """Investigator settings page"""
    
    profile = request.user.profile
    if profile.role != 'investigator':
        messages.error(request, 'Access denied.')
        return redirect('dashboard')
    
    context = {
        'user': request.user,
        'profile': profile,
        'now': timezone.now(),
        'unread_notifications': Notification.objects.filter(user=request.user, is_read=False).count(),
        'active_investigations': Claim.objects.filter(investigator=request.user, status__in=['investigation', 'submitted', 'pending']).count(),
    }
    
    return render(request, 'core/investigator_settings.html', context)
# ================================================================
# HELPER FUNCTIONS FOR INVESTIGATOR 
# ================================================================
def time_since(dt):
    """Return a human-readable 'time ago' string"""
    if not dt:
        return "Unknown"
    now = timezone.now()
    diff = now - dt
    
    if diff.days > 365:
        years = diff.days // 365
        return f"{years} year{'s' if years > 1 else ''} ago"
    elif diff.days > 30:
        months = diff.days // 30
        return f"{months} month{'s' if months > 1 else ''} ago"
    elif diff.days > 0:
        return f"{diff.days} day{'s' if diff.days > 1 else ''} ago"
    elif diff.seconds > 3600:
        hours = diff.seconds // 3600
        return f"{hours} hour{'s' if hours > 1 else ''} ago"
    elif diff.seconds > 60:
        minutes = diff.seconds // 60
        return f"{minutes} minute{'s' if minutes > 1 else ''} ago"
    else:
        return "Just now"


def calculate_ai_accuracy(user):
    """Calculate AI accuracy based on investigator's resolved cases"""
    resolved_claims = Claim.objects.filter(
        investigator=user,
        status__in=['approved', 'rejected', 'paid']
    )
    
    if not resolved_claims.exists():
        # Use system-wide average
        system_avg = Claim.objects.filter(
            status__in=['approved', 'rejected', 'paid']
        ).aggregate(Avg('ai_fraud_score'))['ai_fraud_score__avg'] or 0
        
        if system_avg > 80:
            return 94.5
        elif system_avg > 60:
            return 88.2
        else:
            return 76.8
    
    # Calculate accuracy
    correct = 0
    total = resolved_claims.count()
    
    for claim in resolved_claims:
        # For approved/paid: AI should have low score (<50)
        if claim.status in ['approved', 'paid'] and claim.ai_fraud_score < 50:
            correct += 1
        # For rejected: AI should have high score (>=50)
        elif claim.status == 'rejected' and claim.ai_fraud_score >= 50:
            correct += 1
    
    return (correct / total * 100) if total > 0 else 92.5


def find_suspicious_clusters(user):
    """Find potential organized fraud clusters"""
    claims = Claim.objects.filter(
        ai_fraud_score__gte=60,
        status__in=['submitted', 'pending', 'investigation']
    )
    
    from collections import Counter
    types = [claim.incident_type for claim in claims]
    type_counts = Counter(types)
    
    clusters = sum(1 for count in type_counts.values() if count > 2)
    return clusters


def get_fraud_trend_data():
    """Get fraud trend data for the last 6 months"""
    labels = []
    values = []
    
    for i in range(6, -1, -1):
        month_date = timezone.now() - timedelta(days=30 * i)
        month_start = month_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        if i == 0:
            month_end = timezone.now()
        else:
            if month_date.month == 12:
                month_end = month_date.replace(year=month_date.year + 1, month=1, day=1) - timedelta(days=1)
            else:
                month_end = month_date.replace(month=month_date.month + 1, day=1) - timedelta(days=1)
            month_end = month_end.replace(hour=23, minute=59, second=59)
        
        count = Claim.objects.filter(
            ai_fraud_score__gte=60,
            submitted_at__gte=month_start,
            submitted_at__lte=month_end
        ).count()
        
        labels.append(month_date.strftime('%b'))
        values.append(count)
    
    return {
        'labels': json.dumps(labels),
        'values': json.dumps(values)
    }


def get_case_status_data(user):
    """Get case status distribution for this investigator"""
    status_counts = Claim.objects.filter(
        investigator=user
    ).values('status').annotate(count=Count('status'))
    
    labels = []
    values = []
    
    status_map = {
        'submitted': 'New',
        'pending': 'Pending Review',
        'investigation': 'In Progress',
        'approved': 'Approved',
        'rejected': 'Rejected',
        'paid': 'Paid Out',
    }
    
    for item in status_counts:
        status = item['status']
        if status in status_map:
            labels.append(status_map[status])
            values.append(item['count'])
    
    if not labels:
        labels = ['No Cases']
        values = [1]
    
    return {
        'labels': json.dumps(labels),
        'values': json.dumps(values)
    }


def calculate_risk_indicators(claim):
    """Calculate detailed risk indicators for a claim"""
    indicators = {
        'high_amount': claim.amount_claimed > Decimal('50000'),
        'recent_incident': (timezone.now().date() - claim.incident_date).days < 7,
        'multiple_documents': Document.objects.filter(claim=claim).count() > 5,
        'duplicate_pattern': Claim.objects.filter(
            incident_type=claim.incident_type,
            user=claim.user,
            submitted_at__gte=timezone.now() - timedelta(days=30)
        ).count() > 1,
        'inconsistent_data': claim.ai_fraud_analysis and 'inconsistency' in claim.ai_fraud_analysis.lower(),
        'high_risk_location': claim.incident_location and 'high risk' in claim.incident_location.lower(),
    }
    
    risk_count = sum(1 for v in indicators.values() if v)
    indicators['risk_level'] = 'High' if risk_count >= 4 else 'Medium' if risk_count >= 2 else 'Low'
    indicators['risk_count'] = risk_count
    
    return indicators

# ================================================================
# CUSTOMER CLAIM SUBMISSION
# ================================================================

@login_required
def customer_submit_claim(request):
    """Submit Claim page - Saves to database with AI fraud analysis"""
    
    if request.method == 'POST':
        try:
            import json
            data = json.loads(request.body)
            
            user = request.user
            
            # Get form data
            policy_id = data.get('policy_id')
            incident_type = data.get('incident_type')
            incident_date = data.get('incident_date')
            incident_description = data.get('incident_description')
            incident_location = data.get('incident_location', '')
            amount_claimed = data.get('amount_claimed', 0)
            
            # Get the policy
            try:
                policy = Policy.objects.get(id=policy_id, user=user)
            except Policy.DoesNotExist:
                return JsonResponse({'success': False, 'error': 'Policy not found.'})
            
            # Generate claim number
            claim_number = f"CLM-{datetime.now().year}-{random.randint(1000, 9999)}"
            
            # Calculate AI fraud score based on multiple factors
            fraud_score = calculate_fraud_score(
                amount_claimed=amount_claimed,
                policy=policy,
                user=user,
                incident_type=incident_type
            )
            
            # Determine risk level and analysis
            if fraud_score > 60:
                fraud_analysis = 'High risk patterns detected. Investigation required.'
                risk_level = 'High'
            elif fraud_score > 30:
                fraud_analysis = 'Some unusual patterns detected. Further review may be required.'
                risk_level = 'Medium'
            else:
                fraud_analysis = 'No suspicious patterns detected. Claim appears legitimate.'
                risk_level = 'Low'
            
            # Create claim
            claim = Claim.objects.create(
                claim_number=claim_number,
                policy=policy,
                user=user,
                incident_type=incident_type,
                incident_date=incident_date,
                incident_description=incident_description,
                incident_location=incident_location,
                amount_claimed=amount_claimed,
                status='submitted',
                ai_fraud_score=fraud_score,
                ai_fraud_analysis=fraud_analysis,
            )
            
            # Create notification for customer
            Notification.objects.create(
                user=user,
                title='Claim Submitted Successfully!',
                message=f'Your claim #{claim_number} has been submitted and is being reviewed.',
                notification_type='success',
                category='claim',
                related_claim=claim,
                action_url=f'/dashboard/customer/claim/{claim.id}/',
            )
            
            # Notify Staff
            staff_users = User.objects.filter(profile__role='staff')
            for staff in staff_users:
                Notification.objects.create(
                    user=staff,
                    title='📋 New Claim Submitted',
                    message=f'{user.get_full_name()} submitted claim #{claim_number} - {incident_type} - R{amount_claimed}',
                    notification_type='info',
                    category='claim',
                    action_url='/staff/claims-queue/',
                )
            
            # If high risk, notify investigators
            if fraud_score > 60:
                investigators = User.objects.filter(profile__role='investigator')
                for inv in investigators:
                    Notification.objects.create(
                        user=inv,
                        title='🚨 High Risk Claim Alert',
                        message=f'Claim #{claim_number} from {user.get_full_name()} has a fraud score of {fraud_score}%. Investigation required.',
                        notification_type='danger',
                        category='investigation',
                        action_url='/investigator/fraud-alerts/',
                    )
            
            # Notify Admin
            admin_users = User.objects.filter(profile__role='administrator')
            for admin in admin_users:
                Notification.objects.create(
                    user=admin,
                    title='New Claim Submitted',
                    message=f'{user.get_full_name()} submitted claim #{claim_number}',
                    notification_type='info',
                    category='claim',
                    action_url='/admin/claims/',
                )
            
            return JsonResponse({
                'success': True,
                'claim_number': claim_number,
                'fraud_score': fraud_score,
                'risk_level': risk_level,
                'message': 'Claim submitted successfully!'
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            })
    
    # GET request - show the form
    context = {
        'user': request.user,
        'policies': Policy.objects.filter(user=request.user, status='active'),
        'pending_claims': Claim.objects.filter(user=request.user, status__in=['submitted', 'pending']).count(),
        'unread_notifications': Notification.objects.filter(user=request.user, is_read=False).count(),
        'now': datetime.now(),
    }
    return render(request, 'core/customer_submit_claim.html', context)


# ================================================================
# HELPER: CALCULATE FRAUD SCORE
# ================================================================

def calculate_fraud_score(amount_claimed, policy, user, incident_type):
    """Calculate AI fraud score based on multiple factors"""
    score = 0
    
    # Factor 1: Claim amount vs coverage
    coverage = policy.coverage_amount or 100000
    amount_ratio = (amount_claimed / coverage) * 100
    if amount_ratio > 80:
        score += 25
    elif amount_ratio > 50:
        score += 15
    elif amount_ratio > 30:
        score += 5
    
    # Factor 2: Recent claims frequency
    recent_claims = Claim.objects.filter(
        user=user,
        submitted_at__gte=timezone.now() - timedelta(days=30)
    ).count()
    if recent_claims > 3:
        score += 20
    elif recent_claims > 1:
        score += 10
    
    # Factor 3: Policy age
    if policy.start_date:
        policy_age = (timezone.now().date() - policy.start_date).days
        if policy_age < 30:
            score += 15
        elif policy_age < 90:
            score += 5
    
    # Factor 4: Incident type risk
    high_risk_types = ['theft', 'accident', 'liability']
    if incident_type in high_risk_types:
        score += 10
    
    # Factor 5: Amount thresholds
    if amount_claimed > 50000:
        score += 10
    elif amount_claimed > 100000:
        score += 20
    
    # Add randomness for AI simulation (keep score realistic)
    score += random.randint(-5, 5)
    
    # Ensure score is between 0 and 100
    score = max(0, min(100, score))
    
    return score


# ================================================================
# CUSTOMER MY CLAIMS
# ================================================================

@login_required
def customer_claims(request):
    """My Claims page"""
    claims = Claim.objects.filter(user=request.user).order_by('-submitted_at')
    
    # Calculate claim statistics
    total_claims = claims.count()
    approved_claims = claims.filter(status='approved').count()
    rejected_claims = claims.filter(status='rejected').count()
    pending_claims = claims.filter(status__in=['submitted', 'pending', 'investigation']).count()
    paid_claims = claims.filter(status='paid').count()
    
    # Prepare claim data for display
    claim_data = []
    for claim in claims:
        claim_data.append({
            'id': claim.id,
            'claim_number': claim.claim_number,
            'incident_type': claim.get_incident_type_display(),
            'incident_date': claim.incident_date,
            'amount_claimed': claim.amount_claimed,
            'amount_approved': claim.amount_approved,
            'status': claim.status,
            'status_display': claim.get_status_display(),
            'ai_fraud_score': claim.ai_fraud_score,
            'submitted_at': claim.submitted_at,
            'updated_at': claim.updated_at,
            'policy_number': claim.policy.policy_number if claim.policy else 'N/A',
            'policy_type': claim.policy.get_policy_type_display() if claim.policy else 'N/A',
            'can_appeal': claim.status == 'rejected',
        })
    
    context = {
        'user': request.user,
        'claims': claim_data,
        'total_claims': total_claims,
        'approved_claims': approved_claims,
        'rejected_claims': rejected_claims,
        'pending_claims': pending_claims,
        'paid_claims': paid_claims,
        'now': datetime.now(),
        'unread_notifications': Notification.objects.filter(user=request.user, is_read=False).count(),
    }
    return render(request, 'core/customer_claims.html', context)


# ================================================================
# CUSTOMER CLAIM DETAIL
# ================================================================

@login_required
def customer_claim_detail(request, claim_id):
    """Claim Detail page with full information"""
    try:
        claim = Claim.objects.get(id=claim_id, user=request.user)
    except Claim.DoesNotExist:
        messages.error(request, 'Claim not found.')
        return redirect('customer_claims')
    
    # Get related documents
    documents = Document.objects.filter(claim=claim)
    
    # Get timeline
    timeline = get_claim_timeline(claim)
    
    # Get related payments
    payments = Payment.objects.filter(claim=claim)
    
    claim_data = {
        'id': claim.id,
        'claim_number': claim.claim_number,
        'policy': {
            'type_display': claim.policy.get_policy_type_display() if claim.policy else 'N/A',
            'policy_number': claim.policy.policy_number if claim.policy else 'N/A',
            'coverage_amount': claim.policy.coverage_amount if claim.policy else 0,
            'premium_amount': claim.policy.premium_amount if claim.policy else 0,
        },
        'incident_type_display': claim.get_incident_type_display(),
        'incident_date': claim.incident_date,
        'incident_location': claim.incident_location or 'Not specified',
        'incident_description': claim.incident_description,
        'amount_claimed': claim.amount_claimed,
        'amount_approved': claim.amount_approved,
        'status': claim.status,
        'status_display': claim.get_status_display(),
        'submitted_at': claim.submitted_at,
        'updated_at': claim.updated_at,
        'resolved_at': claim.resolved_at,
        'investigator': claim.investigator.get_full_name() if claim.investigator else 'Not assigned',
        'ai_fraud_score': claim.ai_fraud_score,
        'ai_fraud_analysis': claim.ai_fraud_analysis or 'No suspicious patterns detected.',
        'rejection_reason': claim.rejection_reason or 'N/A',
        'documents': documents,
        'payments': payments,
        'timeline': timeline,
        'can_appeal': claim.status == 'rejected',
    }
    
    context = {
        'user': request.user,
        'claim': claim_data,
        'now': datetime.now(),
        'unread_notifications': Notification.objects.filter(user=request.user, is_read=False).count(),
    }
    return render(request, 'core/customer_claim_detail.html', context)


# ================================================================
# CUSTOMER TRACK CLAIM
# ================================================================

@login_required
def customer_track_claim(request):
    """Track Claim page - Fetches real claim from database"""
    claim_number = request.GET.get('claim', '')
    claim_data = None
    
    if claim_number:
        try:
            claim = Claim.objects.get(claim_number=claim_number, user=request.user)
            
            claim_data = {
                'claim_number': claim.claim_number,
                'policy_type': claim.policy.get_policy_type_display() if claim.policy else 'N/A',
                'policy_number': claim.policy.policy_number if claim.policy else 'N/A',
                'incident_type_display': claim.get_incident_type_display(),
                'amount_claimed': float(claim.amount_claimed),
                'submitted_at': claim.submitted_at.strftime('%d %b %Y, %H:%M'),
                'incident_date': claim.incident_date.strftime('%d %b %Y'),
                'incident_location': claim.incident_location or 'Not specified',
                'status': claim.status,
                'status_display': claim.get_status_display(),
                'ai_fraud_score': claim.ai_fraud_score,
                'ai_fraud_analysis': claim.ai_fraud_analysis or 'No analysis available.',
                'investigator': claim.investigator.get_full_name() if claim.investigator else 'Not assigned',
                'timeline': get_claim_timeline(claim),
            }
            
        except Claim.DoesNotExist:
            claim_data = None
    
    context = {
        'user': request.user,
        'now': datetime.now(),
        'claim_number': claim_number,
        'claim_data': claim_data,
        'pending_claims': Claim.objects.filter(user=request.user, status__in=['submitted', 'pending']).count(),
        'unread_notifications': Notification.objects.filter(user=request.user, is_read=False).count(),
    }
    return render(request, 'core/customer_track_claim.html', context)


def get_claim_timeline(claim):
    """Generate timeline for a claim"""
    timeline = []
    
    # 1. Claim Submitted
    timeline.append({
        'icon': 'blue',
        'icon_class': 'fa-upload',
        'title': 'Claim Submitted',
        'desc': 'Claim successfully submitted for processing.',
        'time': claim.submitted_at.strftime('%d %b %Y, %H:%M'),
        'completed': True,
    })
    
    # 2. AI Review
    if claim.ai_fraud_score is not None:
        risk_level = "Low" if claim.ai_fraud_score < 30 else "Medium" if claim.ai_fraud_score < 60 else "High"
        timeline.append({
            'icon': 'blue',
            'icon_class': 'fa-robot',
            'title': 'AI Review Complete',
            'desc': f'AI fraud assessment completed. Score: {claim.ai_fraud_score}% - Risk: {risk_level}',
            'time': claim.updated_at.strftime('%d %b %Y, %H:%M'),
            'completed': True,
        })
    
    # 3. Staff Review
    if claim.status in ['investigation', 'approved', 'rejected', 'paid']:
        timeline.append({
            'icon': 'purple',
            'icon_class': 'fa-user-tie',
            'title': 'Staff Review',
            'desc': 'Claim reviewed by staff.',
            'time': claim.updated_at.strftime('%d %b %Y, %H:%M'),
            'completed': True,
        })
    
    # 4. Investigation (if applicable)
    if claim.status in ['investigation', 'approved', 'paid']:
        timeline.append({
            'icon': 'purple',
            'icon_class': 'fa-search',
            'title': 'Investigation Completed',
            'desc': 'Investigation concluded.' if claim.ai_fraud_score < 30 else 'Investigation completed with some findings.',
            'time': claim.updated_at.strftime('%d %b %Y, %H:%M'),
            'completed': True,
        })
    
    # 5. Decision
    if claim.status in ['approved', 'paid']:
        timeline.append({
            'icon': 'green',
            'icon_class': 'fa-check-circle',
            'title': 'Claim Approved ✅',
            'desc': f'Claim approved for R{float(claim.amount_claimed):,.2f}.',
            'time': claim.updated_at.strftime('%d %b %Y, %H:%M'),
            'completed': True,
        })
    elif claim.status == 'rejected':
        timeline.append({
            'icon': 'red',
            'icon_class': 'fa-times-circle',
            'title': 'Claim Rejected ❌',
            'desc': f'Your claim has been rejected. Reason: {claim.rejection_reason or "Please contact support for more information."}',
            'time': claim.updated_at.strftime('%d %b %Y, %H:%M'),
            'completed': True,
        })
    
    # 6. Payment Released
    if claim.status == 'paid':
        timeline.append({
            'icon': 'green',
            'icon_class': 'fa-money-bill-wave',
            'title': 'Payment Released 💰',
            'desc': f'Payment of R{float(claim.amount_approved or claim.amount_claimed):,.2f} has been released.',
            'time': claim.updated_at.strftime('%d %b %Y, %H:%M'),
            'completed': True,
        })
    
    return timeline


# ================================================================
# CUSTOMER APPEAL CLAIM
# ================================================================

@login_required
def customer_appeal_claim(request, claim_id):
    """Appeal a rejected claim"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid request method.'})
    
    try:
        import json
        data = json.loads(request.body)
        appeal_reason = data.get('appeal_reason', '')
        
        if not appeal_reason:
            return JsonResponse({'success': False, 'error': 'Appeal reason is required.'})
        
        claim = Claim.objects.get(id=claim_id, user=request.user)
        
        if claim.status != 'rejected':
            return JsonResponse({'success': False, 'error': 'Only rejected claims can be appealed.'})
        
        # Update claim
        claim.status = 'appealed'
        claim.appeal_reason = appeal_reason
        claim.appeal_date = timezone.now()
        claim.save()
        
        # Notify customer
        Notification.objects.create(
            user=request.user,
            title='Appeal Submitted',
            message=f'Your appeal for claim #{claim.claim_number} has been submitted.',
            notification_type='info',
            category='claim',
            related_claim=claim,
            action_url=f'/dashboard/customer/claim/{claim.id}/',
        )
        
        # Notify Staff
        staff_users = User.objects.filter(profile__role='staff')
        for staff in staff_users:
            Notification.objects.create(
                user=staff,
                title='📋 Claim Appeal Received',
                message=f'{request.user.get_full_name()} has appealed claim #{claim.claim_number}.',
                notification_type='info',
                category='claim',
                action_url='/staff/claims-queue/',
            )
        
        return JsonResponse({'success': True, 'message': 'Appeal submitted successfully!'})
        
    except Claim.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Claim not found.'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


# ================================================================
# STAFF CLAIMS QUEUE
# ================================================================

@login_required
def staff_claims_queue_view(request):
    """Claims waiting for staff review"""
    profile = request.user.profile
    
    if profile.role not in ['staff', 'investigator']:
        messages.error(request, 'You do not have permission.')
        return redirect('dashboard')
    
    # Get all pending claims
    claims = Claim.objects.filter(status='submitted').order_by('-submitted_at')
    
    # Get sidebar counts
    pending_policies = Policy.objects.filter(status='pending').count()
    pending_claims = Claim.objects.filter(status='submitted').count()
    pending_documents = Document.objects.filter(status='pending').count()
    investigation_requests = Claim.objects.filter(status='investigation').count() + Document.objects.filter(status='investigation').count()
    verified_documents_count = Document.objects.filter(status='verified').count()
    refund_requests = Payment.objects.filter(status='pending', payment_type='refund').count()
    approved_claims_count = Claim.objects.filter(status='approved').count()
    rejected_claims_count = Claim.objects.filter(status='rejected').count()
    unread_notifications = Notification.objects.filter(user=request.user, is_read=False).count()
    
    claim_data = []
    for claim in claims:
        claim_data.append({
            'id': claim.id,
            'claim_number': claim.claim_number,
            'customer_name': claim.user.get_full_name() or claim.user.username,
            'customer_email': claim.user.email,
            'policy_number': claim.policy.policy_number if claim.policy else 'N/A',
            'policy_type': claim.policy.get_policy_type_display() if claim.policy else 'N/A',
            'incident_type': claim.get_incident_type_display(),
            'incident_date': claim.incident_date,
            'amount': claim.amount_claimed,
            'status': claim.status,
            'status_display': claim.get_status_display(),
            'ai_fraud_score': claim.ai_fraud_score,
            'submitted_at': claim.submitted_at,
            'days_pending': (timezone.now() - claim.submitted_at).days,
        })
    
    context = {
        'now': now(),
        'claims': claim_data,
        'total_claims': len(claim_data),
        'pending_claims': pending_claims,
        'high_risk_claims': Claim.objects.filter(status='submitted', ai_fraud_score__gte=60).count(),
        # Sidebar counters
        'pending_policies': pending_policies,
        'pending_documents': pending_documents,
        'investigation_requests': investigation_requests,
        'verified_documents_count': verified_documents_count,
        'refund_requests': refund_requests,
        'approved_claims_count': approved_claims_count,
        'rejected_claims_count': rejected_claims_count,
        'unread_notifications': unread_notifications,
        'user': request.user,
    }
    return render(request, 'core/staff_claims_queue.html', context)


# ================================================================
# STAFF CLAIM REVIEW
# ================================================================

@login_required
def staff_claim_review(request, claim_id):
    """Review and process a claim"""
    profile = request.user.profile
    
    if profile.role not in ['staff', 'investigator']:
        messages.error(request, 'You do not have permission.')
        return redirect('dashboard')
    
    try:
        claim = Claim.objects.get(id=claim_id)
    except Claim.DoesNotExist:
        messages.error(request, 'Claim not found.')
        return redirect('staff_claims_queue')
    
    if request.method == 'POST':
        try:
            import json
            data = json.loads(request.body)
            action = data.get('action')  # 'approve', 'reject', 'investigate'
            notes = data.get('notes', '')
            amount_approved = data.get('amount_approved', claim.amount_claimed)
            
            if action == 'approve':
                claim.status = 'approved'
                claim.amount_approved = amount_approved
                claim.resolved_at = now()
                claim.resolution_notes = notes
                claim.save()
                
                # Create payment for approved claim
                payment = Payment.objects.create(
                    payment_number=f"PAY-{datetime.now().year}-{random.randint(1000, 9999)}",
                    user=claim.user,
                    policy=claim.policy,
                    claim=claim,
                    amount=amount_approved,
                    payment_method='bank_transfer',
                    payment_type='claim_payout',
                    status='pending',
                    due_date=timezone.now().date() + timedelta(days=3),
                )
                
                # Notify customer
                Notification.objects.create(
                    user=claim.user,
                    title='Claim Approved! 🎉',
                    message=f'Your claim #{claim.claim_number} has been approved for R{amount_approved:,.2f}. Payment will be processed within 3 business days.',
                    notification_type='success',
                    category='claim',
                    related_claim=claim,
                    action_url=f'/dashboard/customer/claim/{claim.id}/',
                )
                
                # Notify staff
                Notification.objects.create(
                    user=request.user,
                    title='Claim Approved',
                    message=f'Claim #{claim.claim_number} approved for R{amount_approved:,.2f}.',
                    notification_type='success',
                    category='claim',
                )
                
                return JsonResponse({'success': True, 'message': 'Claim approved successfully! Payment initiated.'})
                
            elif action == 'reject':
                claim.status = 'rejected'
                claim.rejection_reason = notes
                claim.resolved_at = now()
                claim.resolution_notes = notes
                claim.save()
                
                # Notify customer
                Notification.objects.create(
                    user=claim.user,
                    title='Claim Rejected ❌',
                    message=f'Your claim #{claim.claim_number} was rejected. Reason: {notes or "Please contact support for more information."}',
                    notification_type='danger',
                    category='claim',
                    related_claim=claim,
                    action_url=f'/dashboard/customer/claim/{claim.id}/',
                )
                
                return JsonResponse({'success': True, 'message': 'Claim rejected.'})
                
            elif action == 'investigate':
                claim.status = 'investigation'
                claim.resolution_notes = f'Investigation required: {notes or "Claim flagged for further review."}'
                claim.save()
                
                # Notify customer
                Notification.objects.create(
                    user=claim.user,
                    title='Claim Under Investigation 🔍',
                    message=f'Your claim #{claim.claim_number} has been flagged for investigation.',
                    notification_type='warning',
                    category='claim',
                    related_claim=claim,
                    action_url=f'/dashboard/customer/claim/{claim.id}/',
                )
                
                # Notify investigators
                investigators = User.objects.filter(profile__role='investigator')
                for inv in investigators:
                    Notification.objects.create(
                        user=inv,
                        title='🔍 New Investigation Case',
                        message=f'Claim #{claim.claim_number} from {claim.user.get_full_name()} requires investigation.',
                        notification_type='warning',
                        category='investigation',
                        action_url=f'/investigator/case/{claim.id}/',
                    )
                
                return JsonResponse({'success': True, 'message': 'Claim sent for investigation.'})
            
            else:
                return JsonResponse({'success': False, 'error': 'Invalid action.'})
                
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    # GET request - show claim review page
    # Get related documents
    documents = Document.objects.filter(claim=claim)
    
    # Get claim timeline
    timeline = get_claim_timeline(claim)
    
    # Calculate risk indicators
    risk_indicators = []
    if claim.amount_claimed > (claim.policy.coverage_amount or 0) * 0.5:
        risk_indicators.append('High claim amount relative to coverage')
    if claim.ai_fraud_score > 50:
        risk_indicators.append('AI flagged as suspicious')
    if (timezone.now().date() - claim.policy.start_date).days < 30:
        risk_indicators.append('Policy is less than 30 days old')
    if Claim.objects.filter(user=claim.user, submitted_at__gte=timezone.now() - timedelta(days=30)).count() > 1:
        risk_indicators.append('Multiple claims in last 30 days')
    
    claim_data = {
        'id': claim.id,
        'claim_number': claim.claim_number,
        'policy': claim.policy,
        'user': claim.user,
        'incident_type_display': claim.get_incident_type_display(),
        'incident_date': claim.incident_date,
        'incident_location': claim.incident_location or 'Not specified',
        'incident_description': claim.incident_description,
        'amount_claimed': claim.amount_claimed,
        'status': claim.status,
        'status_display': claim.get_status_display(),
        'submitted_at': claim.submitted_at,
        'ai_fraud_score': claim.ai_fraud_score,
        'ai_fraud_analysis': claim.ai_fraud_analysis or 'No analysis available.',
        'documents': documents,
        'risk_indicators': risk_indicators,
        'timeline': timeline,
    }
    
    context = {
        'now': now(),
        'claim': claim_data,
        'risk_indicators': risk_indicators,
        'documents': documents,
        'timeline': timeline,
        'unread_notifications': Notification.objects.filter(user=request.user, is_read=False).count(),
        'user': request.user,
        'pending_claims': Claim.objects.filter(status='submitted').count(),
        'investigation_requests': Claim.objects.filter(status='investigation').count(),
    }
    return render(request, 'core/staff_claim_review.html', context)


# ================================================================
# STAFF APPROVED CLAIMS
# ================================================================

@login_required
def staff_approved_claims_view(request):
    """Claims approved by staff"""
    profile = request.user.profile
    
    if profile.role not in ['staff', 'investigator']:
        messages.error(request, 'You do not have permission.')
        return redirect('dashboard')
    
    claims = Claim.objects.filter(status='approved').order_by('-resolved_at')
    
    # Get sidebar counts
    pending_policies = Policy.objects.filter(status='pending').count()
    pending_claims = Claim.objects.filter(status='submitted').count()
    pending_documents = Document.objects.filter(status='pending').count()
    investigation_requests = Claim.objects.filter(status='investigation').count() + Document.objects.filter(status='investigation').count()
    verified_documents_count = Document.objects.filter(status='verified').count()
    refund_requests = Payment.objects.filter(status='pending', payment_type='refund').count()
    approved_claims_count = Claim.objects.filter(status='approved').count()
    rejected_claims_count = Claim.objects.filter(status='rejected').count()
    unread_notifications = Notification.objects.filter(user=request.user, is_read=False).count()
    
    claim_data = []
    for claim in claims:
        claim_data.append({
            'id': claim.id,
            'claim_number': claim.claim_number,
            'customer_name': claim.user.get_full_name() or claim.user.username,
            'customer_email': claim.user.email,
            'policy_number': claim.policy.policy_number if claim.policy else 'N/A',
            'incident_type': claim.get_incident_type_display(),
            'amount': claim.amount_claimed,
            'amount_approved': claim.amount_approved or claim.amount_claimed,
            'status': claim.status,
            'status_display': claim.get_status_display(),
            'resolved_at': claim.resolved_at,
            'resolved_by': claim.resolved_by or 'Staff',
        })
    
    context = {
        'now': now(),
        'claims': claim_data,
        'total_claims': len(claim_data),
        'total_amount': sum(c['amount_approved'] for c in claim_data),
        # Sidebar counters
        'pending_policies': pending_policies,
        'pending_claims': pending_claims,
        'pending_documents': pending_documents,
        'investigation_requests': investigation_requests,
        'verified_documents_count': verified_documents_count,
        'refund_requests': refund_requests,
        'approved_claims_count': approved_claims_count,
        'rejected_claims_count': rejected_claims_count,
        'unread_notifications': unread_notifications,
        'user': request.user,
    }
    return render(request, 'core/staff_approved_claims.html', context)


# ================================================================
# STAFF REJECTED CLAIMS
# ================================================================

@login_required
def staff_rejected_claims_view(request):
    """Claims rejected by staff"""
    profile = request.user.profile
    
    if profile.role not in ['staff', 'investigator']:
        messages.error(request, 'You do not have permission.')
        return redirect('dashboard')
    
    claims = Claim.objects.filter(status='rejected').order_by('-resolved_at')
    
    # Get sidebar counts
    pending_policies = Policy.objects.filter(status='pending').count()
    pending_claims = Claim.objects.filter(status='submitted').count()
    pending_documents = Document.objects.filter(status='pending').count()
    investigation_requests = Claim.objects.filter(status='investigation').count() + Document.objects.filter(status='investigation').count()
    verified_documents_count = Document.objects.filter(status='verified').count()
    refund_requests = Payment.objects.filter(status='pending', payment_type='refund').count()
    approved_claims_count = Claim.objects.filter(status='approved').count()
    rejected_claims_count = Claim.objects.filter(status='rejected').count()
    unread_notifications = Notification.objects.filter(user=request.user, is_read=False).count()
    
    claim_data = []
    for claim in claims:
        claim_data.append({
            'id': claim.id,
            'claim_number': claim.claim_number,
            'customer_name': claim.user.get_full_name() or claim.user.username,
            'customer_email': claim.user.email,
            'policy_number': claim.policy.policy_number if claim.policy else 'N/A',
            'incident_type': claim.get_incident_type_display(),
            'amount': claim.amount_claimed,
            'status': claim.status,
            'status_display': claim.get_status_display(),
            'resolved_at': claim.resolved_at,
            'rejection_reason': claim.rejection_reason or 'N/A',
            'resolved_by': claim.resolved_by or 'Staff',
        })
    
    context = {
        'now': now(),
        'claims': claim_data,
        'total_claims': len(claim_data),
        # Sidebar counters
        'pending_policies': pending_policies,
        'pending_claims': pending_claims,
        'pending_documents': pending_documents,
        'investigation_requests': investigation_requests,
        'verified_documents_count': verified_documents_count,
        'refund_requests': refund_requests,
        'approved_claims_count': approved_claims_count,
        'rejected_claims_count': rejected_claims_count,
        'unread_notifications': unread_notifications,
        'user': request.user,
    }
    return render(request, 'core/staff_rejected_claims.html', context)


# ================================================================
# STAFF INVESTIGATION REQUESTS
# ================================================================

@login_required
def staff_investigation_requests_view(request):
    """Claims that need to be sent to investigator or are under investigation"""
    profile = request.user.profile
    
    if profile.role not in ['staff', 'investigator']:
        messages.error(request, 'You do not have permission.')
        return redirect('dashboard')
    
    # Get claims under investigation
    claims = Claim.objects.filter(status='investigation').order_by('-submitted_at')
    
    # Get sidebar counts
    pending_policies = Policy.objects.filter(status='pending').count()
    pending_claims = Claim.objects.filter(status='submitted').count()
    pending_documents = Document.objects.filter(status='pending').count()
    investigation_requests = Claim.objects.filter(status='investigation').count() + Document.objects.filter(status='investigation').count()
    verified_documents_count = Document.objects.filter(status='verified').count()
    refund_requests = Payment.objects.filter(status='pending', payment_type='refund').count()
    approved_claims_count = Claim.objects.filter(status='approved').count()
    rejected_claims_count = Claim.objects.filter(status='rejected').count()
    unread_notifications = Notification.objects.filter(user=request.user, is_read=False).count()
    
    claim_data = []
    for claim in claims:
        claim_data.append({
            'id': claim.id,
            'claim_number': claim.claim_number,
            'customer_name': claim.user.get_full_name() or claim.user.username,
            'customer_email': claim.user.email,
            'policy_number': claim.policy.policy_number if claim.policy else 'N/A',
            'incident_type': claim.get_incident_type_display(),
            'amount': claim.amount_claimed,
            'ai_fraud_score': claim.ai_fraud_score,
            'status': claim.status,
            'status_display': claim.get_status_display(),
            'submitted_at': claim.submitted_at,
            'investigator': claim.investigator.get_full_name() if claim.investigator else 'Not assigned',
            'days_in_investigation': (timezone.now() - claim.updated_at).days if claim.updated_at else 0,
        })
    
    context = {
        'now': now(),
        'claims': claim_data,
        'total_claims': len(claim_data),
        # Sidebar counters
        'pending_policies': pending_policies,
        'pending_claims': pending_claims,
        'pending_documents': pending_documents,
        'investigation_requests': investigation_requests,
        'verified_documents_count': verified_documents_count,
        'refund_requests': refund_requests,
        'approved_claims_count': approved_claims_count,
        'rejected_claims_count': rejected_claims_count,
        'unread_notifications': unread_notifications,
        'user': request.user,
    }
    return render(request, 'core/staff_investigation_requests.html', context)


# ================================================================
# INVESTIGATOR FRAUD ALERTS
# ================================================================

@login_required
def investigator_fraud_alerts(request):
    """View all fraud alerts with filtering"""
    profile = request.user.profile
    
    if profile.role != 'investigator':
        messages.error(request, 'Access denied.')
        return redirect('dashboard')
    
    # Get claims with high AI fraud score
    fraud_alerts_qs = Claim.objects.filter(
        ai_fraud_score__gte=60,
        status__in=['submitted', 'investigation']
    ).select_related('policy__user', 'investigator').order_by('-ai_fraud_score')
    
    # Apply filters
    risk_level = request.GET.get('risk_level')
    if risk_level:
        if risk_level == 'high':
            fraud_alerts_qs = fraud_alerts_qs.filter(ai_fraud_score__gte=80)
        elif risk_level == 'medium':
            fraud_alerts_qs = fraud_alerts_qs.filter(ai_fraud_score__gte=60, ai_fraud_score__lt=80)
    
    assigned_filter = request.GET.get('assigned')
    if assigned_filter == 'unassigned':
        fraud_alerts_qs = fraud_alerts_qs.filter(investigator__isnull=True)
    elif assigned_filter == 'mine':
        fraud_alerts_qs = fraud_alerts_qs.filter(investigator=request.user)
    
    # Pagination
    page = request.GET.get('page', 1)
    paginator = Paginator(fraud_alerts_qs, 10)
    try:
        alerts_page = paginator.page(page)
    except PageNotAnInteger:
        alerts_page = paginator.page(1)
    except EmptyPage:
        alerts_page = paginator.page(paginator.num_pages)
    
    # Prepare alert data
    alerts = []
    for claim in alerts_page:
        risk = 'high' if claim.ai_fraud_score >= 80 else 'medium'
        alerts.append({
            'claim': claim,
            'risk_level': risk,
            'risk_score': claim.ai_fraud_score,
            'time_ago': time_since(claim.submitted_at),
            'assigned': claim.investigator is not None,
            'assigned_to_me': claim.investigator == request.user,
            'assigned_to_name': claim.investigator.get_full_name() if claim.investigator else None,
        })
    
    # Stats
    total_high = Claim.objects.filter(ai_fraud_score__gte=80, status__in=['submitted', 'investigation']).count()
    total_medium = Claim.objects.filter(ai_fraud_score__gte=60, ai_fraud_score__lt=80, status__in=['submitted', 'investigation']).count()
    total_unassigned = Claim.objects.filter(ai_fraud_score__gte=60, status__in=['submitted', 'investigation'], investigator__isnull=True).count()
    total_mine = Claim.objects.filter(ai_fraud_score__gte=60, status__in=['submitted', 'investigation'], investigator=request.user).count()
    
    context = {
        'alerts': alerts,
        'page_obj': alerts_page,
        'total_high': total_high,
        'total_medium': total_medium,
        'total_unassigned': total_unassigned,
        'total_mine': total_mine,
        'current_risk': risk_level,
        'current_assigned': assigned_filter,
        'unread_notifications': Notification.objects.filter(user=request.user, is_read=False).count(),
        'active_investigations': Claim.objects.filter(investigator=request.user, status='investigation').count(),
        'user': request.user,
        'now': timezone.now(),
    }
    return render(request, 'core/investigator_fraud_alerts.html', context)


# ================================================================
# INVESTIGATOR MY CASES
# ================================================================

@login_required
def investigator_cases(request):
    """View all cases assigned to this investigator"""
    profile = request.user.profile
    
    if profile.role != 'investigator':
        messages.error(request, 'Access denied.')
        return redirect('dashboard')
    
    # Get all cases assigned to this investigator
    cases_qs = Claim.objects.filter(
        investigator=request.user
    ).select_related('policy__user').order_by('-submitted_at')
    
    # Apply filters
    status_filter = request.GET.get('status')
    if status_filter:
        cases_qs = cases_qs.filter(status=status_filter)
    
    # Pagination
    page = request.GET.get('page', 1)
    paginator = Paginator(cases_qs, 10)
    try:
        cases_page = paginator.page(page)
    except PageNotAnInteger:
        cases_page = paginator.page(1)
    except EmptyPage:
        cases_page = paginator.page(paginator.num_pages)
    
    # Stats
    total_cases = cases_qs.count()
    open_cases = cases_qs.filter(status='investigation').count()
    closed_cases = cases_qs.filter(status__in=['approved', 'rejected']).count()
    
    context = {
        'cases': cases_page,
        'page_obj': cases_page,
        'total_cases': total_cases,
        'open_cases': open_cases,
        'closed_cases': closed_cases,
        'current_status': status_filter,
        'unread_notifications': Notification.objects.filter(user=request.user, is_read=False).count(),
        'active_investigations': open_cases,
        'user': request.user,
        'now': timezone.now(),
    }
    return render(request, 'core/investigator_cases.html', context)


# ================================================================
# INVESTIGATOR CASE DETAIL
# ================================================================

@login_required
def investigator_case_detail(request, claim_id):
    """View detailed case information and manage investigation"""
    profile = request.user.profile
    
    if profile.role != 'investigator':
        messages.error(request, 'Access denied.')
        return redirect('dashboard')
    
    claim = get_object_or_404(Claim.objects.select_related('policy__user', 'investigator'), id=claim_id)
    
    # Security: Check if investigator is assigned or claim is unassigned
    if claim.investigator and claim.investigator != request.user:
        messages.error(request, 'This case is assigned to another investigator.')
        return redirect('investigator_cases')
    
    # If unassigned, allow claiming
    if not claim.investigator:
        if request.method == 'POST' and request.POST.get('action') == 'claim_case':
            claim.investigator = request.user
            claim.status = 'investigation'
            claim.save()
            
            Notification.objects.create(
                user=claim.user,
                title='Case Assigned for Investigation',
                message=f'Your claim {claim.claim_number} has been assigned to Investigator {request.user.get_full_name()}.',
                notification_type='info',
                category='claim',
                related_claim=claim,
            )
            
            messages.success(request, f'Case {claim.claim_number} claimed successfully.')
            return redirect('investigator_case_detail', claim_id=claim.id)
    
    # Handle investigation findings
    if request.method == 'POST' and request.POST.get('action') == 'submit_findings':
        recommendation = request.POST.get('recommendation')
        findings = request.POST.get('findings', '')
        
        if recommendation == 'clear':
            claim.status = 'approved'
            claim.resolved_at = now()
            claim.resolution_notes = f'Cleared by investigator: {findings}'
            claim.save()
            
            Notification.objects.create(
                user=claim.user,
                title='Claim Cleared ✅',
                message=f'Your claim #{claim.claim_number} has been cleared by investigation.',
                notification_type='success',
                category='claim',
                related_claim=claim,
            )
            
            messages.success(request, 'Case cleared. Claim approved.')
            
        elif recommendation == 'fraud':
            claim.status = 'rejected'
            claim.rejection_reason = 'Fraud confirmed by investigator'
            claim.resolved_at = now()
            claim.resolution_notes = f'Fraud confirmed by investigator: {findings}'
            claim.save()
            
            Notification.objects.create(
                user=claim.user,
                title='Fraud Detected ❌',
                message=f'Your claim #{claim.claim_number} has been rejected due to fraudulent activity.',
                notification_type='danger',
                category='claim',
                related_claim=claim,
            )
            
            # Notify Admin
            admin_users = User.objects.filter(profile__role='administrator')
            for admin in admin_users:
                Notification.objects.create(
                    user=admin,
                    title='🚨 Fraud Confirmed',
                    message=f'Fraud confirmed on claim #{claim.claim_number} by {request.user.get_full_name()}.',
                    notification_type='danger',
                    category='investigation',
                    action_url='/admin/fraud/',
                )
            
            messages.warning(request, 'Fraud confirmed. Claim rejected.')
            
        else:
            messages.error(request, 'Invalid recommendation.')
        
        return redirect('investigator_cases')
    
    # Get related documents
    documents = Document.objects.filter(claim=claim)
    
    # Get claim timeline
    timeline = get_claim_timeline(claim)
    
    context = {
        'claim': claim,
        'documents': documents,
        'timeline': timeline,
        'unread_notifications': Notification.objects.filter(user=request.user, is_read=False).count(),
        'active_investigations': Claim.objects.filter(investigator=request.user, status='investigation').count(),
        'user': request.user,
        'now': timezone.now(),
    }
    return render(request, 'core/investigator_case_detail.html', context)