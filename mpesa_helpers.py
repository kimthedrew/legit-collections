import requests
import base64
import os
from datetime import datetime
from flask import current_app

# M-Pesa Daraja API Configuration
MPESA_ENVIRONMENT = os.getenv('MPESA_ENVIRONMENT', 'sandbox')  # sandbox or production
MPESA_CONSUMER_KEY = os.getenv('MPESA_CONSUMER_KEY')
MPESA_CONSUMER_SECRET = os.getenv('MPESA_CONSUMER_SECRET')
MPESA_SHORTCODE = os.getenv('MPESA_SHORTCODE')  # Business shortcode/paybill
MPESA_PASSKEY = os.getenv('MPESA_PASSKEY')  # Lipa na M-Pesa Online passkey

# API URLs
if MPESA_ENVIRONMENT == 'production':
    BASE_URL = 'https://api.safaricom.co.ke'
else:
    BASE_URL = 'https://sandbox.safaricom.co.ke'

def get_mpesa_access_token():
    """
    Generate OAuth access token for M-Pesa API
    
    Returns:
        str: Access token or None if failed
    """
    try:
        api_url = f"{BASE_URL}/oauth/v1/generate?grant_type=client_credentials"
        
        # Create basic auth header
        credentials = f"{MPESA_CONSUMER_KEY}:{MPESA_CONSUMER_SECRET}"
        encoded_credentials = base64.b64encode(credentials.encode()).decode()
        
        headers = {
            'Authorization': f'Basic {encoded_credentials}'
        }
        
        response = requests.get(api_url, headers=headers)
        response.raise_for_status()
        
        data = response.json()
        access_token = data.get('access_token')
        
        current_app.logger.info("M-Pesa access token obtained successfully")
        return access_token
        
    except Exception as e:
        current_app.logger.error(f"Error getting M-Pesa access token: {str(e)}")
        return None

def generate_password():
    """
    Generate password for STK Push request
    Base64 encoding of: Shortcode + Passkey + Timestamp
    
    Returns:
        tuple: (password, timestamp)
    """
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    data_to_encode = f"{MPESA_SHORTCODE}{MPESA_PASSKEY}{timestamp}"
    encoded = base64.b64encode(data_to_encode.encode()).decode()
    return encoded, timestamp

def initiate_stk_push(phone_number, amount, account_reference, transaction_desc, callback_url):
    """
    Initiate STK Push (Lipa na M-Pesa Online)
    
    Args:
        phone_number: Customer's phone number (format: 254XXXXXXXXX)
        amount: Amount to charge (minimum 1)
        account_reference: Reference for the transaction (e.g., Order-123)
        transaction_desc: Description of the transaction
        callback_url: URL to receive payment notification
    
    Returns:
        dict: Response from M-Pesa API
    """
    try:
        # Validate phone number format
        if not phone_number.startswith('254'):
            if phone_number.startswith('0'):
                phone_number = '254' + phone_number[1:]
            elif phone_number.startswith('+254'):
                phone_number = phone_number[1:]
            elif phone_number.startswith('7') or phone_number.startswith('1'):
                phone_number = '254' + phone_number
        
        # Get access token
        access_token = get_mpesa_access_token()
        if not access_token:
            return {'success': False, 'error': 'Failed to get access token'}
        
        # Generate password
        password, timestamp = generate_password()
        
        # API endpoint
        api_url = f"{BASE_URL}/mpesa/stkpush/v1/processrequest"
        
        # Headers
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }
        
        # Request payload
        payload = {
            'BusinessShortCode': MPESA_SHORTCODE,
            'Password': password,
            'Timestamp': timestamp,
            'TransactionType': 'CustomerPayBillOnline',  # or CustomerBuyGoodsOnline
            'Amount': int(amount),  # M-Pesa requires integer
            'PartyA': phone_number,  # Customer phone number
            'PartyB': MPESA_SHORTCODE,  # Your business shortcode
            'PhoneNumber': phone_number,  # Phone to receive STK push
            'CallBackURL': callback_url,
            'AccountReference': account_reference,  # Order reference
            'TransactionDesc': transaction_desc
        }
        
        current_app.logger.info(f"Initiating STK Push for {phone_number}, Amount: {amount}")
        
        # Make request
        response = requests.post(api_url, json=payload, headers=headers)
        response.raise_for_status()
        
        data = response.json()
        
        if data.get('ResponseCode') == '0':
            current_app.logger.info(f"STK Push initiated successfully: {data.get('CheckoutRequestID')}")
            return {
                'success': True,
                'checkout_request_id': data.get('CheckoutRequestID'),
                'merchant_request_id': data.get('MerchantRequestID'),
                'response_description': data.get('ResponseDescription'),
                'customer_message': data.get('CustomerMessage')
            }
        else:
            current_app.logger.error(f"STK Push failed: {data.get('ResponseDescription')}")
            return {
                'success': False,
                'error': data.get('ResponseDescription', 'STK Push failed')
            }
            
    except Exception as e:
        current_app.logger.error(f"Error initiating STK Push: {str(e)}")
        return {'success': False, 'error': str(e)}

