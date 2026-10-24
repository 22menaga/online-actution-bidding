from django.contrib import admin
from .models import User,SellerProfile,BuyerProfile,SellerVerification
admin.site.register([User,BuyerProfile])


@admin.register(SellerProfile)
class SellerProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'business_name', 'approved', 'verified')
    list_filter = ('approved',)
    actions = ['approve']

    @admin.action(description='Approve selected sellers')
    def approve(self, request, queryset):
        queryset.update(approved=True, verified=True)


admin.site.register(SellerVerification)
