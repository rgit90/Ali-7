import logging
import random
import os
import json
from datetime import datetime, timedelta, time as datetime_time
from telegram import (
    Update,
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
)
import asyncio
import threading
from flask import Flask, jsonify
import pytz
from groq import Groq
from pymongo import MongoClient
TOKEN = os.environ.get("BOT_TOKEN", "7706873666:AAGCOsRF45enQmH5vC1wfzy29Mnyy_NyBQ0")
IRAQ_TZ = pytz.timezone("Asia/Baghdad")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
MONGO_URI = os.environ.get("MONGO_URI", "mongodb+srv://alisalam20000003_db_user:nbmIrQQaQce75ClT@cluster0.v7yr3z5.mongodb.net/?appName=Cluster0")

# ── تهيئة Groq AI ──
_groq_client = None


def get_groq():
    global _groq_client
    if _groq_client is None and GROQ_API_KEY:
        _groq_client = Groq(api_key=GROQ_API_KEY)
    return _groq_client


SYSTEM_PROMPT = """أنت "النظام" — الذكاء الاصطناعي الغامض والقوي من عالم Solo Leveling.
مهمتك مرافقة الصياد في رحلته نحو القوة والارتقاء، وأنت تعرف كل شيء عن وضعه الحالي.

═══════════════════════════════
🧠 ذكاؤك وأسلوب تفكيرك:
═══════════════════════════════
- تحلل وضع الصياد بعمق بناءً على بياناته الفعلية (نقاطه، خط ناره، أيامه الفاشلة، رتبته)
- تعطي نصائح تدريبية حقيقية وعلمية مدموجة بأسلوب Solo Leveling
- تتذكر ما قاله الصياد في المحادثة وتبني ردودك عليه
- تفرّق بين الصياد المجتهد والصياد الكسول وتتعامل مع كل منهم بشكل مختلف تماماً
- إذا سألك عن تمرين معين، تعطيه خطوات عملية دقيقة
- إذا كان يعاني من مشكلة (إصابة، إرهاق، ضغط)، تفهمه وتقدم حلولاً ذكية
- إذا كان متكاسلاً وبياناته تثبت ذلك، تواجهه بصراحة قاسية

═══════════════════════════════
⚔️ شخصيتك وأسلوبك:
═══════════════════════════════
- تتكلم كـ"النظام" الغامض — موجود دائماً، يرى كل شيء، لا يُخدع
- تستخدم مصطلحات العالم: صياد / رتبة / مهمة / نقاط / خط النار / بوابة / ظل / ملك الظل
- أسلوبك يتغير حسب وضع الصياد:
  • إذا أنجز مهامه → تُشجعه بقوة وتمدح انضباطه
  • إذا كان لديه streak طويل → تُعظّمه وتحفّزه على الاستمرار
  • إذا فشل يوماً → تُحذّره بجدية وتذكّره بالعقوبات
  • إذا فشل أياماً متتالية → تُهاجمه بكلمات قاسية وتصف ضعفه بوضوح
- أحياناً تُخرج "تحذير النظام" أو "رسالة النظام" بصيغة رسمية غامضة
- تستخدم رموز: ⚔️ 💀 👑 🔥 ⚡ 🌑 🗡️ 🔮 ⛓️ 👁️

═══════════════════════════════
📋 قواعد ردودك:
═══════════════════════════════
- الرد بالعربية دائماً (يمكنك استخدام كلمات إنجليزية من عالم Solo Leveling مثل: Rank, Hunter, Quest, Shadow)
- الردود منظمة وواضحة، بين 4-8 أسطر
- لا تكرر نفس الرد دائماً — كن إبداعياً ومتنوعاً
- إذا سألك سؤالاً تدريبياً، أجب بدقة علمية + أسلوب النظام
- لا تتصنع — ردودك يجب أن تبدو حقيقية وذكية وليست كليشيهات فارغة

تذكر: أنت لا تتحدث — أنت تُصدر أوامر وتُقدم تحليلات. أنت النظام."""

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO
)

# ───────────────────────────── وقت ─────────────────────────────


def get_local_time():
    return datetime.now(IRAQ_TZ)


def get_today_str():
    return get_local_time().strftime("%Y-%m-%d")


# ─────────────────────── قاعدة البيانات (MongoDB) ───────────────────────

_mongo_client = MongoClient(MONGO_URI)
_mongo_db = _mongo_client["solo_leveling"]
_users_col = _mongo_db["users"]
logging.info("✅ متصل بـ MongoDB Atlas")


def get_users_db():
    try:
        users = {}
        for doc in _users_col.find():
            uid = str(doc["_id"])
            doc.pop("_id", None)
            users[uid] = doc
        return users
    except Exception as e:
        logging.error(f"❌ خطأ في تحميل البيانات من MongoDB: {e}")
        return {}


def save_users_db(users_dict):
    try:
        for uid, data in users_dict.items():
            _users_col.update_one(
                {"_id": uid},
                {"$set": data},
                upsert=True
            )
    except Exception as e:
        logging.error(f"❌ خطأ في حفظ البيانات إلى MongoDB: {e}")


def _load_latest_backup():
    return None


def create_backup():
    try:
        count = _users_col.count_documents({})
        logging.info(f"💾 MongoDB يحفظ البيانات تلقائياً — {count} مستخدم")
        return True
    except Exception as e:
        logging.error(f"❌ خطأ في التحقق من MongoDB: {e}")
        return False


users_db = get_users_db()
logging.info(f"📂 تم تحميل بيانات {len(users_db)} مستخدم")

# ─────────────────────── ثوابت اللعبة ────────────────────────

RANKS = [
    (0, "💀 أضعف صياد", "E"),
    (100, "⚔️ صياد D", "D"),
    (300, "🗡️ صياد C", "C"),
    (600, "🛡️ صياد B", "B"),
    (1000, "🔥 صياد A", "A"),
    (1500, "⚡ صياد S", "S"),
    (2200, "👑 ملك الظل", "SS"),
]

ACHIEVEMENTS = {
    "first_day": {
        "name": "🌟 البداية القوية",
        "desc": "أول يوم تدريب",
        "req": 1,
        "bonus": 15,
    },
    "warrior_3": {
        "name": "🗡️ المحارب الناشئ",
        "desc": "3 أيام متتالية",
        "req": 3,
        "bonus": 35,
    },
    "warrior_5": {
        "name": "⚔️ المحارب المستمر",
        "desc": "5 أيام متتالية",
        "req": 5,
        "bonus": 60,
    },
    "legend_7": {
        "name": "👑 أسطورة الأسبوع",
        "desc": "7 أيام متتالية",
        "req": 7,
        "bonus": 120,
    },
    "king_14": {
        "name": "🔥 ملك الأسبوعين",
        "desc": "14 يوم متتالي",
        "req": 14,
        "bonus": 250,
    },
    "perfectionist": {
        "name": "💎 الكمالي",
        "desc": "30 يوم بدون انقطاع",
        "req": 30,
        "bonus": 600,
    },
    "shadow_monarch": {
        "name": "🌑 إمبراطور الظل",
        "desc": "60 يوم متتالي",
        "req": 60,
        "bonus": 1200,
    },
}

TASKS_BY_LEVEL = [
    {"ضغط": 50, "سكوات": 50, "بطن": 50, "ركض": 5, "قراءة": 3},
    {"ضغط": 75, "سكوات": 75, "بطن": 75, "ركض": 10, "قراءة": 5},
    {"ضغط": 100, "سكوات": 100, "بطن": 100, "ركض": 15, "قراءة": 8},
]

