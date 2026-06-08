from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.http import HttpResponse, JsonResponse, StreamingHttpResponse
import io
from django.core.paginator import Paginator
from django.db.models import Q, Sum
from django.views.decorators.cache import patch_cache_control
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.views.decorators.http import require_POST
import csv
import json

from .models import (
    Category, Product, ProductImage, Order, OrderItem,
    SalesRecord, SalesItem, SiteSettings, Farmer, DynamicMedia, ProductReview, Inquiry
)
from .forms import (
    FarmerRegisterForm, FarmerLoginForm,
    CheckoutForm, SiteSettingsForm, UserUpdateForm, FarmerProfileUpdateForm
)
from .utils import generate_order_receipt_pdf, generate_sales_receipt_pdf


# ══════════════════════════════════════════════════════════════
#  Helper
# ══════════════════════════════════════════════════════════════

def is_admin(user):
    return user.is_staff or user.is_superuser


def get_cart(request):
    """Return the cart dict from session."""
    return request.session.get('cart', {})


def save_cart(request, cart):
    request.session['cart'] = cart
    request.session.modified = True


# ══════════════════════════════════════════════════════════════
#  PUBLIC PAGES
# ══════════════════════════════════════════════════════════════

def home(request):
    categories = Category.objects.all()
    featured = Product.objects.filter(is_active=True, stock__gt=0)[:8]
    # Show recent customer reviews with a rating of 4 or 5 on homepage
    happy_reviews = ProductReview.objects.filter(
        rating__gte=4, message__gt=''
    ).select_related('user', 'product').order_by('-created_at')[:6]
    context = {
        'categories': categories,
        'featured_products': featured,
        'happy_reviews': happy_reviews,
        'page_title': 'Home',
    }
    return render(request, 'home.html', context)


def about(request):
    context = {
        'page_title': 'About Us',
    }
    return render(request, 'about.html', context)


def inquiry_form(request):
    """Public inquiry / contact form — linked from the homepage ticker."""
    inquiry_type = request.GET.get('type', '')  # pre-fill from ticker link
    submitted = False

    if request.method == 'POST':
        name         = request.POST.get('name', '').strip()
        phone        = request.POST.get('phone', '').strip()
        email        = request.POST.get('email', '').strip()
        inq_type     = request.POST.get('inquiry_type', Inquiry.TYPE_SUGGESTION)
        message      = request.POST.get('message', '').strip()

        errors = []
        if not name:    errors.append('Name is required.')
        if not phone:   errors.append('Phone number is required.')
        if not email:   errors.append('Email address is required.')
        if not message: errors.append('Message is required.')

        if errors:
            for e in errors:
                messages.error(request, e)
        else:
            Inquiry.objects.create(
                name=name, phone=phone, email=email,
                inquiry_type=inq_type, message=message
            )
            submitted = True
            messages.success(request, '✅ Your inquiry has been sent! We will get back to you soon.')

    context = {
        'page_title': 'Send Inquiry',
        'inquiry_types': Inquiry.TYPE_CHOICES,
        'preselect_type': inquiry_type,
        'submitted': submitted,
    }
    return render(request, 'inquiry.html', context)


@user_passes_test(is_admin)
def admin_inquiries(request):
    """Admin inbox — all customer inquiries."""
    filter_type = request.GET.get('type', '')
    filter_read = request.GET.get('read', '')

    qs = Inquiry.objects.all()
    if filter_type:
        qs = qs.filter(inquiry_type=filter_type)
    if filter_read == '0':
        qs = qs.filter(is_read=False)
    elif filter_read == '1':
        qs = qs.filter(is_read=True)

    unread_count = Inquiry.objects.filter(is_read=False).count()

    paginator = Paginator(qs, 20)
    page_obj  = paginator.get_page(request.GET.get('page'))

    context = {
        'page_title': 'Inquiry Inbox',
        'inquiries':  page_obj,
        'unread_count': unread_count,
        'inquiry_types': Inquiry.TYPE_CHOICES,
        'filter_type': filter_type,
        'filter_read': filter_read,
    }
    return render(request, 'admin_custom/inquiries.html', context)


@user_passes_test(is_admin)
@require_POST
def admin_inquiry_mark_read(request, pk):
    inq = get_object_or_404(Inquiry, pk=pk)
    inq.is_read = not inq.is_read
    inq.save()
    messages.success(request, f'Inquiry marked as {"read" if inq.is_read else "unread"}.')
    return redirect('store:admin_inquiries')


@user_passes_test(is_admin)
@require_POST
def admin_inquiry_delete(request, pk):
    inq = get_object_or_404(Inquiry, pk=pk)
    inq.delete()
    messages.info(request, 'Inquiry deleted.')
    return redirect('store:admin_inquiries')


def product_list(request):
    products = Product.objects.filter(is_active=True)
    categories = Category.objects.all()

    category_slug = request.GET.get('category', '')
    search_query = request.GET.get('q', '')

    if category_slug:
        products = products.filter(category__slug=category_slug)
    if search_query:
        products = products.filter(
            Q(name__icontains=search_query) | Q(description__icontains=search_query)
        )

    context = {
        'products': products,
        'categories': categories,
        'selected_category': category_slug,
        'search_query': search_query,
        'page_title': 'Products',
    }
    return render(request, 'products/product_list.html', context)


def product_detail(request, pk):
    product = get_object_or_404(Product, pk=pk, is_active=True)
    related = Product.objects.filter(category=product.category, is_active=True).exclude(pk=pk)[:4]
    context = {
        'product': product,
        'related_products': related,
        'page_title': product.name,
    }
    return render(request, 'products/product_detail.html', context)


def contact(request):
    settings = SiteSettings.get_settings()
    context = {
        'settings': settings,
        'page_title': 'Contact Us',
    }
    return render(request, 'contact.html', context)


# ══════════════════════════════════════════════════════════════
#  CART
# ══════════════════════════════════════════════════════════════

