from django.contrib import admin
from django.utils.html import format_html
from django.urls import path, reverse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import HttpResponse
from django.utils import timezone
import csv

from .models import (
    SiteSettings, Category, Product, Farmer,
    Order, OrderItem, SalesRecord, SalesItem, PaymentReceipt
)
from .forms import SalesRecordAdminForm, SalesItemInlineFormSet


# ─────────────────────────────────────────
# Inline admins
# ─────────────────────────────────────────

class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    fields = ('product', 'product_name', 'quantity', 'unit_price')
    readonly_fields = ('product_name', 'unit_price')


class SalesItemInline(admin.TabularInline):
    model = SalesItem
    extra = 1
    fields = ('product_name', 'quantity', 'unit_price')


# ─────────────────────────────────────────
# Model Admins
# ─────────────────────────────────────────

@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    list_display = ('company_name', 'email', 'phone_primary', 'phone_secondary', 'gst_number', 'updated_at')
    fieldsets = (
        ('Company Info', {'fields': ('company_name', 'tagline', 'gst_number')}),
        ('Contact', {'fields': ('email', 'phone_primary', 'phone_secondary')}),
        ('Location', {'fields': ('address', 'landmark', 'maps_embed_url')}),
    )

    def has_add_permission(self, request):
        return not SiteSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'icon')
    prepopulated_fields = {'slug': ('name',)}


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'price', 'stock', 'in_stock_badge', 'is_active', 'created_at')
    list_filter = ('category', 'is_active')
    search_fields = ('name', 'description')
    list_editable = ('price', 'stock', 'is_active')
    list_per_page = 20

    def in_stock_badge(self, obj):
        if obj.stock > 0:
            return format_html('<span style="color:green;font-weight:bold;">✔ In Stock ({})</span>', obj.stock)
        return format_html('<span style="color:red;font-weight:bold;">✘ Out of Stock</span>')
    in_stock_badge.short_description = 'Stock Status'


@admin.register(Farmer)
class FarmerAdmin(admin.ModelAdmin):
    list_display = ('profile_thumbnail', 'user', 'first_name_display', 'last_name_display', 
                    'email_display', 'phone', 'address', 'loyalty_badge', 'created_at')
    search_fields = ('user__username', 'user__first_name', 'user__last_name', 'user__email', 'phone')
    list_filter = ('created_at',)
    readonly_fields = ('profile_thumbnail_preview', 'loyalty_badge', 'created_at')
    fields = ('user', 'phone', 'address', 'profile_pic', 'profile_thumbnail_preview', 'loyalty_badge', 'created_at')

    def profile_thumbnail(self, obj):
        if obj.profile_pic_url:
            return format_html('<img src="{}" style="width: 40px; height: 40px; border-radius: 50%; object-fit: cover; border: 1.5px solid #C9962A;" />', obj.profile_pic_url)
        return format_html('<div style="width: 40px; height: 40px; border-radius: 50%; background: #fdf6e3; display: flex; align-items: center; justify-content: center; font-weight: bold; color: #7A0C2E; border: 1px dashed #7A0C2E;">👤</div>')
    profile_thumbnail.short_description = 'Photo'

    def profile_thumbnail_preview(self, obj):
        if obj.profile_pic_url:
            return format_html('<img src="{}" style="max-width: 150px; max-height: 150px; border-radius: 8px; border: 2px solid #C9962A;" />', obj.profile_pic_url)
        return format_html('<span style="color: #777;">No picture uploaded</span>')
    profile_thumbnail_preview.short_description = 'Profile Picture Preview'

    def loyalty_badge(self, obj):
        tier = obj.loyalty_tier
        return format_html(
            '<span style="background-color: {}; color: {}; padding: 4px 10px; border-radius: 12px; font-size: 11px; font-weight: bold; border: 1.5px solid rgba(0,0,0,0.15); display: inline-block;">{} {}</span>',
            tier['color'], tier['text_color'], tier['icon'], tier['name']
        )
    loyalty_badge.short_description = 'Loyalty Tier'

    def first_name_display(self, obj):
        return obj.user.first_name if obj.user else ''
    first_name_display.short_description = 'First Name'

    def last_name_display(self, obj):
        return obj.user.last_name if obj.user else ''
    last_name_display.short_description = 'Last Name'

    def email_display(self, obj):
        return obj.user.email if obj.user else ''
    email_display.short_description = 'Email'


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'customer_name', 'customer_phone', 'total_amount', 'status', 'status_badge',
                    'payment_mode', 'created_at', 'receipt_link')
    list_filter = ('status', 'payment_mode', 'created_at')
    search_fields = ('customer_name', 'customer_phone')
    list_editable = ('status',)
    inlines = [OrderItemInline]
    list_per_page = 25
    date_hierarchy = 'created_at'
    readonly_fields = ('total_amount', 'gst_amount', 'created_at', 'updated_at')

    def status_badge(self, obj):
        colors = {
            'pending': '#FFC107',
            'processing': '#17A2B8',
            'shipped': '#007BFF',
            'delivered': '#28A745',
            'cancelled': '#DC3545',
        }
        color = colors.get(obj.status, '#666')
        return format_html(
            '<span style="background:{};color:white;padding:3px 10px;border-radius:12px;font-size:12px;">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = 'Status'

    def receipt_link(self, obj):
        url = reverse('store:receipt_pdf', args=[obj.pk])
        return format_html('<a href="{}" target="_blank">📄 Receipt</a>', url)
    receipt_link.short_description = 'Receipt'


@admin.register(SalesRecord)
class SalesRecordAdmin(admin.ModelAdmin):
    list_display = ('id', 'customer_name', 'customer_phone', 'total_amount', 'payment_mode', 'date', 'receipt_link')
    list_filter = ('payment_mode', 'date')
    search_fields = ('customer_name', 'customer_phone')
    inlines = [SalesItemInline]
    date_hierarchy = 'date'
    list_per_page = 25

    def receipt_link(self, obj):
        url = reverse('store:sales_receipt_pdf', args=[obj.pk])
        return format_html('<a href="{}" target="_blank">📄 Receipt</a>', url)
    receipt_link.short_description = 'Receipt'

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('export-csv/', self.admin_site.admin_view(self.export_csv), name='salesrecord_export_csv'),
        ]
        return custom_urls + urls

    def export_csv(self, request):
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="sales_{timezone.now().date()}.csv"'
        writer = csv.writer(response)
        writer.writerow(['ID', 'Customer', 'Phone', 'Address', 'Total (₹)', 'GST (₹)', 'Payment Mode', 'Date'])
        for record in SalesRecord.objects.all():
            writer.writerow([
                record.pk, record.customer_name, record.customer_phone,
                record.customer_address, record.total_amount, record.gst_amount,
                record.payment_mode, record.date
            ])
        return response

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context['export_csv_url'] = 'export-csv/'
        return super().changelist_view(request, extra_context=extra_context)


@admin.register(PaymentReceipt)
class PaymentReceiptAdmin(admin.ModelAdmin):
    list_display = ('receipt_number', 'order', 'sales_record', 'generated_at')
    readonly_fields = ('receipt_number', 'generated_at')
    list_per_page = 25
