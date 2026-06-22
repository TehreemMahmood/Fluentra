from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.shortcuts import redirect


class CustomAccountAdapter(DefaultAccountAdapter):
    """Custom adapter for email-only authentication."""
    
    def populate_username(self, request, user):
        """Skip username population since we don't use usernames."""
        pass
    
    def save_user(self, request, user, form, commit=True):
        """Save user without requiring username."""
        user = super().save_user(request, user, form, commit=False)
        if commit:
            user.save()
        return user
    
    def get_login_redirect_url(self, request):
        """Redirect to profile completion if needed."""
        if request.session.get('is_new_user'):
            return '/complete-profile/'
        return '/app/'


class CustomSocialAccountAdapter(DefaultSocialAccountAdapter):
    """Custom adapter for social login without username."""
    
    def populate_user(self, request, sociallogin, data):
        """Populate user from social login data - DON'T set name here, let user enter it."""
        user = super().populate_user(request, sociallogin, data)
        # Don't auto-populate full_name - let user enter it manually
        return user
    
    def is_auto_signup_allowed(self, request, sociallogin):
        """Allow auto signup for social accounts."""
        return True
    
    def is_existing_user(self, request, sociallogin):
        """Check if this is an existing user logging in."""
        from .models import User
        email = sociallogin.user.email
        if email:
            return User.objects.filter(email=email).exists()
        return False
    
    def pre_social_login(self, request, sociallogin):
        """Called before social login - check if user exists."""
        from .models import User
        email = sociallogin.user.email
        if email:
            try:
                existing_user = User.objects.get(email=email)
                # Connect this social account to existing user
                sociallogin.connect(request, existing_user)
                # Not a new user
                request.session['is_new_user'] = False
            except User.DoesNotExist:
                # This is a new user
                request.session['is_new_user'] = True
    
    def save_user(self, request, sociallogin, form=None):
        """Save user from social login - mark as new user for profile completion."""
        user = sociallogin.user
        user.set_unusable_password()
        # Don't set full_name - leave it blank so user must complete profile
        user.save()
        sociallogin.save(request)
        
        # Mark as new user for redirect
        request.session['is_new_user'] = True
        
        return user
    
    def get_login_redirect_url(self, request):
        """Redirect to profile completion for new users."""
        if request.session.get('is_new_user'):
            return '/complete-profile/'
        return '/app/'


