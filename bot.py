import os
import logging
import json
import asyncio

from dotenv import load_dotenv
from groq import Groq
from telegram import (
    Update,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    filters,
)

# ---------------- CONFIG ----------------

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID")  # il vei pune in .env

if ADMIN_CHAT_ID:
    ADMIN_CHAT_ID = int(ADMIN_CHAT_ID)
else:
    ADMIN_CHAT_ID = None

client = Groq(api_key=GROQ_API_KEY)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ---------------- PRODUSE ----------------

PRODUCTS = [
    {
        "id": "BOX_LOVE",
        "name": "Love Box",
        "price": 650,
        "description": "Cutie romantică cu ciocolată premium, bomboane, ceai și lumânare parfumată.",
        "best_for": "cuplu, Valentine's, aniversări",
    },
    {
        "id": "BOX_PARTY",
        "name": "Party Box",
        "price": 550,
        "description": "Mix dulce + snack-uri sărate, perfect pentru prieteni și colegi.",
        "best_for": "prieteni, colegi, zi de naștere",
    },
    {
        "id": "BOX_DELUXE",
        "name": "Deluxe Sweet Box",
        "price": 950,
        "description": "Cutie mare cu dulciuri premium, ciocolată, biscuiți și băutură fără alcool.",
        "best_for": "cadou impresionant, familie, șefi",
    },
]

def get_product_by_id(pid: str):
    for p in PRODUCTS:
        if p["id"] == pid:
            return p
    return None

def products_as_text():
    lines = []
    for p in PRODUCTS:
        lines.append(
            f"{p['id']}: {p['name']} – {p['price']} MDL\n{p['description']}\nIdeal pentru: {p['best_for']}\n"
        )
    return "\n".join(lines)

# ---------------- MESAJE + BUTOANE ----------------

MAIN_KEYBOARD = ReplyKeyboardMarkup(
    [
        ["🛍 Catalog cadouri"],
        ["🎁 Găsește cadoul perfect (AI)"],
        ["📦 Plasează comandă"],
    ],
    resize_keyboard=True,
)

# State-uri pentru AI Gift Finder
(
    GIFT_WHO,
    GIFT_AGE,
    GIFT_RELATION,
    GIFT_BUDGET,
    GIFT_PREFS,
    GIFT_OCCASION,
) = range(6)

# State pentru detalii comandă
ORDER_DETAILS = 10

# ---------------- HANDLERS DE BAZĂ ----------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    print("User ID:", user.id)   # <- linie nouă
    text = (
        f"Salut, {user.first_name or 'dragă client'}! 👋\n\n"
        "Eu sunt botul magazinului tău de cadouri 🎁\n\n"
        "Cu mine poți:\n"
        "• vedea lista de cutii cadou disponibile\n"
        "• găsi cu ajutorul AI cadoul perfect\n"
        "• plasa comanda direct în chat\n\n"
        "Alege o opțiune din meniu:"
    )
    await update.message.reply_text(text, reply_markup=MAIN_KEYBOARD)

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Folosește butoanele de jos:\n"
        "🛍 Catalog cadouri – vezi toate boxele\n"
        "🎁 Găsește cadoul perfect (AI) – te ajut să alegi\n"
        "📦 Plasează comandă – dacă știi deja ce vrei",
        reply_markup=MAIN_KEYBOARD,
    )

# ---------------- CATALOG ----------------

