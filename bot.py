import os
import logging
import asyncio
import threading
import http.server
import socketserver
from typing import Dict, Any, List
from datetime import datetime, timezone

from dotenv import load_dotenv
from groq import Groq

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

# ----------------- Basic setup -----------------

load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID")
SUPPORT_CHAT_ID = os.getenv("SUPPORT_CHAT_ID")  # optional, alt chat pentru operatori

if ADMIN_CHAT_ID:
    try:
        ADMIN_CHAT_ID = int(ADMIN_CHAT_ID)
    except ValueError:
        ADMIN_CHAT_ID = None
else:
    ADMIN_CHAT_ID = None

if SUPPORT_CHAT_ID:
    try:
        SUPPORT_CHAT_ID = int(SUPPORT_CHAT_ID)
    except ValueError:
        SUPPORT_CHAT_ID = None

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

if not TELEGRAM_TOKEN or not GROQ_API_KEY:
    logger.error("Missing TELEGRAM_TOKEN or GROQ_API_KEY env vars!")

groq_client = Groq(api_key=GROQ_API_KEY)

LANG_RO = "ro"
LANG_RU = "ru"

(
    GIFT_WHO,
    GIFT_OCCASION,
    GIFT_AGE,
    GIFT_RELATION,
    GIFT_BUDGET,
    GIFT_INTERESTS,
    ORDER_PRODUCT,
    ORDER_NAME,
    ORDER_PHONE,
    ORDER_CITY,
    ORDER_DELIVERY,
    ORDER_ADDRESS,
    ORDER_DATE,
    ORDER_PAYMENT,
    ORDER_COMMENTS,
    ORDER_OCCASION,
    ORDER_SOURCE,
    ORDER_UPSELL,
    ORDER_CONFIRM,
    SUPPORT_MESSAGE,
) = range(20)

# In-memorie pentru rapoarte simple
ORDERS: List[Dict[str, Any]] = []

# --------- PRODUSE ----------

PRODUCTS = [
    {
        "id": "SWEET_BOX",
        "name_ro": "Sweet Box Clasic",
        "name_ru": "Sweet Box Классик",
        "price": 650,
        "description_ro": "Cutie cu mix de dulciuri premium, ambalată gata de oferit.",
        "description_ru": "Коробка с миксом премиальных сладостей, сразу готова к подарку.",
    },
    {
        "id": "ROMANTIC_BOX",
        "name_ro": "Romantic Box",
        "name_ru": "Romantic Box",
        "price": 820,
        "description_ro": "Perfectă pentru iubit/ iubită: dulciuri, lumânare și mic mesaj.",
        "description_ru": "Идеальна для второй половинки: сладости, свеча и милое послание.",
    },
    # TODO: adaugă aici restul boxelor tale reale
]

# --------- Texte în RO / RU ----------

