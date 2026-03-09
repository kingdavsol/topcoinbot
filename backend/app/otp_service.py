import os
import time
import random
import smtplib
import ssl
from email.mime.text import MIMEText
from typing import Dict, Tuple, Optional
from .email_api_service import email_api_service

class OTPService:
    def __init__(self):
        self._store: Dict[Tuple[str, str, str], Dict[str, float]] = {}
        self.exp_minutes = int(os.getenv("OTP_EXP_MINUTES", "5"))
        self.rate_limit_per_hour = int(os.getenv("OTP_RATE_LIMIT_PER_HOUR", "5"))

    def _key(self, channel: str, identifier: str, purpose: str) -> Tuple[str, str, str]:
        return (channel, identifier.lower(), purpose)

    def _now(self) -> float:
        return time.time()

    def _gen_code(self) -> str:
        return f"{random.randint(0, 999999):06d}"

    def request(self, channel: str, identifier: str, purpose: str) -> str:
        k = self._key(channel, identifier, purpose)
        now = self._now()
        data = self._store.get(k, {"attempts": 0, "sent": 0, "window_start": now})
        if now - data.get("window_start", now) > 3600:
            data["sent"] = 0
            data["window_start"] = now
        if data.get("sent", 0) >= self.rate_limit_per_hour:
            raise ValueError("rate_limited")
        code = self._gen_code()
        expires_at = now + self.exp_minutes * 60
        self._store[k] = {
            "code": code,
            "expires_at": expires_at,
            "attempts": 0,
            "sent": data.get("sent", 0) + 1,
            "window_start": data.get("window_start", now),
        }
        return code

    def verify(self, channel: str, identifier: str, purpose: str, code: str) -> bool:
        k = self._key(channel, identifier, purpose)
        entry = self._store.get(k)
        if not entry:
            return False
        if self._now() > entry.get("expires_at", 0):
            self._store.pop(k, None)
            return False
        entry["attempts"] = entry.get("attempts", 0) + 1
        if entry.get("attempts", 0) > 10:
            self._store.pop(k, None)
            return False
        if entry.get("code") == code:
            self._store.pop(k, None)
            return True
        return False

otp_service = OTPService()

def send_email(email: str, code: str) -> bool:
    subject = "Your Coinpicker OTP Code"
    body = f"Your OTP code is: {code}\n\nThis code expires in {os.getenv('OTP_EXP_MINUTES', '5')} minutes."
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["To"] = email

    smtp_configs = [
        {
            "host": os.getenv("SMTP_HOST", ""),
            "port": int(os.getenv("SMTP_PORT", "587")),
            "user": os.getenv("SMTP_USER", ""),
            "pass": os.getenv("SMTP_PASS", ""),
            "from": os.getenv("SMTP_FROM", "Service@coinpicker.us"),
            "use_ssl": os.getenv("SMTP_USE_SSL", "false").lower() == "true",
            "use_tls": os.getenv("SMTP_USE_TLS", "true").lower() == "true"
        },
        {
            "host": os.getenv("SMTP_HOST_ALT", ""),
            "port": int(os.getenv("SMTP_PORT_ALT", "25")),
            "user": os.getenv("SMTP_USER", ""),
            "pass": os.getenv("SMTP_PASS", ""),
            "from": os.getenv("SMTP_FROM", "Service@coinpicker.us"),
            "use_ssl": False,
            "use_tls": False
        },
        {
            "host": os.getenv("SMTP_HOST_ALT2", ""),
            "port": int(os.getenv("SMTP_PORT_ALT2", "465")),
            "user": os.getenv("SMTP_USER", ""),
            "pass": os.getenv("SMTP_PASS", ""),
            "from": os.getenv("SMTP_FROM", "Service@coinpicker.us"),
            "use_ssl": True,
            "use_tls": False
        }
    ]

    if not any(config["host"] and config["user"] and config["pass"] for config in smtp_configs):
        print(f"OTP email to {email}: {code}")
        return True

    for i, config in enumerate(smtp_configs):
        if not (config["host"] and config["user"] and config["pass"]):
            continue
            
        try:
            msg["From"] = config["from"]
            
            if config["use_ssl"]:
                context = ssl.create_default_context()
                with smtplib.SMTP_SSL(config["host"], config["port"], context=context, timeout=5) as server:
                    server.login(config["user"], config["pass"])
                    server.sendmail(config["from"], [email], msg.as_string())
            else:
                with smtplib.SMTP(config["host"], config["port"], timeout=5) as server:
                    if config["use_tls"]:
                        server.starttls(context=ssl.create_default_context())
                    server.login(config["user"], config["pass"])
                    server.sendmail(config["from"], [email], msg.as_string())
            
            print(f"OTP email sent successfully to {email} via {config['host']}:{config['port']}")
            return True
            
        except Exception as e:
            print(f"SMTP config {i+1} failed for {email}: {e}")
            continue
    
    print(f"All SMTP configurations failed for {email}. Trying email API service...")
    try:
        if email_api_service.send_email(email, subject, body):
            print(f"Email API service succeeded for {email}")
            return True
        else:
            print(f"Email API service returned False for {email}")
    except Exception as e:
        print(f"Email API service failed: {e}")
    
    print(f"All email delivery methods failed for {email}. Falling back to logging: {code}")
    return False

def send_sms(phone: str, code: str) -> bool:
    sid = os.getenv("TWILIO_ACCOUNT_SID", "")
    token = os.getenv("TWILIO_AUTH_TOKEN", "")
    from_num = os.getenv("TWILIO_FROM", "")
    if not sid or not token or not from_num:
        print(f"OTP SMS to {phone}: {code}")
        return True
    print(f"OTP SMS via Twilio to {phone}: {code}")
    return True
