import requests
import asyncio
import logging
from datetime import datetime
import html
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.enums import ParseMode
import json
import os

# ==================== CONFIGURATION ====================
TELEGRAM_BOT_TOKEN = "8025861936:AAGjidGhuNoB_Y5SrKUCenwWI3AlWaj_XPM"  # Replace with your bot token
ESANA_API_URL = "https://esena-news-api-v3.vercel.app/"
CHECK_INTERVAL = 300  # Check every 5 minutes (recommended by API)
CACHE_FILE = "sent_news_cache.json"

# Store sent news IDs to avoid duplicates
sent_news_ids = set()

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ==================== CACHE FUNCTIONS ====================

def load_cache():
    """Load sent news IDs from cache file"""
    global sent_news_ids
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, 'r') as f:
                data = json.load(f)
                sent_news_ids = set(data.get('sent_ids', []))
                logger.info(f"Loaded {len(sent_news_ids)} cached news IDs")
        except Exception as e:
            logger.error(f"Error loading cache: {e}")

def save_cache():
    """Save sent news IDs to cache file"""
    try:
        with open(CACHE_FILE, 'w') as f:
            json.dump({'sent_ids': list(sent_news_ids)}, f)
    except Exception as e:
        logger.error(f"Error saving cache: {e}")

# ==================== API FUNCTIONS ====================

def fetch_esana_news():
    """Fetch latest news from Esana API"""
    try:
        response = requests.get(ESANA_API_URL, timeout=15)
        response.raise_for_status()
        data = response.json()
        
        # Navigate to the news data array
        news_data = data.get('news_data', {})
        articles = news_data.get('data', [])
        
        if articles:
            logger.info(f"Fetched {len(articles)} articles")
            return articles
        else:
            logger.warning("No articles found in response")
            return None
            
    except requests.exceptions.Timeout:
        logger.error("Timeout fetching Esana news")
        return None
    except requests.exceptions.ConnectionError:
        logger.error("Connection error - API may be down")
        return None
    except Exception as e:
        logger.error(f"Error fetching Esana news: {e}")
        return None

def format_news_message(article):
    """Format a single news article into a readable message"""
    # Get title (prefer Sinhala, fallback to English)
    title_si = article.get('titleSi', '')
    title_en = article.get('titleEn', '')
    title = title_si if title_si else title_en
    
    # Extract content text from contentSi or contentEn
    content_text = ""
    
    # Try contentSi first (Sinhala)
    content_si = article.get('contentSi', [])
    for item in content_si:
        if item.get('type') == 'text':
            content_text += item.get('data', '') + "\n"
    
    # If no Sinhala content, try English
    if not content_text:
        content_en = article.get('contentEn', [])
        for item in content_en:
            if item.get('type') == 'text':
                content_text += item.get('data', '') + "\n"
    
    # Clean and truncate content
    content_text = content_text.strip()
    if len(content_text) > 500:
        content_text = content_text[:500] + "..."
    
    # Get other fields
    thumb = article.get('thumb', '')
    published = article.get('published', '')
    share_url = article.get('share_url', '')
    reactions = article.get('reactions', {})
    comments = article.get('comments', 0)
    
    # Build message
    message = f"📰 *{html.escape(title)}*\n\n"
    
    if content_text:
        message += f"{html.escape(content_text)}\n\n"
    
    # Add metadata
    if published:
        try:
            date_obj = datetime.strptime(published, "%Y-%m-%d %H:%M:%S")
            formatted_date = date_obj.strftime("%Y-%m-%d %I:%M %p")
            message += f"🕒 *Published:* {formatted_date}\n"
        except:
            message += f"🕒 *Published:* {published}\n"
    
    # Add reactions if available
    if reactions:
        total_reactions = sum(reactions.values())
        if total_reactions > 0:
            message += f"❤️ {total_reactions} reactions | 💬 {comments} comments\n"
    
    if share_url:
        message += f"\n🔗 [Read Full Article]({share_url})"
    
    return message, thumb

# ==================== BOT HANDLERS ====================