def cart_view(request):
    cart = get_cart(request)
    cart_items = []
    grand_total = 0

    for product_id, item in cart.items():
        try:
            product = Product.objects.get(pk=product_id)
            total = product.price * item['quantity']
            grand_total += total
            cart_items.append({
                'product': product,
                'quantity': item['quantity'],
                'total': total,
            })
        except Product.DoesNotExist:
            pass

    context = {
        'cart_items': cart_items,
        'grand_total': grand_total,
        'gst': round(float(grand_total) * 0.05, 2),
        'total_with_gst': round(float(grand_total) * 1.05, 2),
        'page_title': 'My Cart',
    }
    return render(request, 'cart.html', context)


@require_POST
def add_to_cart(request, pk):
    product = get_object_or_404(Product, pk=pk, is_active=True)
    cart = get_cart(request)

    quantity = int(request.POST.get('quantity', 1))
    if quantity < 1:
        quantity = 1

    key = str(pk)
    if key in cart:
        new_qty = cart[key]['quantity'] + quantity
        cart[key]['quantity'] = min(new_qty, product.stock)
    else:
        cart[key] = {'quantity': min(quantity, product.stock)}

    save_cart(request, cart)
    messages.success(request, f'✅ "{product.name}" added to cart!')

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        count = sum(i['quantity'] for i in cart.values())
        return JsonResponse({'success': True, 'cart_count': count})
    return redirect('store:cart')


@require_POST
def update_cart(request, pk):
    cart = get_cart(request)
    key = str(pk)
    quantity = int(request.POST.get('quantity', 1))

    if quantity <= 0:
        cart.pop(key, None)
        messages.info(request, 'Item removed from cart.')
    else:
        if key in cart:
            product = get_object_or_404(Product, pk=pk)
            cart[key]['quantity'] = min(quantity, product.stock)

    save_cart(request, cart)
    return redirect('store:cart')


@require_POST
def remove_from_cart(request, pk):
    cart = get_cart(request)
    cart.pop(str(pk), None)
    save_cart(request, cart)
    messages.info(request, 'Item removed from cart.')
    return redirect('store:cart')


# ══════════════════════════════════════════════════════════════
#  CHECKOUT & ORDERS
# ══════════════════════════════════════════════════════════════

@login_required
def checkout(request):
    cart = get_cart(request)
    if not cart:
        messages.warning(request, 'Your cart is empty!')
        return redirect('store:cart')

    cart_items = []
    subtotal = 0
    for product_id, item in cart.items():
        try:
            product = Product.objects.get(pk=product_id)
            total = product.price * item['quantity']
            subtotal += total
            cart_items.append({'product': product, 'quantity': item['quantity'], 'total': total})
        except Product.DoesNotExist:
            pass

    gst = round(float(subtotal) * 0.05, 2)
    grand_total = round(float(subtotal) + gst, 2)

    initial = {}
    if hasattr(request.user, 'farmer_profile'):
        fp = request.user.farmer_profile
        initial = {
            'customer_name': request.user.get_full_name(),
            'customer_phone': fp.phone,
            'customer_address': fp.address,
        }

    if request.method == 'POST':
        form = CheckoutForm(request.POST)
        if form.is_valid():
            # Validate stock
            out_of_stock = []
            for product_id, item in cart.items():
                try:
                    p = Product.objects.get(pk=product_id)
                    if p.stock < item['quantity']:
                        out_of_stock.append(p.name)
                except Product.DoesNotExist:
                    pass

            if out_of_stock:
                messages.error(request, f'Sorry, insufficient stock for: {", ".join(out_of_stock)}')
            else:
                order = form.save(commit=False)
                order.farmer = request.user
                order.total_amount = grand_total
                order.gst_amount = gst
                order.save()

                # Create OrderItems and deduct stock
                for product_id, item in cart.items():
                    try:
                        product = Product.objects.get(pk=product_id)
                        OrderItem.objects.create(
                            order=order,
                            product=product,
                            seller=product.seller,
                            product_name=product.name,
                            quantity=item['quantity'],
                            unit_price=product.price,
                        )
                        product.stock -= item['quantity']
                        product.save()
                    except Product.DoesNotExist:
                        pass

                # Clear cart
                request.session['cart'] = {}
                request.session.modified = True

                messages.success(request, f'🎉 Order #{order.pk} placed successfully!')
                return redirect('store:order_confirmation', pk=order.pk)
    else:
        form = CheckoutForm(initial=initial)

    context = {
        'form': form,
        'cart_items': cart_items,
        'subtotal': subtotal,
        'gst': gst,
        'grand_total': grand_total,
        'page_title': 'Checkout',
    }
    return render(request, 'checkout.html', context)


@login_required
def order_confirmation(request, pk):
    order = get_object_or_404(Order, pk=pk, farmer=request.user)
    context = {
        'order': order,
        'page_title': f'Order #{order.pk} Confirmed',
    }
    return render(request, 'order_confirmation.html', context)


@login_required
def my_orders(request):
    orders = Order.objects.filter(farmer=request.user).prefetch_related('items')
    context = {
        'orders': orders,
        'page_title': 'My Orders',
    }
    return render(request, 'orders/my_orders.html', context)


@login_required
@require_POST
def cancel_order(request, pk):
    order = get_object_or_404(Order, pk=pk, farmer=request.user)
    if order.status != Order.STATUS_PENDING:
        messages.error(request, "Only pending orders can be cancelled.")
        return redirect('store:my_orders')

    reason = request.POST.get('cancellation_reason', '').strip()
    if not reason:
        messages.error(request, "Cancellation reason is required.")
        return redirect('store:my_orders')

    order.status = Order.STATUS_CANCELLED
    order.cancellation_reason = reason
    order.save()

    # Restore stock
    for item in order.items.all():
        if item.product:
            item.product.stock += item.quantity
            item.product.save()

    messages.success(request, f"Order #{order.pk} has been successfully cancelled and stock has been restored.")
    return redirect('store:my_orders')


# ══════════════════════════════════════════════════════════════
#  PDF RECEIPTS
# ══════════════════════════════════════════════════════════════

@login_required
def receipt_pdf(request, pk):
    order = get_object_or_404(Order, pk=pk)
    # Farmer can only see their own; staff/admin can see all
    if not (request.user.is_staff or order.farmer == request.user):
        messages.error(request, 'Access denied.')
        return redirect('store:my_orders')

    buffer = generate_order_receipt_pdf(order)
    content = buffer.getvalue()
    buffer.close() # Explicitly close buffer to free memory
    response = HttpResponse(content, content_type='application/pdf')
    # Use a timestamp in filename to bust browser cache
    ts = timezone.now().strftime('%H%M%S')
    response['Content-Disposition'] = f'inline; filename="receipt_order_{pk}_{ts}.pdf"'
    patch_cache_control(response, no_cache=True, no_store=True, must_revalidate=True)
    return response


