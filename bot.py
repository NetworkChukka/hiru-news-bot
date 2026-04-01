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
from collections import defaultdict

# ==================== CONFIGURATION ====================
TELEGRAM_BOT_TOKEN = "8025861936:AAGjidGhuNoB_Y5SrKUCenwWI3AlWaj_XPM"  # Replace with your bot token

# API Configurations
APIS = {
    "hiru": {
        "name": "Hiru News",
        "url": "https://hirunews.vercel.app/api/latest-news",
        "type": "rest",
        "icon": "📺"
    },
    "esana": {
        "name": "Esana News", 
        "url": "https://esena-news-api-v3.vercel.app/",
        "type": "nested",
        "data_path": ["news_data", "data"],
        "icon": "📰"
    }
}

CHECK_INTERVAL = 300  # Check every 5 minutes
CACHE_FILE = "sent_news_cache.json"
COMBINED_CACHE_FILE = "combined_news_cache.json"

# Store sent news IDs to avoid duplicates
sent_news_ids = set()
combined_news_cache = []

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ==================== CACHE FUNCTIONS ====================

def load_cache():
    """Load sent news IDs from cache file"""
    global sent_news_ids, combined_news_cache
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, 'r') as f:
                data = json.load(f)
                sent_news_ids = set(data.get('sent_ids', []))
                logger.info(f"Loaded {len(sent_news_ids)} cached news IDs")
        except Exception as e:
            logger.error(f"Error loading cache: {e}")
    
    if os.path.exists(COMBINED_CACHE_FILE):
        try:
            with open(COMBINED_CACHE_FILE, 'r') as f:
                combined_news_cache = json.load(f)
                logger.info(f"Loaded {len(combined_news_cache)} cached combined articles")
        except Exception as e:
            logger.error(f"Error loading combined cache: {e}")

def save_cache():
    """Save sent news IDs to cache file"""
    try:
        with open(CACHE_FILE, 'w') as f:
            json.dump({'sent_ids': list(sent_news_ids)}, f)
        
        with open(COMBINED_CACHE_FILE, 'w') as f:
            json.dump(combined_news_cache, f)
    except Exception as e:
        logger.error(f"Error saving cache: {e}")

# ==================== API FUNCTIONS ====================

def fetch_hiru_news():
    """Fetch news from Hiru News API"""
    try:
        response = requests.get(APIS["hiru"]["url"], params={"limit": 30}, timeout=15)
        response.raise_for_status()
        data = response.json()
        
        if data.get('success'):
            articles = data.get('data', [])
            logger.info(f"✅ Hiru News: {len(articles)} articles fetched")
            return articles
        return None
    except Exception as e:
        logger.error(f"❌ Hiru News API error: {e}")
        return None

def fetch_esana_news():
    """Fetch news from Esana News API"""
    try:
        response = requests.get(APIS["esana"]["url"], timeout=15)
        response.raise_for_status()
        data = response.json()
        
        # Navigate to articles
        articles = data
        for key in APIS["esana"].get("data_path", []):
            articles = articles.get(key, [])
        
        if isinstance(articles, list):
            logger.info(f"✅ Esana News: {len(articles)} articles fetched")
            return articles
        return None
    except Exception as e:
        logger.error(f"❌ Esana News API error: {e}")
        return None

def normalize_hiru_article(article, source="hiru"):
    """Convert Hiru article to standard format"""
    return {
        'id': f"hiru_{article.get('id', '')}",
        'source': source,
        'source_name': 'Hiru News',
        'source_icon': '📺',
        'title': article.get('headline', article.get('title', 'No Title')),
        'content': article.get('summary', article.get('content', '')),
        'full_text': article.get('fullText', ''),
        'thumbnail': article.get('thumbnail', ''),
        'url': article.get('url', ''),
        'published': article.get('publishedDate', article.get('date', '')),
        'category': article.get('category', 'General'),
        'reactions': article.get('reactions', {}),
        'comments': article.get('comments', 0),
        'word_count': article.get('wordCount', 0)
    }