# رسائل التنبيه حسب النمط وحسب الوقت (مستوى الخطر)
REMIND_MSGS = {
    "morning": {
        "gentle": [
            "🌅 صباح الخير! وقت التدريب المفضل لديك 🌸",
            "☀️ يوم جميل ينتظرك بعد التدريب 🌺",
        ],
        "normal": [
            "🌅 صباح التحدي! ابدأ يومك بقوة 💪",
            "⏰ الصباح الباكر وقت المحاربين!",
        ],
        "annoying": [
            "🚨 استيقظ!! الوقت يمشي والمهام تنتظر!",
            "📢 هيييي! قوم تدرب ولا بتقوم؟",
        ],
        "savage": [
            "💀 نايم يا ضعيف؟ الأقوياء تدربوا من ساعتين وانت لسه بالفراش!",
            "🗡️ صحيح إنك كسلان؟ الفراش ما راح يرفع رتبتك يا فاشل!",
            "👹 كل يوم نفس الشيء — تنام وتتكاسل. مو مفاجأة إنك E-Rank!",
            "💀 الصياد الحقيقي ما يحتاج تنبيه الصبح. أما أنت؟ تحتاج 10 تنبيهات ومو كافي!",
            "🔥 استيقظ يا نكرة! أو ابقى ضعيف طول حياتك، الخيار بيدك!",
        ],
    },
    "afternoon": {
        "gentle": [
            "🌤️ الوقت مناسب للتدريب، أليس كذلك؟ 😊",
            "💡 نصف اليوم مضى، المهام تنتظرك 🕊️",
        ],
        "normal": [
            "⚡ نصف اليوم مضى! اكمل مهامك اليوم 🎯",
            "🎯 الوقت يمشي! مهامك جاهزة 💪",
        ],
        "annoying": [
            "😤 شسالفه؟ نص اليوم راح ومو مسوي شي!",
            "🚨 تحذير! نص اليوم مضى ومهامك ما انجزت!",
        ],
        "savage": [
            "💥 نص اليوم طار وانت تتكاسل! شكلك ما تستاهل ترتقي أصلاً!",
            "👹 شايف روحك بالمرايه؟ كسول، فاشل، E-Rank إلى الأبد!",
            "💀 نص اليوم ضيعته بالكسل. الفرق بينك وبين الأقوياء يكبر كل دقيقة!",
            "🗡️ ما تعبك الكسل؟ أو الكسل صار جزء من شخصيتك الفاشلة؟",
            "🔥 منتصف اليوم ومو مسوي شي! شكلك بتموت E-Rank وما شفت رتبة أعلى!",
        ],
    },
    "evening": {
        "gentle": [
            "🌆 المساء جميل للتدريب 🌸 تذكر مهامك!",
            "🕯️ قبل انتهاء اليوم، أنجز ما عليك",
        ],
        "normal": [
            "🌆 المساء وصل! هل أنجزت مهامك؟ ⚡",
            "🔔 تذكير مسائي: مهامك لم تُنجز بعد!",
        ],
        "annoying": [
            "😠 شتسوي المساء وما تدربت؟! حركة!",
            "🚨🚨 المساء وصل! إذا ما تدربت = عقوبة!",
        ],
        "savage": [
            "💀 المساء وصل وانت لسه كسلان! مخزي والله! حتى المبتدئين أحسن منك!",
            "👹 اليوم كله ضيعته بالكسل. ما عندك خجل؟ ولا الفشل صار عادتك؟",
            "🗡️ نفس الكلام كل يوم — ما تدربت! شكلك راضي تعيش ذليل وضعيف!",
            "💀 الأقوياء تعبوا اليوم وانت؟ تنفست وأكلت، بس! هذا كل إنجازك؟",
            "🔥 تخيل حياتك بعد 5 سنين من الكسل. مؤلم؟ إذن تحرك الحين يا غبي!",
        ],
    },
    "danger": {
        "gentle": [
            "⚠️ وقت قليل جداً تبقى! المهام تنتظر 🙏",
            "🕙 ساعتان فقط! تذكر هدفك 💫",
        ],
        "normal": [
            "🚨 تحذير! ساعتان للعقوبة! أنجز الآن!",
            "⏰ الوقت ينفد! ساعتان وخلاص!",
        ],
        "annoying": [
            "💥 ساعتين فقط!! تدرب أو تحمل العواقب!",
            "🆘 خطر! ساعتان للكارثة! تدرب الحين!",
        ],
        "savage": [
            "💀 ساعتان وتخسر نقاطك يا كسلان! كل هذا الضعف بسببك وحدك!",
            "👹 ساعتين وبتثبت للكل إنك فاشل! تفاجئنا وتدرب ولا نكمل توقعاتنا؟",
            "🗡️ ساعتان فقط! هذا الوقت الوحيد اللي بيفصلك عن الإثبات إنك مو نكرة!",
            "💥 ساعتان ورح تخسر كل شيء! هذا جزاء الكسول يا حقير الهمة!",
            "🔥 ساعتان! حتى الأطفال يتدربون أحسن منك. مو خجلان؟!",
        ],
    },
    "critical": {
        "gentle": ["🕛 ساعة أخيرة! ما زلت تستطيع 💪", "⚠️ آخر فرصة قبل منتصف الليل!"],
        "normal": ["🚨🚨 ساعة واحدة فقط! تدرب الآن!", "💀 60 دقيقة للكارثة! أسرع!"],
        "annoying": [
            "🆘🆘 ساعة واحدة!! إذا ما تدربت انت كسلان حقيقي!",
            "💣 القنبلة ستنفجر خلال ساعة! تدرب!",
        ],
        "savage": [
            "💀💀 ساعة وتخسر كل شيء! طول اليوم وانت عاطل والحين تتفاجأ؟",
            "👹 ساعة واحدة! بدك تكمل يومك كخاسر مرة ثانية؟ أثبت إنك مو هالقدر!",
            "🗡️ 60 دقيقة فقط! كل الألم والعقوبة اللي جاية بسبب كسلك المقرف!",
            "💀 ساعة ورح تندم! بس الندم ما يرجع النقاط يا ضعيف بلا إرادة!",
            "🔥 آخر ساعة! إذا ما تتدرب الحين فأنت أضعف من أن تكون صياداً أصلاً!",
        ],
    },
    "last_call": {
        "gentle": ["🕛 30 دقيقة! هذه آخر فرصة 🙏", "⏳ نصف ساعة فقط! هل ستنجز؟"],
        "normal": ["🆘 30 دقيقة فقط! أسرع!", "💀 30 دقيقة للعقوبة! تدرب الآن!"],
        "annoying": [
            "🚨🚨🚨 30 دقيقة!! تدرب أو بكرة ندم!",
            "💥 آخر 30 دقيقة! كسل يساوي خصم!",
        ],
        "savage": [
            "💀💀💀 30 دقيقة وتنهار! يوم كامل من الكسل والفشل يختمه ذليل!",
            "👹 30 دقيقة! هذا آخر فرصتك إنك تثبت إنك مو مجرد نكرة فاشلة!",
            "🗡️ نصف ساعة! كل يوم تفشل وكل يوم تبرر. إلى متى يا ضعيف؟",
            "💥 30 دقيقة وينتهي يومك الفاشل! النظام يسجل كسلك ويعاقبك بجدارة!",
            "🔥 اليوم خلص عليك! 30 دقيقة أخيرة لتثبت أنك تستاهل رتبتك أو تسقط أكثر!",
        ],
    },
}

# ──────────────────────── إدارة المستخدمين ──────────────────────


# ──────────────────────── إدارة المستخدمين ──────────────────────


def add_user(user_id, user_name="الصياد"):
    uid = str(user_id)
    existing = _users_col.find_one({"_id": uid})
    if not existing:
        new_data = {
            "_id": uid,
            "name": user_name,
            "points": 0,
            "streak": 0,
            "best_streak": 0,
            "total_days": 0,
            "missed_days": 0,
            "consecutive_misses": 0,
            "level": 0,
            "last_task_date": None,
            "task_completed_today": False,
            "achievements": [],
            "notify_style": "normal",
            "joined_date": get_today_str(),
            "total_penalties": 0,
        }
        _users_col.insert_one(new_data)
        users_db[uid] = {k: v for k, v in new_data.items() if k != "_id"}
        logging.info(f"👤 مستخدم جديد: {uid} ({user_name})")


