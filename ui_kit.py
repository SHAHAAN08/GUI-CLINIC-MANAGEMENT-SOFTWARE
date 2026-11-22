"""Shared look & widgets (theme, tables, stat cards, bar charts) for the clinic GUI."""
from datetime import date, datetime

from PyQt5.QtCore import Qt, QRectF
from PyQt5.QtGui import QColor, QFont, QFontMetrics, QPainter
from PyQt5.QtWidgets import (
    QAbstractItemView, QFrame, QHBoxLayout, QHeaderView, QLabel, QPushButton,
    QSizePolicy, QTableWidget, QTableWidgetItem, QVBoxLayout,
)

NAVY, TEAL, BG = "#0B3C5D", "#0E9AA7", "#F2F7FA"

STYLE = f"""
* {{ font-family: 'Segoe UI', 'Arial'; font-size: 13px; color: #1E293B; }}
QMainWindow, QStackedWidget, #page {{ background: {BG}; }}
#sidebar {{ background: {NAVY}; }}
#logo {{ color: white; font-size: 20px; font-weight: bold; }}
#logoSub {{ color: #8FB8D0; font-size: 11px; }}
#navBtn {{ background: transparent; color: #CFE3EE; border: none; text-align: left;
          padding: 12px 18px; font-size: 14px; border-radius: 8px; margin: 2px 10px; }}
#navBtn:hover {{ background: #14507A; color: white; }}
#navBtn:checked {{ background: {TEAL}; color: white; font-weight: bold; }}
#exitBtn {{ background: #B42318; color: white; border: none; border-radius: 8px;
           padding: 10px; margin: 10px 14px; font-weight: bold; }}
#exitBtn:hover {{ background: #912018; }}
#header {{ background: white; border-bottom: 1px solid #DCE6EC; }}
#pageTitle {{ font-size: 22px; font-weight: bold; color: {NAVY}; }}
#status {{ color: #16A34A; font-weight: bold; }}
#clock {{ color: #64748B; }}
#card {{ background: white; border: 1px solid #DCE6EC; border-radius: 12px; }}
#cardTitle {{ color: #64748B; font-size: 12px; font-weight: bold; }}
#cardValue {{ font-size: 28px; font-weight: bold; color: {NAVY}; }}
#sectionTitle {{ font-size: 15px; font-weight: bold; color: {NAVY}; }}
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QDateEdit {{ background: white; border: 1px solid #C5D3DC;
    border-radius: 8px; padding: 8px 10px; min-height: 20px; }}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus, QDateEdit:focus {{ border: 2px solid {TEAL}; }}
QPushButton#primary {{ background: {TEAL}; color: white; border: none; border-radius: 8px;
    padding: 9px 20px; font-weight: bold; }}
QPushButton#primary:hover {{ background: #0B7F8A; }}
QPushButton#secondary {{ background: white; color: {NAVY}; border: 1px solid #C5D3DC;
    border-radius: 8px; padding: 9px 20px; }}
QPushButton#secondary:hover {{ background: #E8F1F6; }}
QPushButton#danger {{ background: #DC2626; color: white; border: none; border-radius: 8px;
    padding: 9px 20px; font-weight: bold; }}
QPushButton#danger:hover {{ background: #B91C1C; }}
QTableWidget {{ background: white; alternate-background-color: #F6FAFC; border: 1px solid #DCE6EC;
    border-radius: 10px; gridline-color: transparent; selection-background-color: #CDEEF1;
    selection-color: {NAVY}; }}
QHeaderView::section {{ background: {NAVY}; color: white; padding: 9px; border: none; font-weight: bold; }}
QLabel#formLabel {{ font-weight: bold; color: #475569; }}
#brandPanel {{ background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {NAVY}, stop:1 {TEAL}); }}
#brandTitle {{ color: white; font-size: 36px; font-weight: bold; }}
#brandText {{ color: #D6EEF2; font-size: 14px; }}
#authTitle {{ font-size: 24px; font-weight: bold; color: {NAVY}; }}
#authSub {{ color: #64748B; }}
#errLabel {{ color: #DC2626; font-weight: bold; }}
#linkBtn {{ background: transparent; border: none; color: {TEAL}; font-weight: bold; padding: 8px; }}
#linkBtn:hover {{ text-decoration: underline; }}
#chip {{ background: #E6F6F8; color: #0B7F8A; border-radius: 12px; padding: 5px 12px; font-weight: bold; }}
"""