TEXTS: Dict[str, Dict[str, str]] = {
    LANG_RO: {
        "start_choose_lang": "Salut! 👋\nAlege limba în care vrei să vorbim:",
        "menu_title": "Alege ce vrei să facem azi:",
        "btn_catalog": "🛍 Catalog cadouri",
        "btn_ai": "🎁 Consultant AI",
        "btn_order": "📦 Plasează comandă",
        "btn_info": "ℹ️ Despre magazin / Contact",
        "btn_back": "⬅️ Înapoi la meniu",
        "info": (
            "🎁 *Cado Laboratory MD* — botul tău pentru alegerea rapidă a cadoului perfect.\n\n"
            "Lucrăm cu boxe de cadouri dulci pentru zile de naștere, Anul Nou, februarie și alte ocazii speciale.\n\n"
            "📲 Pentru contact direct cu operatorul apasă pe butonul *Contact operator* din meniu "
            "sau scrie-ne pe Instagram."
        ),
        "ai_intro": (
            "Ok, hai să găsim cadoul perfect! 🤖🎁\n\n"
            "Pentru cine este cadoul? (iubită, iubit, prietenă, mamă etc.)"
        ),
        "ask_occasion": "Pentru ce ocazie este cadoul? (zi de naștere, aniversare, 14 februarie, copil, corporate etc.)",
        "ask_age": "Ce vârstă are aproximativ persoana?",
        "ask_relation": "Ce relație ai cu persoana? (iubit/ă, coleg, rudă, prieten etc.)",
        "ask_budget": "Care este bugetul aproximativ pentru cadou?",
        "ask_interests": "Spune-mi câteva preferințe sau detalii: ce îi place, stil, hobby-uri, dulciuri preferate.",
        "ai_thinking": "Analizez informațiile și aleg cele mai potrivite boxe pentru tine... 🤔",
        "ai_error": "A apărut o problemă cu AI-ul. Încearcă din nou sau alege direct din catalog.",
        "ai_done": "Iată ce îți recomand:",
        "ai_message_btn": "✍️ Creează mesaj de felicitare",
        "ai_message_intro": "Iată câteva idei de mesaje de felicitare:",
        "order_from_menu_intro": (
            "Perfect, hai să plasăm o comandă. 📦\n\n"
            "Poți alege cutia din *Catalog cadouri* sau scrie direct numele cutiei dorite."
        ),
        "order_reuse_question": (
            "Ai mai comandat la noi. Vrei să folosim aceleași date de livrare (nume, telefon, oraș, adresă, plată) "
            "ca la ultima comandă?"
        ),
        "btn_reuse_yes": "✅ Da, folosește aceleași date",
        "btn_reuse_no": "✏️ Nu, introdu date noi",
        "order_ask_product": "Scrie numele cutiei pe care o dorești (exact sau aproximativ).",
        "order_ask_name": "Cum te cheamă? (nume și prenume)",
        "order_ask_phone": "Numărul tău de telefon pentru livrare?",
        "order_ask_city": "În ce oraș se face livrarea?",
        "order_ask_delivery": "Cum vrei livrarea?",
        "btn_delivery_courier": "🚚 Livrare la adresă",
        "btn_delivery_pickup": "📍 Ridicare personală",
        "order_ask_address": "Scrie adresa completă de livrare.",
        "order_ask_date": "Când dorești livrarea? (dată și interval orar)",
        "order_ask_payment": "Cum preferi să plătești? (cash, card etc.)",
        "order_ask_comments": "Ai observații speciale? Dacă nu, scrie „nu”.",
        "order_ask_occasion": "Pentru ce ocazie este această comandă? (zi de naștere, aniversare, copil, corporate etc.)",
        "order_ask_source": "Cum ai aflat de noi? (Instagram, recomandare, reclamă etc.)",
        "order_ask_upsell": "Vrei să adaugi ceva mic pe lângă box?",
        "btn_upsell_balloon": "🎈 Balon",
        "btn_upsell_flower": "🌹 Floare",
        "btn_upsell_card": "📝 Mesaj printat",
        "btn_upsell_none": "NU, e ok așa",
        "order_summary_title": "Verifică dacă datele sunt corecte:",
        "order_confirm_btn": "✅ Confirmă comanda",
        "order_edit_btn": "✏️ Modifică (reia datele)",
        "order_cancel_btn": "❌ Anulează",
        "order_confirmed_client": "✅ Comanda ta a fost transmisă! În scurt timp te vom contacta pentru confirmare.",
        "order_cancelled": "Comanda a fost anulată. Poți încerca din nou oricând.",
        "back_to_menu": "Te-am adus înapoi la meniu.",
        "support_intro": (
            "✉️ Scrie aici mesajul tău pentru operator.\n"
            "Eu îl voi trimite mai departe în chatul de lucru. Când ai terminat, poți apăsa *Înapoi la meniu*."
        ),
        "support_sent": "Am trimis mesajul tău operatorului. Îți va răspunde cât mai curând.",
    },
    LANG_RU: {
        "start_choose_lang": "Привет! 👋\nВыбери язык, на котором будем общаться:",
        "menu_title": "Выбери действие:",
        "btn_catalog": "🛍 Каталог подарков",
        "btn_ai": "🎁 Консультант AI",
        "btn_order": "📦 Оформить заказ",
        "btn_info": "ℹ️ О магазине / Контакты",
        "btn_back": "⬅️ Назад в меню",
        "info": (
            "🎁 *Cado Laboratory MD* — твой бот для быстрого подбора идеального подарка.\n\n"
            "Работаем со сладкими подарочными боксами на дни рождения, Новый год, февраль и другие поводы.\n\n"
            "📲 Для прямой связи с оператором жми кнопку *Связаться с оператором* или пиши в Instagram."
        ),
        "ai_intro": (
            "Давай подберём идеальный подарок! 🤖🎁\n\n"
            "Для кого этот подарок? (девушка, парень, подруга, мама и т.д.)"
        ),
        "ask_occasion": "Для какого повода подарок? (день рождения, годовщина, 14 февраля, ребёнку, корпоратив и т.д.)",
        "ask_age": "Сколько человеку примерно лет?",
        "ask_relation": "Какие у вас отношения? (парень/девушка, коллега, родственник, друг и т.д.)",
        "ask_budget": "Какой примерный бюджет на подарок?",
        "ask_interests": "Напиши пару предпочтений: что любит человек, стиль, хобби, любимые сладости.",
        "ai_thinking": "Собираю информацию и подбираю самые подходящие боксы... 🤔",
        "ai_error": "Возникла ошибка при запросе к AI. Попробуй ещё раз или выбери коробку из каталога.",
        "ai_done": "Вот что я рекомендую:",
        "ai_message_btn": "✍️ Создать текст поздравления",
        "ai_message_intro": "Вот несколько идей для поздравительного текста:",
        "order_from_menu_intro": (
            "Отлично, давай оформим заказ. 📦\n\n"
            "Можно выбрать бокс в *Каталоге подарков* или просто написать название нужной коробки."
        ),
        "order_reuse_question": (
            "Ты уже оформлял(а) у нас заказ. Использовать те же данные доставки (имя, телефон, город, адрес, оплата), "
            "что и в прошлый раз?"
        ),
        "btn_reuse_yes": "✅ Да, использовать те же данные",
        "btn_reuse_no": "✏️ Нет, ввести новые",
        "order_ask_product": "Напиши название бокса, который хочешь (точно или примерно).",
        "order_ask_name": "Как тебя зовут? (имя и фамилия)",
        "order_ask_phone": "Твой номер телефона для доставки?",
        "order_ask_city": "В каком городе будет доставка?",
        "order_ask_delivery": "Какой способ доставки хочешь?",
        "btn_delivery_courier": "🚚 Доставка по адресу",
        "btn_delivery_pickup": "📍 Самовывоз",
        "order_ask_address": "Напиши полный адрес доставки.",
        "order_ask_date": "На какую дату и время нужна доставка?",
        "order_ask_payment": "Как удобнее оплатить? (наличные, карта и т.д.)",
        "order_ask_comments": "Есть ли особые пожелания? Если нет, напиши «нет».",
        "order_ask_occasion": "Для какого повода этот заказ? (день рождения, годовщина, ребёнок, корпоратив и т.д.)",
        "order_ask_source": "Откуда ты о нас узнал(а)? (Instagram, рекомендация, реклама и т.д.)",
        "order_ask_upsell": "Хочешь добавить что-то небольшое к боксу?",
        "btn_upsell_balloon": "🎈 Шар",
        "btn_upsell_flower": "🌹 Цветок",
        "btn_upsell_card": "📝 Открытка с текстом",
        "btn_upsell_none": "НЕТ, так достаточно",
        "order_summary_title": "Проверь, всё ли верно:",
        "order_confirm_btn": "✅ Подтвердить заказ",
        "order_edit_btn": "✏️ Изменить (ввести заново)",
        "order_cancel_btn": "❌ Отменить",
        "order_confirmed_client": "✅ Твой заказ отправлен! Мы скоро свяжемся с тобой для подтверждения.",
        "order_cancelled": "Заказ отменён. Можешь оформить новый в любое время.",
        "back_to_menu": "Возвращаю тебя в главное меню.",
        "support_intro": (
            "✉️ Напиши здесь сообщение оператору.\n"
            "Я перешлю его в рабочий чат. Когда закончишь, можешь нажать *Назад в меню*."
        ),
        "support_sent": "Я отправил твоё сообщение оператору. Он ответит как можно скорее.",
    },
}


