from .models import SiteSettings, Category, Inquiry


def site_settings(request):
    """Inject site settings into all templates."""
    return {'site_settings': SiteSettings.get_settings()}


def cart_count(request):
    """Inject cart item count into all templates."""
    cart = request.session.get('cart', {})
    count = sum(item.get('quantity', 0) for item in cart.values())
    return {'cart_count': count}


def categories_processor(request):
    """Inject categories into all templates for the navbar."""
    return {'categories': Category.objects.all()}


def unread_inquiries_processor(request):
    """Inject unread inquiry count for the admin sidebar badge."""
    try:
        count = Inquiry.objects.filter(is_read=False).count()
    except Exception:
        count = 0
    return {'unread_inquiries': count}
