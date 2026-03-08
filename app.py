from flask import Flask, request, jsonify, render_template
import mysql.connector
from datetime import date, datetime
from email_service import send_application_confirmation_email
from PIL import Image
import io
import os

def parse_birthdate(raw):
    """Convert any birthdate string to YYYY-MM-DD for MySQL.
    Handles: 'March 23, 2000', '2000-03-23', '03/23/2000', '23/03/2000'
    Returns None if empty or unparseable.
    """
    if not raw or not raw.strip():
        return None
    raw = raw.strip()
    for fmt in ('%B %d, %Y', '%Y-%m-%d', '%m/%d/%Y', '%d/%m/%Y', '%m-%d-%Y'):
        try:
            return datetime.strptime(raw, fmt).strftime('%Y-%m-%d')
        except ValueError:
            continue
    return None

def get_db_connection():
    conn = mysql.connector.connect(
        host=os.environ.get("DB_HOST"),
        user=os.environ.get("DB_USER"),
        password=os.environ.get("DB_PASSWORD"),
        database=os.environ.get("DB_NAME", "ncems"),
        port=int(os.environ.get("DB_PORT", 3306))
    )
    return conn

def get_db_connectionforlocation():
    return mysql.connector.connect(
        host=os.environ.get("DB_HOST"),
        user=os.environ.get("DB_USER"),
        password=os.environ.get("DB_PASSWORD"),
        database=os.environ.get("DB_NAME_LOCATION", "psgc_db"),
        port=int(os.environ.get("DB_PORT", 3306))
    )
app = Flask(__name__)
app_secret_key = "your_secret_key_here"


@app.route('/api/provinces')
def get_provinces():
    """Return all provinces"""
    conn = get_db_connectionforlocation()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT code, name FROM provinces ORDER BY name")
    provinces = cursor.fetchall()
    cursor.close()
    conn.close()
    return jsonify(provinces)

@app.route('/api/municipalities/<province_code>')
def get_municipalities(province_code):
    """Return municipalities for a given province"""
    conn = get_db_connectionforlocation()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT code, name FROM municipalities WHERE provinceCode = %s ORDER BY name", (province_code,))
    municipalities = cursor.fetchall()
    cursor.close()
    conn.close()
    return jsonify(municipalities)

@app.route('/api/barangays/<municipality_code>')
def get_barangays(municipality_code):
    """Return barangays for a given municipality"""
    conn = get_db_connectionforlocation()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT code, name FROM barangays WHERE municipalityCode = %s ORDER BY name", (municipality_code,))
    barangays = cursor.fetchall()
    cursor.close()
    conn.close()
    return jsonify(barangays)

@app.route("/")
def index():
    return render_template("enrollment.html")