def get_lang(context: ContextTypes.DEFAULT_TYPE) -> str:
    return context.user_data.get("lang", LANG_RO)


def tr(lang: str, key: str) -> str:
    return TEXTS.get(lang, TEXTS[LANG_RO])[key]


def get_menu_keyboard(lang: str) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [
            [TEXTS[lang]["btn_catalog"], TEXTS[lang]["btn_ai"]],
            [TEXTS[lang]["btn_order"], TEXTS[lang]["btn_info"]],
            [TEXTS[lang]["btn_back"]],
        ],
        resize_keyboard=True,
    )


async def send_text(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    text: str,
    reply_markup=None,
):
    """Trimite mesaj simplu, fără ștergeri agresive."""
    chat = update.effective_chat
    if not chat:
        return None
    msg = await chat.send_message(text, reply_markup=reply_markup)
    return msg


def run_http_server():
    port = int(os.getenv("PORT", "10000"))
    handler = http.server.SimpleHTTPRequestHandler
    with socketserver.TCPServer(("", port), handler) as httpd:
        logger.info(f"HTTP dummy server running on port {port}")
        httpd.serve_forever()


# ----------------- Helperi produse / statistici -----------------


def _find_product_by_id(product_id: str) -> Dict[str, Any] | None:
    for p in PRODUCTS:
        if p["id"] == product_id:
            return p
    return None


def _find_product_by_name_guess(text: str) -> Dict[str, Any] | None:
    text_l = text.lower()
    for p in PRODUCTS:
        if p["name_ro"].lower() in text_l or p["name_ru"].lower() in text_l:
            return p
    return None


def save_order_for_stats(order: Dict[str, Any]):
    """Hook pentru viitor Google Sheets, deocamdată doar log + listă in-memory."""
    ORDERS.append(order)
    logger.info("Order saved for stats: %s", order)


# ----------------- Start & meniu -----------------


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.setdefault("lang", LANG_RO)
    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("🇷🇴 Română", callback_data="lang:ro"),
                InlineKeyboardButton("🇷🇺 Русский", callback_data="lang:ru"),
            ]
        ]
    )
    await send_text(
        update, context, TEXTS[LANG_RO]["start_choose_lang"], reply_markup=keyboard
    )


async def set_language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lang_code = query.data.split(":")[1]
    context.user_data["lang"] = LANG_RO if lang_code == "ro" else LANG_RU
    lang = get_lang(context)
    await send_text(
        update, context, tr(lang, "menu_title"), reply_markup=get_menu_keyboard(lang)
    )


async def back_to_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_lang(context)
    await send_text(
        update, context, tr(lang, "back_to_menu"), reply_markup=get_menu_keyboard(lang)
    )
    return ConversationHandler.END


# ----------------- Info & catalog -----------------


async def info_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_lang(context)
    text = tr(lang, "info")
    await send_text(update, context, text, reply_markup=get_menu_keyboard(lang))


