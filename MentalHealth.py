import streamlit as st
import pandas as pd
import requests
import base64
import cv2
import numpy as np
from io import StringIO
from datetime import datetime
from zoneinfo import ZoneInfo
from urllib.parse import urlparse, parse_qs

st.set_page_config(page_title="Mental Health Station", page_icon="🧠", layout="centered")

GITHUB_TOKEN = st.secrets["GITHUB_TOKEN"]
GITHUB_REPO = st.secrets["GITHUB_REPO"]
GITHUB_BRANCH = st.secrets.get("GITHUB_BRANCH", "main")
GITHUB_FILE = st.secrets.get("GITHUB_FILE", "student_registry_log.csv")


# -----------------------------
# Utility functions
# -----------------------------
def bkk_now():
    return datetime.now(ZoneInfo("Asia/Bangkok")).strftime("%Y-%m-%d %H:%M:%S")


def read_qr_from_image(uploaded_img):
    file_bytes = np.asarray(bytearray(uploaded_img.getvalue()), dtype=np.uint8)
    img = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
    detector = cv2.QRCodeDetector()
    data, _, _ = detector.detectAndDecode(img)
    return data.strip() if data else ""


def extract_student_id(qr_text):
    if not qr_text:
        return ""
    if "student_ID=" in qr_text:
        parsed = urlparse(qr_text)
        qs = parse_qs(parsed.query)
        return qs.get("student_ID", [""])[0]
    return qr_text.strip()


def color_label(color):
    return {
        "green": "🟢 เขียว",
        "yellow": "🟡 เหลือง",
        "red": "🔴 แดง",
        "gray": "⚪ ยังประเมินไม่ได้",
    }.get(color, "⚪ ยังประเมินไม่ได้")


def phq_color(score):
    if score >= 10:
        return "red"
    if score >= 3:
        return "yellow"
    return "green"


def gad_color(score):
    if score >= 10:
        return "red"
    if score >= 3:
        return "yellow"
    return "green"


def sleep_color(hours):
    if 7 <= hours <= 9:
        return "green"
    if 5 <= hours < 7 or 9 < hours <= 10:
        return "yellow"
    return "red"


def likert_risk_color(score):
    if score <= 2:
        return "green"
    if score == 3:
        return "yellow"
    return "red"


def exercise_color(score):
    if score >= 4:
        return "green"
    if score == 3:
        return "yellow"
    return "red"


def substance_color(any_substance):
    return "red" if any_substance else "green"


def github_get_file():
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{GITHUB_FILE}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    params = {"ref": GITHUB_BRANCH}

    r = requests.get(url, headers=headers, params=params)
    if r.status_code == 404:
        return None, None

    r.raise_for_status()
    data = r.json()
    content = base64.b64decode(data["content"]).decode("utf-8-sig")
    return content, data["sha"]


def github_save_csv(df):
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{GITHUB_FILE}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}

    _, sha = github_get_file()

    csv_text = df.to_csv(index=False, encoding="utf-8-sig")
    encoded = base64.b64encode(csv_text.encode("utf-8-sig")).decode("utf-8")

    payload = {
        "message": f"Append MentalHealth data {bkk_now()}",
        "content": encoded,
        "branch": GITHUB_BRANCH,
    }

    if sha:
        payload["sha"] = sha

    r = requests.put(url, headers=headers, json=payload)
    r.raise_for_status()


def append_to_github(row):
    old_content, _ = github_get_file()
    new_row_df = pd.DataFrame([row])

    if old_content:
        old_df = pd.read_csv(StringIO(old_content), dtype=str).fillna("")
        all_cols = list(dict.fromkeys(list(old_df.columns) + list(new_row_df.columns)))
        old_df = old_df.reindex(columns=all_cols, fill_value="")
        new_row_df = new_row_df.reindex(columns=all_cols, fill_value="")
        new_df = pd.concat([old_df, new_row_df], ignore_index=True)
    else:
        new_df = new_row_df

    github_save_csv(new_df)


def safe_join(items):
    items = [x for x in items if x]
    return "; ".join(items) if items else ""


score_options = {
    "ไม่เลย": 0,
    "หลายวัน": 1,
    "มากกว่าครึ่งหนึ่งของวัน": 2,
    "เกือบทุกวัน": 3,
}


# -----------------------------
# Page introduction: Trust by Design
# -----------------------------
st.title("🧠 แบบคัดกรองสุขภาพใจนักศึกษา")

