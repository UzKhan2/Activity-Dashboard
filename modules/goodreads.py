import os
import re
import requests
from datetime import datetime
from bs4 import BeautifulSoup
import xml.etree.ElementTree as ET
from collections import defaultdict
from typing import List, Dict, Any, Optional
from flask import Blueprint, render_template, jsonify

goodreads_bp = Blueprint('goodreads', __name__)

class GoodreadsAPI:
    def __init__(self):
        self.rating_cache = {}
        self.book_details_cache = {}

    def extract_review_id(self, url: str) -> Optional[str]:
        try:
            match = re.search(r'/show/(\d+)', url)
            if match:
                return match.group(1)
        except Exception as e:
            print(f"Error extracting review ID: {str(e)}")
        return None

    def get_book_details(self, book_id: str) -> Optional[Dict[str, Any]]:
        # Check cache first
        if book_id in self.book_details_cache:
            return self.book_details_cache[book_id]

        try:
            print(f"\nFetching details for book ID: {book_id}")
            url = f"https://www.goodreads.com/book/show/{book_id}"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            rating = None
            rating_element = soup.find('div', {'class': 'RatingStatistics__rating'})
            if rating_element:
                try:
                    rating = float(rating_element.text.strip())
                    print(f"Found rating: {rating} stars")
                except ValueError:
                    print("Could not parse rating value")
            else:
                print("Rating element not found")
                    
            image_url = None
            try:
                img_element = soup.find('img', {'class': 'ResponsiveImage'})
                if img_element and 'src' in img_element.attrs:
                    image_url = img_element['src']
                    if '_SY' in image_url:
                        image_url = re.sub(r'_SY\d+_', '_SY1000_', image_url)
                    if '_SX' in image_url:
                        image_url = re.sub(r'_SX\d+_', '_SX1000_', image_url)
                    print(f"Found high quality image: {image_url}")
                else:
                    print("Could not find high quality image")
            except Exception as e:
                print(f"Error extracting image URL: {str(e)}")
                    
            pages = None
            author = None
            
            # Look for author
            author_element = soup.find('span', {'class': 'ContributorLink__name'}) or \
                            soup.find('a', {'class': 'ContributorLink'}) or \
                            soup.find('a', {'class': 'authorName'})
            
            if author_element:
                author = author_element.text.strip()
                print(f"Found author: {author}")
            else:
                print("Author element not found")
            
            # Look for page count from different pormats
            page_patterns = [
                r'(\d+)\s*pages',
                r'Paperback,\s*(\d+)\s*pages',
                r'Hardcover,\s*(\d+)\s*pages',
                r'ebook,\s*(\d+)\s*pages',
                r'Kindle\s*Edition,\s*(\d+)\s*pages'
            ]
            
            text_elements = soup.find_all(['div', 'span', 'p'])
            for element in text_elements:
                if element.text:
                    for pattern in page_patterns:
                        match = re.search(pattern, element.text, re.IGNORECASE)
                        if match:
                            try:
                                pages = int(match.group(1))
                                print(f"Found pages: {pages}")
                                break
                            except ValueError:
                                continue
                if pages:
                    break
                    
            if pages is None:
                print("Page count not found")
            
            details = {
                "rating": rating,
                "pages": pages,
                "author": author,
                "image_url": image_url
            }
            
            # Store in cache
            self.book_details_cache[book_id] = details
            return details
                
        except Exception as e:
            print(f"Error fetching book details for book ID {book_id}: {str(e)}")
            return None

    def parse_goodreads_rss(self, xml_content: str) -> List[Dict[str, Any]]:
        if not xml_content or not xml_content.strip():
            print("Warning: Empty XML content received")
            return []
            
        try:
            root = ET.fromstring(xml_content)
        except ET.ParseError as e:
            print(f"XML parsing error: {str(e)}")
            return []
        
        books = []
        
        for item in root.findall('.//item'):
            try:
                title = item.find('title')
                description = item.find('description')
                link = item.find('link')
                
                if title is not None and description is not None and description.text:
                    title_text = title.text.strip()
                    desc_text = description.text
                    
                    book_info = {
                        'title': title_text,
                        'author': 'Unknown Author',
                        'rating': None,
                        'date_read': None,
                        'link': None,
                        'image_url': '/api/placeholder/200/300',
                        'pages': None
                    }
                    
                    if ' stars to ' in title_text:
                        try:
                            title_parts = title_text.split(' stars to ')
                            if len(title_parts) > 1:
                                book_title_author = title_parts[1].strip()
                                if ' by ' in book_title_author:
                                    book_title, _ = book_title_author.split(' by ', 1)
                                    book_info['title'] = book_title.strip()
                        except Exception as e:
                            print(f"Error extracting title: {str(e)}")
                    
                    # Get link
                    if link is not None and link.text:
                        book_info['link'] = link.text.strip()
                    
                    # Get book ID and fetch additional details
                    try:
                        href_start = desc_text.find('href="/book/show/')
                        if href_start >= 0:
                            start_idx = href_start + len('href="/book/show/')
                            end_idx = desc_text.find('"', start_idx)
                            if end_idx > start_idx:
                                book_id = desc_text[start_idx:end_idx].split('-')[0]
                                book_details = self.get_book_details(book_id)
                                
                                if book_details:
                                    book_info['rating'] = book_details.get('rating')
                                    book_info['pages'] = book_details.get('pages')
                                    if book_details.get('author'):
                                        book_info['author'] = book_details['author']
                                    if book_details.get('image_url'):
                                        book_info['image_url'] = book_details['image_url']
                    except Exception as e:
                        print(f"Error getting book details: {str(e)}")
                    
                    # Extract date
                    pub_date = item.find('pubDate')
                    if pub_date is not None and pub_date.text:
                        try:
                            date_obj = datetime.strptime(pub_date.text.strip(), '%a, %d %b %Y %H:%M:%S %z')
                            book_info['date_read'] = date_obj.isoformat()
                        except ValueError as e:
                            print(f"Error parsing date: {str(e)}")
                            book_info['date_read'] = pub_date.text.strip()
                    
                    books.append(book_info)
                    
            except Exception as e:
                print(f"Error processing book item: {str(e)}")
                continue

        return books

    
    def extract_date_read(self, description_element: ET.Element) -> Optional[str]:
        #Extract the date read from the description
        if description_element is None or not description_element.text:
            return None
            
        try:
            date_match = re.search(r'(\w+ \d{1,2}, \d{4})', description_element.text)
            if date_match:
                date_str = date_match.group(1)
                date_obj = datetime.strptime(date_str, '%B %d, %Y')
                return date_obj.isoformat()
        except Exception as e:
            print(f"Error extracting date read: {str(e)}")
        return None

    def calculate_stats(self, books: List[Dict[str, Any]]) -> Dict[str, Any]:
        #Calculate reading statistics from the book list
        if not books:
            return {
                "total_books": 0,
                "average_rating": 0,
                "total_pages": 0,
                "books_per_month": 0
            }
        
        total_books = len(books)
        rated_books = [book for book in books if book.get('rating')]
        average_rating = sum(book['rating'] for book in rated_books) / len(rated_books) if rated_books else 0
        total_pages = sum(book.get('pages', 0) for book in books)
        
        # Calculate books per month
        if books and 'date_read' in books[0]:
            dates = [datetime.fromisoformat(book['date_read']) for book in books if book.get('date_read')]
            if dates:
                date_range = max(dates) - min(dates)
                months = date_range.days / 30.44  # Average days per month
                books_per_month = total_books / months if months > 0 else total_books
            else:
                books_per_month = 0
        else:
            books_per_month = 0
        
        return {
            "total_books": total_books,
            "average_rating": round(average_rating, 2),
            "total_pages": total_pages,
            "books_per_month": round(books_per_month, 1)
        }

    def calculate_reading_stats(self, books: List[Dict[str, Any]]) -> Dict[str, Any]:
        #Calculate monthly reading statistics
        monthly_stats = defaultdict(int)
        
        for book in books:
            if book.get('date_read'):
                try:
                    date = datetime.fromisoformat(book['date_read'])
                    month_key = date.strftime('%Y-%m')
                    monthly_stats[month_key] += 1
                except (ValueError, TypeError):
                    continue
        
        # Convert to sorted list of months
        months = [
            {"month": k, "books_read": v}
            for k, v in sorted(monthly_stats.items())
        ]
        
        return {"months": months}

