def format_telegram_message(self, new_regattas: List[Dict]) -> str:
        """Format new regattas for Telegram posting with clean visual design"""
        if not new_regattas:
            return ""
        
        # Sort events by club and date for better organization
        sorted_regattas = sorted(new_regattas, key=lambda x: (x['club'], x['date']))
        
        message_parts = [
            "⛵ Balearic Sailing Regattas ⛵",
            f"**[View Full Calendar]({self.get_calendar_url()})**",
            ""
        ]
        
        # Track message length to stay under 4096 characters
        current_length = len("\n".join(message_parts))
        max_length = 3500  # Leave buffer for footer
        
        # Group by club for clean presentation
        current_club = None
        event_count = 0
        
        for regatta in sorted_regattas:
            if current_length > max_length:
                break
                
            event_count += 1
            
            # Add club separator if new club
            if regatta['club'] != current_club:
                if current_club is not None:  # Add separator between clubs
                    message_parts.append("---")
                current_club = regatta['club']
            
            # Get symbols and names for categorization
            boat_symbol = regatta['boat_symbol']
            boat_type_name = {
                'yachts': 'Yachts',
                'dinghies': 'Dinghies', 
                'mixed': 'Mixed'
            }.get(regatta['boat_type'], 'Mixed')
            
            # Get event type with colored emoji
            event_type_display = {
                'single_day': '🔵 Single Day',
                'multi_day': '🟢 Multi-Day',
                'series': '🔴 Series'
            }.get(regatta['event_type'], '🔵 Single Day')
            
            # Format event entry in clean style
            event_entry = [
                f"{event_count}. {regatta['club']} {boat_symbol} {boat_type_name}",
                f"   {regatta['title']}",
                f"   {regatta['date']}",
                f"   {event_type_display}",
                f"   [More info]({regatta['url']})",
                ""
            ]#!/usr/bin/env python3
"""
Balearic Islands Sailing Regatta Scraper - SMART CATEGORIZED VERSION
- Only sends Telegram messages when NEW events are found
- Categorizes boats: Large Boats, Dinghies, Mixed
- Color codes events: Blue (single day), Green (multi-day), Orange (series)
- Always updates calendar with all events
"""