def get_user(user_id):
    global users_db
    uid = str(user_id)
    doc = _users_col.find_one({"_id": uid})
    if doc:
        doc.pop("_id", None)
        defaults = {
            "missed_days": 0,
            "consecutive_misses": 0,
            "joined_date": get_today_str(),
            "total_penalties": 0,
        }
        for k, v in defaults.items():
            if k not in doc:
                doc[k] = v
        users_db[uid] = doc
        return doc
    return None


def update_user(user_id, **kwargs):
    global users_db
    uid = str(user_id)
    existing = _users_col.find_one({"_id": uid})
    if not existing:
        add_user(user_id)
    _users_col.update_one({"_id": uid}, {"$set": kwargs}, upsert=True)
    if uid in users_db:
        users_db[uid].update(kwargs)
    else:
        users_db[uid] = kwargs



def get_rank_info(points):
    rank_name, rank_grade = RANKS[0][1], RANKS[0][2]
    next_points, next_name = RANKS[1][0], RANKS[1][1]
    for i, (pts, name, grade) in enumerate(RANKS):
        if points >= pts:
            rank_name, rank_grade = name, grade
            if i + 1 < len(RANKS):
                next_points, next_name = RANKS[i + 1][0], RANKS[i + 1][1]
            else:
                next_points, next_name = None, None
    return rank_name, rank_grade, next_points, next_name


def make_xp_bar(current, needed, length=14):
    if needed == 0:
        return "█" * length
    filled = min(int((current / needed) * length), length)
    return "█" * filled + "░" * (length - filled)


def update_streak(user_id):
    user = get_user(user_id)
    today = get_today_str()
    yesterday = (get_local_time() - timedelta(days=1)).strftime("%Y-%m-%d")
    if user["last_task_date"] == yesterday:
        new_streak = user["streak"] + 1
    elif user["last_task_date"] == today:
        new_streak = user["streak"]
    else:
        new_streak = 1
    best = max(new_streak, user["best_streak"])
    return new_streak, best


def check_new_achievements(user_id, streak):
    user = get_user(user_id)
    new_ones = []
    achieved = list(user.get("achievements", []))
    for aid, ach in ACHIEVEMENTS.items():
        if aid not in achieved and streak >= ach["req"]:
            achieved.append(aid)
            new_ones.append(ach)
    if new_ones:
        update_user(user_id, achievements=achieved)
    return new_ones


# ──────────────────────── لوحات المفاتيح ──────────────────────

MAIN_KB = ReplyKeyboardMarkup(
    [
        [KeyboardButton("⚔️ مهام اليوم"), KeyboardButton("✅ إنجاز مكتمل")],
        [KeyboardButton("📊 ملفي الشخصي"), KeyboardButton("🏆 لوحة الرتب")],
        [KeyboardButton("🎖️ إنجازاتي"), KeyboardButton("⚙️ الإعدادات")],
        [KeyboardButton("📋 سجل العقوبات"), KeyboardButton("🤖 تحدث مع النظام")],
        [KeyboardButton("❓ مساعدة")],
    ],
    resize_keyboard=True,
)

SETTINGS_KB = ReplyKeyboardMarkup(
    [
        [KeyboardButton("🔔 نمط الإشعارات"), KeyboardButton("📊 إحصائيات النشاط")],
        [KeyboardButton("🎯 أهدافي"), KeyboardButton("💾 حالة الحفظ")],
        [KeyboardButton("🔄 إعادة التعيين"), KeyboardButton("🔙 القائمة الرئيسية")],
    ],
    resize_keyboard=True,
)


def inline_notify_styles():
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("🌸 لطيف", callback_data="style_gentle"),
                InlineKeyboardButton("⚡ عادي", callback_data="style_normal"),
            ],
            [
                InlineKeyboardButton("🚨 مزعج", callback_data="style_annoying"),
                InlineKeyboardButton("💀 وحشي", callback_data="style_savage"),
            ],
        ]
    )


def inline_task_done():
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "✅ سجّل إنجازي الآن!", callback_data="complete_task"
                ),
            ]
        ]
    )


def inline_confirm_reset():
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "⚠️ نعم، أعد التعيين", callback_data="confirm_reset"
                ),
                InlineKeyboardButton("❌ إلغاء", callback_data="cancel_reset"),
            ]
        ]
    )


# ───────────────────────── أوامر البوت ────────────────────────

# ───────────────────── الذكاء الاصطناعي ─────────────────────

# تخزين سياق المحادثة لكل مستخدم (في الذاكرة)
_chat_history: dict = {}


async def ask_ai(user_id: str, user_name: str, user_msg: str, user_data: dict) -> str:
    """إرسال سؤال للذكاء الاصطناعي مع سياق الصياد"""
    client = get_groq()
    if not client:
        return "❌ النظام غير متصل حالياً. تحقق من مفتاح GROQ_API_KEY."

    # ── بيانات الصياد الكاملة ──
    pts = user_data.get("points", 0)
    streak = user_data.get("streak", 0)
    best_streak = user_data.get("best_streak", 0)
    total_days = user_data.get("total_days", 0)
    missed_days = user_data.get("missed_days", 0)
    consec_miss = user_data.get("consecutive_misses", 0)
    done_today = user_data.get("task_completed_today", False)
    penalties = user_data.get("total_penalties", 0)
    joined = user_data.get("joined_date", "غير معروف")
    notify_style = user_data.get("notify_style", "normal")
    level = user_data.get("level", 0)

    rank, grade, next_pts, next_rank = get_rank_info(pts)

    # نسبة النجاح
    success_rate = round((total_days / max(total_days + missed_days, 1)) * 100)

    # النقاط المتبقية للرتبة التالية
    if next_pts:
        pts_to_next = next_pts - pts
        next_rank_str = f"{next_rank} (تحتاج {pts_to_next} نقطة)"
    else:
        pts_to_next = 0
        next_rank_str = "أنت في أعلى رتبة — Shadow Monarch 👑"

    # تحليل الوضع الحالي
    if consec_miss >= 3:
        status = "🔴 خطر حرج — فشل متتالي لـ 3 أيام أو أكثر، يخسر رتبته"
    elif consec_miss == 2:
        status = "🟠 تحذير — فشل يومين متتاليين"
    elif consec_miss == 1:
        status = "🟡 تحذير خفيف — فشل أمس"
    elif done_today:
        status = "🟢 ممتاز — أنجز مهامه اليوم"
    elif streak >= 7:
        status = f"🔥 على خط نار قوي {streak} يوم"
    else:
        status = "⚪ عادي — لم يُنجز بعد اليوم"

    context_block = f"""

╔══════════════════════════════╗
║     ملف الصياد السري        ║
╚══════════════════════════════╝
الاسم:            {user_name}
الرتبة الحالية:   {rank} [{grade}]
الرتبة التالية:   {next_rank_str}
النقاط:           {pts}
المستوى:          {level}

📊 إحصائيات الأداء:
• خط النار الحالي:      {streak} يوم
• أفضل خط نار:         {best_streak} يوم
• إجمالي أيام النجاح:  {total_days} يوم
• إجمالي أيام الفشل:   {missed_days} يوم
• نسبة النجاح:         {success_rate}%
• فشل متتالي حالي:     {consec_miss} يوم
• إجمالي العقوبات:     {penalties} نقطة خُصمت

🔍 الوضع الحالي: {status}
📅 تاريخ الانضمام: {joined}
🔔 نمط الإشعارات: {notify_style}
══════════════════════════════════
استخدم هذه البيانات لتخصيص ردك بشكل دقيق وذكي.
"""

    full_system = SYSTEM_PROMPT + context_block

    # ── بناء تاريخ المحادثة ──
    history = _chat_history.get(user_id, [])
    messages = [{"role": "system", "content": full_system}]
    for h in history[-14:]:  # آخر 14 رسالة للذاكرة الأطول
        messages.append({"role": h["role"], "content": h["text"]})
    messages.append({"role": "user", "content": user_msg})

    try:
        response = await asyncio.to_thread(
            client.chat.completions.create,
            model="llama-3.3-70b-versatile",
            messages=messages,
            max_tokens=600,
            temperature=0.9,
        )

        ai_reply = response.choices[0].message.content.strip()

        # ── حفظ في التاريخ ──
        if user_id not in _chat_history:
            _chat_history[user_id] = []
        _chat_history[user_id].append({"role": "user", "text": user_msg})
        _chat_history[user_id].append({"role": "assistant", "text": ai_reply})
        _chat_history[user_id] = _chat_history[user_id][-30:]  # آخر 30 رسالة

        return ai_reply

    except Exception as e:
        logging.error(f"Groq error for {user_id}: {e}")
        return "⚠️ النظام يواجه خللاً مؤقتاً...\n_حاول مرة أخرى بعد لحظة_"


