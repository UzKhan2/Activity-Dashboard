from flask import Flask, render_template, jsonify
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
import traceback
from trakt_api import TraktAPI
from collections import defaultdict
from flask import send_file
from PIL import Image
import io

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY', os.urandom(24))

# Initialize Trakt API
try:
    trakt = TraktAPI()
    if not trakt.access_token:
        print("Warning: No access token found. Authentication is required.")
except Exception as e:
    print(f"Error initializing TraktAPI: {str(e)}")
    print(traceback.format_exc())

@app.route('/')
def index():
    try:
        return render_template('index.html')
    except Exception as e:
        print(f"Error rendering index: {str(e)}")
        return "Error loading dashboard", 500

@app.route('/api/stats')
def get_stats():
    """Get overview statistics with accurate watch time and movie counts"""
    try:
        try:
            shows = trakt.get_watched_shows() or []
            movies = trakt.get_watched_movies() or []
            episodes = trakt.get_watched_episodes() or []
        except Exception as e:
            print(f"Error fetching data from Trakt: {str(e)}")
            print(traceback.format_exc())
            return jsonify({'error': 'Failed to fetch data from Trakt'}), 500

        print(f"Debug - Raw counts: Shows={len(shows)}, Movies={len(movies)}, Episodes={len(episodes)}")

        total_watch_time = 0
        
        # Calculate episode watch time
        for episode in episodes:
            try:
                if isinstance(episode, dict) and 'episode' in episode:
                    runtime = episode['episode'].get('runtime', 0)
                    if runtime:
                        total_watch_time += runtime
            except Exception as e:
                print(f"Error processing episode: {str(e)}")
                continue
        
        # Calculate movie watch time
        movies_count = 0
        for movie in movies:
            try:
                if isinstance(movie, dict) and 'movie' in movie:
                    runtime = movie['movie'].get('runtime', 0)
                    plays = movie.get('plays', 1)
                    if runtime:
                        total_watch_time += runtime * plays
                    movies_count += 1
            except Exception as e:
                print(f"Error processing movie: {str(e)}")
                continue

        total_hours = round(total_watch_time / 60, 1) if total_watch_time > 0 else 0
        
        stats = {
            'total_shows': len(shows),
            'total_movies': movies_count,
            'total_episodes': len(episodes),
            'total_watch_time': total_hours
        }
        
        print(f"Debug - Calculated stats: {stats}")
        return jsonify(stats)
        
    except Exception as e:
        print(f"Error in get_stats: {str(e)}")
        print(traceback.format_exc())
        return jsonify({'error': str(e)}), 500
        
@app.route('/api/shows')
def get_shows():
    """Get watched shows with formatted data including images"""
    try:
        try:
            shows = trakt.get_watched_shows() or []
        except Exception as e:
            print(f"Error fetching shows from Trakt: {str(e)}")
            return jsonify({'error': 'Failed to fetch shows from Trakt'}), 500

        formatted_shows = []
        for show in shows:
            if not isinstance(show, dict) or 'show' not in show:
                continue
                
            show_data = show['show']
            if not isinstance(show_data, dict):
                continue
            
            # Get image URLs directly from the TMDb data
            images = show_data.get('images', {})
            poster_url = images.get('poster_url')
            backdrop_url = images.get('backdrop_url')
            
            # Debug print
            print(f"\nDEBUG - Show: {show_data.get('title')}")
            print(f"Poster URL: {poster_url}")
            print(f"Backdrop URL: {backdrop_url}")
            
            formatted_shows.append({
                'title': show_data.get('title', ''),
                'year': show_data.get('year'),
                'overview': show_data.get('overview', ''),
                'runtime': show_data.get('runtime', 0),
                'plays': show.get('plays', 0),
                'episodes_watched': show.get('plays', 0),
                'total_episodes': show_data.get('aired_episodes', 0),
                'last_watched_at': show.get('last_watched_at', ''),
                'genres': show_data.get('genres', []),
                'rating': show_data.get('rating', 0),
                'status': show_data.get('status', ''),
                'network': show_data.get('network', ''),
                'poster_url': poster_url,
                'backdrop_url': backdrop_url
            })
        
        return jsonify(sorted(formatted_shows, 
                            key=lambda x: x['last_watched_at'] or '', 
                            reverse=True))
    except Exception as e:
        print(f"Error in get_shows: {str(e)}")
        return jsonify({'error': str(e)}), 500
        
@app.route('/api/movies')
def get_movies():
    """Get watched movies with formatted data"""
    try:
        print("Fetching movies...")  # Debug print
        try:
            movies = trakt.get_watched_movies() or []
        except Exception as e:
            print(f"Error fetching movies from Trakt: {str(e)}")
            print(traceback.format_exc())
            return jsonify({'error': 'Failed to fetch movies from Trakt'}), 500

        print(f"Debug - Raw movies count: {len(movies)}")  # Debug print
        
        formatted_movies = []
        for movie in movies:
            try:
                if not isinstance(movie, dict) or 'movie' not in movie:
                    print(f"Debug - Invalid movie format: {movie}")
                    continue
                
                movie_data = movie['movie']
                if not isinstance(movie_data, dict):
                    print(f"Debug - Invalid movie_data format: {movie_data}")
                    continue
                
                formatted_movies.append({
                    'title': movie_data.get('title', 'Unknown Title'),
                    'year': movie_data.get('year'),
                    'overview': movie_data.get('overview', ''),
                    'runtime': movie_data.get('runtime', 0),
                    'plays': movie.get('plays', 1),
                    'last_watched_at': movie.get('last_watched_at', ''),
                    'genres': movie_data.get('genres', []),
                    'rating': movie_data.get('rating', 0)
                })
            except Exception as e:
                print(f"Error processing movie: {str(e)}")
                print(traceback.format_exc())
                continue
        
        print(f"Debug - Formatted {len(formatted_movies)} movies")  # Debug print
        return jsonify(formatted_movies)
        
    except Exception as e:
        print(f"Error in get_movies: {str(e)}")
        print(traceback.format_exc())
        return jsonify({'error': str(e)}), 500

