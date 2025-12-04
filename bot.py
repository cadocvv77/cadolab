import os
import logging
import asyncio
from typing import Dict, Any

from dotenv import load_dotenv
from groq import Groq

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
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

if ADMIN_CHAT_ID:
    try:
        ADMIN_CHAT_ID = int(ADMIN_CHAT_ID)
    except ValueError:
        ADMIN_CHAT_ID = None
else:
    ADMIN_CHAT_ID = None

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
    GIFT_AGE,
    GIFT_RELATION,
    GIFT_BUDGET,
    GIFT_INTERESTS,
    ORDER_PRODUCT,
    ORDER_NAME,
    ORDER_PHONE,
    ORDER_CITY,
    ORDER_ADDRESS,
    ORDER_DATE,
    ORDER_PAYMENT,
    ORDER_COMMENTS,
    ORDER_CONFIRM,
) = range(14)

# --------- PRODUSE (editează-le cum vrei) ----------

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
    # adaugă aici restul boxelor tale...
]

# --------- Texte în RO / RU ----------

TEXTS: Dict[str, Dict[str, str]] = {
    LANG_RO: {
        "start_choose_lang": "Salut! 👋\nAlege limba în care vrei să vorbim:",
        "menu_title": "Alege ce vrei să facem azi:",
        "btn_catalog": "🛍 Catalog cadouri",
        "btn_ai": "🎁 Găsește cadoul perfect (AI)",
        "btn_order": "📦 Plasează comandă",
        "btn_info": "ℹ️ Despre magazin / Contact",
        "btn_back": "⬅️ Înapoi la meniu",
        "info": (
            "🎁 *Cadolab* — botul tău pentru alegerea rapidă a cadoului perfect.\n\n"
            "Lucrăm cu boxe de cadouri dulci pentru zile de naștere, Anul Nou, februarie și alte ocazii.\n\n"
            "📲 Contact: scrie-ne direct aici sau pe Instagram (@contul_tău)."
        ),
        "ai_intro": (
            "Ok, hai să găsim cadoul perfect! 🤖🎁\n\n"
            "Pentru cine este cadoul? (ex: iubită, iubit, prietenă, mamă...)"
        ),
        "ask_age": "Ce vârstă are aproximativ persoana?",
        "ask_relation": "Ce relație ai cu persoana? (ex: iubit/ă, coleg, rudă...)",
        "ask_budget": "Care este bugetul aproximativ? (ex: 500-700 MDL, max 1000 MDL)",
        "ask_interests": "Spune-mi câteva preferințe sau detalii (dulciuri preferate, stil, hobby-uri).",
        "ai_thinking": "Analizez informațiile și aleg cele mai potrivite boxe pentru tine... 🤔",
        "ai_error": "A apărut o problemă cu AI-ul. Încearcă din nou sau alege direct din catalog.",
        "ai_done": "Iată ce îți recomand:",
        "order_from_menu_intro": (
            "Perfect, hai să plasăm o comandă. 📦\n\n"
            "Mai întâi, alege cutia dorită din *Catalog cadouri* sau scrie numele cutiei:"
        ),
        "order_ask_name": "Cum te cheamă (nume și prenume)?",
        "order_ask_phone": "Numărul tău de telefon pentru livrare?",
        "order_ask_city": "În ce oraș se face livrarea?",
        "order_ask_address": "Adresa completă de livrare?",
        "order_ask_date": "Când dorești livrarea? (dată și interval orar)",
        "order_ask_payment": "Cum preferi să plătești? (cash, card, altceva)",
        "order_ask_comments": "Ai observații speciale? (ex: fără alune, mesaj pe cutie etc.) Dacă nu, scrie „nu”.",
        "order_summary_title": "Verifică dacă datele sunt corecte:",
        "order_confirm_btn": "✅ Confirmă comanda",
        "order_cancel_btn": "❌ Anulează",
        "order_confirmed_client": "✅ Comanda ta a fost transmisă! În scurt timp te vom contacta pentru confirmare finală.",
        "order_cancelled": "Comanda a fost anulată. Dacă vrei, o poți reface oricând.",
        "back_to_menu": "Te-am adus înapoi la meniu.",
    },
    LANG_RU: {
        "start_choose_lang": "Привет! 👋\nВыбери язык, на котором будем общаться:",
        "menu_title": "Выбери действие:",
        "btn_catalog": "🛍 Каталог подарков",
        "btn_ai": "🎁 Подбор идеального подарка (AI)",
        "btn_order": "📦 Оформить заказ",
        "btn_info": "ℹ️ О магазине / Контакты",
        "btn_back": "⬅️ Назад в меню",
        "info": (
            "🎁 *Cadolab* — твой бот для быстрого подбора идеального подарка.\n\n"
            "Работаем с подарочными сладкими боксами на дни рождения, Новый год, февраль и другие поводы.\n\n"
            "📲 Контакт: пиши нам прямо сюда или в Instagram (@твой_аккаунт)."
        ),
        "ai_intro": (
            "Давай подберём идеальный подарок! 🤖🎁\n\n"
            "Для кого этот подарок? (например: девушка, парень, подруга, мама...)"
        ),
        "ask_age": "Сколько человеку примерно лет?",
        "ask_relation": "Какие у вас отношения? (парень/девушка, коллега, родственник...)",
        "ask_budget": "Какой у тебя примерный бюджет? (например: 500–700 MDL, максимум 1000 MDL)",
        "ask_interests": "Напиши пару предпочтений или интересов (любимые сладости, стиль, хобби).",
        "ai_thinking": "Собираю информацию и подбираю самые подходящие боксы... 🤔",
        "ai_error": "Возникла ошибка при запросе к AI. Попробуй ещё раз или выбери коробку из каталога.",
        "ai_done": "Вот что я рекомендую:",
        "order_from_menu_intro": (
            "Отлично, давай оформим заказ. 📦\n\n"
            "Сначала выбери бокс в *Каталоге подарков* или напиши его название:"
        ),
        "order_ask_name": "Как тебя зовут? (имя и фамилия)",
        "order_ask_phone": "Твой номер телефона для доставки?",
        "order_ask_city": "В каком городе будет доставка?",
        "order_ask_address": "Полный адрес доставки?",
        "order_ask_date": "На какую дату и время нужна доставка?",
        "order_ask_payment": "Как удобнее оплатить? (наличные, карта и т.д.)",
        "order_ask_comments": "Есть ли особые пожелания? (например: без орехов, надпись на коробке). Если нет, напиши «нет».",
        "order_summary_title": "Проверь, всё ли верно:",
        "order_confirm_btn": "✅ Подтвердить заказ",
        "order_cancel_btn": "❌ Отменить",
        "order_confirmed_client": "✅ Твой заказ отправлен! Мы свяжемся с тобой для окончательного подтверждения.",
        "order_cancelled": "Заказ отменён. Можешь оформить новый в любое время.",
        "back_to_menu": "Возвращаю тебя в главное меню.",
    },
}