async def show_catalog(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_lang(context)
    lines = []
    keyboard_buttons = []
    for p in PRODUCTS:
        if lang == LANG_RO:
            name = p["name_ro"]
            desc = p["description_ro"]
        else:
            name = p["name_ru"]
            desc = p["description_ru"]
        lines.append(f"• {name} — {p['price']} MDL\n   {desc}")
        keyboard_buttons.append(
            [
                InlineKeyboardButton(
                    f"📦 {name} ({p['price']} MDL)",
                    callback_data=f"order:{p['id']}",
                )
            ]
        )
    text = "\n\n".join(lines)
    keyboard = InlineKeyboardMarkup(keyboard_buttons)
    await send_text(update, context, text, reply_markup=keyboard)


async def show_catalog_from_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await show_catalog(update, context)


# ----------------- Consultant AI cadouri -----------------


async def gift_ai_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_lang(context)
    context.user_data["gift_ai"] = {}
    await send_text(update, context, tr(lang, "ai_intro"))
    return GIFT_WHO


async def gift_ai_who(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_lang(context)
    context.user_data["gift_ai"]["who"] = update.message.text.strip()
    await send_text(update, context, tr(lang, "ask_occasion"))
    return GIFT_OCCASION


async def gift_ai_occasion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_lang(context)
    context.user_data["gift_ai"]["occasion"] = update.message.text.strip()
    await send_text(update, context, tr(lang, "ask_age"))
    return GIFT_AGE


async def gift_ai_age(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_lang(context)
    context.user_data["gift_ai"]["age"] = update.message.text.strip()
    await send_text(update, context, tr(lang, "ask_relation"))
    return GIFT_RELATION


async def gift_ai_relation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_lang(context)
    context.user_data["gift_ai"]["relation"] = update.message.text.strip()
    await send_text(update, context, tr(lang, "ask_budget"))
    return GIFT_BUDGET


async def gift_ai_budget(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_lang(context)
    context.user_data["gift_ai"]["budget"] = update.message.text.strip()
    await send_text(update, context, tr(lang, "ask_interests"))
    return GIFT_INTERESTS


async def gift_ai_interests(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_lang(context)
    context.user_data["gift_ai"]["interests"] = update.message.text.strip()
    await send_text(update, context, tr(lang, "ai_thinking"))

    data = context.user_data["gift_ai"]

    products_text_parts = []
    for p in PRODUCTS:
        if lang == LANG_RO:
            name = p["name_ro"]
            desc = p["description_ro"]
        else:
            name = p["name_ru"]
            desc = p["description_ru"]
        products_text_parts.append(
            f"- ID: {p['id']}, nume: {name}, pret: {p['price']} MDL, descriere: {desc}"
        )
    products_text = "\n".join(products_text_parts)

    if lang == LANG_RO:
        system_prompt = (
            "Ești un consultant de cadouri pentru un magazin de boxe cadouri dulci. "
            "Ai o listă de produse (boxe). În funcție de persoană, ocazie, vârstă, relație, buget și preferințe, "
            "alegi 1-2 boxe din listă și explici foarte pe scurt de ce le recomanzi. "
            "Nu inventa produse noi."
        )
    else:
        system_prompt = (
            "Ты консультант по подаркам в магазине сладких подарочных боксов. "
            "У тебя есть список боксов. В зависимости от человека, повода, возраста, отношений, бюджета и "
            "предпочтений подбери 1–2 бокса из списка и очень кратко объясни, почему именно они. "
            "Не придумывай новых товаров."
        )

    user_prompt = (
        f"Date client:\n"
        f"- Pentru cine: {data['who']}\n"
        f"- Ocazie: {data['occasion']}\n"
        f"- Vârstă: {data['age']}\n"
        f"- Relația: {data['relation']}\n"
        f"- Buget: {data['budget']}\n"
        f"- Preferințe: {data['interests']}\n\n"
        f"Lista boxe disponibile:\n{products_text}\n\n"
        "Răspunde în limba utilizatorului, fă o recomandare clară și menționează ID-ul sau numele boxei."
    )

    try:
        response = await asyncio.to_thread(
            groq_client.chat.completions.create,
            model="llama-3.1-70b-versatile",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.7,
            max_tokens=700,
        )
        ai_text = response.choices[0].message.content.strip()
    except Exception as e:
        logger.exception("Groq error: %s", e)
        if ADMIN_CHAT_ID:
            try:
                await context.bot.send_message(
                    ADMIN_CHAT_ID, f"[AI ERROR] {e!r}"
                )
            except Exception:
                pass
        await send_text(update, context, tr(lang, "ai_error"))
        return ConversationHandler.END

    final_text = f"{tr(lang, 'ai_done')}\n\n{ai_text}"
    keyboard = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(tr(lang, "ai_message_btn"), callback_data="ai:message")],
            [InlineKeyboardButton(tr(lang, "btn_catalog"), callback_data="menu:catalog")],
        ]
    )
    await send_text(update, context, final_text, reply_markup=keyboard)
    return ConversationHandler.END


async def gift_ai_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_lang(context)
    await send_text(
        update, context, tr(lang, "back_to_menu"), reply_markup=get_menu_keyboard(lang)
    )
    return ConversationHandler.END


async def ai_message_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lang = get_lang(context)
    data = context.user_data.get("gift_ai", {})

    if not data:
        await query.edit_message_text(
            "Nu am suficiente informații pentru mesaj. Pornește din nou consultantul AI.",
        )
        return

    if lang == LANG_RO:
        system_prompt = (
            "Ești un copywriter pentru mesaje de felicitare. Generă 2-3 mesaje scurte, calde, "
            "pentru a fi scrise pe un card de cadou."
        )
    else:
        system_prompt = (
            "Ты копирайтер поздравительных текстов. Сгенерируй 2–3 коротких, тёплых текста "
            "для открытки к подарку."
        )

    user_prompt = (
        f"Persoana: {data.get('who')}\n"
        f"Ocazie: {data.get('occasion')}\n"
        f"Relația: {data.get('relation')}\n"
        f"Preferințe: {data.get('interests')}\n\n"
        "Te rugăm să scrii mesajele în limba utilizatorului."
    )
    try:
        response = await asyncio.to_thread(
            groq_client.chat.completions.create,
            model="llama-3.1-70b-versatile",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.8,
            max_tokens=400,
        )
        msg = response.choices[0].message.content.strip()
    except Exception as e:
        logger.exception("Groq error (msg): %s", e)
        if ADMIN_CHAT_ID:
            try:
                await context.bot.send_message(
                    ADMIN_CHAT_ID, f"[AI MSG ERROR] {e!r}"
                )
            except Exception:
                pass
        await query.edit_message_text(tr(lang, "ai_error"))
        return

    text = f"{tr(lang, 'ai_message_intro')}\n\n{msg}"
    await query.edit_message_text(text)


# ----------------- Flow comenzi -----------------


async def order_from_menu_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_lang(context)
    context.user_data["order"] = {}
    last_order = context.user_data.get("last_order")

    if last_order:
        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        tr(lang, "btn_reuse_yes"), callback_data="order_reuse_yes"
                    )
                ],
                [
                    InlineKeyboardButton(
                        tr(lang, "btn_reuse_no"), callback_data="order_reuse_no"
                    )
                ],
            ]
        )
        await send_text(update, context, tr(lang, "order_reuse_question"), reply_markup=keyboard)
        return ORDER_PRODUCT
    else:
        await send_text(update, context, tr(lang, "order_from_menu_intro"))
        await send_text(update, context, tr(lang, "order_ask_product"))
        return ORDER_PRODUCT