@app.route("/login", methods=["POST"])
def login():
    global email
    email = request.form.get("email", "").strip()

    conn   = None
    cursor = None
    try:
        conn   = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # ── Check if email exists in STUDENTS ──────────────────────────────
        cursor.execute(
            "SELECT student_email, student_status, student_type FROM students WHERE student_email = %s",
            (email,)
        )
        student = cursor.fetchone()

        if student:
            # ── Fetch school status (enrollment) ───────────────────────────
            cursor.execute("SELECT Enrollment, academic_year, semester FROM school_status ORDER BY id DESC LIMIT 1")
            school_status = cursor.fetchone()

            if not school_status or school_status["Enrollment"] == 0:
                return jsonify({
                    "type": "error",
                    "message": "Norzagaray College is not yet accepting enrollment as of the moment. Please wait for further announcements."
                })

            if student["student_type"].upper() != "REGULAR":
                return jsonify({
                    "type": "error",
                    "message": "Your account is not eligible for online enrollment. Please contact your college adviser for enrollment."
                })

            status = student["student_status"].upper()
            print(f"DEBUG: Student found with email {email}, status: {status}")

            if status == "ENROLLED":
                return jsonify({
                    "type": "warning",
                    "message": "You are already Enrolled, kindly check your email for your COR."
                })
            elif status == "ENROLLEE":
                return jsonify({
                    "type": "info",
                    "message": "You already applied for Enrollment. Please wait for the Registrar's verification."
                })
            elif status == "INACTIVE":
                return jsonify({
                    "type": "info",
                    "message": "You are marked as inactive. Please approach the Registrar's Office."
                })
            elif status == "UNENROLLED":
                # Fetch full student details for the confirmation modal
                cursor.execute("""
                    SELECT student_number, student_firstname, student_lastname,
                           student_middlename, student_course, student_yearlevel,
                           student_section, student_curriculum
                    FROM students WHERE student_email = %s
                """, (email,))
                stu = cursor.fetchone()

                if not stu:
                    return jsonify({"type": "error", "message": "Student record not found. Please contact the Registrar."})

                return jsonify({
                    "type":           "enroll_confirm",
                    "student_number": stu["student_number"],
                    "student_name":   f"{stu['student_firstname']} {stu['student_middlename'] or ''} {stu['student_lastname']}".strip(),
                    "course":         stu["student_course"],
                    "year_level":     stu["student_yearlevel"],
                    "section":        stu["student_section"],
                    "curriculum":     stu["student_curriculum"],
                    "academic_year":  school_status.get("academic_year", "N/A"),
                    "semester":       school_status.get("semester", "N/A"),
                    "email":          email,
                })

        else:
            # ── Email not in STUDENTS — check ADMISSIONS ────────────────────
            cursor.execute("SELECT student_email FROM admissions WHERE student_email = %s", (email,))
            admission = cursor.fetchone()

            if admission:
                return jsonify({
                    "type": "error",
                    "message": "This email is already used for an admission application. Please check your email for updates or visit the Registrar's Office."
                })

            # Check if admissions are open
            cursor.execute("SELECT Admission FROM school_status ORDER BY id DESC LIMIT 1")
            school_status = cursor.fetchone()

            if not school_status or school_status["Admission"] == 0:
                return jsonify({
                    "type": "error",
                    "message": "Norzagaray College is not yet accepting admissions as of the moment. Please wait for further announcements."
                })

            return jsonify({
                "type":    "question",
                "message": "Are you a new student?",
                "options": ["FRESHMEN", "TRANSFEREE"]
            })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            "type":    "error",
            "message": f"A server error occurred. Please try again later. ({type(e).__name__})"
        }), 500
    finally:
        try:
            if cursor: cursor.close()
            if conn:   conn.close()
        except Exception:
            pass

@app.route("/transferee.html", methods=["GET", "POST"])
def transferee():
    email = request.args.get("email", "")
    print("Transferee Email: ",email)
    return render_template("transferee.html", email=email)

@app.route("/freshmen.html", methods=["GET", "POST"])
def freshmen():
    email = request.args.get("email", "")
    print("Freshmen Email: ",email)
    return render_template("freshmen.html", email=email)

