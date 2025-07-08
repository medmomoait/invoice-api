import os
import uuid
import json
from flask import Flask, request, send_file, jsonify
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from dotenv import load_dotenv
import stripe

# Load .env
load_dotenv()
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

app = Flask(__name__)
PDF_FOLDER = 'invoices'
KEY_FILE = 'keys.json'
os.makedirs(PDF_FOLDER, exist_ok=True)

if not os.path.exists(KEY_FILE):
    with open(KEY_FILE, 'w') as f:
        json.dump([], f)

def generate_api_key():
    return str(uuid.uuid4())

def save_api_key(new_key):
    with open(KEY_FILE, 'r') as f:
        keys = json.load(f)
    keys.append(new_key)
    with open(KEY_FILE, 'w') as f:
        json.dump(keys, f)

def is_valid_key(key):
    with open(KEY_FILE, 'r') as f:
        keys = json.load(f)
    return key in keys

@app.route('/health')
def health():
    return "API is running!"

@app.route('/generate-invoice', methods=['POST'])
def generate_invoice():
    api_key = request.headers.get('x-api-key')
    if not api_key or not is_valid_key(api_key):
        return jsonify({'error': 'Unauthorized. Missing or invalid API key.'}), 401

    data = request.json
    invoice_id = str(uuid.uuid4())
    filename = os.path.join(PDF_FOLDER, f"{invoice_id}.pdf")

    c = canvas.Canvas(filename, pagesize=A4)
    c.drawString(100, 800, f"Invoice #: {data['invoice_number']}")
    c.drawString(100, 780, f"Client: {data['client_name']}")
    c.drawString(100, 760, f"Email: {data['client_email']}")
    c.drawString(100, 740, f"Due Date: {data['due_date']}")

    y = 700
    total = 0
    for item in data['items']:
        line = f"{item['description']} - {item['quantity']} x ${item['unit_price']}"
        c.drawString(100, y, line)
        total += item['quantity'] * item['unit_price']
        y -= 20

    c.drawString(100, y - 20, f"Total: ${total}")
    c.save()

    return jsonify({
        'invoice_id': invoice_id,
        'pdf_url': f"/invoice/{invoice_id}"
    })

@app.route('/invoice/<invoice_id>', methods=['GET'])
def get_invoice(invoice_id):
    filepath = os.path.join(PDF_FOLDER, f"{invoice_id}.pdf")
    if os.path.exists(filepath):
        return send_file(filepath, as_attachment=True)
    return jsonify({'error': 'Invoice not found'}), 404

@app.route('/create-checkout-session', methods=['POST'])
def create_checkout_session():
    try:
        session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            mode='payment',
            line_items=[{
                'price_data': {
                    'currency': 'usd',
                    'product_data': {'name': 'Invoice API Access'},
                    'unit_amount': 500
                },
                'quantity': 1
            }],
            success_url='http://localhost:5000/success?session_id={CHECKOUT_SESSION_ID}',
            cancel_url='http://localhost:5000/cancel'
        )
        return jsonify({'checkout_url': session.url})
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/success')
def success():
    new_key = generate_api_key()
    save_api_key(new_key)
    return f"""
    Payment successful!<br><br>
    Your API key is:<br><br>
    <b>{new_key}</b><br><br>
    Save this key! You’ll need it to call <code>/generate-invoice</code>.<br>
    Include it in your header like this:<br>
    <code>x-api-key: {new_key}</code>
    """

@app.route('/cancel')
def cancel():
    return "Payment was cancelled."

if __name__ == '__main__':
    print("Visit http://127.0.0.1:5000/success to get your API key.")
    app.run(debug=True)
