"""
Email Service Module
Handles sending emails for application confirmations and notifications
"""
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
import os

SENDER_EMAIL = os.environ.get("SENDER_EMAIL")
SENDER_PASSWORD = os.environ.get("SENDER_PASSWORD")
print('SENDER_EMAIL:',SENDER_EMAIL)
print('SENDER_PASSWORD:',SENDER_PASSWORD)
# SMTP Configuration
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SENDER_EMAIL = "espiritujoseph008@gmail.com"
SENDER_PASSWORD = "oqan sgvo qwnn agfw"

def send_application_confirmation_email(student_email, student_name, student_type, course_choices):
    """
    Send an email confirmation to the student regarding their successful application.
    
    Args:
        student_email (str): The email address of the student
        student_name (str): The full name of the student
        student_type (str): Type of student (FRESHMEN or TRANSFEREE)
        course_choices (list): List of course choices [choice1, choice2, choice3]
    
    Returns:
        tuple: (success: bool, message: str)
    """
    try:
        # Create email message
        message = MIMEMultipart("alternative")
        message["Subject"] = "Application Submission Confirmation - Norzagaray College"
        message["From"] = "Norzagaray College Registrar's Office"
        message["To"] = student_email
        
        # Format course choices for display
        course_list = "\n".join([f"{i+1}. {course}" for i, course in enumerate(course_choices) if course])
        
        # Create HTML email body
        html_body = f"""
        <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                <div style="max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #ddd; border-radius: 8px;">
                    <h2 style="color: #004b87; border-bottom: 3px solid #004b87; padding-bottom: 10px;">
                        Application Submission Confirmation
                    </h2>
                    
                    <p>Dear <strong>{student_name}</strong>,</p>
                    
                    <p>Thank you for submitting your application to <strong>Norzagaray College</strong>. We are pleased to confirm that your application has been successfully received and processed.</p>
                    
                    <div style="background-color: #f0f0f0; padding: 15px; border-left: 4px solid #004b87; margin: 20px 0;">
                        <h3 style="margin-top: 0; color: #004b87;">Application Details:</h3>
                        <p><strong>Applicant Name:</strong> {student_name}</p>
                        <p><strong>Email Address:</strong> {student_email}</p>
                        <p><strong>Student Type:</strong> {student_type}</p>
                        <p><strong>Application Date:</strong> {datetime.now().strftime('%B %d, %Y')}</p>
                        <p><strong>Application Status:</strong> <span style="color: #28a745; font-weight: bold;">PENDING VERIFICATION</span></p>
                    </div>
                    
                    <h3 style="color: #004b87;">Course Preferences:</h3>
                    <p>{course_list if course_list else "No courses selected"}</p>
                    
                    <div style="background-color: #e8f4f8; padding: 15px; border-radius: 5px; margin: 20px 0;">
                        <h3 style="margin-top: 0; color: #004b87;">What's Next?</h3>
                        <ul>
                            <li>Our admissions team will review your application</li>
                            <li>You will receive updates via email about your application status</li>
                            <li>Please monitor your email inbox and spam folder for updates</li>
                            <li>If you have any questions, please contact us at the registrar's office</li>
                        </ul>
                    </div>
                    
                    <p style="margin-top: 30px; padding-top: 20px; border-top: 1px solid #ddd; font-size: 12px; color: #666;">
                        <strong>Norzagaray College</strong><br>
                        Registrar's Office<br>
                        <em>This is an automated message. Please do not reply directly to this email.</em>
                        <em>Replies to this message are routed to an unmonitored mailbox.</em>
                        <em>If you have any questions, please contact us at the registrar's office.</em>
                    </p>
                </div>
            </body>
        </html>
        """
        
        # Create plain text version as fallback
        text_body = f"""
Application Submission Confirmation - Norzagaray College

Dear {student_name},

Thank you for submitting your application to Norzagaray College. We are pleased to confirm that your application has been successfully received and processed.

Application Details:
- Applicant Name: {student_name}
- Email Address: {student_email}
- Student Type: {student_type}
- Application Date: {datetime.now().strftime('%B %d, %Y')}
- Application Status: PENDING VERIFICATION

Course Preferences:
{course_list if course_list else "No courses selected"}

What's Next?
- Our admissions team will review your application
- You will receive updates via email about your application status
- Please monitor your email inbox and spam folder for updates
- If you have any questions, please contact us at the registrar's office

Best regards,
Norzagaray College
Registrar's Office

This is an automated message. Please do not reply directly to this email.
        """
        
        # Attach both plain text and HTML versions
        part1 = MIMEText(text_body, "plain")
        part2 = MIMEText(html_body, "html")
        message.attach(part1)
        message.attach(part2)
        
        # Connect to SMTP server and send email
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()  # Secure the connection
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.send_message(message)
        
        return True, "Email sent successfully"
    
    except smtplib.SMTPAuthenticationError:
        error_msg = "SMTP Authentication failed. Please check email credentials."
        print(f"Email Error: {error_msg}")
        return False, error_msg
    
    except smtplib.SMTPException as e:
        error_msg = f"SMTP error occurred: {str(e)}"
        print(f"Email Error: {error_msg}")
        return False, error_msg
    
    except Exception as e:
        error_msg = f"Failed to send email: {str(e)}"
        print(f"Email Error: {error_msg}")
        return False, error_msg