@user_passes_test(is_admin)
def sales_receipt_pdf(request, pk):
    sales_record = get_object_or_404(SalesRecord, pk=pk)
    buffer = generate_sales_receipt_pdf(sales_record)
    content = buffer.getvalue()
    buffer.close() # Explicitly close buffer to free memory
    response = HttpResponse(content, content_type='application/pdf')
    ts = timezone.now().strftime('%H%M%S')
    response['Content-Disposition'] = f'inline; filename="receipt_sale_{pk}_{ts}.pdf"'
    patch_cache_control(response, no_cache=True, no_store=True, must_revalidate=True)
    return response


# ══════════════════════════════════════════════════════════════
#  AUTH
# ══════════════════════════════════════════════════════════════

def farmer_register(request):
    if request.user.is_authenticated:
        return redirect('store:home')

    if request.method == 'POST':
        form = FarmerRegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, f'🌾 Welcome, {user.first_name}! Your account has been created.')
            return redirect('store:home')
    else:
        form = FarmerRegisterForm()

    return render(request, 'auth/register.html', {'form': form, 'page_title': 'Register'})


def farmer_login(request):
    if request.user.is_authenticated:
        return redirect('store:home')

    if request.method == 'POST':
        form = FarmerLoginForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            password = form.cleaned_data['password']
            user = authenticate(request, username=username, password=password)
            if user:
                login(request, user)
                messages.success(request, f'🌾 Welcome back, {user.first_name or user.username}!')
                next_url = request.GET.get('next', '')
                if next_url:
                    return redirect(next_url)
                if hasattr(user, 'seller_profile') and user.seller_profile.is_approved:
                    return redirect('store:seller_dashboard')
                return redirect('store:home')
            else:
                messages.error(request, '❌ Invalid username or password. Please try again.')
    else:
        form = FarmerLoginForm()

    return render(request, 'auth/login.html', {'form': form, 'page_title': 'Login'})


@csrf_exempt
def farmer_logout(request):
    logout(request)
    messages.info(request, 'You have been logged out.')
    return redirect('store:home')


@login_required
def my_account(request):
    # Ensure Farmer profile exists for the logged in user
    farmer_profile, created = Farmer.objects.get_or_create(
        user=request.user,
        defaults={'phone': '', 'address': ''}
    )

    if request.method == 'POST':
        # Check if they are deleting the profile picture
        if request.POST.get('delete_profile_pic') == 'on':
            farmer_profile.profile_pic = None
            farmer_profile.profile_pic_db = None
            farmer_profile.save()
            messages.success(request, 'Profile picture removed.')

        user_form = UserUpdateForm(request.POST, instance=request.user)
        profile_form = FarmerProfileUpdateForm(request.POST, request.FILES, instance=farmer_profile)

        if user_form.is_valid() and profile_form.is_valid():
            user_form.save()
            profile_form.save()
            messages.success(request, '✅ Your profile details have been updated successfully!')
            return redirect('store:my_account')
        else:
            messages.error(request, '❌ Please check the errors in the form.')
    else:
        user_form = UserUpdateForm(instance=request.user)
        profile_form = FarmerProfileUpdateForm(instance=farmer_profile)

    context = {
        'user_form': user_form,
        'profile_form': profile_form,
        'farmer': farmer_profile,
        'page_title': 'My Account',
    }
    return render(request, 'auth/my_account.html', context)


# ══════════════════════════════════════════════════════════════
#  CUSTOM ADMIN VIEWS
# ══════════════════════════════════════════════════════════════

@login_required
def admin_sales_list(request):
    """Custom admin view: list all sales records with export."""
    if not request.user.is_staff:
        return render(request, 'admin_custom/access_denied.html', status=403)
    sales = SalesRecord.objects.prefetch_related('items').all()

    # CSV export
    if request.GET.get('export') == 'csv':
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="sales_{timezone.now().date()}.csv"'
        writer = csv.writer(response)
        writer.writerow(['ID', 'Customer', 'Phone', 'Address', 'Total (₹)', 'GST (₹)', 'Payment Mode', 'Date'])
        for record in sales:
            writer.writerow([
                record.pk, record.customer_name, record.customer_phone,
                record.customer_address, record.total_amount, record.gst_amount,
                record.payment_mode, record.date
            ])
        return response

    # Filter
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    payment = request.GET.get('payment', '')

    if date_from:
        sales = sales.filter(date__gte=date_from)
    if date_to:
        sales = sales.filter(date__lte=date_to)
    if payment:
        sales = sales.filter(payment_mode=payment)

    total_revenue = sales.aggregate(total=Sum('total_amount'))['total'] or 0

    # Pagination
    paginator = Paginator(sales, 20) # 20 per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'sales': page_obj, # Use page_obj instead of full queryset
        'total_revenue': total_revenue,
        'payment_choices': SalesRecord.PAYMENT_CHOICES,
        'page_title': 'Sales Records',
    }
    return render(request, 'admin_custom/sales_list.html', context)


