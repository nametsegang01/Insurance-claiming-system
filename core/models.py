# core/models.py
from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
import uuid

# ==============================
# USER PROFILE MODEL (UPDATED - Added admin fields)
# ==============================
class UserProfile(models.Model):
    """Extended user profile for all roles"""
    
    # Role choices
    ROLE_CHOICES = [
        ('policyholder', 'Policyholder'),
        ('staff', 'Insurance Staff'),
        ('investigator', 'Investigator'),
        ('administrator', 'Administrator'),
    ]
    
    # Status choices
    STATUS_CHOICES = [
        ('pending', 'Pending Approval'),
        ('active', 'Active'),
        ('suspended', 'Suspended'),
        ('disabled', 'Disabled'),
        ('archived', 'Archived'),
    ]
    
    # Department choices
    DEPARTMENT_CHOICES = [
        ('claims', 'Claims'),
        ('underwriting', 'Underwriting'),
        ('customer_support', 'Customer Support'),
        ('policy_admin', 'Policy Administration'),
        ('finance', 'Finance'),
        ('compliance', 'Compliance'),
        ('it', 'IT'),
        ('hr', 'Human Resources'),
        ('marketing', 'Marketing'),
        ('sales', 'Sales'),
        ('fraud_investigation', 'Fraud Investigation'),
        ('forensic_investigation', 'Forensic Investigation'),
        ('special_investigations', 'Special Investigations'),
        ('claims_investigation', 'Claims Investigation'),
    ]
    
    # Specialization choices (for investigators)
    SPECIALIZATION_CHOICES = [
        ('vehicle_fraud', 'Vehicle Fraud'),
        ('property_fraud', 'Property Fraud'),
        ('health_fraud', 'Health Fraud'),
        ('life_fraud', 'Life Insurance Fraud'),
        ('cyber_fraud', 'Cyber Fraud'),
        ('general_fraud', 'General Fraud'),
        ('organized_crime', 'Organized Crime'),
    ]
    
    # Link to Django User
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    
    # Basic info
    phone = models.CharField(max_length=20, blank=True, null=True)
    id_number = models.CharField(max_length=20, blank=True, null=True)
    
    # Address
    province = models.CharField(max_length=50, blank=True, null=True)
    city = models.CharField(max_length=50, blank=True, null=True)
    postal_code = models.CharField(max_length=10, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    
    # Role & Status
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='policyholder')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    
    # Staff/Investigator specific fields
    employee_number = models.CharField(max_length=50, blank=True, null=True)
    department = models.CharField(max_length=50, choices=DEPARTMENT_CHOICES, blank=True, null=True)
    branch = models.CharField(max_length=100, blank=True, null=True)
    position = models.CharField(max_length=100, blank=True, null=True)
    specialization = models.CharField(max_length=50, choices=SPECIALIZATION_CHOICES, blank=True, null=True)
    
    # ===== NEW ADMIN FIELDS (Added for registration/login system) =====
    # Admin invitation tracking
    invited_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='invited_admins'
    )
    is_verified = models.BooleanField(default=False)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # AI Risk Profile
    ai_trust_score = models.IntegerField(default=100)  # 0-100
    fraud_risk_level = models.CharField(max_length=20, default='Low')
    
    def __str__(self):
        return f"{self.user.username} - {self.get_role_display()}"
    
    def is_active_user(self):
        """Check if user account is active"""
        return self.status == 'active'
    
    def is_pending(self):
        """Check if user account is pending approval"""
        return self.status == 'pending'
    
    def can_login(self):
        """Check if user can login"""
        return self.status in ['active', 'pending']
    
    def is_administrator(self):
        """Check if user is an administrator"""
        return self.role == 'administrator' and self.status == 'active'
    
    def is_staff_or_investigator(self):
        """Check if user is staff or investigator"""
        return self.role in ['staff', 'investigator']