async def order_reuse_yes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lang = get_lang(context)
    last_order = context.user_data.get("last_order", {})
    context.user_data["order"] = {
        "product_id": None,
        "product_custom": None,
        "name": last_order.get("name"),
        "phone": last_order.get("phone"),
        "city": last_order.get("city"),
        "delivery_type": last_order.get("delivery_type"),
        "address": last_order.get("address"),
        "payment": last_order.get("payment"),
    }
    await query.edit_message_text(tr(lang, "order_from_menu_intro"))
    await send_text(update, context, tr(lang, "order_ask_product"))
    return ORDER_PRODUCT


async def order_reuse_no(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lang = get_lang(context)
    context.user_data["order"] = {}
    await query.edit_message_text(tr(lang, "order_from_menu_intro"))
    await send_text(update, context, tr(lang, "order_ask_product"))
    return ORDER_PRODUCT


async def order_set_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_lang(context)
    text = update.message.text.strip()
    product = _find_product_by_name_guess(text)
    if product:
        context.user_data["order"]["product_id"] = product["id"]
        context.user_data["order"]["product_custom"] = None
    else:
        context.user_data["order"]["product_id"] = None
        context.user_data["order"]["product_custom"] = text

    if not context.user_data["order"].get("name"):
        await send_text(update, context, tr(lang, "order_ask_name"))
        return ORDER_NAME
    else:
        # avem date reutilizate, sărim direct la data livrării
        await send_text(update, context, tr(lang, "order_ask_date"))
        return ORDER_DATE


async def order_from_catalog_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lang = get_lang(context)
    product_id = query.data.split(":", maxsplit=1)[1]
    context.user_data.setdefault("order", {})
    context.user_data["order"]["product_id"] = product_id
    context.user_data["order"]["product_custom"] = None

    if not context.user_data["order"].get("name"):
        await send_text(update, context, tr(lang, "order_ask_name"))
        return ORDER_NAME
    else:
        await send_text(update, context, tr(lang, "order_ask_date"))
        return ORDER_DATE


async def order_set_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_lang(context)
    context.user_data["order"]["name"] = update.message.text.strip()
    await send_text(update, context, tr(lang, "order_ask_phone"))
    return ORDER_PHONE


async def order_set_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_lang(context)
    context.user_data["order"]["phone"] = update.message.text.strip()
    await send_text(update, context, tr(lang, "order_ask_city"))
    return ORDER_CITY


async def order_set_city(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_lang(context)
    context.user_data["order"]["city"] = update.message.text.strip()

    keyboard = ReplyKeyboardMarkup(
        [
            [tr(lang, "btn_delivery_courier"), tr(lang, "btn_delivery_pickup")],
            [tr(lang, "btn_back")],
        ],
        resize_keyboard=True,
    )
    await send_text(update, context, tr(lang, "order_ask_delivery"), reply_markup=keyboard)
    return ORDER_DELIVERY


async def order_set_delivery(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_lang(context)
    text = update.message.text.strip()
    if text == tr(lang, "btn_delivery_courier"):
        context.user_data["order"]["delivery_type"] = "courier"
        await send_text(update, context, tr(lang, "order_ask_address"), reply_markup=get_menu_keyboard(lang))
        return ORDER_ADDRESS
    elif text == tr(lang, "btn_delivery_pickup"):
        context.user_data["order"]["delivery_type"] = "pickup"
        context.user_data["order"]["address"] = "Ridicare personală"
        await send_text(update, context, tr(lang, "order_ask_date"), reply_markup=get_menu_keyboard(lang))
        return ORDER_DATE
    else:
        await send_text(update, context, tr(lang, "order_ask_delivery"))
        return ORDER_DELIVERY


async def order_set_address(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_lang(context)
    context.user_data["order"]["address"] = update.message.text.strip()
    await send_text(update, context, tr(lang, "order_ask_date"))
    return ORDER_DATE


async def order_set_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_lang(context)
    context.user_data["order"]["date"] = update.message.text.strip()
    if not context.user_data["order"].get("payment"):
        await send_text(update, context, tr(lang, "order_ask_payment"))
        return ORDER_PAYMENT
    else:
        await send_text(update, context, tr(lang, "order_ask_comments"))
        return ORDER_COMMENTS


async def order_set_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_lang(context)
    context.user_data["order"]["payment"] = update.message.text.strip()
    await send_text(update, context, tr(lang, "order_ask_comments"))
    return ORDER_COMMENTS


async def order_set_comments(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_lang(context)
    context.user_data["order"]["comments"] = update.message.text.strip()
    await send_text(update, context, tr(lang, "order_ask_occasion"))
    return ORDER_OCCASION


async def order_set_occasion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_lang(context)
    context.user_data["order"]["occasion"] = update.message.text.strip()
    await send_text(update, context, tr(lang, "order_ask_source"))
    return ORDER_SOURCE


async def order_set_source(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_lang(context)
    context.user_data["order"]["source"] = update.message.text.strip()

    keyboard = ReplyKeyboardMarkup(
        [
            [
                tr(lang, "btn_upsell_balloon"),
                tr(lang, "btn_upsell_flower"),
                tr(lang, "btn_upsell_card"),
            ],
            [tr(lang, "btn_upsell_none")],
            [tr(lang, "btn_back")],
        ],
        resize_keyboard=True,
    )
    await send_text(update, context, tr(lang, "order_ask_upsell"), reply_markup=keyboard)
    return ORDER_UPSELL


async def order_set_upsell(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_lang(context)
    text = update.message.text.strip()
    context.user_data["order"]["upsell"] = text
    await send_text(update, context, "", reply_markup=get_menu_keyboard(lang))  # revenim la meniul principal de butoane

    data = context.user_data["order"]
    product = _find_product_by_id(data.get("product_id"))
    if product:
        name = product["name_ro"] if lang == LANG_RO else product["name_ru"]
        price = product["price"]
    else:
        name = data.get("product_custom") or "Nespecificat"
        price = "—"

    summary_lines = [
        tr(lang, "order_summary_title"),
        "",
        f"🎁 Box: {name} ({price} MDL)",
        f"👤 Nume: {data.get('name')}",
        f"📞 Telefon: {data.get('phone')}",
        f"🏙️ Oraș: {data.get('city')}",
        f"🚚 Tip livrare: {data.get('delivery_type')}",
        f"📍 Adresă: {data.get('address')}",
        f"📅 Livrare: {data.get('date')}",
        f"💳 Plată: {data.get('payment')}",
        f"🎉 Ocazie: {data.get('occasion')}",
        f"📣 Cum a aflat: {data.get('source')}",
        f"➕ Extra: {data.get('upsell')}",
        f"✏️ Observații: {data.get('comments')}",
    ]
    text = "\n".join(line for line in summary_lines if line is not None)

    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(tr(lang, "order_confirm_btn"), callback_data="order_confirm"),
            ],
            [
                InlineKeyboardButton(tr(lang, "order_edit_btn"), callback_data="order_edit"),
            ],
            [
                InlineKeyboardButton(tr(lang, "order_cancel_btn"), callback_data="order_cancel"),
            ],
        ]
    )
    await send_text(update, context, text, reply_markup=keyboard)
    return ORDER_CONFIRM


async def order_confirm_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lang = get_lang(context)
    data = context.user_data.get("order", {})
    product = _find_product_by_id(data.get("product_id"))
    if product:
        name = product["name_ro"] if lang == LANG_RO else product["name_ru"]
        price = product["price"]
    else:
        name = data.get("product_custom") or "Nespecificat"
        price = "—"

    client = query.from_user
    now = datetime.now(timezone.utc)
    order_id = int(now.timestamp())

    order_text = (
        f"📥 Comandă nouă #{order_id}\n\n"
        f"🎁 Box: {name} ({price} MDL)\n"
        f"👤 Nume: {data.get('name')}\n"
        f"📞 Telefon: {data.get('phone')}\n"
        f"🏙️ Oraș: {data.get('city')}\n"
        f"🚚 Tip livrare: {data.get('delivery_type')}\n"
        f"📍 Adresă: {data.get('address')}\n"
        f"📅 Livrare: {data.get('date')}\n"
        f"💳 Plată: {data.get('payment')}\n"
        f"🎉 Ocazie: {data.get('occasion')}\n"
        f"📣 Cum a aflat: {data.get('source')}\n"
        f"➕ Extra: {data.get('upsell')}\n"
        f"✏️ Observații: {data.get('comments')}\n\n"
        f"👤 Client Telegram: @{client.username or 'fără_username'} (ID: {client.id})"
    )

    # salvăm pentru rapoarte / KYC simplu
    stats_record = {
        "order_id": order_id,
        "timestamp": now,
        "product_id": data.get("product_id"),
        "product_name": name,
        "price": price if isinstance(price, (int, float)) else 0,
        "name": data.get("name"),
        "city": data.get("city"),
        "occasion": data.get("occasion"),
        "source": data.get("source"),
    }
    save_order_for_stats(stats_record)

    # reținem ca „ultima comandă” a userului (pentru quick reorder)
    context.user_data["last_order"] = {
        "name": data.get("name"),
        "phone": data.get("phone"),
        "city": data.get("city"),
        "delivery_type": data.get("delivery_type"),
        "address": data.get("address"),
        "payment": data.get("payment"),
    }

    if ADMIN_CHAT_ID:
        admin_keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "✅ Acceptă comanda", callback_data=f"admin_accept:{client.id}"
                    ),
                    InlineKeyboardButton(
                        "❌ Anulează comanda", callback_data=f"admin_reject:{client.id}"
                    ),
                ]
            ]
        )
        try:
            await context.bot.send_message(
                chat_id=ADMIN_CHAT_ID, text=order_text, reply_markup=admin_keyboard
            )
        except Exception as e:
            logger.exception("Failed to send order to admin: %s", e)

    await query.edit_message_text(
        tr(lang, "order_confirmed_client"), reply_markup=get_menu_keyboard(lang)
    )
    return ConversationHandler.END


