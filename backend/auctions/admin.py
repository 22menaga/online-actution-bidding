from django.contrib import admin
from .models import Auction, ScheduleRequest, Watch


@admin.register(Auction)
class AuctionAdmin(admin.ModelAdmin):
    list_display = ('id', 'product', 'seller', 'status', 'current_highest_bid', 'bid_count', 'end_at')
    list_filter = ('status',)
    search_fields = ('product__name', 'seller__username')
    actions = ['approve']

    @admin.action(description='Approve pending auctions that already have start/end times set (-> SCHEDULED)')
    def approve(self, request, queryset):
        for a in queryset.filter(status='PENDING_APPROVAL', start_at__isnull=False, end_at__isnull=False).select_related('product'):
            a.status = 'SCHEDULED'; a.save(update_fields=['status', 'updated_at'])
            a.product.status = 'AUCTION'; a.product.save(update_fields=['status', 'updated_at'])


admin.site.register([Watch, ScheduleRequest])
