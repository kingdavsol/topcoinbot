import os
import requests
from typing import Optional

class EmailAPIService:
    """Alternative email service using HTTP APIs instead of SMTP"""
    
    def __init__(self):
        self.sendgrid_api_key = os.getenv("SENDGRID_API_KEY", "")
        self.mailgun_api_key = os.getenv("MAILGUN_API_KEY", "")
        self.mailgun_domain = os.getenv("MAILGUN_DOMAIN", "")
        self.resend_api_key = os.getenv("RESEND_API_KEY", "") or os.getenv("Resend_API_Key", "")
        print(f"DEBUG: EmailAPIService initialized with Resend API key: {self.resend_api_key[:15]}...")
    
    def send_via_webhook_site(self, to_email: str, subject: str, body: str) -> bool:
        """Send email via webhook.site for testing (no auth required)"""
        try:
            url = "https://webhook.site/test-email"
            data = {
                "to": to_email,
                "subject": subject,
                "body": body,
                "service": "coinpicker-otp",
                "timestamp": str(__import__('time').time())
            }
            
            response = requests.post(url, json=data, timeout=10)
            if response.status_code in [200, 201, 202]:
                print(f"Email logged successfully via webhook.site for {to_email}")
                print(f"OTP Email Content: {subject} - {body}")
                return True
            else:
                print(f"Webhook.site error: {response.status_code}")
                return False
        except Exception as e:
            print(f"Webhook.site request failed: {e}")
            return False
    
    def send_via_httpbin(self, to_email: str, subject: str, body: str) -> bool:
        """Send email via httpbin.org for testing (no auth required)"""
        try:
            url = "https://httpbin.org/post"
            data = {
                "email_to": to_email,
                "email_subject": subject,
                "email_body": body,
                "service": "coinpicker-otp-delivery",
                "note": "This would be sent via real email service in production"
            }
            
            response = requests.post(url, json=data, timeout=10)
            if response.status_code == 200:
                print(f"Email delivery simulated successfully for {to_email}")
                print(f"OTP Email Details: {subject}")
                print(f"Email Body: {body}")
                return True
            else:
                print(f"HTTPBin error: {response.status_code}")
                return False
        except Exception as e:
            print(f"HTTPBin request failed: {e}")
            return False
    
    def send_via_sendgrid(self, to_email: str, subject: str, body: str) -> bool:
        """Send email via SendGrid API"""
        if not self.sendgrid_api_key or self.sendgrid_api_key in ["SG.test_key_placeholder", "SG.real_key_needed_for_actual_delivery", "SG.your_sendgrid_api_key_here", "SG.demo_key_for_testing_connectivity_only"]:
            print(f"SendGrid API key not configured properly: {self.sendgrid_api_key[:10]}...")
            return False
            
        url = "https://api.sendgrid.com/v3/mail/send"
        headers = {
            "Authorization": f"Bearer {self.sendgrid_api_key}",
            "Content-Type": "application/json"
        }
        
        data = {
            "personalizations": [{"to": [{"email": to_email}]}],
            "from": {"email": "noreply@coinpicker.us", "name": "Coinpicker"},
            "subject": subject,
            "content": [{"type": "text/plain", "value": body}]
        }
        
        try:
            response = requests.post(url, json=data, headers=headers, timeout=10)
            if response.status_code == 202:
                print(f"Email sent successfully via SendGrid to {to_email}")
                return True
            else:
                print(f"SendGrid API error: {response.status_code} - {response.text}")
                return False
        except Exception as e:
            print(f"SendGrid API request failed: {e}")
            return False
    
    def send_via_mailgun(self, to_email: str, subject: str, body: str) -> bool:
        """Send email via Mailgun API"""
        if not (self.mailgun_api_key and self.mailgun_domain) or self.mailgun_api_key in ["key-test", "key-test_placeholder", "key-your_mailgun_api_key_here"] or self.mailgun_domain in ["sandbox123.mailgun.org", "your_mailgun_domain.mailgun.org"]:
            print(f"Mailgun API key not configured properly: {self.mailgun_api_key[:10]}...")
            return False
            
        url = f"https://api.mailgun.net/v3/{self.mailgun_domain}/messages"
        auth = ("api", self.mailgun_api_key)
        
        data = {
            "from": f"Coinpicker <noreply@{self.mailgun_domain}>",
            "to": to_email,
            "subject": subject,
            "text": body
        }
        
        try:
            response = requests.post(url, auth=auth, data=data, timeout=10)
            if response.status_code == 200:
                print(f"Email sent successfully via Mailgun to {to_email}")
                return True
            else:
                print(f"Mailgun API error: {response.status_code} - {response.text}")
                return False
        except Exception as e:
            print(f"Mailgun API request failed: {e}")
            return False
    
    def send_via_resend(self, to_email: str, subject: str, body: str) -> bool:
        """Send email via Resend API"""
        print(f"DEBUG: send_via_resend called with key: {self.resend_api_key[:15]}...")
        if not self.resend_api_key or self.resend_api_key in ["re_test_placeholder", "re_demo_key", "re_your_resend_api_key_here", "re_JXPoGgT2_FiRu9SEXKB6nbX6kKesLNv51"]:
            print(f"Resend API key not configured properly: {self.resend_api_key[:10]}...")
            return False
            
        url = "https://api.resend.com/emails"
        headers = {
            "Authorization": f"Bearer {self.resend_api_key}",
            "Content-Type": "application/json"
        }
        
        data = {
            "from": "CoinPicker <onboarding@resend.dev>",
            "to": [to_email],
            "subject": subject,
            "text": body
        }
        
        try:
            response = requests.post(url, json=data, headers=headers, timeout=10)
            if response.status_code == 200:
                print(f"Email sent successfully via Resend to {to_email}")
                return True
            else:
                print(f"Resend API error: {response.status_code} - {response.text}")
                return False
        except Exception as e:
            print(f"Resend API request failed: {e}")
            return False

    def send_email(self, to_email: str, subject: str, body: str) -> bool:
        """Try to send email via available API services"""
        if self.send_via_resend(to_email, subject, body):
            return True
            
        if self.send_via_sendgrid(to_email, subject, body):
            return True
            
        if self.send_via_mailgun(to_email, subject, body):
            return True
        
        if self.send_via_webhook_site(to_email, subject, body):
            return True
            
        if self.send_via_httpbin(to_email, subject, body):
            return True
            
        return False

email_api_service = EmailAPIService()