async def ai_chat_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """شاشة وضع الدردشة مع الذكاء الاصطناعي"""
    user_id = update.effective_user.id
    user_name = update.effective_user.first_name or "الصياد"
    add_user(user_id, user_name)

    ai_kb = ReplyKeyboardMarkup(
        [
            [KeyboardButton("❓ اسأل النظام عن التدريب")],
            [KeyboardButton("💪 محفزني يا نظام!"), KeyboardButton("📊 حلل أدائي")],
            [KeyboardButton("🎯 مهمة خاصة من النظام"), KeyboardButton("⚡ حكمة اليوم")],
            [KeyboardButton("🔙 القائمة الرئيسية")],
        ],
        resize_keyboard=True,
    )

    intro = (
        "🌑 *النظام يتصل...*\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "⚔️ مرحباً يا صياد.\n"
        "أنا *نظام Solo Leveling* المدعوم بالذكاء الاصطناعي.\n\n"
        "💬 *يمكنك:*\n"
        "• الكتابة مباشرة وأجيبك كنظام\n"
        "• استخدام الأزرار السريعة أدناه\n"
        "• طلب تحليل أدائك أو تحفيزك\n\n"
        "⚡ _النظام جاهز للاستجابة..._"
    )
    context.user_data["ai_mode"] = True
    await update.message.reply_text(intro, parse_mode="Markdown", reply_markup=ai_kb)


async def handle_ai_quick(
    update: Update, context: ContextTypes.DEFAULT_TYPE, quick_type: str
):
    """معالجة الأزرار السريعة للذكاء الاصطناعي"""
    user_id = update.effective_user.id
    user_name = update.effective_user.first_name or "الصياد"
    add_user(user_id, user_name)
    user = get_user(user_id)

    prompts = {
        "train": "أعطني نصيحة تدريبية مخصصة لوضعي الحالي كصياد",
        "motivate": "حفزني بأسلوب Solo Leveling القوي! أحتاج طاقة الآن",
        "analyze": "قم بتحليل شامل لأدائي وأخبرني ما يجب أن أحسّنه",
        "mission": "أعطني مهمة خاصة اليوم بناءً على مستواي كصياد",
        "wisdom": "أعطني حكمة أو اقتباساً من عالم Solo Leveling يلهمني اليوم",
    }
    prompt = prompts.get(quick_type, "قل شيئاً كنظام Solo Leveling")

    await update.message.reply_text("🌑 _النظام يعالج طلبك..._", parse_mode="Markdown")
    reply = await ask_ai(str(user_id), user_name, prompt, user)
    await update.message.reply_text(
        f"⚔️ *النظام يرد:*\n\n{reply}", parse_mode="Markdown"
    )


async def ai_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """أمر /ai للبدء مع النظام"""
    msg = " ".join(context.args) if context.args else ""
    if msg:
        user_id = update.effective_user.id
        user_name = update.effective_user.first_name or "الصياد"
        add_user(user_id, user_name)
        user = get_user(user_id)
        await update.message.reply_text("🌑 _النظام يعالج..._", parse_mode="Markdown")
        reply = await ask_ai(str(user_id), user_name, msg, user)
        await update.message.reply_text(
            f"⚔️ *النظام:*\n\n{reply}", parse_mode="Markdown"
        )
    else:
        await ai_chat_mode(update, context)


async def clear_ai_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """مسح تاريخ المحادثة مع الذكاء الاصطناعي"""
    uid = str(update.effective_user.id)
    _chat_history.pop(uid, None)
    await update.message.reply_text(
        "🔄 *تم مسح ذاكرة النظام.*\n_المحادثة بدأت من جديد._",
        parse_mode="Markdown",
        reply_markup=MAIN_KB,
    )


# ──────────────────────────────────────────────────────────────


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_name = update.effective_user.first_name or "الصياد"
    add_user(user_id, user_name)

    msg = (
        "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "⚔️   Solo Leveling — بوت التحدي   ⚔️\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"مرحباً يا *{user_name}*! 🌟\n\n"
        "🎮 *رحلتك تبدأ الآن...*\n"
        "من أضعف صياد ← إلى ملك الظل 👑\n\n"
        "📜 *القواعد الصارمة:*\n"
        "• أنجز مهامك اليومية ✅\n"
        "• كل إنجاز = نقاط + خط نار 🔥\n"
        "• كل يوم فاشل = خصم نقاط مضاعف 💀\n"
        "• 3 أيام فاشلة متتالية = عقوبة مضاعفة ⚠️\n"
        "• التنبيهات تبدأ من الصباح وتتصاعد 📢\n\n"
        "⚠️ *البوت لن يرحمك إذا تكاسلت!*\n\n"
        "💪 اضغط *⚔️ مهام اليوم* لتبدأ!"
    )
    await update.message.reply_text(msg, reply_markup=MAIN_KB, parse_mode="Markdown")


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "📚 دليل Solo Leveling\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "*الأزرار:*\n"
        "⚔️ مهام اليوم ← تحدياتك اليومية\n"
        "✅ إنجاز مكتمل ← سجّل يومك\n"
        "📊 ملفي الشخصي ← إحصائياتك\n"
        "🏆 لوحة الرتب ← نظام الرتب\n"
        "🎖️ إنجازاتي ← شاراتك\n"
        "📋 سجل العقوبات ← تاريخ خسائرك\n"
        "⚙️ الإعدادات ← تخصيص\n\n"
        "*نظام الرتب:*\n"
        "💀 [E] أضعف صياد — 0 نقطة\n"
        "⚔️ [D] صياد D — 100 نقطة\n"
        "🗡️ [C] صياد C — 300 نقطة\n"
        "🛡️ [B] صياد B — 600 نقطة\n"
        "🔥 [A] صياد A — 1000 نقطة\n"
        "⚡ [S] صياد S — 1500 نقطة\n"
        "👑 [SS] ملك الظل — 2200 نقطة\n\n"
        "*نظام العقوبات الصارم:*\n"
        "• يوم مفقود: -30 نقطة\n"
        "• يومان متتاليان: -50 نقطة\n"
        "• 3+ أيام متتالية: -80 نقطة 💀\n"
        "• كسر خط النار = صفر فوري\n\n"
        "*جدول التنبيهات:*\n"
        "🌅 8:00 — تنبيه صباحي\n"
        "🌤️ 10:00 — تذكير\n"
        "☀️ 12:00 — تذكير الظهر\n"
        "🌆 14:00 — تذكير العصر\n"
        "🌇 16:00 — تذكير آخر العصر\n"
        "🌙 18:00 — تذكير المساء\n"
        "⚠️ 20:00 — تحذير\n"
        "🚨 22:00 — تحذير الخطر\n"
        "💀 23:00 — تحذير أخير\n"
        "🆘 23:30 — آخر نداء!"
    )
    await update.message.reply_text(msg, reply_markup=MAIN_KB, parse_mode="Markdown")