st.success(
    "ยินดีต้อนรับ แบบคัดกรองนี้ออกแบบมาเพื่อช่วยให้สถานพยาบาลเข้าใจสุขภาพของนักศึกษา "
    "และดูแลได้เหมาะสมยิ่งขึ้น ไม่มีคำตอบที่ถูกหรือผิด"
)

st.info(
    "🔒 ข้อมูลนี้เป็นข้อมูลสุขภาพ ใช้เพื่อการคัดกรองและการดูแลเท่านั้น "
    "ไม่ส่งข้อมูลรายบุคคลให้คณะ อาจารย์ หรือผู้ฝึกสอน และไม่มีผลต่อผลการเรียนหรือสถานภาพนักศึกษา "
    "เว้นแต่มีความเสี่ยงเร่งด่วนต่อชีวิตหรือความปลอดภัย ซึ่งจะเปิดเผยเท่าที่จำเป็นเพื่อช่วยเหลือ"
)

st.warning(
    "แบบประเมินนี้เป็นการคัดกรองเบื้องต้น ไม่ใช่การวินิจฉัยโรค "
    "หากมีความคิดทำร้ายตนเองหรือรู้สึกไม่ปลอดภัย กรุณาแจ้งเจ้าหน้าที่สถานพยาบาลทันที"
)

with st.expander("อ่านก่อนทำแบบคัดกรอง: ความลับและการดูแล", expanded=False):
    st.markdown(
        """
        - แบบคัดกรองนี้ช่วยให้สถานพยาบาลรู้ว่าควรดูแลหรือติดตามนักศึกษาอย่างไร
        - ผลที่ได้เป็นเพียงสัญญาณคัดกรอง ไม่ใช่การติดป้ายหรือวินิจฉัยโรค
        - หากพบความเสี่ยง เจ้าหน้าที่สุขภาพจะพูดคุยเป็นการส่วนตัวเพื่อยืนยันข้อมูลและเข้าใจบริบทก่อน
        - หากไม่สะดวกตอบบางข้อ สามารถเลือก “ไม่ประสงค์ตอบ” ในหัวข้อที่มีตัวเลือกนี้ได้
        """
    )


# -----------------------------
# Accessibility Profile
# -----------------------------
st.header("0) การเข้าถึงและความสะดวกในการใช้ระบบ")
st.caption("หัวข้อนี้ช่วยให้เราปรับวิธีให้บริการ ไม่ใช่การประเมินความสามารถของนักศึกษา")

needs_assistance = st.checkbox("ต้องการให้เจ้าหน้าที่ช่วยกรอกข้อมูล")
large_text = st.checkbox("ต้องการตัวอักษรใหญ่หรืออ่านคำถามช้า ๆ")
communication_text = st.checkbox("ต้องการสื่อสารด้วยการอ่านข้อความ/พิมพ์ มากกว่าการพูด")
sign_language = st.checkbox("ใช้ภาษามือ หรือต้องการผู้ช่วยสื่อสาร")
upper_limb_difference = st.checkbox("มีความแตกต่างของแขน/มือ หรือใช้หน้าจอสัมผัสลำบาก")
mobility_support = st.checkbox("ใช้อุปกรณ์ช่วยเคลื่อนไหว หรือต้องการความช่วยเหลือในการเคลื่อนย้าย")
other_accessibility = st.text_input("ความต้องการอื่น ๆ เพื่อให้ใช้ระบบได้สะดวกขึ้น", placeholder="เช่น ขอให้เพื่อนช่วยอ่านคำถาม")

accessibility_notes = []
if needs_assistance:
    accessibility_notes.append("staff_assisted")
if large_text:
    accessibility_notes.append("large_text_or_slow_reading")
if communication_text:
    accessibility_notes.append("text_based_communication")
if sign_language:
    accessibility_notes.append("sign_language_or_communication_support")
if upper_limb_difference:
    accessibility_notes.append("upper_limb_difference_or_touch_difficulty")
if mobility_support:
    accessibility_notes.append("mobility_support")
if other_accessibility:
    accessibility_notes.append(f"other: {other_accessibility.strip()}")

if accessibility_notes:
    st.info("รับทราบครับ/ค่ะ ระบบจะบันทึกความต้องการนี้เพื่อให้เจ้าหน้าที่ช่วยดูแลอย่างเหมาะสม")


# -----------------------------
# Student ID
# -----------------------------
if "student_ID" not in st.session_state:
    st.session_state["student_ID"] = ""

