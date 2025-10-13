# M-Pesa Daraja API Setup Guide

## 🎯 Overview
This guide will help you set up **direct M-Pesa integration** using Safaricom's Daraja API. This allows customers to pay directly via M-Pesa STK Push (Lipa na M-Pesa Online) without going through a third-party gateway.

### Benefits:
- ✅ **Lower fees** (~1.5-2% vs 3-5% for gateways)
- ✅ **Instant payment** - STK Push directly to customer's phone
- ✅ **Better control** - Direct integration with Safaricom
- ✅ **Professional** - No intermediary

---

## 📝 Step 1: Register on Daraja Portal

1. **Go to Daraja Portal**
   - Sandbox (Testing): https://developer.safaricom.co.ke/
   - Create an account if you don't have one

2. **Create a New App**
   - Click **"My Apps"** → **"Add a New App"**
   - Give it a name (e.g., "LegitCollections")
   - Select **"Lipa Na M-Pesa Online"** product
   - Click **"Create App"**

3. **Get Your Credentials**
   - After creating, you'll see:
     - **Consumer Key**
     - **Consumer Secret**
   - Copy these - you'll need them!

---

## 🔑 Step 2: Get Production Credentials (For Live)

### Requirements for Production:
1. **Register Business on M-Pesa**
   - You need a registered business/company
   - Apply for M-Pesa Paybill or Till Number
   - Contact: paybill@safaricom.co.ke

2. **Documents Needed:**
   - Certificate of Registration/Incorporation
   - KRA PIN Certificate
   - ID/Passport of directors
   - Bank account details

3. **Approval Process:**
   - Submit application to Safaricom
   - Wait for approval (1-2 weeks)
   - Get your **Shortcode** (Paybill/Till number)
   - Get your **Passkey** (Lipa na M-Pesa Online Passkey)

---

## ⚙️ Step 3: Configure Environment Variables

### For Sandbox (Testing):

Add these to your `.env` file:

```bash
# M-Pesa Daraja API Configuration (Sandbox)
MPESA_ENVIRONMENT=sandbox
MPESA_CONSUMER_KEY=your_consumer_key_from_daraja
MPESA_CONSUMER_SECRET=your_consumer_secret_from_daraja
MPESA_SHORTCODE=174379  # Sandbox shortcode
MPESA_PASSKEY=bfb279f9aa9bdbcf158e97dd71a467cd2e0c893059b10f78e6b72ada1ed2c919  # Sandbox passkey
```

### For Production:

```bash
# M-Pesa Daraja API Configuration (Production)
MPESA_ENVIRONMENT=production
MPESA_CONSUMER_KEY=your_production_consumer_key
MPESA_CONSUMER_SECRET=your_production_consumer_secret
MPESA_SHORTCODE=your_paybill_or_till_number
MPESA_PASSKEY=your_production_passkey_from_safaricom
```

---

## 🚀 Step 4: Configure Deployment (Koyeb)

Add these environment variables in Koyeb:

| Variable Name | Value | Description |
|--------------|-------|-------------|
| `MPESA_ENVIRONMENT` | `sandbox` or `production` | Use sandbox for testing |
| `MPESA_CONSUMER_KEY` | Your consumer key | From Daraja portal |
| `MPESA_CONSUMER_SECRET` | Your consumer secret | From Daraja portal |
| `MPESA_SHORTCODE` | 174379 (sandbox) | Your business shortcode |
| `MPESA_PASSKEY` | See above (sandbox) | Lipa na M-Pesa passkey |

---

## 🧪 Step 5: Test in Sandbox

### Sandbox Test Credentials:

**Business Shortcode:** 174379  
**Passkey:** bfb279f9aa9bdbcf158e97dd71a467cd2e0c893059b10f78e6b72ada1ed2c919

**Test Phone Numbers:**
- Any number in format `254XXXXXXXXX`
- Example: `254708374149`
- **Note:** In sandbox, you won't receive an actual STK push, but the API will simulate success

### Testing Steps:

1. **Add product to cart**
2. **Go to checkout**
3. **Select "M-Pesa STK Push"**
4. **Enter test phone:** `254708374149`
5. **Click "Pay with M-Pesa"**
6. **Wait for confirmation** (auto-refreshes)
7. **Verify order status** changes to "Processing"
8. **Check payment status** shows "Paid"

---

## 🌐 Step 6: Expose Callback URL

M-Pesa needs to send payment confirmations to your server.

