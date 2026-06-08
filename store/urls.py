from django.urls import path
from . import views

app_name = 'store'

urlpatterns = [
    # Public
    path('', views.home, name='home'),
    path('products/', views.product_list, name='product_list'),
    path('products/<int:pk>/', views.product_detail, name='product_detail'),
    path('contact/', views.contact, name='contact'),
    path('about/', views.about, name='about'),
    path('inquiry/', views.inquiry_form, name='inquiry'),
    path('seller-request/', views.seller_request, name='seller_request'),
    path('seller-login/', views.seller_login, name='seller_login'),

    # Cart
    path('cart/', views.cart_view, name='cart'),
    path('cart/add/<int:pk>/', views.add_to_cart, name='add_to_cart'),
    path('cart/update/<int:pk>/', views.update_cart, name='update_cart'),
    path('cart/remove/<int:pk>/', views.remove_from_cart, name='remove_from_cart'),

    # Checkout & Orders
    path('checkout/', views.checkout, name='checkout'),
    path('orders/confirmation/<int:pk>/', views.order_confirmation, name='order_confirmation'),
    path('orders/', views.my_orders, name='my_orders'),
    path('orders/<int:pk>/cancel/', views.cancel_order, name='cancel_order'),

    # PDF Receipts
    path('receipt/<int:pk>/pdf/', views.receipt_pdf, name='receipt_pdf'),
    path('receipt/sales/<int:pk>/pdf/', views.sales_receipt_pdf, name='sales_receipt_pdf'),

    # Auth
    path('register/', views.farmer_register, name='register'),
    path('login/', views.farmer_login, name='login'),
    path('logout/', views.farmer_logout, name='logout'),
    path('account/', views.my_account, name='my_account'),

    # Custom Admin Views
    path('dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('dashboard/users/', views.admin_users_list, name='admin_users_list'),
    path('dashboard/orders/', views.admin_orders_list, name='admin_orders_list'),
    path('dashboard/orders/<int:pk>/', views.admin_order_detail, name='admin_order_detail'),
    path('dashboard/sales/', views.admin_sales_list, name='admin_sales_list'),
    path('dashboard/sales/add/', views.admin_sales_add, name='admin_sales_add'),
    path('dashboard/settings/', views.admin_site_settings, name='admin_settings'),
    path('dashboard/inquiries/', views.admin_inquiries, name='admin_inquiries'),
    path('dashboard/inquiries/<int:pk>/read/', views.admin_inquiry_mark_read, name='admin_inquiry_mark_read'),
    path('dashboard/inquiries/<int:pk>/delete/', views.admin_inquiry_delete, name='admin_inquiry_delete'),
    
    # Seller Requests (Admin)
    path('dashboard/seller-requests/', views.admin_seller_requests, name='admin_seller_requests'),
    path('dashboard/seller-requests/<int:pk>/approve/', views.admin_seller_approve, name='admin_seller_approve'),
    path('dashboard/seller-requests/<int:pk>/reject/', views.admin_seller_reject, name='admin_seller_reject'),
    
    path('dashboard/sellers/', views.admin_sellers_list, name='admin_sellers_list'),
    path('dashboard/sellers/<int:pk>/edit/', views.admin_seller_edit, name='admin_seller_edit'),
    path('dashboard/sellers/<int:pk>/remove/', views.admin_seller_remove, name='admin_seller_remove'),
    path('dashboard/sellers/<int:pk>/dashboard/', views.admin_seller_dashboard_view, name='admin_seller_dashboard_view'),
    
    # Seller Dashboard
    path('seller/dashboard/', views.seller_dashboard, name='seller_dashboard'),
    path('seller/products/', views.seller_products, name='seller_products'),
    path('seller/products/add/', views.seller_product_add, name='seller_product_add'),
    path('seller/products/<int:pk>/edit/', views.seller_product_edit, name='seller_product_edit'),
    path('seller/products/<int:pk>/delete/', views.seller_product_delete, name='seller_product_delete'),
    path('seller/orders/', views.seller_orders, name='seller_orders'),
    path('seller/orders/<int:pk>/', views.seller_order_detail, name='seller_order_detail'),
    path('seller/sales/', views.seller_sales_list, name='seller_sales_list'),
    path('seller/sales/add/', views.seller_sales_add, name='seller_sales_add'),
    path('seller/report/', views.seller_report, name='seller_report'),
    
    # Reviews
    path('product/<int:order_item_id>/review/', views.product_review_add, name='product_review_add'),

    # Category Management (Admin)
    path('dashboard/categories/', views.admin_categories_list, name='admin_categories_list'),
    path('dashboard/categories/add/', views.admin_categories_add, name='admin_categories_add'),
    path('dashboard/categories/<int:pk>/edit/', views.admin_categories_edit, name='admin_categories_edit'),
    path('dashboard/categories/<int:pk>/delete/', views.admin_categories_delete, name='admin_categories_delete'),

    # Product Management (Admin)
    path('dashboard/products/', views.admin_products_list, name='admin_products_list'),
    path('dashboard/products/add/', views.admin_products_add, name='admin_products_add'),
    path('dashboard/products/<int:pk>/edit/', views.admin_products_edit, name='admin_products_edit'),
    path('dashboard/products/<int:pk>/delete/', views.admin_products_delete, name='admin_products_delete'),

    # Dynamic Media
    path('media/db/<uuid:file_id>/', views.serve_db_media, name='serve_db_media'),

    # Chatbot
    path('chat/api/', views.chatbot_api, name='chatbot_api'),
    path('chat/report/<str:session_id>/pdf/', views.chat_report_pdf, name='chat_report_pdf'),
]
