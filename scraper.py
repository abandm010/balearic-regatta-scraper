#!/usr/bin/env python3
"""
Balearic Islands Sailing Regatta Scraper - FINAL IMPROVED VERSION
Scrapes regatta information from sailing club websites and posts to Telegram
Includes: Date filtering, content filtering, better translations, calendar link
"""

import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime, timedelta
import json
import time
import logging
import os
import urllib.parse

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class RegattaScraper:
    def __init__(self, telegram_bot_token=None, telegram_chat_id=None):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        
        # Telegram setup
        self.telegram_bot_token = telegram_bot_token
        self.telegram_chat_id = telegram_chat_id
        
        # Keywords to identify regatta content (improved list)
        self.regatta_keywords = [
            # Spanish
            'regata', 'copa', 'trofeo', 'campeonato', 'competición', 'torneo', 
            'inscripción', 'inscripciones', 'calendario', 'evento', 'series',
            'vuelta', 'memorial', 'navegación', 'vela', 'náutico',
            # Catalan  
            'regata', 'competició', 'torneig', 'campionat', 'inscripció', 'inscripcions',
            'calendari', 'esdeveniment', 'vela', 'nàutic', 'trofeu',
            # English
            'regatta', 'race', 'sailing', 'competition', 'championship', 'registration',
            'event', 'tournament', 'yacht', 'boat', 'cup', 'trophy',
            # German
            'regatta', 'wettfahrt', 'segelregatta', 'wettbewerb', 'meisterschaft',
            'anmeldung', 'veranstaltung', 'segeln',
            # Special event names
            'mapfre', 'palmavela', 'princesa', 'sofia'
        ]
        
        # FILTER OUT: Administrative/irrelevant content
        self.exclude_keywords = [
            'results', 'resultados', 'resultado', 'resultat',
            'latest news', 'noticias', 'notícies', 'news',
            'regattas office', 'oficina de regatas', 'oficina',
            'finished regatta', 'regata finalizada', 'regata acabada',
            'next tank tops', 'próximas camisetas',
            'read more', 'leer más', 'llegir més', 'more information',
            'this sunday has begun', 'este domingo ha comenzado'
        ]
        
        # Improved date patterns for Spanish dates
        self.date_patterns = [
            r'\bdel\s+\d{1,2}\s+de\s+\w+\s+al\s+\d{1,2}\s+de\s+\w+\s+de\s+\d{4}\b',  # del X de mes al Y de mes de año
            r'\bdel\s+\d{1,2}\s+al\s+\d{1,2}\s+de\s+\w+\s+de\s+\d{4}\b',  # del X al Y de mes de año
            r'\b\d{1,2}\s+de\s+\w+\s+de\s+\d{4}\b',  # X de mes de año
            r'\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b',  # DD/MM/YYYY
            r'\b\d{4}-\d{1,2}-\d{1,2}\b',  # YYYY-MM-DD
            r'\b\w+\s+\d{1,2},?\s+\d{4}\b',  # Month DD, YYYY
        ]
        
        # Sailing-specific translation dictionary
        self.sailing_translations = {
            'optimistic': 'optimist',
            'ilca': 'ILCA',
            'orc': 'ORC',
            'crucero': 'cruiser',
            'vela latina': 'latin sail',
            'master': 'Masters',
            'trofeo': 'trophy',
            'copa': 'cup',
            'campeonato': 'championship'
        }

    def is_future_event(self, date_str):
        """Check if event date is in the future (2025 or later, after current date)"""
        try:
            current_date = datetime.now()
            
            # Extract year from date string
            year_match = re.search(r'\b(20\d{2})\b', date_str)
            if year_match:
                year = int(year_match.group(1))
                # Only accept events from 2025 onwards
                if year < 2025:
                    return False
                # For 2025 events, check if they're after current date
                if year == 2025:
                    # Simple month check for 2025 events
                    month_names = {
                        'enero': 1, 'febrero': 2, 'marzo': 3, 'abril': 4, 'mayo': 5, 'junio': 6,
                        'julio': 7, 'agosto': 8, 'septiembre': 9, 'octubre': 10, 'noviembre': 11, 'diciembre': 12
                    }
                    for month_name, month_num in month_names.items():
                        if month_name in date_str.lower():
                            # If it's a month that has passed in 2025, exclude it
                            if month_num < current_date.month:
                                return False
                            break
                return True
            
            # If no year found, assume it's current year and check if reasonable
            return True
            
        except:
            # If date parsing fails, include the event (better safe than sorry)
            return True

    def is_relevant_regatta(self, title, details):
        """Check if this is a relevant regatta (not results, news, etc.)"""
        combined_text = f"{title} {details}".lower()
        
        # Check if it contains excluded keywords
        for exclude_word in self.exclude_keywords:
            if exclude_word.lower() in combined_text:
                return False
        
        # Check for garbled text (too many question marks)
        if '????????' in combined_text:
            return False
            
        # Must contain at least one regatta keyword
        has_regatta_keyword = any(
            keyword.lower() in combined_text 
            for keyword in self.regatta_keywords
        )
        
        return has_regatta_keyword

    def translate_to_english_improved(self, text):
        """Improved translation with sailing-specific terms"""
        try:
            # First, apply sailing-specific translations
            improved_text = text
            for spanish_term, english_term in self.sailing_translations.items():
                improved_text = re.sub(rf'\b{spanish_term}\b', english_term, improved_text, flags=re.IGNORECASE)
            
            # Use the simple web interface approach
            url = 'https://translate.googleapis.com/translate_a/single'
            params = {
                'client': 'gtx',
                'sl': 'auto',
                'tl': 'en',
                'dt': 't',
                'q': improved_text[:500]  # Limit length to avoid issues
            }
            
            response = requests.get(url, params=params, timeout=10)
            if response.status_code == 200:
                result = response.json()
                if result and len(result) > 0 and len(result[0]) > 0:
                    translated = result[0][0][0]
                    detected_lang = result[2] if len(result) > 2 else 'unknown'
                    
                    # Post-process translation for better sailing terms
                    translated = re.sub(r'\boptimistic\b', 'Optimist', translated, flags=re.IGNORECASE)
                    translated = re.sub(r'\bilca\b', 'ILCA', translated, flags=re.IGNORECASE)
                    translated = re.sub(r'\borc\b', 'ORC', translated, flags=re.IGNORECASE)
                    
                    return translated, detected_lang
            
            # If translation fails, return improved original text
            return improved_text, 'unknown'
            
        except Exception as e:
            logger.warning(f"Translation failed: {str(e)}, returning original text")
            return text, 'unknown'

    def send_to_telegram(self, message):
        """Send message to Telegram group with improved error handling"""
        if not self.telegram_bot_token or not self.telegram_chat_id:
            logger.warning("Telegram credentials not provided, skipping send")
            return False
            
        try:
            url = f"https://api.telegram.org/bot{self.telegram_bot_token}/sendMessage"
            
            # Split long messages
            max_length = 4000
            if len(message) > max_length:
                messages = [message[i:i+max_length] for i in range(0, len(message), max_length)]
            else:
                messages = [message]
            
            for msg in messages:
                data = {
                    'chat_id': self.telegram_chat_id,
                    'text': msg,
                    'parse_mode': 'Markdown',
                    'disable_web_page_preview': False
                }
                
                response = requests.post(url, data=data, timeout=10)
                response.raise_for_status()
                time.sleep(1)  # Rate limiting
            
            logger.info(f"Sent {len(messages)} message(s) to Telegram successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error sending to Telegram: {str(e)}")
            return False

    def scrape_club(self, club_name, url, timeout=15):
        """
        Scrape regatta information from a sailing club website with improved error handling
        """
        try:
            logger.info(f"Scraping {club_name}: {url}")
            
            response = self.session.get(url, timeout=timeout)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Remove script and style elements
            for script in soup(["script", "style"]):
                script.decompose()
            
            # Get text content
            text = soup.get_text()
            
            # Extract regatta events using improved logic
            regattas = self.extract_regatta_events(text, url, club_name)
            
            logger.info(f"Found {len(regattas)} relevant regattas at {club_name}")
            return regattas
            
        except requests.exceptions.Timeout:
            logger.error(f"Timeout scraping {club_name} ({url})")
            return []
        except requests.exceptions.RequestException as e:
            logger.error(f"Request error scraping {club_name} ({url}): {str(e)}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error scraping {club_name} ({url}): {str(e)}")
            return []

    def extract_regatta_events(self, text, source_url, club_name):
        """Extract regatta events using improved multi-line pattern matching with filtering"""
        regattas = []
        
        # Split text into lines and clean
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        
        # Look for regatta events as groups: title + date + details
        for i in range(len(lines) - 1):
            current_line = lines[i]
            next_line = lines[i + 1] if i + 1 < len(lines) else ''
            third_line = lines[i + 2] if i + 2 < len(lines) else ''
            
            # Skip very short or very long lines
            if len(current_line) < 5 or len(current_line) > 200:
                continue
            
            # Check if current line contains regatta keywords
            has_regatta_keyword = any(
                keyword.lower() in current_line.lower() 
                for keyword in self.regatta_keywords
            )
            
            # Check if next line contains dates
            dates_found = []
            for pattern in self.date_patterns:
                matches = re.findall(pattern, next_line, re.IGNORECASE)
                dates_found.extend(matches)
            
            # If we found a regatta title and dates, check if it's relevant
            if has_regatta_keyword and dates_found:
                # Clean up the dates (remove duplicates)
                unique_dates = list(set(dates_found))
                
                # Filter out irrelevant content and old events
                if not self.is_relevant_regatta(current_line, third_line):
                    continue
                    
                # Filter out past events
                if not any(self.is_future_event(date) for date in unique_dates):
                    continue
                
                regatta = {
                    'club': club_name,
                    'title': current_line,
                    'dates': unique_dates,
                    'details': third_line[:100] if third_line else '',
                    'description': f"{current_line} - {unique_dates[0]}" + (f" - {third_line[:50]}" if third_line else ""),
                    'source_url': source_url,
                    'scraped_at': datetime.now().isoformat()
                }
                
                regattas.append(regatta)
        
        # Remove duplicates and return
        return self.remove_duplicates(regattas)

    def remove_duplicates(self, regattas):
        """Remove duplicate regattas based on title similarity"""
        unique = []
        
        for regatta in regattas:
            is_duplicate = False
            for existing in unique:
                # Check if titles are very similar (first 40 chars)
                if regatta['title'][:40].lower() == existing['title'][:40].lower():
                    is_duplicate = True
                    break
            
            if not is_duplicate:
                unique.append(regatta)
        
        return unique

    def format_regatta_message(self, regattas):
        """Format regatta information for Telegram with improved layout and calendar link"""
        if not regattas:
            return "🏁 No upcoming regattas found today."
        
        # Sort regattas by date and club
        try:
            regattas.sort(key=lambda x: (x['club'], x['dates'][0] if x['dates'] else 'zzz'))
        except:
            pass  # If sorting fails, keep original order
        
        message_parts = [
            "⛵ **Balearic Sailing Regattas** ⛵\n",
            "📅 [**View Full Calendar**](https://abandm010.github.io/balearic-regatta-scraper)\n"
        ]
        
        current_club = ""
        regatta_count = 0
        
        for regatta in regattas[:15]:  # Limit to 15 to avoid message length issues
            regatta_count += 1
            
            # Group by club with separators
            if regatta['club'] != current_club:
                if current_club:  # Add separator between clubs
                    message_parts.append("---")
                current_club = regatta['club']
            
            # Translate title if needed
            english_title, source_lang = self.translate_to_english_improved(regatta['title'])
            
            # Format dates nicely
            dates_str = regatta['dates'][0] if regatta['dates'] else 'Date TBD'
            
            # Clean up the club name display
            club_display = regatta['club'].replace('CN ', '').replace('Real Club Náutico de ', 'RCN ')
            
            message_parts.append(f"**{regatta_count}. {club_display}**")
            message_parts.append(f"🏆 {english_title}")
            message_parts.append(f"📅 {dates_str}")
            
            if regatta['details'] and not any(exclude in regatta['details'].lower() for exclude in self.exclude_keywords):
                english_details, _ = self.translate_to_english_improved(regatta['details'])
                message_parts.append(f"⛵ {english_details}")
            
            message_parts.append(f"🔗 [More info]({regatta['source_url']})")
            
            if source_lang not in ['en', 'unknown']:
                message_parts.append(f"🌐 _(Translated from {source_lang})_")
                
            message_parts.append("")  # Empty line between regattas
        
        if len(regattas) > 15:
            message_parts.append(f"... and {len(regattas) - 15} more upcoming regattas!")
        
        message_parts.append(f"🤖 _Updated: {datetime.now().strftime('%Y-%m-%d %H:%M UTC')}_")
        
        return "\n".join(message_parts)