def normalize_esana_article(article, source="esana"):
    """Convert Esana article to standard format"""
    # Extract title
    title = article.get('titleSi', '')
    if not title:
        title = article.get('titleEn', 'No Title')
    
    # Extract content from contentSi or contentEn
    content = ""
    content_si = article.get('contentSi', [])
    for item in content_si:
        if isinstance(item, dict) and item.get('type') == 'text':
            content += item.get('data', '') + " "
    
    if not content:
        content_en = article.get('contentEn', [])
        for item in content_en:
            if isinstance(item, dict) and item.get('type') == 'text':
                content += item.get('data', '') + " "
    
    return {
        'id': f"esana_{article.get('id', '')}",
        'source': source,
        'source_name': 'Esana News',
        'source_icon': '📰',
        'title': title.strip(),
        'content': content.strip()[:500],
        'full_text': content.strip(),
        'thumbnail': article.get('thumb', article.get('cover', '')),
        'url': article.get('share_url', ''),
        'published': article.get('published', ''),
        'category': article.get('category', 'General'),
        'reactions': article.get('reactions', {}),
        'comments': article.get('comments', 0),
        'word_count': 0
    }

def fetch_combined_news():
    """Fetch and combine news from both sources"""
    all_articles = []
    source_stats = {}
    
    # Fetch Hiru News
    hiru_articles = fetch_hiru_news()
    if hiru_articles:
        source_stats['hiru'] = len(hiru_articles)
        for article in hiru_articles[:30]:
            all_articles.append(normalize_hiru_article(article))
    
    # Fetch Esana News
    esana_articles = fetch_esana_news()
    if esana_articles:
        source_stats['esana'] = len(esana_articles)
        for article in esana_articles[:30]:
            all_articles.append(normalize_esana_article(article))
    
    # Sort by published date (newest first)
    all_articles.sort(key=lambda x: x.get('published', ''), reverse=True)
    
    logger.info(f"Combined {len(all_articles)} articles from both sources")
    return all_articles, source_stats

def get_news_by_category(articles, category):
    """Filter articles by category"""
    category_map = {
        'sports': ['sports', 'Sports', 'ක්‍රීඩා'],
        'business': ['business', 'Business', 'ව්‍යාපාර'],
        'entertainment': ['entertainment', 'Entertainment', 'විනෝදාස්වාදය'],
        'international': ['international', 'International', 'විදේශ'],
        'alert': [4, 'Alert', 'අනතුරු ඇඟවීම'],
        'local': [2, 'local', 'Local', 'දේශීය']
    }
    
    if category not in category_map:
        return articles
    
    filtered = []
    for article in articles:
        article_cat = article.get('category', '')
        if any(cat.lower() in str(article_cat).lower() for cat in category_map[category]):
            filtered.append(article)
    
    return filtered

def get_hot_news(articles, limit=10):
    """Get most popular news based on reactions"""
    for article in articles:
        reactions = article.get('reactions', {})
        total = sum(reactions.values()) if isinstance(reactions, dict) else 0
        article['popularity'] = total
    
    return sorted(articles, key=lambda x: x.get('popularity', 0), reverse=True)[:limit]

def format_news_message(article):
    """Format a single news article into a readable message"""
    source_icon = article.get('source_icon', '📰')
    source_name = article.get('source_name', 'News')
    title = article.get('title', 'No Title')
    content = article.get('content', '')
    full_text = article.get('full_text', '')
    thumbnail = article.get('thumbnail', '')
    url = article.get('url', '')
    published = article.get('published', '')
    category = article.get('category', 'General')
    reactions = article.get('reactions', {})
    comments = article.get('comments', 0)
    
    # Use full text if available and content is too short
    if len(content) < 100 and full_text:
        content = full_text
    
    # Clean and truncate content
    if len(content) > 500:
        content = content[:500] + "..."
    
    # Category emoji mapping
    category_emojis = {
        'sports': '🏏',
        'business': '💰',
        'entertainment': '🎬',
        'international': '🌍',
        'General': '📰'
    }
    cat_emoji = category_emojis.get(str(category).lower(), '📰')
    
    # Build message
    message = f"{source_icon} *{html.escape(source_name)}*\n\n"
    message += f"📌 *{html.escape(title)}*\n\n"
    
    if content:
        message += f"{html.escape(content)}\n\n"
    
    message += f"{cat_emoji} *Category:* {category}\n"
    
    # Format published date
    if published:
        try:
            # Try different date formats
            for fmt in ["%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d"]:
                try:
                    date_obj = datetime.strptime(published, fmt)
                    formatted_date = date_obj.strftime("%Y-%m-%d %I:%M %p")
                    message += f"🕒 *Published:* {formatted_date}\n"
                    break
                except:
                    continue
            else:
                message += f"🕒 *Published:* {published}\n"
        except:
            message += f"🕒 *Published:* {published}\n"
    
    # Add reactions if available
    if reactions and isinstance(reactions, dict):
        total_reactions = sum(reactions.values())
        if total_reactions > 0:
            message += f"❤️ {total_reactions} reactions | 💬 {comments} comments\n"
    
    if url:
        message += f"\n🔗 [Read Full Article]({url})"
    
    return message, thumbnail

