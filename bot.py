import requests
import asyncio
import logging
from datetime import datetime
import html
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.enums import ParseMode
import asyncio

# ==================== CONFIGURATION ====================
TELEGRAM_BOT_TOKEN = "8025861936:AAGjidGhuNoB_Y5SrKUCenwWI3AlWaj_XPM"  # Replace with your bot token
HIRU_API_BASE = "https://hirunews.vercel.app/api"
CHECK_INTERVAL = 600  # Check for new news every 10 minutes (in seconds)

# Store sent news IDs to avoid duplicates
sent_news_ids = set()

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ==================== API FUNCTIONS ====================

def fetch_from_api(endpoint, params=None):
    """Generic function to fetch data from Hiru News API"""
    try:
        url = f"{HIRU_API_BASE}/{endpoint}"
        response = requests.get(url, params=params, timeout=15)
        response.raise_for_status()
        data = response.json()
        
        if data.get('success'):
            return data.get('data', [])
        else:
            logger.error(f"API error: {data.get('error')}")
            return None
            
    except requests.exceptions.Timeout:
        logger.error(f"Timeout fetching {endpoint}")
        return None
    except Exception as e:
        logger.error(f"Error fetching {endpoint}: {e}")
        return None

def get_latest_news(limit=5):
    """Get latest news articles"""
    return fetch_from_api("latest-news", {"limit": limit})

def get_breaking_news(limit=5):
    """Get breaking news"""
    return fetch_from_api("breaking-news", {"limit": limit})

def get_category_news(category, limit=10, details=True):
    """Get news by category"""
    params = {"limit": limit}
    if not details:
        params["details"] = "false"
    return fetch_from_api(f"category/{category}", params)

def search_news(query, limit=10):
    """Search for news"""
    return fetch_from_api("search", {"q": query, "limit": limit})

def format_news_message(article):
    """Format a single news article into a readable message"""
    headline = article.get('headline', 'No Title')
    summary = article.get('summary', '')
    url = article.get('url', '')
    published_date = article.get('publishedDate', '')
    category = article.get('category', 'General')
    word_count = article.get('wordCount', 0)
    
    # Truncate summary if too long
    if len(summary) > 500:
        summary = summary[:500] + "..."
    
    message = f"📰 *{html.escape(headline)}*\n\n"
    message += f"{html.escape(summary)}\n\n"
    message += f"📁 *Category:* {category}\n"
    message += f"📝 *Words:* {word_count}\n"
    
    if published_date:
        # Format date nicely
        try:
            date_obj = datetime.fromisoformat(published_date.replace('Z', '+00:00'))
            formatted_date = date_obj.strftime("%Y-%m-%d %I:%M %p")
            message += f"🕒 *Published:* {formatted_date}\n"
        except:
            message += f"🕒 *Published:* {published_date}\n"
    
    if url:
        message += f"\n🔗 [Read Full Article]({url})"
    
    return message

# ==================== BOT HANDLERS ====================

async def start_command(message: types.Message):
    """Handle /start command"""
    welcome_message = (
        "🇱🇰 *Welcome to Hiru News Bot!* 📰\n\n"
        "I deliver breaking news from Sri Lanka's #1 news source directly to you.\n\n"
        "*Available Commands:*\n"
        "/news - Get latest 5 news articles\n"
        "/breaking - Get breaking news\n"
        "/latest - Get the most recent news\n"
        "/category [name] - Get news by category\n"
        "/search [query] - Search for news\n"
        "/subscribe - Subscribe to automatic updates\n"
        "/unsubscribe - Unsubscribe from updates\n"
        "/help - Show this help message\n\n"
        "*Available Categories:*\n"
        "sports, business, entertainment, international, local, general\n\n"
        "🔔 *Note:* Add me to any group and I'll send news updates there too!"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📰 Latest News", callback_data="latest"),
            InlineKeyboardButton(text="⚡ Breaking News", callback_data="breaking")
        ],
        [
            InlineKeyboardButton(text="🏏 Sports", callback_data="cat_sports"),
            InlineKeyboardButton(text="💰 Business", callback_data="cat_business")
        ],
        [
            InlineKeyboardButton(text="🎬 Entertainment", callback_data="cat_entertainment"),
            InlineKeyboardButton(text="🌍 International", callback_data="cat_international")
        ],
        [
            InlineKeyboardButton(text="🔔 Subscribe", callback_data="subscribe"),
            InlineKeyboardButton(text="ℹ️ Help", callback_data="help")
        ]
    ])
    
    await message.answer(
        welcome_message,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=keyboard,
        disable_web_page_preview=True
    )

