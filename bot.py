import os
import tempfile
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext, CallbackQueryHandler
from PyPDF2 import PdfFileWriter, PdfFileReader
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
import io

# Get token from environment variable
TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
if not TOKEN:
    raise ValueError("No token found! Set TELEGRAM_BOT_TOKEN environment variable")

# Global variable to store user states
user_states = {}

def start(update: Update, context: CallbackContext) -> None:
    """Send a message when the command /start is issued."""
    keyboard = [
        [InlineKeyboardButton("Text Watermark", callback_data='text')],
        [InlineKeyboardButton("Logo Watermark", callback_data='logo')],
        [InlineKeyboardButton("Clickable Link", callback_data='link')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text(
        'Welcome to PDF Watermarking Bot! 🎉\n\n'
        'Please choose what type of watermark you want to add:',
        reply_markup=reply_markup
    )

def button(update: Update, context: CallbackContext) -> None:
    """Handle button presses."""
    query = update.callback_query
    query.answer()
    
    user_id = query.from_user.id
    choice = query.data
    
    user_states[user_id] = {'type': choice}
    
    if choice == 'text':
        query.edit_message_text("Please send the text you want to use as watermark.")
    elif choice == 'logo':
        query.edit_message_text("Please send the image you want to use as a logo watermark.")
    elif choice == 'link':
        query.edit_message_text("Please send the URL you want to make clickable in the PDF.")

def handle_text(update: Update, context: CallbackContext) -> None:
    """Handle text messages."""
    user_id = update.message.from_user.id
    
    if user_id not in user_states:
        update.message.reply_text("Please start over with /start command.")
        return
        
    state = user_states[user_id]
    
    if state['type'] == 'text':
        state['text'] = update.message.text
        update.message.reply_text("Great! Now send me the PDF file you want to watermark.")
    elif state['type'] == 'link':
        state['url'] = update.message.text
        update.message.reply_text("Great! Now send me the PDF file you want to add the clickable link to.")

def create_watermark(text=None, url=None):
    """Create a watermark PDF."""
    packet = io.BytesIO()
    can = canvas.Canvas(packet, pagesize=letter)
    
    if text:
        can.setFont("Helvetica", 60)
        can.setFillGray(0.5, 0.5)  # Set transparency
        can.rotate(45)
        can.drawString(180, 0, text)
    
    if url:
        can.setFont("Helvetica", 12)
        can.linkURL(url, (100, 100, 500, 120), relative=1)
        can.drawString(100, 100, f"Click here: {url}")
    
    can.save()
    packet.seek(0)
    return packet

def handle_document(update: Update, context: CallbackContext) -> None:
    """Handle PDF documents."""
    user_id = update.message.from_user.id
    
    if user_id not in user_states:
        update.message.reply_text("Please start over with /start command.")
        return
        
    state = user_states[user_id]
    
    if update.message.document.mime_type != 'application/pdf':
        update.message.reply_text("Please send a PDF file.")
        return

    # Download the file
    file = context.bot.get_file(update.message.document.file_id)
    
    with tempfile.NamedTemporaryFile(delete=False) as temp_input:
        file.download(custom_path=temp_input.name)
        
        # Create watermark based on type
        if state['type'] == 'text':
            watermark_packet = create_watermark(text=state['text'])
        elif state['type'] == 'link':
            watermark_packet = create_watermark(url=state['url'])
        
        # Apply watermark
        watermark = PdfFileReader(watermark_packet)
        original = PdfFileReader(temp_input.name)
        output = PdfFileWriter()
        
        for i in range(original.getNumPages()):
            page = original.getPage(i)
            page.mergePage(watermark.getPage(0))
            output.addPage(page)
        
        # Save the watermarked file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_output:
            output.write(temp_output)
            
            # Send the watermarked PDF back to user
            context.bot.send_document(
                chat_id=update.message.chat_id,
                document=open(temp_output.name, 'rb'),
                filename='watermarked.pdf'
            )
            
        # Cleanup
        os.unlink(temp_input.name)
        os.unlink(temp_output.name)
    
    # Clear user state
    del user_states[user_id]

def main() -> None:
    """Start the bot."""
    updater = Updater(TOKEN)

    dispatcher = updater.dispatcher

    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CallbackQueryHandler(button))
    dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_text))
    dispatcher.add_handler(MessageHandler(Filters.document, handle_document))

    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()