from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html
from django.db.models import Count, Avg
from django.urls import reverse
from django.utils import timezone
from .models import User, SubscriptionPlan, Subscription, Payment, SpeechSession


class UserAdmin(BaseUserAdmin):
    list_display = ('email', 'full_name', 'level_badge', 'streak_display', 'is_staff', 'is_active', 'verification_status', 'created_at')
    list_filter = ('is_staff', 'is_active', 'email_verified', 'onboarding_completed', 'experience_level', 'level')
    search_fields = ('email', 'full_name')
    ordering = ('-created_at',)
    list_per_page = 25
    date_hierarchy = 'created_at'
    
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('👤 Personal Info', {'fields': ('full_name', 'avatar', 'age')}),
        ('🎯 Onboarding', {'fields': ('referral_source', 'primary_goal', 'experience_level', 'onboarding_completed')}),
        ('✉️ Email Verification', {'fields': ('email_verified', 'email_verification_token', 'email_verification_sent_at')}),
        ('🎮 Gamification', {'fields': ('xp_points', 'level', 'streak_days', 'last_practice_date')}),
        ('🔐 Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('📅 Important dates', {'fields': ('last_login', 'created_at')}),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'password1', 'password2', 'full_name', 'is_staff', 'is_active'),
        }),
    )
    
    readonly_fields = ('created_at',)
    actions = ['verify_email', 'reset_streak', 'add_xp']
    
    def level_badge(self, obj):
        colors = ['#6c757d', '#28a745', '#17a2b8', '#ffc107', '#dc3545', '#6f42c1']
        color = colors[min(obj.level - 1, len(colors) - 1)]
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 12px; font-weight: bold;">Level {}</span>',
            color, obj.level
        )
    level_badge.short_description = 'Level'
    level_badge.admin_order_field = 'level'
    
    def streak_display(self, obj):
        if obj.streak_days > 0:
            return format_html('🔥 {} days', obj.streak_days)
        return format_html('<span style="color: #999;">No streak</span>')
    streak_display.short_description = 'Streak'
    streak_display.admin_order_field = 'streak_days'
    
    def verification_status(self, obj):
        if obj.email_verified:
            return format_html('<span style="color: #28a745;">✓ Verified</span>')
        return format_html('<span style="color: #dc3545;">✗ Not Verified</span>')
    verification_status.short_description = 'Email'
    
    @admin.action(description='✓ Mark selected users as email verified')
    def verify_email(self, request, queryset):
        updated = queryset.update(email_verified=True)
        self.message_user(request, f'{updated} users marked as verified.')
    
    @admin.action(description='🔄 Reset streak to 0')
    def reset_streak(self, request, queryset):
        queryset.update(streak_days=0)
        self.message_user(request, 'Streaks reset.')
    
    @admin.action(description='➕ Add 100 XP to selected users')
    def add_xp(self, request, queryset):
        for user in queryset:
            user.xp_points += 100
            user.save()
        self.message_user(request, f'Added 100 XP to {queryset.count()} users.')


