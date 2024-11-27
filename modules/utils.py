import io
import requests
from PIL import Image
from typing import Any
from flask import send_file

def fetch_rss_feed(url: str, feed_type: str = 'generic') -> str:
    try:
        headers = {}
        
        if feed_type == 'goodreads':
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'application/rss+xml, application/xml, application/atom+xml, text/xml;q=0.9, */*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive'
            }
        elif feed_type == 'letterboxd':
            headers = {
                'User-Agent': 'Mozilla/5.0',
                'Accept': 'application/rss+xml, application/xml'
            }
        elif feed_type == 'myanimelist':
            headers = {
                'User-Agent': 'Mozilla/5.0',
                'Accept': 'application/rss+xml, application/xml'
            }
            
        # Send request with appropriate headers
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        # Print response details 
        print(f"Response status code: {response.status_code}")
        print(f"Response headers: {response.headers}")
        
        # Check RSS feed in in xml
        content_type = response.headers.get('Content-Type', '').lower()
        if not ('xml' in content_type or 'rss' in content_type):
            print(f"Warning: Unexpected content type: {content_type}")
        
        return response.text
        
    except requests.RequestException as e:
        print(f"Error fetching RSS feed: {str(e)}")
        print(f"Response details (if available): {getattr(e.response, 'text', 'No response text')}")
        raise

def generate_placeholder_image(width: int, height: int) -> Any:
    try:
        # Generate placeholder image
        img = Image.new('RGB', (width, height), color='#333333')
        
        # Save image to a bytes buffer
        img_io = io.BytesIO()
        img.save(img_io, 'PNG')
        img_io.seek(0)
        
        return send_file(img_io, mimetype='image/png')
    except Exception as e:
        print(f"Error generating placeholder: {str(e)}")
        raise