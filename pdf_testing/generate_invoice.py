import os
from datetime import datetime
from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML, CSS

def generate_credit_invoice():
    # 1. Mock Data (Simulating a database payload)
    
    # We will generate 35 items to ensure the table breaks onto a second page.
    items = []
    subtotal = 0.0
    for i in range(1, 36):
        qty = 2
        price = 15.50 + i
        total = qty * price
        subtotal += total
        
        items.append({
            "name": f"Enterprise Software License - Tier {i}",
            "sku": f"LIC-ENT-{1000+i}",
            "quantity": qty,
            "unit_price": price,
            "total": total
        })

    tax_rate = 7.0
    tax_amount = subtotal * (tax_rate / 100)
    grand_total = subtotal + tax_amount

    context = {
        "company": {
            "name": "Global Tech Solutions LLC",
            "address": "100 Innovation Drive, Silicon Valley, CA 94025",
            "email": "billing@globaltech.com",
            "phone": "+1 (555) 019-8273",
            "tax_id": "US-987654321"
        },
        "client": {
            "name": "Acme Corporation",
            "address": "450 Corporate Blvd, Suite 200, New York, NY 10001",
            "contact": "Jane Doe, Accounts Payable",
            "email": "invoices@acmecorp.com"
        },
        "invoice": {
            "number": "CRD-2026-0892",
            "date": datetime.now().strftime("%B %d, %Y"),
            "original_invoice": "INV-2026-4401",
            "reason": "Over-provisioning of licenses / SLA breach"
        },
        "items": items,
        "totals": {
            "subtotal": subtotal,
            "tax_rate": tax_rate,
            "tax_amount": tax_amount,
            "grand_total": grand_total
        }
    }

    # 2. Setup Jinja2 Environment
    env = Environment(loader=FileSystemLoader('.'))
    template = env.get_template('invoice.html')

    # 3. Render HTML with context data
    rendered_html = template.render(context)

    # 4. Generate PDF using WeasyPrint
    output_filename = "credit_invoice_output.pdf"
    
    print(f"Rendering PDF to {output_filename}...")
    
    # Base URL is required so Weasyprint can find local assets like style.css
    HTML(string=rendered_html, base_url=os.path.abspath('.')).write_pdf(
        output_filename,
        stylesheets=[CSS('style.css')]
    )
    
    print("Success! PDF generated.")

if __name__ == "__main__":
    generate_credit_invoice()