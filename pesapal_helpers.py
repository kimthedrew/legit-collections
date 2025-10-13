import requests
import json
import os
from datetime import datetime, timedelta
from flask import current_app

# Pesapal API Configuration
PESAPAL_CONSUMER_KEY = os.getenv('PESAPAL_CONSUMER_KEY')
PESAPAL_CONSUMER_SECRET = os.getenv('PESAPAL_CONSUMER_SECRET')
PESAPAL_ENVIRONMENT = os.getenv('PESAPAL_ENVIRONMENT', 'sandbox')  # sandbox or live

# API URLs
if PESAPAL_ENVIRONMENT == 'live':
    BASE_URL = 'https://pay.pesapal.com/v3'
else:
    BASE_URL = 'https://cybqa.pesapal.com/pesapalv3'

# Token cache (in production, use Redis or database)
_token_cache = {
    'token': None,
    'expires_at': None
}

def get_access_token():
    """Get OAuth access token from Pesapal"""
    global _token_cache
    
    # Check if we have a valid cached token
    if _token_cache['token'] and _token_cache['expires_at']:
        if datetime.now() < _token_cache['expires_at']:
            return _token_cache['token']
    
    try:
        url = f"{BASE_URL}/api/Auth/RequestToken"
        
        headers = {
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        }
        
        payload = {
            'consumer_key': PESAPAL_CONSUMER_KEY,
            'consumer_secret': PESAPAL_CONSUMER_SECRET
        }
        
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()
        
        data = response.json()
        token = data.get('token')
        
        # Cache token (expires in 5 minutes typically, so cache for 4 minutes)
        _token_cache['token'] = token
        _token_cache['expires_at'] = datetime.now() + timedelta(minutes=4)
        
        current_app.logger.info("Pesapal access token obtained successfully")
        return token
        
    except Exception as e:
        current_app.logger.error(f"Error getting Pesapal access token: {str(e)}")
        return None

def register_ipn_url(ipn_url):
    """Register IPN (Instant Payment Notification) URL with Pesapal"""
    try:
        token = get_access_token()
        if not token:
            return None
        
        url = f"{BASE_URL}/api/URLSetup/RegisterIPN"
        
        headers = {
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {token}'
        }
        
        payload = {
            'url': ipn_url,
            'ipn_notification_type': 'GET'  # Can be GET or POST
        }
        
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()
        
        data = response.json()
        ipn_id = data.get('ipn_id')
        
        current_app.logger.info(f"IPN URL registered: {ipn_id}")
        return ipn_id
        
    except Exception as e:
        current_app.logger.error(f"Error registering IPN URL: {str(e)}")
        return None

def initiate_payment(order_id, amount, description, callback_url, notification_id, customer_email, customer_phone):
    """
    Initiate a payment transaction with Pesapal
    
    Args:
        order_id: Your internal order ID
        amount: Amount to charge
        description: Payment description
        callback_url: URL to redirect after payment
        notification_id: IPN notification ID from register_ipn_url()
        customer_email: Customer's email
        customer_phone: Customer's phone number
    
    Returns:
        dict: {'success': bool, 'redirect_url': str, 'order_tracking_id': str, 'merchant_reference': str}
    """
    try:
        token = get_access_token()
        if not token:
            return {'success': False, 'error': 'Failed to get access token'}
        
        url = f"{BASE_URL}/api/Transactions/SubmitOrderRequest"
        
        headers = {
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {token}'
        }
        
        # Generate unique merchant reference
        merchant_reference = f"ORDER-{order_id}-{int(datetime.now().timestamp())}"
        
        payload = {
            'id': merchant_reference,
            'currency': 'KES',  # Kenya Shillings
            'amount': float(amount),
            'description': description,
            'callback_url': callback_url,
            'notification_id': notification_id,
            'billing_address': {
                'email_address': customer_email,
                'phone_number': customer_phone,
                'country_code': 'KE',
                'first_name': '',
                'middle_name': '',
                'last_name': '',
                'line_1': '',
                'line_2': '',
                'city': '',
                'state': '',
                'postal_code': '',
                'zip_code': ''
            }
        }
        
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()
        
        data = response.json()
        
        if data.get('status') == '200':
            current_app.logger.info(f"Payment initiated for order {order_id}")
            return {
                'success': True,
                'redirect_url': data.get('redirect_url'),
                'order_tracking_id': data.get('order_tracking_id'),
                'merchant_reference': data.get('merchant_reference'),
                'error': data.get('error')
            }
        else:
            current_app.logger.error(f"Payment initiation failed: {data.get('message')}")
            return {
                'success': False,
                'error': data.get('message', 'Payment initiation failed')
            }
            
    except Exception as e:
        current_app.logger.error(f"Error initiating payment: {str(e)}")
        return {'success': False, 'error': str(e)}

def get_transaction_status(order_tracking_id):
    """
    Check the status of a transaction
    
    Args:
        order_tracking_id: The tracking ID from initiate_payment()
    
    Returns:
        dict: Transaction status details
    """
    try:
        token = get_access_token()
        if not token:
            return {'success': False, 'error': 'Failed to get access token'}
        
        url = f"{BASE_URL}/api/Transactions/GetTransactionStatus?orderTrackingId={order_tracking_id}"
        
        headers = {
            'Accept': 'application/json',
            'Authorization': f'Bearer {token}'
        }
        
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        data = response.json()
        
        return {
            'success': True,
            'payment_status': data.get('payment_status_description'),
            'payment_status_code': data.get('status_code'),
            'amount': data.get('amount'),
            'currency': data.get('currency'),
            'payment_method': data.get('payment_method'),
            'confirmation_code': data.get('confirmation_code'),
            'payment_account': data.get('payment_account'),
            'merchant_reference': data.get('merchant_reference')
        }
        
    except Exception as e:
        current_app.logger.error(f"Error checking transaction status: {str(e)}")
        return {'success': False, 'error': str(e)}

def is_payment_successful(payment_status_code):
    """
    Check if payment status code indicates success
    
    Args:
        payment_status_code: Status code from Pesapal (0, 1, 2, 3, etc.)
    
    Returns:
        bool: True if payment was successful
    """
    # Status codes:
    # 0 = INVALID
    # 1 = COMPLETED (successful)
    # 2 = FAILED
    # 3 = REVERSED
    
    return payment_status_code == 1