def query_stk_status(checkout_request_id):
    """
    Query the status of an STK Push transaction
    
    Args:
        checkout_request_id: CheckoutRequestID from initiate_stk_push
    
    Returns:
        dict: Transaction status
    """
    try:
        # Get access token
        access_token = get_mpesa_access_token()
        if not access_token:
            return {'success': False, 'error': 'Failed to get access token'}
        
        # Generate password
        password, timestamp = generate_password()
        
        # API endpoint
        api_url = f"{BASE_URL}/mpesa/stkpushquery/v1/query"
        
        # Headers
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }
        
        # Request payload
        payload = {
            'BusinessShortCode': MPESA_SHORTCODE,
            'Password': password,
            'Timestamp': timestamp,
            'CheckoutRequestID': checkout_request_id
        }
        
        # Make request
        response = requests.post(api_url, json=payload, headers=headers)
        response.raise_for_status()
        
        data = response.json()
        
        return {
            'success': True,
            'result_code': data.get('ResultCode'),
            'result_desc': data.get('ResultDesc'),
            'response_code': data.get('ResponseCode')
        }
        
    except Exception as e:
        current_app.logger.error(f"Error querying STK status: {str(e)}")
        return {'success': False, 'error': str(e)}

def is_mpesa_payment_successful(result_code):
    """
    Check if M-Pesa payment was successful
    
    Args:
        result_code: ResultCode from M-Pesa callback (0 = success)
    
    Returns:
        bool: True if payment successful
    """
    return str(result_code) == '0'

def format_phone_number(phone):
    """
    Format phone number to M-Pesa format (254XXXXXXXXX)
    
    Args:
        phone: Phone number in various formats
    
    Returns:
        str: Formatted phone number
    """
    # Remove spaces and special characters
    phone = ''.join(filter(str.isdigit, phone))
    
    # Convert to 254 format
    if phone.startswith('254'):
        return phone
    elif phone.startswith('0'):
        return '254' + phone[1:]
    elif phone.startswith('7') or phone.startswith('1'):
        return '254' + phone
    else:
        return phone

def validate_mpesa_credentials():
    """
    Check if all required M-Pesa credentials are configured
    
    Returns:
        tuple: (bool, str) - (is_valid, error_message)
    """
    if not MPESA_CONSUMER_KEY:
        return False, "M-Pesa Consumer Key not configured"
    
    if not MPESA_CONSUMER_SECRET:
        return False, "M-Pesa Consumer Secret not configured"
    
    if not MPESA_SHORTCODE:
        return False, "M-Pesa Business Shortcode not configured"
    
    if not MPESA_PASSKEY:
        return False, "M-Pesa Passkey not configured"
    
    return True, "All credentials configured"

