"""
MediCare - Multi-Clinic Management System (PyQt5, hospital theme)
GUI for your auth.py / clinic.py logic: signup & login per clinic, doctors, patients,
dashboard, reports. Every query is scoped to the logged-in clinic (user_id).

Run:  python clinic_app.py
"""
import csv
import json
import os
import sys
from datetime import datetime, timedelta

from mysql.connector import Error
from PyQt5.QtCore import Qt, QTimer, QRegExp
from PyQt5.QtGui import QRegExpValidator
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QFrame, QLabel, QPushButton, QLineEdit, QComboBox,
    QSpinBox, QDoubleSpinBox, QCheckBox, QVBoxLayout, QHBoxLayout, QGridLayout, QStackedWidget,
    QMessageBox, QDialog, QFileDialog, QButtonGroup,
)

from auth import hash_password, verify_password
from database import ensure_schema, get_connection, load_config
from ui_kit import BG, TEAL, STYLE, BarChart, StatCard, button, card_frame, fill_table, make_table


# ==========================================================
# DATA LAYER (same rules as clinic.py / auth.py)
# ==========================================================
def run(sql, params=(), fetch="all", commit=False):
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(sql, params)
        if commit:
            conn.commit()
            return cur.lastrowid
        return cur.fetchone() if fetch == "one" else cur.fetchall()
    except Error:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


def spec_hint():
    """Placeholder text for the (free-text) specialization box, built from config.json examples."""
    try:
        names = load_config().get("specializations", [])[:3]
    except RuntimeError:
        names = []
    return "e.g. " + ", ".join(n.title() for n in names) if names else "Type the specialization"


def authenticate(username, password):
    r = run("SELECT user_id, clinic_name, username, email, password_hash, created_at "
            "FROM users WHERE username=%s", (username,), "one")
    if not r or not verify_password(password, r[4]):
        return None
    return {"user_id": r[0], "clinic_name": r[1], "username": r[2], "email": r[3], "created_at": r[5]}


def register_clinic(clinic, username, email, pw, confirm):
    """Returns an error message, or None on success."""
    email = email.strip().lower()
    if not all([clinic, username, email, pw]):
        return "All fields are required."
    if "@" not in email or "." not in email.split("@")[-1]:
        return "Enter a valid email address."
    if pw != confirm:
        return "Passwords do not match."
    if len(pw) < 8:
        return "Password must contain at least 8 characters."
    if run("SELECT user_id FROM users WHERE username=%s OR email=%s", (username, email), "one"):
        return "Username or email already registered."
    run("INSERT INTO users (clinic_name, username, email, password_hash) VALUES (%s,%s,%s,%s)",
        (clinic, username, email, hash_password(pw)), commit=True)
    return None


def list_doctors(uid):
    return run("SELECT d.doctor_id, d.name, d.phone, d.gender, d.specialization, d.fees, COUNT(p.patient_id) "
               "FROM doctors d LEFT JOIN patients p ON p.doctor_id = d.doctor_id "
               "WHERE d.user_id=%s GROUP BY d.doctor_id ORDER BY d.doctor_id", (uid,))


def list_patients(uid, term=""):
    sql = ("SELECT p.patient_id, p.name, p.phone, p.age, p.concern, d.name, p.fees, p.regtimestamp, p.doctor_id "
           "FROM patients p INNER JOIN doctors d ON p.doctor_id = d.doctor_id AND p.user_id = d.user_id "
           "WHERE p.user_id=%s")
    params = [uid]
    if term:
        like = f"%{term}%"
        sql += (" AND (CAST(p.patient_id AS CHAR)=%s OR p.name LIKE %s OR p.phone LIKE %s "
                "OR d.name LIKE %s OR p.concern LIKE %s)")
        params += [term, like, like, like, like]
    return run(sql + " ORDER BY p.regtimestamp DESC, p.patient_id DESC", tuple(params))


def save_doctor(uid, d, doctor_id=0):
    """Returns an error message or None. d = (name, phone, gender, specialization, fees)."""
    if run("SELECT doctor_id FROM doctors WHERE user_id=%s AND phone=%s AND name=%s AND doctor_id<>%s",
           (uid, d[1], d[0], doctor_id), "one"):
        return "This doctor already exists in your clinic."
    if doctor_id:
        run("UPDATE doctors SET name=%s, phone=%s, gender=%s, specialization=%s, fees=%s "
            "WHERE doctor_id=%s AND user_id=%s", d + (doctor_id, uid), commit=True)
    else:
        run("INSERT INTO doctors (user_id, name, phone, gender, specialization, fees) "
            "VALUES (%s,%s,%s,%s,%s,%s)", (uid,) + d, commit=True)
    return None


