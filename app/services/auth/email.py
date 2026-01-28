import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class EmailService:
    """Service for sending emails"""
    
    def __init__(self):
        self.smtp_host = os.getenv("SMTP_HOST")
        self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
        self.smtp_user = os.getenv("SMTP_USER")
        self.smtp_password = os.getenv("SMTP_PASSWORD")
        self.email_from = os.getenv("EMAIL_FROM")
        self.email_from_name = os.getenv("EMAIL_FROM_NAME", "PromptForum")
    
    async def send_email(
        self,
        to_email: str,
        subject: str,
        html_content: str
    ) -> bool:
        """Send an email"""
        try:
            # Create message
            message = MIMEMultipart("alternative")
            message["Subject"] = subject
            message["From"] = f"{self.email_from_name} <{self.email_from}>"
            message["To"] = to_email
            
            # Add HTML content
            html_part = MIMEText(html_content, "html")
            message.attach(html_part)
            
            # Send email
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_user, self.smtp_password)
                server.send_message(message)
            
            return True
        except Exception as e:
            print(f"Error sending email: {e}")
            return False
    
    async def send_otp_email(self, to_email: str, otp_code: str) -> bool:
        """Send OTP verification email"""
        app_name = os.getenv("APP_NAME", "PromptForum")
        otp_expire_minutes = os.getenv("OTP_EXPIRE_MINUTES", "10")
        print(f"Sending OTP email to {to_email} with code {otp_code}")
        subject = f"Your {app_name} Verification Code"
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background-color: #4F46E5; color: white; padding: 20px; text-align: center; border-radius: 5px 5px 0 0; }}
                .content {{ background-color: #f9fafb; padding: 30px; border: 1px solid #e5e7eb; }}
                .otp-code {{ font-size: 32px; font-weight: bold; text-align: center; padding: 20px; background-color: white; border: 2px dashed #4F46E5; border-radius: 5px; margin: 20px 0; letter-spacing: 8px; }}
                .footer {{ text-align: center; padding: 20px; color: #6b7280; font-size: 14px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>{app_name}</h1>
                </div>
                <div class="content">
                    <h2>Verify Your Email</h2>
                    <p>Hello,</p>
                    <p>Thank you for signing up with {app_name}! To complete your registration, please use the verification code below:</p>
                    <div class="otp-code">{otp_code}</div>
                    <p>This code will expire in {otp_expire_minutes} minutes.</p>
                    <p>If you didn't request this code, please ignore this email.</p>
                </div>
                <div class="footer">
                    <p>&copy; 2024 {app_name}. All rights reserved.</p>
                </div>
            </div>
        </body>
        </html>
        """
        return await self.send_email(to_email, subject, html_content)
    
    async def send_password_reset_email(self, to_email: str, otp_code: str) -> bool:
        """Send password reset email"""
        app_name = os.getenv("APP_NAME", "PromptForum")
        otp_expire_minutes = os.getenv("OTP_EXPIRE_MINUTES", "10")
        
        subject = f"Reset Your {app_name} Password"
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background-color: #DC2626; color: white; padding: 20px; text-align: center; border-radius: 5px 5px 0 0; }}
                .content {{ background-color: #f9fafb; padding: 30px; border: 1px solid #e5e7eb; }}
                .otp-code {{ font-size: 32px; font-weight: bold; text-align: center; padding: 20px; background-color: white; border: 2px dashed #DC2626; border-radius: 5px; margin: 20px 0; letter-spacing: 8px; }}
                .footer {{ text-align: center; padding: 20px; color: #6b7280; font-size: 14px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Password Reset</h1>
                </div>
                <div class="content">
                    <h2>Reset Your Password</h2>
                    <p>Hello,</p>
                    <p>We received a request to reset your password. Use the code below to proceed:</p>
                    <div class="otp-code">{otp_code}</div>
                    <p>This code will expire in {otp_expire_minutes} minutes.</p>
                    <p>If you didn't request a password reset, please ignore this email or contact support if you have concerns.</p>
                </div>
                <div class="footer">
                    <p>&copy; 2024 {app_name}. All rights reserved.</p>
                </div>
            </div>
        </body>
        </html>
        """
        return await self.send_email(to_email, subject, html_content)
    
    async def send_welcome_email(self, to_email: str, full_name: str = None) -> bool:
        """Send welcome email after successful verification"""
        app_name = os.getenv("APP_NAME", "PromptForum")
        name = full_name if full_name else "there"
        
        subject = f"Welcome to {app_name}!"
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background-color: #10B981; color: white; padding: 20px; text-align: center; border-radius: 5px 5px 0 0; }}
                .content {{ background-color: #f9fafb; padding: 30px; border: 1px solid #e5e7eb; }}
                .footer {{ text-align: center; padding: 20px; color: #6b7280; font-size: 14px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Welcome to {app_name}!</h1>
                </div>
                <div class="content">
                    <h2>Hello {name},</h2>
                    <p>Your account has been successfully verified! 🎉</p>
                    <p>You can now enjoy all the features of {app_name}.</p>
                    <p>If you have any questions or need assistance, feel free to reach out to our support team.</p>
                </div>
                <div class="footer">
                    <p>&copy; 2024 {app_name}. All rights reserved.</p>
                </div>
            </div>
        </body>
        </html>
        """
        return await self.send_email(to_email, subject, html_content)


email_service = EmailService()