async def start_command(message: types.Message):
    """Handle /start command"""
    welcome_message = (
        "🇱🇰 *Welcome to Esana News Bot!* 📰\n\n"
        "I deliver breaking news from Sri Lanka's top news source directly to you.\n\n"
        "*Available Commands:*\n"
        "/news - Get latest 10 news articles\n"
        "/latest - Get the most recent news\n"
        "/alerts - Get alert/warning news\n"
        "/hot - Get most popular news\n"
        "/subscribe - Subscribe to automatic updates\n"
        "/unsubscribe - Unsubscribe from updates\n"
        "/help - Show this help message\n\n"
        "🔔 *Note:* Add me to any group and I'll send news updates there too!\n\n"
        "📌 *Source:* Esana News (helakuru.lk/esana)\n"
        "⚡ *API:* Updated every 5 minutes"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📰 Latest News", callback_data="latest"),
            InlineKeyboardButton(text="🔥 Hot News", callback_data="hot")
        ],
        [
            InlineKeyboardButton(text="⚠️ Alerts", callback_data="alerts"),
            InlineKeyboardButton(text="🔔 Subscribe", callback_data="subscribe")
        ],
        [
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
        "*📖 Esana News Bot Help*\n\n"
        "*Commands:*\n"
        "/news - Get latest 10 news articles\n"
        "/latest - Get the most recent news\n"
        "/alerts - Get alert/warning news\n"
        "/hot - Get most popular news\n"
        "/subscribe - Subscribe to automatic updates\n"
        "/unsubscribe - Unsubscribe from updates\n\n"
        "*Features:*\n"
        "• Automatic news delivery every 5 minutes\n"
        "• Full article text extraction\n"
        "• Image thumbnails with news\n"
        "• Real-time breaking news alerts\n\n"
        "*Source:* Esana News via Helakuru\n"
        "*API Developer:* Thamindu Disna\n\n"
        "📌 *Tip:* Use inline buttons for quick access!\n"
        "🔄 *Update interval:* 5 minutes (as recommended by API)"
    )
    
    await message.answer(help_text, parse_mode=ParseMode.MARKDOWN)

async def news_command(message: types.Message):
    """Handle /news command - Send latest 10 news"""
    await message.answer("📡 Fetching latest news from Esana...")
    
    articles = fetch_esana_news()
    if not articles:
        await message.answer("❌ Failed to fetch news. Please try again later.")
        return
    
    # Send first 10 articles
    sent = 0
    for article in articles[:10]:
        message_text, thumbnail = format_news_message(article)
        
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
            sent += 1
            await asyncio.sleep(0.5)
        except Exception as e:
            logger.error(f"Error sending news: {e}")
    
    await message.answer(f"✅ Sent {sent} news articles")

async def latest_command(message: types.Message):
    """Handle /latest command - Send most recent news"""
    articles = fetch_esana_news()
    if not articles or len(articles) == 0:
        await message.answer("❌ Failed to fetch latest news.")
        return
    
    article = articles[0]
    message_text, thumbnail = format_news_message(article)
    
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
    except Exception as e:
        logger.error(f"Error sending latest news: {e}")

async def alerts_command(message: types.Message):
    """Handle alerts - Send news with category 4 (Alerts/Warnings)"""
    await message.answer("⚠️ Fetching alerts from Esana...")
    
    articles = fetch_esana_news()
    if not articles:
        await message.answer("❌ Failed to fetch alerts.")
        return
    
    # Filter alerts (category 4)
    alerts = [a for a in articles if a.get('category') == 4]
    
    if not alerts:
        await message.answer("No alerts at the moment.")
        return
    
    for article in alerts[:5]:
        message_text, thumbnail = format_news_message(article)
        
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
            logger.error(f"Error sending alert: {e}")