# ==========================================================
# SESSION (stay logged in until Logout)
# ==========================================================
SESSION_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".session.json")


def save_session(user_id):
    try:
        with open(SESSION_FILE, "w", encoding="utf-8") as f:
            json.dump({"user_id": user_id}, f)
    except OSError:
        pass


def clear_session():
    try:
        os.remove(SESSION_FILE)
    except OSError:
        pass


def restore_session():
    """Returns the saved user (as after a normal login) or None if nobody is signed in."""
    try:
        with open(SESSION_FILE, encoding="utf-8") as f:
            uid = int(json.load(f)["user_id"])
    except (OSError, ValueError, KeyError, TypeError):
        return None
    try:
        r = run("SELECT user_id, clinic_name, username, email, created_at FROM users WHERE user_id=%s",
                (uid,), "one")
    except Error:
        return None
    if not r:  # account no longer exists
        clear_session()
        return None
    return {"user_id": r[0], "clinic_name": r[1], "username": r[2], "email": r[3], "created_at": r[4]}


# ==========================================================
# SMALL UI HELPERS
# ==========================================================
def field(placeholder="", password=False):
    e = QLineEdit()
    e.setPlaceholderText(placeholder)
    if password:
        e.setEchoMode(QLineEdit.Password)
    return e


def lbl(text, name="formLabel"):
    l = QLabel(text)
    l.setObjectName(name)
    return l


def phone_field():
    e = field("03XX-XXXXXXX")
    e.setValidator(QRegExpValidator(QRegExp(r"[0-9+\-\s]{0,15}")))
    return e


def grid_form(fields, cols=2):
    g = QGridLayout()
    g.setHorizontalSpacing(20)
    g.setVerticalSpacing(8)
    for i, (text, w) in enumerate(fields):
        r, c = divmod(i, cols)
        g.addWidget(lbl(text), r * 2, c)
        g.addWidget(w, r * 2 + 1, c)
    return g


def db_error(parent, e):
    QMessageBox.critical(parent, "Database Error", str(e))


class FormDialog(QDialog):
    def __init__(self, title, ok_text, fields, parent=None, width=560):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(width)
        self.setStyleSheet(f"QDialog {{ background: {BG}; }}")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 20)
        lay.setSpacing(14)
        lay.addWidget(lbl(title, "sectionTitle"))
        lay.addLayout(grid_form(fields))
        row = QHBoxLayout()
        row.addStretch()
        cancel, ok = button("Cancel", "secondary"), button(ok_text)
        cancel.clicked.connect(self.reject)
        ok.clicked.connect(self.try_accept)
        row.addWidget(cancel)
        row.addWidget(ok)
        lay.addLayout(row)

    def validate(self):
        return None

    def try_accept(self):
        err = self.validate()
        if err:
            QMessageBox.warning(self, "Invalid Data", err)
        else:
            self.accept()


class DoctorDialog(FormDialog):
    def __init__(self, parent=None, row=None):
        name, phone = field("Dr. Full Name"), phone_field()
        gender = QComboBox(); gender.addItems(["Male", "Female", "Other"])
        spec = field(spec_hint())
        fees = QDoubleSpinBox(); fees.setRange(0, 10_000_000); fees.setPrefix("Rs "); fees.setSingleStep(100)
        super().__init__("Edit Doctor" if row else "➕  Add Doctor", "💾  Save Doctor",
                         [("Doctor Name *", name), ("Phone Number *", phone), ("Gender", gender),
                          ("Specialization *", spec), ("Doctor Fees", fees)], parent)
        self.name, self.phone, self.gender, self.spec, self.fees = name, phone, gender, spec, fees
        if row:
            name.setText(row[1]); phone.setText(row[2] or ""); gender.setCurrentText(row[3] or "Other")
            spec.setText(row[4]); fees.setValue(float(row[5]))

    def data(self):
        return (self.name.text().strip(), self.phone.text().strip(), self.gender.currentText(),
                self.spec.text().strip().upper(), self.fees.value())

    def validate(self):
        d = self.data()
        if not d[0]:
            return "Doctor name is required."
        if len(d[1]) < 7:
            return "Enter a valid phone number (at least 7 digits)."
        if not d[3]:
            return "Specialization is required."
        return None