async def show_catalog(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = "📦 *Catalog cadouri:*\n\n" + products_as_text()
    keyboard = [
        [
            InlineKeyboardButton(
                f"Comandă {p['name']} ({p['price']} MDL)", callback_data=f"order_{p['id']}"
            )
        ]
        for p in PRODUCTS
    ]
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

# ---------------- AI GIFT FINDER (GROQ) ----------------

async def gift_ai_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["gift"] = {}
    await update.message.reply_text(
        "Super! Începem să găsim cadoul perfect 🎁\n\n"
        "Pentru cine este cadoul? (ex: iubit, iubită, prieten, copil, părinte)"
    )
    return GIFT_WHO

async def gift_who(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["gift"]["who"] = update.message.text
    await update.message.reply_text("Ce vârstă are aproximativ? (ex: 18, 25-30, 40+)")
    return GIFT_AGE

async def gift_age(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["gift"]["age"] = update.message.text
    await update.message.reply_text("Ce relație ai cu el/ea? (ex: iubit(ă), prieten(ă), coleg, rudă)")
    return GIFT_RELATION

async def gift_relation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["gift"]["relation"] = update.message.text
    await update.message.reply_text("Care este bugetul aproximativ în MDL? (ex: 400-600)")
    return GIFT_BUDGET

async def gift_budget(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["gift"]["budget"] = update.message.text
    await update.message.reply_text(
        "Ce preferă mai mult? (ex: foarte dulce, minimalist, romantic, funny, elegant, etc.)"
    )
    return GIFT_PREFS

async def gift_prefs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["gift"]["prefs"] = update.message.text
    await update.message.reply_text(
        "Pentru ce ocazie este? (ex: zi de naștere, Anul Nou, februarie/Valentine's, altceva)"
    )
    return GIFT_OCCASION

def build_groq_prompt(gift_answers: dict) -> (list, str):
    prods_text = products_as_text()

    system_prompt = f"""
Ești consultant de cadouri pentru un magazin online din Moldova.
Ai următoarea listă de cutii cadou (produse):

{prods_text}

Fiecare produs are un câmp "id". Alege întotdeauna DOAR dintre aceste produse.
Răspunzi STRICT în format JSON, fără alt text în plus, cu structură:

{{
  "recommended_ids": ["ID1", "ID2"],
  "reasoning": "Explicație în limba română, 2-4 fraze.",
  "upsell_text": "Fraza scurtă de încheiere sau upsell."
}}

Dacă ți se pare că bugetul este prea mic, alege totuși cea mai apropiată opțiune și explică de ce.
"""

    user_prompt = (
        "Datele clientului despre persoana pentru care se caută cadoul:\n"
        f"- Pentru cine: {gift_answers.get('who')}\n"
        f"- Vârsta: {gift_answers.get('age')}\n"
        f"- Relația: {gift_answers.get('relation')}\n"
        f"- Buget: {gift_answers.get('budget')} MDL\n"
        f"- Preferințe: {gift_answers.get('prefs')}\n"
        f"- Ocazie: {gift_answers.get('occasion')}\n\n"
        "Alege 1-2 produse potrivite și răspunde în formatul JSON cerut."
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    return messages, user_prompt

def call_groq_sync(gift_answers: dict) -> str:
    messages, _ = build_groq_prompt(gift_answers)

    chat_completion = client.chat.completions.create(
        messages=messages,
        model="llama-3.3-70b-versatile",
        temperature=0.7,
    )

    content = chat_completion.choices[0].message.content

    # Incercam sa parsam JSON
    try:
        data = json.loads(content)
    except Exception:
        # Daca modelul nu a raspuns strict JSON, intoarcem textul brut
        return "Răspuns AI:\n\n" + content

    rec_ids = data.get("recommended_ids", [])
    reasoning = data.get("reasoning", "")
    upsell = data.get("upsell_text", "")

    lines = ["🎯 Recomandarea mea pentru tine:\n"]
    for pid in rec_ids:
        p = get_product_by_id(pid)
        if p:
            lines.append(
                f"✅ *{p['name']}* – *{p['price']} MDL*\n{p['description']}\n"
            )

    if reasoning:
        lines.append(f"🧠 De ce: {reasoning}")
    if upsell:
        lines.append(f"\nℹ️ {upsell}")

    # Daca avem macar un produs, atasam si butoane de comanda
    return "\n".join(lines)

async def gift_occasion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["gift"]["occasion"] = update.message.text
    gift_data = context.user_data.get("gift", {})

    await update.message.reply_text("Analizez opțiunile pentru tine... 🤖🎁")

    loop = asyncio.get_running_loop()
    result_text = await loop.run_in_executor(None, call_groq_sync, gift_data)

    # Trimitem rezultatul + butoane de comanda pentru toate boxele (clientul alege)
    keyboard = [
        [
            InlineKeyboardButton(
                f"Comandă {p['name']} ({p['price']} MDL)", callback_data=f"order_{p['id']}"
            )
        ]
        for p in PRODUCTS
    ]

    await update.message.reply_text(
        result_text + "\n\nDacă îți place o boxă, apasă pe butonul de mai jos pentru comandă 👇",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )

    context.user_data["gift"] = {}
    return ConversationHandler.END

async def gift_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["gift"] = {}
    await update.message.reply_text(
        "Am oprit consultarea. Poți reîncepe oricând din meniu.", reply_markup=MAIN_KEYBOARD
    )
    return ConversationHandler.END

# ---------------- COMANDA ----------------

async def start_order_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    product_id = query.data.replace("order_", "")
    product = get_product_by_id(product_id)
    if not product:
        await query.edit_message_text("Produsul nu a fost găsit. Te rog încearcă din nou.")
        return ConversationHandler.END

    context.user_data["order_product"] = product

    text = (
        f"📦 Vrei să comanzi *{product['name']}* – *{product['price']} MDL*.\n\n"
        "Te rog trimite într-un singur mesaj următoarele:\n"
        "• Nume și prenume\n"
        "• Telefon\n"
        "• Oraș / adresă de livrare\n"
        "• Data și interval orar preferat\n"
        "• Alte detalii (dacă sunt)\n\n"
        "Exemplu:\n"
        "Ion Popescu, 069000000, Chișinău, str. X..., mâine după 18:00, fără alune."
    )

    await query.edit_message_text(text, parse_mode="Markdown")
    return ORDER_DETAILS

async def order_details(update: Update, context: ContextTypes.DEFAULT_TYPE):
    details = update.message.text
    product = context.user_data.get("order_product")

    if not product:
        await update.message.reply_text(
            "Nu găsesc produsul selectat. Te rog revino în Catalog.", reply_markup=MAIN_KEYBOARD
        )
        return ConversationHandler.END

    order_text = (
        "📥 *Comandă nouă!*\n\n"
        f"Produs: *{product['name']}* – *{product['price']} MDL*\n"
        f"Detalii client:\n{details}\n\n"
        f"Username client: @{update.effective_user.username}\n"
        f"ID Telegram: {update.effective_user.id}"
    )

    # Trimitem adminului
    if ADMIN_CHAT_ID:
        await context.bot.send_message(
            chat_id=ADMIN_CHAT_ID, text=order_text
        )

    # Confirmare pentru client
    await update.message.reply_text(
        "✅ Comanda ta a fost transmisă!\n\n" + order_text,
        reply_markup=MAIN_KEYBOARD,
    )

    context.user_data["order_product"] = None
    return ConversationHandler.END

async def order_from_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Clientul apasă „Plasează comandă” din meniu fără să fi ales înainte
    text = (
        "Pentru a plasa o comandă, intră întâi la 🛍 *Catalog cadouri* sau folosește "
        "🎁 *Găsește cadoul perfect (AI)* și apoi apasă pe butonul „Comandă”."
    )
    await update.message.reply_text(text, reply_markup=MAIN_KEYBOARD)

async def cancel_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["order_product"] = None
    await update.message.reply_text(
        "Am anulat comanda. Poți reîncepe oricând din meniu.", reply_markup=MAIN_KEYBOARD
    )
    return ConversationHandler.END

# ---------------- MAIN ----------------

def main():
    if not TELEGRAM_TOKEN:
        raise RuntimeError("TELEGRAM_TOKEN nu este setat!")

    application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    # Conversatie AI Gift Finder
    gift_conv = ConversationHandler(
        entry_points=[
            MessageHandler(
                filters.Regex("^🎁 Găsește cadoul perfect \\(AI\\)$"), gift_ai_start
            )
        ],
        states={
            GIFT_WHO: [MessageHandler(filters.TEXT & ~filters.COMMAND, gift_who)],
            GIFT_AGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, gift_age)],
            GIFT_RELATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, gift_relation)],
            GIFT_BUDGET: [MessageHandler(filters.TEXT & ~filters.COMMAND, gift_budget)],
            GIFT_PREFS: [MessageHandler(filters.TEXT & ~filters.COMMAND, gift_prefs)],
            GIFT_OCCASION: [MessageHandler(filters.TEXT & ~filters.COMMAND, gift_occasion)],
        },
        fallbacks=[CommandHandler("cancel", gift_cancel)],
    )

    # Conversatie comanda (pornita din buton inline)
    order_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(start_order_callback, pattern="^order_")],
        states={
            ORDER_DETAILS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, order_details)
            ]
        },
        fallbacks=[CommandHandler("cancel", cancel_order)],
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_cmd))

    application.add_handler(gift_conv)
    application.add_handler(order_conv)

    # Meniu: Catalog + Plaseaza comanda
    application.add_handler(
        MessageHandler(filters.Regex("^🛍 Catalog cadouri$"), show_catalog)
    )
    application.add_handler(
        MessageHandler(filters.Regex("^📦 Plasează comandă$"), order_from_menu)
    )

    # Pornim botul
    application.run_polling()

if __name__ == "__main__":
    main()