goodreads_api = GoodreadsAPI()

@goodreads_bp.route('/goodreads')
def goodreads_dashboard():
    return render_template('goodreads.html')

@goodreads_bp.route('/api/goodreads/books')
def goodreads_books():
    try:
        rss_url = os.getenv('GOODREADS_RSS_URL')
        if not rss_url:
            raise ValueError("Goodreads RSS URL not configured")
            
        xml_content = fetch_rss_feed(rss_url, feed_type='goodreads')
        books = goodreads_api.parse_goodreads_rss(xml_content)
        books.sort(key=lambda x: x.get('date_read', ''), reverse=True)
        
        return jsonify(books)
    except Exception as e:
        print(f"Error fetching books: {str(e)}")
        return jsonify({"error": str(e)}), 500

@goodreads_bp.route('/api/goodreads/stats')
def goodreads_stats():
    try:
        rss_url = os.getenv('GOODREADS_RSS_URL')
        if not rss_url:
            raise ValueError("Goodreads RSS URL not configured")
            
        xml_content = fetch_rss_feed(rss_url, feed_type='goodreads')
        books = goodreads_api.parse_goodreads_rss(xml_content)
        stats = goodreads_api.calculate_stats(books)
        
        return jsonify(stats)
    except Exception as e:
        print(f"Error fetching stats: {str(e)}")
        return jsonify({"error": str(e)}), 500

@goodreads_bp.route('/api/goodreads/history')
def goodreads_history():
    try:
        rss_url = os.getenv('GOODREADS_RSS_URL')
        if not rss_url:
            raise ValueError("Goodreads RSS URL not configured")
            
        xml_content = fetch_rss_feed(rss_url, feed_type='goodreads')
        books = goodreads_api.parse_goodreads_rss(xml_content)
        books.sort(key=lambda x: x.get('date_read', ''), reverse=True)
        
        return jsonify(books)
    except Exception as e:
        print(f"Error fetching history: {str(e)}")
        return jsonify({"error": str(e)}), 500

@goodreads_bp.route('/api/goodreads/reading-stats')
def goodreads_reading_stats():
    try:
        rss_url = os.getenv('GOODREADS_RSS_URL')
        if not rss_url:
            raise ValueError("Goodreads RSS URL not configured")
            
        xml_content = fetch_rss_feed(rss_url, feed_type='goodreads')
        books = goodreads_api.parse_goodreads_rss(xml_content)
        reading_stats = goodreads_api.calculate_reading_stats(books)
        
        return jsonify(reading_stats)
    except Exception as e:
        print(f"Error fetching reading stats: {str(e)}")
        return jsonify({"error": str(e)}), 500

def init_goodreads_routes(app, feed_fetcher):
    global fetch_rss_feed
    fetch_rss_feed = feed_fetcher
    app.register_blueprint(goodreads_bp)