class PatientDialog(FormDialog):
    """Concern is limited to your doctors' specializations and the doctor list follows it,
    so the 'specialization must match concern' rule from clinic.py is always satisfied."""

    def __init__(self, doctors, parent=None, row=None):
        name, phone = field("Patient full name"), phone_field()
        age = QSpinBox(); age.setRange(0, 120); age.setValue(25)
        concern, doctor = QComboBox(), QComboBox()
        concern.addItems(sorted({d[2] for d in doctors}))
        fee = QLabel("Rs 0"); fee.setStyleSheet(f"font-size:18px; font-weight:bold; color:{TEAL};")
        super().__init__("Edit Patient" if row else "➕  Register Patient", "💾  Save Patient",
                         [("Patient Name *", name), ("Phone Number *", phone), ("Age", age),
                          ("Concern (specialization)", concern), ("Doctor", doctor), ("Consultation Fee", fee)], parent)
        self.doctors, self.name, self.phone, self.age = doctors, name, phone, age
        self.concern, self.doctor, self.fee = concern, doctor, fee
        concern.currentTextChanged.connect(self.load_doctors)
        doctor.currentIndexChanged.connect(self.show_fee)
        cur = next((d for d in doctors if row and d[0] == row[8]), None)
        if row:
            name.setText(row[1]); phone.setText(row[2] or ""); age.setValue(int(row[3] or 0))
        if cur:
            concern.setCurrentText(cur[2])
        self.load_doctors()
        if cur:
            doctor.setCurrentIndex(max(doctor.findData(cur[0]), 0))

    def load_doctors(self):
        self.doctor.clear()
        for d in self.doctors:
            if d[2] == self.concern.currentText():
                self.doctor.addItem(f"{d[1]}  (Rs {float(d[3]):,.0f})", d[0])
        self.show_fee()

    def show_fee(self):
        d = next((x for x in self.doctors if x[0] == self.doctor.currentData()), None)
        self.fee.setText(f"Rs {float(d[3]):,.2f}" if d else "Rs 0")

    def data(self):
        d = next(x for x in self.doctors if x[0] == self.doctor.currentData())
        return (self.name.text().strip(), self.phone.text().strip(), self.age.value(),
                self.concern.currentText(), d[0], float(d[3]))

    def validate(self):
        if not self.name.text().strip():
            return "Patient name is required."
        if len(self.phone.text().strip()) < 7:
            return "Enter a valid phone number (at least 7 digits)."
        if self.doctor.currentData() is None:
            return "Please select a doctor."
        return None