# ==============================
# NEW: ADMIN INVITATION MODEL
# ==============================
class AdminInvitation(models.Model):
    """Model to track administrator invitations"""
    
    ADMIN_TYPES = [
        ('full', 'Full Administrator'),
        ('finance', 'Finance Administrator'),
        ('system', 'System Administrator'),
    ]
    
    # Basic info
    email = models.EmailField(unique=True)
    invited_by = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='sent_invitations'
    )
    
    # Token & Expiry
    token = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    admin_type = models.CharField(max_length=20, choices=ADMIN_TYPES, default='full')
    
    # Status
    accepted = models.BooleanField(default=False)
    accepted_at = models.DateTimeField(null=True, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    
    def is_valid(self):
        """Check if invitation is still valid"""
        return not self.accepted and timezone.now() < self.expires_at
    
    def is_expired(self):
        """Check if invitation has expired"""
        return timezone.now() > self.expires_at
    
    def __str__(self):
        return f"Invitation for {self.email} by {self.invited_by.username}"
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Admin Invitation'
        verbose_name_plural = 'Admin Invitations'


# ==============================
# POLICY MODEL (UNCHANGED - DO NOT TOUCH)
# ==============================
class Policy(models.Model):
    """Insurance Policy Model"""
    
    POLICY_TYPES = [
        ('vehicle', 'Vehicle Insurance'),
        ('home', 'Home Insurance'),
        ('life', 'Life Insurance'),
        ('health', 'Health Insurance'),
        ('business', 'Business Insurance'),
        ('travel', 'Travel Insurance'),
    ]
    
    POLICY_STATUS = [
        ('active', 'Active'),
        ('pending', 'Pending'),
        ('expired', 'Expired'),
        ('cancelled', 'Cancelled'),
        ('suspended', 'Suspended'),
    ]
    
    # Basic Info
    policy_number = models.CharField(max_length=50, unique=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='policies')
    policy_type = models.CharField(max_length=20, choices=POLICY_TYPES)
    
    # Coverage & Premium
    coverage_amount = models.DecimalField(max_digits=15, decimal_places=2)
    premium_amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_frequency = models.CharField(max_length=20, default='monthly')
    
    # Dates
    start_date = models.DateField()
    end_date = models.DateField()
    renewal_date = models.DateField()
    
    # Status
    status = models.CharField(max_length=20, choices=POLICY_STATUS, default='pending')
    
    # AI Risk
    ai_risk_score = models.IntegerField(default=0)  # 0-100
    ai_risk_level = models.CharField(max_length=20, default='Low')
    
    # Beneficiary Info
    beneficiary_name = models.CharField(max_length=200, blank=True, null=True)
    beneficiary_id = models.CharField(max_length=20, blank=True, null=True)
    beneficiary_relationship = models.CharField(max_length=50, blank=True, null=True)
    beneficiary_phone = models.CharField(max_length=20, blank=True, null=True)
    beneficiary_email = models.EmailField(blank=True, null=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.policy_number} - {self.get_policy_type_display()}"
    
    def get_status_display(self):
        return dict(self.POLICY_STATUS).get(self.status, self.status)
    
    def type_display(self):
        return dict(self.POLICY_TYPES).get(self.policy_type, self.policy_type)


# ==============================
# CLAIM MODEL (UNCHANGED - DO NOT TOUCH)
# ==============================
class Claim(models.Model):
    """Insurance Claim Model"""
    
    INCIDENT_TYPES = [
        ('accident', 'Accident'),
        ('theft', 'Theft'),
        ('damage', 'Damage'),
        ('fire', 'Fire'),
        ('natural_disaster', 'Natural Disaster'),
        ('medical', 'Medical Emergency'),
        ('death', 'Death Claim'),
        ('other', 'Other'),
    ]
    
    CLAIM_STATUS = [
        ('submitted', 'Submitted'),
        ('pending', 'Pending Review'),
        ('investigation', 'Under Investigation'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('paid', 'Paid Out'),
    ]
    
    # Basic Info
    claim_number = models.CharField(max_length=50, unique=True)
    policy = models.ForeignKey(Policy, on_delete=models.CASCADE, related_name='claims')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='claims')
    
    # Incident Details
    incident_type = models.CharField(max_length=20, choices=INCIDENT_TYPES)
    incident_date = models.DateField()
    incident_description = models.TextField()
    incident_location = models.CharField(max_length=255, blank=True, null=True)
    
    # Claim Amount
    amount_claimed = models.DecimalField(max_digits=15, decimal_places=2)
    amount_approved = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    
    # Status
    status = models.CharField(max_length=20, choices=CLAIM_STATUS, default='submitted')
    
    # AI Fraud Detection
    ai_fraud_score = models.IntegerField(default=0)  # 0-100
    ai_fraud_analysis = models.TextField(blank=True, null=True)
    
    # Investigator (for high-risk claims)
    investigator = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='investigated_claims')
    investigation_notes = models.TextField(blank=True, null=True)
    
    # Death Claim specific fields
    deceased_name = models.CharField(max_length=200, blank=True, null=True)
    deceased_id = models.CharField(max_length=20, blank=True, null=True)
    date_of_death = models.DateField(null=True, blank=True)
    cause_of_death = models.CharField(max_length=255, blank=True, null=True)
    
    # Timestamps
    submitted_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    
    def __str__(self):
        return f"{self.claim_number} - {self.get_status_display()}"
    
    def get_status_display(self):
        return dict(self.CLAIM_STATUS).get(self.status, self.status)
    
    def incident_type_display(self):
        return dict(self.INCIDENT_TYPES).get(self.incident_type, self.incident_type)