@login_required
def admin_sales_add(request):
    """Custom admin view: add a manual sales record."""
    if not request.user.is_staff:
        return render(request, 'admin_custom/access_denied.html', status=403)
    from .forms import SalesRecordAdminForm

    if request.method == 'POST':
        customer_name = request.POST.get('customer_name', '').strip()
        customer_phone = request.POST.get('customer_phone', '').strip()
        customer_address = request.POST.get('customer_address', '').strip()
        payment_mode = request.POST.get('payment_mode', 'Cash')
        date = request.POST.get('date') or timezone.now().date()
        notes = request.POST.get('notes', '')
        gst_rate = float(request.POST.get('gst_rate', 0)) / 100

        # Parse items
        product_names = request.POST.getlist('product_name[]')
        quantities = request.POST.getlist('quantity[]')
        unit_prices = request.POST.getlist('unit_price[]')

        items = []
        subtotal = 0
        for i in range(len(product_names)):
            try:
                pname = product_names[i].strip()
                qty = int(quantities[i])
                price = float(unit_prices[i])
                if pname and qty > 0 and price >= 0:
                    items.append({'name': pname, 'qty': qty, 'price': price})
                    subtotal += qty * price
            except (ValueError, IndexError):
                pass

        if not customer_name or not items:
            messages.error(request, 'Customer name and at least one item are required.')
        else:
            gst_amount = round(subtotal * gst_rate, 2)
            grand_total = round(subtotal + gst_amount, 2)

            record = SalesRecord.objects.create(
                customer_name=customer_name,
                customer_phone=customer_phone,
                customer_address=customer_address,
                payment_mode=payment_mode,
                date=date,
                notes=notes,
                total_amount=grand_total,
                gst_amount=gst_amount,
                added_by=request.user,
            )
            for item in items:
                SalesItem.objects.create(
                    sales_record=record,
                    product_name=item['name'],
                    quantity=item['qty'],
                    unit_price=item['price'],
                )
            messages.success(request, f'✅ Sales record #{record.pk} added for {customer_name}!')
            return redirect('store:admin_sales_list')

    products = Product.objects.filter(is_active=True)
    context = {
        'payment_choices': SalesRecord.PAYMENT_CHOICES,
        'products': products,
        'today': timezone.now().date(),
        'page_title': 'Add Sales Record',
    }
    return render(request, 'admin_custom/sales_add.html', context)


@login_required
def admin_site_settings(request):
    if not request.user.is_staff:
        return render(request, 'admin_custom/access_denied.html', status=403)
    settings_obj = SiteSettings.get_settings()
    if request.method == 'POST':
        form = SiteSettingsForm(request.POST, request.FILES, instance=settings_obj)
        if form.is_valid():
            settings_instance = form.save(commit=False)
            if 'promo_video' in request.FILES:
                settings_instance.promo_video = request.FILES['promo_video']
            settings_instance.save()
            messages.success(request, '✅ Site settings updated successfully!')
            return redirect('store:admin_settings')
    else:
        form = SiteSettingsForm(instance=settings_obj)

    context = {
        'form': form,
        'page_title': 'Site Settings',
    }
    return render(request, 'admin_custom/settings.html', context)


@login_required
def admin_products_list(request):
    """Custom admin view: list all products with search/filter."""
    if not request.user.is_staff:
        return render(request, 'admin_custom/access_denied.html', status=403)
    products = Product.objects.select_related('category').all()
    categories = Category.objects.all()

    category_slug = request.GET.get('category', '')
    search_query = request.GET.get('q', '')

    if category_slug:
        products = products.filter(category__slug=category_slug)
    if search_query:
        products = products.filter(
            Q(name__icontains=search_query) | Q(description__icontains=search_query)
        )

    # Pagination
    paginator = Paginator(products, 15)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'products': page_obj,
        'categories': categories,
        'current_category': category_slug,
        'search_query': search_query,
        'page_title': 'Products',
    }
    return render(request, 'admin_custom/products_list.html', context)


@login_required
def admin_products_add(request):
    """Custom admin view: add a new product."""
    if not request.user.is_staff:
        return render(request, 'admin_custom/access_denied.html', status=403)
    categories = Category.objects.all()
    form_data = None

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        description = request.POST.get('description', '').strip()
        category_id = request.POST.get('category', '')
        price = request.POST.get('price', '')
        stock = request.POST.get('stock', 0)
        is_active = request.POST.get('is_active') == 'on'
        image = request.FILES.get('image')

        errors = []
        if not name:
            errors.append('Product name is required.')
        if not description:
            errors.append('Description is required.')
        if not category_id:
            errors.append('Category is required.')
        try:
            price = float(price)
            if price < 0:
                errors.append('Price cannot be negative.')
        except (ValueError, TypeError):
            errors.append('Enter a valid price.')
        try:
            stock = int(stock)
        except (ValueError, TypeError):
            stock = 0

        if errors:
            for e in errors:
                messages.error(request, e)
        else:
            category = get_object_or_404(Category, pk=category_id)
            product = Product(
                name=name,
                description=description,
                category=category,
                price=price,
                stock=stock,
                is_active=is_active,
                video_url=request.POST.get('video_url', '').strip(),
            )
            if image:
                product.image = image
            video_file = request.FILES.get('video_file')
            if video_file:
                product.video_file = video_file
            product.save()

            # Handle gallery images (up to 10)
            gallery_images = request.FILES.getlist('gallery_images')
            for img in gallery_images[:10]:
                ProductImage.objects.create(product=product, image=img)

            messages.success(request, f'✅ Product "{name}" added successfully with gallery!')
            return redirect('store:admin_products_list')

    context = {
        'categories': categories,
        'form': form_data,
        'page_title': 'Add Product',
    }
    return render(request, 'admin_custom/products_add.html', context)


@login_required
def admin_products_edit(request, pk):
    """Custom admin view: edit an existing product."""
    if not request.user.is_staff:
        return render(request, 'admin_custom/access_denied.html', status=403)
    product = get_object_or_404(Product, pk=pk)
    categories = Category.objects.all()

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        description = request.POST.get('description', '').strip()
        category_id = request.POST.get('category', '')
        price = request.POST.get('price', '')
        stock = request.POST.get('stock', 0)
        is_active = request.POST.get('is_active') == 'on'
        image = request.FILES.get('image')
        clear_image = request.POST.get('clear_image') == 'on'

        errors = []
        if not name:
            errors.append('Product name is required.')
        if not description:
            errors.append('Description is required.')
        if not category_id:
            errors.append('Category is required.')
        try:
            price = float(price)
        except (ValueError, TypeError):
            errors.append('Enter a valid price.')
        try:
            stock = int(stock)
        except (ValueError, TypeError):
            stock = 0

        if errors:
            for e in errors:
                messages.error(request, e)
        else:
            product.name = name
            product.description = description
            product.category = get_object_or_404(Category, pk=category_id)
            product.price = price
            product.stock = stock
            product.is_active = is_active
            product.video_url = request.POST.get('video_url', '').strip()
            
            if clear_image:
                product.image = None
            if image:
                product.image = image
                
            if request.POST.get('clear_video') == 'on':
                product.video_file = None
            video_file = request.FILES.get('video_file')
            if video_file:
                product.video_file = video_file
                
            product.save()

            # Handle gallery deletions
            delete_gallery_ids = request.POST.getlist('delete_gallery')
            if delete_gallery_ids:
                ProductImage.objects.filter(pk__in=delete_gallery_ids, product=product).delete()

            # Handle new gallery images (up to 10 total)
            current_count = product.images.count()
            new_gallery_images = request.FILES.getlist('gallery_images')
            for img in new_gallery_images[:(10 - current_count)]:
                ProductImage.objects.create(product=product, image=img)

            messages.success(request, f'✅ Product "{name}" updated successfully!')
            return redirect('store:admin_products_list')

    context = {
        'product': product,
        'categories': categories,
        'form': None,
        'page_title': f'Edit — {product.name}',
    }
    return render(request, 'admin_custom/products_edit.html', context)


