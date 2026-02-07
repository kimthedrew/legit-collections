from flask_mail import Mail, Message
from flask import current_app, render_template_string
import os

mail = Mail()

def init_mail(app):
    """Initialize Flask-Mail with app"""
    app.config['MAIL_SERVER'] = os.getenv('MAIL_SERVER', 'smtp.gmail.com')
    app.config['MAIL_PORT'] = int(os.getenv('MAIL_PORT', 587))
    app.config['MAIL_USE_TLS'] = os.getenv('MAIL_USE_TLS', 'True') == 'True'
    app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
    app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
    app.config['MAIL_DEFAULT_SENDER'] = os.getenv('MAIL_DEFAULT_SENDER', 'Country Hub Collections <noreply@countryhubcollections.com>')
    
    mail.init_app(app)
    return mail

def send_order_confirmation(order):
    """Send order confirmation email to customer"""
    try:
        if not current_app.config.get('MAIL_USERNAME'):
            current_app.logger.warning("Email not configured, skipping order confirmation email")
            return False
        
        subject = f"Order Confirmation #{order.id} - Country Hub Collections"
        
        # Email body (HTML)
        html_body = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }}
                .content {{ background: #f8f9fa; padding: 30px; }}
                .order-details {{ background: white; padding: 20px; border-radius: 10px; margin: 20px 0; }}
                .footer {{ text-align: center; padding: 20px; color: #666; font-size: 12px; }}
                .btn {{ display: inline-block; padding: 12px 30px; background: #667eea; color: white; text-decoration: none; border-radius: 5px; margin: 10px 0; }}
                .status-badge {{ display: inline-block; padding: 5px 15px; background: #28a745; color: white; border-radius: 20px; font-size: 14px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🎉 Order Confirmed!</h1>
                    <p>Thank you for your purchase</p>
                </div>
                
                <div class="content">
                    <h2>Hi {order.user.name},</h2>
                    <p>We've received your order and it's being processed. Here are your order details:</p>
                    
                    <div class="order-details">
                        <h3>Order #{order.id}</h3>
                        <hr>
                        <p><strong>Product:</strong> {order.shoe.name if order.shoe else 'N/A'}</p>
                        <p><strong>Size:</strong> {order.size}</p>
                        <p><strong>Amount:</strong> Ksh{order.amount or (order.shoe.price if order.shoe else 0):.2f}</p>
                        <p><strong>Payment Method:</strong> {order.payment_method or 'Cash'}</p>
                        <p><strong>Payment Status:</strong> <span class="status-badge">{order.payment_status}</span></p>
                        {f'<p><strong>Transaction Reference:</strong> {order.payment_reference or order.payment_code}</p>' if order.payment_reference or order.payment_code else ''}
                        <p><strong>Order Date:</strong> {order.created_at.strftime('%B %d, %Y at %I:%M %p')}</p>
                    </div>
                    
                    <p><strong>What's Next?</strong></p>
                    <ul>
                        <li>We'll verify your payment</li>
                        <li>Your order will be prepared</li>
                        <li>You'll receive tracking information</li>
                        <li>Delivery within 3-5 business days</li>
                    </ul>
                    
                    <div style="text-align: center; margin: 30px 0;">
                        <a href="https://yoursite.com/orders" class="btn">Track Your Order</a>
                    </div>
                    
                    <p>If you have any questions, feel free to reach out via WhatsApp: <strong>+254 113 690 898</strong></p>
                </div>
                
                <div class="footer">
                    <p>© 2025 Country Hub Collections. All rights reserved.</p>
                    <p>
                        <a href="#">Instagram</a> |
                        <a href="#">Privacy Policy</a> |
                        <a href="#">Terms of Service</a>
                    </p>
                </div>
            </div>
        </body>
        </html>
        """
        
        msg = Message(
            subject=subject,
            recipients=[order.user.email],
            html=html_body
        )
        
        mail.send(msg)
        current_app.logger.info(f"Order confirmation email sent to {order.user.email}")
        return True
        
    except Exception as e:
        current_app.logger.error(f"Error sending order confirmation email: {str(e)}")
        return False

def send_payment_confirmation(order):
    """Send payment confirmation email"""
    try:
        if not current_app.config.get('MAIL_USERNAME'):
            return False
        
        subject = f"Payment Confirmed - Order #{order.id}"
        
        html_body = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: linear-gradient(135deg, #28a745 0%, #20c997 100%); color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }}
                .content {{ background: #f8f9fa; padding: 30px; }}
                .success-box {{ background: #d4edda; border: 2px solid #28a745; padding: 20px; border-radius: 10px; text-align: center; margin: 20px 0; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>✅ Payment Confirmed!</h1>
                </div>
                
                <div class="content">
                    <div class="success-box">
                        <h2 style="color: #28a745;">Payment Received</h2>
                        <p><strong>Ksh{order.amount or 0:.2f}</strong></p>
                        <p>Receipt: <code>{order.payment_reference or 'Pending'}</code></p>
                    </div>
                    
                    <p>Hi {order.user.name},</p>
                    <p>Great news! Your payment has been confirmed and your order is now being prepared for shipment.</p>
                    
                    <p><strong>Order Details:</strong></p>
                    <ul>
                        <li>Order ID: #{order.id}</li>
                        <li>Product: {order.shoe.name if order.shoe else 'N/A'}</li>
                        <li>Size: {order.size}</li>
                    </ul>
                    
                    <p>We'll notify you once your order has been shipped!</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        msg = Message(subject=subject, recipients=[order.user.email], html=html_body)
        mail.send(msg)
        return True
        
    except Exception as e:
        current_app.logger.error(f"Error sending payment confirmation: {str(e)}")
        return False

def send_order_status_update(order, new_status):
    """Send order status update email"""
    try:
        if not current_app.config.get('MAIL_USERNAME'):
            return False
        
        status_messages = {
            'Processing': 'Your order is being prepared',
            'Shipped': 'Your order has been shipped',
            'Delivered': 'Your order has been delivered',
            'Cancelled': 'Your order has been cancelled'
        }
        
        subject = f"Order #{order.id} - {status_messages.get(new_status, 'Status Update')}"
        
        html_body = f"""
        <!DOCTYPE html>
        <html>
        <body style="font-family: Arial, sans-serif; padding: 20px; background: #f8f9fa;">
            <div style="max-width: 600px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px;">
                <h2>Order Status Update</h2>
                <p>Hi {order.user.name},</p>
                <p>Your order #{order.id} status has been updated to: <strong>{new_status}</strong></p>
                <p>{status_messages.get(new_status, '')}</p>
                <p>Best regards,<br>Country Hub Collections Team</p>
            </div>
        </body>
        </html>
        """
        
        msg = Message(subject=subject, recipients=[order.user.email], html=html_body)
        mail.send(msg)
        return True
        
    except Exception as e:
        current_app.logger.error(f"Error sending status update: {str(e)}")
        return False

