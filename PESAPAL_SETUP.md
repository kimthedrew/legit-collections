# Pesapal Payment Gateway Setup Guide

## 🎯 Overview
This guide will help you set up Pesapal payment integration for LegitCollections. Pesapal allows your customers to pay using:
- **M-Pesa** (Lipa na M-Pesa)
- **Credit/Debit Cards** (Visa, Mastercard)
- **Bank Transfers**
- **Airtel Money**

---

## 📝 Step 1: Create Pesapal Account

1. **Go to Pesapal Website**
   - Sandbox (Testing): https://developer.pesapal.com/
   - Live (Production): https://www.pesapal.com/

2. **Register for an Account**
   - Click "Sign Up" or "Create Account"
   - Fill in your business details
   - Verify your email

3. **Complete Business Verification**
   - For LIVE environment, you'll need:
     - Business registration documents
     - ID/Passport
     - Bank account details
   - Approval takes 1-3 business days

---

## 🔑 Step 2: Get API Credentials

### For Sandbox (Testing):
1. Login to https://developer.pesapal.com/
2. Go to **"API Keys"** section
3. Click **"Create Consumer Key"**
4. Copy your credentials:
   - **Consumer Key**
   - **Consumer Secret**

### For Production:
1. Login to https://www.pesapal.com/
2. Navigate to **Settings → API Keys**
3. Generate your production credentials

---

## ⚙️ Step 3: Configure Environment Variables

Add these to your `.env` file (create one if it doesn't exist):

```bash
# Pesapal Configuration
PESAPAL_CONSUMER_KEY=your_consumer_key_here
PESAPAL_CONSUMER_SECRET=your_consumer_secret_here
PESAPAL_ENVIRONMENT=sandbox  # Change to 'live' for production
PESAPAL_IPN_ID=  # Leave empty initially, will be auto-generated
```

### Example:
```bash
PESAPAL_CONSUMER_KEY=qkio1BGGYAXTu2JOfm7XSXNjhiuFImzo
PESAPAL_CONSUMER_SECRET=osGQ364R49cXKeOYSpaOnT++rHs=
PESAPAL_ENVIRONMENT=sandbox
```

---

## 🚀 Step 4: Configure Deployment (Koyeb)

1. **Go to Koyeb Dashboard**
2. **Select your app** (legit-collections)
3. **Go to Settings → Environment Variables**
4. **Add the following variables:**

| Variable Name | Value | Description |
|--------------|-------|-------------|
| `PESAPAL_CONSUMER_KEY` | Your consumer key | From Pesapal dashboard |
| `PESAPAL_CONSUMER_SECRET` | Your consumer secret | From Pesapal dashboard |
| `PESAPAL_ENVIRONMENT` | `sandbox` or `live` | Use sandbox for testing |
| `PESAPAL_IPN_ID` | Leave empty initially | Auto-generated on first payment |

5. **Save and redeploy**

---

## 🔔 Step 5: Register IPN URL (Automatic)

The app will automatically register your IPN (Instant Payment Notification) URL on the first payment attempt.

**Manual Registration (Optional):**
1. Login to Pesapal dashboard
2. Go to **Settings → IPN Settings**
3. Add your IPN URL: `https://yourdomain.com/pesapal/ipn`
4. Copy the IPN ID
5. Add it to your environment variables as `PESAPAL_IPN_ID`

---

## 🧪 Step 6: Test the Integration

### Testing in Sandbox:

1. **Use Test Payment Details:**
   - **M-Pesa (Sandbox):**
     - Phone: Any 254XXXXXXXXX format
     - Don't actually send real money in sandbox!
   
   - **Test Cards (Sandbox):**
     ```
     Card Number: 4111111111111111 (Visa)
     Expiry: Any future date
     CVV: 123
     ```

2. **Test Flow:**
   - Add product to cart
   - Go to checkout
   - Select "Pay with Pesapal"
   - Enter phone number
   - Click "Pay Now"
   - Complete payment on Pesapal page
   - Verify you're redirected back
   - Check order status updated to "Processing"
   - Check payment status shows "Paid"

---

## 📊 Step 7: Monitor Transactions

### In Your Admin Dashboard:
- Go to **Admin Panel → Order Management**
- You'll see:
  - Payment Method (Pesapal/M-Pesa/Cash)
  - Payment Status (Paid/Pending/Failed)
  - Transaction Reference
  - Order Status

### In Pesapal Dashboard:
- Login to Pesapal
- Go to **Transactions**
- View all payments
- Download reports
- Issue refunds if needed

---

## 🔄 Step 8: Go Live (When Ready)

1. **Complete Business Verification** with Pesapal
2. **Get Production Credentials** from Pesapal live dashboard
3. **Update Environment Variables:**
   ```bash
   PESAPAL_ENVIRONMENT=live
   PESAPAL_CONSUMER_KEY=your_live_consumer_key
   PESAPAL_CONSUMER_SECRET=your_live_consumer_secret
   ```
4. **Test thoroughly** before announcing to customers
5. **Enable HTTPS** (required for production)

---

## 💳 Supported Payment Methods

Once configured, customers can pay using:

| Method | Supported | Notes |
|--------|-----------|-------|
| M-Pesa (Safaricom) | ✅ | Most popular in Kenya |
| M-Pesa (Airtel Money) | ✅ | Alternative mobile money |
| Visa/Mastercard | ✅ | Local & international cards |
| Bank Transfer | ✅ | Direct bank payments |

---

## 🛟 Troubleshooting

### Issue: "Payment service temporarily unavailable"
**Solution:**
- Check environment variables are set correctly
- Verify Consumer Key and Secret are correct
- Check internet connection
- Review app logs for detailed error

### Issue: IPN not updating order status
**Solution:**
- Ensure IPN URL is accessible (HTTPS required)
- Check firewall settings
- Verify IPN ID is registered
- Check app logs for IPN errors

### Issue: Callback fails after payment
**Solution:**
- Ensure user stays logged in during payment
- Check session configuration
- Verify callback URL is correct

---

## 📞 Support

- **Pesapal Support:** support@pesapal.com
- **Pesapal Docs:** https://developer.pesapal.com/how-to-integrate/api-30-integration
- **Phone:** +254 709 117 000

---

## 🔐 Security Best Practices

1. **Never commit credentials** to Git
2. **Use .env file** for local development
3. **Use environment variables** in production
4. **Enable HTTPS** for production
5. **Validate all callbacks** from Pesapal
6. **Log all transactions** for audit trail
7. **Monitor for suspicious activity**

---

## 💰 Pricing

Pesapal charges a small percentage per transaction:
- **M-Pesa:** ~2-3% per transaction
- **Cards:** ~3-4% per transaction
- **No setup fees** in most cases
- **No monthly fees**

Check current rates: https://www.pesapal.com/pricing

---

## ✅ Checklist

Before going live, ensure:

- [ ] Pesapal account created and verified
- [ ] API credentials obtained (Consumer Key + Secret)
- [ ] Environment variables configured in Koyeb
- [ ] Tested payments in sandbox environment
- [ ] IPN URL registered successfully
- [ ] Callback URLs working correctly
- [ ] HTTPS enabled on your domain
- [ ] Tested all payment methods (M-Pesa, Card, etc.)
- [ ] Admin can see payment statuses
- [ ] Order confirmation emails working (if configured)
- [ ] Terms of service and privacy policy pages created

---

**Document Version:** 1.0  
**Last Updated:** October 2025