def get_lang(context: ContextTypes.DEFAULT_TYPE) -> str:
    return context.user_data.get("lang", LANG_RO)


def tr(lang: str, key: str) -> str:
    return TEXTS.get(lang, TEXTS[LANG_RO])[key]


def get_menu_keyboard(lang: str) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [
            [TEXTS[lang]["btn_catalog"]],
            [TEXTS[lang]["btn_ai"]],
            [TEXTS[lang]["btn_order"]],
            [TEXTS[lang]["btn_info"]],
        ],
        resize_keyboard=True,
    )

# helper: șterge ultimul mesaj al botului înainte să trimită altul
async def send_clean_text(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    text: str,
    reply_markup=None,
):
    chat = update.effective_chat
    if not chat:
        return None
    last_id = context.user_data.get("last_bot_message_id")
    if last_id:
        try:
            await context.bot.delete_message(chat.id, last_id)
        except Exception:
            pass
    msg = await chat.send_message(text, reply_markup=reply_markup)
    context.user_data["last_bot_message_id"] = msg.message_id
    return msg

# ----------------- Handlers -----------------


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
    await send_clean_text(
        update,
        context,
        TEXTS[LANG_RO]["start_choose_lang"],
        reply_markup=keyboard,
    )


async def set_language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lang_code = query.data.split(":")[1]
    context.user_data["lang"] = LANG_RO if lang_code == "ro" else LANG_RU
    lang = get_lang(context)
    await send_clean_text(
        update, context, tr(lang, "menu_title"), reply_markup=get_menu_keyboard(lang)
    )