@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    list_display = ('display_name', 'name', 'price_display', 'sessions_per_month', 'subscriber_count', 'status_badge')
    list_filter = ('is_active', 'currency')
    search_fields = ('name', 'display_name')
    list_per_page = 20
    
    def price_display(self, obj):
        if obj.price == 0:
            return format_html('<span style="color: #28a745; font-weight: bold;">FREE</span>')
        return format_html('<strong>{} {}</strong>', obj.currency, obj.price)
    price_display.short_description = 'Price'
    price_display.admin_order_field = 'price'
    
    def subscriber_count(self, obj):
        count = Subscription.objects.filter(plan=obj, status='active').count()
        return format_html('<span style="background: #e9ecef; padding: 2px 8px; border-radius: 10px;">{} subscribers</span>', count)
    subscriber_count.short_description = 'Active Subscribers'
    
    def status_badge(self, obj):
        if obj.is_active:
            return format_html('<span style="color: #28a745;">● Active</span>')
        return format_html('<span style="color: #dc3545;">● Inactive</span>')
    status_badge.short_description = 'Status'


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ('user', 'plan', 'status_badge', 'start_date', 'end_date', 'auto_renew_icon')
    list_filter = ('status', 'plan', 'auto_renew', 'start_date')
    search_fields = ('user__email',)
    raw_id_fields = ('user',)
    list_per_page = 25
    date_hierarchy = 'start_date'
    actions = ['activate_subscriptions', 'cancel_subscriptions']
    
    def status_badge(self, obj):
        colors = {
            'active': '#28a745',
            'cancelled': '#dc3545',
            'expired': '#6c757d',
            'pending': '#ffc107',
        }
        color = colors.get(obj.status, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 12px; text-transform: uppercase; font-size: 11px;">{}</span>',
            color, obj.status
        )
    status_badge.short_description = 'Status'
    
    def auto_renew_icon(self, obj):
        if obj.auto_renew:
            return format_html('<span style="color: #28a745; font-size: 18px;">🔄</span>')
        return format_html('<span style="color: #999;">—</span>')
    auto_renew_icon.short_description = 'Auto Renew'
    
    @admin.action(description='✓ Activate selected subscriptions')
    def activate_subscriptions(self, request, queryset):
        queryset.update(status='active')
        self.message_user(request, 'Subscriptions activated.')
    
    @admin.action(description='✗ Cancel selected subscriptions')
    def cancel_subscriptions(self, request, queryset):
        queryset.update(status='cancelled')
        self.message_user(request, 'Subscriptions cancelled.')


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('short_id', 'user', 'amount_display', 'status_badge', 'payment_method', 'created_at')
    list_filter = ('status', 'payment_method', 'currency', 'created_at')
    search_fields = ('user__email', 'transaction_id')
    raw_id_fields = ('user', 'subscription')
    readonly_fields = ('id', 'created_at')
    list_per_page = 25
    date_hierarchy = 'created_at'
    actions = ['mark_completed', 'mark_refunded']
    
    def short_id(self, obj):
        return format_html('<code>{}</code>', str(obj.id)[:8])
    short_id.short_description = 'ID'
    
    def amount_display(self, obj):
        return format_html('<strong style="color: #28a745;">{} {}</strong>', obj.currency, obj.amount)
    amount_display.short_description = 'Amount'
    amount_display.admin_order_field = 'amount'
    
    def status_badge(self, obj):
        colors = {
            'completed': '#28a745',
            'failed': '#dc3545',
            'pending': '#ffc107',
            'refunded': '#17a2b8',
        }
        icons = {
            'completed': '✓',
            'failed': '✗',
            'pending': '⏳',
            'refunded': '↩',
        }
        color = colors.get(obj.status, '#6c757d')
        icon = icons.get(obj.status, '')
        return format_html(
            '<span style="color: {};">{} {}</span>',
            color, icon, obj.status.title()
        )
    status_badge.short_description = 'Status'
    
    @admin.action(description='✓ Mark as Completed')
    def mark_completed(self, request, queryset):
        queryset.update(status='completed', completed_at=timezone.now())
        self.message_user(request, 'Payments marked as completed.')
    
    @admin.action(description='↩ Mark as Refunded')
    def mark_refunded(self, request, queryset):
        queryset.update(status='refunded')
        self.message_user(request, 'Payments marked as refunded.')


@admin.register(SpeechSession)
class SpeechSessionAdmin(admin.ModelAdmin):
    list_display = ('user_email', 'session_type', 'fluency_score_display', 'words_analyzed', 'duration_display', 'stuttering_summary', 'created_at')
    list_filter = ('session_type', 'stuttering_type', 'created_at')
    search_fields = ('user__email', 'transcription_text')
    raw_id_fields = ('user',)
    readonly_fields = ('created_at',)
    list_per_page = 25
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('📝 Session Info', {'fields': ('user', 'session_type', 'created_at')}),
        ('🎤 Audio & Transcription', {'fields': ('audio_file', 'transcription_text', 'transcription_data'), 'classes': ('collapse',)}),
        ('📊 Analysis Results', {'fields': ('fluency_score', 'words_analyzed', 'duration_seconds', 'analysis_data')}),
        ('🔍 Stuttering Breakdown', {'fields': ('stuttering_type', 'repetitions_count', 'prolongations_count', 'blocks_count', 'interjections_count')}),
        ('⚠️ Flagged Words', {'fields': ('flagged_words',), 'classes': ('collapse',)}),
    )

    def user_email(self, obj):
        return obj.user.email
    user_email.short_description = 'Email'
    user_email.admin_order_field = 'user__email'
    
    def fluency_score_display(self, obj):
        if obj.fluency_score is None:
            return format_html('<span style="color: #999;">—</span>')
        score = obj.fluency_score
        if score >= 80:
            color = '#28a745'
        elif score >= 60:
            color = '#ffc107'
        else:
            color = '#dc3545'
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 12px; font-weight: bold;">{}%</span>',
            color, int(score)
        )
    fluency_score_display.short_description = 'Fluency'
    fluency_score_display.admin_order_field = 'fluency_score'
    
    def duration_display(self, obj):
        mins = obj.duration_seconds // 60
        secs = obj.duration_seconds % 60
        if mins > 0:
            return format_html('{}m {}s', mins, secs)
        return format_html('{}s', secs)
    duration_display.short_description = 'Duration'
    
    def stuttering_summary(self, obj):
        total = obj.repetitions_count + obj.prolongations_count + obj.blocks_count + obj.interjections_count
        if total == 0:
            return format_html('<span style="color: #28a745;">Clean ✓</span>')
        parts = []
        if obj.repetitions_count:
            parts.append(f'R:{obj.repetitions_count}')
        if obj.prolongations_count:
            parts.append(f'P:{obj.prolongations_count}')
        if obj.blocks_count:
            parts.append(f'B:{obj.blocks_count}')
        if obj.interjections_count:
            parts.append(f'I:{obj.interjections_count}')
        return format_html('<span style="color: #666; font-size: 12px;">{}</span>', ' | '.join(parts))
    stuttering_summary.short_description = 'Stuttering'


admin.site.register(User, UserAdmin)