# ==================== BOT HANDLERS ====================

async def start_command(message: types.Message):
    """Handle /start command"""
    welcome_message = (
        "🇱🇰 *Welcome to Sri Lanka News Bot!* 📰📺\n\n"
        "I combine **Hiru News** and **Esana News** to bring you the best coverage!\n\n"
        "*Available Commands:*\n"
        "/news - Get latest 20 news (combined)\n"
        "/latest - Get most recent news\n"
        "/hiru - Get news from Hiru only\n"
        "/esana - Get news from Esana only\n"
        "/sports - Sports news\n"
        "/business - Business news\n"
        "/entertainment - Entertainment news\n"
        "/hot - Most popular news\n"
        "/alerts - Alerts & warnings\n"
        "/status - Check API status\n"
        "/subscribe - Auto updates every 5 min\n"
        "/unsubscribe - Stop updates\n"
        "/help - Show this help\n\n"
        "⚡ *Dual Source:* News from 2 major Sri Lankan sources!"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📰 Latest News", callback_data="latest"),
            InlineKeyboardButton(text="🔥 Hot News", callback_data="hot")
        ],
        [
            InlineKeyboardButton(text="📺 Hiru Only", callback_data="hiru"),
            InlineKeyboardButton(text="📰 Esana Only", callback_data="esana")
        ],
        [
            InlineKeyboardButton(text="🏏 Sports", callback_data="sports"),
            InlineKeyboardButton(text="💰 Business", callback_data="business")
        ],
        [
            InlineKeyboardButton(text="⚠️ Alerts", callback_data="alerts"),
            InlineKeyboardButton(text="📊 Status", callback_data="status")
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
        "*📖 Sri Lanka News Bot Help*\n\n"
        "*Commands:*\n"
        "/news - Latest 20 news (combined)\n"
        "/latest - Most recent single news\n"
        "/hiru - Hiru News only\n"
        "/esana - Esana News only\n"
        "/sports - Sports news\n"
        "/business - Business news\n"
        "/entertainment - Entertainment news\n"
        "/hot - Most popular news\n"
        "/alerts - Alerts & warnings\n"
        "/status - API status\n"
        "/subscribe - Auto updates (5 min)\n"
        "/unsubscribe - Stop updates\n\n"
        "*Features:*\n"
        "• **Dual Source** - Hiru + Esana\n"
        "• Automatic updates every 5 minutes\n"
        "• Smart content formatting\n"
        "• Category filtering\n"
        "• Popularity ranking\n\n"
        "*Sources:*\n"
        "📺 Hiru News - hirunews.lk\n"
        "📰 Esana News - helakuru.lk/esana\n\n"
        "📌 *Tip:* Use inline buttons for quick access!"
    )
    
    await message.answer(help_text, parse_mode=ParseMode.MARKDOWN)

async def news_command(message: types.Message):
    """Handle /news command - Combined news"""
    await message.answer("📡 Fetching news from both sources...")
    
    articles, stats = fetch_combined_news()
    if not articles:
        await message.answer("❌ Failed to fetch news from both sources. Please try again.")
        return
    
    await message.answer(
        f"✅ *Fetched {len(articles)} articles*\n"
        f"📺 Hiru: {stats.get('hiru', 0)} | 📰 Esana: {stats.get('esana', 0)}",
        parse_mode=ParseMode.MARKDOWN
    )
    
    sent = 0
    for article in articles[:20]:
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
    
    await message.answer(f"✅ Sent {sent} news articles from both sources!")