# ==============================
# PAYMENT MODEL (UNCHANGED - DO NOT TOUCH)
# ==============================
class Payment(models.Model):
    """Payment Model"""
    
    PAYMENT_STATUS = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded'),
    ]
    
    PAYMENT_METHODS = [
        ('card', 'Card Payment'),
        ('bank_transfer', 'Bank Transfer'),
        ('debit_order', 'Debit Order'),
        ('payfast', 'PayFast'),
    ]
    
    # Basic Info
    payment_number = models.CharField(max_length=50, unique=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='payments')
    policy = models.ForeignKey(Policy, on_delete=models.CASCADE, related_name='payments', null=True, blank=True)
    
    # Payment Details
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHODS)
    payment_type = models.CharField(max_length=20, default='premium')
    
    # Status
    status = models.CharField(max_length=20, choices=PAYMENT_STATUS, default='pending')
    
    # Gateway Details
    transaction_id = models.CharField(max_length=100, blank=True, null=True)
    gateway_response = models.TextField(blank=True, null=True)
    
    # Dates
    due_date = models.DateField()
    paid_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.payment_number} - {self.get_status_display()}"
    
    def get_status_display(self):
        return dict(self.PAYMENT_STATUS).get(self.status, self.status)


# ==============================
# DOCUMENT MODEL (UNCHANGED - DO NOT TOUCH)
# ==============================
class Document(models.Model):
    """Document Model"""
    
    DOCUMENT_TYPES = [
        ('id_document', 'ID Document'),
        ('proof_of_address', 'Proof of Address'),
        ('policy_schedule', 'Policy Schedule'),
        ('terms_conditions', 'Terms & Conditions'),
        ('welcome_letter', 'Welcome Letter'),
        ('premium_schedule', 'Premium Schedule'),
        ('fica_document', 'FICA Document'),
        ('police_report', 'Police Report'),
        ('accident_photos', 'Accident Photos'),
        ('medical_report', 'Medical Report'),
        ('death_certificate', 'Death Certificate'),
        ('bank_details', 'Bank Details'),
        ('other', 'Other'),
    ]
    
    DOCUMENT_STATUS = [
        ('pending', 'Pending Verification'),
        ('verified', 'Verified'),
        ('rejected', 'Rejected'),
    ]
    
    # Basic Info
    document_number = models.CharField(max_length=50, unique=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='documents')
    policy = models.ForeignKey(Policy, on_delete=models.CASCADE, related_name='documents', null=True, blank=True)
    claim = models.ForeignKey(Claim, on_delete=models.CASCADE, related_name='documents', null=True, blank=True)
    
    # Document Details
    document_type = models.CharField(max_length=50, choices=DOCUMENT_TYPES)
    document_name = models.CharField(max_length=255)
    document_file = models.FileField(upload_to='documents/%Y/%m/%d/', blank=True, null=True)
    file_size = models.IntegerField(default=0)
    file_type = models.CharField(max_length=50, blank=True, null=True)
    
    # Status
    status = models.CharField(max_length=20, choices=DOCUMENT_STATUS, default='pending')
    
    # AI Verification
    ai_verification_score = models.IntegerField(default=0)
    ai_verification_notes = models.TextField(blank=True, null=True)
    
    # Staff Verification
    verified_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='verified_documents')
    verified_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True, null=True)
    
    # Timestamps
    uploaded_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.document_number} - {self.document_name}"
    
    def get_status_display(self):
        return dict(self.DOCUMENT_STATUS).get(self.status, self.status)


# ==============================
# NOTIFICATION MODEL (UNCHANGED - DO NOT TOUCH)
# ==============================
class Notification(models.Model):
    """Notification Model"""
    
    NOTIFICATION_TYPES = [
        ('info', 'Information'),
        ('success', 'Success'),
        ('warning', 'Warning'),
        ('danger', 'Urgent'),
    ]
    
    NOTIFICATION_CATEGORIES = [
        ('policy', 'Policy Update'),
        ('claim', 'Claim Update'),
        ('payment', 'Payment Update'),
        ('document', 'Document Update'),
        ('fraud', 'Fraud Alert'),
        ('renewal', 'Renewal Reminder'),
        ('system', 'System Message'),
    ]
    
    # Basic Info
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    title = models.CharField(max_length=255)
    message = models.TextField()
    
    # Type & Category
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES, default='info')
    category = models.CharField(max_length=20, choices=NOTIFICATION_CATEGORIES, default='system')
    
    # Read Status
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    
    # Related Objects
    related_policy = models.ForeignKey(Policy, on_delete=models.SET_NULL, null=True, blank=True)
    related_claim = models.ForeignKey(Claim, on_delete=models.SET_NULL, null=True, blank=True)
    related_payment = models.ForeignKey(Payment, on_delete=models.SET_NULL, null=True, blank=True)
    
    # Link/URL
    action_url = models.CharField(max_length=255, blank=True, null=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.title} - {self.user.username}"
    
    def mark_as_read(self):
        self.is_read = True
        self.read_at = timezone.now()
        self.save()


# ==============================
# SIGNALS: Auto-create profile when user is created
# ==============================
@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """Automatically create a UserProfile when a User is created"""
    if created:
        UserProfile.objects.create(user=instance)


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    """Save UserProfile when User is saved"""
    if hasattr(instance, 'profile'):
        instance.profile.save()