@app.route("/admissionfreshmen", methods=["POST"])
def admission_freshmen():
    try:
        # Get all form data
        last_name = request.form.get("last_name")
        first_name = request.form.get("first_name")
        middle_name = request.form.get("middle_name")
        suffix = request.form.get("suffix")
        civil_status = request.form.get("civil_status")
        gender = request.form.get("gender")
        birthdate = parse_birthdate(request.form.get("birthdate", ""))
        age = request.form.get("age")
        nationality = request.form.get("nationality")
        religion = request.form.get("religion")
        disability = request.form.get("disability")
        email = request.form.get("email")
        contact_number = request.form.get("contact_number")
        house_number = request.form.get("house_number")
        streetorvillage = request.form.get("streetorvillage")
        barangay = request.form.get("barangay")
        municipality = request.form.get("municipality")
        province = request.form.get("province")
        country = request.form.get("country")
        zipcode = request.form.get("zipcode")
        father_lastname = request.form.get("father_lastname")
        father_firstname = request.form.get("father_firstname")
        father_middlename = request.form.get("father_middlename")
        father_age = request.form.get("father_age")
        father_email = request.form.get("father_email")
        father_contact_number = request.form.get("father_contact_number")
        father_occupation = request.form.get("father_occupation")
        father_education = request.form.get("father_education")
        mother_lastname = request.form.get("mother_lastname")
        mother_firstname = request.form.get("mother_firstname")
        mother_middlename = request.form.get("mother_middlename")
        mother_age = request.form.get("mother_age")
        mother_email = request.form.get("mother_email")
        mother_contact_number = request.form.get("mother_contact_number")
        mother_occupation = request.form.get("mother_occupation")
        mother_education = request.form.get("mother_education")
        last_school_attended = request.form.get("last_school_attended")
        last_school_type = request.form.get("last_school_type")
        last_school_address = request.form.get("last_school_address")
        academic_strand = request.form.get("academic_strand")
        course_first = request.form.get("course_first")
        course_second = request.form.get("course_second")
        course_third = request.form.get("course_third")
        
        student_type = "Freshmen"
        
        # Function to read and compress uploaded files before storing
        def read_file(name):
            f = request.files.get(name)
            if not f or not f.filename:
                return None
            raw = f.read()
            ext = f.filename.rsplit(".", 1)[-1].lower()
            # Compress images (jpg/png); leave PDFs as-is but warn if too large
            if ext in ("jpg", "jpeg", "png"):
                try:
                    img = Image.open(io.BytesIO(raw))
                    img = img.convert("RGB")
                    # Resize if larger than 1200px on longest side
                    max_px = 1200
                    if max(img.size) > max_px:
                        img.thumbnail((max_px, max_px), Image.LANCZOS)
                    buf = io.BytesIO()
                    img.save(buf, format="JPEG", quality=75, optimize=True)
                    compressed = buf.getvalue()
                    print(f"DEBUG: {name} compressed {len(raw)//1024}KB -> {len(compressed)//1024}KB")
                    return compressed
                except Exception as img_err:
                    print(f"DEBUG: Image compress failed for {name}: {img_err}")
                    return raw
            return raw
        
        # Read freshmen required files
        stu_coe = read_file("stuCOE")
        stu_pic = read_file("stuPic")
        stu_good_moral = read_file("stuGoodMoral")
        stu_psa = read_file("stuPSA")
        stu_form137 = read_file("stuForm137")
        
        # Transferee-specific files set to None
        stu_hon_dis = None
        stu_cog = None
        
        print(f"DEBUG: Freshmen admission - About to insert data for {first_name} {last_name}")
        print(f"DEBUG: Email: {email}")
        print(f"DEBUG: Student Type: {student_type}")
        
        # Connect to database
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Prepare data tuple
        data_tuple = (
            last_name, first_name, middle_name, suffix,
            gender, birthdate, age, civil_status, nationality, religion, disability,
            email, contact_number,
            house_number, streetorvillage, barangay, municipality, province, country, zipcode,
            father_lastname, father_firstname, father_middlename,
            father_age, father_email, father_contact_number, father_occupation, father_education,
            mother_lastname, mother_firstname, mother_middlename,
            mother_age, mother_email, mother_contact_number, mother_occupation, mother_education,
            last_school_attended, last_school_type, last_school_address, academic_strand,
            course_first, course_second, course_third,
            student_type,
            stu_pic, stu_psa, stu_good_moral, stu_form137, stu_coe, stu_hon_dis, stu_cog, date.today()
        )
        
        # SQL Insert statement
        sql = """
        INSERT INTO `admissions`(
            `student_lastname`, `student_firstname`, `student_middlename`, `student_suffix`,
            `student_gender`, `student_birthdate`, `student_age`, `student_civilstatus`, `student_nationality`, `student_religion`, `student_dissability`, 
            `student_email`, `student_contactnumber`, 
            `student_address_house_number`, `student_address_streetorvillage`, `student_address_barangay`, `student_address_municipalityorcity`, `student_address_province`, `student_address_country`, `student_address_zipcode`, 
            `student_father_lastname`, `student_father_firstname`, `student_father_middlename`, 
            `student_father_age`, `student_father_email`, `student_father_contactnumber`, `student_father_occupation`, `student_father_education`, 
            `student_mother_lastname`, `student_mother_firstname`, `student_mother_middlename`, 
            `student_mother_age`, `student_mother_email`, `student_mother_contactnumber`, `student_mother_occupation`, `student_mother_education`, 
            `student_lastschool_attended`, `student_lastschool_type`, `student_lastschool_address`, `student_academic_strand`, 
            `student_course_choice1`, `student_course_choice2`, `student_course_choice3`, 
            `student_type`, 
            `student_picture`, `student_psa`, `student_goodmoral`, `student_form138`, `student_certificateofenrollment`, `student_honorabledismissal`, `student_certificateofgrade`, `student_date_submitted`, `student_admission_status`
        )
        VALUES (
            %s, %s, %s, %s,
            %s, %s, %s, %s, %s, %s, %s,
            %s, %s,
            %s, %s, %s, %s, %s, %s, %s,
            %s, %s, %s,
            %s, %s, %s, %s, %s,
            %s, %s, %s,
            %s, %s, %s, %s, %s,
            %s, %s, %s, %s,
            %s, %s, %s,
            %s,
            %s, %s, %s, %s, %s, %s, %s, %s, 'Pending'
        )
        """
        
        cursor.execute(sql, data_tuple)
        conn.commit()
        print(f"DEBUG: Successfully inserted Freshmen record for {first_name} {last_name}")
        
        # Send confirmation email to the student
        course_choices = [course_first, course_second, course_third]
        full_name = f"{first_name} {middle_name} {last_name}".strip()
        
        email_success, email_message = send_application_confirmation_email(
            student_email=email,
            student_name=full_name,
            student_type=student_type,
            course_choices=course_choices
        )
        
        if email_success:
            print(f"DEBUG: Confirmation email sent successfully to {email}")
        else:
            print(f"DEBUG: Email sending failed - {email_message}")
        
        cursor.close()
        conn.close()
        
        return jsonify({
            "success": True,
            "message": "Your application has been submitted successfully! Please check your email for updates regarding your application."
        })
        
    except mysql.connector.Error as db_error:
        print(f"DEBUG: Database error: {str(db_error)}")
        return jsonify({
            "success": False,
            "message": f"Database error: {str(db_error)}"
        }), 500
    except Exception as e:
        print(f"DEBUG: Exception error: {str(e)}")
        return jsonify({
            "success": False,
            "message": f"Error: {str(e)}"
        }), 500