# ==========================================================
# LOGIN / SIGNUP WINDOW
# ==========================================================
class AuthWindow(QWidget):
    def __init__(self, on_login):
        super().__init__()
        self.on_login = on_login
        self.setWindowTitle("MediCare - Clinic Login")
        self.resize(1000, 660)
        self.setMinimumSize(900, 620)
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        brand = QFrame(); brand.setObjectName("brandPanel"); brand.setFixedWidth(420)
        bl = QVBoxLayout(brand); bl.setContentsMargins(44, 0, 44, 0); bl.addStretch()
        bl.addWidget(lbl("✚  MediCare", "brandTitle"))
        t = lbl("Multi-clinic management system.\nSecure, simple and built for care teams.", "brandText")
        t.setWordWrap(True); bl.addWidget(t); bl.addSpacing(24)
        bl.addWidget(lbl("✔  Private data for every clinic\n✔  Doctors and patient records\n"
                         "✔  Live dashboard and reports", "brandText"))
        bl.addStretch()

        self.stack = QStackedWidget()
        self.stack.addWidget(self.login_page())
        self.stack.addWidget(self.signup_page())
        right = QVBoxLayout(); right.addStretch()
        card = card_frame(); card.setFixedWidth(400)
        cl = QVBoxLayout(card); cl.setContentsMargins(32, 28, 32, 28); cl.addWidget(self.stack)
        right.addWidget(card, 0, Qt.AlignHCenter); right.addStretch()
        root.addWidget(brand); root.addLayout(right, 1)

    def link(self, text, idx):
        b = QPushButton(text); b.setObjectName("linkBtn"); b.setCursor(Qt.PointingHandCursor)
        b.clicked.connect(lambda: self.stack.setCurrentIndex(idx))
        return b

    def login_page(self):
        w = QWidget(); l = QVBoxLayout(w); l.setSpacing(8)
        l.addWidget(lbl("Welcome back 👋", "authTitle"))
        l.addWidget(lbl("Sign in to your clinic account", "authSub")); l.addSpacing(10)
        self.l_user, self.l_pass = field("Username"), field("Password", True)
        show = QCheckBox("Show password")
        show.toggled.connect(lambda c: self.l_pass.setEchoMode(QLineEdit.Normal if c else QLineEdit.Password))
        self.l_err = lbl("", "errLabel"); self.l_err.setWordWrap(True)
        go = button("Sign In"); go.clicked.connect(self.do_login)
        self.l_user.returnPressed.connect(self.do_login); self.l_pass.returnPressed.connect(self.do_login)
        for x in (lbl("Username"), self.l_user, lbl("Password"), self.l_pass, show, self.l_err, go,
                  self.link("New clinic? Create an account", 1)):
            l.addWidget(x)
        return w

    def signup_page(self):
        w = QWidget(); l = QVBoxLayout(w); l.setSpacing(6)
        l.addWidget(lbl("Create clinic account", "authTitle"))
        l.addWidget(lbl("Register your clinic in a minute", "authSub")); l.addSpacing(6)
        self.s_clinic, self.s_user, self.s_mail = field("Clinic name"), field("Username"), field("name@clinic.com")
        self.s_pass, self.s_conf = field("At least 8 characters", True), field("Repeat password", True)
        self.s_err = lbl("", "errLabel"); self.s_err.setWordWrap(True)
        go = button("Create Account"); go.clicked.connect(self.do_signup)
        self.s_conf.returnPressed.connect(self.do_signup)
        for text, f in (("Clinic Name", self.s_clinic), ("Username", self.s_user), ("Email", self.s_mail),
                        ("Password", self.s_pass), ("Confirm Password", self.s_conf)):
            l.addWidget(lbl(text)); l.addWidget(f)
        l.addWidget(self.s_err); l.addWidget(go); l.addWidget(self.link("Already registered? Sign in", 0))
        return w

    def do_login(self):
        u, p = self.l_user.text().strip(), self.l_pass.text()
        if not u or not p:
            return self.l_err.setText("Enter your username and password.")
        try:
            user = authenticate(u, p)
        except Error as e:
            return self.l_err.setText(f"Database error: {e}")
        if not user:
            return self.l_err.setText("Invalid username or password.")
        self.l_pass.clear(); self.l_err.clear()
        self.on_login(user)

    def do_signup(self):
        try:
            err = register_clinic(self.s_clinic.text().strip(), self.s_user.text().strip(),
                                  self.s_mail.text(), self.s_pass.text(), self.s_conf.text())
        except Error as e:
            err = f"Database error: {e}"
        if err:
            return self.s_err.setText(err)
        QMessageBox.information(self, "Account Created", "Your clinic account has been created.\nYou can now sign in.")
        self.l_user.setText(self.s_user.text().strip())
        for f in (self.s_clinic, self.s_user, self.s_mail, self.s_pass, self.s_conf):
            f.clear()
        self.s_err.clear(); self.stack.setCurrentIndex(0); self.l_pass.setFocus()

    def closeEvent(self, e):
        QApplication.quit()


