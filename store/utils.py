"""
PDF Receipt Generator using ReportLab
for Jay Bn Poultry Farm and Feeding Point
"""

import os
from io import BytesIO
from django.conf import settings as django_settings
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm, cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable, Image
)
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from .models import SiteSettings, PaymentReceipt

# ── Font Registration (for Rupee Symbol support) ──────
def register_fonts():
    # Try common paths for fonts that support Rupee (₹)
    font_paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",         # Linux
        "/usr/share/fonts/dejavu/DejaVuSans.ttf",                 # Linux (alt)
        "C:\\Windows\\Fonts\\DejaVuSans.ttf",                     # Windows (if installed)
        "C:\\Windows\\Fonts\\SegoeUI.ttf",                        # Windows Segoe UI
        "C:\\Windows\\Fonts\\arial.ttf",                          # Windows Arial
    ]
    for path in font_paths:
        if os.path.exists(path):
            name = os.path.splitext(os.path.basename(path))[0]
            try:
                pdfmetrics.registerFont(TTFont(name, path))
                return name
            except:
                pass
    return 'Helvetica' # Fallback

UNICODE_FONT = register_fonts()


# ── Color palette (Mithila White Gold Premium) ──────
GOLD = colors.HexColor('#C9962A')
GOLD_LIGHT = colors.HexColor('#E8B84B')
CRIMSON = colors.HexColor('#7A0C2E')
CRIMSON_DARK = colors.HexColor('#3D0617')
IVORY = colors.HexColor('#FDF6E3')
DARK = colors.HexColor('#120609')
TEXT_DARK = colors.HexColor('#120609')
TEXT_LIGHT = colors.HexColor('#FDF6E3')
BORDER_COLOR = colors.HexColor('#C9962A')
STRIPE_COLOR = colors.HexColor('#FFFDF9') # Very light ivory for rows


def _get_or_create_receipt(order=None, sales_record=None):
    if order:
        receipt, _ = PaymentReceipt.objects.get_or_create(order=order)
    else:
        receipt, _ = PaymentReceipt.objects.get_or_create(sales_record=sales_record)
    return receipt


def generate_order_receipt_pdf(order):
    """Generate a PDF receipt for an online Order."""
    receipt = _get_or_create_receipt(order=order)
    settings = SiteSettings.get_settings()

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4,
                            topMargin=1.5*cm, bottomMargin=2*cm,
                            leftMargin=2*cm, rightMargin=2*cm)

    items_data = [['Product', 'Qty', 'Rate (₹)', 'Total (₹)']]
    for item in order.items.all():
        items_data.append([
            item.product_name,
            str(item.quantity),
            f'₹{item.unit_price:,.2f}',
            f'₹{item.total:,.2f}'
        ])

    story = _build_receipt_story(
        doc=doc,
        settings=settings,
        receipt=receipt,
        customer_name=order.customer_name,
        customer_phone=order.customer_phone,
        customer_address=order.customer_address,
        date=order.created_at.date(),
        items_data=items_data,
        subtotal=order.subtotal,
        gst_amount=order.gst_amount,
        grand_total=order.total_amount,
        payment_mode=order.payment_mode,
    )

    doc.build(story, onFirstPage=_draw_watermark, onLaterPages=_draw_watermark)
    buffer.seek(0)
    return buffer


