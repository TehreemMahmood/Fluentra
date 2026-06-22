from django.urls import path
from django.views.generic import RedirectView
from . import views

urlpatterns = [
    # Pages
    path('', views.index, name='index'),
    path('about/', views.about, name='about'),
    path('app/', views.app, name='app'),
    path('app/techniques/', views.techniques, name='techniques'),
    path('app/techniques/breathing/', views.technique_breathing, name='technique_breathing'),
    path('app/techniques/articulation/', views.technique_articulation, name='technique_articulation'),
    path('app/techniques/cancellation/', views.technique_cancellation, name='technique_cancellation'),
    path('app/techniques/prolonged/', views.technique_prolonged, name='technique_prolonged'),
    path('app/techniques/onset/', views.technique_onset, name='technique_onset'),
    path('app/exercises/', views.exercises, name='exercises'),
    path('app/exercises/repetition/', views.exercise_repetition, name='exercise_repetition'),
    path('app/exercises/prolongation/', views.exercise_prolongation, name='exercise_prolongation'),
    path('app/exercises/blocking/', views.exercise_blocking, name='exercise_blocking'),
    path('app/exercises/interjection/', views.exercise_interjection, name='exercise_interjection'),
    path('app/practice/', views.practice_view, name='practice'),
    path('api/transcribe/', views.transcribe_audio, name='transcribe_audio'),
    path('api/ai-chat/', views.ai_chat, name='ai_chat'),
    path('app/analytics/', views.analytics, name='analytics'),
    path('app/settings/', views.settings_view, name='settings'),
    path('auth/', views.auth_view, name='auth'),
    path('contact/', views.contact, name='contact'),
    path('pricing/', views.pricing, name='pricing'),
    
    # Authentication
    path('api/signup/', views.signup_view, name='signup'),
    path('api/login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('google-login/', RedirectView.as_view(url='/accounts/google/login/', permanent=False), name='google_login'),
    path('complete-profile/', views.complete_profile_view, name='complete_profile'),
    path('api/complete-profile/', views.complete_profile_api, name='complete_profile_api'),
    
    # Email Verification
    path('verify-email/<str:token>/', views.verify_email_view, name='verify_email'),
    path('verify-pending/', views.verify_pending_view, name='verify_pending'),
    path('api/resend-verification/', views.resend_verification_view, name='resend_verification'),
    
    # Subscription & Payments
    path('subscription/', views.subscription_view, name='subscription'),
    path('checkout/<str:plan_name>/', views.checkout_view, name='checkout'),
    path('api/payment/process/', views.process_payment, name='process_payment'),
    path('api/subscription/cancel/', views.cancel_subscription, name='cancel_subscription'),
    
    # User API
    path('api/user/profile/', views.get_user_profile, name='user_profile'),
    path('api/user/payments/', views.get_payment_history, name='payment_history'),
    
    # Exercise API
    path('api/exercise/evaluate/', views.evaluate_exercise, name='evaluate_exercise'),
]