@app.route("/admissiontransferee", methods=["POST"])
def admission_transferee():
    try:
        # Get all form data
        last_name = request.form.get("last_name")
        first_name = request.form.get("first_name")
        middle_name = request.form.get("middle_name")
        suffix = request.form.get("suffix")
        civil_status = request.form.get("civil_status")
        gender = request.form.get("gender")
        birthdate = parse_birthdate(request.form.get("birthdate", ""))
        age = request.form.get("age")
        nationality = request.form.get("nationality")
        religion = request.form.get("religion")
        disability = request.form.get("disability")
        email = request.form.get("email")
        contact_number = request.form.get("contact_number")
        house_number = request.form.get("house_number")
        streetorvillage = request.form.get("streetorvillage")
        barangay = request.form.get("barangay")
        municipality = request.form.get("municipality")
        province = request.form.get("province")
        country = request.form.get("country")
        zipcode = request.form.get("zipcode")
        father_lastname = request.form.get("father_lastname")
        father_firstname = request.form.get("father_firstname")
        father_middlename = request.form.get("father_middlename")
        father_age = request.form.get("father_age")
        father_email = request.form.get("father_email")
        father_contact_number = request.form.get("father_contact_number")
        father_occupation = request.form.get("father_occupation")
        father_education = request.form.get("father_education")
        mother_lastname = request.form.get("mother_lastname")
        mother_firstname = request.form.get("mother_firstname")
        mother_middlename = request.form.get("mother_middlename")
        mother_age = request.form.get("mother_age")
        mother_email = request.form.get("mother_email")
        mother_contact_number = request.form.get("mother_contact_number")
        mother_occupation = request.form.get("mother_occupation")
        mother_education = request.form.get("mother_education")
        last_school_attended = request.form.get("last_school_attended")
        last_school_type = request.form.get("last_school_type")
        last_school_address = request.form.get("last_school_address")
        academic_strand = request.form.get("academic_strand")
        course_first = request.form.get("course_first")
        course_second = request.form.get("course_second")
        course_third = request.form.get("course_third")
        
        student_type = "Transferee"
        
        # Function to read and compress uploaded files before storing
        def read_file(name):
            f = request.files.get(name)
            if not f or not f.filename:
                return None
            raw = f.read()
            ext = f.filename.rsplit(".", 1)[-1].lower()
            # Compress images (jpg/png); leave PDFs as-is but warn if too large
            if ext in ("jpg", "jpeg", "png"):
                try:
                    img = Image.open(io.BytesIO(raw))
                    img = img.convert("RGB")
                    # Resize if larger than 1200px on longest side
                    max_px = 1200
                    if max(img.size) > max_px:
                        img.thumbnail((max_px, max_px), Image.LANCZOS)
                    buf = io.BytesIO()
                    img.save(buf, format="JPEG", quality=75, optimize=True)
                    compressed = buf.getvalue()
                    print(f"DEBUG: {name} compressed {len(raw)//1024}KB -> {len(compressed)//1024}KB")
                    return compressed
                except Exception as img_err:
                    print(f"DEBUG: Image compress failed for {name}: {img_err}")
                    return raw
            return raw
        
        # Read transferee required files
        stu_hon_dis = read_file("stuHonDis")
        stu_cog = read_file("stuCOG")
        stu_pic = read_file("stuPic")
        stu_good_moral = read_file("stuGoodMoral")
        stu_psa = read_file("stuPSA")
        
        # Freshmen-specific files set to None
        stu_coe = None
        stu_form137 = None
        
        print(f"DEBUG: Transferee admission - About to insert data for {first_name} {last_name}")
        print(f"DEBUG: Email: {email}")
        print(f"DEBUG: Student Type: {student_type}")
        
        # Connect to database
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Prepare data tuple
        data_tuple = (
            last_name, first_name, middle_name, suffix,
            gender, birthdate, age, civil_status, nationality, religion, disability,
            email, contact_number,
            house_number, streetorvillage, barangay, municipality, province, country, zipcode,
            father_lastname, father_firstname, father_middlename,
            father_age, father_email, father_contact_number, father_occupation, father_education,
            mother_lastname, mother_firstname, mother_middlename,
            mother_age, mother_email, mother_contact_number, mother_occupation, mother_education,
            last_school_attended, last_school_type, last_school_address, academic_strand,
            course_first, course_second, course_third,
            student_type,
            stu_pic, stu_psa, stu_good_moral, stu_form137, stu_coe, stu_hon_dis, stu_cog, date.today()
        )
        
        # SQL Insert statement
        sql = """
        INSERT INTO `admissions`(
            `student_lastname`, `student_firstname`, `student_middlename`, `student_suffix`,
            `student_gender`, `student_birthdate`, `student_age`, `student_civilstatus`, `student_nationality`, `student_religion`, `student_dissability`, 
            `student_email`, `student_contactnumber`, 
            `student_address_house_number`, `student_address_streetorvillage`, `student_address_barangay`, `student_address_municipalityorcity`, `student_address_province`, `student_address_country`, `student_address_zipcode`, 
            `student_father_lastname`, `student_father_firstname`, `student_father_middlename`, 
            `student_father_age`, `student_father_email`, `student_father_contactnumber`, `student_father_occupation`, `student_father_education`, 
            `student_mother_lastname`, `student_mother_firstname`, `student_mother_middlename`, 
            `student_mother_age`, `student_mother_email`, `student_mother_contactnumber`, `student_mother_occupation`, `student_mother_education`, 
            `student_lastschool_attended`, `student_lastschool_type`, `student_lastschool_address`, `student_academic_strand`, 
            `student_course_choice1`, `student_course_choice2`, `student_course_choice3`, 
            `student_type`, 
            `student_picture`, `student_psa`, `student_goodmoral`, `student_form138`, `student_certificateofenrollment`, `student_honorabledismissal`, `student_certificateofgrade`, `student_date_submitted`, `student_admission_status`
        )
        VALUES (
            %s, %s, %s, %s,
            %s, %s, %s, %s, %s, %s, %s,
            %s, %s,
            %s, %s, %s, %s, %s, %s, %s,
            %s, %s, %s,
            %s, %s, %s, %s, %s,
            %s, %s, %s,
            %s, %s, %s, %s, %s,
            %s, %s, %s, %s,
            %s, %s, %s,
            %s,
            %s, %s, %s, %s, %s, %s, %s, %s, 'Pending'
        )
        """
        
        cursor.execute(sql, data_tuple)
        conn.commit()
        print(f"DEBUG: Successfully inserted Transferee record for {first_name} {last_name}")
        
        # Send confirmation email to the student
        course_choices = [course_first, course_second, course_third]
        full_name = f"{first_name} {middle_name} {last_name}".strip()
        
        email_success, email_message = send_application_confirmation_email(
            student_email=email,
            student_name=full_name,
            student_type=student_type,
            course_choices=course_choices
        )
        
        if email_success:
            print(f"DEBUG: Confirmation email sent successfully to {email}")
        else:
            print(f"DEBUG: Email sending failed - {email_message}")
        
        cursor.close()
        conn.close()
        
        return jsonify({
            "success": True,
            "message": "Your application has been submitted successfully! Please check your email for updates regarding your application."
        })
        
    except mysql.connector.Error as db_error:
        print(f"DEBUG: Database error: {str(db_error)}")
        return jsonify({
            "success": False,
            "message": f"Database error: {str(db_error)}"
        }), 500
    except Exception as e:
        print(f"DEBUG: Exception error: {str(e)}")
        return jsonify({
            "success": False,
            "message": f"Error: {str(e)}"
        }), 500