def generate_sales_receipt_pdf(sales_record):
    """Generate a PDF receipt for a manual SalesRecord."""
    receipt = _get_or_create_receipt(sales_record=sales_record)
    settings = SiteSettings.get_settings()

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4,
                            topMargin=1.5*cm, bottomMargin=2*cm,
                            leftMargin=2*cm, rightMargin=2*cm)

    items_data = [['Product', 'Qty', 'Rate (₹)', 'Total (₹)']]
    for item in sales_record.items.all():
        items_data.append([
            item.product_name,
            str(item.quantity),
            f'₹{item.unit_price:,.2f}',
            f'₹{item.total:,.2f}'
        ])

    story = _build_receipt_story(
        doc=doc,
        settings=settings,
        receipt=receipt,
        customer_name=sales_record.customer_name,
        customer_phone=sales_record.customer_phone,
        customer_address=sales_record.customer_address,
        date=sales_record.date,
        items_data=items_data,
        subtotal=sales_record.subtotal,
        gst_amount=sales_record.gst_amount,
        grand_total=sales_record.total_amount,
        payment_mode=sales_record.payment_mode,
    )

    doc.build(story, onFirstPage=_draw_watermark, onLaterPages=_draw_watermark)
    buffer.seek(0)
    return buffer


def _draw_watermark(canvas, doc):
    """Draw a subtle watermark in the background."""
    canvas.saveState()
    canvas.setFont('Times-Bold', 60)
    canvas.setStrokeColor(GOLD)
    canvas.setFillAlpha(0.04)
    canvas.translate(A4[0]/2, A4[1]/2)
    canvas.rotate(45)
    canvas.drawCentredString(0, 0, "MITHILA WHITE GOLD")
    canvas.restoreState()


