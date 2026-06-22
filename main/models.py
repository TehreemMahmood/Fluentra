from django.db import models
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.utils import timezone
import uuid


class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('The Email field must be set')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        return self.create_user(email, password, **extra_fields)


class User(AbstractUser):
    username = None
    email = models.EmailField(unique=True)
    full_name = models.CharField(max_length=255, blank=True)
    avatar = models.URLField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    # Email verification
    email_verified = models.BooleanField(default=False)
    email_verification_token = models.CharField(max_length=100, blank=True, null=True)
    email_verification_sent_at = models.DateTimeField(null=True, blank=True)
    
    # Onboarding fields
    age = models.IntegerField(null=True, blank=True)
    referral_source = models.CharField(max_length=50, blank=True, choices=[
        ('search', 'Search Engine'),
        ('social', 'Social Media'),
        ('friend', 'Friend or Family'),
        ('therapist', 'Speech Therapist'),
        ('other', 'Other'),
    ])
    primary_goal = models.CharField(max_length=50, blank=True, choices=[
        ('reduce_stuttering', 'Reduce Stuttering'),
        ('build_confidence', 'Build Confidence'),
        ('professional', 'Professional Speaking'),
        ('therapy_support', 'Support Therapy'),
    ])
    experience_level = models.CharField(max_length=20, blank=True, choices=[
        ('new', 'Just Starting'),
        ('some', 'Some Experience'),
        ('experienced', 'Experienced'),
    ])
    onboarding_completed = models.BooleanField(default=False)
    
    # Gamification fields
    xp_points = models.IntegerField(default=0)
    level = models.IntegerField(default=1)
    streak_days = models.IntegerField(default=0)
    last_practice_date = models.DateField(null=True, blank=True)
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []
    
    objects = UserManager()
    
    def __str__(self):
        return self.email
    
    def get_initials(self):
        if self.full_name:
            names = self.full_name.split()
            if len(names) >= 2:
                return f"{names[0][0]}{names[1][0]}".upper()
            return self.full_name[:2].upper()
        return self.email[:2].upper()
    
    def generate_verification_token(self):
        import secrets
        self.email_verification_token = secrets.token_urlsafe(32)
        self.email_verification_sent_at = timezone.now()
        self.save()
        return self.email_verification_token


class SubscriptionPlan(models.Model):
    PLAN_CHOICES = [
        ('basic', 'Basic'),
        ('pro', 'Pro'),
        ('clinic', 'Clinic'),
    ]
    
    name = models.CharField(max_length=50, choices=PLAN_CHOICES, unique=True)
    display_name = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=10, default='PKR')
    description = models.TextField(blank=True)
    features = models.JSONField(default=list)
    sessions_per_month = models.IntegerField(default=3)  # -1 for unlimited
    is_active = models.BooleanField(default=True)
    
    def __str__(self):
        return self.display_name


class Subscription(models.Model):
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('cancelled', 'Cancelled'),
        ('expired', 'Expired'),
        ('pending', 'Pending'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='subscription')
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.PROTECT)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    start_date = models.DateTimeField(auto_now_add=True)
    end_date = models.DateTimeField(null=True, blank=True)
    auto_renew = models.BooleanField(default=True)
    
    def __str__(self):
        return f"{self.user.email} - {self.plan.name}"
    
    def is_active(self):
        if self.status != 'active':
            return False
        if self.end_date and self.end_date < timezone.now():
            return False
        return True


class Payment(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='payments')
    subscription = models.ForeignKey(Subscription, on_delete=models.SET_NULL, null=True, related_name='payments')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=10, default='PKR')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    payment_method = models.CharField(max_length=50, default='card')
    transaction_id = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    # Card details (fake gateway - in production, never store these)
    card_last_four = models.CharField(max_length=4, blank=True)
    card_brand = models.CharField(max_length=20, blank=True)
    
    def __str__(self):
        return f"{self.user.email} - {self.amount} {self.currency}"


class SpeechSession(models.Model):
    SESSION_TYPES = [
        ('speech_analysis', 'Speech Analysis'),
        ('tongue_twister', 'Tongue Twister'),
        ('reading_exercise', 'Reading Exercise'),
        ('conversation', 'Conversation Practice'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sessions')
    created_at = models.DateTimeField(auto_now_add=True)
    duration_seconds = models.IntegerField(default=0)
    fluency_score = models.FloatField(null=True, blank=True)
    words_analyzed = models.IntegerField(default=0)
    session_type = models.CharField(max_length=50, choices=SESSION_TYPES, default='speech_analysis')
    
    # Audio and transcription
    audio_file = models.FileField(upload_to='recordings/', null=True, blank=True)
    transcription_text = models.TextField(blank=True)
    transcription_data = models.JSONField(default=dict, blank=True)  # Full word-level data
    
    # Analysis results
    analysis_data = models.JSONField(default=dict, blank=True)  # Full Gemini analysis
    stuttering_type = models.CharField(max_length=50, blank=True)
    repetitions_count = models.IntegerField(default=0)
    prolongations_count = models.IntegerField(default=0)
    blocks_count = models.IntegerField(default=0)
    interjections_count = models.IntegerField(default=0)
    
    # Flagged words for review
    flagged_words = models.JSONField(default=list, blank=True)
    
    def __str__(self):
        return f"{self.user.email} - {self.created_at.strftime('%Y-%m-%d %H:%M')}"
    
    def get_dysfluency_breakdown(self):
        return {
            'repetitions': self.repetitions_count,
            'prolongations': self.prolongations_count,
            'blocks': self.blocks_count,
            'interjections': self.interjections_count,
        }


class ExerciseResult(models.Model):
    """Stores results of exercise attempts (tongue twisters, etc.)"""
    EXERCISE_TYPES = [
        ('repetition', 'Repetition'),
        ('prolongation', 'Prolongation'),
        ('blocking', 'Blocking'),
        ('interjection', 'Interjection'),
    ]
    
    DIFFICULTY_LEVELS = [
        ('easy', 'Easy'),
        ('medium', 'Medium'),
        ('hard', 'Hard'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='exercise_results')
    exercise_type = models.CharField(max_length=50, choices=EXERCISE_TYPES)
    difficulty = models.CharField(max_length=20, choices=DIFFICULTY_LEVELS)
    
    # The sentence they were supposed to say
    expected_text = models.TextField()
    
    # What they actually said (transcribed)
    transcribed_text = models.TextField(blank=True)
    
    # Scoring
    accuracy_score = models.FloatField(default=0)  # 0-100
    fluency_score = models.FloatField(default=0)   # 0-100
    overall_score = models.FloatField(default=0)   # 0-10 points
    
    # XP awarded
    xp_earned = models.IntegerField(default=0)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    duration_seconds = models.IntegerField(default=0)
    
    # Audio file (optional)
    audio_file = models.FileField(upload_to='exercise_recordings/', null=True, blank=True)
    
    # Detailed feedback
    feedback = models.TextField(blank=True)
    word_matches = models.JSONField(default=dict, blank=True)  # Word-by-word comparison
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.user.email} - {self.exercise_type} ({self.difficulty}) - {self.overall_score}/10"