import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime, timedelta
import json
import os
import logging
import time
from typing import List, Dict, Set

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class SmartRegattaScraper:
    def __init__(self, telegram_bot_token=None, telegram_chat_id=None):
        self.telegram_bot_token = telegram_bot_token
        self.telegram_chat_id = telegram_chat_id
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        
        # Boat category keywords
        self.yacht_keywords = [
            'orc', 'swan', 'j70', 'j/70', 'crucero', 'cruceros', 'cruising', 
            'keelboat', 'maxi', 'phrf', 'irc', 'crf', 'open', 'big boat',
            'yacht', 'monohull', 'multihull', 'catamaran', 'trimaran'
        ]
        
        self.dinghy_keywords = [
            'optimist', 'optimista', 'laser', 'ilca', '420', 'snipe', 'dragon',
            'dragón', 'cadet', 'europe', 'finn', 'radial', 'standard', 'dinghy',
            'single handed', 'double handed', 'youth', 'junior', 'cadete'
        ]
        
        # Event type keywords
        self.series_keywords = [
            'series', 'liga', 'championship', 'campeonato', 'circuit', 'circuito',
            'anual', 'annual', 'temporada', 'season', 'ranking'
        ]
        
        # Balearic Islands sailing clubs
        self.clubs = [
            {
                'name': 'CN Port d\'Ítxol',
                'url': 'https://www.cnportitxol.info/regatas/',
                'location': 'Mallorca'
            },
            {
                'name': 'La Ruta de la Sal',
                'url': 'https://larutadelasal.com/',
                'location': 'Mallorca'
            },
            {
                'name': 'Copa del Rey MAPFRE',
                'url': 'https://www.regatacopadelrey.com/home',
                'location': 'Mallorca'
            },
            {
                'name': 'Trofeo Conde de Godó',
                'url': 'https://www.trofeocondegodo.com/',
                'location': 'Mallorca'
            },
            {
                'name': 'PalmaVela',
                'url': 'https://www.palmavela.com/',
                'location': 'Mallorca'
            },
            {
                'name': 'Real Club Náutico de Palma',
                'url': 'https://www.rcnp.es/regatas',
                'location': 'Mallorca'
            },
            {
                'name': 'CN Ciutadella',
                'url': 'https://regates.cnciutadella.com/es/default/races',
                'location': 'Menorca'
            },
            {
                'name': 'CN Arenal',
                'url': 'https://regatas.cnarenal.com/es/default/races',
                'location': 'Mallorca'
            },
            {
                'name': 'Regata Ophiusa',
                'url': 'https://www.regataophiusa.com/pag_2/index.php',
                'location': 'Formentera'
            },
            {
                'name': 'Club Marítimo San Antonio',
                'url': 'https://www.cmsap.com/en/default/races/calendar',
                'location': 'Ibiza'
            },
            {
                'name': 'CN Colonia Sant Jordi',
                'url': 'https://cncoloniasp.com/regatas/',
                'location': 'Mallorca'
            },
            {
                'name': 'CV Port d\'Andratx',
                'url': 'http://regatas.cvpa.es/es/default/races/calendar/year/2025/all/1',
                'location': 'Mallorca'
            },
            {
                'name': 'CN Ràpita',
                'url': 'https://regatas.cnrapita.com/es/default/races',
                'location': 'Mallorca'
            }
        ]

    def create_event_signature(self, regatta: Dict) -> str:
        """Create a unique signature for each event"""
        return f"{regatta.get('title', '')}-{regatta.get('date', '')}-{regatta.get('club', '')}"

    def load_previous_events(self, filename='previous_events.json') -> Set[str]:
        """Load previously found events"""
        try:
            if os.path.exists(filename):
                with open(filename, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return set(data.get('event_signatures', []))
            return set()
        except Exception as e:
            logger.error(f"Error loading previous events: {e}")
            return set()

    def save_current_events(self, event_signatures: Set[str], filename='previous_events.json'):
        """Save current events for next comparison"""
        try:
            data = {
                'event_signatures': list(event_signatures),
                'last_updated': datetime.now().isoformat()
            }
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving current events: {e}")

    def categorize_boat_type(self, text: str) -> str:
        """Categorize boat type based on text content"""
        text_lower = text.lower()
        
        # Check for yacht keywords
        for keyword in self.yacht_keywords:
            if keyword in text_lower:
                return 'yachts'
        
        # Check for dinghy keywords
        for keyword in self.dinghy_keywords:
            if keyword in text_lower:
                return 'dinghies'
        
        # Default to mixed if unclear
        return 'mixed'

    def categorize_event_type(self, title: str, date_str: str, details: str) -> str:
        """Categorize event type based on date patterns and keywords"""
        combined_text = f"{title} {date_str} {details}".lower()
        
        # Check for series keywords
        for keyword in self.series_keywords:
            if keyword in combined_text:
                return 'series'
        
        # Check date patterns for multi-day events
        multi_day_patterns = [
            r'del\s+\d{1,2}\s+de\s+\w+\s+al\s+\d{1,2}\s+de\s+\w+',  # del X de mes al Y de mes
            r'del\s+\d{1,2}\s+al\s+\d{1,2}\s+de\s+\w+',  # del X al Y de mes
            r'\d{1,2}\s*-\s*\d{1,2}\s+\w+',  # 26-28 July
            r'\d{1,2}/\d{1,2}\s*-\s*\d{1,2}/\d{1,2}'  # 26/7 - 28/7
        ]
        
        for pattern in multi_day_patterns:
            if re.search(pattern, date_str.lower()):
                return 'multi_day'
        
        # Default to single day
        return 'single_day'

    def get_event_color(self, event_type: str) -> str:
        """Get color code for event type"""
        color_map = {
            'single_day': '#4285f4',    # Blue
            'multi_day': '#34a853',     # Green
            'series': '#ff9800'         # Orange
        }
        return color_map.get(event_type, '#4285f4')

    def get_event_symbol(self, event_type: str) -> str:
        """Get color symbol for event type"""
        symbols = {
            'single_day': 'BLUE',
            'multi_day': 'GREEN',
            'series': 'RED'
        }
        return symbols.get(event_type, 'BLUE')

    def get_boat_symbol(self, boat_type: str) -> str:
        """Get text symbol for boat type"""
        symbols = {
            'yachts': '▲',
            'dinghies': '●',
            'mixed': '■'
        }
        return symbols.get(boat_type, '■')

    def identify_new_events(self, current_regattas: List[Dict]) -> List[Dict]:
        """Identify which events are new since last run"""
        previous_signatures = self.load_previous_events()
        current_signatures = set()
        new_events = []
        
        for regatta in current_regattas:
            signature = self.create_event_signature(regatta)
            current_signatures.add(signature)
            
            if signature not in previous_signatures:
                new_events.append(regatta)
        
        # Save current signatures for next run
        self.save_current_events(current_signatures)
        
        logger.info(f"Found {len(new_events)} new events out of {len(current_regattas)} total events")
        return new_events

    def scrape_club_regattas(self, club_info: Dict) -> List[Dict]:
        """Scrape regatta information from a specific club"""
        regattas = []
        
        try:
            logger.info(f"Processing {club_info['name']}...")
            
            response = self.session.get(club_info['url'], timeout=8)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            text_content = soup.get_text()
            
            # Extract regatta information
            found_regattas = self.extract_regatta_info(text_content, club_info)
            
            if found_regattas:
                logger.info(f"Found {len(found_regattas)} regattas at {club_info['name']}")
                regattas.extend(found_regattas)
            else:
                logger.info(f"No regattas found at {club_info['name']}")
                
        except Exception as e:
            logger.error(f"Error scraping {club_info['name']}: {e}")
            
        return regattas

    def extract_regatta_info(self, text: str, club_info: Dict) -> List[Dict]:
        """Extract regatta information from text content with categorization"""
        regattas = []
        
        # Enhanced regatta keywords
        regatta_keywords = [
            'regata', 'copa', 'trofeo', 'campeonato', 'series', 'vuelta',
            'memorial', 'challenge', 'open', 'master', 'junior', 'youth'
        ]
        
        # Filter content
        filtered_keywords = [
            'resultado', 'results', 'clasificación', 'classification',
            'inscripción', 'registration', 'noticias', 'news', 'archivo',
            'archive', 'galería', 'gallery', 'contacto', 'contact'
        ]
        
        # Date patterns
        date_patterns = [
            r'\bdel\s+\d{1,2}\s+de\s+\w+\s+al\s+\d{1,2}\s+de\s+\w+\s+de\s+\d{4}\b',
            r'\bdel\s+\d{1,2}\s+al\s+\d{1,2}\s+de\s+\w+\s+de\s+\d{4}\b',
            r'\b\d{1,2}\s+de\s+\w+\s+de\s+\d{4}\b',
            r'\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b'
        ]
        
        # Split text into manageable chunks
        lines = text.split('\n')
        
        for i, line in enumerate(lines):
            line = line.strip()
            if len(line) < 10:
                continue
            
            # Check if line contains regatta keywords
            has_regatta_keyword = any(keyword in line.lower() for keyword in regatta_keywords)
            
            # Skip filtered content
            if any(keyword in line.lower() for keyword in filtered_keywords):
                continue
            
            # Look for dates in current and next few lines
            dates_found = []
            details_text = ""
            
            # Check current line and next 2 lines for dates and details
            for j in range(min(3, len(lines) - i)):
                check_line = lines[i + j].strip()
                
                for pattern in date_patterns:
                    matches = re.findall(pattern, check_line, re.IGNORECASE)
                    dates_found.extend(matches)
                
                if j > 0:  # Collect details from subsequent lines
                    details_text += " " + check_line
            
            # Filter dates to only include future events
            valid_dates = self.filter_future_dates(dates_found)
            
            if has_regatta_keyword and valid_dates:
                # Categorize the event
                boat_type = self.categorize_boat_type(line + " " + details_text)
                event_type = self.categorize_event_type(line, valid_dates[0], details_text)
                
                regatta = {
                    'title': self.clean_title(line),
                    'date': valid_dates[0],
                    'details': details_text.strip()[:200],  # Limit details length
                    'club': club_info['name'],
                    'location': club_info['location'],
                    'url': club_info['url'],
                    'boat_type': boat_type,
                    'event_type': event_type,
                    'color': self.get_event_color(event_type),
                    'boat_symbol': self.get_boat_symbol(boat_type),
                    'event_symbol': self.get_event_symbol(event_type)
                }
                regattas.append(regatta)
        
        return regattas

    def filter_future_dates(self, dates: List[str]) -> List[str]:
        """Filter out past dates, only return future events"""
        future_dates = []
        current_date = datetime.now()
        
        for date_str in dates:
            try:
                # Extract year from date string
                year_match = re.search(r'\b(202[5-9]|20[3-9]\d)\b', date_str)
                if year_match:
                    year = int(year_match.group(1))
                    if year >= current_date.year:
                        future_dates.append(date_str)
            except:
                continue
        
        return future_dates

    def clean_title(self, title: str) -> str:
        """Clean and format regatta title"""
        # Remove extra whitespace and special characters
        title = re.sub(r'\s+', ' ', title)
        title = re.sub(r'[^\w\s\-\.\/\(\)áéíóúñçüÁÉÍÓÚÑÇÜ]', '', title)
        return title.strip()

    def translate_text(self, text: str, target_lang: str = 'en') -> str:
        """Simple translation with fallback"""
        try:
            # First apply manual translations for sailing terms
            sailing_terms = {
                'regata': 'regatta', 'regatas': 'regattas', 'vela': 'sailing',
                'competición': 'competition', 'campeonato': 'championship',
                'trofeo': 'trophy', 'copa': 'cup', 'crucero': 'cruising',
                'optimist': 'optimist', 'optimista': 'optimist', 'dragón': 'dragon'
            }
            
            translated_text = text
            for spanish, english in sailing_terms.items():
                translated_text = re.sub(r'\b' + spanish + r'\b', english, translated_text, flags=re.IGNORECASE)
            
            # Simple Google Translate API call with short timeout
            url = 'https://translate.googleapis.com/translate_a/single'
            params = {
                'client': 'gtx',
                'sl': 'auto',
                'tl': target_lang,
                'dt': 't',
                'q': translated_text
            }
            
            response = requests.get(url, params=params, timeout=3)
            if response.status_code == 200:
                result = response.json()
                if result and result[0]:
                    return result[0][0][0]
            
        except Exception as e:
            logger.warning(f"Translation failed, using original text: {e}")
        
        # Fallback: return original text if translation fails
        return text

    def format_telegram_message(self, new_regattas: List[Dict]) -> str:
        """Format new regattas for Telegram posting with clean visual design"""
        if not new_regattas:
            return ""
        
        # Sort events by club and date for better organization
        sorted_regattas = sorted(new_regattas, key=lambda x: (x['club'], x['date']))
        
        message_parts = [
            "⛵ Balearic Sailing Regattas ⛵",
            f"**[View Full Calendar]({self.get_calendar_url()})**",
            ""
        ]
        
        # Track message length to stay under 4096 characters
        current_length = len("\n".join(message_parts))
        max_length = 3500  # Leave buffer for footer
        
        # Group by club for clean presentation
        current_club = None
        event_count = 0
        
        for regatta in sorted_regattas:
            if current_length > max_length:
                break
                
            event_count += 1
            
            # Add club header if new club
            if regatta['club'] != current_club:
                if current_club is not None:  # Add separator between clubs
                    message_parts.append("---")
                current_club = regatta['club']
            
            # Get symbols for categorization
            boat_symbol = regatta['boat_symbol']
            event_symbol = regatta['event_symbol'] 
            
            # Format event entry
            event_entry = [
                f"{event_count}. {regatta['club']} {boat_symbol}",
                f"   {regatta['title']}",
                f"   {regatta['date']} [{event_symbol}]",
                f"   [More info]({regatta['url']})",
                ""
            ]
            
            # Check if we can fit this event
            entry_length = len("\n".join(event_entry))
            if current_length + entry_length < max_length:
                message_parts.extend(event_entry)
                current_length += entry_length
            else:
                break
        
        # Add footer with legend
        footer = [
            "---",
            f"Found {len(new_regattas)} NEW events",
            "",
            "▲ Yachts | ● Dinghies | ■ Mixed Fleet",
            "🔵 Single Day | 🟢 Multi-Day | 🔴 Series",
            f"*Updated: {datetime.now().strftime('%Y-%m-%d %H:%M UTC')}*"
        ]
        
        message_parts.extend(footer)
        
        return "\n".join(message_parts)

    def get_calendar_url(self) -> str:
        """Get the calendar URL"""
        return "https://abandm010.github.io/balearic-regatta-scraper"

    def send_telegram_message(self, message: str):
        """Send message to Telegram"""
        if not self.telegram_bot_token or not self.telegram_chat_id:
            logger.warning("Telegram credentials not provided")
            return
        
        try:
            url = f"https://api.telegram.org/bot{self.telegram_bot_token}/sendMessage"
            data = {
                'chat_id': self.telegram_chat_id,
                'text': message,
                'parse_mode': 'Markdown'
            }
            
            response = requests.post(url, data=data, timeout=10)
            if response.status_code == 200:
                logger.info("✅ Telegram message sent successfully")
            else:
                logger.error(f"❌ Failed to send Telegram message: {response.status_code}")
                
        except Exception as e:
            logger.error(f"❌ Error sending Telegram message: {e}")

    def save_regattas_json(self, regattas: List[Dict], filename: str = 'regattas.json'):
        """Save all regattas to JSON file for calendar"""
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(regattas, f, indent=2, ensure_ascii=False)
            logger.info(f"✅ Saved {len(regattas)} regattas to {filename}")
        except Exception as e:
            logger.error(f"❌ Error saving regattas: {e}")

    def run(self):
        """Main scraping function"""
        logger.info("🚀 Starting Balearic Sailing Regatta Scraper...")
        
        all_regattas = []
        
        # Scrape all clubs
        for club_info in self.clubs:
            club_regattas = self.scrape_club_regattas(club_info)
            all_regattas.extend(club_regattas)
            time.sleep(1)  # Be respectful to servers
        
        # Remove duplicates
        unique_regattas = []
        seen_signatures = set()
        
        for regatta in all_regattas:
            signature = self.create_event_signature(regatta)
            if signature not in seen_signatures:
                unique_regattas.append(regatta)
                seen_signatures.add(signature)
        
        logger.info(f"📊 SCRAPING SUMMARY:")
        logger.info(f"   Clubs processed: {len(self.clubs)}")
        logger.info(f"   Total regattas found: {len(unique_regattas)}")
        
        # Categorize events
        yachts = [r for r in unique_regattas if r['boat_type'] == 'yachts']
        dinghies = [r for r in unique_regattas if r['boat_type'] == 'dinghies']
        mixed = [r for r in unique_regattas if r['boat_type'] == 'mixed']
        
        single_day = [r for r in unique_regattas if r['event_type'] == 'single_day']
        multi_day = [r for r in unique_regattas if r['event_type'] == 'multi_day']
        series = [r for r in unique_regattas if r['event_type'] == 'series']
        
        logger.info(f"   Yachts: {len(yachts)}")
        logger.info(f"   Dinghies: {len(dinghies)}")
        logger.info(f"   Mixed: {len(mixed)}")
        logger.info(f"   Single day: {len(single_day)}")
        logger.info(f"   Multi-day: {len(multi_day)}")
        logger.info(f"   Series: {len(series)}")
        
        # Always save all regattas for calendar
        self.save_regattas_json(unique_regattas)
        
        # Check for new events
        new_events = self.identify_new_events(unique_regattas)
        
        if new_events:
            logger.info(f"🆕 Found {len(new_events)} new events - sending Telegram message")
            message = self.format_telegram_message(new_events)
            
            if message:
                self.send_telegram_message(message)
            else:
                logger.warning("⚠️ No message generated for new events")
        else:
            logger.info("✅ No new events found - skipping Telegram notification")
        
        # Add error notification if no events found at all
        if not unique_regattas:
            logger.error("❌ No regattas found from any club - possible scraper failure")
            error_message = (
                "⚠️ SCRAPER ALERT ⚠️\n"
                "No sailing events found from any club.\n"
                "This might indicate a problem with the scraper.\n"
                f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M UTC')}"
            )
            self.send_telegram_message(error_message)
        
        logger.info("🏁 Scraper completed successfully!")

def main():
    """Main function"""
    # Get credentials from environment variables
    telegram_bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
    telegram_chat_id = os.getenv('TELEGRAM_CHAT_ID')
    
    if not telegram_bot_token or not telegram_chat_id:
        logger.warning("⚠️ Telegram credentials not found in environment variables")
        logger.info("Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID to enable notifications")
    
    # Initialize and run scraper
    scraper = SmartRegattaScraper(telegram_bot_token, telegram_chat_id)
    scraper.run()

if __name__ == "__main__":
    main()