def _build_receipt_story(doc, settings, receipt, customer_name, customer_phone,
                          customer_address, date, items_data,
                          subtotal, gst_amount, grand_total, payment_mode):
    """Build the premium platypus story for the receipt PDF."""
    styles = getSampleStyleSheet()

    # Custom premium styles
    title_style = ParagraphStyle('Title', parent=styles['Heading1'],
                                  fontSize=26, textColor=CRIMSON,
                                  spaceAfter=4, alignment=TA_LEFT, fontName='Times-Bold')
    
    header_info_style = ParagraphStyle('HeaderInfo', parent=styles['Normal'],
                                        fontSize=10, alignment=TA_RIGHT, spaceAfter=2, textColor=DARK, leading=12)
    
    label_style = ParagraphStyle('Label', parent=styles['Normal'],
                                  fontSize=10, textColor=colors.grey, leading=12)
    
    invoice_title_style = ParagraphStyle('InvTitle', parent=styles['Normal'],
                                          fontSize=20, fontName='Times-Bold', textColor=CRIMSON)
    
    footer_style = ParagraphStyle('Footer', parent=styles['Normal'],
                                   fontSize=10, textColor=colors.grey,
                                   alignment=TA_CENTER)

    story = []

    # ── Decorative Top Border ───────────────────
    story.append(HRFlowable(width="100%", thickness=3, color=GOLD, spaceAfter=10))

    # ── Header Layout ───────────────────────────
    logo_path = os.path.join(django_settings.BASE_DIR, 'static', 'img', 'logo.png')
    logo = None
    if os.path.exists(logo_path):
        logo = Image(logo_path, width=2.4*cm, height=2.4*cm)

    title_text = settings.company_name.upper()
    custom_title_style = ParagraphStyle('CustomTitle', parent=styles['Heading1'],
                                         fontSize=22, textColor=CRIMSON,
                                         alignment=TA_LEFT, fontName='Times-Bold')

    header_content_info = [
        Paragraph(f'<b>GSTIN: {settings.gst_number}</b>', header_info_style),
        Paragraph(settings.address, header_info_style),
        Paragraph(f'Phone: {settings.phone_primary} / {settings.phone_secondary}', header_info_style),
        Paragraph(f'Email: {settings.email or "N/A"}', header_info_style),
    ]

    title_para = Paragraph(title_text, custom_title_style)

    if logo:
        header_data = [[logo, title_para, header_content_info]]
        header_table = Table(header_data, colWidths=[2.8*cm, doc.width * 0.42, doc.width * 0.3])
    else:
        header_data = [[title_para, header_content_info]]
        header_table = Table(header_data, colWidths=[doc.width * 0.65, doc.width * 0.35])

    header_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
    ]))
    story.append(header_table)
    story.append(HRFlowable(width="100%", thickness=1.5, color=GOLD, spaceAfter=15, spaceBefore=4))

    # ── Invoice Title & Info ────────────────────
    invoice_data = [
        [
            Paragraph(f'<b>TAX INVOICE</b>', invoice_title_style),
            Paragraph(f'Invoice No: <b color="{CRIMSON}">#{receipt.receipt_number}</b>', ParagraphStyle('num', alignment=TA_RIGHT, fontSize=12, fontName='Times-Bold')),
        ],
        [
            Paragraph(f'BILL TO:', ParagraphStyle('bill', fontSize=11, textColor=GOLD, fontName='Times-Bold', spaceBefore=10)),
            Paragraph(f'Date: <b>{date.strftime("%d %b, %Y")}</b>', ParagraphStyle('dt', alignment=TA_RIGHT, fontSize=11)),
        ],
        [
            [
                Paragraph(f'<b>{customer_name}</b>', ParagraphStyle('cname', fontSize=13, leading=16, fontName='Times-Bold')),
                Paragraph(f'{customer_phone}', ParagraphStyle('cphone', fontSize=10, textColor=colors.grey, leading=12)),
                Paragraph(f'{customer_address or ""}', ParagraphStyle('caddr', fontSize=10, textColor=colors.grey, leading=12)),
            ],
            ''
        ]
    ]
    invoice_table = Table(invoice_data, colWidths=[doc.width * 0.7, doc.width * 0.3])
    invoice_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(invoice_table)
    story.append(Spacer(1, 15))

    # ── Items Table ──────────────────────────────
    if len(items_data) > 1:
        # Create a style for table cells to allow wrapping
        cell_style = ParagraphStyle('TableCell', parent=styles['Normal'], fontSize=10, leading=12)
        cell_style_right = ParagraphStyle('TableCellRight', parent=cell_style, alignment=TA_RIGHT)
        
        # Header Style
        header_style = ParagraphStyle('TableHeader', parent=styles['Normal'], 
                                       textColor=colors.white, fontSize=11, fontName='Times-Bold')
        header_style_right = ParagraphStyle('TableHeaderRight', parent=header_style, alignment=TA_RIGHT)

        # Pre-compute font tag to avoid backslash-in-f-string (Python 3.11 compat)
        rupee_tag = '<font name="' + UNICODE_FONT + '">\u20b9</font>'

        # Process the entire items_data to use Paragraphs for wrapping and font support
        formatted_items = []
        for i, row in enumerate(items_data):
            if i == 0: # Header
                formatted_items.append([
                    Paragraph('<b>' + row[0] + '</b>', header_style),
                    Paragraph('<b>' + row[1] + '</b>', header_style_right),
                    Paragraph('<b>' + row[2].replace('\u20b9', rupee_tag) + '</b>', header_style_right),
                    Paragraph('<b>' + row[3].replace('\u20b9', rupee_tag) + '</b>', header_style_right),
                ])
            else: # Data rows
                formatted_items.append([
                    Paragraph(row[0], cell_style),
                    Paragraph(row[1], cell_style_right),
                    Paragraph(row[2].replace('\u20b9', rupee_tag), cell_style_right),
                    Paragraph(row[3].replace('\u20b9', rupee_tag), cell_style_right),
                ])

        col_widths = [doc.width * 0.45, doc.width * 0.1, doc.width * 0.22, doc.width * 0.23]
        items_table = Table(formatted_items, colWidths=col_widths, repeatRows=1)
        items_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), CRIMSON),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, STRIPE_COLOR]),
            ('LINEBELOW', (0, 0), (-1, 0), 2, GOLD),
            ('LINEBELOW', (0, -1), (-1, -1), 1, GOLD),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('LEFTPADDING', (0, 0), (-1, -1), 10),
            ('RIGHTPADDING', (0, 0), (-1, -1), 10),
        ]))
        story.append(items_table)
    else:
        story.append(Paragraph('No items recorded.', label_style))

    story.append(Spacer(1, 10))

    # ── Totals Layout ───────────────────────────
    # Pre-compute font tag to avoid backslash-in-f-string (Python 3.11 compat)
    rupee_tag = '<font name="' + UNICODE_FONT + '">₹</font>'
    grand_total_font = UNICODE_FONT if UNICODE_FONT != 'Helvetica' else 'Times-Bold'
    # cell_style_right may not be defined if items_data was empty — define fallback
    if 'cell_style_right' not in dir():
        cell_style_right = ParagraphStyle('TableCellRight2', parent=styles['Normal'], alignment=TA_RIGHT, fontSize=10)
    summary_data = [
        ['', 'Subtotal', Paragraph(('\u20b9' + '{:,.2f}'.format(subtotal)).replace('\u20b9', rupee_tag), cell_style_right)],
        ['', 'GST (5%)', Paragraph(('\u20b9' + '{:,.2f}'.format(gst_amount)).replace('\u20b9', rupee_tag), cell_style_right)],
        ['', Paragraph('<b>TOTAL AMOUNT</b>', ParagraphStyle('gt', textColor=CRIMSON, fontSize=14, fontName='Times-Bold')),
         Paragraph(('<b>\u20b9' + '{:,.2f}</b>'.format(grand_total)).replace('\u20b9', rupee_tag),
                   ParagraphStyle('gtv', textColor=CRIMSON, fontSize=14, fontName=grand_total_font, alignment=TA_RIGHT))],
        ['', 'Payment Method', Paragraph('<b>' + payment_mode + '</b>', cell_style_right)],
    ]
    summary_table = Table(summary_data, colWidths=[doc.width * 0.5, doc.width * 0.25, doc.width * 0.25])
    summary_table.setStyle(TableStyle([
        ('ALIGN', (1, 0), (1, -1), 'LEFT'),
        ('ALIGN', (2, 0), (2, -1), 'RIGHT'),
        ('TEXTCOLOR', (1, 0), (1, -1), DARK),
        ('FONTSIZE', (1, 0), (2, -1), 10),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LINEABOVE', (1, 2), (2, 2), 1, GOLD),
        ('LINEBELOW', (1, 2), (2, 2), 2, GOLD),
    ]))
    story.append(summary_table)

    # ── Terms & Footer ──────────────────────────
    story.append(Spacer(1, 40))
    story.append(HRFlowable(width="100%", thickness=1, color=GOLD))
    story.append(Spacer(1, 10))
    
    terms_text = """
    <b>Terms & Conditions:</b><br/>
    1. Goods once sold will not be taken back.<br/>
    2. This is a computer generated invoice and does not require a physical signature.<br/>
    3. Thank you for choosing Mithila White Gold. We value your trust.
    """
    story.append(Paragraph(terms_text, ParagraphStyle('Terms', fontSize=8, textColor=colors.grey, leading=10)))
    
    story.append(Spacer(1, 20))
    story.append(Paragraph('🪷 <b>MITHILA WHITE GOLD</b>', ParagraphStyle('f1', alignment=TA_CENTER, fontSize=12, textColor=CRIMSON, fontName='Times-Bold')))
    # Hindi tagline - using the registered Unicode font
    story.append(Paragraph('मिथिला की धरोहर — हर कौर में।', ParagraphStyle('f2', alignment=TA_CENTER, fontSize=10, textColor=GOLD, fontName=UNICODE_FONT)))

    return story