async def back_to_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_lang(context)
    await send_clean_text(
        update, context, tr(lang, "back_to_menu"), reply_markup=get_menu_keyboard(lang)
    )
    return ConversationHandler.END


async def info_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_lang(context)
    text = tr(lang, "info")
    await send_clean_text(update, context, text, reply_markup=get_menu_keyboard(lang))


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
    await send_clean_text(update, context, text, reply_markup=keyboard)

async def show_catalog_from_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await show_catalog(update, context)

# -------- AI gift assistant --------


async def gift_ai_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_lang(context)
    context.user_data["gift_ai"] = {}
    await send_clean_text(update, context, tr(lang, "ai_intro"))
    return GIFT_WHO


async def gift_ai_who(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_lang(context)
    context.user_data["gift_ai"]["who"] = update.message.text.strip()
    await send_clean_text(update, context, tr(lang, "ask_age"))
    return GIFT_AGE


async def gift_ai_age(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_lang(context)
    context.user_data["gift_ai"]["age"] = update.message.text.strip()
    await send_clean_text(update, context, tr(lang, "ask_relation"))
    return GIFT_RELATION


async def gift_ai_relation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_lang(context)
    context.user_data["gift_ai"]["relation"] = update.message.text.strip()
    await send_clean_text(update, context, tr(lang, "ask_budget"))
    return GIFT_BUDGET


async def gift_ai_budget(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_lang(context)
    context.user_data["gift_ai"]["budget"] = update.message.text.strip()
    await send_clean_text(update, context, tr(lang, "ask_interests"))
    return GIFT_INTERESTS


async def gift_ai_interests(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_lang(context)
    context.user_data["gift_ai"]["interests"] = update.message.text.strip()
    await send_clean_text(update, context, tr(lang, "ai_thinking"))
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
            "Ai o listă de produse (boxe de cadouri). În funcție de info despre persoană, "
            "vârstă, relație, buget și preferințe, alege 1-2 boxe din listă și explică foarte pe scurt "
            "de ce le recomanzi. Răspunsul să fie clar, prietenos și concret. Nu inventa produse noi."
        )
    else:
        system_prompt = (
            "Ты консультант по подаркам в магазине сладких подарочных боксов. "
            "У тебя есть список боксов. В зависимости от человека, возраста, отношений, бюджета и предпочтений "
            "подбери 1–2 бокса из списка и очень кратко объясни, почему именно они. "
            "Не придумывай новых товаров."
        )

    user_prompt = (
        f"Date client:\n"
        f"- Pentru cine: {data['who']}\n"
        f"- Vârsta: {data['age']}\n"
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
            max_tokens=600,
        )
        ai_text = response.choices[0].message.content.strip()
    except Exception as e:
        logger.exception("Groq error: %s", e)
        await send_clean_text(update, context, tr(lang, "ai_error"))
        return ConversationHandler.END

    lang = get_lang(context)
    final_text = f"{tr(lang, 'ai_done')}\n\n{ai_text}"
    keyboard = InlineKeyboardMarkup(
        [[InlineKeyboardButton(tr(lang, "btn_catalog"), callback_data="menu:catalog")]]
    )
    await send_clean_text(update, context, final_text, reply_markup=keyboard)
    return ConversationHandler.END


async def gift_ai_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_lang(context)
    await send_clean_text(
        update, context, tr(lang, "back_to_menu"), reply_markup=get_menu_keyboard(lang)
    )
    return ConversationHandler.END


# ------------- Order flow -------------


def _find_product_by_id(product_id: str) -> Dict[str, Any] | None:
    for p in PRODUCTS:
        if p["id"] == product_id:
            return p
    return None


async def order_from_menu_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_lang(context)
    context.user_data["order"] = {"product_id": None}
    await send_clean_text(update, context, tr(lang, "order_from_menu_intro"))
    return ORDER_PRODUCT


async def order_set_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_lang(context)
    text = update.message.text.strip()

    chosen = None
    for p in PRODUCTS:
        if p["name_ro"].lower() in text.lower() or p["name_ru"].lower() in text.lower():
            chosen = p
            break

    context.user_data["order"]["product_id"] = chosen["id"] if chosen else None
    context.user_data["order"]["product_custom"] = text if not chosen else None

    await send_clean_text(update, context, tr(lang, "order_ask_name"))
    return ORDER_NAME


async def order_from_catalog_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lang = get_lang(context)
    product_id = query.data.split(":", maxsplit=1)[1]
    context.user_data["order"] = {"product_id": product_id, "product_custom": None}
    await send_clean_text(update, context, tr(lang, "order_ask_name"))
    return ORDER_NAME


async def order_set_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_lang(context)
    context.user_data["order"]["name"] = update.message.text.strip()
    await send_clean_text(update, context, tr(lang, "order_ask_phone"))
    return ORDER_PHONE


async def order_set_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_lang(context)
    context.user_data["order"]["phone"] = update.message.text.strip()
    await send_clean_text(update, context, tr(lang, "order_ask_city"))
    return ORDER_CITY


async def order_set_city(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_lang(context)
    context.user_data["order"]["city"] = update.message.text.strip()
    await send_clean_text(update, context, tr(lang, "order_ask_address"))
    return ORDER_ADDRESS


async def order_set_address(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_lang(context)
    context.user_data["order"]["address"] = update.message.text.strip()
    await send_clean_text(update, context, tr(lang, "order_ask_date"))
    return ORDER_DATE


async def order_set_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_lang(context)
    context.user_data["order"]["date"] = update.message.text.strip()
    await send_clean_text(update, context, tr(lang, "order_ask_payment"))
    return ORDER_PAYMENT


async def order_set_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_lang(context)
    context.user_data["order"]["payment"] = update.message.text.strip()
    await send_clean_text(update, context, tr(lang, "order_ask_comments"))
    return ORDER_COMMENTS


async def order_set_comments(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_lang(context)
    context.user_data["order"]["comments"] = update.message.text.strip()

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
        f"📍 Adresă: {data.get('address')}",
        f"📅 Livrare: {data.get('date')}",
        f"💳 Plată: {data.get('payment')}",
        f"✏️ Observații: {data.get('comments')}",
    ]
    text = "\n".join(summary_lines)

    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(tr(lang, "order_confirm_btn"), callback_data="order_confirm"),
                InlineKeyboardButton(tr(lang, "order_cancel_btn"), callback_data="order_cancel"),
            ]
        ]
    )
    await send_clean_text(update, context, text, reply_markup=keyboard)
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
    order_text = (
        "📥 Comandă nouă (Telegram bot)\n\n"
        f"🎁 Box: {name} ({price} MDL)\n"
        f"👤 Nume: {data.get('name')}\n"
        f"📞 Telefon: {data.get('phone')}\n"
        f"🏙️ Oraș: {data.get('city')}\n"
        f"📍 Adresă: {data.get('address')}\n"
        f"📅 Livrare: {data.get('date')}\n"
        f"💳 Plată: {data.get('payment')}\n"
        f"✏️ Observații: {data.get('comments')}\n\n"
        f"👤 Client Telegram: @{client.username or 'fără_username'} (ID: {client.id})"
    )

    if ADMIN_CHAT_ID:
        try:
            await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=order_text)
        except Exception as e:
            logger.exception("Failed to send order to admin: %s", e)

    await send_clean_text(
        update,
        context,
        tr(lang, "order_confirmed_client"),
        reply_markup=get_menu_keyboard(lang),
    )
    return ConversationHandler.END


async def order_cancel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lang = get_lang(context)
    await send_clean_text(
        update,
        context,
        tr(lang, "order_cancelled"),
        reply_markup=get_menu_keyboard(lang),
    )
    return ConversationHandler.END


async def order_cancel_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_lang(context)
    await send_clean_text(
        update,
        context,
        tr(lang, "order_cancelled"),
        reply_markup=get_menu_keyboard(lang),
    )
    return ConversationHandler.END


# ------------- Admin basic panel -------------


async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if ADMIN_CHAT_ID and update.effective_user and update.effective_user.id == ADMIN_CHAT_ID:
        await update.message.reply_text(
            "👑 Panou admin simplu.\n\n"
            "Deocamdată: primești comenzi direct aici.\n"
            "Într-un update viitor putem adăuga statistici și export în Google Sheets. 🙂"
        )
    else:
        await update.message.reply_text("Această comandă este doar pentru admin.")


# ------------- Main -------------


def main():
    if not TELEGRAM_TOKEN:
        raise RuntimeError("TELEGRAM_TOKEN is missing")

    application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    gift_conv = ConversationHandler(
        entry_points=[
            MessageHandler(
                filters.Regex("Găsește cadoul perfect|Подбор идеального подарка"),
                gift_ai_start,
            )
        ],
        states={
            GIFT_WHO: [MessageHandler(filters.TEXT & ~filters.COMMAND, gift_ai_who)],
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
            MessageHandler(
                filters.Regex("⬅️ Înapoi la meniu|⬅️ Назад в меню"), back_to_menu
            ),
        ],
        per_message=False,
    )

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
                MessageHandler(filters.TEXT & ~filters.COMMAND, order_set_product)
            ],
            ORDER_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, order_set_name)
            ],
            ORDER_PHONE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, order_set_phone)
            ],
            ORDER_CITY: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, order_set_city)
            ],
            ORDER_ADDRESS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, order_set_address)
            ],
            ORDER_DATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, order_set_date)
            ],
            ORDER_PAYMENT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, order_set_payment)
            ],
            ORDER_COMMENTS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, order_set_comments)
            ],
            ORDER_CONFIRM: [
                CallbackQueryHandler(order_confirm_callback, pattern="^order_confirm$"),
                CallbackQueryHandler(order_cancel_callback, pattern="^order_cancel$"),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", order_cancel_text),
            MessageHandler(
                filters.Regex("⬅️ Înapoi la meniu|⬅️ Назад в меню"), back_to_menu
            ),
        ],
        per_message=False,
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(set_language, pattern=r"^lang:"))
    application.add_handler(CallbackQueryHandler(show_catalog_from_callback, pattern=r"^menu:catalog$"))
    application.add_handler(
        MessageHandler(
            filters.Regex("Catalog cadouri|Каталог подарков"), show_catalog
        )
    )
    application.add_handler(
        MessageHandler(filters.Regex("Despre magazin|О магазине"), info_handler)
    )
    application.add_handler(
        MessageHandler(
            filters.Regex("Înapoi la meniu|Назад в меню"), back_to_menu
        )
    )
    application.add_handler(CommandHandler("admin", admin_panel))
    application.add_handler(gift_conv)
    application.add_handler(order_conv)

    application.run_polling()


if __name__ == "__main__":
    main()
