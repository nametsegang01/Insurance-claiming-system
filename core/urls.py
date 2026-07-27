# core/urls.py
from django.urls import path
from . import views

urlpatterns = [
    # ============================================================ */
    # LANDING & STATIC PAGES
    # ============================================================ */
    path('', views.home, name='home'),
    path('features/', views.features, name='features'),
    path('about/', views.about, name='about'),
    path('contact/', views.contact, name='contact'),
    
    # ============================================================ */
    # AUTHENTICATION
    # ============================================================ */
    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    
    # ============================================================ */
    # DASHBOARD ROUTING
    # ============================================================ */
    path('dashboard/', views.dashboard, name='dashboard'),
    path('dashboard/customer/', views.customer_dashboard, name='customer_dashboard'),
    path('dashboard/staff/', views.staff_dashboard_view, name='staff_dashboard'),
    path('dashboard/investigator/', views.investigator_dashboard, name='investigator_dashboard'),
    
    # ============================================================ */
    # CUSTOMER PAGES
    # ============================================================ */
    path('dashboard/customer/policies/', views.customer_policies, name='customer_policies'),
    path('dashboard/customer/policy/<int:policy_id>/', views.customer_policy_detail, name='customer_policy_detail'),
    path('dashboard/customer/claims/', views.customer_claims, name='customer_claims'),
    path('dashboard/customer/claim/<int:claim_id>/', views.customer_claim_detail, name='customer_claim_detail'),
    path('dashboard/customer/payments/', views.customer_payments, name='customer_payments'),
    path('dashboard/customer/documents/', views.customer_documents, name='customer_documents'),
    path('dashboard/customer/notifications/', views.customer_notifications, name='customer_notifications'),
    path('dashboard/customer/ai-assistant/', views.customer_ai_assistant, name='customer_ai_assistant'),
    path('dashboard/customer/profile/', views.customer_profile, name='customer_profile'),
    path('dashboard/customer/settings/', views.customer_settings, name='customer_settings'),
    path('dashboard/customer/purchase/', views.customer_purchase_policy, name='customer_purchase_policy'),
    path('dashboard/customer/submit-claim/', views.customer_submit_claim, name='customer_submit_claim'),
    path('dashboard/customer/invoices/', views.customer_invoices, name='customer_invoices'),
    path('dashboard/customer/support/', views.customer_support, name='customer_support'),
    path('dashboard/customer/fraud-monitor/', views.customer_fraud_monitor, name='customer_fraud_monitor'),
    path('dashboard/customer/track-claim/', views.customer_track_claim, name='customer_track_claim'),
    path('dashboard/customer/renew/', views.customer_renew_policy, name='customer_renew_policy'),
    path('dashboard/customer/update/', views.customer_update_policy, name='customer_update_policy'),
    path('dashboard/customer/cancel/', views.customer_cancel_policy, name='customer_cancel_policy'),
    path('dashboard/customer/purchase-wizard/', views.customer_purchase_wizard, name='customer_purchase_wizard'),
    path('customer/documents/upload/', views.customer_upload_document, name='customer_upload_document'),
    path('customer/appeal-claim/<int:claim_id>/', views.customer_appeal_claim, name='customer_appeal_claim'),
    
    # ============================================================ */
    # STAFF PAGES
    # ============================================================ */
    # Staff Dashboard
    path('dashboard/staff/', views.staff_dashboard_view, name='staff_dashboard'),
    
    # Policy Management
    path('staff/new-applications/', views.staff_new_applications_view, name='staff_new_applications'),
    path('staff/policies/', views.staff_policies_view, name='staff_policies'),
    path('staff/customers/', views.staff_customers_view, name='staff_customers'),
    path('staff/verify-document/', views.staff_verify_document, name='staff_verify_document'),
    path('staff/process-application/', views.staff_process_application, name='staff_process_application'),
    
    # Claims Management
    path('staff/claims-queue/', views.staff_claims_queue_view, name='staff_claims_queue'),
    path('staff/claim-review/<int:claim_id>/', views.staff_claim_review, name='staff_claim_review'),
    path('staff/approved-claims/', views.staff_approved_claims_view, name='staff_approved_claims'),
    path('staff/rejected-claims/', views.staff_rejected_claims_view, name='staff_rejected_claims'),
    path('staff/investigation-requests/', views.staff_investigation_requests_view, name='staff_investigation_requests'),
    
    # Payments
    path('staff/payments/', views.staff_payments_view, name='staff_payments'),
    path('staff/refund-requests/', views.staff_refund_requests_view, name='staff_refund_requests'),
    
    # Documents
    path('staff/documents/', views.staff_documents_view, name='staff_documents'),
    path('staff/verified-documents/', views.staff_verified_documents_view, name='staff_verified_documents'),
    
    # Communication
    path('staff/notifications/', views.staff_notifications_view, name='staff_notifications'),
    
    # Reports
    path('staff/reports/', views.staff_reports_view, name='staff_reports'),
    path('staff/analytics/', views.staff_analytics_view, name='staff_analytics'),
    
    # Account
    path('staff/profile/', views.staff_profile_view, name='staff_profile'),
    path('staff/settings/', views.staff_settings_view, name='staff_settings'),
    
    # ============================================================ */
    # ADMIN PAGES
    # ============================================================ */
    path('admin/dashboard/', views.admin_dashboard_view, name='admin_dashboard'),
    path('admin/users/', views.admin_users_view, name='admin_users'),
    path('admin/staff/', views.admin_staff_view, name='admin_staff'),
    path('admin/staff/add/', views.admin_staff_add, name='admin_staff_add'),
    path('admin/staff/approve/', views.admin_staff_approve, name='admin_staff_approve'),
    path('admin/staff/approve-all/', views.admin_staff_approve_all, name='admin_staff_approve_all'),
    path('admin/policies/', views.admin_policies_view, name='admin_policies'),
    path('admin/claims/', views.admin_claims_view, name='admin_claims'),
    path('admin/fraud/', views.admin_fraud_view, name='admin_fraud'),
    path('admin/payments/', views.admin_payments_view, name='admin_payments'),
    path('admin/settings/', views.admin_settings_view, name='admin_settings'),
    path('admin/reports/', views.admin_reports_view, name='admin_reports'),
    path('admin/ai-insights/', views.admin_ai_insights_view, name='admin_ai_insights'),
    path('admin/notifications/', views.admin_notifications_view, name='admin_notifications'),
    path('admin/analytics/', views.admin_analytics_view, name='admin_analytics'),
    path('admin/customer/<int:user_id>/', views.admin_customer_detail_view, name='admin_customer_detail'),
    path('admin/invite/', views.admin_invite_view, name='admin_invite'),
    path('admin/invite/accept/<uuid:token>/', views.admin_accept_invite_view, name='admin_accept_invite'),
    
    # ============================================================ */
    # INVESTIGATOR PAGES
    # ============================================================ */
    path('investigator/dashboard/', views.investigator_dashboard, name='investigator_dashboard'),
    path('investigator/fraud-alerts/', views.investigator_fraud_alerts, name='investigator_fraud_alerts'),
    path('investigator/cases/', views.investigator_cases, name='investigator_cases'),
    path('investigator/case/<int:claim_id>/', views.investigator_case_detail, name='investigator_case_detail'),
    path('investigator/documents/', views.investigator_document_analysis, name='investigator_document_analysis'),
    path('investigator/reports/', views.investigator_fraud_reports, name='investigator_fraud_reports'),
    path('investigator/analytics/', views.investigator_fraud_analytics, name='investigator_fraud_analytics'),
    path('investigator/ai-insights/', views.investigator_ai_insights, name='investigator_ai_insights'),
    path('investigator/notifications/', views.investigator_notifications, name='investigator_notifications'),
    path('investigator/profile/', views.investigator_profile, name='investigator_profile'),
    path('investigator/settings/', views.investigator_settings, name='investigator_settings'),
]