@login_required
def admin_products_delete(request, pk):
    """Custom admin view: delete a product."""
    if not request.user.is_staff:
        return render(request, 'admin_custom/access_denied.html', status=403)
    product = get_object_or_404(Product, pk=pk)
    if request.method == 'POST':
        name = product.name
        product.delete()
        messages.success(request, f'🗑️ Product "{name}" deleted.')
    return redirect('store:admin_products_list')


@login_required
def admin_dashboard(request):
    """Custom unified Admin Dashboard using standard UI."""
    if not request.user.is_staff:
        return render(request, 'admin_custom/access_denied.html', status=403)
    online_sales = Order.objects.aggregate(total=Sum('total_amount'))['total'] or 0
    walkin_sales = SalesRecord.objects.aggregate(total=Sum('total_amount'))['total'] or 0
    total_revenue = online_sales + walkin_sales

    total_orders = Order.objects.count()
    total_walkins = SalesRecord.objects.count()
    total_farmers = Farmer.objects.count()
    
    recent_orders = Order.objects.all().order_by('-created_at')[:5]
    unread_inquiries = Inquiry.objects.filter(is_read=False).count()

    context = {
        'page_title': 'Admin Dashboard',
        'total_revenue': total_revenue,
        'total_orders': total_orders,
        'total_walkins': total_walkins,
        'total_farmers': total_farmers,
        'recent_orders': recent_orders,
        'unread_inquiries': unread_inquiries,
    }
    return render(request, 'admin_custom/dashboard.html', context)


@login_required
def admin_users_list(request):
    """Custom admin view: list all registered farmer users with their profiles."""
    if not request.user.is_staff:
        return render(request, 'admin_custom/access_denied.html', status=403)

    search_query = request.GET.get('q', '').strip()
    tier_filter = request.GET.get('tier', '').strip()

    farmers = Farmer.objects.select_related('user', 'profile_pic_db').all().order_by('-created_at')

    if search_query:
        farmers = farmers.filter(
            Q(user__first_name__icontains=search_query) |
            Q(user__last_name__icontains=search_query) |
            Q(user__email__icontains=search_query) |
            Q(user__username__icontains=search_query) |
            Q(phone__icontains=search_query)
        )

    # Client-side tier filter applied in template using loyalty_tier property
    paginator = Paginator(farmers, 20)
    page_obj = paginator.get_page(request.GET.get('page'))

    context = {
        'page_title': 'Registered Users',
        'farmers': page_obj,
        'search_query': search_query,
        'tier_filter': tier_filter,
        'total_count': farmers.count(),
    }
    return render(request, 'admin_custom/users_list.html', context)