async def hot_command(message: types.Message):
    """Handle hot news - Send news with most reactions"""
    await message.answer("🔥 Fetching hot news from Esana...")
    
    articles = fetch_esana_news()
    if not articles:
        await message.answer("❌ Failed to fetch hot news.")
        return
    
    # Calculate total reactions for each article
    for article in articles:
        reactions = article.get('reactions', {})
        article['total_reactions'] = sum(reactions.values())
    
    # Sort by reactions
    hot_news = sorted(articles, key=lambda x: x.get('total_reactions', 0), reverse=True)[:5]
    
    for article in hot_news:
        message_text, thumbnail = format_news_message(article)
        
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
            logger.error(f"Error sending hot news: {e}")

# Global bot data
bot_data = {'subscribers': set()}

async def subscribe_command(message: types.Message):
    """Handle /subscribe command"""
    chat_id = message.chat.id
    
    if 'subscribers' not in bot_data:
        bot_data['subscribers'] = set()
    
    bot_data['subscribers'].add(chat_id)
    save_cache()
    
    await message.answer(
        "✅ *Successfully subscribed!*\n\n"
        "You will now receive automatic Esana News updates every 5 minutes.\n"
        "Use /unsubscribe to stop receiving updates.",
        parse_mode=ParseMode.MARKDOWN
    )

async def unsubscribe_command(message: types.Message):
    """Handle /unsubscribe command"""
    chat_id = message.chat.id
    
    if 'subscribers' in bot_data:
        bot_data['subscribers'].discard(chat_id)
    
    save_cache()
    
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
    
    # Create a mock message object
    class MockMessage:
        def __init__(self, original_message):
            self.chat = original_message.chat
            self.answer = original_message.answer
            self.answer_photo = original_message.answer_photo
        
        async def answer(self, *args, **kwargs):
            await original_message.answer(*args, **kwargs)
        
        async def answer_photo(self, *args, **kwargs):
            await original_message.answer_photo(*args, **kwargs)
    
    mock_msg = MockMessage(message)
    
    if data == "latest":
        await latest_command(mock_msg)
    elif data == "subscribe":
        await subscribe_command(mock_msg)
    elif data == "alerts":
        await alerts_command(mock_msg)
    elif data == "hot":
        await hot_command(mock_msg)
    elif data == "help":
        await help_command(mock_msg)

# ==================== AUTO-NEWS CHECKER ====================

async def check_for_new_news(bot: Bot):
    """Background task to check for new news and send to subscribers"""
    global sent_news_ids
    
    logger.info("Checking for new Esana News...")
    articles = fetch_esana_news()
    
    if not articles:
        logger.warning("No news data received")
        return
    
    # Check for new articles
    new_articles = []
    for article in articles:
        news_id = article.get('id')
        if news_id and news_id not in sent_news_ids:
            new_articles.append(article)
            sent_news_ids.add(news_id)
    
    # Limit cache size
    if len(sent_news_ids) > 500:
        sent_news_ids = set(list(sent_news_ids)[-250:])
    
    save_cache()
    
    if not new_articles:
        logger.info("No new news found")
        return
    
    logger.info(f"Found {len(new_articles)} new articles")
    
    # Send to subscribers
    subscribers = bot_data.get('subscribers', set())
    if not subscribers:
        logger.info("No subscribers to notify")
        return
    
    for article in new_articles[:5]:  # Send max 5 new articles
        message_text, thumbnail = format_news_message(article)
        
        for chat_id in subscribers:
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
    # Load cache
    load_cache()
    
    # Initialize bot and dispatcher
    bot = Bot(token=TELEGRAM_BOT_TOKEN)
    dp = Dispatcher()
    
    # Register handlers
    dp.message.register(start_command, Command("start"))
    dp.message.register(help_command, Command("help"))
    dp.message.register(news_command, Command("news"))
    dp.message.register(latest_command, Command("latest"))
    dp.message.register(alerts_command, Command("alerts"))
    dp.message.register(hot_command, Command("hot"))
    dp.message.register(subscribe_command, Command("subscribe"))
    dp.message.register(unsubscribe_command, Command("unsubscribe"))
    
    # Callback query handler
    dp.callback_query.register(callback_handler)
    
    # Start background task
    asyncio.create_task(background_news_checker(bot))
    
    logger.info("Starting Esana News Bot with aiogram...")
    logger.info(f"API URL: {ESANA_API_URL}")
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