st.header("1) ยืนยันตัวตนนักศึกษา")
st.caption("หากสแกน QR ไม่สะดวก สามารถกรอก Student ID หรือให้เจ้าหน้าที่ช่วยได้")

qr_img = st.camera_input("เปิดกล้องมือถือเพื่อถ่าย QR Code ของตนเอง")

if qr_img:
    qr_text = read_qr_from_image(qr_img)
    if qr_text:
        st.session_state["student_ID"] = extract_student_id(qr_text)
        st.success(f"อ่าน QR สำเร็จ: {st.session_state['student_ID']}")
    else:
        st.error("ยังอ่าน QR ไม่ได้ กรุณาถ่ายใหม่ให้ QR ชัดเจน หรือกรอก Student ID แทน")

manual_student_id = st.text_input(
    "หรือกรอก Student ID แทน",
    value=st.session_state["student_ID"]
)

if manual_student_id:
    st.session_state["student_ID"] = manual_student_id.strip()

if not st.session_state["student_ID"]:
    st.info("กรุณาสแกน QR หรือกรอก Student ID ก่อนเริ่มแบบคัดกรอง")
    st.stop()

student_id = st.session_state["student_ID"]
st.info(f"Student ID: {student_id}")


# -----------------------------
# PHQ-2 / PHQ-9
# -----------------------------
st.header("2) อารมณ์และความสนใจในช่วง 2 สัปดาห์ที่ผ่านมา")
st.caption("ตอบตามความรู้สึกจริงของตนเอง ไม่มีคำตอบถูกหรือผิด")

phq1 = st.radio("1. เบื่อ ไม่สนใจ หรือไม่เพลิดเพลินกับสิ่งต่าง ๆ", list(score_options.keys()))
phq2 = st.radio("2. รู้สึกเศร้า หดหู่ หรือสิ้นหวัง", list(score_options.keys()))

phq2_score = score_options[phq1] + score_options[phq2]
phq_status = phq_color(phq2_score)

st.caption("บันทึกคำตอบส่วนนี้แล้ว")

phq9_score = None
suicide_risk = False
suicide_answers = {}

if phq2_score >= 3:
    st.subheader("PHQ-9 เพิ่มเติม")

    phq_items = [
        "3. หลับยาก หลับ ๆ ตื่น ๆ หรือหลับมากเกินไป",
        "4. เหนื่อยง่าย หรือไม่ค่อยมีแรง",
        "5. เบื่ออาหาร หรือกินมากเกินไป",
        "6. รู้สึกไม่ดีกับตัวเอง ล้มเหลว หรือทำให้ตนเอง/ครอบครัวผิดหวัง",
        "7. สมาธิไม่ดี เช่น อ่านหนังสือหรือดูสื่อไม่รู้เรื่อง",
        "8. พูดหรือทำอะไรช้าลง หรือกระสับกระส่ายมากกว่าปกติ",
        "9. คิดว่าตายไปเสียคงจะดี หรือคิดทำร้ายตนเอง",
    ]

    phq_extra_scores = []
    for item in phq_items:
        ans = st.radio(item, list(score_options.keys()), key=item)
        phq_extra_scores.append(score_options[ans])

    phq9_score = phq2_score + sum(phq_extra_scores)
    phq_status = phq_color(phq9_score)

    st.caption("บันทึกคำตอบส่วนนี้แล้ว")

    if phq9_score >= 10 or phq_extra_scores[-1] > 0:
        st.subheader("คำถามเพิ่มเติมด้านความปลอดภัย")
        st.info("คำถามนี้มีไว้เพื่อช่วยเหลืออย่างทันท่วงที ไม่ใช่การตำหนิหรือตัดสิน")

        s1 = st.radio("ช่วงนี้เคยรู้สึกว่าชีวิตไม่มีค่า หรือไม่อยากมีชีวิตอยู่หรือไม่", ["ไม่ใช่", "ใช่"])
        s2 = st.radio("เคยคิดทำร้ายตนเองหรือไม่", ["ไม่ใช่", "ใช่"])
        s3 = st.radio("มีแผนหรือวิธีที่จะทำร้ายตนเองหรือไม่", ["ไม่ใช่", "ใช่"])
        s4 = st.radio("ขณะนี้รู้สึกไม่ปลอดภัยกับตนเองหรือไม่", ["ไม่ใช่", "ใช่"])

        suicide_answers = {
            "suicide_life_not_worth": s1,
            "suicide_self_harm_thought": s2,
            "suicide_plan": s3,
            "suicide_current_unsafe": s4,
        }

        suicide_risk = any(x == "ใช่" for x in [s1, s2, s3, s4])

        if suicide_risk:
            st.error("เพื่อความปลอดภัย กรุณาแจ้งเจ้าหน้าที่สถานพยาบาลทันที ไม่ควรอยู่คนเดียว")
        else:
            st.info("ขอบคุณที่ตอบคำถามส่วนนี้ เจ้าหน้าที่สุขภาพอาจพูดคุยเพิ่มเติมอย่างเป็นส่วนตัวหากจำเป็น")