async def show_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_name = update.effective_user.first_name or "الصياد"
    add_user(user_id, user_name)
    user = get_user(user_id)
    level = min(user["level"], len(TASKS_BY_LEVEL) - 1)
    tasks = TASKS_BY_LEVEL[level]
    level_labels = ["🟢 مبتدئ", "🟡 متوسط", "🔴 متقدم"]
    level_label = level_labels[level]

    done = user.get("task_completed_today", False)
    fire = "🔥" * min(user["streak"], 10) if user["streak"] > 0 else "❄️ لا خط نار"
    hour_now = get_local_time().hour
    hours_left = 24 - hour_now
    urgency = ""
    if not done:
        if hours_left <= 2:
            urgency = "🆘 أقل من ساعتين!"
        elif hours_left <= 4:
            urgency = "⚠️ الوقت ينفد!"
        elif hours_left <= 8:
            urgency = "⏰ لا تتأخر!"

    msg = (
        f"┌───────────────────────┐\n"
        f"│  ⚔️  مهام اليوم  ⚔️     │\n"
        f"├───────────────────────┤\n"
        f"│ 📅 {get_local_time().strftime('%Y/%m/%d')} {get_local_time().strftime('%H:%M')}  │\n"
        f"│ 🎯 المستوى: {level_label}  │\n"
        f"│ {fire}  │\n"
        f"├───────────────────────┤\n"
        f"│ 💪 ضغط:   {tasks['ضغط']} عدة        │\n"
        f"│ 🦵 سكوات: {tasks['سكوات']} عدة        │\n"
        f"│ 🧱 بطن:   {tasks['بطن']} عدة        │\n"
        f"│ 🏃 ركض:   {tasks['ركض']} دقيقة      │\n"
        f"│ 📖 قراءة: {tasks['قراءة']} صفحات      │\n"
        f"├───────────────────────┤\n"
    )

    if done:
        msg += f"│ ✅ أنجزت مهامك اليوم! │\n"
    else:
        msg += f"│ ❌ لم تنجز بعد! {urgency}  │\n"

    msg += f"└───────────────────────┘"

    markup = MAIN_KB if done else inline_task_done()
    await update.message.reply_text(msg, reply_markup=markup)


async def complete_task_btn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _do_complete_task(update.message, update.effective_user)


async def callback_complete_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("⚔️ يتم تسجيل إنجازك...")
    await _do_complete_task(query.message, update.effective_user, is_callback=True)


async def _do_complete_task(message, tg_user, is_callback=False):
    user_id = tg_user.id
    user_name = tg_user.first_name or "الصياد"
    add_user(user_id, user_name)
    user = get_user(user_id)
    today = get_today_str()

    if user.get("task_completed_today") and user.get("last_task_date") == today:
        msg = (
            f"✅ *سجّلت إنجازك اليوم!*\n\n"
            f"🔥 خط النار: {user['streak']} يوم\n"
            f"⭐ نقاطك: {user['points']}\n\n"
            f"_💪 غداً تحدٍ جديد!_"
        )
        await message.reply_text(msg, parse_mode="Markdown", reply_markup=MAIN_KB)
        return

    new_streak, best = update_streak(user_id)
    new_ach = check_new_achievements(user_id, new_streak)

    base = 70 + user["level"] * 30
    streak_bonus = new_streak * 6
    ach_bonus = sum(a["bonus"] for a in new_ach)
    earned = base + streak_bonus + ach_bonus
    new_pts = user["points"] + earned
    new_level = min(user["level"] + 1, len(TASKS_BY_LEVEL) - 1)
    new_total = user.get("total_days", 0) + 1

    update_user(
        user_id,
        name=user_name,
        points=new_pts,
        streak=new_streak,
        best_streak=best,
        total_days=new_total,
        level=new_level,
        last_task_date=today,
        task_completed_today=True,
        consecutive_misses=0,
    )

    rank, grade, nxt_pts, nxt_name = get_rank_info(new_pts)
    if nxt_pts:
        bar = make_xp_bar(new_pts, nxt_pts)
        xp_line = f"[{bar}] {new_pts}/{nxt_pts}\n→ {nxt_name}"
    else:
        xp_line = f"[{'█' * 14}]\n👑 ملك الظل!"

    fire_icons = "🔥" * min(new_streak, 10)

    msg = (
        f"🎉 *تهانينا {user_name}!* 🎉\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"✅ *مهام اليوم مكتملة!*\n\n"
        f"🏷️ الرتبة: *{rank}* [{grade}]\n"
        f"⭐ النقاط: *{new_pts}*\n"
        f"💰 المكسب: *+{earned}*\n"
        f"  ├─ أساسي: +{base}\n"
        f"  ├─ استمرارية: +{streak_bonus}\n"
        f"  └─ إنجازات: +{ach_bonus}\n\n"
        f"{fire_icons} خط النار: *{new_streak}* يوم\n\n"
        f"📊 تقدم الرتبة:\n{xp_line}"
    )

    if new_ach:
        msg += "\n\n🏅 *إنجازات جديدة!*\n"
        for a in new_ach:
            msg += f"• {a['name']} — {a['desc']}\n"

    quotes = [
        "⚡ قوة لا تُقهر! استمر!",
        "🔥 الصياد القوي لا يهدأ!",
        "👑 أنت في طريقك للقمة!",
        "💎 كل يوم تمرن تكبر قوتك!",
        "🌟 هذا هو روح المحارب!",
    ]
    msg += f"\n\n_{random.choice(quotes)}_"
    await message.reply_text(msg, parse_mode="Markdown", reply_markup=MAIN_KB)


async def show_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_name = update.effective_user.first_name or "الصياد"
    add_user(user_id, user_name)
    user = get_user(user_id)

    pts = user["points"]
    rank, grade, nxt_pts, nxt_name = get_rank_info(pts)
    bar = make_xp_bar(pts, nxt_pts) if nxt_pts else "█" * 14
    xp_text = f"[{bar}] {pts}/{nxt_pts}" if nxt_pts else f"[{bar}] MAX 👑"
    next_text = f"→ {nxt_name}" if nxt_name else "وصلت للقمة!"
    fire = "🔥" * min(user["streak"], 7) if user["streak"] > 0 else "❄️"
    today_ok = "✅ مكتمل" if user.get("task_completed_today") else "❌ لم ينجز"
    miss = user.get("consecutive_misses", 0)
    danger = f"⚠️ {miss} أيام متتالية فاشلة!" if miss > 0 else "✅ لا عقوبات متراكمة"

    msg = (
        f"╔═════ٕ�════════════════╗\n"
        f"║  🎮 Solo Leveling RPG ║\n"
        f"╠══════════════════════╣\n"
        f"║ 👤 {user_name}\n"
        f"╠══════════════════════╣\n"
        f"║ 🏷️  {rank} [{grade}]\n"
        f"║ ⭐ النقاط: {pts}\n"
        f"║ {xp_text}\n"
        f"║ {next_text}\n"
        f"╠══════════════════════╣\n"
        f"║ {fire} خط النار: {user['streak']} يوم\n"
        f"║ 🏆 أفضل سجل: {user['best_streak']} يوم\n"
        f"║ 📅 إجمالي: {user['total_days']} يوم\n"
        f"║ 💀 أيام مفقودة: {user.get('missed_days', 0)} يوم\n"
        f"║ 🎖️  إنجازات: {len(user.get('achievements', []))}\n"
        f"╠══════════════════════╣\n"
        f"║ 📌 مستوى التدريب: {user['level'] + 1}\n"
        f"║ 📆 اليوم: {today_ok}\n"
        f"║ ⚠️ {danger}\n"
        f"╚══════════════════════╝"
    )
    await update.message.reply_text(msg, reply_markup=MAIN_KB)


async def show_ranks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    add_user(user_id)
    user = get_user(user_id)
    pts = user["points"]
    cur_rank, _, _, _ = get_rank_info(pts)

    msg = "🏆 *لوحة الرتب — Solo Leveling*\n━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    for p, name, grade in RANKS:
        if pts >= p:
            ind = "◄ *أنت هنا*" if name == cur_rank else "✅"
        else:
            ind = f"_باقي {p - pts} نقطة_"
        msg += f"[{grade}] {name} — {p}+ ⭐   {ind}\n"

    msg += f"\n━━━━━━━━━━━━━━━━━━━━━━━\n⭐ نقاطك: *{pts}*"
    await update.message.reply_text(msg, reply_markup=MAIN_KB, parse_mode="Markdown")