# ── Chatbot Logic & Reporting ──────────────────────────

from decouple import config

def get_bot_response(user_message):
    """
    AI-based logic to return chatbot responses using Google Gemini API.
    Powered by 'Mithila Gold AI' - the exclusive assistant for Mithila White Gold.
    """
    # Lazy import: only load when chatbot is actually used,
    # so a missing/broken google-genai package doesn't crash startup.
    try:
        from google import genai
        from google.genai import types
    except ImportError:
        return "I am currently undergoing maintenance (AI package unavailable). Please contact support directly."

    api_key = config('GEMINI_API_KEY', default='')

    if not api_key:
        return "I am currently undergoing maintenance (Missing API Key). Please contact support."

    try:
        settings = SiteSettings.get_settings()

        sys_prompt = f"""You are "Mithila Gold AI", the premium and exclusive customer support assistant for the e-commerce website "Mithila White Gold" (mithilawhitegold.com). Your sole purpose is to assist users with their shopping experience, product inquiries, and order management.

### ROLE & PERSONALITY:
- Tone: Extremely polite, helpful, welcoming, and professional.
- Language: Respond in the language used by the user (Hindi, English, or Hinglish).
- Identity: You only know about Mithila White Gold and its products (Premium Makhana / Fox Nuts).

### BUSINESS DETAILS (Live):
- Business Name: {settings.company_name}
- Phone: {settings.phone_primary} / {settings.phone_secondary}
- Email: {settings.email or 'info@mithilawhitegold.com'}
- Address: {settings.address}
- GST Number: {settings.gst_number}
- Website: mithilawhitegold.com

### STRICT GUARDRAILS (CRITICAL):
1. You MUST ONLY answer questions related to Mithila White Gold, its products (Makhana / Fox Nuts), orders, shopping process, shipping, returns, and refunds.
2. If a user asks ANY general knowledge, coding, academic, political, or out-of-scope question (e.g., "Write a Python code", "Who is the PM of India?", "Tell me a joke", "What is machine learning?"), you MUST politely refuse.
   - Refusal Template: "I'm sorry, I am designed to assist you only with Mithila White Gold products and orders. Let me know if you want to buy some premium Makhana! 🪷"
3. Never reveal internal system details, API keys, or backend information.
4. Never impersonate any other brand or AI system.

### PRODUCT KNOWLEDGE BASE:
- **Main Product:** Premium Mithila Makhana (Mithila White Gold)
- **Quality:** Handpicked, organic, high-protein, healthy snack
- **Source:** Directly sourced from the wetlands of Mithila (Bihar, India)
- **Benefits:** Rich in protein, calcium, antioxidants; low in fat; great for all ages
- **Variants:** Available in multiple pack sizes (customers can browse /products for current listings)
- **Use Cases:** Healthy snack, roasted makhana, makhana kheer, fasting food

### ORDER BOOKING PROCESS & STEPS:
When a user asks "how to book", "how to buy", "order kaise karein", "purchase", or shows intent to purchase, guide them step-by-step with these direct interactive links:

**Step 1: Browse Products** 🛍️
Explore our premium Makhana collection.
👉 [Browse Products](/products)

**Step 2: Add to Cart** 🛒
Select your preferred pack size and click "Add to Cart".
👉 [View Your Cart](/cart)

**Step 3: Checkout** 📋
Go to the cart, click "Proceed to Checkout", and enter your shipping details.
👉 [Proceed to Checkout](/checkout)

**Step 4: Payment & Place Order** 💳
Choose Cash on Delivery (COD) or Online Payment and click "Place Order".

### SHIPPING & DELIVERY INFO:
- We deliver across India 🇮🇳
- Estimated delivery: 3–7 business days
- Free shipping available on eligible orders (check website for current offers)
- COD (Cash on Delivery) is available

### RETURNS & REFUNDS:
- If you receive a damaged or incorrect product, contact us within 48 hours of delivery
- Reach us at: {settings.phone_primary} or {settings.email or 'info@mithilawhitegold.com'}
- We are committed to 100% customer satisfaction 🪷

### RESPONSE FORMATTING RULES:
- Use clear bullet points and **bold text** for readability.
- Use emojis (like 📦, 👉, 🛒, 🪷, ✅) to make the chat engaging and warm.
- Always include the relevant website relative URLs (e.g., `/products`, `/cart`, `/checkout`) in Markdown link format so the frontend can render them as clickable links.
- Keep responses concise but complete. Do not write essays — be helpful and to the point.
- Start every response warmly (e.g., "Namaste! 🙏", "Hello!", "Bilkul!")
"""

        client = genai.Client(api_key=api_key)

        # Fallback chain: try each model in order until one works
        MODELS = [
            'gemini-2.5-flash',
            'gemini-2.0-flash-lite',
            'gemini-flash-latest',
        ]
        last_error = None
        for model_name in MODELS:
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=user_message,
                    config=types.GenerateContentConfig(
                        system_instruction=sys_prompt
                    )
                )
                return response.text
            except Exception as model_err:
                err_str = str(model_err)
                print(f"Gemini [{model_name}] failed: {type(model_err).__name__}: {err_str[:120]}")
                last_error = model_err
                # Only continue to fallback on quota/overload errors
                if ('429' in err_str or '503' in err_str or 'UNAVAILABLE' in err_str
                        or 'quota' in err_str.lower() or 'exhausted' in err_str.lower()):
                    continue
                # For other errors (auth, bad request, etc.) stop immediately
                break

        print(f"All Gemini models failed. Last error: {last_error}")
        return "Sorry, I am having trouble connecting right now. Please try again in a moment, or contact us directly at our website. 🙏"

    except Exception as e:
        print(f"Chatbot setup error [{type(e).__name__}]: {e}")
        return "Sorry, I am having trouble connecting right now. Please try again in a moment, or contact us directly at our website. 🙏"