async def help_command(message: types.Message):
    """Handle /help command"""
    help_text = (
        "*📖 Hiru News Bot Help*\n\n"
        "*Commands:*\n"
        "/news - Get latest 5 news articles\n"
        "/breaking - Get breaking/ticker news\n"
        "/latest - Get the most recent single news\n"
        "/category [name] - Get news by category\n"
        "   Example: /category sports\n"
        "/search [query] - Search for news\n"
        "   Example: /search අනතුර\n"
        "/subscribe - Subscribe to automatic updates\n"
        "/unsubscribe - Unsubscribe from updates\n\n"
        "*Available Categories:*\n"
        "🏏 sports | 💰 business | 🎬 entertainment\n"
        "🌍 international | 🏠 local | 📰 general\n\n"
        "*Features:*\n"
        "• Automatic news delivery every 10 minutes\n"
        "• Full article text extraction\n"
        "• Image thumbnails with news\n"
        "• Real-time breaking news alerts\n\n"
        "*Source:* Hiru News (hirunews.lk)\n"
        "*API:* Hiru News API by @tharustack\n\n"
        "📌 *Tip:* Use inline buttons for quick access!"
    )
    
    await message.answer(help_text, parse_mode=ParseMode.MARKDOWN)

async def news_command(message: types.Message):
    """Handle /news command"""
    await message.answer("📡 Fetching latest news from Hiru...")
    
    news_data = get_latest_news(limit=5)
    if not news_data:
        await message.answer("❌ Failed to fetch news. Please try again later.")
        return
    
    for article in news_data:
        message_text = format_news_message(article)
        thumbnail = article.get('thumbnail')
        
        try:
            if thumbnail:
                await message.answer_photo(
                    photo=thumbnail,
                    caption=message_text,
                    parse_mode=ParseMode.MARKDOWN
                )
            else:
                await message.answer(
                    message_text,
                    parse_mode=ParseMode.MARKDOWN,
                    disable_web_page_preview=True
                )
            await asyncio.sleep(0.5)
        except Exception as e:
            logger.error(f"Error sending news: {e}")

async def breaking_command(message: types.Message):
    """Handle /breaking command"""
    await message.answer("⚡ Fetching breaking news...")
    
    news_data = get_breaking_news(limit=5)
    if not news_data:
        await message.answer("No breaking news at the moment.")
        return
    
    for article in news_data:
        message_text = format_news_message(article)
        thumbnail = article.get('thumbnail')
        
        try:
            if thumbnail:
                await message.answer_photo(
                    photo=thumbnail,
                    caption=message_text,
                    parse_mode=ParseMode.MARKDOWN
                )
            else:
                await message.answer(
                    message_text,
                    parse_mode=ParseMode.MARKDOWN,
                    disable_web_page_preview=True
                )
            await asyncio.sleep(0.5)
        except Exception as e:
            logger.error(f"Error sending breaking news: {e}")