async def latest_command(message: types.Message):
    """Handle /latest command - Most recent news"""
    articles, _ = fetch_combined_news()
    if not articles:
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

async def hiru_only_command(message: types.Message):
    """Handle /hiru command - Hiru News only"""
    await message.answer("📺 Fetching Hiru News...")
    
    articles = fetch_hiru_news()
    if not articles:
        await message.answer("❌ Failed to fetch Hiru News.")
        return
    
    for article in articles[:10]:
        normalized = normalize_hiru_article(article)
        message_text, thumbnail = format_news_message(normalized)
        
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
            logger.error(f"Error sending Hiru news: {e}")

async def esana_only_command(message: types.Message):
    """Handle /esana command - Esana News only"""
    await message.answer("📰 Fetching Esana News...")
    
    articles = fetch_esana_news()
    if not articles:
        await message.answer("❌ Failed to fetch Esana News.")
        return
    
    for article in articles[:10]:
        normalized = normalize_esana_article(article)
        message_text, thumbnail = format_news_message(normalized)
        
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
            logger.error(f"Error sending Esana news: {e}")

async def sports_command(message: types.Message):
    """Handle /sports command"""
    await message.answer("🏏 Fetching sports news...")
    
    articles, _ = fetch_combined_news()
    if not articles:
        await message.answer("❌ Failed to fetch news.")
        return
    
    sports_news = get_news_by_category(articles, 'sports')
    
    if not sports_news:
        await message.answer("No sports news at the moment.")
        return
    
    for article in sports_news[:10]:
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
            logger.error(f"Error sending sports news: {e}")

async def business_command(message: types.Message):
    """Handle /business command"""
    await message.answer("💰 Fetching business news...")
    
    articles, _ = fetch_combined_news()
    if not articles:
        await message.answer("❌ Failed to fetch news.")
        return
    
    business_news = get_news_by_category(articles, 'business')
    
    if not business_news:
        await message.answer("No business news at the moment.")
        return
    
    for article in business_news[:10]:
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
            logger.error(f"Error sending business news: {e}")

async def entertainment_command(message: types.Message):
    """Handle /entertainment command"""
    await message.answer("🎬 Fetching entertainment news...")
    
    articles, _ = fetch_combined_news()
    if not articles:
        await message.answer("❌ Failed to fetch news.")
        return
    
    entertainment_news = get_news_by_category(articles, 'entertainment')
    
    if not entertainment_news:
        await message.answer("No entertainment news at the moment.")
        return
    
    for article in entertainment_news[:10]:
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
            logger.error(f"Error sending entertainment news: {e}")

async def hot_command(message: types.Message):
    """Handle /hot command - Most popular news"""
    await message.answer("🔥 Fetching most popular news...")
    
    articles, _ = fetch_combined_news()
    if not articles:
        await message.answer("❌ Failed to fetch news.")
        return
    
    hot_news = get_hot_news(articles, limit=10)
    
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

async def alerts_command(message: types.Message):
    """Handle /alerts command"""
    await message.answer("⚠️ Fetching alerts and warnings...")
    
    articles, _ = fetch_combined_news()
    if not articles:
        await message.answer("❌ Failed to fetch news.")
        return
    
    alerts_news = get_news_by_category(articles, 'alert')
    
    if not alerts_news:
        await message.answer("No alerts at the moment.")
        return
    
    for article in alerts_news[:10]:
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