@app.route("/enroll-student", methods=["POST"])
def enroll_student():
    """
    Enrolls a returning UNENROLLED regular student.
    Steps:
      1. Re-fetch student details for safety.
      2. Determine curriculum table from school_status (CURRICULUM_<COURSE>).
      3. Find active subjects for student's course + year_level + current semester.
      4. Update those subject columns to 2 in the curriculum table.
      5. Set student_status = 'Enrollee' in students table.
    """
    try:
        data         = request.get_json()
        student_email = data.get("email", "").strip()

        if not student_email:
            return jsonify({"success": False, "message": "Missing student email."}), 400

        conn   = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # ── 1. Re-fetch student ──────────────────────────────────────────────
        cursor.execute("""
            SELECT student_number, student_firstname, student_lastname,
                   student_course, student_yearlevel, student_section,
                   student_curriculum, student_status, student_type
            FROM students WHERE student_email = %s
        """, (student_email,))
        stu = cursor.fetchone()

        if not stu:
            return jsonify({"success": False, "message": "Student not found."}), 404

        if stu["student_status"].upper() != "UNENROLLED":
            return jsonify({"success": False, "message": "Student is not eligible for enrollment."}), 400

        course      = stu["student_course"].strip().upper()
        year_level  = stu["student_yearlevel"]
        student_num = stu["student_number"]

        # ── 2. Determine curriculum table from school_status ─────────────────
        CURRICULUM_COL_MAP = {
            "BSCS": "CURRICULUM_BSCS",
            "ACT":  "CURRICULUM_BSCS",
            "BSHM": "CURRICULUM_BSHM",
            "BSED": "CURRICULUM_BSED",
            "BEED": "CURRICULUM_BEED",
        }
        col = CURRICULUM_COL_MAP.get(course)
        if not col:
            return jsonify({"success": False, "message": f"Unknown course: {course}"}), 400

        cursor.execute(f"SELECT `{col}`, semester FROM school_status ORDER BY id DESC LIMIT 1")
        sch = cursor.fetchone()
        if not sch or not sch[col]:
            return jsonify({"success": False, "message": "Curriculum table not configured in school settings."}), 500

        curriculum_table = sch[col]
        import re as _re
        _sem_match = _re.search(r"\d", str(sch["semester"]).strip())
        current_semester = _sem_match.group() if _sem_match else str(sch["semester"]).strip()

        # ── 3. Find active subjects for this course + year_level + semester ──
        # If semester = 2, use the student's current year_level.
        # If semester = 1, the student is moving to the next year, so use year_level + 1.
        if current_semester == "2":
            query_level = str(year_level)
        else:  # semester = 1
            query_level = str(int(year_level) + 1)

        cursor.execute("""
            SELECT Subject_Code FROM subjects
            WHERE Course = %s
              AND Level = %s
              AND Semester = %s
              AND status = 'Active'
        """, (course, query_level, current_semester))
        active_subjects = [r["Subject_Code"] for r in cursor.fetchall()]

        if not active_subjects:
            return jsonify({
                "success": False,
                "message": f"No active subjects found for {course} Year {query_level} Sem {current_semester}."
            }), 400

        # ── 4. Get all columns in curriculum table to validate subject codes ─
        cursor.execute("""
            SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = %s
            ORDER BY ORDINAL_POSITION
        """, (curriculum_table,))
        table_cols = {r["COLUMN_NAME"] for r in cursor.fetchall()}

        META_COLS = {"id", "student_number", "students_fullname",
                     "students_section", "student_type", "student_status"}

        # Only update columns that actually exist in the curriculum table
        valid_subjects = [s for s in active_subjects if s in table_cols and s not in META_COLS]

        if not valid_subjects:
            return jsonify({
                "success": False,
                "message": "No matching subject columns found in the curriculum table."
            }), 400

        # Build:  SET `CSC1` = 2, `CSC2` = 2, ...
        set_clause = ", ".join(f"`{s}` = 2" for s in valid_subjects)

        # ── 4. Update subject columns to 2 AND student_status in curriculum table ──
        cursor.execute(f"""
            UPDATE `{curriculum_table}`
            SET {set_clause}, `student_status` = 'Enrollee'
            WHERE student_number = %s
        """, (student_num,))

        # ── 5. Set student_status = 'Enrollee' in students table ─────────────
        cursor.execute("""
            UPDATE students SET student_status = 'Enrollee'
            WHERE student_email = %s
        """, (student_email,))

        conn.commit()

        print(f"[enroll_student] {student_num} — "
              f"{len(valid_subjects)} subjects set to 2 in `{curriculum_table}` "
              f"(Course={course}, Level={query_level}, Sem={current_semester}), "
              f"student_status set to 'Enrollee'")

        return jsonify({
            "success":  True,
            "message":  "Enrollment submitted! Please wait for admin verification.",
            "subjects_updated": len(valid_subjects),
        })

    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({"success": False, "message": f"Error: {str(e)}"}), 500
    finally:
        try:
            cursor.close()
            conn.close()
        except Exception:
            pass


@app.route("/admission", methods=["POST"])
def admission():
    """Legacy endpoint - redirects to appropriate admission endpoint"""
    student_type = request.form.get("student_type", "").strip()
    if student_type == "Transferee":
        return admission_transferee()
    elif student_type == "Freshmen":
        return admission_freshmen()
    else:
        return jsonify({
            "success": False,
            "message": f"Unknown student type: '{student_type}'. Please refresh and try again."
        }), 400




if __name__ == "__main__":
    app.run(debug=True)