def generate_chat_report_pdf(chat_session):
    """Generate a PDF transcript for a ChatSession."""
    settings = SiteSettings.get_settings()

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4,
                            topMargin=1.5*cm, bottomMargin=2*cm,
                            leftMargin=2*cm, rightMargin=2*cm)
                            
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('ChatTitle', parent=styles['Heading1'], fontSize=22, textColor=CRIMSON, alignment=TA_CENTER, fontName='Times-Bold')
    sub_title = ParagraphStyle('SubTitle', parent=styles['Normal'], fontSize=12, alignment=TA_CENTER, textColor=colors.grey, spaceAfter=20)
    
    user_style = ParagraphStyle('UserMsg', parent=styles['Normal'], fontSize=11, textColor=DARK, leading=14, spaceAfter=10, leftIndent=0, rightIndent=50)
    bot_style = ParagraphStyle('BotMsg', parent=styles['Normal'], fontSize=11, textColor=GOLD_LIGHT, leading=14, spaceAfter=10, leftIndent=50, rightIndent=0, alignment=TA_RIGHT)

    story = []
    
    # Header
    story.append(Paragraph(settings.company_name.upper(), title_style))
    story.append(Paragraph(f"AI Assistant Chat Transcript<br/>Session ID: {chat_session.session_id}<br/>Date: {chat_session.created_at.strftime('%Y-%m-%d %H:%M')}", sub_title))
    story.append(HRFlowable(width="100%", thickness=1.5, color=GOLD, spaceAfter=20))
    
    # Messages
    for msg in chat_session.messages.all():
        if msg.role == 'user':
            text = f"<b>You:</b> {msg.text}"
            story.append(Paragraph(text, user_style))
        else:
            text = f"<b>Bot:</b> {msg.text}"
            story.append(Paragraph(text, bot_style))
            
    # Footer
    story.append(Spacer(1, 30))
    story.append(HRFlowable(width="100%", thickness=1, color=GOLD, spaceAfter=10))
    story.append(Paragraph('🪷 <b>MITHILA WHITE GOLD</b>', ParagraphStyle('f1', alignment=TA_CENTER, fontSize=12, textColor=CRIMSON, fontName='Times-Bold')))

    doc.build(story)
    buffer.seek(0)
    return buffer