# -----------------------------
# GAD-2 / GAD-7
# -----------------------------
st.header("3) ความกังวลในช่วง 2 สัปดาห์ที่ผ่านมา")

gad1 = st.radio("1. รู้สึกกังวล ตื่นเต้น หรือกระวนกระวาย", list(score_options.keys()))
gad2 = st.radio("2. ไม่สามารถหยุดหรือควบคุมความกังวลได้", list(score_options.keys()))

gad2_score = score_options[gad1] + score_options[gad2]
gad_status = gad_color(gad2_score)

st.caption("บันทึกคำตอบส่วนนี้แล้ว")

gad7_score = None

if gad2_score >= 3:
    st.subheader("GAD-7 เพิ่มเติม")

    gad_items = [
        "3. กังวลมากเกินไปในเรื่องต่าง ๆ",
        "4. ผ่อนคลายได้ยาก",
        "5. กระสับกระส่ายจนอยู่นิ่งได้ยาก",
        "6. หงุดหงิดง่าย",
        "7. รู้สึกกลัวเหมือนว่าจะมีเรื่องร้ายเกิดขึ้น",
    ]

    gad_extra_scores = []
    for item in gad_items:
        ans = st.radio(item, list(score_options.keys()), key=item)
        gad_extra_scores.append(score_options[ans])

    gad7_score = gad2_score + sum(gad_extra_scores)
    gad_status = gad_color(gad7_score)

    st.caption("บันทึกคำตอบส่วนนี้แล้ว")


# -----------------------------
# Life and social factors
# -----------------------------
st.header("4) ปัจจัยชีวิตและสังคม")
st.caption("หัวข้อนี้ช่วยให้สถานพยาบาลเห็นบริบทของชีวิตนักศึกษา เพื่อวางแผนช่วยเหลืออย่างเหมาะสม")

sleep_hours = st.slider("ชั่วโมงการนอนต่อคืน", 0.0, 14.0, 7.0, 0.5)
sleep_status = sleep_color(sleep_hours)
st.caption(f"บันทึกชั่วโมงการนอน: {sleep_hours} ชม.")

loneliness = st.slider("ความโดดเดี่ยว 1=น้อยที่สุด, 5=มากที่สุด", 1, 5, 3)
exercise = st.slider("การออกกำลังกาย 1=น้อยที่สุด, 5=มากที่สุด", 1, 5, 3)
academic = st.slider("ภาระการเรียน 1=น้อยที่สุด, 5=มากที่สุด", 1, 5, 3)
family = st.slider("ปัญหาครอบครัว 1=น้อยที่สุด, 5=มากที่สุด", 1, 5, 1)
sexual = st.slider("ปัญหาเพศสัมพันธ์ 1=น้อยที่สุด, 5=มากที่สุด", 1, 5, 1)
financial = st.slider("ปัญหาการเงิน 1=น้อยที่สุด, 5=มากที่สุด", 1, 5, 1)

loneliness_status = likert_risk_color(loneliness)
exercise_status = exercise_color(exercise)
academic_status = likert_risk_color(academic)
family_status = likert_risk_color(family)
sexual_status = likert_risk_color(sexual)
financial_status = likert_risk_color(financial)

st.caption("บันทึกคำตอบปัจจัยชีวิตและสังคมแล้ว")


# -----------------------------
# Substance use: trust-first wording
# -----------------------------
st.header("5) การใช้สาร")
st.info(
    "หัวข้อนี้ใช้เพื่อคัดกรองความเสี่ยงด้านสุขภาพและวางแผนช่วยเหลือเท่านั้น "
    "ข้อมูลรายบุคคลไม่ส่งให้คณะ อาจารย์ หรือผู้ฝึกสอน และไม่มีผลต่อการเรียนหรือการแข่งขันกีฬา"
)

substance_prefer_not = st.checkbox("ไม่ประสงค์ตอบหัวข้อนี้")

