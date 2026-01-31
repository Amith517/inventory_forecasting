import smtplib
from email.mime.text import MIMEText
from modules.database import get_connection

# Configure these with your email settings if you want real emails
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587
SMTP_USER = "amithreddynagireddy@gmail.com"
SMTP_PASS = "zcdz fpxp olzw qloz"
FROM_EMAIL = SMTP_USER
ENABLE_SMTP = True

def send_email(to_email, subject, body):
    if not ENABLE_SMTP:
        print(f"[EMAIL disabled] To: {to_email}, Subject: {subject}\n{body}\n")
        return True

    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = FROM_EMAIL
    msg['To'] = to_email

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.send_message(msg)
        return True
    except Exception as e:
        print("Failed to send email:", e)
        return False


def record_alert(product_id, alert_type, message):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("INSERT INTO alerts (product_id, alert_type, message) VALUES (?, ?, ?)",
                (product_id, alert_type, message))
    conn.commit()
    conn.close()


# ---------------------------------------------------------
# NEW — Send Early Warning Email With Forecast
# ---------------------------------------------------------
def send_stock_alert_email(product_name, current_stock, early_warning_stock, forecast_text):
    subject = f"Early Stock Warning – {product_name}"

    body = f"""
Product: {product_name}
Current Stock: {current_stock}
Early Warning Level: {early_warning_stock}

-------------------------
Next 14 Days Forecast
-------------------------
{forecast_text}

Action Required:
Stock is nearing the minimum level. Please restock soon.
"""

    send_email(SMTP_USER, subject, body)