# ==========================================================
# PAGES
# ==========================================================
class DashboardPage(QWidget):
    def __init__(self, uid):
        super().__init__()
        self.uid = uid
        lay = QVBoxLayout(self); lay.setContentsMargins(24, 20, 24, 20); lay.setSpacing(16)
        cards = QHBoxLayout(); cards.setSpacing(16)
        self.c_doc = StatCard("Doctors", "🩺", "#2563EB")
        self.c_pat = StatCard("Patients", "🧑‍⚕️", "#0E9AA7")
        self.c_today = StatCard("Registered Today", "📅", "#F59E0B")
        self.c_rev = StatCard("Total Revenue", "💰", "#16A34A")
        for c in (self.c_doc, self.c_pat, self.c_today, self.c_rev):
            cards.addWidget(c)
        lay.addLayout(cards)
        charts = QHBoxLayout(); charts.setSpacing(16)
        self.ch_doc, self.ch_week = BarChart("Patients per Doctor"), BarChart("Registrations - Last 7 Days", "#2563EB")
        charts.addWidget(self.ch_doc); charts.addWidget(self.ch_week)
        lay.addLayout(charts)
        lay.addWidget(lbl("Recently Registered Patients", "sectionTitle"))
        self.table = make_table(PatientsPage.HEAD)
        lay.addWidget(self.table, 1)

    def refresh(self):
        u = self.uid
        docs = run("SELECT COUNT(*) FROM doctors WHERE user_id=%s", (u,), "one")[0]
        n, rev, today = run("SELECT COUNT(*), COALESCE(SUM(fees),0), COALESCE(SUM(DATE(regtimestamp)=CURDATE()),0) "
                            "FROM patients WHERE user_id=%s", (u,), "one")
        self.c_doc.set(str(docs)); self.c_pat.set(str(n)); self.c_today.set(str(int(today)))
        self.c_rev.set(f"Rs {float(rev):,.0f}")
        self.ch_doc.set_data([(d, float(c)) for d, c in run(
            "SELECT d.name, COUNT(p.patient_id) FROM doctors d LEFT JOIN patients p ON p.doctor_id=d.doctor_id "
            "WHERE d.user_id=%s GROUP BY d.doctor_id ORDER BY 2 DESC LIMIT 6", (u,))])
        counts = {str(d): c for d, c in run(
            "SELECT DATE(regtimestamp), COUNT(*) FROM patients WHERE user_id=%s "
            "AND regtimestamp >= CURDATE() - INTERVAL 6 DAY GROUP BY DATE(regtimestamp)", (u,))}
        days = [datetime.now().date() - timedelta(days=i) for i in range(6, -1, -1)]
        self.ch_week.set_data([(d.strftime("%a %d"), float(counts.get(str(d), 0))) for d in days])
        fill_table(self.table, [r[:8] for r in list_patients(u)[:8]], money_cols=(6,))