# ==========================================================
# REUSABLE WIDGETS
# ==========================================================
def make_table(headers):
    t = QTableWidget(0, len(headers))
    t.setHorizontalHeaderLabels(headers)
    t.setEditTriggers(QAbstractItemView.NoEditTriggers)
    t.setSelectionBehavior(QAbstractItemView.SelectRows)
    t.setSelectionMode(QAbstractItemView.SingleSelection)
    t.setAlternatingRowColors(True)
    t.verticalHeader().setVisible(False)
    t.verticalHeader().setDefaultSectionSize(38)
    t.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
    t.setShowGrid(False)
    return t


def fill_table(t, rows, money_cols=()):
    t.setRowCount(len(rows))
    for r, row in enumerate(rows):
        for c, v in enumerate(row):
            if c in money_cols:
                v = f"Rs {float(v):,.2f}"
            elif isinstance(v, datetime):
                v = v.strftime("%d-%b-%Y  %I:%M %p")
            elif isinstance(v, date):
                v = v.strftime("%d-%b-%Y")
            item = QTableWidgetItem("" if v is None else str(v))
            if c == 0 or isinstance(row[c], (int, float)):
                item.setTextAlignment(Qt.AlignCenter)
            t.setItem(r, c, item)


def card_frame():
    f = QFrame()
    f.setObjectName("card")
    return f


def button(text, kind="primary"):
    b = QPushButton(text)
    b.setObjectName(kind)
    b.setCursor(Qt.PointingHandCursor)
    return b


class StatCard(QFrame):
    def __init__(self, title, icon, color):
        super().__init__()
        self.setObjectName("card")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(18, 16, 18, 16)
        badge = QLabel(icon)
        badge.setFixedSize(52, 52)
        badge.setAlignment(Qt.AlignCenter)
        badge.setStyleSheet(f"background:{color}; border-radius:26px; font-size:22px; color:white;")
        col = QVBoxLayout()
        t = QLabel(title.upper())
        t.setObjectName("cardTitle")
        self.value = QLabel("0")
        self.value.setObjectName("cardValue")
        col.addWidget(t)
        col.addWidget(self.value)
        lay.addWidget(badge)
        lay.addLayout(col)
        lay.addStretch()

    def set(self, text):
        self.value.setText(text)


class BarChart(QFrame):
    """Lightweight horizontal bar chart (no extra dependencies)."""

    def __init__(self, title, color=TEAL, money=False):
        super().__init__()
        self.setObjectName("card")
        self.title, self.color, self.money, self.data = title, color, money, []
        self.setMinimumHeight(240)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def set_data(self, data):
        self.data = data
        self.update()

    def paintEvent(self, e):
        super().paintEvent(e)
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        p.setPen(QColor(NAVY))
        p.setFont(QFont("Segoe UI", 11, QFont.Bold))
        p.drawText(QRectF(16, 10, w - 32, 26), Qt.AlignVCenter | Qt.AlignLeft, self.title)
        if not self.data:
            p.setPen(QColor("#94A3B8"))
            p.drawText(QRectF(0, 0, w, h), Qt.AlignCenter, "No data yet")
            return
        top, lab_w, val_w = 48, 130, 90
        row_h = min(40, (h - top - 10) / len(self.data))
        mx = max(v for _, v in self.data) or 1
        font = QFont("Segoe UI", 9)
        p.setFont(font)
        fm = QFontMetrics(font)
        for i, (label, val) in enumerate(self.data):
            y = top + i * row_h
            p.setPen(QColor("#334155"))
            p.drawText(QRectF(10, y, lab_w - 8, row_h), Qt.AlignVCenter | Qt.AlignRight,
                       fm.elidedText(str(label or "N/A"), Qt.ElideRight, lab_w - 10))
            bw = max((w - lab_w - val_w - 20) * val / mx, 3)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(self.color))
            p.drawRoundedRect(QRectF(lab_w + 6, y + row_h * 0.2, bw, row_h * 0.6), 5, 5)
            p.setPen(QColor(NAVY))
            txt = f"Rs {val:,.0f}" if self.money else f"{val:,.0f}"
            p.drawText(QRectF(lab_w + bw + 12, y, val_w, row_h), Qt.AlignVCenter | Qt.AlignLeft, txt)