@login_required
def admin_orders_list(request):
    """Custom view for listing all online orders."""
    if not request.user.is_staff:
        return render(request, 'admin_custom/access_denied.html', status=403)
    orders = Order.objects.prefetch_related('items').all()
    
    status_filter = request.GET.get('status', '')
    if status_filter:
        orders = orders.filter(status=status_filter)
        
    # Pagination
    paginator = Paginator(orders, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
        
    context = {
        'orders': page_obj,
        'status_choices': Order.STATUS_CHOICES,
        'current_status': status_filter,
        'page_title': 'Online Orders',
    }
    return render(request, 'admin_custom/orders_list.html', context)


@user_passes_test(is_admin)
def admin_order_detail(request, pk):
    """Custom view for managing a specific online order."""
    order = get_object_or_404(Order, pk=pk)
    
    if request.method == 'POST':
        new_status = request.POST.get('status')
        if new_status in dict(Order.STATUS_CHOICES):
            order.status = new_status
            order.save()
            messages.success(request, f'Order #{order.pk} status updated to {order.get_status_display()}.')
            return redirect('store:admin_order_detail', pk=order.pk)
            
    context = {
        'order': order,
        'status_choices': Order.STATUS_CHOICES,
        'page_title': f'Manage Order #{order.pk}',
    }
    return render(request, 'admin_custom/order_detail.html', context)


# ══════════════════════════════════════════════════════════════
#  CATEGORY MANAGEMENT (ADMIN)
# ══════════════════════════════════════════════════════════════

@login_required
def admin_categories_list(request):
    """Custom view for listing all categories."""
    if not request.user.is_staff:
        return render(request, 'admin_custom/access_denied.html', status=403)
    categories = Category.objects.all()

    context = {
        'categories': categories,
        'page_title': 'Categories',
    }
    return render(request, 'admin_custom/categories_list.html', context)


@login_required
def admin_categories_add(request):
    """Custom admin view: add a new category."""
    if not request.user.is_staff:
        return render(request, 'admin_custom/access_denied.html', status=403)
    
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        from django.utils.text import slugify
        slug = request.POST.get('slug', '').strip() or slugify(name)
        description = request.POST.get('description', '').strip()
        icon = request.POST.get('icon', '📌').strip()

        if not name:
            messages.error(request, 'Category name is required.')
        elif Category.objects.filter(slug=slug).exists():
            messages.error(request, 'A category with this name/slug already exists.')
        else:
            Category.objects.create(name=name, slug=slug, description=description, icon=icon)
            messages.success(request, f'✅ Category "{name}" added successfully!')
            return redirect('store:admin_categories_list')

    context = {
        'page_title': 'Add Category',
    }
    return render(request, 'admin_custom/categories_add.html', context)


@login_required
def admin_categories_edit(request, pk):
    """Custom admin view: edit an existing category."""
    if not request.user.is_staff:
        return render(request, 'admin_custom/access_denied.html', status=403)
    
    category = get_object_or_404(Category, pk=pk)

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        slug = request.POST.get('slug', '').strip()
        description = request.POST.get('description', '').strip()
        icon = request.POST.get('icon', '').strip()

        if not name or not slug:
            messages.error(request, 'Category name and slug are required.')
        elif Category.objects.exclude(pk=pk).filter(slug=slug).exists():
            messages.error(request, 'A category with this slug already exists.')
        else:
            category.name = name
            category.slug = slug
            category.description = description
            category.icon = icon
            category.save()
            messages.success(request, f'✅ Category "{name}" updated successfully!')
            return redirect('store:admin_categories_list')

    context = {
        'category': category,
        'page_title': f'Edit Category — {category.name}',
    }
    return render(request, 'admin_custom/categories_edit.html', context)


@login_required
def admin_categories_delete(request, pk):
    """Custom admin view: delete a category."""
    if not request.user.is_staff:
        return render(request, 'admin_custom/access_denied.html', status=403)
    
    category = get_object_or_404(Category, pk=pk)
    if request.method == 'POST':
        name = category.name
        category.delete()
        messages.success(request, f'🗑️ Category "{name}" deleted.')
    return redirect('store:admin_categories_list')


def serve_db_media(request, file_id):
    """Serves media content stored in DynamicMedia model using streaming to save memory."""
    media = get_object_or_404(DynamicMedia, id=file_id)
    
    # Use StreamingHttpResponse with a generator or BytesIO for memory efficiency
    # This prevents loading the entire BinaryField into RAM at once for the response
    def file_iterator(file_content, chunk_size=8192):
        # file_content is a memoryview or bytes
        offset = 0
        while offset < len(file_content):
            yield file_content[offset:offset + chunk_size]
            offset += chunk_size

    response = StreamingHttpResponse(file_iterator(media.file_content), content_type=media.content_type)
    response['Content-Length'] = media.file_size
    # Cache for 30 days
    patch_cache_control(response, public=True, max_age=2592000)
    return response


# ══════════════════════════════════════════════════════════════
#  SELLER FEATURES
# ══════════════════════════════════════════════════════════════

from .models import SellerRequest, Seller
from .forms import SellerRequestForm, SellerLoginForm
from django.contrib.auth.models import User

def seller_login(request):
    if request.user.is_authenticated:
        return redirect('store:seller_dashboard')

    if request.method == 'POST':
        form = SellerLoginForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            password = form.cleaned_data['password']
            try:
                user_obj = User.objects.get(email=email)
                user = authenticate(request, username=user_obj.username, password=password)
            except User.DoesNotExist:
                user = None
                
            if user:
                login(request, user)
                messages.success(request, f'Welcome back, {user.first_name}!')
                return redirect('store:seller_dashboard')
            else:
                messages.error(request, '❌ Invalid email or password.')
    else:
        form = SellerLoginForm()
        
    return render(request, 'seller/seller_login.html', {'form': form, 'page_title': 'Seller Login'})

def seller_request(request):
    if request.user.is_authenticated and hasattr(request.user, 'seller_profile'):
        messages.info(request, "You are already a seller.")
        return redirect('store:seller_dashboard')
    
    if request.method == 'POST':
        form = SellerRequestForm(request.POST, user_is_authenticated=request.user.is_authenticated)
        if form.is_valid():
            req = form.save(commit=False)
            if request.user.is_authenticated:
                req.user = request.user
            else:
                # Create user
                password = form.cleaned_data.get('password')
                username = req.email
                if User.objects.filter(username=username).exists():
                    messages.error(request, "This email is already registered. Please log in first.")
                    return redirect('store:seller_login')
                user = User.objects.create_user(
                    username=username,
                    email=req.email,
                    password=password,
                    first_name=req.full_name
                )
                req.user = user
                from django.contrib.auth import login
                login(request, user)
            req.save()
            messages.success(request, "Your request to become a seller has been submitted.")
            return redirect('store:seller_dashboard')
    else:
        initial = {}
        if request.user.is_authenticated:
            initial = {'full_name': request.user.get_full_name(), 'email': request.user.email}
            if hasattr(request.user, 'farmer_profile'):
                initial['phone'] = request.user.farmer_profile.phone
                initial['address'] = request.user.farmer_profile.address
        form = SellerRequestForm(initial=initial, user_is_authenticated=request.user.is_authenticated)
        
    return render(request, 'seller/seller_request.html', {'form': form, 'page_title': 'Register as Seller'})


@login_required
def admin_seller_requests(request):
    if not request.user.is_staff:
        return render(request, 'admin_custom/access_denied.html', status=403)
    requests = SellerRequest.objects.all().order_by('-created_at')
    return render(request, 'admin_custom/seller_requests.html', {'requests': requests, 'page_title': 'Seller Requests'})

@login_required
def admin_seller_approve(request, pk):
    if not request.user.is_staff:
        return render(request, 'admin_custom/access_denied.html', status=403)
    req = get_object_or_404(SellerRequest, pk=pk)
    if req.status == SellerRequest.STATUS_PENDING:
        req.status = SellerRequest.STATUS_APPROVED
        req.save()
        
        user = req.user
        if not user:
            from django.contrib.auth.models import User
            username = req.phone
            if User.objects.filter(username=username).exists():
                username = f"{req.phone}_{req.pk}"
            user = User.objects.create_user(
                username=username,
                email=req.email,
                password=req.phone,
                first_name=req.full_name
            )
            req.user = user
            req.save()
            
        if not hasattr(user, 'seller_profile'):
            Seller.objects.create(
                user=user,
                business_name=req.business_name,
                phone=req.phone,
                address=req.address,
                is_approved=True
            )
        messages.success(request, f"Seller request for {req.business_name} approved.")
    return redirect('store:admin_seller_requests')

@login_required
def admin_seller_reject(request, pk):
    if not request.user.is_staff:
        return render(request, 'admin_custom/access_denied.html', status=403)
    req = get_object_or_404(SellerRequest, pk=pk)
    if req.status == SellerRequest.STATUS_PENDING:
        req.status = SellerRequest.STATUS_REJECTED
        req.save()
        messages.success(request, f"Seller request for {req.business_name} rejected.")
    return redirect('store:admin_seller_requests')

@login_required
def admin_sellers_list(request):
    if not request.user.is_staff:
        return render(request, 'admin_custom/access_denied.html', status=403)
    sellers = Seller.objects.filter(is_approved=True).order_by('-created_at')
    return render(request, 'admin_custom/sellers_list.html', {'sellers': sellers, 'page_title': 'Approved Sellers'})

@login_required
def admin_seller_edit(request, pk):
    if not request.user.is_staff:
        return render(request, 'admin_custom/access_denied.html', status=403)
    seller = get_object_or_404(Seller, pk=pk)
    target_user = seller.user
    
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        is_active = request.POST.get('is_active') == 'on'
        is_blacklisted = request.POST.get('is_blacklisted') == 'on'
        
        if email:
            target_user.email = email
            target_user.username = email
        if password:
            target_user.set_password(password)
            
        target_user.is_active = is_active
        target_user.save()
        
        seller.is_blacklisted = is_blacklisted
        seller.save()
        messages.success(request, f"Seller {seller.business_name} updated successfully.")
        return redirect('store:admin_sellers_list')
        
    return render(request, 'admin_custom/seller_edit.html', {'seller': seller, 'target_user': target_user, 'page_title': 'Edit Seller'})

@login_required
def admin_seller_remove(request, pk):
    if not request.user.is_staff:
        return render(request, 'admin_custom/access_denied.html', status=403)
    seller = get_object_or_404(Seller, pk=pk)
    if request.method == 'POST':
        seller.user.delete() # Cascades
        messages.success(request, f"Seller {seller.business_name} removed.")
    return redirect('store:admin_sellers_list')

@login_required
def admin_seller_dashboard_view(request, pk):
    if not request.user.is_staff:
        return render(request, 'admin_custom/access_denied.html', status=403)
    seller = get_object_or_404(Seller, pk=pk)
    products_count = seller.products.count()
    from .models import OrderItem
    from django.db.models import Sum, F
    orders_count = OrderItem.objects.filter(seller=seller).values('order').distinct().count()
    total_sales = OrderItem.objects.filter(seller=seller).annotate(t=F('unit_price')*F('quantity')).aggregate(total=Sum('t'))['total'] or 0
    
    return render(request, 'seller/dashboard.html', {
        'seller': seller, 'products_count': products_count, 
        'orders_count': orders_count, 'total_sales': total_sales,
        'page_title': f'Dashboard: {seller.business_name}',
        'is_admin_view': True
    })

def get_seller(user):
    if hasattr(user, 'seller_profile') and user.seller_profile.is_approved:
        return user.seller_profile
    return None

@login_required
def seller_dashboard(request):
    seller = get_seller(request.user)
    if not seller:
        pending_req = SellerRequest.objects.filter(user=request.user, status=SellerRequest.STATUS_PENDING).first()
        if pending_req:
            return render(request, 'seller/pending_approval.html', {'page_title': 'Pending Approval'})
        messages.error(request, "Access denied. You are not an approved seller.")
        return redirect('store:seller_request')
    
    products_count = seller.products.count()
    orders_count = OrderItem.objects.filter(seller=seller).values('order').distinct().count()
    from django.db.models import F
    total_sales = OrderItem.objects.filter(seller=seller).annotate(t=F('unit_price')*F('quantity')).aggregate(total=Sum('t'))['total'] or 0
    
    return render(request, 'seller/dashboard.html', {
        'seller': seller, 'products_count': products_count, 
        'orders_count': orders_count, 'total_sales': total_sales,
        'page_title': 'Seller Dashboard'
    })

@login_required
def seller_products(request):
    seller = get_seller(request.user)
    if not seller: return redirect('store:home')
    
    products = seller.products.all()
    return render(request, 'seller/products.html', {'products': products, 'page_title': 'My Products'})

@login_required
def seller_product_add(request):
    seller = get_seller(request.user)
    if not seller: return redirect('store:home')
    
    categories = Category.objects.all()
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        description = request.POST.get('description', '').strip()
        category_id = request.POST.get('category', '')
        price = request.POST.get('price', '')
        stock = request.POST.get('stock', 0)
        is_active = request.POST.get('is_active') == 'on'
        image = request.FILES.get('image')
        
        if name and description and category_id and price:
            category = get_object_or_404(Category, pk=category_id)
            product = Product(
                name=name, description=description, category=category,
                price=price, stock=stock, is_active=is_active, seller=seller
            )
            if image: product.image = image
            video_file = request.FILES.get('video_file')
            if video_file: product.video_file = video_file
            product.save()
            
            from .models import ProductImage
            for g_img in request.FILES.getlist('gallery_images'):
                ProductImage.objects.create(product=product, image=g_img)
                
            messages.success(request, "Product added successfully.")
            return redirect('store:seller_products')
        else:
            messages.error(request, "Please fill all required fields.")
            
    return render(request, 'seller/product_add.html', {'categories': categories, 'page_title': 'Add Product'})

@login_required
def seller_product_edit(request, pk):
    seller = get_seller(request.user)
    if not seller: return redirect('store:home')
    
    product = get_object_or_404(Product, pk=pk, seller=seller)
    categories = Category.objects.all()
    
    if request.method == 'POST':
        product.name = request.POST.get('name', '').strip()
        product.description = request.POST.get('description', '').strip()
        product.category = get_object_or_404(Category, pk=request.POST.get('category'))
        product.price = request.POST.get('price', 0)
        product.stock = request.POST.get('stock', 0)
        product.is_active = request.POST.get('is_active') == 'on'
        
        if request.POST.get('clear_image') == 'on':
            product.image = None
        elif request.FILES.get('image'):
            product.image = request.FILES.get('image')
            
        if request.FILES.get('video_file'):
            product.video_file = request.FILES.get('video_file')
            
        product.save()
        
        from .models import ProductImage
        for g_img in request.FILES.getlist('gallery_images'):
            ProductImage.objects.create(product=product, image=g_img)
            
        messages.success(request, "Product updated.")
        return redirect('store:seller_products')
        
    return render(request, 'seller/product_edit.html', {'product': product, 'categories': categories, 'page_title': 'Edit Product'})

@login_required
def seller_product_delete(request, pk):
    seller = get_seller(request.user)
    if not seller: return redirect('store:home')
    
    product = get_object_or_404(Product, pk=pk, seller=seller)
    if request.method == 'POST':
        product.delete()
        messages.success(request, "Product deleted.")
    return redirect('store:seller_products')

@login_required
def seller_orders(request):
    seller = get_seller(request.user)
    if not seller: return redirect('store:home')
    
    orders = Order.objects.filter(items__seller=seller).distinct().order_by('-created_at')
    return render(request, 'seller/orders.html', {'orders': orders, 'page_title': 'My Orders'})

@login_required
def seller_sales_list(request):
    seller = get_seller(request.user)
    if not seller: return redirect('store:home')
    
    sales = SalesRecord.objects.filter(seller=seller).prefetch_related('items').order_by('-created_at')
    return render(request, 'seller/sales_list.html', {'sales': sales, 'page_title': 'Manual Sales'})

@login_required
def seller_sales_add(request):
    seller = get_seller(request.user)
    if not seller: return redirect('store:home')
    
    products = Product.objects.filter(seller=seller, is_active=True)
    
    if request.method == 'POST':
        customer_name = request.POST.get('customer_name', '').strip()
        customer_phone = request.POST.get('customer_phone', '').strip()
        product_id = request.POST.get('product')
        quantity = int(request.POST.get('quantity', 1))
        payment_mode = request.POST.get('payment_mode', 'Cash')
        
        if not customer_name or not product_id:
            messages.error(request, 'Customer name and product are required.')
        else:
            product = get_object_or_404(Product, pk=product_id, seller=seller)
            total = product.price * quantity
            
            sale = SalesRecord.objects.create(
                customer_name=customer_name,
                customer_phone=customer_phone,
                total_amount=total,
                seller=seller,
                added_by=request.user,
                payment_mode=payment_mode
            )
            SalesItem.objects.create(
                sales_record=sale,
                product_name=product.name,
                quantity=quantity,
                unit_price=product.price
            )
            if product.stock >= quantity:
                product.stock -= quantity
                product.save()
                
            from .utils import generate_sales_receipt_pdf
            generate_sales_receipt_pdf(sale)
                
            messages.success(request, "Manual sale recorded and receipt generated.")
            return redirect('store:seller_sales_list')
            
    return render(request, 'seller/sales_add.html', {'products': products, 'page_title': 'Record Walk-in Sale'})

@login_required
def product_review_add(request, order_item_id):
    order_item = get_object_or_404(OrderItem, pk=order_item_id, order__farmer=request.user, order__status=Order.STATUS_DELIVERED)
    if not order_item.product:
        messages.error(request, "Product is no longer available.")
        return redirect('store:my_orders')
        
    if request.method == 'POST':
        rating = int(request.POST.get('rating', 5))
        message = request.POST.get('message', '').strip()
        image = request.FILES.get('image')
        
        from .models import ProductReview
        ProductReview.objects.create(
            product=order_item.product,
            user=request.user,
            rating=rating,
            message=message,
            image=image
        )
        messages.success(request, "Thank you for your review!")
        return redirect('store:my_orders')
        
    return render(request, 'product_review_add.html', {'order_item': order_item, 'page_title': 'Review Product'})

@login_required
def seller_order_detail(request, pk):
    seller = get_seller(request.user)
    if not seller: return redirect('store:home')
    
    order = get_object_or_404(Order, pk=pk, items__seller=seller)
    items = order.items.filter(seller=seller)
    
    return render(request, 'seller/order_detail.html', {'order': order, 'items': items, 'page_title': f'Order #{order.pk}'})

@login_required
def seller_report(request):
    seller = get_seller(request.user)
    if not seller: return redirect('store:home')
    
    now = timezone.now()
    items = OrderItem.objects.filter(seller=seller, order__created_at__year=now.year, order__created_at__month=now.month)
    
    if request.GET.get('export') == 'csv':
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="sales_report_{now.strftime("%Y_%m")}.csv"'
        writer = csv.writer(response)
        writer.writerow(['Order ID', 'Date', 'Product', 'Quantity', 'Unit Price', 'Total'])
        for item in items:
            writer.writerow([item.order.pk, item.order.created_at.date(), item.product_name, item.quantity, item.unit_price, item.total])
        return response
        
    return render(request, 'seller/report.html', {'items': items, 'page_title': 'Monthly Report'})


# ── Chatbot Views ──────────────────────────────────
import json
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import get_object_or_404
from .models import ChatSession, ChatMessage
from .utils import get_bot_response, generate_chat_report_pdf

@csrf_exempt
def chatbot_api(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            user_text = data.get('message', '').strip()
            session_id = data.get('session_id')
            
            if not user_text:
                return JsonResponse({'error': 'Message cannot be empty'}, status=400)
                
            # Get or create session
            if session_id:
                try:
                    chat_session = ChatSession.objects.get(session_id=session_id)
                except ChatSession.DoesNotExist:
                    chat_session = ChatSession.objects.create(
                        user=request.user if request.user.is_authenticated else None
                    )
            else:
                chat_session = ChatSession.objects.create(
                    user=request.user if request.user.is_authenticated else None
                )
                
            # Save user message
            ChatMessage.objects.create(session=chat_session, role='user', text=user_text)
            
            # Generate bot response
            bot_text = get_bot_response(user_text)
            
            # Save bot message
            ChatMessage.objects.create(session=chat_session, role='bot', text=bot_text)
            
            return JsonResponse({
                'session_id': str(chat_session.session_id),
                'response': bot_text
            })
            
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
            
    return JsonResponse({'error': 'Invalid request'}, status=400)


def chat_report_pdf(request, session_id):
    """Generates and downloads the PDF report for a chat session."""
    chat_session = get_object_or_404(ChatSession, session_id=session_id)
    
    # Generate PDF
    pdf_buffer = generate_chat_report_pdf(chat_session)
    
    # Return as HTTP response
    response = HttpResponse(pdf_buffer.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="chat_report_{session_id}.pdf"'
    
    return response