def send_enrollment_confirmation_email(student_email, student_name):
    """
    Send an email confirmation for successful enrollment.
    
    Args:
        student_email (str): The email address of the student
        student_name (str): The full name of the student
    
    Returns:
        tuple: (success: bool, message: str)
    """
    try:
        # Create email message
        message = MIMEMultipart("alternative")
        message["Subject"] = "Enrollment Confirmation - Norzagaray College"
        message["From"] = "Norzagaray College Registrar's Office"
        message["To"] = student_email
        
        # Create HTML email body
        html_body = f"""
        <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                <div style="max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #ddd; border-radius: 8px;">
                    <h2 style="color: #004b87; border-bottom: 3px solid #004b87; padding-bottom: 10px;">
                        Enrollment Confirmation
                    </h2>
                    
                    <p>Dear <strong>{student_name}</strong>,</p>
                    
                    <p>Congratulations! Your enrollment at <strong>Norzagaray College</strong> has been successfully processed and confirmed.</p>
                    
                    <div style="background-color: #d4edda; padding: 15px; border-left: 4px solid #28a745; margin: 20px 0;">
                        <h3 style="margin-top: 0; color: #155724;">Enrollment Status: <span style="color: #28a745; font-weight: bold;">CONFIRMED</span></h3>
                        <p><strong>Enrollment Date:</strong> {datetime.now().strftime('%B %d, %Y')}</p>
                    </div>
                    
                    <div style="background-color: #e8f4f8; padding: 15px; border-radius: 5px; margin: 20px 0;">
                        <h3 style="margin-top: 0; color: #004b87;">Important Information:</h3>
                        <ul>
                            <li>Your Certificate of Enrollment (COR) has been generated</li>
                            <li>Please check your email for your COR attachment</li>
                            <li>Keep your COR for registration and official transactions</li>
                            <li>Contact the registrar's office if you have any concerns</li>
                        </ul>
                    </div>
                    
                    <p style="margin-top: 30px; padding-top: 20px; border-top: 1px solid #ddd; font-size: 12px; color: #666;">
                        <strong>Norzagaray College</strong><br>
                        Registrar's Office<br>
                        <em>This is an automated message. Please do not reply directly to this email.</em>
                    </p>
                </div>
            </body>
        </html>
        """
        
        # Create plain text version
        text_body = f"""
Enrollment Confirmation - Norzagaray College

Dear {student_name},

Congratulations! Your enrollment at Norzagaray College has been successfully processed and confirmed.

Enrollment Status: CONFIRMED
Enrollment Date: {datetime.now().strftime('%B %d, %Y')}

Important Information:
- Your Certificate of Enrollment (COR) has been generated
- Please check your email for your COR attachment
- Keep your COR for registration and official transactions
- Contact the registrar's office if you have any concerns

Best regards,
Norzagaray College
Registrar's Office

This is an automated message. Please do not reply directly to this email.
        """
        
        # Attach both versions
        part1 = MIMEText(text_body, "plain")
        part2 = MIMEText(html_body, "html")
        message.attach(part1)
        message.attach(part2)
        
        # Send email
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.send_message(message)
        
        return True, "Email sent successfully"
    
    except Exception as e:
        error_msg = f"Failed to send enrollment email: {str(e)}"
        print(f"Email Error: {error_msg}")
        return False, error_msg