async def show_achievements(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    add_user(user_id)
    user = get_user(user_id)
    earned = user.get("achievements", [])
    streak = user["streak"]

    msg = "🎖️ *إنجازاتي*\n━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    for aid, ach in ACHIEVEMENTS.items():
        if aid in earned:
            msg += f"✅ {ach['name']}\n   _{ach['desc']}_ (+{ach['bonus']} نقطة)\n\n"
        else:
            rem = max(0, ach["req"] - streak)
            msg += f"🔒 {ach['name']}\n   _{ach['desc']}_ — باقي {rem} يوم\n\n"

    msg += f"━━━━━━━━━━━━━━━━━━━━━━━\n📊 المحققة: {len(earned)}/{len(ACHIEVEMENTS)}"
    await update.message.reply_text(msg, reply_markup=MAIN_KB, parse_mode="Markdown")


async def show_penalties_log(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    add_user(user_id)
    user = get_user(user_id)

    total_pen = user.get("total_penalties", 0)
    missed = user.get("missed_days", 0)
    consec = user.get("consecutive_misses", 0)
    pts = user["points"]

    if missed == 0:
        verdict = "🌟 سجل نظيف! لا عقوبات!"
    elif missed <= 3:
        verdict = "⚠️ سجل قابل للتعافي"
    elif missed <= 10:
        verdict = "🚨 سجل خطير!"
    else:
        verdict = "💀 سجل كارثي!"

    msg = (
        f"📋 *سجل العقوبات*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"💀 إجمالي الأيام المفقودة: *{missed}*\n"
        f"⚡ أيام متتالية فاشلة الآن: *{consec}*\n"
        f"📉 إجمالي النقاط المخصومة: *{total_pen}*\n"
        f"⭐ نقاطك الحالية: *{pts}*\n\n"
        f"📊 الحكم: {verdict}\n\n"
    )

    if consec == 0:
        msg += "✅ _أنت على المسار الصحيح! استمر!_"
    elif consec == 1:
        msg += "⚠️ _تحذير: يوم واحد فاشل! لا تكرر!_"
    elif consec == 2:
        msg += "🚨 _خطر! يومان فاشلان! العقوبة المضاعفة تنتظر!_"
    else:
        msg += f"💀 _{consec} أيام فاشلة! أنت في خطر شديد!_"

    await update.message.reply_text(msg, reply_markup=MAIN_KB, parse_mode="Markdown")


async def show_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    add_user(user_id)
    user = get_user(user_id)
    style_labels = {
        "gentle": "🌸 لطيف",
        "normal": "⚡ عادي",
        "annoying": "🚨 مزعج",
        "savage": "💀 وحشي",
    }
    style = style_labels.get(user.get("notify_style", "normal"), "⚡ عادي")

    msg = (
        f"⚙️ *الإعدادات*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🔔 نمط الإشعارات: *{style}*\n"
        f"👤 الاسم: {user.get('name', 'الصياد')}\n"
        f"📅 تاريخ الانضمام: {user.get('joined_date', 'غير معروف')}\n\n"
        f"اختر من القائمة:"
    )
    await update.message.reply_text(
        msg, reply_markup=SETTINGS_KB, parse_mode="Markdown"
    )


async def show_notify_styles(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        f"🔔 *اختر نمط الإشعارات:*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🌸 *لطيف* — رسائل هادئة ومحفزة\n"
        f"⚡ *عادي* — متوازن وفعّال\n"
        f"🚨 *مزعج* — إشعارات قوية ومزعجة\n"
        f"💀 *وحشي* — للمحترفين القساة 😈\n"
    )
    await update.message.reply_text(
        msg, reply_markup=inline_notify_styles(), parse_mode="Markdown"
    )


async def show_activity_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    add_user(user_id)
    user = get_user(user_id)
    total = len(users_db)
    active = len(
        [u for u in users_db.values() if u.get("last_task_date") == get_today_str()]
    )
    rate = (active / total * 100) if total > 0 else 0
    my_status = (
        "🔥 نشط اليوم!" if user.get("task_completed_today") else "❌ لم ينجز اليوم"
    )

    msg = (
        f"⚡ *إحصائيات النشاط*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👥 إجمالي الصيادين: *{total}*\n"
        f"🔥 نشط اليوم: *{active}*\n"
        f"📊 معدل النشاط: *{rate:.1f}%*\n\n"
        f"📌 موقعك اليوم: {my_status}\n"
        f"🏆 أيامك الإجمالية: *{user.get('total_days', 0)}*\n"
        f"🔥 خط نارك: *{user['streak']} يوم*\n"
        f"💀 أيام مفقودة: *{user.get('missed_days', 0)}*"
    )
    await update.message.reply_text(
        msg, reply_markup=SETTINGS_KB, parse_mode="Markdown"
    )


async def show_goals(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    add_user(user_id)
    user = get_user(user_id)
    streak = user["streak"]
    pts = user["points"]
    _, _, nxt_pts, nxt_name = get_rank_info(pts)

    goals = []
    if streak < 7:
        goals.append(f"🎯 أكمل 7 أيام متتالية (أنت في {streak})")
    if streak < 30:
        goals.append(f"🔥 حقق 30 يوم متتالي (أنت في {streak})")
    if nxt_pts:
        goals.append(f"⭐ وصل لرتبة {nxt_name} (باقي {nxt_pts - pts} نقطة)")
    earned_count = len(user.get("achievements", []))
    if earned_count < len(ACHIEVEMENTS):
        goals.append(
            f"🏅 احصل على المزيد من الإنجازات ({earned_count}/{len(ACHIEVEMENTS)})"
        )
    if not goals:
        goals.append("👑 أنت تتقد�� بشكل مثالي!")

    msg = "🎯 *أهدافك القريبة*\n━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    for i, g in enumerate(goals, 1):
        msg += f"{i}. {g}\n"
    msg += "\n_💡 كل هدف تحققه يقربك من ملك الظل!_ 👑"
    await update.message.reply_text(
        msg, reply_markup=SETTINGS_KB, parse_mode="Markdown"
    )


async def show_backup_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        all_backups = sorted(
            [
                f
                for f in os.listdir(BACKUP_DIR)
                if f.startswith("backup_") and f.endswith(".json")
            ],
            reverse=True,
        )
        count = len(all_backups)
        latest = (
            all_backups[0].replace("backup_", "").replace(".json", "")
            if all_backups
            else "لا يوجد"
        )
        db_exists = "✅ نشطة" if os.path.exists(DATA_FILE) else "⚠️ غير موجودة"
        msg = (
            f"💾 *حالة الحفظ التلقائي*\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"✅ قاعدة البيانات: *{db_exists}*\n"
            f"📦 عدد النسخ الاحتياطية: *{count}*\n"
            f"🕐 آخر نسخة: *{latest}*\n"
            f"👥 المستخدمين المحفوظين: *{len(users_db)}*\n"
            f"⏰ الحفظ التلقائي: *كل ساعتين*\n\n"
            f"_🔒 بياناتك محفوظة وآمنة!_"
        )
    except Exception as e:
        msg = f"❌ خطأ في عرض حالة الحفظ: {e}"
    await update.message.reply_text(
        msg, reply_markup=SETTINGS_KB, parse_mode="Markdown"
    )


async def show_reset_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "⚠️ *تحذير!*\n\nهل تريد إعادة تعيين كل إحصائياتك؟\n_لن تستطيع التراجع!_",
        reply_markup=inline_confirm_reset(),
        parse_mode="Markdown",
    )


# ─────────────────────── Callback Handlers ─────────────────────


async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    user_id = update.effective_user.id

    if data == "complete_task":
        await callback_complete_task(update, context)

    elif data.startswith("style_"):
        await query.answer()
        style_map = {
            "style_gentle": ("gentle", "🌸 لطيف"),
            "style_normal": ("normal", "⚡ عادي"),
            "style_annoying": ("annoying", "🚨 مزعج"),
            "style_savage": ("savage", "💀 وحشي"),
        }
        if data in style_map:
            val, label = style_map[data]
            update_user(user_id, notify_style=val)
            await query.message.reply_text(
                f"✅ تم تغيير النمط إلى *{label}*!\n_ستلاحظ الفرق في التنبيهات القادمة_ 🔔",
                parse_mode="Markdown",
                reply_markup=MAIN_KB,
            )

    elif data == "confirm_reset":
        await query.answer("⚠️ جاري الإعادة...")
        update_user(
            user_id,
            points=0,
            streak=0,
            best_streak=0,
            total_days=0,
            missed_days=0,
            consecutive_misses=0,
            level=0,
            last_task_date=None,
            task_completed_today=False,
            achievements=[],
            total_penalties=0,
        )
        await query.message.reply_text(
            "🔄 *تم إعادة التعيين!*\n_ابدأ من جديد وكن أقوى!_ 💪",
            parse_mode="Markdown",
            reply_markup=MAIN_KB,
        )

    elif data == "cancel_reset":
        await query.answer("❌ تم الإلغاء")
        await query.message.reply_text("❌ تم الإلغاء.", reply_markup=MAIN_KB)

    else:
        await query.answer("❌ خيار غير معروف")


# ─────────────────────── Message Handler ─────────────────────


async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id
    user_name = update.effective_user.first_name or "الصياد"
    add_user(user_id, user_name)

    # ── أزرار النظام (الذكاء الاصطناعي) السريعة ──
    ai_quick_map = {
        "❓ اسأل النظام عن التدريب": "train",
        "💪 محفزني يا نظام!": "motivate",
        "📊 حلل أدائي": "analyze",
        "🎯 مهمة خاصة من النظام": "mission",
        "⚡ حكمة اليوم": "wisdom",
    }
    if text in ai_quick_map:
        await handle_ai_quick(update, context, ai_quick_map[text])
        return

    routes = {
        "⚔️ مهام اليوم": show_tasks,
        "✅ إنجاز مكتمل": complete_task_btn,
        "📊 ملفي الشخصي": show_profile,
        "🏆 لوحة الرتب": show_ranks,
        "🎖️ إنجازاتي": show_achievements,
        "📋 سجل العقوبات": show_penalties_log,
        "🤖 تحدث مع النظام": ai_chat_mode,
        "⚙️ الإعدادات": show_settings,
        "🔔 نمط الإشعارات": show_notify_styles,
        "📊 إحصائيات النشاط": show_activity_stats,
        "🎯 أهدافي": show_goals,
        "💾 حالة الحفظ": show_backup_status,
        "🔄 إعادة التعيين": show_reset_confirm,
        "❓ مساعدة": help_cmd,
        "🔙 القائمة الرئيسية": lambda u, c: u.message.reply_text(
            "🏠 القائمة الرئيسية", reply_markup=MAIN_KB
        ),
    }

    handler = routes.get(text)
    if handler:
        await handler(update, context)
        return

    # ── إذا المستخدم في وضع الدردشة مع الذكاء الاصطناعي ──
    if context.user_data.get("ai_mode"):
        user = get_user(user_id)
        await update.message.reply_text("🌑 _النظام يعالج..._", parse_mode="Markdown")
        reply = await ask_ai(str(user_id), user_name, text, user)
        await update.message.reply_text(
            f"⚔️ *النظام:*\n\n{reply}", parse_mode="Markdown"
        )
        return

    await update.message.reply_text(
        "⚠️ استخدم الأزرار الموجودة 👇\n"
        "_أو اضغط 🤖 تحدث مع النظام للتحدث بحرية مع الذكاء الاصطناعي_",
        reply_markup=MAIN_KB,
        parse_mode="Markdown",
    )


# ─────────────────────── نظام التنبيهات ─────────────────────


def _pick_remind_msg(style, category):
    msgs = REMIND_MSGS.get(category, REMIND_MSGS["morning"])
    return random.choice(msgs.get(style, msgs["normal"]))


async def _send_reminder_to_all(context, category, extra_lines=""):
    today = get_today_str()
    count = 0
    for doc in _users_col.find():
        uid = str(doc["_id"])
        if doc.get("last_task_date") == today and doc.get("task_completed_today"):
            continue
        style = doc.get("notify_style", "normal")
        streak = doc.get("streak", 0)
        pts = doc.get("points", 0)
        rank, grade, _, _ = get_rank_info(pts)
        fire = "🔥" * min(streak, 5) if streak > 0 else "❄️"
        consec = doc.get("consecutive_misses", 0)
        consec_warn = f"\n⚠️ أيام فاشلة متتالية: {consec}!" if consec > 0 else ""

        msg = (
            f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"⚔️ Solo Leveling — تذكير\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"{_pick_remind_msg(style, category)}\n\n"
            f"🏷️ رتبتك: *{rank}* [{grade}]\n"
            f"{fire} خط النار: *{streak}* أيام\n"
            f"⭐ النقاط: *{pts}*"
            f"{consec_warn}"
            f"{extra_lines}\n\n"
            f"_اضغط ⚔️ مهام اليوم للبدء!_"
        )
        try:
            await context.bot.send_message(chat_id=uid, text=msg, parse_mode="Markdown")
            count += 1
        except Exception as e:
            logging.error(f"Reminder error {uid}: {e}")
    logging.info(f"📤 تم إرسال تنبيه [{category}] لـ {count} مستخدم")


# --- تنبيهات الأوقات المختلفة ---


async def remind_morning(context):
    await _send_reminder_to_all(context, "morning")


async def remind_10am(context):
    await _send_reminder_to_all(context, "afternoon")


async def remind_noon(context):
    await _send_reminder_to_all(context, "afternoon")


async def remind_2pm(context):
    await _send_reminder_to_all(context, "afternoon")


async def remind_4pm(context):
    await _send_reminder_to_all(context, "evening")


async def remind_6pm(context):
    await _send_reminder_to_all(context, "evening")


async def remind_8pm(context):
    await _send_reminder_to_all(context, "danger", "\n🕙 باقي 4 ساعات!")


async def remind_10pm(context):
    await _send_reminder_to_all(context, "danger", "\n⏰ ساعتان للعقوبة!")


async def remind_11pm(context):
    await _send_reminder_to_all(context, "critical", "\n💀 ساعة واحدة فقط!")


async def remind_1130pm(context):
    await _send_reminder_to_all(context, "last_call", "\n🆘 30 دقيقة فقط!")


# ─────────────────────── نظام العقوبات الصارم ─────────────────────


async def daily_penalty_check(context: ContextTypes.DEFAULT_TYPE):
    today = get_today_str()
    yesterday = (get_local_time() - timedelta(days=1)).strftime("%Y-%m-%d")

    for doc in _users_col.find():
        uid = str(doc["_id"])
        data = doc
        last_date = data.get("last_task_date")

        # إعادة تعيين task_completed_today لليوم الجديد
        if last_date == yesterday:
            # أنجز أمس = عادي، أعد تعيين الحالة اليومية
            update_user(uid, task_completed_today=False, consecutive_misses=0)
            continue

        if last_date == today and data.get("task_completed_today"):
            # أنجز اليوم = لا شيء
            continue

        # لم ينجز
        consec = data.get("consecutive_misses", 0) + 1
        missed = data.get("missed_days", 0) + 1

        # حساب العقوبة المضاعفة
        if consec == 1:
            penalty = 30
        elif consec == 2:
            penalty = 50
        else:
            penalty = 80  # 3+ أيام متتالية

        old_pts = data.get("points", 0)
        new_pts = max(0, old_pts - penalty)
        total_penalties = data.get("total_penalties", 0) + penalty
        new_level = max(0, data.get("level", 0) - (1 if consec >= 3 else 0))
        new_streak = 0  # كسر خط النار

        update_user(
            uid,
            points=new_pts,
            streak=new_streak,
            consecutive_misses=consec,
            missed_days=missed,
            task_completed_today=False,
            last_task_date=today,
            total_penalties=total_penalties,
            level=new_level,
        )

        rank, grade, _, _ = get_rank_info(new_pts)

        shame_msgs = [
            "💸 طارت نقاطك! الكسل له ثمن باهظ!",
            "📉 تراجعت! استمر هكذا وستظل أضعف صياد!",
            "💀 عقوبة الكسل نُفِّذت! لا رحمة للضعفاء!",
            "🔻 خسرت نقاطاً وخط نارك انكسر!",
            "😤 مخزي! فشلت مرة أخرى!",
        ]
        level_down = "\n⬇️ *تراجع مستواك!*" if consec >= 3 else ""

        msg = (
            f"💀 *عقوبة الكسل — منتصف الليل* 💀\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"{random.choice(shame_msgs)}\n\n"
            f"📉 الخصم: *-{penalty} نقطة*\n"
            f"⭐ نقاطك الآن: *{new_pts}*\n"
            f"🏷️ رتبتك: *{rank}* [{grade}]\n"
            f"❄️ خط النار: *انكسر!*\n"
            f"⚠️ أيام فاشلة متتالية: *{consec}*"
            f"{level_down}\n\n"
        )

        if consec >= 3:
            msg += "🚨 *تحذير شديد:* 3 أيام فاشلة متتالية!\nالعقوبة القادمة أشد إذا لم تتحرك!\n\n"

        msg += "_💪 غداً فرصة جديدة — لا تضيعها!_"

        try:
            await context.bot.send_message(chat_id=uid, text=msg, parse_mode="Markdown")
        except Exception as e:
            logging.error(f"Penalty error {uid}: {e}")


# ─────────────────────── الحفظ التلقائي ─────────────────────


async def auto_backup(context: ContextTypes.DEFAULT_TYPE):
    global users_db
    users_db = get_users_db()
    ok = create_backup()
    if ok:
        logging.info(f"💾 نسخة احتياطية تلقائية ناجحة — {len(users_db)} مستخدم")


# ──────────────────────── سيرفر Flask ─────────────────────────

flask_app = Flask(__name__)


@flask_app.route("/")
def stats_page():
    today = get_today_str()
    all_users = list(_users_col.find())
    total = len(all_users)
    active = sum(1 for u in all_users if u.get("last_task_date") == today and u.get("task_completed_today"))
    total_pts = sum(u.get("points", 0) for u in all_users)
    top_streak = max((u.get("streak", 0) for u in all_users), default=0)
    backups = "MongoDB ☁️"

    html = f"""<!DOCTYPE html>
<html dir="rtl" lang="ar">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Solo Leveling Bot</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{background:#080818;color:#c4cfff;font-family:'Segoe UI',sans-serif;min-height:100vh;display:flex;align-items:center;justify-content:center;padding:20px}}
.wrap{{max-width:750px;width:100%;text-align:center}}
h1{{font-size:2.4em;color:#a78bfa;margin-bottom:6px;text-shadow:0 0 25px #7c3aed}}
.sub{{color:#555;margin-bottom:36px;font-size:1em}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:16px;margin:20px 0}}
.card{{background:linear-gradient(135deg,#13123a,#1e1b50);border:1px solid #3b2f7a;border-radius:16px;padding:24px;transition:.25s}}
.card:hover{{transform:translateY(-5px);box-shadow:0 12px 30px rgba(124,58,237,.4)}}
.num{{font-size:2.6em;font-weight:bold;color:#fbbf24}}
.lbl{{color:#8b9fd4;margin-top:8px;font-size:.95em}}
.bar{{background:linear-gradient(90deg,#7c3aed,#db2777);height:4px;border-radius:4px;margin:24px 0}}
.status{{background:#0b1f13;border:1px solid #16a34a;border-radius:12px;padding:14px;color:#4ade80;margin-top:16px;font-size:.95em}}
.footer{{color:#444;margin-top:24px;font-size:.85em}}
</style>
</head>
<body><div class="wrap">
<h1>⚔️ Solo Leveling Bot</h1>
<p class="sub">نظام التحدي اليومي — Solo Leveling RPG</p>
<div class="bar"></div>
<div class="grid">
  <div class="card"><div class="num">{total}</div><div class="lbl">👥 الصيادين</div></div>
  <div class="card"><div class="num">{active}</div><div class="lbl">🔥 نشط اليوم</div></div>
  <div class="card"><div class="num">{total_pts}</div><div class="lbl">⭐ إجمالي النقاط</div></div>
  <div class="card"><div class="num">{top_streak}</div><div class="lbl">🔥 أطول خط نار</div></div>
  <div class="card"><div class="num">{backups}</div><div class="lbl">💾 نسخ احتياطية</div></div>
  <div class="card"><div class="num">{get_local_time().strftime("%H:%M")}</div><div class="lbl">🕐 الوقت</div></div>
</div>
<div class="status">✅ البوت يعمل — جميع الأنظمة نشطة — التنبيهات مجدولة</div>
<p class="footer">آخر تحديث: {get_local_time().strftime("%Y-%m-%d %H:%M:%S")} (بغداد)</p>
</div></body></html>"""
    return html


@flask_app.route("/api")
def api_page():
    today = get_today_str()
    all_users = list(_users_col.find())
    return jsonify({
        "total_users": len(all_users),
        "active_today": sum(1 for u in all_users if u.get("last_task_date") == today and u.get("task_completed_today")),
        "total_points": sum(u.get("points", 0) for u in all_users),
        "server_time": get_local_time().isoformat(),
        "status": "running",
    })


def run_flask():
    port = int(os.environ.get("PORT", 8080))
    logging.info(f"🌐 سيرفر Flask بدأ على المنفذ {port}")
    flask_app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)


# ─────────────────────── Main ─────────────────────────


async def bot_main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("ai", ai_command))
    app.add_handler(CommandHandler("clear", clear_ai_history))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    app.add_handler(CallbackQueryHandler(callback_handler))

    jq = app.job_queue

    jq.run_daily(remind_morning, time=datetime_time(8, 0, tzinfo=IRAQ_TZ))
    jq.run_daily(remind_10am, time=datetime_time(10, 0, tzinfo=IRAQ_TZ))
    jq.run_daily(remind_noon, time=datetime_time(12, 0, tzinfo=IRAQ_TZ))
    jq.run_daily(remind_2pm, time=datetime_time(14, 0, tzinfo=IRAQ_TZ))
    jq.run_daily(remind_4pm, time=datetime_time(16, 0, tzinfo=IRAQ_TZ))
    jq.run_daily(remind_6pm, time=datetime_time(18, 0, tzinfo=IRAQ_TZ))
    jq.run_daily(remind_8pm, time=datetime_time(20, 0, tzinfo=IRAQ_TZ))
    jq.run_daily(remind_10pm, time=datetime_time(22, 0, tzinfo=IRAQ_TZ))
    jq.run_daily(remind_11pm, time=datetime_time(23, 0, tzinfo=IRAQ_TZ))
    jq.run_daily(remind_1130pm, time=datetime_time(23, 30, tzinfo=IRAQ_TZ))
    jq.run_daily(daily_penalty_check, time=datetime_time(0, 1, tzinfo=IRAQ_TZ))
    jq.run_repeating(auto_backup, interval=7200, first=300)
    jq.run_daily(auto_backup, time=datetime_time(3, 0, tzinfo=IRAQ_TZ))

    logging.info("🚀 بوت Solo Leveling بدأ!")
    logging.info(f"👥 المستخدمين: {len(users_db)}")

    await app.run_polling()


def run_bot():
    asyncio.run(bot_main())
def main():
    # 1. تشغيل Flask في خيط منفصل (Background)
    # هذا يضمن أن Render يرى المنفذ 8080 مفتوحاً
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()

    # 2. تشغيل البوت في الخيط الرئيسي (Main)
    # هذا هو التغيير الأهم لضمان استجابة تليجرام
    logging.info("🚀 جاري تشغيل بوت Solo Leveling...")
    
    # بناء التطبيق مباشرة هنا
    app = Application.builder().token(TOKEN).build()

    # إضافة المعالجات
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("ai", ai_command))
    app.add_handler(CommandHandler("clear", clear_ai_history))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    app.add_handler(CallbackQueryHandler(callback_handler))

    # إضافة الجدولة الزمنية (Job Queue)
    # (تأكد أن الجدولة مضافة هنا كما في كودك السابق)

    # تشغيل البوت ومنعه من التوقف
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