def main():
    """Main scraping function with improved error handling and filtering"""
    # Get credentials from environment variables
    telegram_bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
    telegram_chat_id = os.getenv('TELEGRAM_CHAT_ID')
    
    scraper = RegattaScraper(telegram_bot_token, telegram_chat_id)
    
    # Curated list of working sailing club websites
    clubs = [
        {
            'name': 'CN Port d\'Ítxol',
            'url': 'https://www.cnportitxol.info/regatas/',
        },
        {
            'name': 'Real Club Náutico de Palma',
            'url': 'https://www.rcnp.es/regatas',
        },
        {
            'name': 'Copa del Rey MAPFRE',
            'url': 'https://www.regatacopadelrey.com/home',
        },
        {
            'name': 'PalmaVela',
            'url': 'https://www.palmavela.com/',
        },
        {
            'name': 'CN Ciutadella',
            'url': 'https://regates.cnciutadella.com/es/default/races',
        },
        {
            'name': 'CN Arenal',
            'url': 'https://regatas.cnarenal.com/es/default/races',
        },
        {
            'name': 'Club Marítimo San Antonio',
            'url': 'https://www.cmsap.com/en/default/races/calendar',
        },
        {
            'name': 'RCN Port de Pollença',
            'url': 'https://regatas.rcnpp.club/es/default/races',
        },
        # Add more clubs gradually after testing
    ]
    
    all_regattas = []
    successful_scrapes = 0
    
    for club in clubs:
        logger.info(f"Processing {club['name']}...")
        
        try:
            regattas = scraper.scrape_club(club['name'], club['url'])
            if regattas:
                all_regattas.extend(regattas)
                successful_scrapes += 1
            
            # Be polite - wait between requests
            time.sleep(3)
            
        except Exception as e:
            logger.error(f"Failed to process {club['name']}: {str(e)}")
            continue
    
    logger.info(f"Successfully scraped {successful_scrapes}/{len(clubs)} clubs")
    logger.info(f"Total relevant regattas found: {len(all_regattas)}")
    
    # Save results to file
    with open('regattas.json', 'w', encoding='utf-8') as f:
        json.dump(all_regattas, f, indent=2, ensure_ascii=False)
    
    # Send to Telegram if we found regattas
    if all_regattas:
        message = scraper.format_regatta_message(all_regattas)
        
        # Always print the message for debugging
        print("\n" + "="*60)
        print("GENERATED TELEGRAM MESSAGE:")
        print("="*60)
        print(message)
        print("="*60)
        
        # Send to Telegram if configured
        if telegram_bot_token and telegram_chat_id:
            success = scraper.send_to_telegram(message)
            if success:
                logger.info("✅ Message sent to Telegram successfully")
            else:
                logger.error("❌ Failed to send message to Telegram")
        else:
            logger.info("ℹ️  Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID to send to Telegram")
    
    else:
        logger.warning("No relevant upcoming regattas found")
    
    # Print summary
    print(f"\n📊 SCRAPING SUMMARY:")
    print(f"   Clubs processed: {len(clubs)}")
    print(f"   Successful scrapes: {successful_scrapes}")
    print(f"   Relevant upcoming regattas: {len(all_regattas)}")
    print(f"   Data saved to: regattas.json")

if __name__ == "__main__":
    main()