@app.route('/api/history')
def get_history():
    try:
        try:
            history = trakt.get_watch_history(limit=20) or []
        except Exception as e:
            print(f"Error fetching history from Trakt: {str(e)}")
            return jsonify({'error': 'Failed to fetch history from Trakt'}), 500

        formatted_history = []
        for item in history:
            if not isinstance(item, dict):
                continue
                
            history_item = {
                'type': item.get('type', ''),
                'watched_at': item.get('watched_at', ''),
            }
            
            if item.get('type') == 'episode' and 'episode' in item and 'show' in item:
                episode = item['episode']
                show = item['show']
                history_item.update({
                    'show_title': show.get('title', ''),
                    'episode_title': episode.get('title', ''),
                    'season': episode.get('season'),
                    'episode': episode.get('number'),
                    'full_episode_title': f"S{episode.get('season', 0):02d}E{episode.get('episode', 0):02d} - {episode.get('title', '')}",
                    'poster_url': show.get('images', {}).get('poster', {}).get('thumb')
                })
            elif 'movie' in item:
                movie = item['movie']
                history_item.update({
                    'movie_title': movie.get('title', ''),
                    'year': movie.get('year'),
                    'poster_url': movie.get('images', {}).get('poster', {}).get('thumb')
                })
                
            formatted_history.append(history_item)
        
        return jsonify(formatted_history)
    except Exception as e:
        print(f"Error in get_history: {str(e)}")
        return jsonify({'error': str(e)}), 500
    
@app.route('/api/watch-time')
def get_watch_time():
    try:
        try:
            history = trakt.get_watch_history(limit=1000) or []
        except Exception as e:
            print(f"Error fetching history from Trakt: {str(e)}")
            return jsonify({'error': 'Failed to fetch history from Trakt'}), 500

        monthly_stats = defaultdict(lambda: {
            'total_minutes': 0,
            'shows': set(),
            'movies': 0,
            'episodes': 0
        })
        
        for item in history:
            if not isinstance(item, dict):
                continue
                
            try:
                watched_at = datetime.strptime(item.get('watched_at', ''), '%Y-%m-%dT%H:%M:%S.%fZ')
                month_key = watched_at.strftime('%Y-%m')
                
                if item.get('type') == 'episode' and 'episode' in item and 'show' in item:
                    runtime = item['episode'].get('runtime', 0)
                    monthly_stats[month_key]['episodes'] += 1
                    monthly_stats[month_key]['shows'].add(item['show'].get('title', ''))
                elif 'movie' in item:
                    runtime = item['movie'].get('runtime', 0)
                    monthly_stats[month_key]['movies'] += 1
                else:
                    runtime = 0
                
                monthly_stats[month_key]['total_minutes'] += runtime
            except (ValueError, KeyError) as e:
                print(f"Error processing history item: {str(e)}")
                continue
        
        months = []
        for i in range(6):
            date = datetime.now() - timedelta(days=30*i)
            month_key = date.strftime('%Y-%m')
            
            if month_key in monthly_stats:
                stats = monthly_stats[month_key]
                shows_count = len(stats['shows'])
            else:
                stats = {'total_minutes': 0, 'shows': set(), 'movies': 0, 'episodes': 0}
                shows_count = 0
            
            months.append({
                'month': date.strftime('%b %Y'),
                'hours': round(stats['total_minutes'] / 60, 1),
                'shows': shows_count,
                'movies': stats['movies'],
                'episodes': stats['episodes']
            })
        
        return jsonify({
            'months': list(reversed(months)),
            'total_hours': round(sum(m['hours'] for m in months), 1)
        })
    except Exception as e:
        print(f"Error in get_watch_time: {str(e)}")
        return jsonify({'error': str(e)}), 500
    
@app.route('/api/placeholder/<int:width>/<int:height>')
def placeholder_image(width, height):
    """Generate a placeholder image with specified dimensions"""
    try:
        # Create a gray placeholder image
        img = Image.new('RGB', (width, height), color='#333333')
        
        # Save the image to a bytes buffer
        img_io = io.BytesIO()
        img.save(img_io, 'PNG')
        img_io.seek(0)
        
        return send_file(img_io, mimetype='image/png')
    except Exception as e:
        print(f"Error generating placeholder: {str(e)}")
        return jsonify({'error': 'Failed to generate placeholder'}), 500
    
@app.route('/static/js/<path:path>')
def send_js(path):
    return send_from_directory('static/js', path)

if __name__ == '__main__':
    load_dotenv()
    debug_mode = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    print("Starting Flask application...")
    print(f"Debug mode: {debug_mode}")
    print(f"Trakt API authenticated: {bool(trakt.access_token)}")
    app.run(debug=debug_mode, host='0.0.0.0', port=int(os.getenv('PORT', 5000)))