if substance_prefer_not:
    smoking = False
    alcohol = False
    cannabis = False
    stimulant = False
    substance_status = "gray"
    st.warning("บันทึกว่าไม่ประสงค์ตอบหัวข้อนี้ เจ้าหน้าที่อาจพูดคุยเพิ่มเติมอย่างเป็นส่วนตัวหากจำเป็น")
else:
    smoking = st.checkbox("บุหรี่")
    alcohol = st.checkbox("แอลกอฮอล์")
    cannabis = st.checkbox("กัญชา")
    stimulant = st.checkbox("ยากระตุ้นจิตประสาท")
    any_substance = smoking or alcohol or cannabis or stimulant
    substance_status = substance_color(any_substance)

st.caption("บันทึกคำตอบหัวข้อนี้แล้ว")


# -----------------------------
# Overall status
# -----------------------------
overall_red = (
    phq_status == "red"
    or gad_status == "red"
    or suicide_risk
    or substance_status == "red"
)

overall_yellow = (
    phq_status == "yellow"
    or gad_status == "yellow"
    or sleep_status == "yellow"
    or loneliness_status == "yellow"
    or exercise_status == "yellow"
    or academic_status == "yellow"
    or family_status == "yellow"
    or sexual_status == "yellow"
    or financial_status == "yellow"
)

if overall_red:
    overall_status = "red"
elif overall_yellow:
    overall_status = "yellow"
else:
    overall_status = "green"


# -----------------------------
# Summary and save
# -----------------------------
st.header("6) สรุปผลก่อนบันทึก")
st.caption("ผลนี้เป็นข้อมูลคัดกรองเพื่อให้เจ้าหน้าที่สุขภาพตรวจทาน ไม่ใช่คำวินิจฉัย")

summary = {
    "student_ID": student_id,
    "timestamp_BKK": bkk_now(),
    "station": "MentalHealth",
    "user_type": "student",

    "accessibility_needs_assistance": needs_assistance,
    "accessibility_large_text": large_text,
    "accessibility_text_based_communication": communication_text,
    "accessibility_sign_language": sign_language,
    "accessibility_upper_limb_difference": upper_limb_difference,
    "accessibility_mobility_support": mobility_support,
    "accessibility_other": other_accessibility.strip() if other_accessibility else "",
    "accessibility_profile": safe_join(accessibility_notes),

    "PHQ2": phq2_score,
    "PHQ9": phq9_score if phq9_score is not None else "",
    "PHQ_status": phq_status,

    "suicide_risk": suicide_risk,
    **suicide_answers,

    "GAD2": gad2_score,
    "GAD7": gad7_score if gad7_score is not None else "",
    "GAD_status": gad_status,

    "sleep_hours": sleep_hours,
    "sleep_status": sleep_status,

    "loneliness": loneliness,
    "loneliness_status": loneliness_status,

    "exercise": exercise,
    "exercise_status": exercise_status,

    "academic_burden": academic,
    "academic_status": academic_status,

    "family_problem": family,
    "family_status": family_status,

    "sexual_problem": sexual,
    "sexual_status": sexual_status,

    "financial_problem": financial,
    "financial_status": financial_status,

    "substance_prefer_not_to_answer": substance_prefer_not,
    "smoking": smoking,
    "alcohol": alcohol,
    "cannabis": cannabis,
    "stimulant": stimulant,
    "substance_status": substance_status,

    "overall_mental_health_status": overall_status,
}

# Do not show backend risk colors or raw scores to students.
# They are saved in GitHub CSV for clinician review and verification.
st.success("ตอบแบบคัดกรองครบแล้ว กรุณาตรวจทานว่ายืนยันส่งข้อมูลได้")

st.info(
    "หากผลคัดกรองมีความเสี่ยง เจ้าหน้าที่สุขภาพจะพูดคุยเพิ่มเติมเป็นการส่วนตัวเพื่อยืนยันข้อมูล "
    "ทำความเข้าใจบริบท และร่วมกันวางแผนดูแล"
)

final_ok = st.checkbox("ยืนยันส่งแบบคัดกรอง โดยเข้าใจว่าข้อมูลนี้ใช้เพื่อการดูแลสุขภาพ")

if st.button("Save ลง GitHub CSV"):
    if not final_ok:
        st.error("กรุณาติ๊กยืนยันก่อนบันทึก")
        st.stop()

    try:
        append_to_github(summary)
        st.success("บันทึกแบบคัดกรองสุขภาพใจลง GitHub CSV แล้ว")
    except Exception as e:
        st.error(f"บันทึก GitHub ไม่สำเร็จ: {e}")