async def order_admin_decision(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    if ":" not in data:
        return
    action, user_id_str = data.split(":", maxsplit=1)
    try:
        user_id = int(user_id_str)
    except ValueError:
        return

    if not ADMIN_CHAT_ID or query.from_user.id != ADMIN_CHAT_ID:
        await query.edit_message_reply_markup(reply_markup=None)
        return

    if action == "admin_accept":
        try:
            await context.bot.send_message(
                user_id, "✅ Comanda ta a fost confirmată de operator. Mulțumim!"
            )
        except Exception:
            pass
        await query.edit_message_reply_markup(reply_markup=None)
    elif action == "admin_reject":
        try:
            await context.bot.send_message(
                user_id, "❌ Comanda ta a fost marcată ca anulată de operator."
            )
        except Exception:
            pass
        await query.edit_message_reply_markup(reply_markup=None)


async def order_edit_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lang = get_lang(context)
    # păstrăm datele curente în user_data["order"], dar reluăm de la început
    await query.edit_message_text(tr(lang, "order_from_menu_intro"))
    await send_text(update, context, tr(lang, "order_ask_product"))
    return ORDER_PRODUCT


async def order_cancel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lang = get_lang(context)
    await query.edit_message_text(
        tr(lang, "order_cancelled"), reply_markup=get_menu_keyboard(lang)
    )
    return ConversationHandler.END


async def order_cancel_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_lang(context)
    await send_text(
        update, context, tr(lang, "order_cancelled"), reply_markup=get_menu_keyboard(lang)
    )
    return ConversationHandler.END


# ----------------- Contact operator -----------------


async def support_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_lang(context)
    await send_text(update, context, tr(lang, "support_intro"))
    return SUPPORT_MESSAGE


async def support_forward(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_lang(context)
    chat_id = SUPPORT_CHAT_ID or ADMIN_CHAT_ID
    if chat_id:
        user = update.effective_user
        text = update.message.text
        payload = (
            f"📩 Mesaj nou pentru operator de la @{user.username or 'fără_username'} (ID: {user.id}):\n\n{text}"
        )
        try:
            await context.bot.send_message(chat_id, payload)
        except Exception as e:
            logger.exception("Failed to forward support msg: %s", e)
    await send_text(update, context, tr(lang, "support_sent"), reply_markup=get_menu_keyboard(lang))
    return ConversationHandler.END


async def support_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_lang(context)
    await send_text(update, context, tr(lang, "back_to_menu"), reply_markup=get_menu_keyboard(lang))
    return ConversationHandler.END


# ----------------- Admin comenzi / rapoarte -----------------


async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if ADMIN_CHAT_ID and update.effective_user and update.effective_user.id == ADMIN_CHAT_ID:
        await update.message.reply_text(
            "👑 Panou admin simplu.\n\n"
            "• Primești comenzi direct în acest chat.\n"
            "• Poți folosi /raport_azi pentru un mic rezumat."
        )
    else:
        await update.message.reply_text("Această comandă este doar pentru admin.")


async def raport_azi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not ADMIN_CHAT_ID or update.effective_user.id != ADMIN_CHAT_ID:
        await update.message.reply_text("Această comandă este doar pentru admin.")
        return

    if not ORDERS:
        await update.message.reply_text("Nu există comenzi salvate în această sesiune.")
        return

    today = datetime.now(timezone.utc).date()
    todays = [o for o in ORDERS if o["timestamp"].date() == today]
    if not todays:
        await update.message.reply_text("Astăzi nu au fost comenzi (în această sesiune).")
        return

    total = sum(o["price"] for o in todays if isinstance(o["price"], (int, float)))
    count = len(todays)

    # top produse
    freq: Dict[str, int] = {}
    for o in todays:
        name = o["product_name"]
        freq[name] = freq.get(name, 0) + 1
    top = sorted(freq.items(), key=lambda x: x[1], reverse=True)[:3]
    top_str = "\n".join(f"• {name}: {cnt} comenzi" for name, cnt in top)

    text = (
        f"📊 Raport pentru azi ({today.isoformat()}):\n\n"
        f"🧾 Număr comenzi: {count}\n"
        f"💰 Total estimat: {total} MDL\n\n"
        f"🏆 Top produse:\n{top_str if top_str else '—'}"
    )
    await update.message.reply_text(text)


# ----------------- Main -----------------


def main():
    if not TELEGRAM_TOKEN:
        raise RuntimeError("TELEGRAM_TOKEN is missing")

    application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    # Conversație AI cadouri
    gift_conv = ConversationHandler(
        entry_points=[
            MessageHandler(
                filters.Regex("Consultant AI|Консультант AI"), gift_ai_start
            )
        ],
        states={
            GIFT_WHO: [MessageHandler(filters.TEXT & ~filters.COMMAND, gift_ai_who)],
            GIFT_OCCASION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, gift_ai_occasion)
            ],
            GIFT_AGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, gift_ai_age)],
            GIFT_RELATION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, gift_ai_relation)
            ],
            GIFT_BUDGET: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, gift_ai_budget)
            ],
            GIFT_INTERESTS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, gift_ai_interests)
            ],
        },
        fallbacks=[
            CommandHandler("cancel", gift_ai_cancel),
            MessageHandler(filters.Regex("⬅️ Înapoi la meniu|⬅️ Назад в меню"), back_to_menu),
        ],
        per_message=False,
    )

    # Conversație comandă
    order_conv = ConversationHandler(
        entry_points=[
            MessageHandler(
                filters.Regex("Plasează comandă|Оформить заказ"),
                order_from_menu_entry,
            ),
            CallbackQueryHandler(order_from_catalog_callback, pattern=r"^order:"),
        ],
        states={
            ORDER_PRODUCT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, order_set_product),
                CallbackQueryHandler(order_reuse_yes, pattern="^order_reuse_yes$"),
                CallbackQueryHandler(order_reuse_no, pattern="^order_reuse_no$"),
            ],
            ORDER_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, order_set_name)],
            ORDER_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, order_set_phone)],
            ORDER_CITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, order_set_city)],
            ORDER_DELIVERY: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, order_set_delivery)
            ],
            ORDER_ADDRESS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, order_set_address)
            ],
            ORDER_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, order_set_date)],
            ORDER_PAYMENT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, order_set_payment)
            ],
            ORDER_COMMENTS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, order_set_comments)
            ],
            ORDER_OCCASION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, order_set_occasion)
            ],
            ORDER_SOURCE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, order_set_source)
            ],
            ORDER_UPSELL: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, order_set_upsell)
            ],
            ORDER_CONFIRM: [
                CallbackQueryHandler(order_confirm_callback, pattern="^order_confirm$"),
                CallbackQueryHandler(order_edit_callback, pattern="^order_edit$"),
                CallbackQueryHandler(order_cancel_callback, pattern="^order_cancel$"),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", order_cancel_text),
            MessageHandler(filters.Regex("⬅️ Înapoi la meniu|⬅️ Назад в меню"), back_to_menu),
        ],
        per_message=False,
    )

    # Contact operator
    support_conv = ConversationHandler(
        entry_points=[
            MessageHandler(
                filters.Regex("Contact operator|оператор"), support_start
            )
        ],
        states={
            SUPPORT_MESSAGE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, support_forward)
            ],
        },
        fallbacks=[
            CommandHandler("cancel", support_cancel),
            MessageHandler(filters.Regex("⬅️ Înapoi la meniu|⬅️ Назад в меню"), back_to_menu),
        ],
        per_message=False,
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(set_language, pattern=r"^lang:"))
    application.add_handler(CallbackQueryHandler(show_catalog_from_callback, pattern=r"^menu:catalog$"))
    application.add_handler(CallbackQueryHandler(ai_message_callback, pattern=r"^ai:message$"))
    application.add_handler(CallbackQueryHandler(order_admin_decision, pattern=r"^admin_"))

    application.add_handler(
        MessageHandler(filters.Regex("Catalog cadouri|Каталог подарков"), show_catalog)
    )
    application.add_handler(
        MessageHandler(filters.Regex("Despre magazin / Contact|О магазине / Контакты"), info_handler)
    )
    application.add_handler(
        MessageHandler(filters.Regex("⬅️ Înapoi la meniu|⬅️ Назад в меню"), back_to_menu)
    )

    application.add_handler(CommandHandler("admin", admin_panel))
    application.add_handler(CommandHandler("raport_azi", raport_azi))

    application.add_handler(gift_conv)
    application.add_handler(order_conv)
    application.add_handler(support_conv)

    # HTTP server pentru Render
    threading.Thread(target=run_http_server, daemon=True).start()

    application.run_polling()


if __name__ == "__main__":
    main()