async def latest_command(message: types.Message):
    """Handle /latest command"""
    news_data = get_latest_news(limit=1)
    if not news_data or len(news_data) == 0:
        await message.answer("❌ Failed to fetch latest news.")
        return
    
    article = news_data[0]
    message_text = format_news_message(article)
    thumbnail = article.get('thumbnail')
    
    try:
        if thumbnail:
            await message.answer_photo(
                photo=thumbnail,
                caption=message_text,
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            await message.answer(message_text, parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        logger.error(f"Error sending latest news: {e}")

async def category_command(message: types.Message):
    """Handle /category command"""
    args = message.text.split()
    
    if len(args) < 2:
        await message.answer(
            "Please specify a category.\n\n"
            "*Available categories:*\n"
            "sports, business, entertainment, international, local, general\n\n"
            "*Example:* `/category sports`",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    category = args[1].lower()
    valid_categories = ['sports', 'business', 'entertainment', 'international', 'local', 'general']
    
    if category not in valid_categories:
        await message.answer(
            f"❌ Invalid category: {category}\n\n"
            f"*Available categories:*\n{', '.join(valid_categories)}",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    await message.answer(f"📡 Fetching {category} news...")
    
    news_data = get_category_news(category, limit=5, details=True)
    if not news_data:
        await message.answer(f"No news found in {category} category.")
        return
    
    for article in news_data:
        message_text = format_news_message(article)
        thumbnail = article.get('thumbnail')
        
        try:
            if thumbnail:
                await message.answer_photo(
                    photo=thumbnail,
                    caption=message_text,
                    parse_mode=ParseMode.MARKDOWN
                )
            else:
                await message.answer(
                    message_text,
                    parse_mode=ParseMode.MARKDOWN,
                    disable_web_page_preview=True
                )
            await asyncio.sleep(0.5)
        except Exception as e:
            logger.error(f"Error sending category news: {e}")

async def search_command(message: types.Message):
    """Handle /search command"""
    args = message.text.split()
    
    if len(args) < 2:
        await message.answer(
            "Please specify a search query.\n\n"
            "*Example:* `/search අනතුර`",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    query = ' '.join(args[1:])
    await message.answer(f"🔍 Searching for: *{html.escape(query)}*", parse_mode=ParseMode.MARKDOWN)
    
    news_data = search_news(query, limit=5)
    if not news_data:
        await message.answer(f"No results found for '{html.escape(query)}'.")
        return
    
    results_message = f"*Search Results for '{html.escape(query)}':*\n\n"
    for i, article in enumerate(news_data[:5], 1):
        headline = article.get('headline', 'No Title')
        results_message += f"{i}. {headline[:100]}...\n"
    
    await message.answer(results_message, parse_mode=ParseMode.MARKDOWN)
    
    # Send first result with details
    if news_data:
        article = news_data[0]
        message_text = format_news_message(article)
        thumbnail = article.get('thumbnail')
        
        try:
            if thumbnail:
                await message.answer_photo(
                    photo=thumbnail,
                    caption=message_text,
                    parse_mode=ParseMode.MARKDOWN
                )
            else:
                await message.answer(message_text, parse_mode=ParseMode.MARKDOWN)
        except Exception as e:
            logger.error(f"Error sending search result: {e}")

# Global bot data
bot_data = {'subscribers': set()}

async def subscribe_command(message: types.Message):
    """Handle /subscribe command"""
    chat_id = message.chat.id
    
    if 'subscribers' not in bot_data:
        bot_data['subscribers'] = set()
    
    bot_data['subscribers'].add(chat_id)
    
    await message.answer(
        "✅ *Successfully subscribed!*\n\n"
        "You will now receive automatic Hiru News updates every 10 minutes.\n"
        "Use /unsubscribe to stop receiving updates.",
        parse_mode=ParseMode.MARKDOWN
    )

async def unsubscribe_command(message: types.Message):
    """Handle /unsubscribe command"""
    chat_id = message.chat.id
    
    if 'subscribers' in bot_data:
        bot_data['subscribers'].discard(chat_id)
    
    await message.answer(
        "🔕 *Unsubscribed*\n\n"
        "You will no longer receive automatic news updates.\n"
        "Use /subscribe to subscribe again.",
        parse_mode=ParseMode.MARKDOWN
    )

async def callback_handler(callback_query: types.CallbackQuery):
    """Handle callback queries from inline buttons"""
    await callback_query.answer()
    
    data = callback_query.data
    message = callback_query.message
    
    # Create a mock message object for the handlers
    class MockMessage:
        def __init__(self, original_message, text):
            self.chat = original_message.chat
            self.answer = original_message.answer
            self.answer_photo = original_message.answer_photo
            self.text = text
        
        async def answer(self, *args, **kwargs):
            await original_message.answer(*args, **kwargs)
        
        async def answer_photo(self, *args, **kwargs):
            await original_message.answer_photo(*args, **kwargs)
    
    if data == "latest":
        await latest_command(message)
    elif data == "breaking":
        await breaking_command(message)
    elif data == "cat_sports":
        mock_msg = MockMessage(message, "/category sports")
        await category_command(mock_msg)
    elif data == "cat_business":
        mock_msg = MockMessage(message, "/category business")
        await category_command(mock_msg)
    elif data == "cat_entertainment":
        mock_msg = MockMessage(message, "/category entertainment")
        await category_command(mock_msg)
    elif data == "cat_international":
        mock_msg = MockMessage(message, "/category international")
        await category_command(mock_msg)
    elif data == "subscribe":
        await subscribe_command(message)
    elif data == "help":
        await help_command(message)

# ==================== AUTO-NEWS CHECKER ====================

async def check_for_new_news(bot: Bot):
    """Background task to check for new news and send to subscribers"""
    global sent_news_ids
    
    logger.info("Checking for new Hiru News...")
    news_data = get_latest_news(limit=5)
    
    if not news_data:
        logger.warning("No news data received")
        return
    
    # Check for new news
    new_news = []
    for article in news_data:
        news_id = article.get('id')
        if news_id and news_id not in sent_news_ids:
            new_news.append(article)
            sent_news_ids.add(news_id)
    
    # Limit sent_news_ids size
    if len(sent_news_ids) > 500:
        sent_news_ids = set(list(sent_news_ids)[-250:])
    
    if not new_news:
        logger.info("No new news found")
        return
    
    logger.info(f"Found {len(new_news)} new news items")
    
    # Send to all subscribers
    if not bot_data.get('subscribers'):
        logger.info("No subscribers to notify")
        return
    
    for article in new_news:
        message_text = format_news_message(article)
        thumbnail = article.get('thumbnail')
        
        for chat_id in bot_data['subscribers']:
            try:
                if thumbnail:
                    await bot.send_photo(
                        chat_id=chat_id,
                        photo=thumbnail,
                        caption=message_text,
                        parse_mode=ParseMode.MARKDOWN
                    )
                else:
                    await bot.send_message(
                        chat_id=chat_id,
                        text=message_text,
                        parse_mode=ParseMode.MARKDOWN,
                        disable_web_page_preview=True
                    )
                await asyncio.sleep(0.5)
            except Exception as e:
                logger.error(f"Error sending to {chat_id}: {e}")

# ==================== MAIN APPLICATION ====================

async def main():
    """Start the bot"""
    # Initialize bot and dispatcher
    bot = Bot(token=TELEGRAM_BOT_TOKEN)
    dp = Dispatcher()
    
    # Register handlers
    dp.message.register(start_command, Command("start"))
    dp.message.register(help_command, Command("help"))
    dp.message.register(news_command, Command("news"))
    dp.message.register(breaking_command, Command("breaking"))
    dp.message.register(latest_command, Command("latest"))
    dp.message.register(category_command, Command("category"))
    dp.message.register(search_command, Command("search"))
    dp.message.register(subscribe_command, Command("subscribe"))
    dp.message.register(unsubscribe_command, Command("unsubscribe"))
    
    # Callback query handler
    dp.callback_query.register(callback_handler)
    
    # Start background task for checking news
    asyncio.create_task(background_news_checker(bot))
    
    logger.info("Starting Hiru News Bot with aiogram...")
    await dp.start_polling(bot)

async def background_news_checker(bot: Bot):
    """Background task that runs every CHECK_INTERVAL seconds"""
    while True:
        try:
            await check_for_new_news(bot)
        except Exception as e:
            logger.error(f"Error in background checker: {e}")
        await asyncio.sleep(CHECK_INTERVAL)

if __name__ == '__main__':
    asyncio.run(main())