async def status_command(message: types.Message):
    """Check API status for both sources"""
    status_text = "*📊 API Status Report*\n\n"
    
    # Check Hiru API
    try:
        start_time = datetime.now()
        response = requests.get(APIS["hiru"]["url"], params={"limit": 1}, timeout=10)
        response_time = (datetime.now() - start_time).total_seconds()
        
        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                status_text += f"✅ *Hiru News API*\n"
                status_text += f"   Status: Online\n"
                status_text += f"   Response: {response_time:.2f}s\n"
                status_text += f"   Articles: {len(data.get('data', []))}\n\n"
            else:
                status_text += f"⚠️ *Hiru News API*\n"
                status_text += f"   Status: Error in response\n\n"
        else:
            status_text += f"⚠️ *Hiru News API*\n"
            status_text += f"   Status: HTTP {response.status_code}\n\n"
    except Exception as e:
        status_text += f"❌ *Hiru News API*\n"
        status_text += f"   Status: Offline\n"
        status_text += f"   Error: {str(e)[:50]}\n\n"
    
    # Check Esana API
    try:
        start_time = datetime.now()
        response = requests.get(APIS["esana"]["url"], timeout=10)
        response_time = (datetime.now() - start_time).total_seconds()
        
        if response.status_code == 200:
            data = response.json()
            articles = data
            for key in APIS["esana"].get("data_path", []):
                articles = articles.get(key, [])
            
            if isinstance(articles, list):
                status_text += f"✅ *Esana News API*\n"
                status_text += f"   Status: Online\n"
                status_text += f"   Response: {response_time:.2f}s\n"
                status_text += f"   Articles: {len(articles)}\n\n"
            else:
                status_text += f"⚠️ *Esana News API*\n"
                status_text += f"   Status: Invalid data format\n\n"
        else:
            status_text += f"⚠️ *Esana News API*\n"
            status_text += f"   Status: HTTP {response.status_code}\n\n"
    except Exception as e:
        status_text += f"❌ *Esana News API*\n"
        status_text += f"   Status: Offline\n"
        status_text += f"   Error: {str(e)[:50]}\n\n"
    
    await message.answer(status_text, parse_mode=ParseMode.MARKDOWN)

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
        "You will now receive automatic news updates from **both Hiru and Esana** every 5 minutes.\n"
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
    elif data == "hiru":
        await hiru_only_command(mock_msg)
    elif data == "esana":
        await esana_only_command(mock_msg)
    elif data == "sports":
        await sports_command(mock_msg)
    elif data == "business":
        await business_command(mock_msg)
    elif data == "alerts":
        await alerts_command(mock_msg)
    elif data == "hot":
        await hot_command(mock_msg)
    elif data == "status":
        await status_command(mock_msg)
    elif data == "subscribe":
        await subscribe_command(mock_msg)
    elif data == "help":
        await help_command(mock_msg)

# ==================== AUTO-NEWS CHECKER ====================

async def check_for_new_news(bot: Bot):
    """Background task to check for new news from both sources"""
    global sent_news_ids
    
    logger.info("Checking for new news from both sources...")
    articles, stats = fetch_combined_news()
    
    if not articles:
        logger.warning("No news data received from either source")
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
    
    logger.info(f"Found {len(new_articles)} new articles from both sources")
    
    # Send to subscribers
    subscribers = bot_data.get('subscribers', set())
    if not subscribers:
        logger.info("No subscribers to notify")
        return
    
    # Send only the most recent 5 new articles
    for article in new_articles[:5]:
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
    
    # Register all command handlers
    dp.message.register(start_command, Command("start"))
    dp.message.register(help_command, Command("help"))
    dp.message.register(news_command, Command("news"))
    dp.message.register(latest_command, Command("latest"))
    dp.message.register(hiru_only_command, Command("hiru"))
    dp.message.register(esana_only_command, Command("esana"))
    dp.message.register(sports_command, Command("sports"))
    dp.message.register(business_command, Command("business"))
    dp.message.register(entertainment_command, Command("entertainment"))
    dp.message.register(hot_command, Command("hot"))
    dp.message.register(alerts_command, Command("alerts"))
    dp.message.register(status_command, Command("status"))
    dp.message.register(subscribe_command, Command("subscribe"))
    dp.message.register(unsubscribe_command, Command("unsubscribe"))
    
    # Callback query handler
    dp.callback_query.register(callback_handler)
    
    # Start background task
    asyncio.create_task(background_news_checker(bot))
    
    logger.info("Starting Sri Lanka News Bot (Hiru + Esana)...")
    logger.info("Bot combines news from both sources for comprehensive coverage!")
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
