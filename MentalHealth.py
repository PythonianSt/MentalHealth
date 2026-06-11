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


score_options = {
    "ไม่เลย": 0,
    "หลายวัน": 1,
    "มากกว่าครึ่งหนึ่งของวัน": 2,
    "เกือบทุกวัน": 3,
}


st.title("🧠 แบบประเมินสุขภาพจิตนักศึกษา")
st.warning(
    "แบบประเมินนี้เป็นการคัดกรองเบื้องต้น ไม่ใช่การวินิจฉัยโรค "
    "หากมีความคิดทำร้ายตนเองหรือไม่ปลอดภัย กรุณาแจ้งเจ้าหน้าที่สถานพยาบาลทันที"
)

if "student_ID" not in st.session_state:
    st.session_state["student_ID"] = ""

st.header("1) Scan QR Code ของนักศึกษา")

qr_img = st.camera_input("เปิดกล้องมือถือเพื่อถ่าย QR Code ของตนเอง")

if qr_img:
    qr_text = read_qr_from_image(qr_img)
    if qr_text:
        st.session_state["student_ID"] = extract_student_id(qr_text)
        st.success(f"อ่าน QR สำเร็จ: {st.session_state['student_ID']}")
    else:
        st.error("ยังอ่าน QR ไม่ได้ กรุณาถ่ายใหม่ให้ QR ชัดเจน")

manual_student_id = st.text_input(
    "หรือกรอก student_ID แทน",
    value=st.session_state["student_ID"]
)

if manual_student_id:
    st.session_state["student_ID"] = manual_student_id.strip()

if not st.session_state["student_ID"]:
    st.stop()

student_id = st.session_state["student_ID"]
st.info(f"Student ID: {student_id}")


st.header("2) PHQ-2")

phq1 = st.radio("1. เบื่อ ไม่สนใจ หรือไม่เพลิดเพลินกับสิ่งต่าง ๆ", list(score_options.keys()))
phq2 = st.radio("2. รู้สึกเศร้า หดหู่ หรือสิ้นหวัง", list(score_options.keys()))

phq2_score = score_options[phq1] + score_options[phq2]
phq_status = phq_color(phq2_score)

st.markdown(f"### PHQ-2 = {phq2_score} — {color_label(phq_status)}")

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

    st.markdown(f"### PHQ-9 = {phq9_score} — {color_label(phq_status)}")

    if phq9_score >= 10 or phq_extra_scores[-1] > 0:
        st.subheader("Suicide Screening")

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
            st.error("🔴 กรุณาแจ้งเจ้าหน้าที่สถานพยาบาลทันที ไม่ควรอยู่คนเดียว")
        else:
            st.warning("🟡 ควรติดตามและพูดคุยกับเจ้าหน้าที่เมื่อสะดวก")


st.header("3) GAD-2")

gad1 = st.radio("1. รู้สึกกังวล ตื่นเต้น หรือกระวนกระวาย", list(score_options.keys()))
gad2 = st.radio("2. ไม่สามารถหยุดหรือควบคุมความกังวลได้", list(score_options.keys()))

gad2_score = score_options[gad1] + score_options[gad2]
gad_status = gad_color(gad2_score)

st.markdown(f"### GAD-2 = {gad2_score} — {color_label(gad_status)}")

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

    st.markdown(f"### GAD-7 = {gad7_score} — {color_label(gad_status)}")


st.header("4) ปัจจัยชีวิตและสังคม")

sleep_hours = st.slider("ชั่วโมงการนอนต่อคืน", 0.0, 14.0, 7.0, 0.5)
sleep_status = sleep_color(sleep_hours)
st.markdown(f"Sleep: {sleep_hours} ชม. — {color_label(sleep_status)}")

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

st.write("ความโดดเดี่ยว:", color_label(loneliness_status))
st.write("การออกกำลังกาย:", color_label(exercise_status))
st.write("ภาระการเรียน:", color_label(academic_status))
st.write("ปัญหาครอบครัว:", color_label(family_status))
st.write("ปัญหาเพศสัมพันธ์:", color_label(sexual_status))
st.write("ปัญหาการเงิน:", color_label(financial_status))


st.header("5) การใช้สาร")

smoking = st.checkbox("บุหรี่")
alcohol = st.checkbox("แอลกอฮอล์")
cannabis = st.checkbox("กัญชา")
stimulant = st.checkbox("ยากระตุ้นจิตประสาท")

any_substance = smoking or alcohol or cannabis or stimulant
substance_status = substance_color(any_substance)

st.markdown(f"Substance risk — {color_label(substance_status)}")


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


st.header("6) สรุปผลก่อนบันทึก")

summary = {
    "student_ID": student_id,
    "timestamp_BKK": bkk_now(),
    "station": "MentalHealth",
    "user_type": "student",

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

    "smoking": smoking,
    "alcohol": alcohol,
    "cannabis": cannabis,
    "stimulant": stimulant,
    "substance_status": substance_status,

    "overall_mental_health_status": overall_status,
}

st.dataframe(pd.DataFrame([summary]))
st.markdown(f"## Overall: {color_label(overall_status)}")

final_ok = st.checkbox("ยืนยันส่งแบบประเมิน")

if st.button("Save ลง GitHub CSV"):
    if not final_ok:
        st.error("กรุณาติ๊กยืนยันก่อนบันทึก")
        st.stop()

    try:
        append_to_github(summary)
        st.success("บันทึกแบบประเมินสุขภาพจิตลง GitHub CSV แล้ว")
    except Exception as e:
        st.error(f"บันทึก GitHub ไม่สำเร็จ: {e}")