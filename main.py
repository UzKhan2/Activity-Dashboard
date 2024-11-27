import os
from dotenv import load_dotenv
from flask import Flask, render_template, send_from_directory

from modules.github import init_github_routes
from modules.letterboxd import init_letterboxd_routes
from modules.goodreads import init_goodreads_routes
from modules.trueachievements import init_trueachievements_routes
from modules.myanimelist import init_myanimelist_routes
from modules.trakt import init_trakt_routes, TraktAPI
from modules.utils import fetch_rss_feed, generate_placeholder_image

def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY', os.urandom(32))
    
    # Set up Trakt API for watch time data #-- Add in other time stats
    try:
        trakt = TraktAPI()
        if not trakt.access_token:
            print("Warning: No access token found. Authentication is required.")
    except Exception as e:
        print(f"Error initializing TraktAPI: {str(e)}")
        trakt = None

    # Initialize modules routes
    init_github_routes(app)
    init_letterboxd_routes(app, trakt, fetch_rss_feed)
    init_goodreads_routes(app, fetch_rss_feed)
    init_trueachievements_routes(app)
    init_myanimelist_routes(app, fetch_rss_feed)
    init_trakt_routes(app)

    # Home page
    @app.route('/')
    def home():
        try:
            return render_template('index.html')
        except Exception as e:
            print(f"Error rendering home: {str(e)}")
            return "Error loading home page", 500

    # Utility routes
    @app.route('/api/placeholder/<int:width>/<int:height>')
    def placeholder_image(width, height):
        return generate_placeholder_image(width, height)
    
    @app.route('/static/js/<path:path>')
    def send_js(path):
        return send_from_directory('static/js', path)

    return app

def main():
    load_dotenv()
    app = create_app()
    
    debug_mode = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    port = int(os.getenv('PORT', 5000))
    
    print("Starting Flask application...")
    print(f"Debug mode: {debug_mode}")
    
    app.run(
        debug=debug_mode,
        host='0.0.0.0',
        port=port
    )

if __name__ == '__main__':
    main()