class PatientsPage(QWidget):
    HEAD = ["ID", "Name", "Phone", "Age", "Concern", "Doctor", "Fees", "Registered"]

    def __init__(self, uid, on_change):
        super().__init__()
        self.uid, self.on_change, self.rows = uid, on_change, []
        lay = QVBoxLayout(self); lay.setContentsMargins(24, 20, 24, 20); lay.setSpacing(12)
        bar = QHBoxLayout()
        self.search = QLineEdit(); self.search.setPlaceholderText("🔍  Search by ID, name, phone, doctor or concern...")
        self.search.textChanged.connect(self.refresh)
        add, edit = button("➕  Add Patient"), button("✏️  Edit", "secondary")
        delete, export = button("🗑  Delete", "danger"), button("📤  Export CSV", "secondary")
        add.clicked.connect(self.add); edit.clicked.connect(self.edit)
        delete.clicked.connect(self.delete); export.clicked.connect(self.export)
        bar.addWidget(self.search, 1)
        for b in (add, edit, delete, export):
            bar.addWidget(b)
        self.table = make_table(self.HEAD); self.table.doubleClicked.connect(self.edit)
        self.count = lbl("", "cardTitle")
        lay.addLayout(bar); lay.addWidget(self.table, 1); lay.addWidget(self.count)

    def refresh(self):
        self.rows = list_patients(self.uid, self.search.text().strip())
        fill_table(self.table, [r[:8] for r in self.rows], money_cols=(6,))
        self.count.setText(f"{len(self.rows)} patient record(s)")

    def doctors(self):
        docs = [(d[0], d[1], d[4], d[5]) for d in list_doctors(self.uid)]
        if not docs:
            QMessageBox.information(self, "No Doctors", "Doctor not found in your clinic.\nAdd a doctor first.")
        return docs

    def selected(self):
        r = self.table.currentRow()
        if r < 0:
            QMessageBox.information(self, "Select Patient", "Please select a patient from the table first.")
            return None
        return self.rows[r]

    def add(self):
        docs = self.doctors()
        if not docs:
            return
        dlg = PatientDialog(docs, self)
        if dlg.exec_():
            try:
                run("INSERT INTO patients (user_id, name, phone, age, concern, doctor_id, fees) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s)", (self.uid,) + dlg.data(), commit=True)
            except Error as e:
                return db_error(self, e)
            self.on_change()

    def edit(self):
        row = self.selected()
        docs = self.doctors() if row else None
        if not row or not docs:
            return
        dlg = PatientDialog(docs, self, row)
        if dlg.exec_():
            d = dlg.data()
            fees = d[5] if d[4] != row[8] else float(row[6])  # keep the original fee unless the doctor changes
            try:
                run("UPDATE patients SET name=%s, phone=%s, age=%s, concern=%s, doctor_id=%s, fees=%s "
                    "WHERE patient_id=%s AND user_id=%s", d[:5] + (fees, row[0], self.uid), commit=True)
            except Error as e:
                return db_error(self, e)
            self.on_change()

    def delete(self):
        row = self.selected()
        if row and QMessageBox.question(self, "Confirm Delete", f"Delete patient #{row[0]} - {row[1]}?\n"
                                        "This cannot be undone.", QMessageBox.Yes | QMessageBox.No,
                                        QMessageBox.No) == QMessageBox.Yes:
            try:
                run("DELETE FROM patients WHERE patient_id=%s AND user_id=%s", (row[0], self.uid), commit=True)
            except Error as e:
                return db_error(self, e)
            self.on_change()

    def export(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export Patients", "patients.csv", "CSV Files (*.csv)")
        if path:
            with open(path, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f); w.writerow(self.HEAD); w.writerows(r[:8] for r in self.rows)
            QMessageBox.information(self, "Exported", f"Saved {len(self.rows)} records to:\n{path}")


class DoctorsPage(QWidget):
    def __init__(self, uid, on_change):
        super().__init__()
        self.uid, self.on_change, self.rows = uid, on_change, []
        lay = QVBoxLayout(self); lay.setContentsMargins(24, 20, 24, 20); lay.setSpacing(12)
        bar = QHBoxLayout(); bar.addWidget(lbl("Doctors of your clinic", "sectionTitle")); bar.addStretch()
        add, edit, delete = button("➕  Add Doctor"), button("✏️  Edit", "secondary"), button("🗑  Delete", "danger")
        add.clicked.connect(self.add); edit.clicked.connect(self.edit); delete.clicked.connect(self.delete)
        for b in (add, edit, delete):
            bar.addWidget(b)
        self.table = make_table(["ID", "Name", "Phone", "Gender", "Specialization", "Fees", "Patients"])
        self.table.doubleClicked.connect(self.edit)
        lay.addLayout(bar); lay.addWidget(self.table, 1)

    def refresh(self):
        self.rows = list_doctors(self.uid)
        fill_table(self.table, self.rows, money_cols=(5,))

    def selected(self):
        r = self.table.currentRow()
        if r < 0:
            QMessageBox.information(self, "Select Doctor", "Please select a doctor from the table first.")
            return None
        return self.rows[r]

    def save(self, dlg, doctor_id=0):
        try:
            err = save_doctor(self.uid, dlg.data(), doctor_id)
        except Error as e:
            return db_error(self, e)
        if err:
            return QMessageBox.warning(self, "Duplicate Doctor", err)
        self.on_change()

    def add(self):
        dlg = DoctorDialog(self)
        if dlg.exec_():
            self.save(dlg)

    def edit(self):
        row = self.selected()
        if row:
            dlg = DoctorDialog(self, row)
            if dlg.exec_():
                self.save(dlg, row[0])

    def delete(self):
        row = self.selected()
        if not row:
            return
        if row[6]:
            return QMessageBox.warning(self, "Cannot Delete", f"{row[1]} has {row[6]} patient(s) assigned.\n"
                                       "Reassign or delete those patients first.")
        if QMessageBox.question(self, "Confirm Delete", f"Delete doctor {row[1]}?", QMessageBox.Yes | QMessageBox.No,
                                QMessageBox.No) == QMessageBox.Yes:
            try:
                run("DELETE FROM doctors WHERE doctor_id=%s AND user_id=%s", (row[0], self.uid), commit=True)
            except Error as e:
                return db_error(self, e)
            self.on_change()


class ReportsPage(QWidget):
    def __init__(self, uid):
        super().__init__()
        self.uid = uid
        lay = QVBoxLayout(self); lay.setContentsMargins(24, 20, 24, 20); lay.setSpacing(16)
        row = QHBoxLayout(); row.setSpacing(16)
        self.ch_con = BarChart("Patients by Concern")
        self.ch_rev = BarChart("Revenue by Doctor", "#16A34A", money=True)
        row.addWidget(self.ch_con); row.addWidget(self.ch_rev)
        lay.addLayout(row, 1)
        exp = button("📤  Export Revenue Report (CSV)"); exp.clicked.connect(self.export)
        lay.addWidget(exp, 0, Qt.AlignRight)

    def revenue(self):
        return run("SELECT d.name, d.specialization, COUNT(p.patient_id), COALESCE(SUM(p.fees),0) "
                   "FROM doctors d LEFT JOIN patients p ON p.doctor_id=d.doctor_id "
                   "WHERE d.user_id=%s GROUP BY d.doctor_id ORDER BY 4 DESC", (self.uid,))

    def refresh(self):
        self.ch_con.set_data([(c, float(n)) for c, n in run(
            "SELECT concern, COUNT(*) FROM patients WHERE user_id=%s GROUP BY concern ORDER BY 2 DESC LIMIT 8",
            (self.uid,))])
        self.ch_rev.set_data([(r[0], float(r[3])) for r in self.revenue()[:8]])

    def export(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export Report", "clinic_report.csv", "CSV Files (*.csv)")
        if path:
            with open(path, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f); w.writerow(["Doctor", "Specialization", "Patients", "Revenue"])
                w.writerows(self.revenue())
            QMessageBox.information(self, "Exported", f"Report saved to:\n{path}")


class ProfilePage(QWidget):
    def __init__(self, user):
        super().__init__()
        self.user = user
        lay = QVBoxLayout(self); lay.setContentsMargins(24, 20, 24, 20)
        card = card_frame(); card.setMaximumWidth(560)
        cl = QVBoxLayout(card); cl.setContentsMargins(26, 22, 26, 22); cl.setSpacing(8)
        cl.addWidget(lbl("🏥  Clinic Account", "sectionTitle"))
        since = user["created_at"].strftime("%d %B %Y") if user.get("created_at") else "-"
        for k, v in (("Clinic", user["clinic_name"]), ("Username", user["username"]),
                     ("Email", user["email"]), ("Member since", since)):
            cl.addWidget(lbl(k)); cl.addWidget(QLabel(v))
        cl.addSpacing(10); cl.addWidget(lbl("🔒  Change Password", "sectionTitle"))
        self.old, self.new, self.conf = field("Current password", True), field("New password (min 8)", True), \
            field("Confirm new password", True)
        for f in (self.old, self.new, self.conf):
            cl.addWidget(f)
        b = button("Update Password"); b.clicked.connect(self.change)
        cl.addWidget(b, 0, Qt.AlignRight)
        lay.addWidget(card, 0, Qt.AlignTop | Qt.AlignLeft); lay.addStretch()

    def change(self):
        old, new, conf = self.old.text(), self.new.text(), self.conf.text()
        if new != conf:
            return QMessageBox.warning(self, "Password", "Passwords do not match.")
        if len(new) < 8:
            return QMessageBox.warning(self, "Password", "Password must contain at least 8 characters.")
        try:
            r = run("SELECT password_hash FROM users WHERE user_id=%s", (self.user["user_id"],), "one")
            if not r or not verify_password(old, r[0]):
                return QMessageBox.warning(self, "Password", "Current password is incorrect.")
            run("UPDATE users SET password_hash=%s WHERE user_id=%s", (hash_password(new), self.user["user_id"]),
                commit=True)
        except Error as e:
            return db_error(self, e)
        for f in (self.old, self.new, self.conf):
            f.clear()
        QMessageBox.information(self, "Password", "Password updated successfully.")

    def refresh(self):
        pass


# ==========================================================
# MAIN WINDOW
# ==========================================================
class MainWindow(QMainWindow):
    def __init__(self, user, on_logout):
        super().__init__()
        self.user, self.on_logout, self.logging_out = user, on_logout, False
        self.setWindowTitle(f"MediCare - {user['clinic_name']}")
        self.resize(1280, 780); self.setMinimumSize(1000, 640)
        uid = user["user_id"]

        root = QWidget(); self.setCentralWidget(root)
        outer = QHBoxLayout(root); outer.setContentsMargins(0, 0, 0, 0); outer.setSpacing(0)
        side = QFrame(); side.setObjectName("sidebar"); side.setFixedWidth(240)
        sl = QVBoxLayout(side); sl.setContentsMargins(0, 18, 0, 6); sl.setSpacing(0)
        sl.addWidget(lbl("  ✚  MediCare", "logo")); sl.addWidget(lbl("     Multi-Clinic System", "logoSub"))
        sl.addSpacing(22)

        self.pages = QStackedWidget()
        self.page_list = [
            ("🏠   Dashboard", "Dashboard", DashboardPage(uid)),
            ("👥   Patients", "Patient Records", PatientsPage(uid, self.refresh_all)),
            ("🩺   Doctors", "Doctors", DoctorsPage(uid, self.refresh_all)),
            ("📈   Reports", "Reports & Analytics", ReportsPage(uid)),
            ("👤   My Account", "My Account", ProfilePage(user)),
        ]
        group = QButtonGroup(self); group.setExclusive(True)
        for i, (text, _, page) in enumerate(self.page_list):
            b = QPushButton(text); b.setObjectName("navBtn"); b.setCheckable(True); b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda _, idx=i: self.go(idx))
            group.addButton(b); sl.addWidget(b)
            page.setObjectName("page"); self.pages.addWidget(page)
            b.setChecked(i == 0)
        sl.addStretch()
        out = QPushButton("🚪   Logout"); out.setObjectName("exitBtn"); out.clicked.connect(self.logout)
        sl.addWidget(out)

        right = QVBoxLayout(); right.setSpacing(0)
        header = QFrame(); header.setObjectName("header"); header.setFixedHeight(66)
        hl = QHBoxLayout(header); hl.setContentsMargins(24, 0, 24, 0)
        self.title = lbl("Dashboard", "pageTitle"); self.clock = lbl("", "clock")
        hl.addWidget(self.title); hl.addStretch()
        hl.addWidget(lbl(f"🏥  {user['clinic_name']}", "chip")); hl.addSpacing(10)
        hl.addWidget(lbl(f"👤  {user['username']}", "chip")); hl.addSpacing(20); hl.addWidget(self.clock)
        right.addWidget(header); right.addWidget(self.pages, 1)
        outer.addWidget(side); outer.addLayout(right, 1)

        timer = QTimer(self); timer.timeout.connect(self.tick); timer.start(1000); self.tick()
        self.go(0)

    def tick(self):
        self.clock.setText(datetime.now().strftime("%A, %d %B %Y   %I:%M:%S %p"))

    def go(self, idx):
        self.title.setText(self.page_list[idx][1])
        self.pages.setCurrentIndex(idx)
        self.safe_refresh(self.page_list[idx][2])

    def refresh_all(self):
        self.safe_refresh(self.pages.currentWidget())

    def safe_refresh(self, page):
        try:
            page.refresh()
        except Error as e:
            db_error(self, e)

    def logout(self):
        if QMessageBox.question(self, "Logout", "Do you want to log out?", QMessageBox.Yes | QMessageBox.No,
                                QMessageBox.No) == QMessageBox.Yes:
            self.logging_out = True
            self.close()
            self.on_logout()

    def closeEvent(self, e):
        if not self.logging_out:
            QApplication.quit()


# ==========================================================
# APP CONTROLLER
# ==========================================================
class Controller:
    def __init__(self):
        self.auth, self.main = AuthWindow(self.login_ok), None
        user = restore_session()  # still signed in from last time?
        if user:
            self.start(user)
        else:
            self.auth.show()

    def login_ok(self, user):
        save_session(user["user_id"])
        self.start(user)

    def start(self, user):
        self.auth.hide()
        self.main = MainWindow(user, self.logout)
        self.main.show()

    def logout(self):
        clear_session()
        self.main = None
        self.auth.show()


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(STYLE)
    app.setQuitOnLastWindowClosed(False)
    try:
        ensure_schema()
    except (Error, RuntimeError) as e:
        QMessageBox.critical(None, "Startup Error", str(e))
        sys.exit(1)
    ctrl = Controller()  # keep a reference so windows aren't garbage-collected
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()