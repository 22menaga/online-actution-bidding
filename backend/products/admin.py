from django.contrib import admin
from .models import AIEstimate, Category, Product, ProductImage


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'seller', 'status', 'starting_price')
    list_filter = ('status', 'category')
    search_fields = ('name', 'seller__username')
    actions = ['approve']

    @admin.action(description='Approve selected pending products')
    def approve(self, request, queryset):
        queryset.filter(status='PENDING_APPROVAL').update(status='APPROVED')


admin.site.register([Category, ProductImage, AIEstimate])