### Requirements:
- **HTTPS Required** (M-Pesa doesn't work with HTTP)
- **Publicly accessible** URL
- **No authentication** on callback endpoint

### Your Callback URLs:
```
https://yourdomain.com/mpesa/callback
```

### If using Koyeb:
- Your URL will be: `https://your-app-name.koyeb.app/mpesa/callback`
- HTTPS is automatic ✅
- Publicly accessible ✅

### Testing Callbacks Locally:
Use **ngrok** to expose your local server:
```bash
ngrok http 5000
```
Then use the ngrok URL as your callback URL.

---

## 📱 Step 7: Understanding the Flow

### Customer Experience:
```
1. Customer clicks "Pay with M-Pesa"
2. Enters phone number (254XXXXXXXXX)
3. Clicks "Pay Now"
4. Receives STK push on phone
5. Enters M-Pesa PIN
6. Payment processed
7. Redirected to order confirmation
```

### Backend Flow:
```
1. Customer submits checkout
   ↓
2. App creates order (status: Pending)
   ↓
3. App sends STK Push request to M-Pesa API
   ↓
4. M-Pesa sends push to customer's phone
   ↓
5. Customer enters PIN
   ↓
6. M-Pesa processes payment
   ↓
7. M-Pesa sends callback to your app
   ↓
8. App updates order status (Completed/Failed)
   ↓
9. App reduces stock (if successful)
   ↓
10. Customer sees confirmation
```

---

## 🔍 Step 8: Monitor & Debug

### Check Logs:
```bash
# View application logs
tail -f /var/log/yourapp.log

# Look for:
- "M-Pesa access token obtained successfully"
- "STK Push initiated successfully"
- "M-Pesa callback received"
- "M-Pesa payment completed"
```

### Common Errors:

| Error | Cause | Solution |
|-------|-------|----------|
| "Failed to get access token" | Wrong Consumer Key/Secret | Check credentials in .env |
| "Invalid phone number" | Wrong format | Use 254XXXXXXXXX format |
| "Insufficient funds" | Customer has no money | Ask customer to check M-Pesa balance |
| "User cancelled transaction" | Customer pressed Cancel | Normal - user chose not to pay |
| "Request timeout" | Customer didn't respond | They have 60 seconds to complete |
| "Internal server error" | Various issues | Check Safaricom status page |

---

## 💰 Transaction Fees

### Sandbox:
- **FREE** - No charges for testing

### Production:
- **Transaction Fee:** ~1.5% - 2% per transaction
- **Minimum Transaction:** Ksh 10
- **Maximum Transaction:** Ksh 150,000 per transaction
- **Settlement:** T+1 (Next business day)

**Note:** Fees vary based on your business agreement with Safaricom.

---

## 🔐 Security Best Practices

1. **HTTPS Only** - M-Pesa requires SSL/TLS
2. **Validate Callbacks** - Check all data from M-Pesa
3. **Log Everything** - Keep audit trail of all transactions
4. **Handle Timeouts** - User has 60 seconds to complete
5. **Idempotency** - Prevent duplicate payment processing
6. **Secure Credentials** - Never commit to Git
7. **IP Whitelisting** - Consider whitelisting M-Pesa IPs

### M-Pesa Callback IPs (for firewall whitelist):
```
196.201.214.200
196.201.214.206
196.201.213.114
196.201.214.207
196.201.214.208
196.201.213.44
196.201.212.127
196.201.212.138
196.201.212.129
196.201.212.136
196.201.212.74
196.201.212.69
```

---

## 🧪 Sandbox Test Scenarios

### Successful Payment:
- Phone: `254708374149`
- Amount: Any (e.g., 1000)
- Result: Success after ~5 seconds

### Failed Payment:
- Phone: `254799999999`
- Amount: Any
- Result: Simulated failure

### Timeout:
- Just wait without completing
- Result: Timeout after 60 seconds

---

## 📊 Admin Features

### What Admins Can See:
- Payment method used (M-Pesa STK)
- Payment status (Paid/Pending/Failed)
- M-Pesa receipt number
- Transaction amount
- Customer phone number
- Real-time payment confirmations

---

## 🔄 Going Live Checklist

Before enabling M-Pesa in production:

- [ ] Business registered with Safaricom
- [ ] M-Pesa Paybill/Till number obtained
- [ ] Production credentials from Daraja
- [ ] Production passkey from Safaricom
- [ ] Environment variables updated
- [ ] HTTPS enabled on domain
- [ ] Callback URL tested and working
- [ ] Thoroughly tested in sandbox
- [ ] Customer support ready
- [ ] Refund process documented
- [ ] Reconciliation process in place

---

## 🆘 Support & Resources

- **Daraja Portal:** https://developer.safaricom.co.ke/
- **Documentation:** https://developer.safaricom.co.ke/APIs/MpesaExpressSimulate
- **Support Email:** apisupport@safaricom.co.ke
- **Phone:** 0722 000 000

---

## 💡 Tips & Best Practices

1. **Test Thoroughly** - Use sandbox extensively before going live
2. **Handle All Scenarios** - Success, failure, timeout, cancellation
3. **User Communication** - Keep users informed during payment
4. **Fallback Options** - Offer alternative payment methods
5. **Monitor Closely** - Watch for failed transactions
6. **Reconciliation** - Daily reconciliation with M-Pesa statements
7. **Customer Service** - Quick response to payment issues

---

## ❓ FAQs

**Q: How long does STK Push take?**  
A: Usually 5-10 seconds if customer responds immediately.

**Q: What if customer doesn't receive push?**  
A: Check phone number format, network issues, or phone settings.

**Q: Can I refund payments?**  
A: Yes, but requires manual process through M-Pesa portal.

**Q: What's the difference between Paybill and Till?**  
A: Paybill is for larger businesses, Till for smaller. Both work similarly.

**Q: Do I need a business to test?**  
A: No, sandbox is available for anyone to test.

**Q: How do I switch from sandbox to production?**  
A: Change `MPESA_ENVIRONMENT` to `production` and update credentials.

---

**Document Version:** 1.0  
**Last Updated:** October 2025  
**Next Review:** Before production launch

